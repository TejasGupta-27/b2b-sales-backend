FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements files
COPY pyproject.toml requirements.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir "fastapi[all]" "uvicorn[standard]" python-dotenv aiofiles  -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p Data/json

# Expose port
EXPOSE 3001

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3001", "--reload"]