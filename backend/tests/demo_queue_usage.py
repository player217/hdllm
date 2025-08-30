"""
큐 시스템 사용법 데모 스크립트
Author: Claude Code
Date: 2025-01-27
Description: 새로운 TaskQueue 기반 시스템 사용법 시연
"""

import asyncio
import time
import logging
import sys
import os
from pathlib import Path

# 상위 디렉토리 경로 추가
sys.path.append(str(Path(__file__).parent.parent))

from backend.resource_manager import ResourceManager
from backend.pipeline.async_pipeline import AsyncPipeline
from backend.pipeline.task_queue import TaskQueue, QueueTask, TaskStatus

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)

class QueueSystemDemo:
    """큐 시스템 사용법 데모"""
    
    def __init__(self):
        self.resource_manager = None
        self.pipeline = None
    
    async def setup(self):
        """데모 환경 설정"""
        logger.info("🔧 Setting up demo environment...")
        
        # ResourceManager 초기화
        self.resource_manager = ResourceManager()
        await self.resource_manager.initialize()
        
        # AsyncPipeline 초기화 (작은 큐 사이즈로 데모)
        self.pipeline = AsyncPipeline(
            resource_manager=self.resource_manager,
            max_concurrent=2,  # 작업자 2명
            max_queue_size=10  # 큐 크기 10
        )
        
        # 큐 시스템 시작
        await self.pipeline.start_queue()
        
        logger.info("✅ Demo environment ready!")
    
    async def cleanup(self):
        """환경 정리"""
        logger.info("🧹 Cleaning up...")
        
        if self.pipeline:
            await self.pipeline.stop_queue()
        
        if self.resource_manager:
            await self.resource_manager.cleanup()
        
        logger.info("✅ Cleanup complete!")
    
    async def demo_basic_queueing(self):
        """기본 큐잉 데모"""
        logger.info("\n" + "="*50)
        logger.info("📤 DEMO 1: Basic Task Queueing")
        logger.info("="*50)
        
        # 1. 검색 작업들을 큐에 추가
        search_queries = [
            "GPU 가속이란 무엇인가요?",
            "벡터 데이터베이스 사용법",
            "임베딩 모델 성능 최적화",
            "비동기 처리 장점"
        ]
        
        logger.info(f"📝 Adding {len(search_queries)} search tasks to queue...")
        
        task_ids = []
        for i, query in enumerate(search_queries):
            payload = {
                "query": query,
                "source_type": "mail",
                "limit": 3,
                "score_threshold": 0.3
            }
            
            # 우선순위 설정 (높은 숫자 = 높은 우선순위)
            priority = len(search_queries) - i  # 첫 번째가 가장 높은 우선순위
            
            task_id = await self.pipeline.enqueue("search", payload, priority=priority)
            task_ids.append(task_id)
            
            logger.info(f"  📤 Task {i+1}: {task_id} (priority: {priority})")
        
        # 2. 큐 상태 모니터링
        logger.info("\n📊 Monitoring queue progress...")
        
        for _ in range(15):  # 최대 30초 모니터링
            stats = self.pipeline.get_queue_stats()
            logger.info(f"  Queue: {stats.get('pending_tasks', 0)} pending, "
                       f"{stats.get('processing_tasks', 0)} processing, "
                       f"{stats.get('total_completed', 0)} completed")
            
            if stats.get('pending_tasks', 0) == 0 and stats.get('processing_tasks', 0) == 0:
                break
            
            await asyncio.sleep(2)
        
        logger.info("✅ Basic queueing demo completed!")
        return task_ids
    
    async def demo_priority_queueing(self):
        """우선순위 큐잉 데모"""
        logger.info("\n" + "="*50)
        logger.info("⚡ DEMO 2: Priority-Based Queueing")
        logger.info("="*50)
        
        # 다양한 우선순위의 작업들
        tasks_with_priority = [
            {"type": "search", "query": "긴급 질문", "priority": 10},
            {"type": "embed", "text": "일반 임베딩", "priority": 1},
            {"type": "search", "query": "중요한 질문", "priority": 5},
            {"type": "embed", "text": "긴급 임베딩", "priority": 8},
            {"type": "search", "query": "일반 질문", "priority": 1}
        ]
        
        logger.info("📝 Adding tasks with different priorities...")
        
        for i, task in enumerate(tasks_with_priority):
            if task["type"] == "search":
                payload = {
                    "query": task["query"],
                    "source_type": "mail",
                    "limit": 2
                }
            else:  # embed
                payload = {
                    "text": task["text"],
                    "document_id": f"demo_doc_{i}",
                    "chunk_idx": 0
                }
            
            task_id = await self.pipeline.enqueue(task["type"], payload, priority=task["priority"])
            logger.info(f"  📤 {task['type']}: {task_id} (priority: {task['priority']})")
            
            # 작은 지연으로 큐에 순서대로 들어가도록
            await asyncio.sleep(0.1)
        
        # 큐 처리 모니터링
        logger.info("\n📊 Priority processing order:")
        
        start_time = time.time()
        while time.time() - start_time < 30:  # 30초 제한
            stats = self.pipeline.get_queue_stats()
            
            if stats.get('pending_tasks', 0) == 0 and stats.get('processing_tasks', 0) == 0:
                break
            
            await asyncio.sleep(2)
        
        logger.info("✅ Priority queueing demo completed!")
    
    async def demo_batch_operations(self):
        """배치 작업 데모"""
        logger.info("\n" + "="*50)
        logger.info("📦 DEMO 3: Batch Operations")
        logger.info("="*50)
        
        # 배치 작업 정의
        batch_tasks = [
            {
                "task_type": "embed",
                "payload": {
                    "text": f"배치 텍스트 {i+1}",
                    "document_id": f"batch_doc_{i+1}",
                    "chunk_idx": i
                },
                "priority": 2
            }
            for i in range(5)
        ]
        
        # 검색 작업들도 추가
        batch_tasks.extend([
            {
                "task_type": "search",
                "payload": {
                    "query": f"배치 검색 {i+1}",
                    "source_type": "mail",
                    "limit": 2
                },
                "priority": 3
            }
            for i in range(3)
        ])
        
        logger.info(f"📝 Adding batch of {len(batch_tasks)} tasks...")
        
        # 배치로 큐에 추가
        task_ids = await self.pipeline.enqueue_batch(batch_tasks, default_priority=1)
        
        successful_tasks = [tid for tid in task_ids if tid is not None]
        logger.info(f"  📤 Successfully enqueued: {len(successful_tasks)}/{len(batch_tasks)} tasks")
        
        # 처리 진행 모니터링
        logger.info("\n📊 Batch processing progress:")
        
        start_time = time.time()
        last_completed = 0
        
        while time.time() - start_time < 45:  # 45초 제한
            stats = self.pipeline.get_queue_stats()
            completed = stats.get('total_completed', 0)
            
            if completed > last_completed:
                logger.info(f"  Progress: {completed} tasks completed")
                last_completed = completed
            
            if stats.get('pending_tasks', 0) == 0 and stats.get('processing_tasks', 0) == 0:
                break
            
            await asyncio.sleep(3)
        
        logger.info("✅ Batch operations demo completed!")
    
    async def demo_task_monitoring(self):
        """작업 모니터링 데모"""
        logger.info("\n" + "="*50)
        logger.info("👀 DEMO 4: Task Monitoring & Management")
        logger.info("="*50)
        
        # 장시간 작업 시뮬레이션을 위한 검색 작업
        task_id = await self.pipeline.enqueue("search", {
            "query": "모니터링 테스트 질문",
            "source_type": "mail",
            "limit": 5
        }, priority=1)
        
        logger.info(f"📤 Monitoring task: {task_id}")
        
        # 작업 상태 추적
        for i in range(10):
            task_status = await self.pipeline.get_task_status(task_id)
            
            if task_status:
                logger.info(f"  Status: {task_status.status.value}, "
                           f"Duration: {task_status.duration or 0:.3f}s")
                
                if task_status.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                    break
            else:
                logger.info("  Task not found in queue (may be completed)")
                break
            
            await asyncio.sleep(2)
        
        # 전체 큐 통계
        logger.info("\n📊 Final Queue Statistics:")
        stats = self.pipeline.get_stats()
        
        for key, value in stats.items():
            if isinstance(value, dict):
                logger.info(f"  {key}:")
                for sub_key, sub_value in value.items():
                    logger.info(f"    {sub_key}: {sub_value}")
            else:
                logger.info(f"  {key}: {value}")
        
        logger.info("✅ Task monitoring demo completed!")
    
    async def demo_error_scenarios(self):
        """에러 시나리오 데모"""
        logger.info("\n" + "="*50)
        logger.info("⚠️ DEMO 5: Error Handling")
        logger.info("="*50)
        
        # 1. 잘못된 작업 타입
        logger.info("🧪 Testing invalid task type...")
        try:
            await self.pipeline.enqueue("invalid_task", {"data": "test"})
            logger.info("  ❌ Should have failed!")
        except Exception as e:
            logger.info(f"  ✅ Properly rejected: {e}")
        
        # 2. 빈 페이로드로 검색
        logger.info("\n🧪 Testing empty search payload...")
        try:
            await self.pipeline.enqueue("search", {})
            logger.info("  ⚠️ Enqueued (will fail during processing)")
        except Exception as e:
            logger.info(f"  ✅ Rejected at enqueue: {e}")
        
        # 3. DLQ 상태 확인
        await asyncio.sleep(5)  # 처리 대기
        
        dlq_stats = self.pipeline.dlq.get_stats()
        logger.info(f"\n📊 Dead Letter Queue Stats: {dlq_stats}")
        
        logger.info("✅ Error handling demo completed!")
    
    async def run_all_demos(self):
        """모든 데모 실행"""
        logger.info("🎬 Starting Queue System Demo")
        logger.info("This demo shows how to use the new TaskQueue-based system")
        
        await self.setup()
        
        try:
            # 각 데모 실행
            await self.demo_basic_queueing()
            await asyncio.sleep(2)
            
            await self.demo_priority_queueing()
            await asyncio.sleep(2)
            
            await self.demo_batch_operations()
            await asyncio.sleep(2)
            
            await self.demo_task_monitoring()
            await asyncio.sleep(2)
            
            await self.demo_error_scenarios()
            
            logger.info("\n" + "="*60)
            logger.info("🎉 All demos completed successfully!")
            logger.info("="*60)
            
        finally:
            await self.cleanup()


async def main():
    """메인 데모 함수"""
    demo = QueueSystemDemo()
    await demo.run_all_demos()


if __name__ == "__main__":
    asyncio.run(main())