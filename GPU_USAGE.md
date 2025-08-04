# GPU Support for Mokuro Server

The mokuro-server Docker container includes complete CUDA 12.6 support with all necessary libraries for GPU acceleration.

## What's Included ✅

- **PyTorch 2.7.1** with CUDA 12.6 support
- **cuDNN 9.5.1** for deep learning acceleration
- **Complete NVIDIA CUDA libraries**: cuBLAS, cuFFT, cuRAND, cuSOLVER, NCCL, etc.
- **Automatic GPU detection** and usage when available

## Prerequisites

### 1. NVIDIA Drivers
Install the latest NVIDIA drivers for your GPU:
```bash
# Check current driver
nvidia-smi

# If not installed, install via package manager or from NVIDIA website
```

### 2. NVIDIA Container Toolkit
```bash
# Ubuntu/Debian
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

## Usage

### Method 1: Docker Compose (Recommended)
```bash
# Use the GPU-enabled compose file
docker compose -f docker-compose.gpu.yml up -d

# Test GPU functionality
./test-gpu.sh
```

### Method 2: Docker Run
```bash
docker run -d \
  --name mokuro-server-gpu \
  --gpus all \
  -p 7331:7331 \
  -e CUDA_VISIBLE_DEVICES=0 \
  -v mokuro-models:/root/.cache \
  ghcr.io/xrishox/mokuro-server:latest
```

### Method 3: Docker Compose with Runtime
```yaml
version: '3.8'
services:
  mokuro-server:
    image: ghcr.io/xrishox/mokuro-server:latest
    runtime: nvidia
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
      - NVIDIA_DRIVER_CAPABILITIES=compute,utility
      - CUDA_VISIBLE_DEVICES=0
```

## Performance Benefits

With GPU acceleration, you can expect:

- **manga-ocr**: ~3-5x faster inference
- **Text detection**: ~2-3x faster processing
- **Batch processing**: Significant speedup for multiple images
- **Lower CPU usage**: Offloads computation to GPU

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CUDA_VISIBLE_DEVICES` | `0` | Which GPU(s) to use (0, 1, or 0,1) |
| `TORCH_CUDA_ARCH_LIST` | Auto | CUDA architectures to optimize for |
| `NVIDIA_VISIBLE_DEVICES` | `all` | NVIDIA runtime GPU visibility |

## GPU Memory Requirements

- **Minimum**: 4GB VRAM
- **Recommended**: 8GB+ VRAM
- **Optimal**: 12GB+ VRAM for large batches

The container will automatically fall back to CPU if:
- No GPU is detected
- Insufficient VRAM
- CUDA libraries are incompatible

## Troubleshooting

### GPU Not Detected
```bash
# Check NVIDIA driver
nvidia-smi

# Check Docker GPU support
docker run --rm --gpus all nvidia/cuda:12.6-base-ubuntu22.04 nvidia-smi

# Test mokuro container GPU
docker run --rm --gpus all ghcr.io/xrishox/mokuro-server:latest \
  python3 -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"
```

### Common Issues

1. **"no matching manifest"**: Update Docker to support GPU syntax
2. **"could not select device driver"**: Restart Docker after installing nvidia-container-toolkit
3. **"CUDA out of memory"**: Reduce batch size or use a GPU with more VRAM
4. **"driver version mismatch"**: Update NVIDIA drivers

### Monitoring GPU Usage
```bash
# Watch GPU usage while processing images
watch -n 1 nvidia-smi

# Check mokuro container GPU usage
docker exec mokuro-server-gpu nvidia-smi
```

## Testing GPU Performance

Use the included test script:
```bash
./test-gpu.sh
```

Or test manually:
```bash
# Send an image for processing and time it
time curl -X POST -F "image=@test.jpg" http://localhost:7331/api/ocr
```

## Supported GPU Architectures

The container supports NVIDIA GPUs with compute capability 7.0+:
- **RTX 20/30/40 series** (Turing, Ampere, Ada)
- **GTX 16 series** (Turing)
- **Tesla V100, A100** (Volta, Ampere)
- **RTX A4000/5000/6000** (Ampere)

Older GPUs (GTX 10 series and earlier) may work but are not optimized.