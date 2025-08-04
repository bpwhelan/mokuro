#!/bin/bash
# Test script to verify GPU functionality in mokuro-server

echo "Testing GPU support in mokuro-server container..."

# Start the GPU-enabled container
echo "Starting GPU-enabled container..."
docker compose -f docker-compose.gpu.yml up -d

# Wait for startup
echo "Waiting for container to start..."
sleep 30

# Test GPU detection
echo "Testing CUDA availability..."
docker exec mokuro-server-gpu python3 -c "
import torch
import sys

print('=== GPU Test Results ===')
print(f'PyTorch version: {torch.__version__}')
print(f'CUDA available: {torch.cuda.is_available()}')
print(f'CUDA version: {torch.version.cuda}')
print(f'Number of GPUs: {torch.cuda.device_count()}')

if torch.cuda.is_available():
    for i in range(torch.cuda.device_count()):
        print(f'GPU {i}: {torch.cuda.get_device_name(i)}')
        print(f'  Memory: {torch.cuda.get_device_properties(i).total_memory / 1024**3:.1f} GB')
    print('✅ GPU support is working!')
    sys.exit(0)
else:
    print('❌ GPU not detected')
    print('Check:')
    print('1. NVIDIA drivers are installed')
    print('2. nvidia-container-toolkit is installed')
    print('3. Docker daemon was restarted after toolkit installation')
    sys.exit(1)
"

# Test health endpoint
echo "Testing API health endpoint..."
curl -s http://localhost:7331/health | jq

echo "GPU test complete!"
echo "To stop the container: docker compose -f docker-compose.gpu.yml down"