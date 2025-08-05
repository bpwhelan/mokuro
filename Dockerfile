# Mokuro Server Dockerfile
# For building, use: ./build.sh
# This is a simplified version for quick builds.
# The build.sh script contains the optimized multi-stage build.

FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git nodejs npm build-essential \
    libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev libgomp1 wget \
    && rm -rf /var/lib/apt/lists/*

# Copy and install dependencies
COPY requirements-server.txt package.json lens_ocr_wrapper.js ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements-server.txt && \
    npm install

# Copy application
COPY . .
RUN pip install --no-cache-dir -e .

# Setup
RUN mkdir -p /tmp/mokuro_api

# Configure
EXPOSE 7331
ENV MOKURO_HOST=0.0.0.0
ENV MOKURO_PORT=7331
ENV MOKURO_PRELOAD_MODELS=true

CMD ["python", "mokuro_server.py"]