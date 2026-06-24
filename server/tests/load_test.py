import asyncio
import websockets
import json
import aiohttp

API_URL = "http://localhost:8000/predict"
WS_URL = "ws://localhost:8000/api/v1/ws"

async def simulate_user(user_id: int):
    # 1. Open WebSocket connection
    ws_endpoint = f"{WS_URL}/{user_id}"
    
    try:
        async with websockets.connect(ws_endpoint) as websocket:
            print(f"[User {user_id}] WebSocket Connected.")
            
            # 2. Trigger a prediction via HTTP
            async with aiohttp.ClientSession() as session:
                payload = {
                    "lat": 30.84 + (user_id * 0.001), # Slightly vary location to bypass cache
                    "lon": 75.89, "acres": 10, "N": 50, "P": 50, "K": 50, "ph": 6.5,
                    "image_base64": "dummy_data"
                }
                
                # We bypass auth for the test by sending user_id directly if your test route allows it
                # Otherwise, you would need to fetch 100 JWT tokens here.
                headers = {"Authorization": "Bearer YOUR_TEST_TOKEN"} 
                
                print(f"[User {user_id}] Sending HTTP Prediction Request...")
                async with session.post(API_URL, json=payload, headers=headers) as resp:
                    if resp.status == 429:
                        print(f"[User {user_id}] ❌ RATE LIMITED!")
                        return
                    
            # 3. Wait for the Celery -> Redis -> FastAPI WebSocket broadcast
            response = await websocket.recv()
            data = json.loads(response)
            print(f"[User {user_id}] ✅ WebSocket Received Data: {data['recommended_crop']}")
            
    except Exception as e:
        print(f"[User {user_id}] Connection Error: {e}")

async def main():
    print("Initializing 100 Simultaneous Connections...")
    # Fire off 100 concurrent async tasks
    tasks = [simulate_user(i) for i in range(1, 101)]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())