import pytest
from fastapi.testclient import TestClient
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from main import app

client = TestClient(app)

def test_language_update_endpoint():
    # First create a conversation
    lead_data = {
        "name": "Test User",
        "company": "Test Company",
        "language": "en"
    }
    response = client.post("/chat/start", json=lead_data)
    assert response.status_code == 200
    lead_id = response.json()["lead_id"]
    
    # Test updating to Japanese
    response = client.post("/chat/language", json={
        "lead_id": lead_id,
        "language": "ja"
    })
    assert response.status_code == 200
    assert response.json()["language"] == "ja"
    
    # Send a message and verify response language
    message_data = {
        "lead_id": lead_id,
        "message": "Hello",
        "language": "ja"
    }
    response = client.post("/chat/message", json=message_data)
    assert response.status_code == 200
    
    # Test updating back to English
    response = client.post("/chat/language", json={
        "lead_id": lead_id,
        "language": "en"
    })
    assert response.status_code == 200
    assert response.json()["language"] == "en"

def test_invalid_language_update():
    response = client.post("/chat/language", json={
        "lead_id": "invalid_id",
        "language": "en"
    })
    assert response.status_code == 404

def test_missing_lead_id():
    response = client.post("/chat/language", json={
        "language": "en"
    })
    assert response.status_code == 422  # FastAPI validation error
