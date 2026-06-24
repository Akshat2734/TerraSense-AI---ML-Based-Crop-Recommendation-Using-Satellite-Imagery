import base64
import tempfile
import os

import redis
import json

from celery import Celery
from shapely.geometry import Polygon
from sqlalchemy.exc import OperationalError, PendingRollbackError
from geoalchemy2.shape import from_shape

from model.session import SessionLocalPrimary
from model.models import Prediction

from features.builder import build_features
from ml_model.inference import predict_crop

broker_url = os.getenv(
    "CELERY_BROKER_URL",
    "amqp://guest:guest@localhost:5672//"
)

result_backend = os.getenv(
    "CELERY_RESULT_BACKEND",
    "rpc://"
)

celery_app = Celery(
    "terrasense_tasks",
    broker=broker_url,
    backend=result_backend
)

sync_redis = redis.Redis(host='redis', port=6379, db=0)

@celery_app.task(bind=True, name="process_crop_prediction", max_retries=3, default_retry_delay=5)
def process_crop_prediction(self, payload: dict):
    db = None
    try:
        # Decode image
        raw_b64 = payload["image_base64"]

        if "," in raw_b64:
            raw_b64 = raw_b64.split(",")[1]

        raw_b64 += "=" * ((4 - len(raw_b64) % 4) % 4)

        image_data = base64.b64decode(raw_b64)

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".jpg"
        ) as temp_image:
            temp_image.write(image_data)
            temp_image_path = temp_image.name

        # Feature engineering + inference
        X, ndvi, ee_coords = build_features(
            payload["lat"],
            payload["lon"],
            payload["acres"],
            payload["N"],
            payload["P"],
            payload["K"],
            payload["ph"]
        )

        soil_name, crop_name = predict_crop(
            temp_image_path,
            X
        )

        # Convert Earth Engine polygon -> PostGIS geometry
        coords = ee_coords[0]

        polygon = Polygon(coords)

        if not polygon.is_valid:
            raise ValueError("Invalid polygon received from Earth Engine")

        location_geom = from_shape(
            polygon,
            srid=4326
        )

        # Save prediction
        db = SessionLocalPrimary()

        new_prediction = Prediction(
            user_id=payload["user_id"],
            recommended_crop=str(crop_name),
            detected_soil=str(soil_name),
            satellite_ndvi=float(ndvi),
            location=location_geom
        )

        db.add(new_prediction)
        db.commit()
        db.refresh(new_prediction)
        
        final_result = {
            "status": "SUCCESS",
            "user_id": payload["user_id"],
            "db_id": new_prediction.id,
            "recommended_crop": str(crop_name),
            "detected_soil": str(soil_name),
            "ndvi": float(ndvi)
        }
        
        try:
            # 1. Cache the result for future identical requests (Expires in 24 hours)
            if "cache_key" in payload:
                sync_redis.setex(payload["cache_key"], 86400, json.dumps(final_result))

            # 2. Publish to Redis so FastAPI can broadcast via WebSocket
            sync_redis.publish("celery_websocket_updates", json.dumps(final_result))
        except Exception as redis_error:
            print(f"Redis error: {redis_error}")
        
        return final_result
    
    except (OperationalError, PendingRollbackError) as db_err:
        # TRANSIENT ERROR: Database is locked by another request. Rollback and Retry.
        print(f"[RETRY] Database locked. Retrying task... ({self.request.retries}/3)")
        if db:
            db.rollback()
        raise self.retry(exc=db_err)
    
    except Exception as e:
        if db:
            db.rollback()

        self.update_state(
            state="FAILURE",
            meta={
                "exc_type": type(e).__name__,
                "exc_message": str(e)
            }
        )

        raise

    finally:
        if db:
            db.close()

        if "temp_image_path" in locals():
            try:
                os.remove(temp_image_path)
            except Exception:
                pass