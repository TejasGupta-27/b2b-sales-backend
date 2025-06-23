#!/usr/bin/env python3
"""
Test script to verify conversation flow fixes
"""

import asyncio
import sys
import os

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ai_services.factory import AIServiceFactory
from ai_services.enhanced_b2b_sales_agent import EnhancedB2BSalesAgent
from ai_services.base import AIMessage
from config import settings

async def test_conversation_flow():
    """Test the conversation flow to ensure it doesn't get stuck"""
    
    print("🧪 Testing Conversation Flow Fixes")
    print("=" * 50)
    
    try:
        # Create base provider
        base_provider = AIServiceFactory.create_provider(settings.default_ai_provider)
        
        # Create enhanced sales agent
        agent = EnhancedB2BSalesAgent(
            base_provider=base_provider,
            use_hybrid_retriever=settings.use_hybrid_retriever
        )
        
        # Initialize agent
        await agent.initialize()
        
        # Test conversation messages
        test_messages = [
            AIMessage(role="user", content="Hi, I need help with video backup storage"),
            AIMessage(role="assistant", content="Hello! I'd be happy to help you with video backup storage. To provide the best recommendations, could you tell me a bit about your current setup and requirements?"),
            AIMessage(role="user", content="I have a lot of video files and need reliable storage"),
            AIMessage(role="assistant", content="I understand you need reliable storage for video files. To help you choose the right solution, could you share more details about your video storage needs?"),
            AIMessage(role="user", content="I need about 16TB of storage with RAID 6"),
            AIMessage(role="assistant", content="Great! 16TB with RAID 6 is a solid choice for video storage. What's your budget range for this solution?"),
            AIMessage(role="user", content="My budget is around $2000"),
            AIMessage(role="assistant", content="Perfect! With a $2000 budget for 16TB RAID 6 storage, I can recommend some excellent options. What's your timeline for implementation?"),
            AIMessage(role="user", content="I need it within the next month"),
            AIMessage(role="assistant", content="Excellent! A one-month timeline is very doable. Based on your requirements, I'd like to show you some NAS solutions that would be perfect for your video backup needs."),
            AIMessage(role="user", content="Yes, please show me some options"),
            AIMessage(role="assistant", content="I'll present you with some excellent NAS options that meet your 16TB RAID 6 requirements within your budget."),
            AIMessage(role="user", content="I like the Synology DS1621+ option"),
            AIMessage(role="assistant", content="Excellent choice! The Synology DS1621+ is a great NAS for your video backup needs. Would you like me to prepare a detailed quote for this solution?"),
            AIMessage(role="user", content="Yes, please generate a quote"),
        ]
        
        print(f"📝 Testing with {len(test_messages)} messages")
        
        # Test each message in sequence
        for i, message in enumerate(test_messages):
            if message.role == "user":
                print(f"\n🔄 Processing message {i+1}: {message.content[:50]}...")
                
                # Get conversation context up to this point
                conversation_context = test_messages[:i+1]
                
                # Generate response
                response = await agent.generate_response(
                    messages=conversation_context,
                    customer_context={
                        "company_name": "Test Company",
                        "contact_name": "Test User",
                        "industry": "Technology"
                    }
                )
                
                print(f"✅ Response generated: {response.content[:100]}...")
                print(f"📊 Stage: {agent.conversation_state['current_stage']}")
                print(f"📊 Message count: {agent.conversation_state['message_count']}")
                print(f"📊 Repeated responses: {agent.conversation_state['repeated_responses']}")
                
                # Check if we're stuck
                if agent.conversation_state['repeated_responses'] > 5:
                    print("⚠️ WARNING: High repeated response count detected!")
                
                # Add the response to our test messages for next iteration
                test_messages.insert(i+1, AIMessage(role="assistant", content=response.content))
        
        print("\n✅ Conversation flow test completed successfully!")
        print(f"📊 Final stage: {agent.conversation_state['current_stage']}")
        print(f"📊 Total messages processed: {agent.conversation_state['message_count']}")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_conversation_flow()) 