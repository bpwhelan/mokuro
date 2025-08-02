FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    nodejs \
    npm \
    build-essential \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements-server.txt

# Setup Google Lens OCR (optional - will fail gracefully if not needed)
RUN chmod +x setup_lens.sh && ./setup_lens.sh || true

# Create temp directory for API
RUN mkdir -p /tmp/mokuro_api

# Expose port
EXPOSE 7331

# Set environment variables
ENV MOKURO_HOST=0.0.0.0
ENV MOKURO_PORT=7331
ENV MOKURO_PRELOAD_MODELS=true

# Run server
CMD ["python", "mokuro_server.py"]