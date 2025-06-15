#!/usr/bin/env python3
"""
Debug script to understand enum handling
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.models import LeadStatus
from sqlalchemy import text
from db.database import SessionLocal

def debug_enum():
    print("🔍 Debugging enum values...")
    
    # Check what the enum values are
    print(f"LeadStatus.NEW = {LeadStatus.NEW}")
    print(f"LeadStatus.NEW.value = {LeadStatus.NEW.value}")
    print(f"str(LeadStatus.NEW) = {str(LeadStatus.NEW)}")
    
    # Check database enum values
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT enumlabel 
            FROM pg_enum 
            WHERE enumtypid = (
                SELECT oid 
                FROM pg_type 
                WHERE typname = 'leadstatus'
            )
        """)).fetchall()
        
        enum_values = [row[0] for row in result]
        print(f"Database enum values: {enum_values}")
        
    except Exception as e:
        print(f"Error getting enum values: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    debug_enum() 