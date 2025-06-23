#!/usr/bin/env python3
"""
Conversation monitoring script to detect stuck conversations
"""

import asyncio
import aiohttp
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any

class ConversationMonitor:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.stuck_conversations = []
        
    async def get_all_leads(self) -> List[Dict[str, Any]]:
        """Get all leads from the system"""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.base_url}/api/leads") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    print(f"❌ Failed to get leads: {response.status}")
                    return []
    
    async def analyze_conversation_state(self, lead_id: str) -> Dict[str, Any]:
        """Analyze conversation state for a specific lead"""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.base_url}/api/debug/conversation-state/{lead_id}") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    print(f"❌ Failed to analyze conversation state for {lead_id}: {response.status}")
                    return {}
    
    def is_conversation_stuck(self, analysis: Dict[str, Any]) -> bool:
        """Determine if a conversation is stuck"""
        stuck_analysis = analysis.get('stuck_analysis', {})
        
        # Check for stuck indicators
        if stuck_analysis.get('no_progress', False):
            return True
        
        if stuck_analysis.get('same_stage_messages', 0) > 3:
            return True
        
        if stuck_analysis.get('repeated_questions', 0) > 5:
            return True
        
        # Check if conversation has been going on too long without progress
        conversation_stats = analysis.get('conversation_stats', {})
        if conversation_stats.get('total_messages', 0) > 20:
            return True
        
        return False
    
    async def monitor_conversations(self):
        """Monitor all conversations for stuck patterns"""
        print("🔍 Starting conversation monitoring...")
        
        while True:
            try:
                # Get all leads
                leads = await self.get_all_leads()
                print(f"📊 Monitoring {len(leads)} conversations...")
                
                stuck_count = 0
                
                for lead in leads:
                    lead_id = lead.get('id')
                    if not lead_id:
                        continue
                    
                    # Analyze conversation state
                    analysis = await self.analyze_conversation_state(lead_id)
                    if not analysis:
                        continue
                    
                    # Check if conversation is stuck
                    if self.is_conversation_stuck(analysis):
                        stuck_count += 1
                        lead_info = analysis.get('lead_info', {})
                        company_name = lead_info.get('company_name', 'Unknown')
                        
                        print(f"⚠️ STUCK CONVERSATION DETECTED:")
                        print(f"   Lead ID: {lead_id}")
                        print(f"   Company: {company_name}")
                        print(f"   Messages: {analysis.get('conversation_stats', {}).get('total_messages', 0)}")
                        print(f"   Last Stage: {analysis.get('stuck_analysis', {}).get('last_stage', 'Unknown')}")
                        print(f"   Repeated Questions: {analysis.get('stuck_analysis', {}).get('repeated_questions', 0)}")
                        print("-" * 50)
                        
                        # Store stuck conversation info
                        self.stuck_conversations.append({
                            'lead_id': lead_id,
                            'company_name': company_name,
                            'detected_at': datetime.now().isoformat(),
                            'analysis': analysis
                        })
                
                if stuck_count == 0:
                    print("✅ No stuck conversations detected")
                else:
                    print(f"⚠️ Found {stuck_count} stuck conversations")
                
                # Wait before next check
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                print(f"❌ Error in monitoring: {e}")
                await asyncio.sleep(60)
    
    def get_stuck_conversations_report(self) -> Dict[str, Any]:
        """Generate a report of stuck conversations"""
        return {
            'total_stuck': len(self.stuck_conversations),
            'stuck_conversations': self.stuck_conversations,
            'report_generated_at': datetime.now().isoformat()
        }

async def main():
    """Main monitoring function"""
    monitor = ConversationMonitor()
    
    print("🚀 Conversation Monitor Started")
    print("=" * 50)
    print("This script will monitor conversations for stuck patterns")
    print("Press Ctrl+C to stop monitoring")
    print("=" * 50)
    
    try:
        await monitor.monitor_conversations()
    except KeyboardInterrupt:
        print("\n🛑 Monitoring stopped by user")
        
        # Generate final report
        report = monitor.get_stuck_conversations_report()
        print(f"\n📊 Final Report:")
        print(f"Total stuck conversations detected: {report['total_stuck']}")
        
        if report['stuck_conversations']:
            print("\nStuck conversations:")
            for conv in report['stuck_conversations']:
                print(f"  - {conv['company_name']} (ID: {conv['lead_id']})")

if __name__ == "__main__":
    asyncio.run(main()) 