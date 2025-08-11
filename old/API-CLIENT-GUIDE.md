# Mokuro API Client Implementation Guide

## Best Practices for Integrating with Mokuro API

This guide is for developers building clients that interface with the Mokuro API server. Following these practices will ensure optimal performance and reliability for your users.

## Quick Summary

```javascript
// Ideal client configuration
const config = {
  maxConcurrent: 2,        // Don't exceed 2 concurrent requests
  timeout: 30000,          // 30 second timeout
  retryAttempts: 3,        // Retry failed requests
  retryDelay: 1000,        // Start with 1 second delay
  debounceMs: 300,         // Debounce rapid page changes
  cacheResults: true,      // Cache OCR results locally
  respectRateLimit: true,  // Handle 429 responses properly
};
```

## Server Capabilities & Limits

### Rate Limits
- **`/api/ocr`**: 5 requests/second, 300/minute, 5000/hour
- **`/api/ocr/batch`**: 5 requests/second, 300/minute
- **Global**: 10 requests/second across all endpoints

### Processing Limits
- **Max file size**: 50MB per image
- **Concurrent processing**: 3 operations (server-side)
- **Queue size**: 10 pending requests
- **Timeout**: 30 seconds per OCR operation

## Error Handling Matrix

| Status Code | Error Type | Client Action | Example |
|------------|------------|---------------|---------|
| **200** | Success | Process result | Normal response |
| **400** | Bad Request | Don't retry, fix request | Invalid file type, missing file |
| **413** | Payload Too Large | Resize/compress image | File >50MB |
| **429** | Rate Limited | Wait and retry with backoff | Too many requests |
| **503** | Service Unavailable | Retry with exponential backoff | Queue full, high memory |
| **504** | Gateway Timeout | Retry with smaller image/different engine | OCR timeout |
| **500** | Internal Error | Retry 1-2 times, then fail | Server error |

## Optimal Request Patterns

### 1. Page Navigation Pattern (Manga Reader)

```javascript
class MangaOCRClient {
  constructor() {
    this.pendingRequest = null;
    this.cache = new Map();
    this.debounceTimer = null;
  }

  async getPageOCR(pageUrl, pageNumber) {
    // 1. Check cache first
    const cacheKey = `${pageUrl}-${pageNumber}`;
    if (this.cache.has(cacheKey)) {
      return this.cache.get(cacheKey);
    }

    // 2. Cancel previous pending request
    if (this.pendingRequest) {
      this.pendingRequest.abort();
    }

    // 3. Debounce rapid page changes (user scrolling quickly)
    return new Promise((resolve, reject) => {
      clearTimeout(this.debounceTimer);
      this.debounceTimer = setTimeout(async () => {
        try {
          // 4. Create abortable request
          const controller = new AbortController();
          this.pendingRequest = controller;

          const response = await fetch('http://localhost:7331/api/ocr', {
            method: 'POST',
            body: this.createFormData(pageUrl),
            signal: controller.signal,
            timeout: 30000, // 30 second timeout
          });

          // 5. Handle response
          const result = await this.handleResponse(response);
          
          // 6. Cache successful result
          this.cache.set(cacheKey, result);
          
          resolve(result);
        } catch (error) {
          reject(this.handleError(error));
        } finally {
          this.pendingRequest = null;
        }
      }, 300); // 300ms debounce
    });
  }

  async handleResponse(response) {
    if (response.status === 429) {
      // Rate limited - wait and retry
      const retryAfter = response.headers.get('Retry-After') || '1';
      await this.delay(parseInt(retryAfter) * 1000);
      throw new Error('RATE_LIMITED');
    }

    if (response.status === 503) {
      // Server busy - exponential backoff
      throw new Error('SERVER_BUSY');
    }

    if (response.status === 504) {
      // Timeout - maybe try simpler engine
      throw new Error('TIMEOUT');
    }

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    return response.json();
  }
}
```

### 2. Batch Processing Pattern

