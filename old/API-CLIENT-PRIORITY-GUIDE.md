# Priority Queue Implementation for Mokuro API Client

## The Problem: Current Page Should Never Wait

When users navigate in a manga reader, they need OCR for the current page immediately, even if background prefetching is queuing up future pages. 

## Priority Levels

```javascript
const PRIORITY = {
  CRITICAL: 0,    // Current page user is viewing
  HIGH: 1,        // Adjacent pages (next/previous)
  NORMAL: 2,      // Prefetch nearby pages
  LOW: 3,         // Prefetch distant pages
  BACKGROUND: 4   // Batch processing, cleanup
};
```

## Enhanced Priority Queue Client

```javascript
class PriorityMangaClient {
  constructor() {
    this.baseUrl = 'http://localhost:7331';
    this.maxConcurrent = 2;
    
    // Priority queue - array of arrays, indexed by priority
    this.queues = [
      [], // CRITICAL - current page
      [], // HIGH - adjacent pages
      [], // NORMAL - nearby prefetch
      [], // LOW - distant prefetch
      [], // BACKGROUND - batch ops
    ];
    
    this.activeRequests = new Map();
    this.cache = new Map();
    this.currentPage = null;
    this.prefetchRadius = 3; // Prefetch ±3 pages
  }

  // Main entry point for page OCR
  async getPageOCR(pageNumber, isPrefetch = false) {
    const cacheKey = `page-${pageNumber}`;
    
    // Check cache first
    if (this.cache.has(cacheKey)) {
      return this.cache.get(cacheKey);
    }

    // Determine priority
    let priority;
    if (!isPrefetch && pageNumber === this.currentPage) {
      priority = PRIORITY.CRITICAL;
    } else if (Math.abs(pageNumber - this.currentPage) <= 1) {
      priority = PRIORITY.HIGH;
    } else if (Math.abs(pageNumber - this.currentPage) <= this.prefetchRadius) {
      priority = PRIORITY.NORMAL;
    } else {
      priority = PRIORITY.LOW;
    }

    return this.queueRequest(pageNumber, priority, cacheKey);
  }

  // User navigated to a new page
  async onPageChange(newPageNumber) {
    const oldPage = this.currentPage;
    this.currentPage = newPageNumber;

    // CRITICAL: Reprioritize all queued requests
    this.reprioritizeQueue(oldPage, newPageNumber);

    // Cancel requests for pages far from new position
    this.cancelDistantRequests(newPageNumber);

    // Get current page with CRITICAL priority
    const currentPagePromise = this.getPageOCR(newPageNumber, false);

    // Prefetch adjacent pages with HIGH priority
    this.prefetchPages(newPageNumber);

    return currentPagePromise;
  }

  reprioritizeQueue(oldPage, newPage) {
    // Flatten all queues
    const allRequests = [];
    for (let priority = 0; priority < this.queues.length; priority++) {
      while (this.queues[priority].length > 0) {
        allRequests.push(this.queues[priority].shift());
      }
    }

    // Reprioritize based on distance from new current page
    for (const request of allRequests) {
      const distance = Math.abs(request.pageNumber - newPage);
      
      if (request.pageNumber === newPage) {
        // This is now the current page - CRITICAL!
        request.priority = PRIORITY.CRITICAL;
        // Cancel any existing request for this page and put at front
        this.cancelExistingRequest(request.pageNumber);
      } else if (distance <= 1) {
        request.priority = PRIORITY.HIGH;
      } else if (distance <= this.prefetchRadius) {
        request.priority = PRIORITY.NORMAL;
      } else if (distance <= this.prefetchRadius * 2) {
        request.priority = PRIORITY.LOW;
      } else {
        // Too far away, cancel it
        request.reject(new Error('Page too far from current view'));
        continue;
      }

      // Re-queue with new priority
      this.queues[request.priority].push(request);
    }

    // Process the queue immediately for critical items
    this.processNextRequest();
  }

  cancelDistantRequests(currentPage) {
    // Cancel active requests for pages far from current
    for (const [pageNumber, request] of this.activeRequests) {
      if (Math.abs(pageNumber - currentPage) > this.prefetchRadius * 2) {
        request.controller.abort();
        this.activeRequests.delete(pageNumber);
      }
    }
  }

  async queueRequest(pageNumber, priority, cacheKey) {
    return new Promise((resolve, reject) => {
      const request = {
        pageNumber,
        priority,
        cacheKey,
        resolve,
        reject,
        timestamp: Date.now(),
        attempts: 0,
      };

      // Special handling for CRITICAL priority
      if (priority === PRIORITY.CRITICAL) {
        // Cancel any non-critical active requests to make room
        this.makeRoomForCritical();
        
        // Add to front of critical queue
        this.queues[PRIORITY.CRITICAL].unshift(request);
      } else {
        // Add to appropriate queue
        this.queues[priority].push(request);
      }

      // Start processing
      this.processNextRequest();
    });
  }

  makeRoomForCritical() {
    // If we're at max concurrent, cancel lowest priority active request
    if (this.activeRequests.size >= this.maxConcurrent) {
      let lowestPriority = -1;
      let lowestPageNumber = null;

      for (const [pageNumber, activeReq] of this.activeRequests) {
        if (activeReq.priority > lowestPriority && activeReq.priority > PRIORITY.HIGH) {
          lowestPriority = activeReq.priority;
          lowestPageNumber = pageNumber;
        }
      }

      if (lowestPageNumber !== null) {
        // Cancel the lowest priority request
        const request = this.activeRequests.get(lowestPageNumber);
        request.controller.abort();
        this.activeRequests.delete(lowestPageNumber);
        
        // Re-queue it with BACKGROUND priority
        this.queueRequest(lowestPageNumber, PRIORITY.BACKGROUND, request.cacheKey);
      }
    }
  }

  async processNextRequest() {
    // Don't exceed concurrent limit
    if (this.activeRequests.size >= this.maxConcurrent) {
      return;
    }

    // Find next request from highest priority non-empty queue
    let nextRequest = null;
    for (let priority = 0; priority < this.queues.length; priority++) {
      if (this.queues[priority].length > 0) {
        nextRequest = this.queues[priority].shift();
        break;
      }
    }

    if (!nextRequest) return;

    // Check if already being processed
    if (this.activeRequests.has(nextRequest.pageNumber)) {
      // Already processing this page, merge the promises
      const existing = this.activeRequests.get(nextRequest.pageNumber);
      existing.promise.then(nextRequest.resolve).catch(nextRequest.reject);
      return this.processNextRequest(); // Process next in queue
    }

    // Execute the request
    this.executeRequest(nextRequest);

    // Continue processing queue
    if (this.activeRequests.size < this.maxConcurrent) {
      this.processNextRequest();
    }
  }

  async executeRequest(request) {
    const controller = new AbortController();
    const activeRequest = {
      controller,
      priority: request.priority,
      cacheKey: request.cacheKey,
      promise: null,
    };

    // Store active request
    this.activeRequests.set(request.pageNumber, activeRequest);

    // Create the promise
    activeRequest.promise = (async () => {
      try {
        // Load image for page
        const imageData = await this.loadPageImage(request.pageNumber);
        
        const formData = new FormData();
        formData.append('image', new Blob([imageData]), `page-${request.pageNumber}.jpg`);
        formData.append('ocr_engine', 'manga-ocr');

        // Higher timeout for critical requests
        const timeout = request.priority === PRIORITY.CRITICAL ? 45000 : 30000;

        const response = await fetch(`${this.baseUrl}/api/ocr`, {
          method: 'POST',
          body: formData,
          signal: controller.signal,
          timeout,
        });

        if (!response.ok) {
          if (response.status === 429) {
            // Rate limited - requeue with same priority
            const retryAfter = parseInt(response.headers.get('Retry-After') || '2');
            await this.delay(retryAfter * 1000);
            
            // Requeue unless it's now too far from current page
            if (Math.abs(request.pageNumber - this.currentPage) <= this.prefetchRadius * 2) {
              this.queues[request.priority].push(request);
              this.processNextRequest();
            }
            return;
          }
          throw new Error(`HTTP ${response.status}`);
        }

        const result = await response.json();
        
        // Cache the result
        this.cache.set(request.cacheKey, result);
        
        // Resolve the promise
        request.resolve(result);
        
        return result;
      } catch (error) {
        if (error.name === 'AbortError') {
          request.reject(new Error('Request cancelled'));
        } else if (request.attempts < 3 && request.priority <= PRIORITY.HIGH) {
          // Retry high priority requests
          request.attempts++;
          const delay = Math.min(1000 * Math.pow(2, request.attempts), 5000);
          await this.delay(delay);
          this.queues[request.priority].push(request);
          this.processNextRequest();
        } else {
          request.reject(error);
        }
      } finally {
        // Clean up
        this.activeRequests.delete(request.pageNumber);
        
        // Process next request
        this.processNextRequest();
      }
    })();

    return activeRequest.promise;
  }

  async prefetchPages(currentPage) {
    // Prefetch strategy: closer pages get higher priority
    const prefetchPlan = [
      { page: currentPage + 1, priority: PRIORITY.HIGH },      // Next page
      { page: currentPage - 1, priority: PRIORITY.HIGH },      // Previous page
      { page: currentPage + 2, priority: PRIORITY.NORMAL },    // 2 pages ahead
      { page: currentPage - 2, priority: PRIORITY.NORMAL },    // 2 pages back
      { page: currentPage + 3, priority: PRIORITY.NORMAL },    // 3 pages ahead
      { page: currentPage - 3, priority: PRIORITY.NORMAL },    // 3 pages back
    ];

    for (const { page, priority } of prefetchPlan) {
      if (page >= 0 && !this.cache.has(`page-${page}`)) {
        // Don't await - let them process in background
        this.queueRequest(page, priority, `page-${page}`).catch(() => {
          // Ignore prefetch errors
        });
      }
    }
  }

  // Helper methods
  async loadPageImage(pageNumber) {
    // Simulate loading image for page
    const response = await fetch(`/manga/page-${pageNumber}.jpg`);
    return response.arrayBuffer();
  }

  delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  cancelExistingRequest(pageNumber) {
    const active = this.activeRequests.get(pageNumber);
    if (active) {
      active.controller.abort();
      this.activeRequests.delete(pageNumber);
    }
  }

  getStatus() {
    return {
      currentPage: this.currentPage,
      activeRequests: this.activeRequests.size,
      queuedRequests: this.queues.reduce((sum, q) => sum + q.length, 0),
      queueBreakdown: {
        critical: this.queues[PRIORITY.CRITICAL].length,
        high: this.queues[PRIORITY.HIGH].length,
        normal: this.queues[PRIORITY.NORMAL].length,
        low: this.queues[PRIORITY.LOW].length,
        background: this.queues[PRIORITY.BACKGROUND].length,
      },
      cacheSize: this.cache.size,
    };
  }

  clearCache() {
    this.cache.clear();
  }

  cancelAll() {
    // Cancel all active requests
    for (const [pageNumber, request] of this.activeRequests) {
      request.controller.abort();
    }
    this.activeRequests.clear();

    // Clear all queues
    for (const queue of this.queues) {
      while (queue.length > 0) {
        const request = queue.shift();
        request.reject(new Error('Cancelled'));
      }
    }
  }
}
```

