#!/bin/bash

# Database initialization script for B2B Sales Backend
# This script ensures the database is properly initialized before the application starts

set -e

echo "🚀 Starting database initialization..."

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL to be ready..."
until pg_isready -h postgres -p 5432 -U postgres; do
    echo "PostgreSQL is not ready yet, waiting..."
    sleep 2
done

echo "✅ PostgreSQL is ready!"

# Check if database exists
echo "🔍 Checking if database 'b2b_sales' exists..."
DB_EXISTS=$(psql -h postgres -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname='b2b_sales'")

if [ -z "$DB_EXISTS" ]; then
    echo "📝 Creating database 'b2b_sales'..."
    createdb -h postgres -U postgres b2b_sales
    echo "✅ Database 'b2b_sales' created successfully"
else
    echo "✅ Database 'b2b_sales' already exists"
fi

# Connect to the database and check if tables exist
echo "🔍 Checking if tables exist..."
TABLES_EXIST=$(psql -h postgres -U postgres -d b2b_sales -tAc "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_name IN ('leads', 'chat_messages')")

if [ "$TABLES_EXIST" -eq "0" ]; then
    echo "📝 Tables don't exist, running Alembic migrations..."
    
    # Set environment variables for Alembic
    export DATABASE_URL="postgresql://postgres:postgres@postgres:5432/b2b_sales"
    
    # Run Alembic migrations
    echo "🔄 Running database migrations..."
    alembic upgrade head
    
    echo "✅ Database migrations completed successfully"
else
    echo "✅ Tables already exist, skipping migrations"
fi

# Verify database setup
echo "🔍 Verifying database setup..."
psql -h postgres -U postgres -d b2b_sales -c "\dt" || {
    echo "❌ Database verification failed"
    exit 1
}

echo "✅ Database initialization completed successfully!"
echo "🎉 Database is ready for the application"

# Start the application
exec "$@" 