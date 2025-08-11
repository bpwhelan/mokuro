"""
Enhanced Mokuro API Server V3 with Priority Queue System - FIXED VERSION:
- Proper async processing without deadlocks
- Request returns immediately with request_id
- Polling or callback for results
"""
import asyncio
import hashlib
import json
import os
import psutil
import tempfile
import time
import uuid
import threading
import heapq
from concurrent.futures import ThreadPoolExecutor, Future
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Annotated
from datetime import datetime, timedelta
import numpy as np
from dataclasses import dataclass, field
from enum import IntEnum

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi import File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from cachetools import TTLCache
import json

from mokuro import __version__ as mokuro_version
from mokuro.manga_page_ocr import MangaPageOcr, InvalidImage
from mokuro.api_server.registry import (
    api_to_provider,
    build_engine_registry,
    detect_supported_formats,
    provider_lang_code,
)
from mokuro.utils import NumpyEncoder
from loguru import logger
import sys

# API Server Version
__version__ = "0.3.6"  # Fixed numpy.bool serialization error in /api/result endpoint

# Configure enhanced logging with priority display
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{extra[request_id]: <12}</cyan> | <yellow>P{extra[priority]:1}</yellow> | <level>{message}</level>",
    level="INFO",
    colorize=True,
    backtrace=True,
    diagnose=True,
    filter=lambda record: "request_id" in record["extra"] and "priority" in record["extra"]
)
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{extra[request_id]: <12}</cyan> | <blue>--</blue> | <level>{message}</level>",
    level="INFO",
    colorize=True,
    backtrace=True,
    diagnose=True,
    filter=lambda record: "request_id" in record["extra"] and "priority" not in record["extra"]
)
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <blue>SYSTEM</blue>       | <blue>--</blue> | <level>{message}</level>",
    level="INFO",
    colorize=True,
    backtrace=True,
    diagnose=True,
    filter=lambda record: "request_id" not in record["extra"]
)


class Priority(IntEnum):
    """Request priority levels"""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BACKGROUND = 4
    
    @classmethod
    def from_int(cls, value: int) -> 'Priority':
        try:
            return Priority(min(max(0, value), 4))
        except ValueError:
            return Priority.NORMAL
    
    def __str__(self):
        names = ["CRITICAL", "HIGH", "NORMAL", "LOW", "BACKGROUND"]
        return names[self.value]


