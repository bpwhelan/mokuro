#!/bin/bash
# Build script for mokuro-server Docker image

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
IMAGE_NAME="mokuro-server"
TAG="${1:-latest}"
DOCKERFILE="Dockerfile.server"
COMPOSE_FILE="docker-compose.server.yml"

echo -e "${GREEN}Building mokuro-server Docker image...${NC}"
echo "Image: ${IMAGE_NAME}:${TAG}"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    exit 1
fi

# Build the image
echo -e "${YELLOW}Step 1: Building Docker image...${NC}"
DOCKER_BUILDKIT=1 docker build \
    --progress=plain \
    -f ${DOCKERFILE} \
    -t ${IMAGE_NAME}:${TAG} \
    .

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Docker image built successfully${NC}"
else
    echo -e "${RED}✗ Docker build failed${NC}"
    exit 1
fi

# Show image info
echo -e "${YELLOW}Step 2: Image information...${NC}"
docker images ${IMAGE_NAME}:${TAG}

# Optional: Test the image
if [ "${2}" == "--test" ]; then
    echo -e "${YELLOW}Step 3: Testing the image...${NC}"
    
    # Run a test container
    docker run --rm -d \
        --name mokuro-test \
        -p 7331:7331 \
        ${IMAGE_NAME}:${TAG}
    
    # Wait for startup
    echo "Waiting for server to start..."
    sleep 10
    
    # Test health endpoint
    if curl -f http://localhost:7331/health; then
        echo -e "\n${GREEN}✓ Health check passed${NC}"
    else
        echo -e "\n${RED}✗ Health check failed${NC}"
    fi
    
    # Stop test container
    docker stop mokuro-test
fi

# Build with docker-compose
if [ "${2}" == "--compose" ]; then
    echo -e "${YELLOW}Step 3: Building with docker-compose...${NC}"
    docker-compose -f ${COMPOSE_FILE} build
fi

echo -e "${GREEN}Build complete!${NC}"
echo ""
echo "To run the container:"
echo "  docker run -p 7331:7331 ${IMAGE_NAME}:${TAG}"
echo ""
echo "Or with docker-compose:"
echo "  docker-compose -f ${COMPOSE_FILE} up"