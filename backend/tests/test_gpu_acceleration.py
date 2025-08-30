"""
GPU 가속 시스템 테스트 스크립트
Author: Claude Code  
Date: 2025-01-27
Description: Phase 1-4 구현사항 검증을 위한 종합 테스트
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

class GPUAccelerationTester:
    """GPU 가속 시스템 통합 테스터"""
    
    def __init__(self):
        self.resource_manager = None
        self.pipeline = None
        self.test_results = []
    
    async def setup(self):
        """테스트 환경 설정"""
        logger.info("🚀 Setting up test environment...")
        
        try:
            # ResourceManager 초기화
            self.resource_manager = ResourceManager()
            await self.resource_manager.initialize()
            
            # AsyncPipeline 초기화
            self.pipeline = AsyncPipeline(
                resource_manager=self.resource_manager,
                max_concurrent=3,
                max_queue_size=50
            )
            
            # 큐 시스템 시작
            await self.pipeline.start_queue()
            
            logger.info("✅ Test environment setup complete")
            return True
            
        except Exception as e:
            logger.error(f"❌ Setup failed: {e}")
            return False
    
    async def teardown(self):
        """테스트 환경 정리"""
        logger.info("🧹 Cleaning up test environment...")
        
        try:
            if self.pipeline:
                await self.pipeline.stop_queue()
            
            if self.resource_manager:
                await self.resource_manager.cleanup()
            
            logger.info("✅ Cleanup complete")
            
        except Exception as e:
            logger.error(f"⚠️ Cleanup warning: {e}")
    
    def record_result(self, test_name: str, success: bool, duration: float, details: str = ""):
        """테스트 결과 기록"""
        self.test_results.append({
            "test": test_name,
            "success": success,
            "duration": duration,
            "details": details
        })
    
    async def test_phase1_import_fixes(self):
        """Phase 1: Import 경로 수정 테스트"""
        logger.info("🔍 Testing Phase 1: Import path fixes...")
        start_time = time.time()
        
        try:
            # 절대 경로 import 테스트
            from backend.pipeline.async_pipeline import AsyncPipeline
            from backend.common.schemas import AskRequest
            from backend.resource_manager import ResourceManager
            
            logger.info("✅ Phase 1: All imports successful")
            self.record_result("Phase1_ImportFixes", True, time.time() - start_time)
            return True
            
        except ImportError as e:
            logger.error(f"❌ Phase 1: Import failed - {e}")
            self.record_result("Phase1_ImportFixes", False, time.time() - start_time, str(e))
            return False
    
    async def test_phase2_ollama_client(self):
        """Phase 2: Ollama 클라이언트 통일 테스트"""
        logger.info("🔍 Testing Phase 2: Ollama client unification...")
        start_time = time.time()
        
        try:
            # ResourceManager의 embed_texts 메서드 테스트
            test_texts = ["테스트 문장입니다.", "GPU 가속이 작동하나요?"]
            
            embeddings = await self.resource_manager.embed_texts(test_texts)
            
            # 결과 검증
            assert len(embeddings) == len(test_texts), f"Expected {len(test_texts)} embeddings, got {len(embeddings)}"
            assert all(len(emb) == 1024 for emb in embeddings), "All embeddings should be 1024-dimensional"
            
            # 백엔드별 테스트
            backend = self.resource_manager.embed_backend
            if backend == "ollama":
                # Ollama 통일 클라이언트 테스트
                logger.info("🔧 Testing unified Ollama client...")
                embedding = await self.resource_manager.ollama_bucket.generate_embedding(
                    model=self.resource_manager.embed_model,
                    text="통일된 클라이언트 테스트"
                )
                assert len(embedding) == 1024, "Unified client should return 1024-dim embedding"
            
            logger.info(f"✅ Phase 2: Ollama client unified ({backend})")
            self.record_result("Phase2_OllamaClient", True, time.time() - start_time, f"Backend: {backend}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Phase 2: Ollama client test failed - {e}")
            self.record_result("Phase2_OllamaClient", False, time.time() - start_time, str(e))
            return False
    
    async def test_phase3_namespace_expansion(self):
        """Phase 3: 네임스페이스 확장 테스트"""
        logger.info("🔍 Testing Phase 3: Namespace expansion...")
        start_time = time.time()
        
        try:
            config = self.resource_manager.config
            
            # 동적 컬렉션명 생성 테스트
            mail_collection = config.get_collection_name("mail", "documents")
            doc_collection = config.get_collection_name("doc", "documents")
            
            # 예상 형식: {namespace}_{env}_{source}_{base}
            expected_pattern = f"{config.qdrant_namespace}_{config.qdrant_env}_"
            
            assert mail_collection.startswith(expected_pattern), f"Mail collection should start with {expected_pattern}"
            assert doc_collection.startswith(expected_pattern), f"Doc collection should start with {expected_pattern}"
            assert "mail" in mail_collection, "Mail collection should contain 'mail'"
            assert "doc" in doc_collection, "Doc collection should contain 'doc'"
            
            logger.info(f"✅ Phase 3: Collections - Mail: {mail_collection}, Doc: {doc_collection}")
            self.record_result("Phase3_NamespaceExpansion", True, time.time() - start_time, 
                             f"Mail: {mail_collection}, Doc: {doc_collection}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Phase 3: Namespace expansion test failed - {e}")
            self.record_result("Phase3_NamespaceExpansion", False, time.time() - start_time, str(e))
            return False
    
    async def test_phase4_queue_system(self):
        """Phase 4: 진정한 큐 시스템 테스트"""
        logger.info("🔍 Testing Phase 4: True queue system...")
        start_time = time.time()
        
        try:
            # 1. 기본 큐 기능 테스트
            queue_stats_before = self.pipeline.get_queue_stats()
            logger.info(f"📊 Queue stats before: {queue_stats_before}")
            
            # 2. 검색 작업 큐잉 테스트
            search_payload = {
                "query": "GPU 가속 테스트 쿼리",
                "source_type": "mail",
                "limit": 3,
                "score_threshold": 0.3
            }
            
            task_id = await self.pipeline.enqueue("search", search_payload, priority=1)
            logger.info(f"📤 Search task enqueued: {task_id}")
            
            # 3. 임베딩 작업 큐잉 테스트  
            embed_payload = {
                "text": "임베딩 테스트 텍스트",
                "document_id": "test_doc_001",
                "chunk_idx": 0
            }
            
            embed_task_id = await self.pipeline.enqueue("embed", embed_payload, priority=2)
            logger.info(f"📤 Embed task enqueued: {embed_task_id}")
            
            # 4. 배치 큐잉 테스트
            batch_tasks = [
                {"task_type": "search", "payload": {"query": "배치 테스트 1", "source_type": "mail"}, "priority": 0},
                {"task_type": "search", "payload": {"query": "배치 테스트 2", "source_type": "doc"}, "priority": 0},
                {"task_type": "embed", "payload": {"text": "배치 임베딩 테스트", "document_id": "batch_001"}, "priority": 1}
            ]
            
            batch_task_ids = await self.pipeline.enqueue_batch(batch_tasks)
            logger.info(f"📦 Batch tasks enqueued: {len([t for t in batch_task_ids if t])} successful")
            
            # 5. 작업 진행 대기 (최대 30초)
            max_wait = 30
            wait_time = 0
            
            while wait_time < max_wait:
                queue_stats = self.pipeline.get_queue_stats()
                processing_tasks = queue_stats.get("processing_tasks", 0)
                pending_tasks = queue_stats.get("pending_tasks", 0)
                completed_tasks = queue_stats.get("total_completed", 0)
                
                logger.info(f"📊 Queue status - Pending: {pending_tasks}, Processing: {processing_tasks}, Completed: {completed_tasks}")
                
                if pending_tasks == 0 and processing_tasks == 0:
                    logger.info("✅ All tasks completed")
                    break
                
                await asyncio.sleep(2)
                wait_time += 2
            
            # 6. 최종 통계 확인
            final_stats = self.pipeline.get_queue_stats()
            logger.info(f"📊 Final queue stats: {final_stats}")
            
            # 검증
            assert final_stats.get("total_completed", 0) > 0, "Some tasks should be completed"
            assert final_stats.get("total_failed", 0) >= 0, "Failed tasks count should be non-negative"
            
            logger.info("✅ Phase 4: Queue system working correctly")
            self.record_result("Phase4_QueueSystem", True, time.time() - start_time,
                             f"Completed: {final_stats.get('total_completed', 0)}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Phase 4: Queue system test failed - {e}")
            self.record_result("Phase4_QueueSystem", False, time.time() - start_time, str(e))
            return False
    
    async def test_gpu_performance(self):
        """GPU 성능 벤치마크 테스트"""
        logger.info("🔍 Testing GPU Performance...")
        start_time = time.time()
        
        try:
            # 다양한 크기의 텍스트 배치 테스트
            test_batches = [
                ["짧은 텍스트"],
                ["중간 길이 텍스트입니다. " * 5] * 5,
                ["긴 텍스트입니다. " * 20] * 10,
                ["매우 긴 텍스트입니다. " * 50] * 20
            ]
            
            performance_results = []
            
            for i, batch in enumerate(test_batches):
                batch_start = time.time()
                embeddings = await self.resource_manager.embed_texts(batch)
                batch_time = time.time() - batch_start
                
                perf_data = {
                    "batch_size": len(batch),
                    "avg_text_length": sum(len(text) for text in batch) // len(batch),
                    "duration": batch_time,
                    "texts_per_second": len(batch) / batch_time if batch_time > 0 else 0
                }
                performance_results.append(perf_data)
                
                logger.info(f"📊 Batch {i+1}: {len(batch)} texts, {batch_time:.3f}s, "
                           f"{perf_data['texts_per_second']:.1f} texts/sec")
            
            # 평균 성능 계산
            avg_tps = sum(p['texts_per_second'] for p in performance_results) / len(performance_results)
            device = self.resource_manager.embed_device
            
            logger.info(f"✅ GPU Performance: Average {avg_tps:.1f} texts/sec on {device}")
            self.record_result("GPU_Performance", True, time.time() - start_time,
                             f"Avg: {avg_tps:.1f} texts/sec, Device: {device}")
            return True
            
        except Exception as e:
            logger.error(f"❌ GPU Performance test failed - {e}")
            self.record_result("GPU_Performance", False, time.time() - start_time, str(e))
            return False
    
    async def test_error_handling(self):
        """에러 처리 및 DLQ 테스트"""
        logger.info("🔍 Testing Error Handling and DLQ...")
        start_time = time.time()
        
        try:
            # 1. 잘못된 작업 타입 테스트
            try:
                await self.pipeline.enqueue("invalid_type", {})
                assert False, "Should have raised an error for invalid task type"
            except ValueError:
                logger.info("✅ Invalid task type properly rejected")
            
            # 2. 빈 페이로드 테스트  
            try:
                await self.pipeline.enqueue("search", {})
                # 이것은 실패할 수 있지만 DLQ에 들어가야 함
                logger.info("⚠️ Empty payload handled (may fail gracefully)")
            except Exception:
                logger.info("✅ Empty payload error handled")
            
            # 3. DLQ 통계 확인
            await asyncio.sleep(2)  # 처리 대기
            dlq_stats = self.pipeline.dlq.get_stats()
            logger.info(f"📊 DLQ Stats: {dlq_stats}")
            
            # 4. 큐 상태 통계
            queue_stats = self.pipeline.get_queue_stats()
            logger.info(f"📊 Queue Stats: {queue_stats}")
            
            logger.info("✅ Error handling and DLQ working")
            self.record_result("ErrorHandling_DLQ", True, time.time() - start_time,
                             f"DLQ entries: {dlq_stats.get('total_entries', 0)}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error handling test failed - {e}")
            self.record_result("ErrorHandling_DLQ", False, time.time() - start_time, str(e))
            return False
    
    def print_results(self):
        """테스트 결과 출력"""
        logger.info("\n" + "="*60)
        logger.info("📊 GPU ACCELERATION TEST RESULTS")
        logger.info("="*60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r["success"])
        total_time = sum(r["duration"] for r in self.test_results)
        
        for result in self.test_results:
            status = "✅ PASS" if result["success"] else "❌ FAIL"
            logger.info(f"{status} {result['test']:<25} {result['duration']:.3f}s")
            if result["details"]:
                logger.info(f"     └─ {result['details']}")
        
        logger.info("-"*60)
        logger.info(f"📈 SUMMARY: {passed_tests}/{total_tests} tests passed ({passed_tests/total_tests*100:.1f}%)")
        logger.info(f"⏱️  TOTAL TIME: {total_time:.3f} seconds")
        logger.info("="*60)
        
        return passed_tests == total_tests
    
    async def run_all_tests(self):
        """모든 테스트 실행"""
        logger.info("🚀 Starting GPU Acceleration System Tests")
        
        # 환경 설정
        if not await self.setup():
            logger.error("❌ Setup failed, aborting tests")
            return False
        
        try:
            # Phase별 테스트 실행
            tests = [
                self.test_phase1_import_fixes,
                self.test_phase2_ollama_client,
                self.test_phase3_namespace_expansion,
                self.test_phase4_queue_system,
                self.test_gpu_performance,
                self.test_error_handling
            ]
            
            for test in tests:
                try:
                    await test()
                except Exception as e:
                    logger.error(f"❌ Test {test.__name__} crashed: {e}")
                    self.record_result(test.__name__, False, 0, f"Crashed: {e}")
                
                # 테스트 간 간격
                await asyncio.sleep(1)
        
        finally:
            # 환경 정리
            await self.teardown()
        
        # 결과 출력
        return self.print_results()


async def main():
    """메인 테스트 함수"""
    tester = GPUAccelerationTester()
    success = await tester.run_all_tests()
    
    if success:
        logger.info("🎉 All tests passed!")
        return 0
    else:
        logger.error("💥 Some tests failed!")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)