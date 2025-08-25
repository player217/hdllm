"""
Performance Optimization Module for HD현대미포 Gauss-1 RAG System
Author: Claude Code
Date: 2024-01-22
Description: GPU acceleration, parallel processing, and caching optimizations
"""

import os
import json
import asyncio
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from functools import lru_cache
from datetime import datetime, timedelta
import logging

import torch
import numpy as np
from sentence_transformers import SentenceTransformer

# Optional imports
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    
try:
    import torch.cuda
    CUDA_AVAILABLE = torch.cuda.is_available()
except:
    CUDA_AVAILABLE = False

logger = logging.getLogger(__name__)


# =============================================================================
# GPU Optimization
# =============================================================================

class GPUOptimizedEmbedding:
    """GPU-accelerated embedding generation with batch processing"""
    
    def __init__(self, model_name: str = "BAAI/bge-m3", device: str = None):
        """
        Initialize GPU-optimized embedding model
        
        Args:
            model_name: Name of the embedding model
            device: Device to use (cuda/cpu/auto)
        """
        # Auto-detect device
        if device is None or device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
            
        logger.info(f"Initializing embedding model on device: {self.device}")
        
        # Load model
        self.model = SentenceTransformer(model_name)
        self.model.to(self.device)
        
        # Optimize model if using PyTorch 2.0+
        if hasattr(torch, 'compile') and self.device == "cuda":
            logger.info("Compiling model with torch.compile for better performance")
            self.model = torch.compile(self.model, mode="reduce-overhead")
        
        # Set optimal batch size based on device
        if self.device == "cuda":
            # Get GPU memory to determine batch size
            gpu_mem = torch.cuda.get_device_properties(0).total_memory / 1024**3  # GB
            if gpu_mem >= 16:
                self.batch_size = 128
            elif gpu_mem >= 8:
                self.batch_size = 64
            else:
                self.batch_size = 32
        else:
            self.batch_size = 16
            
        logger.info(f"Batch size set to: {self.batch_size}")
    
    def encode_single(self, text: str) -> np.ndarray:
        """Encode single text to embedding"""
        with torch.no_grad():
            embedding = self.model.encode(
                text,
                convert_to_tensor=True,
                normalize_embeddings=True,
                device=self.device
            )
        return embedding.cpu().numpy()
    
    def encode_batch(self, texts: List[str]) -> np.ndarray:
        """Encode batch of texts to embeddings"""
        with torch.no_grad():
            embeddings = self.model.encode(
                texts,
                batch_size=self.batch_size,
                convert_to_tensor=True,
                normalize_embeddings=True,
                show_progress_bar=False,
                device=self.device
            )
        return embeddings.cpu().numpy()
    
    async def encode_batch_async(self, texts: List[str]) -> np.ndarray:
        """Asynchronously encode batch of texts"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.encode_batch, texts)
    
    def get_memory_usage(self) -> Dict[str, float]:
        """Get current GPU memory usage"""
        if self.device == "cuda":
            return {
                "allocated": torch.cuda.memory_allocated() / 1024**3,
                "reserved": torch.cuda.memory_reserved() / 1024**3,
                "free": (torch.cuda.get_device_properties(0).total_memory - 
                        torch.cuda.memory_allocated()) / 1024**3
            }
        return {"device": "cpu", "memory": "N/A"}


# =============================================================================
# Parallel Processing
# =============================================================================

class ParallelDocumentProcessor:
    """Parallel document processing with thread/process pools"""
    
    def __init__(self, max_workers: int = None, use_processes: bool = False):
        """
        Initialize parallel processor
        
        Args:
            max_workers: Maximum number of workers (None for auto)
            use_processes: Use ProcessPoolExecutor instead of ThreadPoolExecutor
        """
        if max_workers is None:
            import multiprocessing
            max_workers = min(multiprocessing.cpu_count(), 8)
        
        self.max_workers = max_workers
        self.use_processes = use_processes
        
        if use_processes:
            self.executor = ProcessPoolExecutor(max_workers=max_workers)
        else:
            self.executor = ThreadPoolExecutor(max_workers=max_workers)
            
        logger.info(f"Initialized {'Process' if use_processes else 'Thread'}PoolExecutor with {max_workers} workers")
    
    def process_documents(self, documents: List[str], process_func) -> List[Any]:
        """
        Process documents in parallel
        
        Args:
            documents: List of documents to process
            process_func: Function to apply to each document
            
        Returns:
            List of processed results
        """
        futures = []
        for doc in documents:
            future = self.executor.submit(process_func, doc)
            futures.append(future)
        
        results = []
        for future in futures:
            try:
                result = future.result(timeout=30)
                results.append(result)
            except Exception as e:
                logger.error(f"Error processing document: {e}")
                results.append(None)
        
        return results
    
    async def process_documents_async(self, documents: List[str], process_func) -> List[Any]:
        """Asynchronously process documents in parallel"""
        loop = asyncio.get_event_loop()
        
        # Create tasks for each document
        tasks = []
        for doc in documents:
            task = loop.run_in_executor(self.executor, process_func, doc)
            tasks.append(task)
        
        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Log any errors
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error processing document {i}: {result}")
                results[i] = None
        
        return results
    
    def chunk_and_process(self, items: List[Any], chunk_size: int, process_func) -> List[Any]:
        """
        Process items in chunks for better memory management
        
        Args:
            items: List of items to process
            chunk_size: Size of each chunk
            process_func: Function to apply to each chunk
            
        Returns:
            Flattened list of results
        """
        results = []
        
        for i in range(0, len(items), chunk_size):
            chunk = items[i:i + chunk_size]
            chunk_results = self.process_documents(chunk, process_func)
            results.extend(chunk_results)
        
        return results
    
    def __del__(self):
        """Cleanup executor on deletion"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=False)


