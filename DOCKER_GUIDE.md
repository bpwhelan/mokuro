# Mokuro Server Docker Guide

This guide explains how to build and run mokuro-server in a Docker container with full support for both manga-ocr and Google Lens OCR engines.

## Features

- **Dual OCR Engine Support**: Both manga-ocr (offline) and Google Lens OCR (online, multilingual)
- **Ubuntu Noble (24.04) Base**: Modern, stable foundation
- **Multi-stage Build**: Optimized image size (~3-4GB final size)
- **Pre-cached Models**: Models are downloaded during build for faster startup
- **Production Ready**: Health checks, resource limits, logging, and security best practices

## Quick Start

### Building the Image

```bash
# Build the Docker image
docker build -f Dockerfile.server -t mokuro-server:latest .

# Or use docker-compose
docker-compose -f docker-compose.server.yml build
```

### Running the Container

#### Basic Usage

```bash
# Run with default settings
docker run -p 7331:7331 mokuro-server:latest

# Run with docker-compose
docker-compose -f docker-compose.server.yml up
```

#### With Persistent Model Cache

```bash
# Create a volume for model cache
docker volume create mokuro-models

# Run with persistent cache
docker run -p 7331:7331 \
  -v mokuro-models:/root/.cache \
  mokuro-server:latest
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MOKURO_HOST` | `0.0.0.0` | Server bind address |
| `MOKURO_PORT` | `7331` | Server port |
| `MOKURO_DEBUG` | `false` | Enable debug mode |
| `MOKURO_LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `MOKURO_MAX_WORKERS` | `4` | Maximum worker threads |
| `MOKURO_PRELOAD_MODELS` | `true` | Pre-load models on startup |

### Resource Configuration

The docker-compose file includes resource limits:

```yaml
deploy:
  resources:
    limits:
      cpus: '4'
      memory: 8G
    reservations:
      cpus: '2'
      memory: 4G
```

Adjust these based on your system resources.

## API Usage

### Health Check

```bash
curl http://localhost:7331/health
```

Response:
```json
{
  "status": "healthy",
  "version": "0.3.0",
  "available_engines": ["manga-ocr", "lens"]
}
```

### Process Single Image

```bash
# Using manga-ocr (default)
curl -X POST -F "image=@manga_page.jpg" \
  http://localhost:7331/api/ocr

# Using Google Lens OCR
curl -X POST -F "image=@manga_page.jpg" \
  -F "ocr_engine=lens" \
  http://localhost:7331/api/ocr
```

### Process Volume

```bash
# Process entire volume with manga-ocr
curl -X POST -F "file=@volume.zip" \
  http://localhost:7331/api/process-volume

# Process with Google Lens
curl -X POST -F "file=@volume.zip" \
  -F "ocr_engine=lens" \
  http://localhost:7331/api/process-volume
```

## Volumes and Persistence

The container uses several volumes:

1. **Model Cache** (`/root/.cache`): Pre-trained models
2. **Application Cache** (`/app/cache`): Processing cache
3. **Temporary Files** (`/tmp/mokuro_api`): Temporary processing files

Example with all volumes:

```bash
docker run -p 7331:7331 \
  -v mokuro-models:/root/.cache \
  -v ./cache:/app/cache \
  -v ./input:/app/input:ro \
  -v ./output:/app/output \
  mokuro-server:latest
```

## Production Deployment

### With NGINX Reverse Proxy

The docker-compose file includes an optional NGINX configuration:

```bash
# Start with production profile
docker-compose -f docker-compose.server.yml --profile production up
```

Create an `nginx.conf` file:

```nginx
events {
    worker_connections 1024;
}

http {
    upstream mokuro {
        server mokuro-server:7331;
    }

    server {
        listen 80;
        server_name your-domain.com;

        client_max_body_size 100M;

        location / {
            proxy_pass http://mokuro;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}
```

### Security Considerations

1. The container runs as a non-root user (`mokuro`)
2. Only necessary ports are exposed
3. Resource limits prevent runaway processes
4. Health checks ensure availability

### Monitoring

View logs:
```bash
# Docker logs
docker logs mokuro-server

# Docker-compose logs
docker-compose -f docker-compose.server.yml logs -f
```

Check resource usage:
```bash
docker stats mokuro-server
```

## Troubleshooting

### Common Issues

1. **Out of Memory**: Increase memory limits in docker-compose.yml
2. **Model Download Fails**: Check internet connection during build
3. **Google Lens Not Working**: Ensure chrome-lens-ocr npm package is properly installed

### Debug Mode

Run with debug logging:
```bash
docker run -p 7331:7331 \
  -e MOKURO_DEBUG=true \
  -e MOKURO_LOG_LEVEL=DEBUG \
  mokuro-server:latest
```

### Rebuild Without Cache

Force a clean rebuild:
```bash
docker build --no-cache -f Dockerfile.server -t mokuro-server:latest .
```

## GPU Support

To use GPU acceleration (if available):

1. Install NVIDIA Container Toolkit
2. Modify docker-compose.yml:

```yaml
services:
  mokuro-server:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

3. Run with GPU support:
```bash
docker-compose -f docker-compose.server.yml up
```

## Development

For development with live code updates:

```bash
docker run -p 7331:7331 \
  -v $(pwd):/app \
  -e MOKURO_DEBUG=true \
  mokuro-server:latest
```

## License

This Docker configuration follows the same license as the mokuro project.