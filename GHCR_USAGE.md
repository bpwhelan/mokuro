# Using Mokuro Server from GitHub Container Registry

## Quick Start

Pull and run the latest version:

```bash
docker pull ghcr.io/xrishox/mokuro-server:latest
docker run -p 7331:7331 ghcr.io/xrishox/mokuro-server:latest
```

Or use a specific version:

```bash
docker pull ghcr.io/xrishox/mokuro-server:0.2.2
docker run -p 7331:7331 ghcr.io/xrishox/mokuro-server:0.2.2
```

## Docker Compose

Create a `docker-compose.yml`:

```yaml
version: '3.8'

services:
  mokuro-server:
    image: ghcr.io/xrishox/mokuro-server:latest
    ports:
      - "7331:7331"
    environment:
      - MOKURO_HOST=0.0.0.0
      - MOKURO_PORT=7331
      - MOKURO_PRELOAD_MODELS=true
    volumes:
      - mokuro-models:/root/.cache
      - ./cache:/app/cache
    restart: unless-stopped

volumes:
  mokuro-models:
    driver: local
```

Then run:
```bash
docker-compose up -d
```

## API Usage

### Health Check
```bash
curl http://localhost:7331/health
```

### OCR with manga-ocr (default)
```bash
curl -X POST -F "image=@your_manga_page.jpg" \
  http://localhost:7331/api/ocr
```

### OCR with Google Lens
```bash
curl -X POST -F "image=@your_manga_page.jpg" \
  -F "ocr_engine=lens" \
  http://localhost:7331/api/ocr
```

## Features

- ✅ Dual OCR engines (manga-ocr and Google Lens)
- ✅ Pre-loaded models for fast startup
- ✅ REST API on port 7331
- ✅ Health monitoring endpoint
- ✅ Ubuntu Noble (24.04) base
- ✅ Non-root user for security

## Image Details

- **Registry**: GitHub Container Registry (ghcr.io)
- **Repository**: xrishox/mokuro-server
- **Base OS**: Ubuntu 24.04 (Noble)
- **Python**: 3.12
- **Node.js**: 20.x LTS
- **Size**: ~10.7GB (includes ML models)

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MOKURO_HOST` | `0.0.0.0` | Server bind address |
| `MOKURO_PORT` | `7331` | Server port |
| `MOKURO_DEBUG` | `false` | Enable debug mode |
| `MOKURO_LOG_LEVEL` | `INFO` | Log level |
| `MOKURO_MAX_WORKERS` | `4` | Worker threads |
| `MOKURO_PRELOAD_MODELS` | `true` | Pre-load ML models |

## Troubleshooting

If you get a permission error pulling the image, make sure the package is public:
1. Go to https://github.com/xrishox?tab=packages
2. Find `mokuro-server`
3. Click on Package settings
4. Make sure visibility is set to "Public"