import time
import psycopg2
import os
import sys

def wait_for_db():
    """Wait for database to be ready"""
    max_retries = 30
    retry_count = 0
    
    db_config = {
        'host': 'db',
        'port': 5432,
        'user': os.getenv('POSTGRES_USER', 'myuser'),
        'password': os.getenv('POSTGRES_PASSWORD', 'mypassword'),
        'database': os.getenv('POSTGRES_DB', 'chat_db')
    }
    
    while retry_count < max_retries:
        try:
            conn = psycopg2.connect(**db_config)
            conn.close()
            print("Database is ready!")
            return True
        except psycopg2.OperationalError:
            retry_count += 1
            print(f"Database not ready, retrying... ({retry_count}/{max_retries})")
            time.sleep(2)
    
    print("Database failed to become ready")
    return False

if __name__ == "__main__":
    if wait_for_db():
        sys.exit(0)
    else:
        sys.exit(1) 