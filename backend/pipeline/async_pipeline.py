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
from resource_manager import ResourceManager

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
        dlq_path: str = "data/dlq.jsonl",
        batch_size: int = DEFAULT_BATCH_SIZE,
        max_concurrent: int = 10
    ):
        """
        Initialize async pipeline
        
        Args:
            dlq_path: Path to DLQ file
            batch_size: Default batch size for processing
            max_concurrent: Maximum concurrent tasks
        """
        self.dlq = DeadLetterQueue(dlq_path)
        self.batch_size = min(batch_size, MAX_BATCH_SIZE)
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        
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
        
        logger.info(f"🚀 AsyncPipeline initialized with batch_size={batch_size}, max_concurrent={max_concurrent}")
    
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
        return {
            **self.stats,
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