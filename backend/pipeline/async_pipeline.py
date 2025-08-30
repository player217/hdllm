"""
Async Pipeline with Retry Logic and Dead Letter Queue
Author: Claude Code
Date: 2025-01-27
Description: Phase 2B-2 - Resilient async pipeline for document processing
"""

import asyncio
import time
import hashlib
import json
import logging
import traceback
from typing import Callable, Dict, Any, Optional, List, Union
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .dlq import DeadLetterQueue, DLQEntry
from .task_queue import TaskQueue, QueueTask, TaskStatus
from backend.resource_manager import ResourceManager

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRY = 3
BASE_BACKOFF = 0.2  # seconds
MAX_BACKOFF = 30    # seconds

# Batch processing configuration
DEFAULT_BATCH_SIZE = 256  # chunks per batch
MAX_BATCH_SIZE = 1024
TOKEN_LIMIT = 2048  # max tokens per batch


def is_transient_error(e: Exception) -> bool:
    """
    Determine if error is transient and retryable
    
    Args:
        e: Exception to check
        
    Returns:
        True if error is transient and should be retried
    """
    # Check for retryable attribute
    if hasattr(e, "retryable"):
        return e.retryable
    
    # Network errors
    if isinstance(e, (ConnectionError, TimeoutError, asyncio.TimeoutError)):
        return True
    
    # HTTP status codes (if available)
    if hasattr(e, "status_code"):
        return e.status_code in [408, 429, 500, 502, 503, 504]
    
    # Qdrant specific errors
    error_msg = str(e).lower()
    transient_patterns = [
        "timeout",
        "connection",
        "unavailable",
        "too many requests",
        "rate limit",
        "temporary",
        "retry"
    ]
    
    return any(pattern in error_msg for pattern in transient_patterns)


async def run_with_retry(
    task_fn: Callable,
    payload: Dict[str, Any],
    task_id: str,
    dlq: Optional[DeadLetterQueue] = None,
    max_retry: int = MAX_RETRY
) -> Optional[Any]:
    """
    Run task with exponential backoff retry logic
    
    Args:
        task_fn: Async function to execute
        payload: Task payload
        task_id: Unique task identifier
        dlq: Dead letter queue for failed tasks
        max_retry: Maximum retry attempts
        
    Returns:
        Task result or None if failed
    """
    attempt = 0
    last_error = None
    
    while attempt <= max_retry:
        try:
            # Log attempt
            if attempt > 0:
                logger.info(f"🔄 Retry attempt {attempt}/{max_retry} for task {task_id}")
            
            # Execute task
            result = await task_fn(payload)
            
            # Success
            if attempt > 0:
                logger.info(f"✅ Task {task_id} succeeded after {attempt} retries")
            
            return result
            
        except Exception as e:
            attempt += 1
            last_error = e
            error_type = type(e).__name__
            
            # Check if retryable
            if attempt <= max_retry and is_transient_error(e):
                # Calculate backoff with jitter
                backoff = min(
                    BASE_BACKOFF * (2 ** (attempt - 1)) + (asyncio.get_event_loop().time() % 1),
                    MAX_BACKOFF
                )
                
                logger.warning(f"⚠️ Transient error in task {task_id}: {e}. Retrying in {backoff:.1f}s...")
                await asyncio.sleep(backoff)
                continue
            
            # Non-retryable or max attempts reached
            logger.error(f"❌ Task {task_id} failed after {attempt} attempts: {e}")
            
            # Send to DLQ
            if dlq:
                dlq_entry = DLQEntry(
                    task_id=task_id,
                    payload=payload,
                    error=str(e),
                    attempt=attempt,
                    timestamp=time.time(),
                    error_type=error_type,
                    stack_trace=traceback.format_exc()
                )
                dlq.push(dlq_entry)
            
            # Re-raise if no DLQ
            if not dlq:
                raise
            
            return None


