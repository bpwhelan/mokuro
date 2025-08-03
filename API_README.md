# Mokuro API Server

A REST API server that exposes mokuro's manga/comic OCR capabilities as a web service.

## Features

- **Single Image Processing**: Process individual manga/comic pages
- **Batch Processing**: Process multiple images in one request
- **Dynamic OCR Engine Support**: Automatically discovers available OCR engines
  - `manga-ocr` (default) - Fast, offline, specialized for Japanese manga
  - `lens` - Google Lens OCR with multilingual support
  - Additional engines can be added without API changes
- **Engine Discovery**: Query available engines and their capabilities
- **Detailed OCR Results**: Returns text content with precise positioning data
- **CORS Enabled**: Can be called from web applications
- **Simple REST API**: Easy to integrate with any programming language

## Supported Image Formats

The server supports the following image formats:
- **PNG** (.png)
- **JPEG** (.jpg, .jpeg)
- **WebP** (.webp)
- **AVIF** (.avif) - Requires Pillow 10.0.0+
- **BMP** (.bmp)
- **TIFF** (.tiff)

## Installation

1. Install server dependencies:
```bash
pip install -r requirements-server.txt
```

2. If you want to use Google Lens OCR, set it up:
```bash
./setup_lens.sh
```

## Usage

### Starting the Server

```bash
python mokuro_server.py
```

By default, the server runs on `http://localhost:7331` (port 7331 is chosen to avoid conflicts with common services like Flask's 5000, Django's 8000, etc.). You can configure it using environment variables:

```bash
export MOKURO_HOST=0.0.0.0        # Listen on all interfaces
export MOKURO_PORT=8080           # Custom port (default: 7331)
export MOKURO_DEBUG=true          # Enable debug mode
export MOKURO_PRELOAD_MODELS=true # Preload models on startup (default: true)
python mokuro_server.py
```

### API Endpoints

#### Health Check
```
GET /health
```
Returns server status and dynamically discovered OCR engines.

**Response Example:**
```json
{
  "status": "healthy",
  "version": "0.2.1",
  "available_engines": ["manga-ocr", "lens"]
}
```

#### API Info
```
GET /api/info
```
Returns detailed API documentation, capabilities, and comprehensive OCR engine information.

**Response includes:**
- API endpoints and parameters
- Supported file formats
- Available OCR engines with descriptions
- Engine availability status and requirements

**Response Example:**
```json
{
  "name": "Mokuro API Server",
  "version": "0.2.1",
  "endpoints": { ... },
  "ocr_engines": {
    "manga-ocr": "Fast offline OCR specialized for Japanese manga",
    "lens": "Google Lens OCR with multilingual support"
  },
  "ocr_engines_detailed": {
    "manga-ocr": {
      "description": "Fast offline OCR specialized for Japanese manga",
      "available": true,
      "requirements": ["manga-ocr Python package", "PyTorch", "Transformers library"],
      "suggested_language_code": "mo"
    },
    "lens": {
      "description": "Google Lens OCR with multilingual support",
      "available": true,
      "requirements": ["Node.js", "chrome-lens-ocr npm package", "lens_ocr_wrapper.js"],
      "suggested_language_code": "gl"
    }
  }
}
```

#### Process Single Image
```
POST /api/ocr
```

**Parameters:**
- `image` (file): The image file to process (required)
- `ocr_engine` (string): Either "manga-ocr" or "lens" (optional, default: "manga-ocr")
- `force_cpu` (boolean): Force CPU processing (optional, default: false)

**Example with curl:**
```bash
curl -X POST -F "image=@manga_page.jpg" http://localhost:7331/api/ocr
```

**Example with Python:**
```python
import requests

with open('manga_page.jpg', 'rb') as f:
    files = {'image': f}
    response = requests.post('http://localhost:7331/api/ocr', files=files)
    result = response.json()
```

#### Process Multiple Images
```
POST /api/ocr/batch
```

**Parameters:**
- `images` (files): Multiple image files to process (required)
- `ocr_engine` (string): Either "manga-ocr" or "lens" (optional, default: "manga-ocr")
- `force_cpu` (boolean): Force CPU processing (optional, default: false)

**Example with curl:**
```bash
curl -X POST \
  -F "images=@page1.jpg" \
  -F "images=@page2.jpg" \
  -F "images=@page3.jpg" \
  http://localhost:7331/api/ocr/batch
```

