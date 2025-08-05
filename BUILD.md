# Mokuro Build Guide

This guide covers building and running Mokuro both locally and via Docker.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Local Development](#local-development)
- [Docker Build](#docker-build)
- [API Documentation](#api-documentation)
- [OCR Engines](#ocr-engines)

## Prerequisites

### System Requirements
- Python 3.8+ (3.9 recommended)
- Node.js 18+ (for Google Lens OCR)
- Git
- Docker (for containerized deployment)

### GPU Support (Optional)
- NVIDIA GPU with CUDA support for faster OCR processing
- NVIDIA Container Toolkit (for Docker GPU support)

## Local Development

### 1. Clone Repository
```bash
git clone https://github.com/xrishox/mokuro.git
cd mokuro
git submodule update --init --recursive
```

### 2. Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
# Upgrade pip
pip install --upgrade pip setuptools wheel

# Install package in development mode
pip install -e .

# Install server dependencies
pip install -r requirements-server.txt
```

### 4. Setup Google Lens OCR (Optional)
```bash
# Install Node.js dependencies
npm install

# Or manually install chrome-lens-ocr
npm install chrome-lens-ocr
```

### 5. Run Server
```bash
# Default settings (port 7331)
python mokuro_server.py

# Custom settings
export MOKURO_HOST=0.0.0.0
export MOKURO_PORT=8080
export MOKURO_DEBUG=true
export MOKURO_PRELOAD_MODELS=false
python mokuro_server.py
```

## Docker Build

### Quick Start
```bash
# Build and run using the build script
chmod +x build.sh
./build.sh

# Or use Docker directly
docker build -t mokuro-server .
docker run -p 7331:7331 mokuro-server
```

### Multi-Architecture Build
```bash
# Build for multiple platforms (AMD64 + ARM64)
./build.sh --multiarch

# Or manually with buildx
docker buildx build --platform linux/amd64,linux/arm64 -t mokuro-server:multiarch .
```

### Docker Compose
```yaml
version: '3.8'
services:
  mokuro-api:
    image: ghcr.io/xrishox/mokuro:latest
    ports:
      - "7331:7331"
    environment:
      - MOKURO_HOST=0.0.0.0
      - MOKURO_PORT=7331
      - MOKURO_PRELOAD_MODELS=true
    volumes:
      - ./cache:/app/cache  # Optional: persistent cache
    restart: unless-stopped
```

### GPU Support in Docker
```yaml
services:
  mokuro-api:
    image: ghcr.io/xrishox/mokuro:latest
    runtime: nvidia
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
```

## API Documentation

### Endpoints

#### Health Check
```
GET /health
```
Returns server status and available OCR engines.

#### API Info
```
GET /api/info
```
Returns detailed API documentation and OCR engine information.

#### Process Single Image
```
POST /api/ocr
Content-Type: multipart/form-data

Parameters:
- image: Image file (required)
- ocr_engine: 'manga-ocr' or 'lens' (optional, default: manga-ocr)
- force_cpu: boolean (optional, default: false)
```

#### Process Multiple Images
```
POST /api/ocr/batch
Content-Type: multipart/form-data

Parameters:
- images: Multiple image files (required)
- ocr_engine: 'manga-ocr' or 'lens' (optional, default: manga-ocr)
- force_cpu: boolean (optional, default: false)
```

### Supported Image Formats
- JPEG (.jpg, .jpeg)
- PNG (.png)
- WebP (.webp)
- AVIF (.avif)
- BMP (.bmp)
- TIFF (.tiff)

### Response Format
```json
{
  "ocr_engine": "manga-ocr",
  "processing_time": 1.234,
  "results": [
    {
      "text": "recognized text",
      "bbox": [x1, y1, x2, y2]
    }
  ]
}
```

## OCR Engines

### manga-ocr (Default)
- Fast offline OCR specialized for Japanese manga
- Automatically downloaded on first use
- Best for: Japanese text in manga/comics
- Platform: All

### Google Lens OCR
- Multilingual OCR with cloud processing
- Requires Node.js and chrome-lens-ocr
- Best for: Multiple languages, complex layouts
- Platform: All (requires Node.js)

### Apple Vision OCR
- Native macOS text recognition
- Only available on macOS 10.15+
- Best for: macOS users, system integration
- Platform: macOS only

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| MOKURO_HOST | localhost | Server host binding |
| MOKURO_PORT | 7331 | Server port |
| MOKURO_DEBUG | false | Enable debug mode |
| MOKURO_PRELOAD_MODELS | true | Preload OCR models on startup |
| FORCE_CPU | false | Force CPU usage (useful for ARM) |

## Troubleshooting

### Google Lens OCR Not Working
If you see `ERR_REQUIRE_ESM` errors:
1. Ensure `package.json` has `"type": "module"`
2. Update to latest chrome-lens-ocr version
3. Rebuild the Docker image

### GPU Not Detected
1. Install NVIDIA Container Toolkit
2. Add `runtime: nvidia` to docker-compose
3. Set `NVIDIA_VISIBLE_DEVICES=all`

### ARM Build Issues
1. Use the `--multiarch` flag with build.sh
2. Set `FORCE_CPU=true` environment variable
3. Allow extra time for dependency compilation

## API Migration from v0.1.x

### Breaking Changes
- `/mokuro/api/ocr` → `/api/ocr`
- Base64 input removed (use multipart/form-data)
- `engine` parameter → `ocr_engine`

### New Features
- Dynamic OCR engine discovery
- Batch processing endpoint
- Improved error handling
- Platform-specific engine filtering