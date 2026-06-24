from pydantic import BaseModel, Field

class CropPredictionRequest(BaseModel):
    lat: float
    lon: float
    acres: float
    
    N: float
    P: float
    K: float
    ph: float
    
    # Accept image as base64 for pure JSON payloads
    image_base64: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "lat": 30.85,
                "lon": 75.90,
                "acres": 15.0,
                "N": 80.0,
                "P": 40.0,
                "K": 40.0,
                "ph": 6.8,
                "image_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
            }
        }