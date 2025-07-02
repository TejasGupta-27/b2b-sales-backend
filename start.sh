#!/bin/bash

# Startup script for B2B Sales Backend
# This script ensures proper initialization order

set -e

echo "🚀 Starting B2B Sales Backend..."

# Function to check if database is ready
check_database() {
    echo "🔍 Checking database readiness..."
    python wait_for_db.py
    if [ $? -eq 0 ]; then
        echo "✅ Database is ready"
        return 0
    else
        echo "❌ Database is not ready"
        return 1
    fi
}

# Function to initialize database
init_database() {
    echo "🔄 Initializing database..."
    bash scripts/init-db.sh
}

# Function to run migrations
run_migrations() {
    echo "🔄 Running database migrations..."
    export DATABASE_URL="postgresql://postgres:postgres@postgres:5432/b2b_sales"
    alembic upgrade head
    echo "✅ Migrations completed"
}

# Wait for database to be ready
echo "⏳ Waiting for database to be ready..."
max_attempts=30
attempt=0

while [ $attempt -lt $max_attempts ]; do
    if check_database; then
        break
    fi
    attempt=$((attempt + 1))
    echo "Attempt $attempt/$max_attempts - waiting 5 seconds..."
    sleep 5
done

if [ $attempt -eq $max_attempts ]; then
    echo "❌ Database failed to become ready after $max_attempts attempts"
    exit 1
fi

# Check if tables exist
echo "🔍 Checking if database tables exist..."
python -c "
import psycopg2
import os
try:
    conn = psycopg2.connect(os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@postgres:5432/b2b_sales'))
    cursor = conn.cursor()
    cursor.execute(\"\"\"
        SELECT COUNT(*) FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name IN ('leads', 'chat_messages')
    \"\"\")
    count = cursor.fetchone()[0]
    conn.close()
    exit(0 if count >= 2 else 1)
except Exception as e:
    print(f'Error checking tables: {e}')
    exit(1)
"

if [ $? -ne 0 ]; then
    echo "📝 Tables don't exist, running migrations..."
    run_migrations
else
    echo "✅ Database tables already exist"
fi

# Start the application
echo "🎉 Starting the application..."
exec python main.py 