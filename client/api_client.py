import requests
from typing import Dict, Any, Optional

class TerraSenseClient:
    def __init__(self, base_url: str = "http://localhost"):
        # This points directly to your NGINX reverse proxy
        self.base_url = base_url
        self.token: Optional[str] = None
        self.headers = {"Content-Type": "application/json"}

    def set_token(self, token: str):
        """Saves the JWT token and attaches it to future requests."""
        self.token = token
        self.headers["Authorization"] = f"Bearer {self.token}"

    def login(self, username: str, password: str) -> bool:
        """Authenticates with the backend and retrieves a secure token."""
        data = {"username": username, "password": password}
        response = requests.post(f"{self.base_url}/token", data=data)
        
        if response.status_code == 200:
            self.set_token(response.json().get("access_token"))
            return True
        return False

    def submit_prediction(self, payload: Dict[str, Any]) -> str:
        """
        Submits farm data and the Base64 satellite image to the backend.
        Returns the Celery task_id so we can track it.
        """
        # If your endpoint is protected, ensure you call login() first!
        response = requests.post(
            f"{self.base_url}/api/v1/predict", 
            json=payload, 
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()

    def check_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Polls the backend to see if the RabbitMQ/Celery worker has 
        finished crunching the EfficientNet ML model.
        """
        response = requests.get(
            f"{self.base_url}/api/v1/status/{task_id}", 
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def get_history(self) -> list:
        """Fetches the prediction history for the logged-in user."""
        response = requests.get(f"{self.base_url}/api/v1/history", headers=self.headers)
        response.raise_for_status()
        return response.json()