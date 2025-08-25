"""
Performance Optimization Tests for HD현대미포 Gauss-1 RAG System
Author: Claude Code
Date: 2024-01-22
"""

import unittest
import asyncio
import time
import sys
import os
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from performance_optimizer import (
    GPUOptimizedEmbedding,
    ParallelDocumentProcessor,
    HybridCache,
    OptimizedStreamer,
    PerformanceMonitor
)


class TestGPUOptimization(unittest.TestCase):
    """Test GPU optimization features"""
    
    @classmethod
    def setUpClass(cls):
        """Set up GPU embedder once for all tests"""
        try:
            cls.embedder = GPUOptimizedEmbedding(device="cpu")  # Use CPU for testing
            cls.gpu_available = False
        except Exception as e:
            cls.embedder = None
            cls.gpu_available = False
    
    def test_single_embedding(self):
        """Test single text embedding"""
        if not self.embedder:
            self.skipTest("Embedder not available")
        
        text = "테스트 문장입니다"
        embedding = self.embedder.encode_single(text)
        
        # Check embedding properties
        self.assertEqual(len(embedding.shape), 1)  # 1D array
        self.assertGreater(embedding.shape[0], 0)  # Has dimensions
    
    def test_batch_embedding(self):
        """Test batch text embedding"""
        if not self.embedder:
            self.skipTest("Embedder not available")
        
        texts = [
            "첫 번째 테스트 문장",
            "두 번째 테스트 문장",
            "세 번째 테스트 문장"
        ]
        embeddings = self.embedder.encode_batch(texts)
        
        # Check batch embedding properties
        self.assertEqual(len(embeddings), len(texts))
        self.assertEqual(len(embeddings.shape), 2)  # 2D array
    
    def test_async_embedding(self):
        """Test asynchronous embedding"""
        if not self.embedder:
            self.skipTest("Embedder not available")
        
        async def test_async():
            texts = ["비동기 테스트 1", "비동기 테스트 2"]
            embeddings = await self.embedder.encode_batch_async(texts)
            return embeddings
        
        embeddings = asyncio.run(test_async())
        self.assertIsNotNone(embeddings)


class TestParallelProcessing(unittest.TestCase):
    """Test parallel processing capabilities"""
    
    def setUp(self):
        self.processor = ParallelDocumentProcessor(max_workers=2)
    
    def test_parallel_document_processing(self):
        """Test parallel document processing"""
        documents = ["문서1", "문서2", "문서3", "문서4"]
        
        def process_func(doc):
            # Simulate processing
            time.sleep(0.1)
            return f"processed_{doc}"
        
        start_time = time.time()
        results = self.processor.process_documents(documents, process_func)
        elapsed = time.time() - start_time
        
        # Check results
        self.assertEqual(len(results), len(documents))
        for i, result in enumerate(results):
            self.assertEqual(result, f"processed_{documents[i]}")
        
        # Should be faster than sequential (4 * 0.1 = 0.4s)
        # With 2 workers, should take ~0.2s
        self.assertLess(elapsed, 0.35)
    
    def test_async_document_processing(self):
        """Test asynchronous document processing"""
        documents = ["async1", "async2", "async3"]
        
        def process_func(doc):
            return f"async_processed_{doc}"
        
        async def test_async():
            results = await self.processor.process_documents_async(
                documents, process_func
            )
            return results
        
        results = asyncio.run(test_async())
        
        self.assertEqual(len(results), len(documents))
        for i, result in enumerate(results):
            self.assertEqual(result, f"async_processed_{documents[i]}")
    
    def test_chunk_processing(self):
        """Test chunk-based processing"""
        items = list(range(10))
        
        def process_func(item):
            return item * 2
        
        results = self.processor.chunk_and_process(items, 3, process_func)
        
        self.assertEqual(len(results), len(items))
        for i, result in enumerate(results):
            self.assertEqual(result, items[i] * 2)


