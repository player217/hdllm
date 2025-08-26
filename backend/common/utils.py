"""
Common Utility Functions
Author: Claude Code
Date: 2025-01-27  
Description: Phase 2C - Shared utility functions and helpers
"""

import hashlib
import uuid
import time
import asyncio
import functools
import re
import logging
from typing import Any, Callable, Optional, List, TypeVar, Union
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)

T = TypeVar('T')


def generate_request_id() -> str:
    """
    Generate unique request ID
    
    Returns:
        UUID string
    """
    return str(uuid.uuid4())


def calculate_hash(text: str, algorithm: str = "md5") -> str:
    """
    Calculate hash of text
    
    Args:
        text: Input text
        algorithm: Hash algorithm (md5, sha256, sha512)
        
    Returns:
        Hash string
    """
    if algorithm == "md5":
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    elif algorithm == "sha256":
        return hashlib.sha256(text.encode('utf-8')).hexdigest()
    elif algorithm == "sha512":
        return hashlib.sha512(text.encode('utf-8')).hexdigest()
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")


def normalize_text(text: str, lowercase: bool = True, remove_special: bool = False) -> str:
    """
    Normalize text for processing
    
    Args:
        text: Input text
        lowercase: Convert to lowercase
        remove_special: Remove special characters
        
    Returns:
        Normalized text
    """
    # Remove extra whitespace
    text = ' '.join(text.split())
    
    # Lowercase
    if lowercase:
        text = text.lower()
    
    # Remove special characters
    if remove_special:
        text = re.sub(r'[^\w\s가-힣]', ' ', text)
        text = ' '.join(text.split())
    
    return text.strip()


def validate_vector(vector: List[float], expected_dim: Optional[int] = None) -> bool:
    """
    Validate embedding vector
    
    Args:
        vector: Embedding vector
        expected_dim: Expected dimension
        
    Returns:
        Validation result
    """
    if not vector:
        return False
    
    if expected_dim and len(vector) != expected_dim:
        return False
    
    # Check if all elements are floats
    if not all(isinstance(x, (int, float)) for x in vector):
        return False
    
    # Check for NaN or Inf
    if any(np.isnan(x) or np.isinf(x) for x in vector):
        return False
    
    return True


def chunk_text(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    preserve_sentences: bool = True
) -> List[str]:
    """
    Split text into chunks
    
    Args:
        text: Input text
        chunk_size: Maximum chunk size
        chunk_overlap: Overlap between chunks
        preserve_sentences: Try to preserve sentence boundaries
        
    Returns:
        List of text chunks
    """
    if not text:
        return []
    
    chunks = []
    
    if preserve_sentences:
        # Split by sentences (Korean and English)
        sentences = re.split(r'(?<=[.!?。！？])\s+', text)
        
        current_chunk = ""
        for sentence in sentences:
            if len(current_chunk) + len(sentence) <= chunk_size:
                current_chunk += sentence + " "
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + " "
        
        if current_chunk:
            chunks.append(current_chunk.strip())
    
    else:
        # Simple character-based chunking
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start = end - chunk_overlap
    
    return chunks


def mask_pii(text: str) -> str:
    """
    Mask personally identifiable information
    
    Args:
        text: Input text
        
    Returns:
        Text with masked PII
    """
    # Korean SSN pattern
    text = re.sub(
        r'\d{6}-?[1-4]\d{6}',
        '[SSN_MASKED]',
        text
    )
    
    # Phone number pattern
    text = re.sub(
        r'01[0-9]-?\d{3,4}-?\d{4}',
        '[PHONE_MASKED]',
        text
    )
    
    # Email pattern
    text = re.sub(
        r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        '[EMAIL_MASKED]',
        text
    )
    
    # Credit card pattern
    text = re.sub(
        r'\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}',
        '[CARD_MASKED]',
        text
    )
    
    return text


class Timer:
    """
    Context manager for timing operations
    
    Example:
        with Timer() as timer:
            # Do something
            pass
        print(f"Elapsed: {timer.elapsed_ms}ms")
    """
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.perf_counter()
    
    @property
    def elapsed(self) -> float:
        """Elapsed time in seconds"""
        if self.start_time is None:
            return 0
        end = self.end_time or time.perf_counter()
        return end - self.start_time
    
    @property
    def elapsed_ms(self) -> float:
        """Elapsed time in milliseconds"""
        return self.elapsed * 1000


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True
):
    """
    Decorator for retry with exponential backoff
    
    Args:
        max_retries: Maximum retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff
        jitter: Add random jitter to delay
        
    Example:
        @retry_with_backoff(max_retries=3)
        async def fetch_data():
            return await api_call()
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                    
                except Exception as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(f"Max retries ({max_retries}) exceeded for {func.__name__}: {e}")
                        raise
                    
                    # Calculate delay
                    delay = min(base_delay * (exponential_base ** attempt), max_delay)
                    
                    # Add jitter
                    if jitter:
                        import random
                        delay = delay * (0.5 + random.random())
                    
                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries + 1} failed for {func.__name__}: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    
                    await asyncio.sleep(delay)
            
            raise last_exception
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                    
                except Exception as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(f"Max retries ({max_retries}) exceeded for {func.__name__}: {e}")
                        raise
                    
                    # Calculate delay
                    delay = min(base_delay * (exponential_base ** attempt), max_delay)
                    
                    # Add jitter
                    if jitter:
                        import random
                        delay = delay * (0.5 + random.random())
                    
                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries + 1} failed for {func.__name__}: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    
                    time.sleep(delay)
            
            raise last_exception
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


class RateLimiter:
    """
    Rate limiter using token bucket algorithm
    
    Example:
        limiter = RateLimiter(rate=10, per=1.0)  # 10 requests per second
        
        async with limiter:
            await api_call()
    """
    
    def __init__(self, rate: int, per: float = 1.0):
        """
        Initialize rate limiter
        
        Args:
            rate: Number of allowed requests
            per: Time period in seconds
        """
        self.rate = rate
        self.per = per
        self.tokens = rate
        self.updated_at = time.monotonic()
        self._lock = asyncio.Lock()
    
    async def acquire(self, tokens: int = 1) -> None:
        """
        Acquire tokens, blocking if necessary
        
        Args:
            tokens: Number of tokens to acquire
        """
        async with self._lock:
            while tokens > self.tokens:
                self._add_tokens()
                if tokens > self.tokens:
                    sleep_time = (tokens - self.tokens) * (self.per / self.rate)
                    await asyncio.sleep(sleep_time)
            
            self.tokens -= tokens
    
    def _add_tokens(self) -> None:
        """Add tokens based on elapsed time"""
        now = time.monotonic()
        elapsed = now - self.updated_at
        self.tokens = min(self.rate, self.tokens + elapsed * (self.rate / self.per))
        self.updated_at = now
    
    async def __aenter__(self):
        await self.acquire()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


def format_bytes(bytes_value: int) -> str:
    """
    Format bytes to human readable string
    
    Args:
        bytes_value: Size in bytes
        
    Returns:
        Formatted string
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} PB"