def make_json_safe(obj):
    """Convert numpy types and other non-JSON-serializable objects to JSON-safe types"""
    if isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, (np.integer, np.int64, np.int32, np.int16, np.int8)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: make_json_safe(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [make_json_safe(item) for item in obj]
    else:
        return obj


@dataclass(order=True)
class PriorityRequest:
    """Request with priority for queue management"""
    priority: int = field(compare=True)
    timestamp: float = field(compare=True)
    request_id: str = field(compare=False)
    image_path: str = field(compare=False)
    engine_name: str = field(compare=False)
    force_cpu: bool = field(compare=False)
    filename: str = field(compare=False)
    
    def __post_init__(self):
        self.priority = Priority.from_int(self.priority).value


# Configuration
MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100MB for all images
MAX_PARALLEL_CRITICAL = 4
MAX_PARALLEL_OTHER = 2
REQUEST_QUEUE_SIZE = 50
OCR_TIMEOUT = 30
CACHE_TTL = 300
HEALTH_CACHE_TTL = 5
MAX_FILENAME_LENGTH = 255  # Reasonable filesystem limit
MAX_CRITICAL_IMAGE_SIZE = 100 * 1024 * 1024  # 100MB for critical requests (same as others)

PRIORITY_TIMEOUTS = {
    Priority.CRITICAL: 30,
    Priority.HIGH: 25,
    Priority.NORMAL: 20,
    Priority.LOW: 15,
    Priority.BACKGROUND: 10,
}


class ServerConfig:
    def __init__(self):
        self.max_upload_bytes = int(os.getenv("MOKURO_MAX_UPLOAD_BYTES", MAX_UPLOAD_BYTES))
        self.max_parallel_critical = int(os.getenv("MOKURO_MAX_PARALLEL_CRITICAL", MAX_PARALLEL_CRITICAL))
        self.max_parallel_other = int(os.getenv("MOKURO_MAX_PARALLEL_OTHER", MAX_PARALLEL_OTHER))
        self.request_queue_size = int(os.getenv("MOKURO_REQUEST_QUEUE_SIZE", REQUEST_QUEUE_SIZE))
        self.ocr_timeout = int(os.getenv("MOKURO_OCR_TIMEOUT", OCR_TIMEOUT))
        self.cache_ttl = int(os.getenv("MOKURO_CACHE_TTL", CACHE_TTL))


config = ServerConfig()


class OCREnginePool:
    """Manages OCR engine instances with thread safety"""
    def __init__(self):
        self.engines: Dict[Tuple[str, bool], MangaPageOcr] = {}
        self.engine_locks: Dict[Tuple[str, bool], threading.Lock] = {}
        self.pool_lock = threading.Lock()
        self.usage_count: Dict[Tuple[str, bool], int] = {}
        
    def get_engine(self, engine_name: str, force_cpu: bool) -> Tuple[MangaPageOcr, threading.Lock]:
        key = (engine_name, bool(force_cpu))
        
        with self.pool_lock:
            if key not in self.engines:
                logger.info(f"🔧 Creating new engine instance: {engine_name}, CPU={force_cpu}")
                if engine_name and engine_name.startswith("owocr:"):
                    engine = MangaPageOcr(
                        force_cpu=force_cpu,
                        disable_ocr=False,
                        ocr_engine=engine_name
                    )
                else:
                    engine = MangaPageOcr(
                        force_cpu=force_cpu,
                        disable_ocr=False,
                        ocr_engine="manga_ocr"
                    )
                self.engines[key] = engine
                self.engine_locks[key] = threading.Lock()
                self.usage_count[key] = 0
            
            self.usage_count[key] += 1
            return self.engines[key], self.engine_locks[key]
    
    def get_stats(self) -> Dict:
        with self.pool_lock:
            return {
                "total_engines": len(self.engines),
                "engines": [
                    {
                        "engine": key[0],
                        "force_cpu": key[1],
                        "usage_count": self.usage_count.get(key, 0)
                    }
                    for key in self.engines.keys()
                ]
            }
    
    def cleanup(self):
        with self.pool_lock:
            self.engines.clear()
            self.engine_locks.clear()
            self.usage_count.clear()


class PriorityRequestManager:
    """Manages requests with true async processing"""
    def __init__(self):
        # Priority queue
        self.priority_queue: List[PriorityRequest] = []
        self.queue_lock = asyncio.Lock()
        
        # Request tracking
        self.active_requests: Dict[str, PriorityRequest] = {}
        self.active_critical_count = 0
        self.active_other_count = 0
        
        # Results storage
        self.completed_results: Dict[str, Any] = {}
        self.failed_requests: Dict[str, str] = {}
        self.result_timestamps: Dict[str, float] = {}
        
        # Thread pool
        self.executor = ThreadPoolExecutor(
            max_workers=config.max_parallel_critical + config.max_parallel_other,
            thread_name_prefix="ocr-worker"
        )
        
        # Resources
        self.result_cache = TTLCache(maxsize=100, ttl=config.cache_ttl)
        self.engine_pool = OCREnginePool()
        
        # Stats
        self.stats = {
            "total_queued": 0,
            "total_processed": 0,
            "total_cancelled": 0,
            "by_priority": {i: 0 for i in range(5)}
        }
        
        # Processing task
        self.processor_task = None
        self.shutdown = False
    
    async def start_processor(self):
        """Start the background processor"""
        self.processor_task = asyncio.create_task(self._process_queue())
        logger.info("🚀 Priority queue processor started")
    
    async def stop_processor(self):
        """Stop the background processor"""
        self.shutdown = True
        if self.processor_task:
            await self.processor_task
        logger.info("🛑 Priority queue processor stopped")
    
    async def _process_queue(self):
        """Process queued requests"""
        while not self.shutdown:
            async with self.queue_lock:
                if not self.priority_queue:
                    # Nothing to process
                    pass
                else:
                    # Check what we can process
                    critical_active = self.active_critical_count
                    other_active = self.active_other_count
                    
                    # Sort queue
                    heapq.heapify(self.priority_queue)
                    
                    next_request = None
                    if self.priority_queue:
                        candidate = self.priority_queue[0]
                        priority = Priority(candidate.priority)
                        
                        can_process = False
                        if priority == Priority.CRITICAL and critical_active < config.max_parallel_critical:
                            can_process = True
                            self.active_critical_count += 1
                        elif critical_active == 0 and other_active < config.max_parallel_other:
                            # No criticals active, can process others
                            if priority != Priority.CRITICAL:
                                can_process = True
                                self.active_other_count += 1
                        
                        if can_process:
                            next_request = heapq.heappop(self.priority_queue)
                            self.active_requests[next_request.request_id] = next_request
                            # Start processing in background
                            asyncio.create_task(self._execute_request(next_request))
                            logger.bind(request_id=next_request.request_id, priority=next_request.priority).info(
                                f"🎯 Started processing {Priority(next_request.priority)} request"
                            )
            
            # Small delay before next check
            await asyncio.sleep(0.05)
    
    async def _execute_request(self, request: PriorityRequest):
        """Execute OCR request"""
        request_id = request.request_id
        priority = Priority(request.priority)
        
        try:
            # Get engine
            engine, engine_lock = self.engine_pool.get_engine(request.engine_name, request.force_cpu)
            
            # Run OCR in thread pool
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor,
                self._process_with_engine,
                engine,
                engine_lock,
                request.image_path
            )
            
            # Store result
            self.completed_results[request_id] = result
            self.result_timestamps[request_id] = time.time()
            
            logger.bind(request_id=request_id, priority=request.priority).success(
                f"✅ {priority} request completed"
            )
            
            self.stats["total_processed"] += 1
            self.stats["by_priority"][request.priority] += 1
            
        except Exception as e:
            self.failed_requests[request_id] = str(e)
            self.result_timestamps[request_id] = time.time()
            
            logger.bind(request_id=request_id, priority=request.priority).error(
                f"❌ {priority} request failed: {str(e)}"
            )
        finally:
            # Clean up
            self.active_requests.pop(request_id, None)
            async with self.queue_lock:
                if priority == Priority.CRITICAL:
                    self.active_critical_count -= 1
                else:
                    self.active_other_count -= 1
            
            # Clean old results
            self._cleanup_old_results()
            
            # Clean up temp file
            try:
                os.unlink(request.image_path)
            except:
                pass
    
    def _process_with_engine(self, engine: MangaPageOcr, engine_lock: threading.Lock, image_path: str) -> dict:
        """Process image with engine"""
        with engine_lock:
            result = engine(image_path)
        return result
    
    def _cleanup_old_results(self):
        """Clean up old results"""
        current_time = time.time()
        expired = [
            rid for rid, ts in self.result_timestamps.items()
            if current_time - ts > 60
        ]
        for rid in expired:
            self.completed_results.pop(rid, None)
            self.failed_requests.pop(rid, None)
            self.result_timestamps.pop(rid, None)
    
    async def queue_request(
        self,
        request_id: str,
        image_path: str,
        engine_name: str,
        force_cpu: bool,
        filename: str,
        priority: int = 2
    ) -> Dict:
        """Queue a request with priority-based eviction for critical requests"""
        async with self.queue_lock:
            # If queue is full, check if we can evict lower priority
            if len(self.priority_queue) >= config.request_queue_size:
                # If this is a critical request, evict lowest priority
                if priority == Priority.CRITICAL:
                    # Find the lowest priority request to evict
                    if self.priority_queue:
                        # Sort to find lowest priority (highest number)
                        self.priority_queue.sort(reverse=True)
                        lowest = self.priority_queue[0]
                        
                        # Only evict if it's lower priority than critical
                        if lowest.priority > Priority.CRITICAL:
                            evicted = self.priority_queue.pop(0)
                            # Clean up evicted request
                            try:
                                os.unlink(evicted.image_path)
                            except:
                                pass
                            # Store as failed
                            self.failed_requests[evicted.request_id] = "Evicted by higher priority request"
                            self.result_timestamps[evicted.request_id] = time.time()
                            
                            logger.warning(
                                f"🚫 Evicted {Priority(evicted.priority)} request {evicted.request_id} "
                                f"to make room for CRITICAL request"
                            )
                        else:
                            # All requests are critical, can't evict
                            raise HTTPException(503, "Queue full with critical requests")
                else:
                    # Non-critical request and queue is full
                    # Check if we should evict even lower priority
                    can_evict = False
                    for i, req in enumerate(sorted(self.priority_queue, reverse=True)):
                        if req.priority > priority:  # Found lower priority
                            evicted = self.priority_queue.pop(self.priority_queue.index(req))
                            # Clean up evicted request
                            try:
                                os.unlink(evicted.image_path)
                            except:
                                pass
                            self.failed_requests[evicted.request_id] = "Evicted by higher priority request"
                            self.result_timestamps[evicted.request_id] = time.time()
                            
                            logger.warning(
                                f"🚫 Evicted {Priority(evicted.priority)} request {evicted.request_id} "
                                f"to make room for {Priority(priority)} request"
                            )
                            can_evict = True
                            break
                    
                    if not can_evict:
                        raise HTTPException(503, "Queue full with equal or higher priority requests")
            
            # Create request
            req = PriorityRequest(
                priority=priority,
                timestamp=time.time(),
                request_id=request_id,
                image_path=image_path,
                engine_name=engine_name,
                force_cpu=force_cpu,
                filename=filename
            )
            
            heapq.heappush(self.priority_queue, req)
            self.stats["total_queued"] += 1
            
            # Calculate position
            position = sum(1 for r in self.priority_queue if r.priority <= priority)
            
            logger.bind(request_id=request_id, priority=priority).info(
                f"📥 Queued {Priority(priority)} request | Position: {position}"
            )
            
            return {
                "request_id": request_id,
                "priority": priority,
                "queue_position": position,
                "estimated_wait_ms": position * 500
            }
    
    async def get_result(self, request_id: str) -> Optional[Dict]:
        """Get result if ready"""
        if request_id in self.completed_results:
            result = self.completed_results.pop(request_id)
            self.result_timestamps.pop(request_id, None)
            # Make sure result is JSON-serializable
            safe_result = make_json_safe(result)
            return {"status": "completed", "result": safe_result}
        elif request_id in self.failed_requests:
            error = self.failed_requests.pop(request_id)
            self.result_timestamps.pop(request_id, None)
            return {"status": "failed", "error": error}
        elif request_id in self.active_requests:
            return {"status": "processing"}
        else:
            # Check queue
            async with self.queue_lock:
                for req in self.priority_queue:
                    if req.request_id == request_id:
                        return {"status": "queued"}
            return None
    
    def get_stats(self) -> Dict:
        return {
            "queue_length": len(self.priority_queue),
            "active_critical": self.active_critical_count,
            "active_other": self.active_other_count,
            "stats": self.stats,
            "engine_pool": self.engine_pool.get_stats()
        }
    
    def cleanup(self):
        """Cleanup resources"""
        self.executor.shutdown(wait=True)
        self.engine_pool.cleanup()