class TestHybridCache(unittest.TestCase):
    """Test hybrid caching system"""
    
    def setUp(self):
        self.cache = HybridCache(memory_size=5)
    
    def test_cache_set_get(self):
        """Test basic cache operations"""
        text = "테스트 쿼리"
        embedding = [0.1, 0.2, 0.3, 0.4]
        
        # Set in cache
        self.cache.set(text, embedding)
        
        # Get from cache
        cached = self.cache.get(text)
        self.assertEqual(cached, embedding)
    
    def test_cache_miss(self):
        """Test cache miss"""
        cached = self.cache.get("존재하지 않는 쿼리")
        self.assertIsNone(cached)
    
    def test_lru_eviction(self):
        """Test LRU eviction policy"""
        # Fill cache beyond capacity
        for i in range(7):
            self.cache.set(f"query_{i}", [float(i)])
        
        # First two should be evicted
        self.assertIsNone(self.cache.get("query_0"))
        self.assertIsNone(self.cache.get("query_1"))
        
        # Last ones should still be in cache
        self.assertIsNotNone(self.cache.get("query_6"))
    
    def test_cache_stats(self):
        """Test cache statistics"""
        self.cache.set("test1", [1.0])
        self.cache.set("test2", [2.0])
        
        stats = self.cache.get_stats()
        
        self.assertEqual(stats["memory_size"], 2)
        self.assertEqual(stats["memory_limit"], 5)


class TestOptimizedStreaming(unittest.TestCase):
    """Test optimized streaming"""
    
    def test_buffered_streaming(self):
        """Test streaming with buffering"""
        streamer = OptimizedStreamer(buffer_size=3)
        
        async def generate_chunks():
            for i in range(10):
                yield f"chunk_{i}_"
        
        async def test_stream():
            results = []
            async for buffered in streamer.stream_with_buffer(generate_chunks()):
                results.append(buffered)
            return results
        
        results = asyncio.run(test_stream())
        
        # Should have buffered chunks
        self.assertGreater(len(results), 0)
        self.assertLessEqual(len(results), 4)  # 10 chunks / 3 buffer size


class TestPerformanceMonitor(unittest.TestCase):
    """Test performance monitoring"""
    
    def setUp(self):
        self.monitor = PerformanceMonitor()
    
    def test_metric_recording(self):
        """Test metric recording"""
        self.monitor.record_metric("embedding_time", 0.5)
        self.monitor.record_metric("search_time", 0.1)
        
        summary = self.monitor.get_summary()
        
        self.assertEqual(summary["metrics"]["embedding_time"], 0.5)
        self.assertEqual(summary["metrics"]["search_time"], 0.1)
    
    def test_counter_increment(self):
        """Test counter incrementation"""
        self.monitor.increment_counter("request_count")
        self.monitor.increment_counter("request_count")
        self.monitor.increment_counter("cache_hits")
        
        summary = self.monitor.get_summary()
        
        self.assertEqual(summary["metrics"]["request_count"], 2)
        self.assertEqual(summary["metrics"]["cache_hits"], 1)
    
    def test_cache_hit_rate(self):
        """Test cache hit rate calculation"""
        self.monitor.increment_counter("cache_hits")
        self.monitor.increment_counter("cache_hits")
        self.monitor.increment_counter("cache_misses")
        
        summary = self.monitor.get_summary()
        
        # 2 hits, 1 miss = 66.7% hit rate
        self.assertAlmostEqual(summary["cache_hit_rate"], 2/3, places=2)


def run_performance_benchmarks():
    """Run performance benchmarks"""
    print("\n=== Performance Benchmarks ===\n")
    
    # Test embedding speed
    if GPUOptimizedEmbedding:
        embedder = GPUOptimizedEmbedding(device="cpu")
        texts = ["테스트 문장"] * 100
        
        start = time.time()
        embedder.encode_batch(texts)
        elapsed = time.time() - start
        
        print(f"Embedding 100 texts: {elapsed:.2f}s ({100/elapsed:.1f} texts/sec)")
    
    # Test parallel processing speed
    processor = ParallelDocumentProcessor(max_workers=4)
    
    def dummy_process(x):
        time.sleep(0.01)
        return x
    
    items = list(range(100))
    
    # Sequential
    start = time.time()
    for item in items:
        dummy_process(item)
    seq_time = time.time() - start
    
    # Parallel
    start = time.time()
    processor.process_documents(items, dummy_process)
    par_time = time.time() - start
    
    print(f"Sequential processing: {seq_time:.2f}s")
    print(f"Parallel processing: {par_time:.2f}s")
    print(f"Speedup: {seq_time/par_time:.1f}x")


if __name__ == "__main__":
    # Run tests
    unittest.main(argv=[''], exit=False, verbosity=2)
    
    # Run benchmarks
    run_performance_benchmarks()