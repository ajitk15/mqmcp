import requests
import time
import json
import uuid

def test_api():
    print("Testing MQ UI-Agnostic API Gateway...\n")
    url = "http://127.0.0.1:8000/api/v1/chat"
    
    session = str(uuid.uuid4())
    print(f"Session ID: {session}")
    
    payload = {
        "session_id": session,
        "message": "Can you list the queue managers for me?"
    }
    
    print(f"Sending: {payload['message']}")
    
    start = time.time()
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        
        data = response.json()
        print(f"\nResponse received in {time.time() - start:.2f}s:")
        print("-" * 50)
        print(data.get("reply"))
        print("-" * 50)
        print(f"Tools Used: {data.get('tools_used')}")
        
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to API. Is uvicorn running?")
        print("   Run: uvicorn api.main:app --reload")
        
if __name__ == "__main__":
    test_api()