# Global instances
request_manager = PriorityRequestManager()
engine_descs, engine_avail = build_engine_registry()
formats = detect_supported_formats()


def api_to_engine_name(api_name: str) -> str:
    provider = api_to_provider(api_name, engine_descs)
    return provider or "manga_ocr"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage lifecycle"""
    logger.info("=" * 60)
    logger.info(f"🚀 Mokuro API Server V3 FIXED - Version {__version__}")
    logger.info("=" * 60)
    
    await request_manager.start_processor()
    
    # Preload models
    if os.getenv("MOKURO_PRELOAD_MODELS", "true").lower() == "true":
        logger.info("🔧 Preloading models...")
        engine, lock = request_manager.engine_pool.get_engine("manga_ocr", False)
        logger.success("✅ Models loaded")
    
    yield
    
    logger.warning("🛑 Shutting down...")
    await request_manager.stop_processor()
    request_manager.cleanup()


def create_app() -> FastAPI:
    """Create FastAPI app"""
    app = FastAPI(
        title="Mokuro API Server V3 FIXED",
        version=__version__,
        lifespan=lifespan
    )
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    
    @app.get("/health")
    async def health():
        return {
            "status": "healthy",
            "version": __version__,
            "stats": request_manager.get_stats()
        }
    
    @app.post("/api/ocr")
    async def process_image(
        request: Request,
        image: Annotated[UploadFile, File(...)],
        ocr_engine: Annotated[str, Form()] = "manga-ocr",
        force_cpu: Annotated[str, Form()] = "false",
        priority: Annotated[str, Form()] = "2",
    ):
        """Submit image for OCR - returns immediately with request_id"""
        request_id = str(uuid.uuid4())[:8]
        
        # Validate and parse priority
        try:
            if priority == "" or priority is None:
                priority_int = 2  # Default
            else:
                priority_float = float(priority)  # Parse as float first
                # Check for inf/nan
                if not (priority_float == priority_float and abs(priority_float) != float('inf')):
                    raise ValueError("Invalid priority value")
                priority_int = int(priority_float)  # Convert to int
                # Clamp to valid range
                priority_int = max(0, min(4, priority_int))
        except (ValueError, TypeError, OverflowError):
            raise HTTPException(400, f"Invalid priority value: {priority}. Must be 0-4")
        
        # Validate engine
        if ocr_engine not in [n for n, ok in engine_avail.items() if ok]:
            raise HTTPException(400, f"Invalid engine: {ocr_engine}")
        
        # Sanitize and validate filename
        if image.filename:
            # Remove path traversal attempts
            safe_filename = os.path.basename(image.filename)
            # Limit length
            if len(safe_filename) > MAX_FILENAME_LENGTH:
                name, ext = os.path.splitext(safe_filename)
                safe_filename = name[:MAX_FILENAME_LENGTH-len(ext)-10] + "_truncated" + ext
        else:
            safe_filename = "unnamed.jpg"
        
        # Read and validate image data
        image_data = await image.read()
        
        # Size limits based on priority
        if priority_int == 0 and len(image_data) > MAX_CRITICAL_IMAGE_SIZE:
            raise HTTPException(413, f"Critical request image too large: {len(image_data)/1024/1024:.1f}MB (max {MAX_CRITICAL_IMAGE_SIZE/1024/1024}MB)")
        elif len(image_data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"Image too large: {len(image_data)/1024/1024:.1f}MB (max {MAX_UPLOAD_BYTES/1024/1024}MB)")
        
        # Reject if too much extra data in request
        # Check for large unknown fields
        form_data = await request.form()
        for key, value in form_data.items():
            if key not in ['image', 'ocr_engine', 'force_cpu', 'priority']:
                if isinstance(value, str) and len(value) > 1024:
                    raise HTTPException(400, f"Unknown field '{key}' contains too much data")
        
        # Save image with safe filename
        suffix = Path(safe_filename).suffix or '.jpg'
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(image_data)
            tmp_path = tmp.name
        
        # Queue request
        queue_info = await request_manager.queue_request(
            request_id,
            tmp_path,
            api_to_engine_name(ocr_engine),
            force_cpu.lower() == "true",
            safe_filename,
            priority_int
        )
        
        return JSONResponse({
            "status": "queued",
            **queue_info
        })
    
    @app.get("/api/result/{request_id}")
    async def get_result(request_id: str):
        """Poll for result"""
        result = await request_manager.get_result(request_id)
        if result:
            return result
        else:
            raise HTTPException(404, "Request not found")
    
    @app.get("/api/queue/status")
    async def queue_status():
        return request_manager.get_stats()
    
    @app.get("/api/info")
    async def api_info():
        """Return OCR engine information for Kavita LiveOCR integration"""
        # Build detailed engine information in the format Kavita expects
        ocr_engines_detailed = {}
        
        for engine_name, is_available in engine_avail.items():
            if is_available:
                # Get engine info from registry
                engine_desc = engine_descs.get(engine_name)
                
                if engine_desc:
                    description = f"{engine_desc.display_name} OCR engine"
                    display_name = engine_desc.display_name
                    suggested_language_code = engine_desc.suggested_language_code
                else:
                    # Fallback for unknown engines
                    description = f"{engine_name} OCR engine"
                    display_name = engine_name.replace("-", " ").title()
                    suggested_language_code = "mo"  # Default
                
                version = "1.0.0"
                capabilities = ["text_detection", "text_recognition"]
                
                # Add specific capabilities based on engine
                if "manga" in engine_name.lower():
                    capabilities.append("manga_optimized")
                elif "lens" in engine_name.lower():
                    capabilities.extend(["multilingual", "web_based"])
                elif "easyocr" in engine_name.lower() or "rapidocr" in engine_name.lower():
                    capabilities.extend(["multilingual", "offline"])
                elif "gvision" in engine_name.lower() or "azure" in engine_name.lower():
                    capabilities.extend(["cloud_based", "high_accuracy"])
                
                ocr_engines_detailed[engine_name] = {
                    "description": description,
                    "display_name": display_name,
                    "available": True,
                    "version": version,
                    "capabilities": capabilities,
                    "suggested_language_code": suggested_language_code
                }
        
        return {
            "ocr_engines_detailed": ocr_engines_detailed
        }
    
    return app


app = create_app()

def main():
    """Main entry point for the server"""
    import uvicorn
    host = os.getenv("MOKURO_API_HOST", "0.0.0.0")
    port = int(os.getenv("MOKURO_API_PORT", "7331"))
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    main()