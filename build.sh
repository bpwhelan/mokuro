#!/bin/bash

# Mokuro Docker Build Script
# This script handles all aspects of building and deploying Mokuro containers
# including Google Lens OCR setup, multi-architecture builds, and GHCR publishing

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
IMAGE_NAME="mokuro-server"
REGISTRY="ghcr.io"
REGISTRY_USER="xrishox"
REGISTRY_IMAGE="${REGISTRY}/${REGISTRY_USER}/mokuro"
PLATFORM="linux/amd64"
PUSH=false
MULTIARCH=false
TAG="latest"
BUILD_CACHE=true
FORCE_REBUILD=false

# Print colored message
print_message() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Print usage information
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Mokuro Docker Build Script

OPTIONS:
    -h, --help              Show this help message
    -t, --tag TAG           Docker image tag (default: latest)
    -p, --push              Push image to registry after building
    -m, --multiarch         Build multi-architecture image (amd64 + arm64)
    -r, --registry REG      Registry URL (default: ghcr.io)
    -u, --user USER         Registry username (default: xrishox)
    --no-cache              Disable Docker build cache
    --force                 Force rebuild even if image exists
    --local-only            Build for local use only (no registry tags)

EXAMPLES:
    # Build local image
    $0

    # Build and push to GHCR
    $0 --push

    # Build multi-arch and push with custom tag
    $0 --multiarch --push --tag v1.0.0

    # Build for different registry
    $0 --registry docker.io --user myusername --push

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            usage
            exit 0
            ;;
        -t|--tag)
            TAG="$2"
            shift 2
            ;;
        -p|--push)
            PUSH=true
            shift
            ;;
        -m|--multiarch)
            MULTIARCH=true
            PLATFORM="linux/amd64,linux/arm64"
            shift
            ;;
        -r|--registry)
            REGISTRY="$2"
            REGISTRY_IMAGE="${REGISTRY}/${REGISTRY_USER}/mokuro"
            shift 2
            ;;
        -u|--user)
            REGISTRY_USER="$2"
            REGISTRY_IMAGE="${REGISTRY}/${REGISTRY_USER}/mokuro"
            shift 2
            ;;
        --no-cache)
            BUILD_CACHE=false
            shift
            ;;
        --force)
            FORCE_REBUILD=true
            shift
            ;;
        --local-only)
            REGISTRY_IMAGE=""
            shift
            ;;
        *)
            print_message $RED "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Check prerequisites
check_prerequisites() {
    print_message $BLUE "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_message $RED "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    # Check if Docker daemon is running
    if ! docker info &> /dev/null; then
        print_message $RED "Docker daemon is not running. Please start Docker."
        exit 1
    fi
    
    # Check for buildx if multiarch
    if [ "$MULTIARCH" = true ]; then
        if ! docker buildx version &> /dev/null; then
            print_message $RED "Docker Buildx is required for multi-architecture builds."
            exit 1
        fi
    fi
    
    print_message $GREEN "✓ Prerequisites check passed"
}

# Setup buildx for multi-architecture builds
setup_buildx() {
    if [ "$MULTIARCH" = true ]; then
        print_message $BLUE "Setting up Docker Buildx for multi-architecture build..."
        
        # Create buildx builder if it doesn't exist
        if ! docker buildx ls | grep -q "mokuro-builder"; then
            docker buildx create --name mokuro-builder --driver docker-container --use
            print_message $GREEN "✓ Created buildx builder: mokuro-builder"
        else
            docker buildx use mokuro-builder
            print_message $GREEN "✓ Using existing buildx builder: mokuro-builder"
        fi
    fi
}

# Create optimized Dockerfile for builds
create_dockerfile() {
    print_message $BLUE "Creating optimized Dockerfile..."
    
    cat > Dockerfile.build << 'EOF'
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
# Group apt operations to reduce layers
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
    # Additional dependencies for ARM builds
    libopenblas-dev \
    liblapack-dev \
    gfortran \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first for better caching
COPY requirements-server.txt pyproject.toml ./
COPY package.json lens_ocr_wrapper.js ./

# Install Python dependencies
# Use --no-deps for mokuro to avoid reinstalling dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir numpy && \
    pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu || \
    pip install --no-cache-dir torch torchvision && \
    pip install --no-cache-dir -r requirements-server.txt

# Setup Google Lens OCR
# Install chrome-lens-ocr and create node_modules
RUN npm install && \
    # Ensure lens wrapper has correct permissions
    chmod +x lens_ocr_wrapper.js

# Copy the rest of the application
COPY . .

# Install mokuro package
RUN pip install --no-cache-dir -e .

# Create necessary directories
RUN mkdir -p /tmp/mokuro_api /app/cache

# Expose port
EXPOSE 7331

# Set environment variables
ENV MOKURO_HOST=0.0.0.0
ENV MOKURO_PORT=7331
ENV MOKURO_PRELOAD_MODELS=true
# Force CPU for ARM builds
ENV FORCE_CPU=${FORCE_CPU:-false}

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:7331/health').raise_for_status()"

# Run server
CMD ["python", "mokuro_server.py"]
EOF
    
    print_message $GREEN "✓ Dockerfile created"
}

