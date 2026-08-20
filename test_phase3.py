import requests
import json
import time

BASE_URL = "http://localhost:8000/api/v1"

def test_conversation_memory():
    """Test conversation memory functionality"""
    conversation_id = f"conv_test_{int(time.time())}"
    
    print("Phase 3 Test: Conversation Memory\n")
    
    # Test 1: First question
    print("=" * 50)
    print("Test 1: First question - 'What is Python?'")
    print("=" * 50)
    
    try:
        response1 = requests.post(
            f"{BASE_URL}/chat",
            json={
                "conversation_id": conversation_id,
                "message": "What is Python?",
                "metadata": {"user_id": "test_user_1", "client": "python-test"}
            }
        )
        print(f"Status: {response1.status_code}")
        print(f"Response: {json.dumps(response1.json(), indent=2)}\n")
    except Exception as e:
        print(f"Error: {e}\n")
    
    # Test 2: Follow-up question using context
    print("=" * 50)
    print("Test 2: Follow-up question - 'Who created it?'")
    print("=" * 50)
    
    try:
        response2 = requests.post(
            f"{BASE_URL}/chat",
            json={
                "conversation_id": conversation_id,
                "message": "Who created it?",
                "metadata": {"user_id": "test_user_1", "client": "python-test"}
            }
        )
        print(f"Status: {response2.status_code}")
        print(f"Response: {json.dumps(response2.json(), indent=2)}\n")
    except Exception as e:
        print(f"Error: {e}\n")
    
    # Test 3: Get conversation history
    print("=" * 50)
    print("Test 3: Get conversation history")
    print("=" * 50)
    
    try:
        response3 = requests.get(
            f"http://localhost:8001/api/v1/conversations/{conversation_id}/history"
        )
        print(f"Status: {response3.status_code}")
        print(f"History: {json.dumps(response3.json(), indent=2)}\n")
    except Exception as e:
        print(f"Error: {e}\n")
    
    # Test 4: Another context-dependent question
    print("=" * 50)
    print("Test 4: Context-dependent question")
    print("=" * 50)
    
    try:
        response4 = requests.post(
            f"{BASE_URL}/chat",
            json={
                "conversation_id": conversation_id,
                "message": "What can I use it for?",
                "metadata": {"user_id": "test_user_1", "client": "python-test"}
            }
        )
        print(f"Status: {response4.status_code}")
        print(f"Response: {json.dumps(response4.json(), indent=2)}\n")
    except Exception as e:
        print(f"Error: {e}\n")
    
    print("=" * 50)
    print("Phase 3 Test Complete!")
    print("=" * 50)

if __name__ == "__main__":
    test_conversation_memory()
