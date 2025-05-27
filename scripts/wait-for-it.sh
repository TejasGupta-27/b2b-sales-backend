#!/bin/bash
# wait-for-it.sh script to wait for a host:port to be available

set -e

host="$1"
shift
cmd="$@"

until PGPASSWORD=$POSTGRES_PASSWORD psql -h "$host" -U "myuser" -d "chat_db" -c '\q'; do
  >&2 echo "Postgres is unavailable - sleeping"
  sleep 1
done

>&2 echo "Postgres is up - executing command"
exec $cmd 