# Build Docker image
build_image() {
    print_message $BLUE "Building Docker image..."
    
    # Create Dockerfile
    create_dockerfile
    
    # Build arguments
    local BUILD_ARGS=""
    if [ "$BUILD_CACHE" = false ]; then
        BUILD_ARGS="$BUILD_ARGS --no-cache"
    fi
    
    # Set FORCE_CPU for ARM builds
    if [[ "$PLATFORM" == *"arm"* ]]; then
        BUILD_ARGS="$BUILD_ARGS --build-arg FORCE_CPU=true"
    fi
    
    # Build command
    if [ "$MULTIARCH" = true ]; then
        # Multi-architecture build
        local TAGS=""
        if [ -n "$REGISTRY_IMAGE" ]; then
            TAGS="$TAGS -t ${REGISTRY_IMAGE}:${TAG}"
            if [ "$TAG" != "latest" ]; then
                TAGS="$TAGS -t ${REGISTRY_IMAGE}:latest"
            fi
        fi
        TAGS="$TAGS -t ${IMAGE_NAME}:${TAG}"
        
        if [ "$PUSH" = true ] && [ -n "$REGISTRY_IMAGE" ]; then
            # Build and push in one step for multi-arch
            print_message $YELLOW "Building and pushing multi-architecture image..."
            docker buildx build \
                --platform ${PLATFORM} \
                ${BUILD_ARGS} \
                ${TAGS} \
                --push \
                -f Dockerfile.build \
                .
        else
            # Just build locally
            docker buildx build \
                --platform ${PLATFORM} \
                ${BUILD_ARGS} \
                ${TAGS} \
                --load \
                -f Dockerfile.build \
                .
        fi
    else
        # Single architecture build
        docker build \
            ${BUILD_ARGS} \
            -t ${IMAGE_NAME}:${TAG} \
            -f Dockerfile.build \
            .
        
        # Tag for registry if specified
        if [ -n "$REGISTRY_IMAGE" ]; then
            docker tag ${IMAGE_NAME}:${TAG} ${REGISTRY_IMAGE}:${TAG}
            if [ "$TAG" != "latest" ]; then
                docker tag ${IMAGE_NAME}:${TAG} ${REGISTRY_IMAGE}:latest
            fi
        fi
    fi
    
    # Clean up
    rm -f Dockerfile.build
    
    print_message $GREEN "✓ Docker image built successfully"
}

# Push image to registry
push_image() {
    if [ "$PUSH" = true ] && [ -n "$REGISTRY_IMAGE" ] && [ "$MULTIARCH" = false ]; then
        print_message $BLUE "Pushing image to ${REGISTRY}..."
        
        docker push ${REGISTRY_IMAGE}:${TAG}
        if [ "$TAG" != "latest" ]; then
            docker push ${REGISTRY_IMAGE}:latest
        fi
        
        print_message $GREEN "✓ Image pushed to ${REGISTRY_IMAGE}:${TAG}"
    fi
}

# Test the built image
test_image() {
    print_message $BLUE "Testing Docker image..."
    
    # Run container in background
    local CONTAINER_NAME="mokuro-test-$(date +%s)"
    docker run -d --name ${CONTAINER_NAME} -p 7331:7331 ${IMAGE_NAME}:${TAG}
    
    # Wait for container to start
    print_message $YELLOW "Waiting for container to start..."
    sleep 10
    
    # Check if container is running
    if ! docker ps | grep -q ${CONTAINER_NAME}; then
        print_message $RED "Container failed to start. Logs:"
        docker logs ${CONTAINER_NAME}
        docker rm -f ${CONTAINER_NAME} 2>/dev/null
        exit 1
    fi
    
    # Test health endpoint
    if curl -f http://localhost:7331/health 2>/dev/null | grep -q "healthy"; then
        print_message $GREEN "✓ Container health check passed"
    else
        print_message $RED "Container health check failed"
        docker logs ${CONTAINER_NAME}
        docker rm -f ${CONTAINER_NAME} 2>/dev/null
        exit 1
    fi
    
    # Clean up
    docker rm -f ${CONTAINER_NAME} 2>/dev/null
    print_message $GREEN "✓ Image test completed successfully"
}

# Print summary
print_summary() {
    echo
    print_message $GREEN "===== Build Summary ====="
    print_message $BLUE "Image: ${IMAGE_NAME}:${TAG}"
    if [ -n "$REGISTRY_IMAGE" ]; then
        print_message $BLUE "Registry: ${REGISTRY_IMAGE}:${TAG}"
    fi
    print_message $BLUE "Platform: ${PLATFORM}"
    print_message $BLUE "Pushed: ${PUSH}"
    
    echo
    print_message $GREEN "To run the container:"
    echo "docker run -p 7331:7331 ${IMAGE_NAME}:${TAG}"
    
    if [ "$PUSH" = true ] && [ -n "$REGISTRY_IMAGE" ]; then
        echo
        print_message $GREEN "To pull from registry:"
        echo "docker pull ${REGISTRY_IMAGE}:${TAG}"
    fi
}

# Main execution
main() {
    print_message $GREEN "===== Mokuro Docker Build Script ====="
    
    # Check prerequisites
    check_prerequisites
    
    # Setup buildx if needed
    setup_buildx
    
    # Build image
    build_image
    
    # Push if requested (for single arch, multi-arch pushes during build)
    push_image
    
    # Test the image (skip for multi-arch remote builds)
    if [ "$MULTIARCH" = false ] || [ "$PUSH" = false ]; then
        test_image
    fi
    
    # Print summary
    print_summary
}

# Run main function
main