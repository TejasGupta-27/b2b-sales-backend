import asyncio
import httpx
import json
from datetime import datetime
import uuid

async def test_chat_search():
    """Test the chat search functionality with various scenarios"""
    async with httpx.AsyncClient(base_url="http://localhost:3001") as client:
        # First, create a test lead by sending a chat message
        lead_id = str(uuid.uuid4())
        initial_message = "Hello, I'm interested in your products."
        
        # Create lead by sending first message
        response = await client.post("/api/chat", json={
            "message": initial_message,
            "lead_id": lead_id,
            "conversation_stage": "discovery"
        })
        print(f"Created lead with initial message: {response.json()}\n")
        
        # Test messages to create
        test_messages = [
            "What is the product pricing for your enterprise solution?",
            "Can you tell me about your pricing model?",
            "I need information about your product features",
            "What are the key features of your solution?",
            "How does your pricing work for small businesses?",
            "Tell me about your enterprise pricing structure",
            "What are the main features of your platform?",
            "Can you explain your pricing tiers?",
            "I'm interested in your product's capabilities",
            "What's included in your basic package?"
        ]

        # Create test messages
        for message in test_messages:
            response = await client.post("/api/chat", json={
                "message": message,
                "lead_id": lead_id,
                "conversation_stage": "discovery"
            })
            print(f"Created message: {message}")
            print(f"Response: {response.json()}\n")

        # Test 1: Exact search
        print("\n=== Test 1: Exact Search ===")
        response = await client.post("/api/chat/search", json={
            "query": "pricing",
            "lead_id": lead_id,
            "use_fuzzy": False
        })
        print("Exact search results:")
        print(json.dumps(response.json(), indent=2))

        # Test 2: Fuzzy search with typo
        print("\n=== Test 2: Fuzzy Search with Typo ===")
        response = await client.post("/api/chat/search", json={
            "query": "pricng",  # Intentionally misspelled
            "lead_id": lead_id,
            "use_fuzzy": True,
            "similarity_threshold": 0.3
        })
        print("Fuzzy search results (with typo):")
        print(json.dumps(response.json(), indent=2))

        # Test 3: Fuzzy search with different word forms
        print("\n=== Test 3: Fuzzy Search with Different Word Forms ===")
        response = await client.post("/api/chat/search", json={
            "query": "feature",
            "lead_id": lead_id,
            "use_fuzzy": True,
            "similarity_threshold": 0.3
        })
        print("Fuzzy search results (different word forms):")
        print(json.dumps(response.json(), indent=2))

        # Test 4: Fuzzy search with partial words
        print("\n=== Test 4: Fuzzy Search with Partial Words ===")
        response = await client.post("/api/chat/search", json={
            "query": "enterpr",
            "lead_id": lead_id,
            "use_fuzzy": True,
            "similarity_threshold": 0.3
        })
        print("Fuzzy search results (partial words):")
        print(json.dumps(response.json(), indent=2))

        # Test 5: Search with different similarity thresholds
        print("\n=== Test 5: Different Similarity Thresholds ===")
        thresholds = [0.1, 0.3, 0.5, 0.7]
        for threshold in thresholds:
            response = await client.post("/api/chat/search", json={
                "query": "pricing",
                "lead_id": lead_id,
                "use_fuzzy": True,
                "similarity_threshold": threshold
            })
            print(f"\nResults with threshold {threshold}:")
            print(f"Found {len(response.json()['results'])} results")
            print(json.dumps(response.json(), indent=2))

if __name__ == "__main__":
    asyncio.run(test_chat_search())