from fastapi import FastAPI, Depends, HTTPException, status, APIRouter, WebSocket, WebSocketDisconnect
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from celery.result import AsyncResult
from datetime import timedelta
import redis.asyncio as redis
from prometheus_fastapi_instrumentator import Instrumentator
import uvicorn
import bcrypt
import hashlib
import json
import time
import asyncio
from model.schemas import CropPredictionRequest
from users.auth import verify_token, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES, decode_token
from services.worker import celery_app, process_crop_prediction

# --- NEW: Database Imports ---
from model.session import get_db, get_read_db
from model.models import User, Prediction

app = FastAPI(title="TerraSense AI REST API")
redis_client = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]

    async def send_personal_message(self, message: str, client_id: str):
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            await websocket.send_text(message)

manager = ConnectionManager()

# Background Task: Listen to Redis for Celery updates
async def redis_listener():
    pubsub = redis_client.pubsub()
    await pubsub.subscribe("celery_websocket_updates")
    
    async for message in pubsub.listen():
        if message["type"] == "message":
            data = json.loads(message["data"])
            client_id = str(data.get("user_id"))
            # Push payload to specific user's WebSocket
            await manager.send_personal_message(json.dumps(data), client_id)

#Lua Script for Token Bucket Rate Limiter
# ARGV = capacity (5), ARGV = refill_rate per sec, ARGV = current_time
TOKEN_BUCKET_LUA = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local requested = 1

local bucket = redis.call("HMGET", key, "tokens", "last_refill")
local tokens = tonumber(bucket[1])
local last_refill = tonumber(bucket[2])

if not tokens then
    tokens = capacity
    last_refill = now
else
    local elapsed = now - last_refill
    local refill = math.floor(elapsed * refill_rate)
    tokens = math.min(capacity, tokens + refill)
    if refill > 0 then
        last_refill = now
    end
end

if tokens >= requested then
    redis.call("HMSET", key, "tokens", tokens - requested, "last_refill", last_refill)
    redis.call("EXPIRE", key, 60) -- Clean up idle buckets after 60s
    return 1 -- Allowed
else
    return 0 -- Rate Limited
end
"""

async def check_rate_limit(user_id: int):
    # 5 tokens max, refills at 5 tokens per 60 seconds (0.083/sec)
    is_allowed = await redis_client.eval(
        TOKEN_BUCKET_LUA, 1, f"rate_limit:{user_id}", 5, 0.083, time.time()
    )
    if not is_allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Maximum 5 predictions per minute.")

# --- NEW: Helper to get the full Database User from the JWT token ---
def get_current_user(token_payload: dict = Depends(verify_token), db: Session = Depends(get_read_db)):
    username = token_payload.get("sub")
    user = db.query(User).filter(User.email == username).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


# --- NEW: Sign-Up Route (To create your real account in PostGIS) ---
@app.post("/signup")
async def signup(email: str, password: str, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    salt = bcrypt.gensalt()
    hashed_pwd = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    new_user = User(email=email, hashed_password=hashed_pwd)
    db.add(new_user)
    db.commit()
    return {"message": "User created successfully. You can now log in at /token"}


# --- 1. Sign-In Route (UPDATED) ---
@app.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_read_db)):
    # Find user in the PostGIS database
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not bcrypt.checkpw(form_data.password.encode('utf-8'), user.hashed_password.encode('utf-8')):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # If successful, create a token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, 
        expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

# Start listener when FastAPI boots
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(redis_listener())

# The WebSocket Endpoint
@app.websocket("/api/v1/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    db: Session = Depends(get_read_db)
):
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)
        return
    try:
        payload = decode_token(token)
        email = payload.get("sub")
        user = (
            db.query(User)
            .filter(User.email == email)
            .first()
        )
        if not user:
            await websocket.close(code=1008)
            return
        client_id = str(user.id)
        await manager.connect(
            websocket,
            client_id
        )
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            manager.disconnect(client_id)
    except Exception:
        await websocket.close(code=1008)

# --- 2. Protected Prediction Route (UPDATED) ---
@app.post("/api/v1/predict")
async def predict_crop(request: CropPredictionRequest, current_user: User = Depends(get_current_user)):
    
    # 1. Enforce Rate Limit
    await check_rate_limit(current_user.id)
    
    # Convert Pydantic request to a dictionary
    payload = request.dict()
    
    image_hash = hashlib.md5(
        payload["image_base64"].encode()
    ).hexdigest()
    
    # 2. Generate Cache Key based on coordinates and input parameters
    cache_string = (
        f"{payload['lat']}_"
        f"{payload['lon']}_"
        f"{payload['acres']}_"
        f"{payload['N']}_"
        f"{payload['P']}_"
        f"{payload['K']}_"
        f"{payload['ph']}_"
        f"{image_hash}"
    )
    cache_key = f"cache:predict:{hashlib.md5(cache_string.encode()).hexdigest()}"
    
    # 3. Read-Through Cache Check
    cached_result = await redis_client.get(cache_key)
    if cached_result:
        return {"status": "SUCCESS", "source": "redis_cache", "data": json.loads(cached_result)}
    
    # INJECT the real user_id so the Celery worker knows who to save the PostGIS polygon for!
    payload["user_id"] = current_user.id 
    payload["cache_key"] = cache_key
    
    # Safely push the job to the RabbitMQ queue
    task = process_crop_prediction.delay(payload)
    
    return {
        "message": "Prediction job accepted and placed in queue.",
        "task_id": task.id,
        "check_status_url": f"/api/v1/status/{task.id}"
    }
    

# --- 3. Get the Result (UNCHANGED logic, but protected) ---
@app.get("/api/v1/status/{task_id}")
async def get_task_status(task_id: str, current_user: User = Depends(get_current_user)):
    
    # Check the Redis backend to see if the Celery worker has finished
    task_result = AsyncResult(task_id, app=celery_app)
    
    response = {
        "task_id": task_id,
        "status": task_result.status,
    }
    
    if task_result.status == 'SUCCESS':
        response["data"] = task_result.result
    elif task_result.status == 'FAILURE':
        response["error"] = str(task_result.result)
        
    return response


# --- 4. NEW: View Spatial History ---
@app.get("/api/v1/history")
async def get_user_history(current_user: User = Depends(get_current_user), db: Session = Depends(get_read_db)):
    # Fetch all past predictions for this specific user
    predictions = db.query(Prediction).filter(Prediction.user_id == current_user.id).all()
    
    return [
        {
            "prediction_id": p.id,
            "crop": p.recommended_crop,
            "soil": p.detected_soil,
            "ndvi": p.satellite_ndvi,
            "location_wkt": db.scalar(p.location.ST_AsText()), # Converts PostGIS binary to readable text
            "date": p.created_at
        } 
        for p in predictions
    ]

instrumentator = Instrumentator()
instrumentator.instrument(app).expose(app)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)