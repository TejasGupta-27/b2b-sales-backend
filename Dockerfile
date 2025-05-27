FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements files
COPY pyproject.toml requirements.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir "fastapi[all]" "uvicorn[standard]" python-dotenv aiofiles psycopg2-binary -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p Data/json Data/quotes logs services

# Expose port
EXPOSE 3001

# Simple command - let docker-compose handle the waiting
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3001", "--reload"]