#!/bin/bash
set -e

echo "==================================="
echo "Mokuro Server Docker Container"
echo "Version: $(python3 -c 'from mokuro import __version__; print(__version__)')"
echo "==================================="

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Verify environment
echo "Checking environment..."
echo "Python: $(python3 --version)"
echo "Node.js: $(node --version)"
echo "NPM: $(npm --version)"

# Check for GPU availability
if command_exists nvidia-smi && nvidia-smi > /dev/null 2>&1; then
    echo "GPU detected:"
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
    export CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-0}
else
    echo "No GPU detected, using CPU"
    export CUDA_VISIBLE_DEVICES=""
fi

# Ensure directories exist with proper permissions
echo "Setting up directories..."
mkdir -p /tmp/mokuro_api
mkdir -p /app/cache
mkdir -p /app/logs

# Check OCR engines availability
echo "Checking OCR engines..."
python3 -c "
from mokuro.ocr_registry import OCRRegistry
engines = OCRRegistry.get_available_engines()
print(f'Available OCR engines: {engines}')

for engine in engines:
    info = OCRRegistry.get_engine_info(engine)
    print(f'  - {engine}: {info[\"description\"]}')
"

# Pre-load models if requested
if [ "${MOKURO_PRELOAD_MODELS}" = "true" ]; then
    echo "Pre-loading models..."
    python3 -c "
import sys
try:
    # Load manga-ocr model
    print('Loading manga-ocr model...')
    from manga_ocr import MangaOcr
    model = MangaOcr()
    print('✓ manga-ocr model loaded')
    
    # Load comic text detector
    print('Loading comic text detector model...')
    from mokuro.cache import cache
    cache.comic_text_detector
    print('✓ Comic text detector model loaded')
    
    # Test Google Lens if available
    from mokuro.ocr_registry import OCRRegistry
    if 'lens' in OCRRegistry.get_available_engines():
        print('Testing Google Lens OCR...')
        lens = OCRRegistry.get_engine_instance('lens')
        if lens and lens.is_available:
            print('✓ Google Lens OCR is available')
        else:
            print('✗ Google Lens OCR is not properly configured')
    
except Exception as e:
    print(f'Warning during model pre-loading: {e}', file=sys.stderr)
"
fi

# Set process limits
ulimit -n 4096  # Increase file descriptor limit

# Log startup configuration
echo ""
echo "Server Configuration:"
echo "  Host: ${MOKURO_HOST:-0.0.0.0}"
echo "  Port: ${MOKURO_PORT:-7331}"
echo "  Debug: ${MOKURO_DEBUG:-false}"
echo "  Log Level: ${MOKURO_LOG_LEVEL:-INFO}"
echo "  Max Workers: ${MOKURO_MAX_WORKERS:-4}"
echo ""

# Handle signals properly
trap 'echo "Shutting down..."; exit 0' SIGTERM SIGINT

# Start the server
echo "Starting mokuro server..."
exec python3 mokuro_server.py