@dataclass
class PipelineTask:
    """Pipeline task definition"""
    task_id: str
    task_type: str  # embed, upsert, process
    payload: Dict[str, Any]
    priority: int = 0
    created_at: float = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()
    
    def generate_idempotent_id(self) -> str:
        """Generate idempotent task ID based on content"""
        if self.task_type == "document":
            # For documents: hash of path + size + mtime
            file_path = self.payload.get("file_path", "")
            file_size = self.payload.get("file_size", 0)
            file_mtime = self.payload.get("file_mtime", 0)
            content = f"{file_path}:{file_size}:{file_mtime}"
            return f"DOC:{hashlib.sha256(content.encode()).hexdigest()[:16]}"
        
        elif self.task_type == "chunk":
            # For chunks: hash of document_id + chunk_idx
            doc_id = self.payload.get("document_id", "")
            chunk_idx = self.payload.get("chunk_idx", 0)
            content = f"{doc_id}:{chunk_idx}"
            return f"CHUNK:{hashlib.sha256(content.encode()).hexdigest()[:16]}"
        
        return self.task_id


class AsyncPipeline:
    """
    Resilient async pipeline for document processing
    """
    
    def __init__(
        self,
        resource_manager: Optional[ResourceManager] = None,
        dlq_path: str = "data/dlq.jsonl",
        batch_size: int = DEFAULT_BATCH_SIZE,
        max_concurrent: int = 10,
        max_queue_size: int = 1000
    ):
        """
        Initialize async pipeline
        
        Args:
            resource_manager: ResourceManager instance for GPU acceleration
            dlq_path: Path to DLQ file
            batch_size: Default batch size for processing
            max_concurrent: Maximum concurrent tasks
            max_queue_size: Maximum queue size for TaskQueue
        """
        self.resource_manager = resource_manager
        self.dlq = DeadLetterQueue(dlq_path)
        self.batch_size = min(batch_size, MAX_BATCH_SIZE)
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        
        # Initialize TaskQueue
        self.task_queue = TaskQueue(max_workers=max_concurrent, max_queue_size=max_queue_size)
        
        # Register task handlers
        self._register_task_handlers()
        
        # Track processed tasks for idempotency
        self.processed_tasks = set()
        
        # Cancellation token
        self.cancel_event = asyncio.Event()
        
        # Statistics
        self.stats = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "retried_tasks": 0,
            "cancelled_tasks": 0,
            "dlq_tasks": 0
        }
        
        logger.info(f"🚀 AsyncPipeline initialized with batch_size={batch_size}, max_concurrent={max_concurrent}, queue_size={max_queue_size}")
    
    def _register_task_handlers(self):
        """작업 유형별 핸들러 등록"""
        self.task_queue.register_handler("search", self._handle_search_task)
        self.task_queue.register_handler("ingest", self._handle_ingest_task)
        self.task_queue.register_handler("batch_upsert", self._handle_batch_upsert_task)
        self.task_queue.register_handler("embed", self._handle_embed_task)
        self.task_queue.register_handler("replay", self._handle_replay_task)
    
    async def _handle_search_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """검색 작업 핸들러"""
        return await self.run_search(**payload)
    
    async def _handle_ingest_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """문서 수집 작업 핸들러 (향후 구현)"""
        # TODO: 문서 수집 로직 구현
        await asyncio.sleep(0.1)  # 임시
        return {"status": "ingested", "document_id": payload.get("document_id")}
    
    async def _handle_batch_upsert_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """배치 업서트 작업 핸들러 (향후 구현)"""
        # TODO: 배치 업서트 로직 구현
        await asyncio.sleep(0.1)  # 임시
        return {"status": "upserted", "vector_count": len(payload.get("vectors", []))}
    
    async def _handle_embed_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """임베딩 작업 핸들러"""
        if not self.resource_manager:
            raise ValueError("ResourceManager not available for embedding")
        
        texts = [payload.get("text", "")]
        embeddings = await self.resource_manager.embed_texts(texts)
        
        return {
            "embedding": embeddings[0],
            "document_id": payload.get("document_id"),
            "chunk_idx": payload.get("chunk_idx")
        }
    
    async def _handle_replay_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """DLQ 재실행 작업 핸들러"""
        # 기존 페이로드를 다시 실행
        original_task_type = payload.get("original_task_type", "search")
        if original_task_type in ["search", "ingest", "batch_upsert", "embed"]:
            handler = getattr(self, f"_handle_{original_task_type}_task")
            return await handler(payload)
        else:
            raise ValueError(f"Unknown task type for replay: {original_task_type}")
    
    async def start_queue(self):
        """큐 시스템 시작"""
        await self.task_queue.start()
        logger.info("🚀 TaskQueue started")
    
    async def stop_queue(self, timeout: float = 30.0):
        """큐 시스템 종료"""
        await self.task_queue.stop(timeout=timeout)
        logger.info("🛑 TaskQueue stopped")
    
    async def get_task_status(self, task_id: str) -> Optional[QueueTask]:
        """작업 상태 조회"""
        return await self.task_queue.get_task_status(task_id)
    
    async def cancel_task(self, task_id: str) -> bool:
        """작업 취소"""
        return await self.task_queue.cancel_task(task_id)
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """큐 통계 반환"""
        return self.task_queue.get_stats()
    
    async def process_batch(
        self,
        tasks: List[PipelineTask],
        process_fn: Callable
    ) -> Dict[str, Any]:
        """
        Process batch of tasks with concurrency control
        
        Args:
            tasks: List of tasks to process
            process_fn: Async function to process each task
            
        Returns:
            Processing results
        """
        results = {
            "success": [],
            "failed": [],
            "skipped": []
        }
        
        async def process_with_semaphore(task: PipelineTask):
            """Process single task with semaphore"""
            async with self.semaphore:
                # Check cancellation
                if self.cancel_event.is_set():
                    self.stats["cancelled_tasks"] += 1
                    results["skipped"].append(task.task_id)
                    return
                
                # Check idempotency
                idempotent_id = task.generate_idempotent_id()
                if idempotent_id in self.processed_tasks:
                    logger.debug(f"⏭️ Skipping duplicate task {idempotent_id}")
                    results["skipped"].append(task.task_id)
                    return
                
                # Process with retry
                try:
                    result = await run_with_retry(
                        task_fn=process_fn,
                        payload=task.payload,
                        task_id=task.task_id,
                        dlq=self.dlq
                    )
                    
                    if result is not None:
                        self.processed_tasks.add(idempotent_id)
                        self.stats["completed_tasks"] += 1
                        results["success"].append({
                            "task_id": task.task_id,
                            "result": result
                        })
                    else:
                        self.stats["failed_tasks"] += 1
                        self.stats["dlq_tasks"] += 1
                        results["failed"].append(task.task_id)
                        
                except Exception as e:
                    logger.error(f"Unexpected error processing task {task.task_id}: {e}")
                    self.stats["failed_tasks"] += 1
                    results["failed"].append(task.task_id)
        
        # Process tasks concurrently
        self.stats["total_tasks"] += len(tasks)
        await asyncio.gather(
            *[process_with_semaphore(task) for task in tasks],
            return_exceptions=True
        )
        
        return results
    
    async def process_documents(
        self,
        documents: List[Dict[str, Any]],
        embedding_fn: Callable,
        upsert_fn: Callable
    ) -> Dict[str, Any]:
        """
        Process documents through embedding and upsert pipeline
        
        Args:
            documents: List of document metadata
            embedding_fn: Function to generate embeddings
            upsert_fn: Function to upsert to vector store
            
        Returns:
            Processing results
        """
        all_results = {
            "documents_processed": 0,
            "chunks_processed": 0,
            "embeddings_generated": 0,
            "vectors_upserted": 0,
            "errors": []
        }
        
        for doc in documents:
            # Check cancellation
            if self.cancel_event.is_set():
                logger.info("⏹️ Pipeline cancelled")
                break
            
            try:
                # Create document task
                doc_task = PipelineTask(
                    task_id=f"doc_{doc.get('id', '')}_{int(time.time())}",
                    task_type="document",
                    payload=doc
                )
                
                # Process document chunks in batches
                chunks = doc.get("chunks", [])
                for i in range(0, len(chunks), self.batch_size):
                    batch = chunks[i:i + self.batch_size]
                    
                    # Generate embeddings
                    embed_tasks = [
                        PipelineTask(
                            task_id=f"embed_{doc.get('id')}_{j}",
                            task_type="chunk",
                            payload={
                                "document_id": doc.get("id"),
                                "chunk_idx": i + j,
                                "text": chunk["text"]
                            }
                        )
                        for j, chunk in enumerate(batch)
                    ]
                    
                    embed_results = await self.process_batch(embed_tasks, embedding_fn)
                    all_results["embeddings_generated"] += len(embed_results["success"])
                    
                    # Prepare vectors for upsert
                    if embed_results["success"]:
                        vectors = []
                        for result in embed_results["success"]:
                            if result["result"]:
                                vectors.append(result["result"])
                        
                        # Upsert vectors
                        if vectors:
                            upsert_task = PipelineTask(
                                task_id=f"upsert_{doc.get('id')}_{i}",
                                task_type="upsert",
                                payload={
                                    "document_id": doc.get("id"),
                                    "vectors": vectors
                                }
                            )
                            
                            upsert_result = await run_with_retry(
                                task_fn=upsert_fn,
                                payload=upsert_task.payload,
                                task_id=upsert_task.task_id,
                                dlq=self.dlq
                            )
                            
                            if upsert_result:
                                all_results["vectors_upserted"] += len(vectors)
                    
                    all_results["chunks_processed"] += len(batch)
                
                all_results["documents_processed"] += 1
                
            except Exception as e:
                logger.error(f"Error processing document {doc.get('id')}: {e}")
                all_results["errors"].append({
                    "document_id": doc.get("id"),
                    "error": str(e)
                })
        
        return all_results
    
    def cancel(self):
        """Cancel pipeline processing"""
        self.cancel_event.set()
        logger.info("🛑 Pipeline cancellation requested")
    
    def reset_cancel(self):
        """Reset cancellation token"""
        self.cancel_event.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pipeline statistics"""
        queue_stats = self.get_queue_stats()
        
        return {
            **self.stats,
            "queue_stats": queue_stats,
            "dlq_stats": self.dlq.get_stats(),
            "processed_tasks_count": len(self.processed_tasks)
        }
    
    async def replay_dlq(
        self,
        process_fn: Callable,
        count: int = 10,
        task_type_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Replay failed tasks from DLQ
        
        Args:
            process_fn: Function to process tasks
            count: Number of tasks to replay
            task_type_filter: Filter by task type
            
        Returns:
            Replay results
        """
        # Get tasks from DLQ
        dlq_entries = self.dlq.filter_entries(task_type=task_type_filter)[:count]
        
        if not dlq_entries:
            logger.info("📭 No tasks to replay from DLQ")
            return {"replayed": 0, "success": 0, "failed": 0}
        
        # Convert to pipeline tasks
        tasks = []
        for entry in dlq_entries:
            tasks.append(PipelineTask(
                task_id=f"replay_{entry.task_id}_{int(time.time())}",
                task_type="replay",
                payload=entry.payload
            ))
        
        # Process tasks
        results = await self.process_batch(tasks, process_fn)
        
        # Remove successfully replayed tasks from DLQ
        success_count = len(results["success"])
        if success_count > 0:
            # Pop the replayed entries
            self.dlq.pop(success_count)
        
        return {
            "replayed": len(tasks),
            "success": success_count,
            "failed": len(results["failed"])
        }
    
    async def run_search(
        self,
        query: str,
        source_type: str = "mail",
        limit: int = 10,
        score_threshold: float = 0.3
    ) -> Dict[str, Any]:
        """
        GPU 가속 검색 실행 (ResourceManager 통합)
        
        Args:
            query: 검색 쿼리
            source_type: 소스 타입 ('mail' or 'doc')
            limit: 결과 제한
            score_threshold: 유사도 임계값
            
        Returns:
            검색 결과 및 메타데이터
        """
        if not self.resource_manager:
            raise ValueError("ResourceManager not available for GPU acceleration")
        
        try:
            start_time = time.time()
            
            # GPU 가속 임베딩 생성
            logger.info(f"🔍 Generating embeddings for query: {query[:50]}...")
            query_embeddings = await self.resource_manager.embed_texts([query])
            query_vector = query_embeddings[0]
            
            embed_time = time.time() - start_time
            logger.info(f"⚡ GPU embedding generated in {embed_time:.3f}s")
            
            # 벡터 검색
            search_start = time.time()
            
            results = await self.resource_manager.search_vectors(
                source_type=source_type,
                query_vector=query_vector,
                limit=limit,
                score_threshold=score_threshold,
                with_payload=True,
                with_vectors=False
            )
            
            search_time = time.time() - search_start
            total_time = time.time() - start_time
            
            logger.info(f"🎯 Search completed: {len(results)} results in {search_time:.3f}s (total: {total_time:.3f}s)")
            
            return {
                "query": query,
                "results": results,
                "metadata": {
                    "source_type": source_type,
                    "result_count": len(results),
                    "embed_time_ms": round(embed_time * 1000, 2),
                    "search_time_ms": round(search_time * 1000, 2),
                    "total_time_ms": round(total_time * 1000, 2),
                    "device": self.resource_manager.embed_device,
                    "backend": self.resource_manager.embed_backend
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Search failed: {e}")
            self.stats["failed_tasks"] += 1
            raise
    
    async def enqueue(
        self, 
        task_type: str,
        payload: Dict[str, Any],
        priority: int = 0
    ) -> str:
        """
        비동기 작업 큐에 작업 추가 (진정한 큐잉)
        
        Args:
            task_type: 작업 타입 ('search', 'ingest', 'batch_upsert', 'embed')
            payload: 작업 데이터
            priority: 작업 우선순위 (높을수록 우선)
            
        Returns:
            작업 ID
        """
        # QueueTask 생성
        queue_task = QueueTask(
            task_id=f"{task_type}_{int(time.time()*1000)}",
            task_type=task_type,
            payload=payload,
            priority=priority
        )
        
        try:
            # TaskQueue에 작업 추가
            task_id = await self.task_queue.enqueue(queue_task)
            logger.info(f"📤 Task enqueued: {task_id} ({task_type}) [Priority: {priority}]")
            
            # 통계 업데이트
            self.stats["total_tasks"] += 1
            
            return task_id
            
        except Exception as e:
            logger.error(f"❌ Failed to enqueue task: {e}")
            
            # DLQ에 추가 (큐 오류 시)
            dlq_entry = DLQEntry(
                task_id=queue_task.task_id,
                payload=payload,
                error=str(e),
                attempt=0,
                timestamp=time.time(),
                error_type=type(e).__name__,
                stack_trace=traceback.format_exc()
            )
            self.dlq.push(dlq_entry)
            self.stats["dlq_tasks"] += 1
            
            raise ValueError(f"Queue is full or unavailable: {e}")
    
    async def enqueue_batch(
        self,
        tasks: List[Dict[str, Any]],
        default_priority: int = 0
    ) -> List[str]:
        """
        여러 작업을 배치로 큐에 추가
        
        Args:
            tasks: 작업 목록 [{"task_type": str, "payload": dict, "priority": int}]
            default_priority: 기본 우선순위
            
        Returns:
            작업 ID 목록
        """
        task_ids = []
        
        for task_info in tasks:
            task_type = task_info["task_type"]
            payload = task_info["payload"]
            priority = task_info.get("priority", default_priority)
            
            try:
                task_id = await self.enqueue(task_type, payload, priority)
                task_ids.append(task_id)
            except Exception as e:
                logger.error(f"Failed to enqueue batch task {task_type}: {e}")
                # 실패한 작업은 None으로 표시
                task_ids.append(None)
        
        logger.info(f"📦 Batch enqueued: {len(task_ids)} tasks, {sum(1 for t in task_ids if t)} successful")
        return task_ids