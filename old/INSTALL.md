# Mokuro Installation Guide

## Quick Installation Options

### 1. Basic Installation (CLI only)
```bash
pip install mokuro
```

### 2. API Server Installation
```bash
# Basic API server
pip install "mokuro[api]"

# Enhanced API server with production features
pip install "mokuro[api-enhanced]"
```

### 3. OCR Engine Support
```bash
# All OCR engines via owocr
pip install "mokuro[owocr]"

# Extended image format support (AVIF, JPEG XL)
pip install "mokuro[images]"
```

### 4. Complete Installation (Everything)
```bash
# Install with all features
pip install "mokuro[all]"

# Or from source with all features
git clone https://github.com/kha-white/mokuro.git
cd mokuro
pip install -e ".[all]"
```

## Installation Methods

### From PyPI
```bash
# Basic
pip install mokuro

# With specific extras
pip install "mokuro[api-enhanced,owocr,images]"
```

### From Source (Development)
```bash
git clone https://github.com/kha-white/mokuro.git
cd mokuro

# Editable install with all features
pip install -e ".[all,dev]"
```

### Using requirements.txt
```bash
# For enhanced API server only
pip install -r requirements-api-enhanced.txt
```

## Feature Sets

### `[api]` - Basic API Server
- FastAPI web server
- Basic OCR endpoints
- CORS support

### `[api-enhanced]` - Production API Server
- Everything from `[api]`
- Rate limiting (slowapi)
- Request caching (cachetools)
- Resource monitoring (psutil)
- Configuration file support (pyyaml)
- Future: Metrics and structured logging

### `[owocr]` - Multiple OCR Engines
- Manga OCR via owocr
- EasyOCR
- RapidOCR
- Google Lens
- Google Vision
- Azure Image Analysis
- Apple Vision/Live Text (macOS)
- WinRT OCR (Windows)
- OneOCR (Windows)

### `[images]` - Extended Image Format Support
- AVIF support (pillow-heif)
- JPEG XL support (pillow-jxl-plugin)

### `[dev]` - Development Tools
- pytest for testing
- ruff for linting

### `[all]` - Everything
- All OCR engines
- All image formats
- Enhanced API server
- Development tools

## Running the Enhanced API Server

After installation:

```bash
# Option 1: Using the installed script
mokuro-api-enhanced

# Option 2: Using Python module
python -m mokuro.api_server.enhanced_server_v2

# Option 3: With environment variables
MOKURO_MAX_PARALLEL_OCR=5 \
MOKURO_API_PORT=8080 \
mokuro-api-enhanced
```

## Docker Installation

```bash
# Build the Docker image
docker build -t mokuro-api:enhanced .

# Run with GPU support
docker run --rm --gpus all -p 7331:7331 mokuro-api:enhanced

# Run CPU-only
docker run --rm -p 7331:7331 mokuro-api:enhanced
```

## Verifying Installation

### Test the enhanced API server:
```bash
# Start the server
mokuro-api-enhanced

# In another terminal, run tests
python test_enhanced_server.py
```

### Check available features:
```bash
# Check API info
curl http://localhost:7331/api/info

# Check health
curl http://localhost:7331/health
```

## Troubleshooting

### GPU/CUDA Issues
```bash
# Check if CUDA is available
python -c "import torch; print(torch.cuda.is_available())"

# Force CPU mode
MOKURO_FORCE_CPU=true mokuro-api-enhanced
```

### Memory Issues
```bash
# Limit memory usage
MOKURO_MAX_MEMORY_PERCENT=70 mokuro-api-enhanced

# Reduce parallel operations
MOKURO_MAX_PARALLEL_OCR=1 mokuro-api-enhanced
```

### Port Already in Use
```bash
# Use a different port
MOKURO_API_PORT=8080 mokuro-api-enhanced
```

## Configuration

Create a `config.yaml` file to customize settings:

```yaml
server:
  port: 7331
  host: "0.0.0.0"

processing:
  max_parallel_ocr: 3
  ocr_timeout: 30

rate_limiting:
  endpoints:
    /api/ocr:
      - "5 per second"
      - "300 per minute"
```

Then run with:
```bash
MOKURO_CONFIG=config.yaml mokuro-api-enhanced
```