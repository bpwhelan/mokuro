# syntax=docker/dockerfile:1
# Default image: Ubuntu 24.04 base; CUDA-enabled frameworks installed via wheels
FROM nvidia/cuda:12.8.0-runtime-ubuntu24.04 AS runtime

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TRANSFORMERS_NO_ADVISORY_WARNINGS=1

# Base system, Python, toolchain
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl wget git unzip \
    python3 python3-pip python3-venv python3-dev \
    build-essential pkg-config cmake ninja-build \
    && rm -rf /var/lib/apt/lists/*

## Host provides the driver via --gpus all
## PyTorch (cu121 wheels) and onnxruntime-gpu provide/bundle needed CUDA libs.

# Runtime libs for OpenCV/Pillow and image codecs (Ubuntu 24.04 names)
RUN apt-get update && apt-get install -y --no-install-recommends \
      libgl1 \
      libglib2.0-0 \
      libsm6 \
      libxext6 \
      libxrender1 \
      libx11-6 \
      libjpeg-turbo8 \
      libpng16-16 \
      libtiff6 \
      libwebp7 \
      libheif1 \
      libjxl0.7 libjxl-tools libjxl-dev \
      libgomp1 \
      ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy project files
COPY pyproject.toml README.md LICENSE /app/
COPY mokuro /app/mokuro
COPY comic_text_detector /app/comic_text_detector

# Create and use a virtualenv to avoid PEP 668 restrictions
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv "$VIRTUAL_ENV"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Install CUDA-enabled PyTorch, then project extras
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cu126 \
        torch torchvision torchaudio && \
    pip install --no-cache-dir \
        ".[api,owocr]" && \
    # Prefer GPU ONNX Runtime for RapidOCR; replace CPU build if present
    pip uninstall -y onnxruntime || true && \
    pip install --no-cache-dir onnxruntime-gpu

# Non-root user
RUN useradd -m -u 10001 appuser
USER appuser

EXPOSE 7331

ENV MOKURO_API_HOST=0.0.0.0 \
    MOKURO_API_PORT=7331

ENTRYPOINT ["mokuro-api"]
