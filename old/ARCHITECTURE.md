# Enhanced Mokuro API Server - Architecture

## Model Sharing Architecture

### The Problem
When processing multiple OCR requests in parallel, naive implementations would:
1. Load the model separately for each parallel request
2. Consume 3x VRAM for 3 parallel requests
3. Risk OOM errors on GPUs with limited memory (manga-ocr uses ~2-3GB VRAM)

### The Solution: Single Model Instance with Thread-Safe Access

```
┌─────────────────────────────────────────────────┐
│              Request Queue                       │
│  [Request 1] [Request 2] [Request 3] ...        │
└─────────────┬───────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────┐
│         Semaphore (Max 3 parallel)              │
└─────────────┬───────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────┐
│           Thread Pool (3 workers)               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ Worker 1 │ │ Worker 2 │ │ Worker 3 │       │
│  └─────┬────┘ └─────┬────┘ └─────┬────┘       │
│        │            │            │              │
│        └────────────┼────────────┘              │
│                     │                           │
│                     ▼                           │
│         ┌──────────────────────┐               │
│         │   Engine Lock        │               │
│         │  (Threading.Lock)    │               │
│         └──────────┬───────────┘               │
│                    │                            │
│                    ▼                            │
│         ┌──────────────────────┐               │
│         │  Single Model         │               │
│         │  Instance in VRAM     │               │
│         │  (manga-ocr: ~2.5GB)  │               │
│         └──────────────────────┘               │
└─────────────────────────────────────────────────┘
```

### How It Works

1. **Engine Pool**: Maintains a single instance of each unique (engine_type, force_cpu) combination
   ```python
   engines = {
       ("manga_ocr", False): <MangaPageOcr instance>,  # GPU version
       ("manga_ocr", True): <MangaPageOcr instance>,   # CPU version
       ("lens", False): <MangaPageOcr instance>,
   }
   ```

2. **Thread Safety**: Each engine has an associated lock
   - Only one thread can use the model at a time
   - Other threads wait for the lock to be released
   - Prevents concurrent VRAM access issues

3. **Processing Flow**:
   ```python
   # Thread 1: Acquires lock, processes image A
   with engine_lock:
       result = engine(image_A)  # Using VRAM
   
   # Thread 2: Waits for lock...
   # Thread 1 releases lock
   
   # Thread 2: Now acquires lock, processes image B
   with engine_lock:
       result = engine(image_B)  # Same model in VRAM
   ```

### Performance Characteristics

#### V1 (Multiple Model Instances):
- **VRAM Usage**: 3 × 2.5GB = 7.5GB for 3 parallel manga-ocr requests
- **Speed**: True parallel processing (all 3 run simultaneously)
- **Risk**: OOM on 8GB GPUs

#### V2 (Single Shared Instance):
- **VRAM Usage**: 1 × 2.5GB = 2.5GB regardless of parallel requests
- **Speed**: Sequential processing with parallel I/O
  - Image loading/saving: Parallel
  - OCR inference: Sequential (but very fast ~50ms per image)
- **Benefit**: Works on all GPU sizes, no OOM risk

### Effective Parallelism

Despite sequential model access, we still achieve parallelism through:

1. **I/O Operations** (Parallel):
   - Reading image files from disk
   - Writing results to cache
   - Network communication

2. **Preprocessing** (Parallel):
   - Image decoding
   - Text detection (if using separate detector)
   - Image resizing/normalization

3. **Postprocessing** (Parallel):
   - Result formatting
   - JSON serialization
   - Response preparation

Only the actual OCR inference (typically 30-70ms) is sequential.

### Example Timeline (3 requests):

```
Time    Thread 1         Thread 2         Thread 3
0ms     Load image A     Load image B     Load image C
50ms    Preprocess A     Preprocess B     Preprocess C
100ms   OCR A (lock)     Wait...          Wait...
150ms   Postprocess A    OCR B (lock)     Wait...
200ms   Return A         Postprocess B    OCR C (lock)
250ms   ---              Return B         Postprocess C
300ms   ---              ---              Return C
```

Total time: ~300ms for 3 images vs ~150ms if truly parallel
But VRAM usage: 2.5GB vs 7.5GB

### Configuration Options

```python
# Environment variables
MOKURO_MAX_PARALLEL_OCR=3  # Max parallel operations
MOKURO_PRELOAD_MODELS=true # Preload model at startup

# Future enhancement: Batch processing
MOKURO_BATCH_SIZE=4  # Process multiple images in one forward pass
```

### Enhanced Server V2

The enhanced server (enhanced_server_v2.py) provides:
- Efficient model sharing - single instance per engine type
- Thread-safe model access with proper locking
- Memory protection with automatic monitoring
- Request cancellation support
- Rate limiting and caching
- Suitable for both high and low VRAM environments

### Future Optimizations

1. **Batch Processing**: Process multiple images in one forward pass
   ```python
   # Instead of:
   for img in images:
       result = model(img)
   
   # Do:
   results = model(batch_of_images)  # Much faster on GPU
   ```

2. **Model Quantization**: Reduce model size with minimal accuracy loss
   - INT8 quantization: ~4x smaller
   - FP16: ~2x smaller

3. **Dynamic Batching**: Accumulate requests for batch processing
   - Wait up to 50ms to collect requests
   - Process as batch if multiple available

4. **Multi-GPU Support**: Distribute models across GPUs
   - Engine 1 on GPU 0
   - Engine 2 on GPU 1