```javascript
class BatchProcessor {
  async processChapter(imageUrls) {
    // Split into optimal batch sizes (3-5 images per batch)
    const batchSize = 3;
    const batches = this.chunk(imageUrls, batchSize);
    const results = [];

    for (const batch of batches) {
      try {
        // Process batch with retry logic
        const batchResults = await this.processBatchWithRetry(batch);
        results.push(...batchResults);
        
        // Small delay between batches to avoid overwhelming server
        await this.delay(200);
      } catch (error) {
        console.error('Batch failed:', error);
        // Process failed batch items individually as fallback
        for (const url of batch) {
          try {
            const result = await this.processSingle(url);
            results.push(result);
          } catch (e) {
            results.push({ url, error: e.message });
          }
        }
      }
    }

    return results;
  }

  async processBatchWithRetry(urls, attempts = 3) {
    for (let i = 0; i < attempts; i++) {
      try {
        const formData = new FormData();
        for (const url of urls) {
          const blob = await fetch(url).then(r => r.blob());
          formData.append('images', blob, `image${i}.jpg`);
        }
        formData.append('ocr_engine', 'manga-ocr');

        const response = await fetch('http://localhost:7331/api/ocr/batch', {
          method: 'POST',
          body: formData,
          timeout: 60000, // Higher timeout for batch
        });

        if (response.status === 429) {
          // Rate limited - wait with exponential backoff
          await this.delay(Math.pow(2, i) * 1000);
          continue;
        }

        if (response.ok) {
          const data = await response.json();
          return data.results;
        }

        throw new Error(`HTTP ${response.status}`);
      } catch (error) {
        if (i === attempts - 1) throw error;
        await this.delay(Math.pow(2, i) * 1000);
      }
    }
  }

  chunk(array, size) {
    const chunks = [];
    for (let i = 0; i < array.length; i += size) {
      chunks.push(array.slice(i, i + size));
    }
    return chunks;
  }

  delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}
```

### 3. Circuit Breaker Pattern

```javascript
class CircuitBreaker {
  constructor() {
    this.state = 'CLOSED'; // CLOSED, OPEN, HALF_OPEN
    this.failureCount = 0;
    this.failureThreshold = 5;
    this.resetTimeout = 60000; // 1 minute
    this.nextAttempt = Date.now();
  }

  async call(fn) {
    if (this.state === 'OPEN') {
      if (Date.now() < this.nextAttempt) {
        throw new Error('Circuit breaker is OPEN');
      }
      this.state = 'HALF_OPEN';
    }

    try {
      const result = await fn();
      this.onSuccess();
      return result;
    } catch (error) {
      this.onFailure();
      throw error;
    }
  }

  onSuccess() {
    this.failureCount = 0;
    this.state = 'CLOSED';
  }

  onFailure() {
    this.failureCount++;
    if (this.failureCount >= this.failureThreshold) {
      this.state = 'OPEN';
      this.nextAttempt = Date.now() + this.resetTimeout;
    }
  }
}

// Usage
const breaker = new CircuitBreaker();
const client = new MangaOCRClient();

async function getOCRWithCircuitBreaker(page) {
  try {
    return await breaker.call(() => client.getPageOCR(page));
  } catch (error) {
    if (error.message === 'Circuit breaker is OPEN') {
      // Use fallback or cached data
      return getCachedOCR(page) || { error: 'Service temporarily unavailable' };
    }
    throw error;
  }
}
```

## Health Monitoring

```javascript
class HealthMonitor {
  constructor() {
    this.healthCheckInterval = 30000; // 30 seconds
    this.serverHealthy = true;
  }

  start() {
    setInterval(async () => {
      try {
        const response = await fetch('http://localhost:7331/health', {
          timeout: 5000,
        });
        
        if (response.ok) {
          const health = await response.json();
          this.serverHealthy = true;
          this.updateServerCapabilities(health);
        } else {
          this.serverHealthy = false;
        }
      } catch (error) {
        this.serverHealthy = false;
      }
    }, this.healthCheckInterval);
  }

  updateServerCapabilities(health) {
    // Adjust client behavior based on server status
    if (health.active_requests > 5) {
      // Server is busy, reduce request rate
      this.recommendedConcurrency = 1;
    } else {
      this.recommendedConcurrency = 2;
    }

    if (parseFloat(health.memory_usage) > 70) {
      // High memory usage, avoid large files
      this.maxFileSize = 25 * 1024 * 1024; // 25MB
    } else {
      this.maxFileSize = 50 * 1024 * 1024; // 50MB
    }
  }
}
```

