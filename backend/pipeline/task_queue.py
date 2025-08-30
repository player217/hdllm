"""
진정한 비동기 작업 큐 시스템
Author: Claude Code
Date: 2025-01-27
Description: AsyncPipeline을 위한 실제 큐 기반 작업 처리 시스템
"""

import asyncio
import time
import logging
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

class TaskStatus(Enum):
    """작업 상태"""
    PENDING = "pending"
    PROCESSING = "processing" 
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class QueueTask:
    """큐 작업 데이터 클래스"""
    task_id: str
    task_type: str
    payload: Dict[str, Any]
    priority: int = 0
    created_at: float = field(default_factory=time.time)
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    @property
    def duration(self) -> Optional[float]:
        """작업 실행 시간 (초)"""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None

class TaskQueue:
    """진정한 비동기 작업 큐"""
    
    def __init__(self, max_workers: int = 5, max_queue_size: int = 1000):
        self.queue = asyncio.PriorityQueue(maxsize=max_queue_size)
        self.tasks: Dict[str, QueueTask] = {}
        self.max_workers = max_workers
        self.workers: List[asyncio.Task] = []
        self.running = False
        self.handlers: Dict[str, Callable] = {}
        
        # 통계
        self.stats = {
            "total_enqueued": 0,
            "total_completed": 0,
            "total_failed": 0,
            "total_cancelled": 0,
            "active_workers": 0,
            "queue_size": 0
        }
        
    def register_handler(self, task_type: str, handler: Callable):
        """작업 유형별 핸들러 등록"""
        self.handlers[task_type] = handler
        logger.info(f"📝 Handler registered for task type: {task_type}")
        
    async def enqueue(self, task: QueueTask) -> str:
        """작업을 큐에 추가 (진정한 큐잉)"""
        if task.task_id in self.tasks:
            raise ValueError(f"Task {task.task_id} already exists")
            
        try:
            # 우선순위가 높을수록 먼저 처리 (음수로 변환)
            priority_item = (-task.priority, task.created_at, task.task_id)
            self.queue.put_nowait(priority_item)
            
            self.tasks[task.task_id] = task
            self.stats["total_enqueued"] += 1
            self.stats["queue_size"] = self.queue.qsize()
            
            logger.info(f"📤 Task enqueued: {task.task_id} ({task.task_type}) [Queue: {self.queue.qsize()}]")
            return task.task_id
            
        except asyncio.QueueFull:
            raise ValueError(f"Queue is full (max size: {self.queue.maxsize})")
        
    async def get_task_status(self, task_id: str) -> Optional[QueueTask]:
        """작업 상태 조회"""
        return self.tasks.get(task_id)
        
    async def cancel_task(self, task_id: str) -> bool:
        """작업 취소 (대기 중인 작업만 가능)"""
        task = self.tasks.get(task_id)
        if not task:
            return False
            
        if task.status == TaskStatus.PENDING:
            task.status = TaskStatus.CANCELLED
            task.completed_at = time.time()
            self.stats["total_cancelled"] += 1
            logger.info(f"⏹️ Task cancelled: {task_id}")
            return True
            
        return False
        
    async def worker(self, worker_id: int):
        """워커 프로세스"""
        logger.info(f"🏃 Worker-{worker_id} started")
        self.stats["active_workers"] += 1
        
        while self.running:
            try:
                # 큐에서 작업 가져오기 (타임아웃 1초)
                try:
                    priority, created_at, task_id = await asyncio.wait_for(
                        self.queue.get(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                task = self.tasks.get(task_id)
                if not task or task.status != TaskStatus.PENDING:
                    continue
                    
                # 작업 시작
                task.status = TaskStatus.PROCESSING
                task.started_at = time.time()
                self.stats["queue_size"] = self.queue.qsize()
                
                logger.info(f"🔄 Worker-{worker_id} processing: {task_id} ({task.task_type})")
                
                # 핸들러 실행
                handler = self.handlers.get(task.task_type)
                if not handler:
                    raise ValueError(f"No handler for task type: {task.task_type}")
                
                try:
                    task.result = await handler(task.payload)
                    task.status = TaskStatus.COMPLETED
                    task.completed_at = time.time()
                    self.stats["total_completed"] += 1
                    
                    duration = task.duration or 0
                    logger.info(f"✅ Worker-{worker_id} completed: {task_id} ({duration:.3f}s)")
                    
                except Exception as handler_error:
                    task.error = str(handler_error)
                    task.status = TaskStatus.FAILED
                    task.completed_at = time.time()
                    self.stats["total_failed"] += 1
                    
                    logger.error(f"❌ Worker-{worker_id} task failed: {task_id} - {task.error}")
                    
            except Exception as worker_error:
                logger.error(f"❌ Worker-{worker_id} error: {worker_error}")
                # 워커는 계속 실행
                continue
                
        self.stats["active_workers"] -= 1
        logger.info(f"🛑 Worker-{worker_id} stopped")
        
    async def start(self):
        """큐 시스템 시작"""
        if self.running:
            logger.warning("TaskQueue is already running")
            return
            
        self.running = True
        self.workers = [
            asyncio.create_task(self.worker(i), name=f"TaskQueue-Worker-{i}")
            for i in range(self.max_workers)
        ]
        logger.info(f"🚀 TaskQueue started with {self.max_workers} workers")
        
    async def stop(self, timeout: float = 30.0):
        """큐 시스템 종료"""
        if not self.running:
            return
            
        logger.info("🛑 Stopping TaskQueue...")
        self.running = False
        
        # 워커 종료 대기
        try:
            await asyncio.wait_for(
                asyncio.gather(*self.workers, return_exceptions=True),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.warning("TaskQueue stop timeout, forcing worker cancellation")
            for worker in self.workers:
                if not worker.done():
                    worker.cancel()
        
        # 미완료 작업 정리
        pending_count = sum(1 for task in self.tasks.values() 
                          if task.status in [TaskStatus.PENDING, TaskStatus.PROCESSING])
        if pending_count > 0:
            logger.warning(f"TaskQueue stopped with {pending_count} pending/processing tasks")
        
        logger.info("✅ TaskQueue stopped successfully")
        
    def get_stats(self) -> Dict[str, Any]:
        """큐 통계 반환"""
        pending_count = sum(1 for task in self.tasks.values() if task.status == TaskStatus.PENDING)
        processing_count = sum(1 for task in self.tasks.values() if task.status == TaskStatus.PROCESSING)
        
        return {
            **self.stats,
            "pending_tasks": pending_count,
            "processing_tasks": processing_count,
            "total_tasks": len(self.tasks),
            "handlers_registered": len(self.handlers),
            "running": self.running,
            "max_workers": self.max_workers,
            "max_queue_size": self.queue.maxsize
        }
        
    async def cleanup_old_tasks(self, max_age_seconds: int = 3600):
        """오래된 작업 정리 (메모리 누수 방지)"""
        current_time = time.time()
        old_task_ids = []
        
        for task_id, task in self.tasks.items():
            if (task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED] and 
                current_time - task.created_at > max_age_seconds):
                old_task_ids.append(task_id)
        
        for task_id in old_task_ids:
            del self.tasks[task_id]
            
        if old_task_ids:
            logger.info(f"🧹 Cleaned up {len(old_task_ids)} old tasks")