def format_duration(seconds: float) -> str:
    """
    Format duration to human readable string
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted string
    """
    if seconds < 60:
        return f"{seconds:.2f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.2f}m"
    elif seconds < 86400:
        hours = seconds / 3600
        return f"{hours:.2f}h"
    else:
        days = seconds / 86400
        return f"{days:.2f}d"


def truncate_text(text: str, max_length: int = 100, ellipsis: str = "...") -> str:
    """
    Truncate text to maximum length
    
    Args:
        text: Input text
        max_length: Maximum length
        ellipsis: Ellipsis string
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(ellipsis)] + ellipsis


def get_timestamp(format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    Get formatted timestamp
    
    Args:
        format_str: Format string
        
    Returns:
        Formatted timestamp
    """
    return datetime.now().strftime(format_str)


class AsyncBatcher:
    """
    Batch async operations for efficiency
    
    Example:
        batcher = AsyncBatcher(batch_size=10, timeout=1.0)
        
        async def process_batch(items):
            return await api_batch_call(items)
        
        result = await batcher.add(item, process_batch)
    """
    
    def __init__(self, batch_size: int = 10, timeout: float = 1.0):
        """
        Initialize async batcher
        
        Args:
            batch_size: Maximum batch size
            timeout: Maximum time to wait for batch
        """
        self.batch_size = batch_size
        self.timeout = timeout
        self._items = []
        self._futures = []
        self._lock = asyncio.Lock()
        self._timer_task = None
    
    async def add(self, item: Any, processor: Callable) -> Any:
        """
        Add item to batch
        
        Args:
            item: Item to process
            processor: Batch processing function
            
        Returns:
            Processing result for item
        """
        future = asyncio.Future()
        
        async with self._lock:
            self._items.append(item)
            self._futures.append(future)
            
            # Process if batch is full
            if len(self._items) >= self.batch_size:
                await self._process_batch(processor)
            
            # Start timer if needed
            elif self._timer_task is None:
                self._timer_task = asyncio.create_task(self._timeout_handler(processor))
        
        return await future
    
    async def _timeout_handler(self, processor: Callable) -> None:
        """Handle timeout for batch processing"""
        await asyncio.sleep(self.timeout)
        async with self._lock:
            if self._items:
                await self._process_batch(processor)
    
    async def _process_batch(self, processor: Callable) -> None:
        """Process current batch"""
        if not self._items:
            return
        
        # Get current batch
        items = self._items.copy()
        futures = self._futures.copy()
        
        # Clear for next batch
        self._items.clear()
        self._futures.clear()
        
        # Cancel timer
        if self._timer_task:
            self._timer_task.cancel()
            self._timer_task = None
        
        try:
            # Process batch
            results = await processor(items)
            
            # Resolve futures
            for future, result in zip(futures, results):
                future.set_result(result)
                
        except Exception as e:
            # Reject all futures
            for future in futures:
                future.set_exception(e)


# Example usage
if __name__ == "__main__":
    # Test utilities
    print(f"Request ID: {generate_request_id()}")
    print(f"Hash: {calculate_hash('test text')}")
    print(f"Normalized: {normalize_text('  Hello   World!  ', remove_special=True)}")
    
    # Test timer
    with Timer() as timer:
        time.sleep(0.1)
    print(f"Elapsed: {timer.elapsed_ms:.2f}ms")
    
    # Test formatting
    print(f"Bytes: {format_bytes(1234567890)}")
    print(f"Duration: {format_duration(3661)}")
    print(f"Truncated: {truncate_text('This is a very long text that needs to be truncated', 20)}")
    
    # Test async operations
    async def test_async():
        # Test rate limiter
        limiter = RateLimiter(rate=5, per=1.0)
        
        for i in range(10):
            async with limiter:
                print(f"Request {i + 1}")
                await asyncio.sleep(0.1)
        
        # Test retry
        @retry_with_backoff(max_retries=2)
        async def flaky_operation():
            import random
            if random.random() < 0.7:
                raise Exception("Random failure")
            return "Success"
        
        try:
            result = await flaky_operation()
            print(f"Result: {result}")
        except Exception as e:
            print(f"Failed: {e}")
    
    # Run async tests
    # asyncio.run(test_async())