# Mokuro API Server Documentation

**Version**: 0.3.6  
**Server Port**: 7331 (default)

## Table of Contents
1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Architecture](#architecture)
4. [API Endpoints](#api-endpoints)
5. [Priority Queue System](#priority-queue-system)
6. [OCR Engines](#ocr-engines)
7. [Configuration](#configuration)
8. [Error Handling](#error-handling)
9. [Integration Examples](#integration-examples)
10. [Performance & Limits](#performance--limits)

---

## Overview

The Mokuro API Server is a high-performance, priority-based OCR service designed specifically for manga and comic text extraction. It provides asynchronous processing with a sophisticated priority queue system, supporting multiple OCR engines and handling concurrent requests efficiently.

### Key Features
- **Priority-based request processing** with 5 priority levels
- **Asynchronous operation** - requests return immediately with tracking ID
- **Multiple OCR engine support** - 13+ OCR providers including specialized manga engines
- **Smart resource management** - separate pools for critical and normal requests
- **Engine pooling** - reuses OCR instances to minimize initialization overhead
- **Automatic result caching** - 5-minute TTL cache for completed results
- **Rate limiting** - per-IP request throttling
- **CORS enabled** - ready for web integration
- **OpenAPI/Swagger documentation** - available at `/docs`

### What It Does
The server extracts text from manga/comic images, returning structured data with:
- Text content for each detected region
- Bounding box coordinates for text blocks
- Line-by-line coordinates within blocks
- Font size estimation
- Vertical/horizontal text orientation detection

---

## Quick Start

### Starting the Server
```bash
# Default configuration (port 7331)
mokuro-api

# Custom configuration
MOKURO_API_PORT=8080 MOKURO_API_HOST=0.0.0.0 mokuro-api
```

### Basic Usage Example
```python
import requests
import time

# 1. Submit image for OCR
with open('manga_page.jpg', 'rb') as f:
    response = requests.post(
        'http://localhost:7331/api/ocr',
        files={'image': f},
        data={
            'priority': '2',  # NORMAL priority
            'ocr_engine': 'manga-ocr',
            'force_cpu': 'false'
        }
    )
    
result = response.json()
request_id = result['request_id']
print(f"Request queued: {request_id}")

# 2. Poll for results
while True:
    response = requests.get(f'http://localhost:7331/api/result/{request_id}')
    result = response.json()
    
    if result['status'] == 'completed':
        print("OCR Results:", result['result'])
        break
    elif result['status'] == 'failed':
        print("OCR Failed:", result['error'])
        break
    
    time.sleep(0.5)  # Wait before next poll
```

---

## Architecture

### Request Flow
1. **Client submits image** → Server returns `request_id` immediately
2. **Request enters priority queue** → Position based on priority level
3. **Background processor picks up request** → Based on priority and available workers
4. **OCR engine processes image** → Text detection and recognition
5. **Results stored in cache** → Available for retrieval
6. **Client polls for results** → Using the `request_id`

### Component Architecture
```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Client    │────▶│  API Server  │────▶│OCR Engines  │
└─────────────┘     └──────────────┘     └─────────────┘
                            │                    │
                    ┌──────────────┐     ┌─────────────┐
                    │Priority Queue│     │Engine Pool  │
                    └──────────────┘     └─────────────┘
                            │
                    ┌──────────────┐
                    │Result Cache  │
                    └──────────────┘
```

---

## API Endpoints

### 1. Health Check - `GET /health`

Check server health and get current statistics.

**Response:**
```json
{
  "status": "healthy",
  "version": "0.3.6",
  "stats": {
    "queue_length": 5,
    "active_critical": 2,
    "active_other": 1,
    "stats": {
      "total_queued": 150,
      "total_processed": 145,
      "total_cancelled": 0,
      "by_priority": {
        "0": 10,  // CRITICAL
        "1": 20,  // HIGH
        "2": 80,  // NORMAL
        "3": 25,  // LOW
        "4": 15   // BACKGROUND
      }
    },
    "engine_pool": {
      "total_engines": 2,
      "engines": [
        {
          "engine": "manga_ocr",
          "force_cpu": false,
          "usage_count": 145
        }
      ]
    }
  }
}
```

### 2. Submit OCR Request - `POST /api/ocr`

Submit an image for OCR processing.

**Request (multipart/form-data):**
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `image` | file | Yes | - | Image file (JPG, PNG, WebP, AVIF, JXL) |
| `priority` | string | No | "2" | Priority level (0-4) |
| `ocr_engine` | string | No | "manga-ocr" | OCR engine to use |
| `force_cpu` | string | No | "false" | Force CPU processing |

**Priority Levels:**
- `0` - CRITICAL: Highest priority, processed immediately
- `1` - HIGH: High priority processing
- `2` - NORMAL: Default priority
- `3` - LOW: Lower priority
- `4` - BACKGROUND: Lowest priority, batch processing

**Response:**
```json
{
  "status": "queued",
  "request_id": "a1b2c3d4",
  "priority": 2,
  "queue_position": 3,
  "estimated_wait_ms": 1500
}
```

**Error Responses:**
- `400` - Invalid parameters (bad priority, unknown engine, etc.)
- `413` - Image too large
- `503` - Queue full

**Size Limits:**
- All priorities: 100MB max per image

### 3. Get OCR Result - `GET /api/result/{request_id}`

Retrieve the OCR results for a submitted request.

**Response States:**

**Queued:**
```json
{
  "status": "queued"
}
```

**Processing:**
```json
{
  "status": "processing"
}
```

**Completed:**
```json
{
  "status": "completed",
  "result": {
    "version": "0.2.2",
    "img_width": 827,
    "img_height": 1170,
    "blocks": [
      {
        "box": [37, 0, 863, 235],
        "vertical": false,
        "font_size": 137.5,
        "lines_coords": [
          [[582.0, 18.0], [785.0, 13.0], [787.0, 53.0], [583.0, 58.0]],
          [[37.0, 0.0], [863.0, 0.0], [863.0, 235.0], [37.0, 235.0]]
        ],
        "lines": [
          "第1話",
          "魔法少女と契約"
        ]
      }
    ]
  }
}
```

**Failed:**
```json
{
  "status": "failed",
  "error": "Invalid image format"
}
```

**Error Response:**
- `404` - Request ID not found

### 4. Queue Status - `GET /api/queue/status`

Get detailed queue and processing statistics.

**Response:**
```json
{
  "queue_length": 8,
  "active_critical": 3,
  "active_other": 2,
  "stats": {
    "total_queued": 1543,
    "total_processed": 1535,
    "total_cancelled": 0,
    "by_priority": {
      "0": 100,
      "1": 243,
      "2": 800,
      "3": 300,
      "4": 100
    }
  },
  "engine_pool": {
    "total_engines": 3,
    "engines": [
      {
        "engine": "manga_ocr",
        "force_cpu": false,
        "usage_count": 1200
      },
      {
        "engine": "owocr:glens",
        "force_cpu": false,
        "usage_count": 335
      }
    ]
  }
}
```

### 5. OCR Engine Information - `GET /api/info`

Get available OCR engines and their capabilities.

**Response:**
```json
{
  "ocr_engines_detailed": {
    "manga-ocr": {
      "description": "Manga OCR OCR engine",
      "display_name": "Manga OCR",
      "available": true,
      "version": "1.0.0",
      "capabilities": ["text_detection", "text_recognition", "manga_optimized"],
      "suggested_language_code": "mo"
    },
    "lens": {
      "description": "Google Lens OCR engine",
      "display_name": "Google Lens",
      "available": true,
      "version": "1.0.0",
      "capabilities": ["text_detection", "text_recognition", "multilingual", "web_based"],
      "suggested_language_code": "gl"
    }
  }
}
```

### 6. OpenAPI Documentation - `GET /docs`

Interactive Swagger UI documentation for the API.

### 7. OpenAPI Specification - `GET /openapi.json`

Machine-readable OpenAPI specification.

---

## Priority Queue System

### How It Works

The server uses a sophisticated priority queue system that ensures critical requests are processed first while maintaining fairness for lower-priority requests.

#### Queue Behavior
1. **Priority Ordering**: Requests are processed in priority order (0 = highest, 4 = lowest)
2. **FIFO Within Priority**: Requests with the same priority are processed first-in-first-out
3. **Queue Position**: Calculated based on how many equal or higher priority requests are ahead
4. **Eviction Policy**: Higher priority requests can evict lower priority ones when queue is full

#### Worker Pools
- **Critical Pool**: 4 concurrent workers for CRITICAL (priority 0) requests
- **Other Pool**: 2 concurrent workers for all other priorities (1-4)
- **Exclusivity**: When critical requests are processing, other priorities wait

#### Priority Clamping
- Invalid negative values → clamped to 0 (CRITICAL)
- Invalid high values (>4) → clamped to 4 (BACKGROUND)
- No priority specified → defaults to 2 (NORMAL)

### Example Priority Scenarios

**Scenario 1: Mixed Priority Queue**
```
Queue: [CRITICAL, CRITICAL, HIGH, NORMAL, NORMAL, LOW, BACKGROUND]
Processing Order: Exactly as shown (priority order)
```

**Scenario 2: Queue Full with Eviction**
```
Queue Full (50 requests, all NORMAL)
New CRITICAL request arrives → Evicts lowest priority request
New BACKGROUND request arrives → Rejected (503 error)
```

---

## OCR Engines

### Available Engines

| Engine ID | Display Name | Requirements | Platform | Description |
|-----------|--------------|--------------|----------|-------------|
| `manga-ocr` | Manga OCR | manga-ocr, torch | All | Specialized for Japanese manga |
| `lens` | Google Lens | owocr[lens] | All | Google's OCR via Lens API |
| `lensweb` | Google Lens (web) | owocr[lensweb] | All | Web-based Google Lens |
| `easyocr` | EasyOCR | owocr[easyocr] | All | Multi-language OCR |
| `rapidocr` | RapidOCR | owocr[rapidocr] | All | Fast ONNX-based OCR |
| `gvision` | Google Vision | owocr[gvision], credentials | All | Google Cloud Vision API |
| `azure` | Azure Image Analysis | owocr[azure], API keys | All | Azure Cognitive Services |
| `bing` | Bing | owocr | All | Bing OCR service |
| `ocrspace` | OCRSpace | owocr, API key | All | OCRSpace online service |
| `avision` | Apple Vision | owocr, pyobjc | macOS | Apple's Vision framework |
| `alivetext` | Apple Live Text | owocr, pyobjc | macOS | Apple's Live Text |
| `winrtocr` | WinRT OCR | owocr[winocr] | Windows | Windows Runtime OCR |
| `oneocr` | OneOCR | oneocr | Windows | Windows OneOCR |

### Engine Selection Guidelines

**For Manga/Comics:**
- `manga-ocr`: Best for Japanese manga (vertical & horizontal text)
- `lens`: Good accuracy, handles various languages
- `lensweb`: Alternative to lens, web-based

**For Speed:**
- `rapidocr`: Fastest offline option
- `easyocr`: Good balance of speed and accuracy

**For Accuracy:**
- `gvision`: Highest accuracy (requires Google Cloud account)
- `azure`: Enterprise-grade accuracy (requires Azure account)

### Engine Pooling

The server maintains a pool of OCR engine instances to avoid initialization overhead:
- Engines are created on first use
- Instances are reused across requests
- Separate instances for CPU/GPU modes
- Thread-safe with per-engine locks

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MOKURO_API_HOST` | 0.0.0.0 | Server bind address |
| `MOKURO_API_PORT` | 7331 | Server port |
| `MOKURO_MAX_UPLOAD_BYTES` | 104857600 | Max upload size (100MB) |
| `MOKURO_MAX_PARALLEL_CRITICAL` | 4 | Max concurrent critical requests |
| `MOKURO_MAX_PARALLEL_OTHER` | 2 | Max concurrent other requests |
| `MOKURO_REQUEST_QUEUE_SIZE` | 50 | Maximum queue size |
| `MOKURO_OCR_TIMEOUT` | 30 | OCR processing timeout (seconds) |
| `MOKURO_CACHE_TTL` | 300 | Result cache TTL (seconds) |
| `MOKURO_PRELOAD_MODELS` | true | Preload models on startup |

### OCR Engine Configuration

**Google Vision:**
```bash
# Place credentials at ~/.config/google_vision.json
export GOOGLE_APPLICATION_CREDENTIALS=~/.config/google_vision.json
```

**Azure:**
```bash
export AZURE_VISION_ENDPOINT=https://your-resource.cognitiveservices.azure.com/
export AZURE_VISION_API_KEY=your-api-key
```

**OCRSpace:**
```bash
export OCRSPACE_API_KEY=your-api-key
```

---

## Error Handling

### HTTP Status Codes

| Code | Meaning | Common Causes |
|------|---------|---------------|
| 200 | Success | Request processed successfully |
| 400 | Bad Request | Invalid parameters, unknown engine |
| 404 | Not Found | Request ID doesn't exist |
| 413 | Payload Too Large | Image exceeds size limit |
| 422 | Unprocessable Entity | Validation error |
| 503 | Service Unavailable | Queue full |

### Error Response Format
```json
{
  "detail": "Error description"
}
```

### Common Error Scenarios

**Invalid Priority:**
```json
{
  "detail": "Invalid priority value: abc. Must be 0-4"
}
```

**Unknown Engine:**
```json
{
  "detail": "Invalid engine: unknown-engine"
}
```

**Queue Full:**
```json
{
  "detail": "Queue full with equal or higher priority requests"
}
```

**Image Too Large:**
```json
{
  "detail": "Image too large: 125.3MB (max 100.0MB)"
}
```

---

## Integration Examples

### Python Client with Retry Logic
```python
import requests
import time
from typing import Optional, Dict

class MokuroClient:
    def __init__(self, base_url: str = "http://localhost:7331"):
        self.base_url = base_url
        self.session = requests.Session()
    
    def process_image(
        self,
        image_path: str,
        priority: int = 2,
        engine: str = "manga-ocr",
        timeout: int = 30
    ) -> Optional[Dict]:
        """Process an image with OCR"""
        
        # Submit request
        with open(image_path, 'rb') as f:
            response = self.session.post(
                f"{self.base_url}/api/ocr",
                files={'image': f},
                data={
                    'priority': str(priority),
                    'ocr_engine': engine,
                    'force_cpu': 'false'
                }
            )
        
        if response.status_code != 200:
            raise Exception(f"Submit failed: {response.text}")
        
        request_id = response.json()['request_id']
        
        # Poll for results
        start_time = time.time()
        while time.time() - start_time < timeout:
            response = self.session.get(
                f"{self.base_url}/api/result/{request_id}"
            )
            
            if response.status_code == 404:
                raise Exception("Request ID not found")
            
            result = response.json()
            status = result['status']
            
            if status == 'completed':
                return result['result']
            elif status == 'failed':
                raise Exception(f"OCR failed: {result.get('error', 'Unknown error')}")
            
            # Adaptive polling - start fast, slow down over time
            elapsed = time.time() - start_time
            if elapsed < 2:
                time.sleep(0.1)
            elif elapsed < 5:
                time.sleep(0.5)
            else:
                time.sleep(1.0)
        
        raise TimeoutError(f"OCR timeout after {timeout} seconds")

# Usage
client = MokuroClient()
result = client.process_image(
    "manga_page.jpg",
    priority=1,  # HIGH priority
    engine="lens"
)
print(f"Found {len(result['blocks'])} text blocks")
```

### JavaScript/TypeScript Client
```typescript
interface OCRResult {
  version: string;
  img_width: number;
  img_height: number;
  blocks: Array<{
    box: [number, number, number, number];
    vertical: boolean;
    font_size: number;
    lines_coords: number[][][];
    lines: string[];
  }>;
}

class MokuroClient {
  private baseUrl: string;

  constructor(baseUrl: string = 'http://localhost:7331') {
    this.baseUrl = baseUrl;
  }

  async processImage(
    imageFile: File,
    priority: number = 2,
    engine: string = 'manga-ocr'
  ): Promise<OCRResult> {
    // Submit request
    const formData = new FormData();
    formData.append('image', imageFile);
    formData.append('priority', priority.toString());
    formData.append('ocr_engine', engine);
    formData.append('force_cpu', 'false');

    const submitResponse = await fetch(`${this.baseUrl}/api/ocr`, {
      method: 'POST',
      body: formData
    });

    if (!submitResponse.ok) {
      throw new Error(`Submit failed: ${await submitResponse.text()}`);
    }

    const { request_id } = await submitResponse.json();

    // Poll for results
    const maxAttempts = 60;
    const delays = [100, 100, 200, 200, 500, 500, 1000]; // ms

    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      const resultResponse = await fetch(
        `${this.baseUrl}/api/result/${request_id}`
      );

      if (!resultResponse.ok) {
        throw new Error('Request not found');
      }

      const result = await resultResponse.json();

      if (result.status === 'completed') {
        return result.result;
      } else if (result.status === 'failed') {
        throw new Error(`OCR failed: ${result.error}`);
      }

      // Wait before next poll
      const delay = delays[Math.min(attempt, delays.length - 1)];
      await new Promise(resolve => setTimeout(resolve, delay));
    }

    throw new Error('OCR timeout');
  }
}
```

### Batch Processing Example
```python
import asyncio
import aiohttp
from pathlib import Path

async def process_batch(image_paths, priority=2):
    """Process multiple images concurrently"""
    base_url = "http://localhost:7331"
    
    async with aiohttp.ClientSession() as session:
        # Submit all images
        request_ids = []
        for path in image_paths:
            with open(path, 'rb') as f:
                data = aiohttp.FormData()
                data.add_field('image', f, filename=Path(path).name)
                data.add_field('priority', str(priority))
                data.add_field('ocr_engine', 'manga-ocr')
                
                async with session.post(f"{base_url}/api/ocr", data=data) as resp:
                    result = await resp.json()
                    request_ids.append((path, result['request_id']))
        
        # Collect results
        results = {}
        pending = request_ids.copy()
        
        while pending:
            await asyncio.sleep(0.5)
            still_pending = []
            
            for path, request_id in pending:
                async with session.get(f"{base_url}/api/result/{request_id}") as resp:
                    result = await resp.json()
                    
                    if result['status'] == 'completed':
                        results[path] = result['result']
                    elif result['status'] == 'failed':
                        results[path] = {'error': result.get('error')}
                    else:
                        still_pending.append((path, request_id))
            
            pending = still_pending
        
        return results

# Usage
images = ['page1.jpg', 'page2.jpg', 'page3.jpg']
results = asyncio.run(process_batch(images, priority=1))
```

---

## Performance & Limits

### Request Limits
- **Max image size**: 100MB (all priorities)
- **Max filename length**: 255 characters
- **Max queue size**: 50 requests
- **Request timeout**: 30 seconds default
- **Result cache TTL**: 5 minutes

### Performance Characteristics
- **Queue response time**: <10ms
- **OCR processing time**: 0.5-3 seconds per image (engine dependent)
- **Concurrent processing**: Up to 6 requests (4 critical + 2 other)
- **Engine initialization**: First request ~2-5 seconds, subsequent <100ms

### Optimization Tips

1. **Use appropriate priority levels:**
   - CRITICAL: User-facing, real-time needs
   - HIGH: Important but can wait briefly
   - NORMAL: Standard processing
   - LOW: Batch jobs with flexible timing
   - BACKGROUND: Non-urgent bulk processing

2. **Engine selection for performance:**
   - `rapidocr`: Fastest for simple text
   - `manga-ocr`: Best for manga/comics
   - `lens`: Good balance of speed/accuracy

3. **Batch processing:**
   - Submit multiple requests with BACKGROUND priority
   - Use async/concurrent clients for parallel submission
   - Monitor queue status to avoid overload

---

## Monitoring & Debugging

### Health Monitoring
```bash
# Check server health and stats
curl http://localhost:7331/health | jq

# Monitor queue status
watch -n 1 'curl -s http://localhost:7331/api/queue/status | jq'
```

### Log Analysis
The server uses structured logging with request IDs:
```
2024-01-15 10:23:45.123 | INFO     | a1b2c3d4     | P2 | Queued NORMAL request | Position: 3
2024-01-15 10:23:45.456 | INFO     | a1b2c3d4     | P2 | Started processing NORMAL request
2024-01-15 10:23:47.789 | SUCCESS  | a1b2c3d4     | P2 | NORMAL request completed
```

### Common Issues & Solutions

**Issue: Requests timing out**
- Check `/health` for queue length
- Consider using higher priority
- Verify OCR engine is working

**Issue: 503 Queue Full errors**
- Reduce submission rate
- Use background priority for batch jobs
- Increase `MOKURO_REQUEST_QUEUE_SIZE`

**Issue: Slow processing**
- Check if forcing CPU mode
- Monitor engine pool usage

---

## Security Considerations

### Input Validation
- Filename sanitization (path traversal prevention)
- File size limits based on priority
- Priority value clamping (0-4)
- Unknown form field size limits

### Rate Limiting
- Per-IP request limits via slowapi
- Queue size limits
- Priority-based eviction

### CORS Configuration
- Currently allows all origins (`*`)
- Configure for production use

---

## Appendix

### OCR Result Schema
```typescript
interface OCRResult {
  version: string;           // OCR version (e.g., "0.2.2")
  img_width: number;         // Image width in pixels
  img_height: number;        // Image height in pixels
  blocks: TextBlock[];       // Array of detected text blocks
}

interface TextBlock {
  box: [number, number, number, number];  // [x1, y1, x2, y2] bounding box
  vertical: boolean;         // Text orientation
  font_size: number;         // Estimated font size
  lines_coords: number[][][]; // Coordinates for each line
  lines: string[];           // Extracted text lines
}
```

### Complete cURL Examples
```bash
# Submit with CRITICAL priority
curl -X POST http://localhost:7331/api/ocr \
  -F "image=@manga_page.jpg" \
  -F "priority=0" \
  -F "ocr_engine=manga-ocr"

# Check result
curl http://localhost:7331/api/result/a1b2c3d4

# Get queue status
curl http://localhost:7331/api/queue/status

# Get available engines
curl http://localhost:7331/api/info

# Health check
curl http://localhost:7331/health
```

### Docker Deployment
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .

RUN pip install mokuro[api]

EXPOSE 7331

CMD ["mokuro-api"]
```

```yaml
# docker-compose.yml
version: '3.8'
services:
  mokuro-api:
    build: .
    ports:
      - "7331:7331"
    environment:
      - MOKURO_API_HOST=0.0.0.0
      - MOKURO_API_PORT=7331
      - MOKURO_MAX_PARALLEL_CRITICAL=4
      - MOKURO_MAX_PARALLEL_OTHER=2
    volumes:
      - ./config:/app/config
    restart: unless-stopped
```

---

## Support & Resources

- **GitHub Repository**: https://github.com/kha-white/mokuro
- **Issue Tracker**: https://github.com/kha-white/mokuro/issues
- **OpenAPI Docs**: http://localhost:7331/docs (when running)

---

*Last Updated: API Version 0.3.6*
