"""
Qdrant Batch Operations and HNSW Optimization
Author: Claude Code
Date: 2025-01-27
Description: Phase 2B-2 - Efficient batch operations and HNSW parameter tuning
"""

import asyncio
import time
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import (
    PointStruct,
    VectorParams,
    Distance,
    OptimizersConfigDiff,
    HnswConfigDiff,
    CollectionStatus,
    UpdateStatus,
    Filter,
    FieldCondition,
    MatchValue,
    SearchParams,
    QuantizationConfig,
    ScalarQuantization,
    ScalarType,
    CompressionRatio
)
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from resource_manager import ResourceManager

logger = logging.getLogger(__name__)


class HNSWProfile(Enum):
    """HNSW parameter profiles for different use cases"""
    ACCURACY = "accuracy"      # High accuracy, slower
    BALANCED = "balanced"       # Balanced performance
    SPEED = "speed"            # Fast search, lower accuracy
    MEMORY = "memory"          # Memory optimized


@dataclass
class HNSWConfig:
    """HNSW configuration parameters"""
    m: int = 16                    # Number of edges per node
    ef_construct: int = 200        # Size of dynamic candidate list
    ef_search: int = 100          # Search time parameter
    full_scan_threshold: int = 10000
    max_payload_size: int = 2000000  # 2MB
    
    @classmethod
    def from_profile(cls, profile: HNSWProfile) -> 'HNSWConfig':
        """Create config from predefined profile"""
        configs = {
            HNSWProfile.ACCURACY: cls(
                m=32,
                ef_construct=400,
                ef_search=200,
                full_scan_threshold=20000
            ),
            HNSWProfile.BALANCED: cls(
                m=16,
                ef_construct=200,
                ef_search=100,
                full_scan_threshold=10000
            ),
            HNSWProfile.SPEED: cls(
                m=8,
                ef_construct=100,
                ef_search=50,
                full_scan_threshold=5000
            ),
            HNSWProfile.MEMORY: cls(
                m=4,
                ef_construct=100,
                ef_search=50,
                full_scan_threshold=5000,
                max_payload_size=1000000  # 1MB
            )
        }
        return configs[profile]


@dataclass
class BatchUploadResult:
    """Result of batch upload operation"""
    success_count: int
    failed_count: int
    total_time: float
    vectors_per_second: float
    failed_ids: List[str]
    error_messages: Dict[str, str]


