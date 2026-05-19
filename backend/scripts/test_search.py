import asyncio
import json
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.search_routes import router

app = FastAPI()
app.include_router(router)

def run_test():
    client = TestClient(app)
    
    term = "ell"
    limite = 8
    
    print(f"Searching for: ?q={term}&limit={limite}...")
    response = client.get(f"/api/search?q={term}&limit={limite}")
    
    if response.status_code == 200:
        print("\n--- endpoint response ---")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    else:
        print(f"\nendpoint error: status {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    run_test()