# =============================================================================
# Advanced Caching
# =============================================================================

class HybridCache:
    """Hybrid caching with memory and Redis support"""
    
    def __init__(self, 
                 redis_host: str = "localhost",
                 redis_port: int = 6379,
                 redis_db: int = 0,
                 memory_size: int = 1000,
                 ttl: int = 3600):
        """
        Initialize hybrid cache
        
        Args:
            redis_host: Redis server host
            redis_port: Redis server port
            redis_db: Redis database number
            memory_size: Size of in-memory LRU cache
            ttl: Time-to-live in seconds
        """
        self.ttl = ttl
        self.memory_cache = {}
        self.memory_size = memory_size
        self.access_times = {}
        
        # Initialize Redis if available
        self.redis_client = None
        if REDIS_AVAILABLE:
            try:
                self.redis_client = redis.Redis(
                    host=redis_host,
                    port=redis_port,
                    db=redis_db,
                    decode_responses=True
                )
                self.redis_client.ping()
                logger.info("Redis cache connected successfully")
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}. Using memory cache only.")
                self.redis_client = None
    
    def _get_cache_key(self, text: str) -> str:
        """Generate cache key from text"""
        return hashlib.md5(text.encode()).hexdigest()
    
    def get(self, text: str) -> Optional[List[float]]:
        """Get embedding from cache"""
        key = self._get_cache_key(text)
        
        # Check memory cache first
        if key in self.memory_cache:
            self.access_times[key] = datetime.now()
            return self.memory_cache[key]
        
        # Check Redis if available
        if self.redis_client:
            try:
                cached = self.redis_client.get(f"emb:{key}")
                if cached:
                    embedding = json.loads(cached)
                    # Add to memory cache
                    self._add_to_memory(key, embedding)
                    return embedding
            except Exception as e:
                logger.error(f"Redis get error: {e}")
        
        return None
    
    def set(self, text: str, embedding: List[float]):
        """Set embedding in cache"""
        key = self._get_cache_key(text)
        
        # Add to memory cache
        self._add_to_memory(key, embedding)
        
        # Add to Redis if available
        if self.redis_client:
            try:
                self.redis_client.setex(
                    f"emb:{key}",
                    self.ttl,
                    json.dumps(embedding)
                )
            except Exception as e:
                logger.error(f"Redis set error: {e}")
    
    def _add_to_memory(self, key: str, value: Any):
        """Add item to memory cache with LRU eviction"""
        # Check if we need to evict
        if len(self.memory_cache) >= self.memory_size:
            # Find least recently used
            if self.access_times:
                lru_key = min(self.access_times, key=self.access_times.get)
                del self.memory_cache[lru_key]
                del self.access_times[lru_key]
        
        self.memory_cache[key] = value
        self.access_times[key] = datetime.now()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        stats = {
            "memory_size": len(self.memory_cache),
            "memory_limit": self.memory_size,
            "redis_available": self.redis_client is not None
        }
        
        if self.redis_client:
            try:
                info = self.redis_client.info()
                stats["redis_used_memory"] = info.get("used_memory_human", "N/A")
                stats["redis_keys"] = self.redis_client.dbsize()
            except:
                pass
        
        return stats
    
    def clear(self):
        """Clear all caches"""
        self.memory_cache.clear()
        self.access_times.clear()
        
        if self.redis_client:
            try:
                self.redis_client.flushdb()
            except Exception as e:
                logger.error(f"Redis clear error: {e}")


