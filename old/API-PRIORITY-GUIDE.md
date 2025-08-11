# Mokuro Priority API Integration Guide

## Version 0.2.0 - Priority Queue System

This guide documents the new priority-based request processing system in Mokuro API Server V3.

## Overview

The Mokuro Priority Server implements a **strict priority queue system** where higher priority requests are always processed before lower priority ones. This ensures that user-facing requests (like the current page being viewed) are never blocked by background prefetch operations.

## Key Features

- **5 Priority Levels** (0=Critical to 4=Background)
- **4 Parallel Critical Slots** - Up to 4 critical requests can run simultaneously
- **Strict Priority Enforcement** - Critical requests block ALL non-critical processing
- **Engine Locking** - Only one request per OCR engine type at a time
- **Queue Position Tracking** - Know exactly where your request stands
- **Wait Time Estimation** - Get estimated processing time
- **Request Cancellation** - Cancel queued or active requests

## Priority Levels

| Priority | Name       | Use Case                                    | Parallel Slots |
|----------|------------|---------------------------------------------|----------------|
| 0        | CRITICAL   | Current page user is viewing               | 4              |
| 1        | HIGH       | Next/previous pages (±1)                   | 2              |
| 2        | NORMAL     | Nearby prefetch (±2-3 pages)               | 2              |
| 3        | LOW        | Distant prefetch (±4-10 pages)             | 2              |
| 4        | BACKGROUND | Batch processing or very distant pages     | 2              |

## Processing Rules

1. **Critical Priority (0)**
   - Gets up to 4 dedicated parallel processing slots
   - Blocks ALL other priority levels while active
   - Immediate processing when slots available
   - Cannot be preempted

2. **High Priority (1)**
   - Only processes when NO critical requests are active or queued
   - Shares 2 parallel slots with lower priorities
   - Blocks Normal, Low, and Background

3. **Normal/Low/Background (2-4)**
   - Only process when no higher priority requests exist
   - Must wait for all higher priorities to complete
   - Share the same 2 parallel processing slots

## API Changes

### Request Parameters

The `/api/ocr` endpoint now accepts an additional parameter:

```python
# POST /api/ocr
{
    "image": file,           # Required: Image file
    "ocr_engine": "manga-ocr", # Optional: OCR engine (default: manga-ocr)
    "force_cpu": "false",    # Optional: Force CPU processing
    "priority": "2"          # NEW: Priority level 0-4 (default: 2)
}
```

### Response Format

The response now includes queue metadata:

```json
{
    // Original OCR results
    "blocks": [...],
    "filename": "page_001.jpg",
    "ocr_engine": "manga-ocr",
    
    // NEW: Priority queue metadata
    "request_id": "a1b2c3d4",        // Unique request identifier
    "priority": 0,                    // Priority level used
    "queue_info": {
        "request_id": "a1b2c3d4",
        "priority_accepted": 0,       // Server accepted priority
        "priority_name": "CRITICAL",  // Human-readable priority
        "queue_position": 1,          // Position in queue (1 = next)
        "estimated_wait_ms": 200,     // Estimated wait time
        "queue_length": 5,            // Total requests in queue
        "active_critical": 2,         // Active critical requests
        "active_other": 0             // Active non-critical requests
    }
}
```

## Client Implementation Example

### Python Client