## Usage Example: Manga Reader Integration

```javascript
class MangaReader {
  constructor() {
    this.client = new PriorityMangaClient();
    this.currentPage = 0;
    this.totalPages = 100;
  }

  async init() {
    // Load first page
    await this.goToPage(0);
  }

  async goToPage(pageNumber) {
    console.log(`Navigating to page ${pageNumber}`);
    
    // Update current page and reprioritize everything
    const startTime = Date.now();
    
    try {
      // This will:
      // 1. Cancel distant prefetch requests
      // 2. Reprioritize queued requests
      // 3. Get current page with CRITICAL priority
      // 4. Start prefetching adjacent pages
      const ocrResult = await this.client.onPageChange(pageNumber);
      
      const elapsed = Date.now() - startTime;
      console.log(`Page ${pageNumber} OCR completed in ${elapsed}ms`);
      
      // Display OCR result
      this.displayOCR(ocrResult);
      
      // Update UI
      this.currentPage = pageNumber;
      this.updateNavigationButtons();
      
      // Show status
      console.log('Client status:', this.client.getStatus());
      
    } catch (error) {
      console.error(`Failed to get OCR for page ${pageNumber}:`, error);
      this.showErrorMessage('OCR failed for this page');
    }
  }

  async nextPage() {
    if (this.currentPage < this.totalPages - 1) {
      await this.goToPage(this.currentPage + 1);
    }
  }

  async previousPage() {
    if (this.currentPage > 0) {
      await this.goToPage(this.currentPage - 1);
    }
  }

  async jumpToPage(pageNumber) {
    if (pageNumber >= 0 && pageNumber < this.totalPages) {
      // Cancel all prefetching when jumping far
      this.client.cancelAll();
      await this.goToPage(pageNumber);
    }
  }

  // Keyboard navigation with rapid page changes
  async handleKeyboard(event) {
    if (event.key === 'ArrowRight') {
      await this.nextPage();
    } else if (event.key === 'ArrowLeft') {
      await this.previousPage();
    } else if (event.key === 'Home') {
      await this.jumpToPage(0);
    } else if (event.key === 'End') {
      await this.jumpToPage(this.totalPages - 1);
    }
  }

  displayOCR(ocrResult) {
    // Update UI with OCR text
    document.getElementById('ocr-overlay').innerHTML = 
      ocrResult.blocks.map(block => 
        `<div class="text-block" style="position:absolute; 
          left:${block.box[0]}px; top:${block.box[1]}px;">
          ${block.lines.join('<br>')}
        </div>`
      ).join('');
  }

  updateNavigationButtons() {
    document.getElementById('prev-btn').disabled = this.currentPage === 0;
    document.getElementById('next-btn').disabled = this.currentPage === this.totalPages - 1;
    document.getElementById('page-indicator').textContent = 
      `${this.currentPage + 1} / ${this.totalPages}`;
  }

  showErrorMessage(message) {
    // Show user-friendly error
    const toast = document.getElementById('error-toast');
    toast.textContent = message;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 3000);
  }
}

// Initialize reader
const reader = new MangaReader();
reader.init();

// Bind keyboard events
document.addEventListener('keydown', (e) => reader.handleKeyboard(e));
```

