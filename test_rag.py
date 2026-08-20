import requests
import json
import time
import os

BASE_URL = "http://localhost:8000/api/v1"

def test_document_upload():
    """Test document upload and RAG query"""
    
    # Create a test document
    test_content = """
    Cloud Computing and Virtualization
    
    Virtualization is a technology that allows multiple virtual machines to run on a single physical machine.
    A hypervisor is software that creates and manages virtual machines.
    Virtual machines share physical resources like CPU, memory, and storage.
    
    Cloud computing provides on-demand access to computing resources over the internet.
    There are three main service models: IaaS, PaaS, and SaaS.
    Infrastructure as a Service (IaaS) provides virtualized computing resources.
    Platform as a Service (PaaS) provides development platforms.
    Software as a Service (SaaS) provides applications over the internet.
    
    Benefits of virtualization include:
    1. Cost reduction through server consolidation
    2. Improved disaster recovery
    3. Increased flexibility and scalability
    4. Better resource utilization
    """
    
    # Save test document
    test_file = "test_document.txt"
    with open(test_file, "w") as f:
        f.write(test_content)
    
    # Upload document
    print("=" * 60)
    print("Test 1: Upload Document")
    print("=" * 60)
    
    try:
        with open(test_file, "rb") as f:
            files = {"file": f}
            response = requests.post(
                f"{BASE_URL}/documents",
                files=files,
                data={"tenant_id": "test_tenant"}
            )
        
        print(f"Upload Response: {json.dumps(response.json(), indent=2)}")
        document_id = response.json()["document_id"]
    except Exception as e:
        print(f"Error uploading document: {e}")
        document_id = "doc_test"
    
    # Wait for processing
    print("\nWaiting for document processing...")
    time.sleep(2)
    
    # Test RAG query
    print("\n" + "=" * 60)
    print("Test 2: RAG Query")
    print("=" * 60)
    
    conversation_id = f"conv_rag_{int(time.time())}"
    
    try:
        response = requests.post(
            f"{BASE_URL}/chat",
            json={
                "conversation_id": conversation_id,
                "message": "What is virtualization according to the document?",
                "knowledge_base_id": document_id,
                "metadata": {"user_id": "test_user", "client": "python-test"}
            }
        )
        print(f"RAG Response: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"Error querying RAG: {e}")
    
    # Clean up test file
    if os.path.exists(test_file):
        os.remove(test_file)
    
    return document_id

def test_multiple_queries():
    """Test multiple RAG queries"""
    print("\n" + "=" * 60)
    print("Test 3: Multiple RAG Queries")
    print("=" * 60)
    
    queries = [
        "What are the benefits of virtualization?",
        "What are the three service models in cloud computing?",
        "What is IaaS?"
    ]
    
    conversation_id = f"conv_rag_multi_{int(time.time())}"
    
    for query in queries:
        print(f"\nQuery: {query}")
        try:
            response = requests.post(
                f"{BASE_URL}/chat",
                json={
                    "conversation_id": conversation_id,
                    "message": query,
                    "metadata": {"user_id": "test_user"}
                }
            )
            print(f"Response: {json.dumps(response.json(), indent=2)}")
        except Exception as e:
            print(f"Error query: {e}")
        time.sleep(1)

if __name__ == "__main__":
    document_id = test_document_upload()
    test_multiple_queries()
    print("\n" + "=" * 60)
    print("RAG Testing Complete!")
    print("=" * 60)
