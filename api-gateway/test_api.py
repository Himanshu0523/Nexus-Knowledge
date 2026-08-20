import requests
import json

# Test 1: Basic request
print("Test 1: Basic request")
try:
    response = requests.post(
        "http://localhost:8000/api/v1/chat",
        json={
            "conversation_id": "conv_123",
            "message": "Hello"
        }
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}\n")
except Exception as e:
    print(f"Error: {e}\n")

# Test 2: With API key
print("Test 2: With API key")
try:
    response = requests.post(
        "http://localhost:8000/api/v1/chat",
        json={
            "conversation_id": "conv_123",
            "message": "Explain machine learning",
            "stream": False,
            "metadata": {"language": "en", "client": "python-test"}
        },
        headers={"X-API-Key": "sk_dev_key_123456789"}
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}\n")
except Exception as e:
    print(f"Error: {e}\n")

# Test 3: Invalid request
print("Test 3: Invalid request")
try:
    response = requests.post(
        "http://localhost:8000/api/v1/chat",
        json={"conversation_id": "conv_123"}
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}\n")
except Exception as e:
    print(f"Error: {e}\n")
