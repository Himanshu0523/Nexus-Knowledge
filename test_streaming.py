import requests
import json
import time
import asyncio
import httpx

BASE_URL = "http://localhost:8000/api/v1"

def test_streaming_with_curl():
    """Test streaming with curl instruction"""
    print("=" * 60)
    print("Test 1: Streaming with curl (Command Example)")
    print("=" * 60)
    print("""
    curl -N -X POST http://localhost:8000/api/v1/chat/stream \\
      -H "Content-Type: application/json" \\
      -d '{"conversation_id": "conv_stream_1", "message": "Explain machine learning"}'
    """)

async def test_streaming_with_python():
    """Test streaming with Python httpx"""
    print("=" * 60)
    print("Test 2: Streaming with Python")
    print("=" * 60)
    
    conversation_id = f"conv_stream_{int(time.time())}"
    
    try:
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{BASE_URL}/chat/stream",
                json={
                    "conversation_id": conversation_id,
                    "message": "What is Python?",
                    "metadata": {"user_id": "test_user"}
                },
                timeout=60.0
            ) as response:
                print(f"Status: {response.status_code}")
                print(f"Content-Type: {response.headers.get('content-type')}")
                print("\nStreaming response:")
                print("-" * 40)
                
                full_response = ""
                
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        data = json.loads(data_str)
                        
                        event_type = data.get("type")
                        
                        if event_type == "status":
                            print(f"\n[STATUS] {data.get('message', '')}")
                            
                        elif event_type == "token":
                            token = data.get("content", "")
                            full_response += token
                            print(token, end="", flush=True)
                            
                        elif event_type == "done":
                            print(f"\n\n[DONE] Message ID: {data.get('message_id')}")
                            print(f"Model: {data.get('model')}")
                            print(f"Usage: {data.get('usage')}")
                            
                        elif event_type == "error":
                            print(f"\n[ERROR] {data.get('message')}")
                
                print(f"\n\nFull response: {full_response}")
    except Exception as e:
        print(f"Error testing streaming with Python: {e}")

async def test_streaming_with_rag():
    """Test streaming with RAG"""
    print("\n" + "=" * 60)
    print("Test 3: Streaming with RAG")
    print("=" * 60)
    
    conversation_id = f"conv_stream_rag_{int(time.time())}"
    
    try:
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{BASE_URL}/chat/stream",
                json={
                    "conversation_id": conversation_id,
                    "message": "What does the document say about cloud computing?",
                    "metadata": {"user_id": "test_user"}
                },
                timeout=60.0
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = json.loads(line[6:])
                        event_type = data.get("type")
                        
                        if event_type == "source":
                            print(f"\n[SOURCE] {data.get('source')} (Page {data.get('page')})")
                            
                        elif event_type == "token":
                            print(data.get("content", ""), end="", flush=True)
                            
                        elif event_type == "done":
                            print(f"\n\n[DONE]")
    except Exception as e:
        print(f"Error testing streaming with RAG: {e}")

if __name__ == "__main__":
    test_streaming_with_curl()
    asyncio.run(test_streaming_with_python())
    asyncio.run(test_streaming_with_rag())
    
    print("\n" + "=" * 60)
    print("Streaming Tests Completed!")
    print("=" * 60)
