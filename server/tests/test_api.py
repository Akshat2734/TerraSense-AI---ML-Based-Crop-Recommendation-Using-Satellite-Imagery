import pytest
from fastapi.testclient import TestClient
from main import app
from users.auth import verify_token

client = TestClient(app)

# Bypass JWT for testing
app.dependency_overrides[verify_token] = lambda: {"sub": "test_user"}

@pytest.fixture
def valid_payload():
    return {
        "lat": 34.05,
        "lon": -118.24,
        "acres": 15.0,
        "N": 50.0,
        "P": 30.0,
        "K": 40.0,
        "ph": 6.5,
        "image_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=" 
    }

def test_successful_prediction(valid_payload, mocker):
    # Mock the Async GEE Wrapper
    mocker.patch('services.gee_client.GEEAsyncClient.get_ndvi_async', return_value=0.88)
    
    response = client.post("/api/v1/predict", json=valid_payload)
    assert response.status_code == 200
    assert response.json()["data"]["satellite_ndvi"] == 0.75 # Placeholder from main.py

def test_invalid_latitude_boundary(valid_payload):
    invalid_payload = valid_payload.copy()
    invalid_payload["lat"] = 95.0  # Out of bounds
    
    response = client.post("/api/v1/predict", json=invalid_payload)
    
    # FastAPI returns 422 Unprocessable Entity for Pydantic Validation Errors
    assert response.status_code == 422 
    assert "Input should be less than or equal to 90" in response.text

def test_invalid_ph_boundary(valid_payload):
    invalid_payload = valid_payload.copy()
    invalid_payload["ph"] = -2.0  # Impossible pH
    
    response = client.post("/api/v1/predict", json=invalid_payload)
    assert response.status_code == 422