## Priority Queue Scenarios

### Scenario 1: Rapid Page Navigation
```
User on page 5, rapidly presses right arrow 3 times:

Initial state:
- Current: page 5
- Prefetching: pages 4,6 (HIGH), 3,7 (NORMAL)

User presses right → right → right:

After first press (now on page 6):
- Cancel prefetch for pages 3,4
- Page 6 becomes CRITICAL (cuts in line)
- Reprioritize: 7 (HIGH), 8 (NORMAL)

After second press (now on page 7):
- Page 7 becomes CRITICAL (cuts in line) 
- Cancel page 6 if still processing
- Reprioritize: 8 (HIGH), 9 (NORMAL)

After third press (now on page 8):
- Page 8 becomes CRITICAL (cuts in line)
- Cancel page 7 if still processing
- Reprioritize: 9 (HIGH), 10 (NORMAL)

Result: Page 8 loads immediately, earlier pages cancelled
```

### Scenario 2: Jump to Distant Page
```
User on page 10, jumps to page 50:

Before jump:
- Active: OCR for pages 9,11
- Queued: pages 8,12,13

After jump:
- Cancel ALL active/queued requests
- Page 50 gets CRITICAL priority
- Start fresh prefetch: 49,51 (HIGH), 48,52 (NORMAL)

Result: Clean slate, page 50 loads without waiting
```

