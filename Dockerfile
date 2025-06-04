FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including those needed for numpy
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    build-essential \
    python3-dev \
    libatlas-base-dev \
    curl \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip, setuptools and wheel to avoid common build errors
RUN pip install --upgrade pip setuptools wheel

COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/chroma_db && chmod 755 /app/chroma_db

EXPOSE 3001

# Run the application
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3001", "--reload"]