## Complete Example: Production-Ready Client

```javascript
class MokuroAPIClient {
  constructor(config = {}) {
    this.baseUrl = config.baseUrl || 'http://localhost:7331';
    this.maxConcurrent = config.maxConcurrent || 2;
    this.timeout = config.timeout || 30000;
    this.cache = new Map();
    this.activeRequests = new Map();
    this.requestQueue = [];
    this.processing = false;
    this.breaker = new CircuitBreaker();
    this.healthMonitor = new HealthMonitor();
  }

  async initialize() {
    // Start health monitoring
    this.healthMonitor.start();
    
    // Get initial server info
    try {
      const info = await this.getServerInfo();
      console.log('Connected to Mokuro API:', info.version);
      console.log('Available engines:', info.ocr_engines);
    } catch (error) {
      console.warn('Failed to get server info:', error);
    }
  }

  async processImage(imageData, options = {}) {
    const { 
      engine = 'manga-ocr',
      forceCpu = false,
      priority = 'normal',
      cacheKey = null 
    } = options;

    // Check cache
    if (cacheKey && this.cache.has(cacheKey)) {
      return { cached: true, ...this.cache.get(cacheKey) };
    }

    // Queue request
    return new Promise((resolve, reject) => {
      const request = {
        imageData,
        engine,
        forceCpu,
        priority,
        cacheKey,
        resolve,
        reject,
        attempts: 0,
        maxAttempts: 3,
      };

      if (priority === 'high') {
        this.requestQueue.unshift(request);
      } else {
        this.requestQueue.push(request);
      }

      this.processQueue();
    });
  }

  async processQueue() {
    if (this.processing) return;
    this.processing = true;

    while (this.requestQueue.length > 0) {
      // Respect concurrency limit
      if (this.activeRequests.size >= this.maxConcurrent) {
        await this.waitForSlot();
      }

      const request = this.requestQueue.shift();
      this.executeRequest(request);
    }

    this.processing = false;
  }

  async executeRequest(request) {
    const requestId = Math.random().toString(36).substr(2, 9);
    this.activeRequests.set(requestId, request);

    try {
      const result = await this.breaker.call(async () => {
        const formData = new FormData();
        formData.append('image', new Blob([request.imageData]), 'image.jpg');
        formData.append('ocr_engine', request.engine);
        formData.append('force_cpu', request.forceCpu.toString());

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), this.timeout);

        try {
          const response = await fetch(`${this.baseUrl}/api/ocr`, {
            method: 'POST',
            body: formData,
            signal: controller.signal,
          });

          clearTimeout(timeoutId);

          if (response.status === 429) {
            // Rate limited
            const retryAfter = parseInt(response.headers.get('Retry-After') || '1');
            await this.delay(retryAfter * 1000);
            throw new Error('RATE_LIMITED');
          }

          if (response.status === 503) {
            // Server busy
            throw new Error('SERVER_BUSY');
          }

          if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
          }

          return await response.json();
        } finally {
          clearTimeout(timeoutId);
        }
      });

      // Cache successful result
      if (request.cacheKey) {
        this.cache.set(request.cacheKey, result);
      }

      request.resolve(result);
    } catch (error) {
      request.attempts++;
      
      if (request.attempts < request.maxAttempts && this.shouldRetry(error)) {
        // Retry with exponential backoff
        const delay = Math.min(1000 * Math.pow(2, request.attempts), 10000);
        setTimeout(() => {
          this.requestQueue.unshift(request);
          this.processQueue();
        }, delay);
      } else {
        request.reject(error);
      }
    } finally {
      this.activeRequests.delete(requestId);
    }
  }

  shouldRetry(error) {
    const retryableErrors = ['RATE_LIMITED', 'SERVER_BUSY', 'TIMEOUT', 'ECONNRESET'];
    return retryableErrors.some(e => error.message.includes(e));
  }

  async waitForSlot() {
    return new Promise(resolve => {
      const check = setInterval(() => {
        if (this.activeRequests.size < this.maxConcurrent) {
          clearInterval(check);
          resolve();
        }
      }, 100);
    });
  }

  delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  async getServerInfo() {
    const response = await fetch(`${this.baseUrl}/api/info`);
    return response.json();
  }

  // Cancel all pending requests
  cancelAll() {
    this.requestQueue = [];
    for (const [id, request] of this.activeRequests) {
      request.reject(new Error('Cancelled'));
    }
    this.activeRequests.clear();
  }

  // Get current status
  getStatus() {
    return {
      queueLength: this.requestQueue.length,
      activeRequests: this.activeRequests.size,
      cacheSize: this.cache.size,
      serverHealthy: this.healthMonitor.serverHealthy,
      circuitBreakerState: this.breaker.state,
    };
  }
}

// Usage Example
async function main() {
  const client = new MokuroAPIClient({
    baseUrl: 'http://localhost:7331',
    maxConcurrent: 2,
    timeout: 30000,
  });

  await client.initialize();

  // Process single image
  try {
    const imageData = await fetch('manga-page.jpg').then(r => r.arrayBuffer());
    const result = await client.processImage(imageData, {
      engine: 'manga-ocr',
      cacheKey: 'page-001',
      priority: 'high',
    });
    console.log('OCR Result:', result);
  } catch (error) {
    console.error('OCR Failed:', error);
  }

  // Check client status
  console.log('Client Status:', client.getStatus());
}
```