class QdrantBatchProcessor:
    """
    Efficient batch processor for Qdrant operations
    Handles chunking, retries, and parallel uploads
    """
    
    def __init__(
        self,
        client: QdrantClient,
        collection_name: str,
        batch_size: int = 100,
        max_retries: int = 3,
        parallel_batches: int = 3
    ):
        """
        Initialize batch processor
        
        Args:
            client: Qdrant client instance
            collection_name: Target collection name
            batch_size: Vectors per batch
            max_retries: Maximum retry attempts
            parallel_batches: Number of parallel upload tasks
        """
        self.client = client
        self.collection_name = collection_name
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.parallel_batches = parallel_batches
        self.semaphore = asyncio.Semaphore(parallel_batches)
        
        # Statistics
        self.stats = {
            "total_uploaded": 0,
            "total_failed": 0,
            "total_time": 0,
            "batch_times": []
        }
    
    async def upload_batch(
        self,
        vectors: List[List[float]],
        payloads: List[Dict[str, Any]],
        ids: Optional[List[str]] = None
    ) -> BatchUploadResult:
        """
        Upload vectors in optimized batches
        
        Args:
            vectors: List of embedding vectors
            payloads: List of payload dictionaries
            ids: Optional list of IDs
            
        Returns:
            BatchUploadResult with statistics
        """
        if len(vectors) != len(payloads):
            raise ValueError("Vectors and payloads must have same length")
        
        # Generate IDs if not provided
        if ids is None:
            ids = [str(i) for i in range(len(vectors))]
        
        # Split into batches
        batches = self._create_batches(vectors, payloads, ids)
        
        # Upload batches with concurrency control
        start_time = time.time()
        results = await self._upload_batches_parallel(batches)
        total_time = time.time() - start_time
        
        # Aggregate results
        success_count = sum(r["success"] for r in results)
        failed_count = sum(r["failed"] for r in results)
        failed_ids = []
        error_messages = {}
        
        for result in results:
            failed_ids.extend(result.get("failed_ids", []))
            error_messages.update(result.get("errors", {}))
        
        # Calculate throughput
        vectors_per_second = success_count / total_time if total_time > 0 else 0
        
        # Update statistics
        self.stats["total_uploaded"] += success_count
        self.stats["total_failed"] += failed_count
        self.stats["total_time"] += total_time
        
        logger.info(f"✅ Batch upload complete: {success_count} success, {failed_count} failed, {vectors_per_second:.1f} vec/s")
        
        return BatchUploadResult(
            success_count=success_count,
            failed_count=failed_count,
            total_time=total_time,
            vectors_per_second=vectors_per_second,
            failed_ids=failed_ids,
            error_messages=error_messages
        )
    
    def _create_batches(
        self,
        vectors: List[List[float]],
        payloads: List[Dict[str, Any]],
        ids: List[str]
    ) -> List[Dict[str, Any]]:
        """Create batches for upload"""
        batches = []
        
        for i in range(0, len(vectors), self.batch_size):
            batch_end = min(i + self.batch_size, len(vectors))
            
            # Create point structs
            points = []
            for j in range(i, batch_end):
                point = PointStruct(
                    id=ids[j],
                    vector=vectors[j],
                    payload=payloads[j]
                )
                points.append(point)
            
            batches.append({
                "points": points,
                "start_idx": i,
                "end_idx": batch_end
            })
        
        return batches
    
    async def _upload_batches_parallel(self, batches: List[Dict]) -> List[Dict]:
        """Upload batches in parallel with semaphore control"""
        tasks = []
        
        for batch in batches:
            task = self._upload_single_batch_with_retry(batch)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # Batch failed completely
                batch = batches[i]
                batch_size = batch["end_idx"] - batch["start_idx"]
                processed_results.append({
                    "success": 0,
                    "failed": batch_size,
                    "failed_ids": [p.id for p in batch["points"]],
                    "errors": {p.id: str(result) for p in batch["points"]}
                })
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def _upload_single_batch_with_retry(self, batch: Dict) -> Dict:
        """Upload single batch with retry logic"""
        async with self.semaphore:
            points = batch["points"]
            
            for attempt in range(self.max_retries):
                try:
                    # Measure batch upload time
                    start = time.time()
                    
                    # Upload to Qdrant
                    operation_info = self.client.upsert(
                        collection_name=self.collection_name,
                        points=points,
                        wait=True
                    )
                    
                    batch_time = time.time() - start
                    self.stats["batch_times"].append(batch_time)
                    
                    # Check status
                    if operation_info.status == UpdateStatus.COMPLETED:
                        return {
                            "success": len(points),
                            "failed": 0,
                            "failed_ids": [],
                            "errors": {}
                        }
                    
                except Exception as e:
                    if attempt < self.max_retries - 1:
                        wait_time = 2 ** attempt
                        logger.warning(f"⚠️ Batch upload failed (attempt {attempt + 1}): {e}. Retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"❌ Batch upload failed after {self.max_retries} attempts: {e}")
                        raise
            
            # Should not reach here
            return {
                "success": 0,
                "failed": len(points),
                "failed_ids": [p.id for p in points],
                "errors": {p.id: "Max retries exceeded" for p in points}
            }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get upload statistics"""
        avg_batch_time = np.mean(self.stats["batch_times"]) if self.stats["batch_times"] else 0
        
        return {
            "total_uploaded": self.stats["total_uploaded"],
            "total_failed": self.stats["total_failed"],
            "total_time": self.stats["total_time"],
            "avg_batch_time": avg_batch_time,
            "avg_vectors_per_second": self.stats["total_uploaded"] / self.stats["total_time"] if self.stats["total_time"] > 0 else 0,
            "batch_count": len(self.stats["batch_times"])
        }


class HNSWOptimizer:
    """
    HNSW parameter optimizer with experimental profiles
    """
    
    def __init__(self, client: QdrantClient):
        """
        Initialize HNSW optimizer
        
        Args:
            client: Qdrant client instance
        """
        self.client = client
        self.test_results = []
    
    async def optimize_collection(
        self,
        collection_name: str,
        profile: HNSWProfile = HNSWProfile.BALANCED
    ) -> Dict[str, Any]:
        """
        Optimize collection with HNSW profile
        
        Args:
            collection_name: Collection to optimize
            profile: HNSW profile to apply
            
        Returns:
            Optimization results
        """
        config = HNSWConfig.from_profile(profile)
        
        logger.info(f"🔧 Optimizing collection '{collection_name}' with profile: {profile.value}")
        
        # Update HNSW config
        self.client.update_collection(
            collection_name=collection_name,
            hnsw_config=HnswConfigDiff(
                m=config.m,
                ef_construct=config.ef_construct,
                full_scan_threshold=config.full_scan_threshold,
                max_payload_size=config.max_payload_size
            ),
            optimizers_config=OptimizersConfigDiff(
                indexing_threshold=20000,
                deleted_threshold=0.2,
                vacuum_min_vector_number=1000,
                default_segment_number=5
            )
        )
        
        # Set search parameters
        search_params = SearchParams(
            hnsw_ef=config.ef_search,
            exact=False
        )
        
        return {
            "collection": collection_name,
            "profile": profile.value,
            "config": {
                "m": config.m,
                "ef_construct": config.ef_construct,
                "ef_search": config.ef_search,
                "full_scan_threshold": config.full_scan_threshold
            },
            "search_params": {
                "hnsw_ef": config.ef_search,
                "exact": False
            }
        }
    
    async def run_experiment(
        self,
        collection_name: str,
        test_vectors: List[List[float]],
        profiles: List[HNSWProfile] = None
    ) -> Dict[str, Any]:
        """
        Run HNSW parameter experiment
        
        Args:
            collection_name: Collection to test
            test_vectors: Vectors for testing
            profiles: Profiles to test (default: all)
            
        Returns:
            Experiment results
        """
        if profiles is None:
            profiles = list(HNSWProfile)
        
        results = {}
        
        for profile in profiles:
            logger.info(f"📊 Testing profile: {profile.value}")
            
            # Apply profile
            await self.optimize_collection(collection_name, profile)
            
            # Wait for indexing
            await asyncio.sleep(2)
            
            # Run search tests
            search_times = []
            for vector in test_vectors[:10]:  # Test with 10 vectors
                start = time.time()
                
                self.client.search(
                    collection_name=collection_name,
                    query_vector=vector,
                    limit=10
                )
                
                search_time = time.time() - start
                search_times.append(search_time)
            
            # Calculate metrics
            avg_time = np.mean(search_times)
            p95_time = np.percentile(search_times, 95)
            p99_time = np.percentile(search_times, 99)
            
            results[profile.value] = {
                "avg_search_time": avg_time,
                "p95_search_time": p95_time,
                "p99_search_time": p99_time,
                "min_search_time": min(search_times),
                "max_search_time": max(search_times)
            }
            
            logger.info(f"  Avg: {avg_time*1000:.2f}ms, P95: {p95_time*1000:.2f}ms")
        
        # Store results
        self.test_results.append({
            "timestamp": time.time(),
            "collection": collection_name,
            "results": results
        })
        
        return results
    
    def get_best_profile(self, metric: str = "avg_search_time") -> Tuple[HNSWProfile, Dict]:
        """
        Get best profile based on metric
        
        Args:
            metric: Metric to optimize for
            
        Returns:
            Best profile and its results
        """
        if not self.test_results:
            return None, {}
        
        latest_result = self.test_results[-1]["results"]
        
        best_profile = None
        best_value = float('inf')
        
        for profile_name, metrics in latest_result.items():
            if metrics[metric] < best_value:
                best_value = metrics[metric]
                best_profile = HNSWProfile(profile_name)
        
        return best_profile, latest_result[best_profile.value]


class CollectionManager:
    """
    Advanced collection management with security and optimization
    """
    
    def __init__(self, client: QdrantClient, resource_manager: ResourceManager):
        """
        Initialize collection manager
        
        Args:
            client: Qdrant client
            resource_manager: Resource manager for security
        """
        self.client = client
        self.resource_manager = resource_manager
        self.batch_processor = None
        self.hnsw_optimizer = HNSWOptimizer(client)
    
    async def create_secure_collection(
        self,
        namespace: str,
        collection_name: str,
        vector_size: int = 1024,
        distance: Distance = Distance.COSINE,
        profile: HNSWProfile = HNSWProfile.BALANCED,
        enable_quantization: bool = False
    ) -> Dict[str, Any]:
        """
        Create collection with security namespace and optimization
        
        Args:
            namespace: Security namespace (e.g., 'dept_tech', 'project_x')
            collection_name: Base collection name
            vector_size: Dimension of vectors
            distance: Distance metric
            profile: HNSW profile
            enable_quantization: Enable scalar quantization for memory optimization
            
        Returns:
            Collection creation result
        """
        # Apply security namespace
        full_collection_name = f"{namespace}_{collection_name}"
        
        # Get HNSW config
        hnsw_config = HNSWConfig.from_profile(profile)
        
        # Prepare vector config
        vector_config = VectorParams(
            size=vector_size,
            distance=distance,
            hnsw_config={
                "m": hnsw_config.m,
                "ef_construct": hnsw_config.ef_construct,
                "full_scan_threshold": hnsw_config.full_scan_threshold
            }
        )
        
        # Add quantization if enabled
        quantization_config = None
        if enable_quantization:
            quantization_config = ScalarQuantization(
                type="int8",
                quantile=0.99,
                always_ram=True
            )
        
        # Create collection
        self.client.create_collection(
            collection_name=full_collection_name,
            vectors_config=vector_config,
            optimizers_config={
                "deleted_threshold": 0.2,
                "vacuum_min_vector_number": 1000,
                "default_segment_number": 5,
                "indexing_threshold": 20000
            },
            quantization_config=quantization_config
        )
        
        # Initialize batch processor for this collection
        self.batch_processor = QdrantBatchProcessor(
            client=self.client,
            collection_name=full_collection_name,
            batch_size=100,
            parallel_batches=3
        )
        
        logger.info(f"🔐 Created secure collection: {full_collection_name} with {profile.value} profile")
        
        return {
            "collection": full_collection_name,
            "namespace": namespace,
            "vector_size": vector_size,
            "distance": distance.value,
            "profile": profile.value,
            "quantization": enable_quantization
        }
    
    async def batch_upsert_with_security(
        self,
        namespace: str,
        collection_name: str,
        vectors: List[List[float]],
        payloads: List[Dict[str, Any]],
        department: str = None
    ) -> BatchUploadResult:
        """
        Batch upsert with security tagging
        
        Args:
            namespace: Security namespace
            collection_name: Collection name
            vectors: Embedding vectors
            payloads: Payload data
            department: Department tag for access control
            
        Returns:
            Batch upload result
        """
        full_collection_name = f"{namespace}_{collection_name}"
        
        # Add security metadata to payloads
        secured_payloads = []
        for payload in payloads:
            secured_payload = {
                **payload,
                "_namespace": namespace,
                "_indexed_at": time.time(),
                "_department": department or "general"
            }
            secured_payloads.append(secured_payload)
        
        # Use batch processor
        if not self.batch_processor or self.batch_processor.collection_name != full_collection_name:
            self.batch_processor = QdrantBatchProcessor(
                client=self.client,
                collection_name=full_collection_name
            )
        
        return await self.batch_processor.upload_batch(
            vectors=vectors,
            payloads=secured_payloads
        )
    
    async def search_with_security_filter(
        self,
        namespace: str,
        collection_name: str,
        query_vector: List[float],
        department: str = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search with security filtering
        
        Args:
            namespace: Security namespace
            collection_name: Collection name
            query_vector: Query embedding
            department: Department filter
            limit: Result limit
            
        Returns:
            Filtered search results
        """
        full_collection_name = f"{namespace}_{collection_name}"
        
        # Build security filter
        must_conditions = [
            FieldCondition(
                key="_namespace",
                match=MatchValue(value=namespace)
            )
        ]
        
        if department:
            must_conditions.append(
                FieldCondition(
                    key="_department",
                    match=MatchValue(value=department)
                )
            )
        
        filter_condition = Filter(
            must=must_conditions
        )
        
        # Search with filter
        results = self.client.search(
            collection_name=full_collection_name,
            query_vector=query_vector,
            query_filter=filter_condition,
            limit=limit,
            with_payload=True
        )
        
        return [
            {
                "id": r.id,
                "score": r.score,
                "payload": r.payload
            }
            for r in results
        ]
    
    def get_collection_stats(self, namespace: str, collection_name: str) -> Dict[str, Any]:
        """Get collection statistics with security info"""
        full_collection_name = f"{namespace}_{collection_name}"
        
        info = self.client.get_collection(collection_name=full_collection_name)
        
        return {
            "collection": full_collection_name,
            "namespace": namespace,
            "vectors_count": info.vectors_count,
            "indexed_vectors_count": info.indexed_vectors_count,
            "points_count": info.points_count,
            "segments_count": info.segments_count,
            "status": info.status,
            "config": info.config
        }


# Example usage
if __name__ == "__main__":
    async def test_batch_operations():
        # Initialize clients
        client = QdrantClient(host="localhost", port=6333)
        resource_manager = ResourceManager()
        
        # Create collection manager
        manager = CollectionManager(client, resource_manager)
        
        # Create secure collection
        result = await manager.create_secure_collection(
            namespace="dept_tech",
            collection_name="documents",
            vector_size=1024,
            profile=HNSWProfile.BALANCED,
            enable_quantization=True
        )
        print(f"Collection created: {result}")
        
        # Generate test data
        vectors = np.random.rand(1000, 1024).tolist()
        payloads = [
            {"text": f"Document {i}", "doc_id": i}
            for i in range(1000)
        ]
        
        # Batch upload
        upload_result = await manager.batch_upsert_with_security(
            namespace="dept_tech",
            collection_name="documents",
            vectors=vectors,
            payloads=payloads,
            department="선각기술부"
        )
        
        print(f"Upload complete: {upload_result.success_count} vectors in {upload_result.total_time:.2f}s")
        print(f"Throughput: {upload_result.vectors_per_second:.1f} vectors/second")
        
        # Run HNSW optimization experiment
        optimizer = HNSWOptimizer(client)
        experiment_results = await optimizer.run_experiment(
            collection_name="dept_tech_documents",
            test_vectors=vectors[:100]
        )
        
        print("\nHNSW Experiment Results:")
        for profile, metrics in experiment_results.items():
            print(f"  {profile}: avg={metrics['avg_search_time']*1000:.2f}ms, p95={metrics['p95_search_time']*1000:.2f}ms")
        
        # Get best profile
        best_profile, best_metrics = optimizer.get_best_profile()
        print(f"\nBest profile: {best_profile.value} with avg search time: {best_metrics['avg_search_time']*1000:.2f}ms")
    
    # Run test
    asyncio.run(test_batch_operations())