```python
import requests
import asyncio
from enum import IntEnum

class Priority(IntEnum):
    CRITICAL = 0    # Current page
    HIGH = 1        # Adjacent pages
    NORMAL = 2      # Nearby prefetch
    LOW = 3         # Distant prefetch
    BACKGROUND = 4  # Batch processing

class MokuroClient:
    def __init__(self, base_url="http://localhost:7331"):
        self.base_url = base_url
        self.active_requests = {}
    
    async def process_image(self, image_path, priority=Priority.NORMAL):
        """Submit an image for OCR with priority"""
        with open(image_path, 'rb') as f:
            files = {'image': f}
            data = {
                'ocr_engine': 'manga-ocr',
                'priority': str(priority.value)
            }
            
            response = requests.post(
                f"{self.base_url}/api/ocr",
                files=files,
                data=data
            )
            
            if response.status_code == 200:
                result = response.json()
                request_id = result.get('request_id')
                queue_info = result.get('queue_info', {})
                
                print(f"Request {request_id} queued:")
                print(f"  Priority: {queue_info.get('priority_name')}")
                print(f"  Position: {queue_info.get('queue_position')}")
                print(f"  Est. Wait: {queue_info.get('estimated_wait_ms')}ms")
                
                return result
            else:
                print(f"Error: {response.status_code}")
                return None
    
    def cancel_request(self, request_id):
        """Cancel a queued or active request"""
        response = requests.delete(
            f"{self.base_url}/api/ocr/cancel/{request_id}"
        )
        return response.status_code == 200

# Usage example
client = MokuroClient()

# User clicks on page 5 - CRITICAL priority
await client.process_image("page_005.jpg", Priority.CRITICAL)

# Prefetch adjacent pages - HIGH priority
await client.process_image("page_004.jpg", Priority.HIGH)
await client.process_image("page_006.jpg", Priority.HIGH)

# Background prefetch - LOW priority
for i in range(7, 15):
    await client.process_image(f"page_{i:03d}.jpg", Priority.LOW)
```

### JavaScript/TypeScript Client

```typescript
enum Priority {
    CRITICAL = 0,
    HIGH = 1,
    NORMAL = 2,
    LOW = 3,
    BACKGROUND = 4
}

class MokuroClient {
    private baseUrl: string;
    private activeRequests: Map<string, AbortController>;
    
    constructor(baseUrl = "http://localhost:7331") {
        this.baseUrl = baseUrl;
        this.activeRequests = new Map();
    }
    
    async processImage(
        imageFile: File,
        priority: Priority = Priority.NORMAL
    ): Promise<any> {
        const formData = new FormData();
        formData.append('image', imageFile);
        formData.append('ocr_engine', 'manga-ocr');
        formData.append('priority', priority.toString());
        
        const response = await fetch(`${this.baseUrl}/api/ocr`, {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            const result = await response.json();
            const queueInfo = result.queue_info || {};
            
            console.log(`Request ${result.request_id} queued:`);
            console.log(`  Priority: ${queueInfo.priority_name}`);
            console.log(`  Position: ${queueInfo.queue_position}`);
            console.log(`  Est. Wait: ${queueInfo.estimated_wait_ms}ms`);
            
            return result;
        }
        
        throw new Error(`HTTP ${response.status}`);
    }
    
    async cancelRequest(requestId: string): Promise<boolean> {
        const response = await fetch(
            `${this.baseUrl}/api/ocr/cancel/${requestId}`,
            { method: 'DELETE' }
        );
        return response.ok;
    }
}
```

## Queue Management Strategies

### 1. Page Navigation

When user navigates to a new page:
1. Cancel all existing LOW and BACKGROUND requests
2. Submit current page as CRITICAL
3. Submit adjacent pages as HIGH
4. Queue nearby pages as NORMAL
5. Queue distant pages as LOW

### 2. Rapid Page Flipping

When user is quickly flipping through pages:
1. Cancel previous CRITICAL if still queued
2. Keep only the latest CRITICAL request
3. Defer HIGH/NORMAL prefetching until stable

### 3. Batch Processing

For background batch operations:
1. Use BACKGROUND priority
2. Implement client-side rate limiting
3. Monitor queue depth before submitting more

## Server Monitoring

### Queue Status Endpoint

```bash
GET /api/queue/status
```

Returns detailed queue statistics:

```json
{
    "queue": {
        "total": 10,
        "by_priority": {
            "CRITICAL": 1,
            "HIGH": 2,
            "NORMAL": 3,
            "LOW": 4
        },
        "max_size": 50
    },
    "active": {
        "critical": 2,
        "other": 0,
        "total": 2
    },
    "processing": {
        "total_queued": 150,
        "total_processed": 140,
        "total_cancelled": 5,
        "by_priority": {
            "CRITICAL": 50,
            "HIGH": 40,
            "NORMAL": 30,
            "LOW": 20,
            "BACKGROUND": 0
        }
    }
}
```