## Don'ts - Common Mistakes to Avoid

### ❌ DON'T: Fire and Forget
```javascript
// BAD - No error handling, no cancellation
for (let i = 0; i < 100; i++) {
  fetch('/api/ocr', { method: 'POST', body: formData });
}
```

### ❌ DON'T: Ignore Rate Limits
```javascript
// BAD - Will get 429 errors
while (true) {
  await fetch('/api/ocr', { method: 'POST', body: formData });
}
```

### ❌ DON'T: No Timeout
```javascript
// BAD - Can hang forever
const response = await fetch('/api/ocr', {
  method: 'POST',
  body: formData,
  // No timeout!
});
```

### ❌ DON'T: Retry Immediately
```javascript
// BAD - Hammers the server
while (true) {
  try {
    const response = await fetch('/api/ocr', options);
    break;
  } catch (error) {
    // No delay!
    continue;
  }
}
```

## Testing Your Integration

```javascript
// Test suite for your client
describe('Mokuro API Client', () => {
  it('should handle rate limiting gracefully', async () => {
    // Send 10 rapid requests
    const promises = Array(10).fill().map(() => 
      client.processImage(testImage)
    );
    
    // Should complete without errors (client handles 429s)
    const results = await Promise.allSettled(promises);
    expect(results.filter(r => r.status === 'fulfilled').length).toBeGreaterThan(5);
  });

  it('should cancel pending requests on navigation', async () => {
    const promise = client.processImage(largeImage);
    client.cancelAll();
    
    await expect(promise).rejects.toThrow('Cancelled');
    expect(client.getStatus().activeRequests).toBe(0);
  });

  it('should use cache for duplicate requests', async () => {
    const result1 = await client.processImage(testImage, { cacheKey: 'test' });
    const result2 = await client.processImage(testImage, { cacheKey: 'test' });
    
    expect(result2.cached).toBe(true);
  });

  it('should handle server timeout', async () => {
    // Use a complex image that might timeout
    const result = await client.processImage(complexImage, {
      timeout: 5000,
    });
    
    // Should either succeed or retry with simpler settings
    expect(result).toBeDefined();
  });
});
```

## Summary Checklist

- [ ] Implement request debouncing (300ms+)
- [ ] Cancel pending requests when navigating
- [ ] Respect rate limits (handle 429)
- [ ] Add timeouts (30s recommended)
- [ ] Implement exponential backoff
- [ ] Cache results locally
- [ ] Monitor server health
- [ ] Use circuit breaker pattern
- [ ] Limit concurrent requests (2-3 max)
- [ ] Handle all error codes properly
- [ ] Add request prioritization
- [ ] Implement graceful degradation
- [ ] Test error scenarios
- [ ] Log errors for debugging
- [ ] Provide user feedback

## Contact

For API issues or questions, refer to:
- API Documentation: `/api/info` endpoint
- Health Status: `/health` endpoint
- Server Status: `/api/status` endpoint

Remember: A well-behaved client makes the service better for everyone!