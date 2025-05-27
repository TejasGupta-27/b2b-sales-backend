#!/bin/bash
set -e

# Wait for PostgreSQL to be ready
until PGPASSWORD=$POSTGRES_PASSWORD psql -h "db" -U "myuser" -d "chat_db" -c '\q'; do
  >&2 echo "Postgres is unavailable - sleeping"
  sleep 1
done

# Run database migrations
alembic upgrade head

# Start the application
exec "$@" 