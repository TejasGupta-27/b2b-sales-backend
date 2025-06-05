FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    build-essential \
    python3-dev \
    libatlas-base-dev \
    ffmpeg \
    libsndfile1 \
    curl \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip setuptools wheel

# Install core Python deps (caches better)
COPY requirements-core.txt .
RUN pip install --no-cache-dir -r requirements-core.txt

# Install ML deps separately
COPY requirements-ml.txt .
RUN pip install --no-cache-dir -r requirements-ml.txt

# Copy source code
COPY . .

# Setup permissions if needed
RUN mkdir -p /app/chroma_db && chmod 755 /app/chroma_db

EXPOSE 3001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3001", "--reload"]