## CLI Output for Debugging

The server logs comprehensive information about queue operations:

```
2024-01-20 10:15:23.456 | INFO     | a1b2c3d4     | P0 | 📨 NEW CRITICAL REQUEST from 172.18.0.8 | File: page_005.jpg | Engine: manga-ocr
2024-01-20 10:15:23.457 | INFO     | a1b2c3d4     | P0 | 📥 CRITICAL request queued | Position: 1 | Est. wait: 200ms | File: page_005.jpg
2024-01-20 10:15:23.458 | INFO     | SYSTEM       | -- | 📊 Queue State | Active: 0 critical, 0 other | Queued: {'CRITICAL': 1}
2024-01-20 10:15:23.460 | INFO     | a1b2c3d4     | P0 | 🎯 Processing CRITICAL request | File: page_005.jpg
2024-01-20 10:15:23.650 | SUCCESS  | a1b2c3d4     | P0 | ✅ CRITICAL request completed
2024-01-20 10:15:23.651 | INFO     | b2c3d4e5     | P1 | 📨 NEW HIGH REQUEST from 172.18.0.8 | File: page_004.jpg | Engine: manga-ocr
2024-01-20 10:15:23.652 | INFO     | b2c3d4e5     | P1 | 📥 HIGH request queued | Position: 1 | Est. wait: 500ms | File: page_004.jpg
2024-01-20 10:15:23.653 | INFO     | SYSTEM       | -- | 📊 Queue State | Active: 0 critical, 0 other | Queued: {'HIGH': 1}
```

## Environment Variables

Configure the server behavior with these environment variables:

```bash
# Maximum parallel CRITICAL requests (default: 4)
MOKURO_MAX_PARALLEL_CRITICAL=4

# Maximum parallel non-critical requests (default: 2)
MOKURO_MAX_PARALLEL_OTHER=2

# Queue size limit (default: 50)
MOKURO_REQUEST_QUEUE_SIZE=50

# Enable priority preemption (default: true)
MOKURO_PRIORITY_PREEMPTION=true

# Server port (default: 7331)
MOKURO_API_PORT=7331
```

## Migration from V2 to V3

### Minimal Changes (Backward Compatible)

The server is backward compatible. If you don't send the `priority` parameter, requests default to NORMAL (2) priority.

### Recommended Changes

1. **Add priority parameter** to all OCR requests
2. **Track request_id** from responses for cancellation
3. **Implement cancellation** for low-priority requests when user navigates
4. **Monitor queue_info** to adjust client-side throttling
5. **Use appropriate priorities** based on user interaction

## Performance Considerations

1. **Critical Requests**: Keep these minimal - only for user-visible content
2. **Prefetch Strategy**: Balance between responsiveness and server load
3. **Cancellation**: Aggressively cancel outdated requests
4. **Queue Monitoring**: Adjust client behavior based on queue depth
5. **Caching**: The server caches results for 5 minutes by default

## Troubleshooting

### High Wait Times

If seeing high wait times for critical requests:
- Check if too many requests are marked as critical
- Verify other clients aren't flooding with high priority
- Monitor `/api/queue/status` for queue distribution

### Requests Timing Out

- Critical: 30s timeout
- High: 25s timeout  
- Normal: 20s timeout
- Low: 15s timeout
- Background: 10s timeout

Adjust expectations based on priority level.

### Queue Full Errors (503)

Default queue size is 50. If getting 503 errors:
- Implement client-side queuing
- Reduce prefetch aggressiveness
- Cancel outdated requests more aggressively

## Summary

The priority queue system ensures that user-facing requests are never blocked by background operations. By properly categorizing requests and managing the queue, you can achieve both responsive user experience and efficient resource utilization.