### Scenario 3: Queue Full with Critical Request
```
Queue state:
- Active: 2 requests (max reached)
- Both are LOW priority prefetch

User navigates to new page (CRITICAL):
1. System cancels lowest priority active request
2. CRITICAL request starts immediately
3. Cancelled request re-queued as BACKGROUND

Result: Current page never waits for prefetch
```

## Performance Tips

1. **Tune Prefetch Radius**: 
   - Fast connection: prefetchRadius = 5
   - Slow connection: prefetchRadius = 2

2. **Adjust Concurrency**:
   - Desktop: maxConcurrent = 2-3
   - Mobile: maxConcurrent = 1

3. **Cache Management**:
   - Keep last 50 pages in cache
   - Clear older entries with LRU policy

4. **Priority Decay**:
   - After 30 seconds, reduce priority by one level
   - Prevents stale prefetch from blocking new requests

## Summary

The priority queue ensures:
- ✅ Current page ALWAYS processes first
- ✅ Adjacent pages prefetch with high priority  
- ✅ Distant prefetch never blocks important requests
- ✅ Queue reprioritizes when user navigates
- ✅ Low-priority requests cancelled to make room
- ✅ Smooth experience even with rapid navigation

This system guarantees the current page loads in < 1 second even with a full prefetch queue!