### Response Format

The API returns JSON data with the following structure:

```json
{
  "version": "0.2.0",
  "img_width": 827,
  "img_height": 1170,
  "ocr_engine": "manga-ocr",
  "filename": "page1.jpg",
  "blocks": [
    {
      "box": [37, 0, 863, 235],
      "vertical": false,
      "font_size": 137.5,
      "lines_coords": [
        [[582.0, 18.0], [785.0, 13.0], [787.0, 53.0], [583.0, 58.0]],
        [[37.0, 0.0], [863.0, 0.0], [863.0, 235.0], [37.0, 235.0]]
      ],
      "lines": ["ダイアリー・", "うちの猫ず日記"]
    }
  ]
}
```

**Field descriptions:**
- `version`: Mokuro version
- `img_width`, `img_height`: Image dimensions in pixels
- `ocr_engine`: Which OCR engine was used
- `filename`: Original filename
- `blocks`: Array of detected text blocks
  - `box`: Bounding box coordinates [x1, y1, x2, y2]
  - `vertical`: Whether text is vertical (true) or horizontal (false)
  - `font_size`: Estimated font size
  - `lines_coords`: Precise coordinates for each text line
  - `lines`: Array of text strings for each line

### Client Example

See `examples/api_client_example.py` for a complete example of how to use the API:

```bash
python examples/api_client_example.py path/to/manga_page.jpg
```

## Adding Custom OCR Engines

The server now supports dynamic OCR engine discovery. To add a new OCR engine:

1. **Create your OCR engine class:**
```python
# my_ocr_engine.py
from mokuro.ocr_registry import BaseOCR, register_ocr_engine

@register_ocr_engine("my-engine", "My custom OCR engine with special features")
class MyOCREngine(BaseOCR):
    def __init__(self, model_path=None, **kwargs):
        # Initialize your OCR model
        self.model = load_my_model(model_path)
    
    def __call__(self, image) -> str:
        # Process image (PIL Image, numpy array, or file path)
        return self.model.recognize(image)
    
    @property
    def is_available(self) -> bool:
        # Check if engine can be used
        try:
            import my_ocr_library
            return True
        except ImportError:
            return False
    
    @property
    def requirements(self) -> List[str]:
        return ["my-ocr-library>=1.0.0", "Additional requirements"]
```

2. **Import your module** - Add to mokuro's `__init__.py` or import in the server:
```python
import my_ocr_engine  # This registers the engine automatically
```

3. **That's it!** Your engine now:
   - Appears in `/health` and `/api/info` responses
   - Can be used by specifying `ocr_engine=my-engine`
   - Is validated automatically in API requests

### Docker Deployment

You can also run the server in Docker:

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . .

# Install Python dependencies
RUN pip install -r requirements-server.txt

# Setup Google Lens (optional)
RUN ./setup_lens.sh

# Expose port
EXPOSE 7331

# Run server
CMD ["python", "mokuro_server.py"]
```

Build and run:
```bash
docker build -t mokuro-api .
docker run -p 7331:7331 mokuro-api
```

## Performance Considerations

- **Model Preloading**: By default, the server preloads OCR models on startup to avoid cold starts. This means:
  - Server startup takes ~10-30 seconds (depending on hardware)
  - First request is as fast as subsequent requests
  - Models stay loaded in memory for instant processing
  - Disable with `MOKURO_PRELOAD_MODELS=false` if you prefer lazy loading
- **Memory Usage**: Each OCR model uses ~500MB-1GB of RAM when loaded
- **Google Lens OCR**: Includes rate limiting (0.5s delay between requests)
- **Production Deployment**: Use a proper WSGI server like Gunicorn:
  ```bash
  gunicorn -w 4 -b 0.0.0.0:7331 mokuro_server:app
  ```

## Error Handling

The API returns appropriate HTTP status codes:
- `200`: Success
- `400`: Bad request (missing file, invalid parameters)
- `413`: File too large (default limit: 50MB)
- `500`: Internal server error

Error responses include a JSON body with an `error` field explaining the issue.

## Security Notes

- The server accepts file uploads - ensure proper security measures in production
- Configure maximum file size according to your needs
- Consider adding authentication for production deployments
- Use HTTPS in production environments