# =============================================================================
# Streaming Optimization
# =============================================================================

class OptimizedStreamer:
    """Optimized streaming with buffering and compression"""
    
    def __init__(self, buffer_size: int = 10, compress: bool = False):
        """
        Initialize optimized streamer
        
        Args:
            buffer_size: Number of chunks to buffer before sending
            compress: Whether to compress chunks
        """
        self.buffer_size = buffer_size
        self.compress = compress
        self.buffer = []
    
    async def stream_with_buffer(self, generator):
        """Stream with intelligent buffering"""
        async for chunk in generator:
            self.buffer.append(chunk)
            
            if len(self.buffer) >= self.buffer_size:
                # Send buffered chunks
                if self.compress:
                    yield self._compress_chunks(self.buffer)
                else:
                    yield "".join(self.buffer)
                
                self.buffer.clear()
        
        # Send remaining chunks
        if self.buffer:
            if self.compress:
                yield self._compress_chunks(self.buffer)
            else:
                yield "".join(self.buffer)
    
    def _compress_chunks(self, chunks: List[str]) -> str:
        """Compress chunks for transmission"""
        import zlib
        combined = "".join(chunks)
        compressed = zlib.compress(combined.encode())
        # Return base64 encoded for JSON transmission
        import base64
        return base64.b64encode(compressed).decode()


# =============================================================================
# Performance Monitor
# =============================================================================

class PerformanceMonitor:
    """Monitor and report performance metrics"""
    
    def __init__(self):
        self.metrics = {
            "request_count": 0,
            "total_time": 0,
            "embedding_time": 0,
            "search_time": 0,
            "llm_time": 0,
            "cache_hits": 0,
            "cache_misses": 0
        }
        self.start_time = datetime.now()
    
    def record_metric(self, metric_name: str, value: float):
        """Record a performance metric"""
        if metric_name in self.metrics:
            if "time" in metric_name:
                self.metrics[metric_name] += value
            else:
                self.metrics[metric_name] = value
    
    def increment_counter(self, counter_name: str):
        """Increment a counter metric"""
        if counter_name in self.metrics:
            self.metrics[counter_name] += 1
    
    def get_summary(self) -> Dict[str, Any]:
        """Get performance summary"""
        uptime = (datetime.now() - self.start_time).total_seconds()
        
        summary = {
            "uptime_seconds": uptime,
            "total_requests": self.metrics["request_count"],
            "avg_response_time": self.metrics["total_time"] / max(1, self.metrics["request_count"]),
            "cache_hit_rate": self.metrics["cache_hits"] / max(1, self.metrics["cache_hits"] + self.metrics["cache_misses"]),
            "metrics": self.metrics
        }
        
        if CUDA_AVAILABLE:
            summary["gpu_memory"] = {
                "allocated_gb": torch.cuda.memory_allocated() / 1024**3,
                "reserved_gb": torch.cuda.memory_reserved() / 1024**3
            }
        
        return summary


# =============================================================================
# Singleton Instances
# =============================================================================

# Global instances for reuse
_gpu_embedder = None
_parallel_processor = None
_hybrid_cache = None
_performance_monitor = None


def get_gpu_embedder(model_name: str = "BAAI/bge-m3") -> GPUOptimizedEmbedding:
    """Get or create GPU embedder singleton"""
    global _gpu_embedder
    if _gpu_embedder is None:
        _gpu_embedder = GPUOptimizedEmbedding(model_name)
    return _gpu_embedder


def get_parallel_processor(max_workers: int = None) -> ParallelDocumentProcessor:
    """Get or create parallel processor singleton"""
    global _parallel_processor
    if _parallel_processor is None:
        _parallel_processor = ParallelDocumentProcessor(max_workers)
    return _parallel_processor


def get_hybrid_cache() -> HybridCache:
    """Get or create hybrid cache singleton"""
    global _hybrid_cache
    if _hybrid_cache is None:
        _hybrid_cache = HybridCache()
    return _hybrid_cache


def get_performance_monitor() -> PerformanceMonitor:
    """Get or create performance monitor singleton"""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor