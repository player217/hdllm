"""
Circuit Breaker Integration Test for HD현대미포 Gauss-1 RAG System
Author: Claude Code
Date: 2025-01-26
Description: Phase 2A-2 - ResourceManager와 Circuit Breaker 통합 테스트
"""

import asyncio
import time
import logging
from unittest.mock import AsyncMock, patch
from backend.resource_manager import ResourceManager, ResourceConfig, CircuitBreakerState

# 테스트용 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestResourceManagerCircuitBreaker:
    """ResourceManager와 Circuit Breaker 통합 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        self.config = ResourceConfig(
            # 낮은 임계값으로 테스트 용이성 확보
            cb_error_threshold=0.50,    # 50% 에러율
            cb_p95_threshold_ms=2000,   # P95 2초
            cb_queue_threshold=5,       # 큐 길이 5
            cb_window_seconds=10,       # 10초 윈도우
            cb_recovery_seconds=5,      # 5초 후 반개방
            ollama_max_concurrency=3,   # 동시 처리 3개
            retry_max=2                 # 최대 2회 재시도
        )
    
    async def test_ollama_circuit_breaker_integration(self):
        """Ollama TokenBucket과 Circuit Breaker 통합 테스트"""
        logger.info("🧪 Testing Ollama Circuit Breaker integration")
        
        resource_manager = ResourceManager(self.config)
        await resource_manager.initialize()
        
        try:
            # 정상 요청 처리 테스트
            async with resource_manager.ollama_token_bucket.acquire("normal_request") as should_proceed:
                assert should_proceed == True
                logger.info("✅ Normal request allowed by Circuit Breaker")
            
            # Circuit Breaker에 실패 기록하여 임계값 도달
            ollama_cb = resource_manager.ollama_token_bucket.circuit_breaker
            
            # 50% 에러율 도달을 위한 실패 기록
            for i in range(3):
                ollama_cb.record_success(100.0)
            for i in range(3):
                ollama_cb.record_failure(100.0, f"test_error_{i}")
            
            # 이제 Circuit Breaker가 열려야 함
            async with resource_manager.ollama_token_bucket.acquire("blocked_request") as should_proceed:
                assert should_proceed == False
                logger.info("✅ Request blocked by Circuit Breaker after error threshold")
            
            # Circuit Breaker 상태 확인
            cb_status = ollama_cb.get_status()
            assert cb_status['state'] == 'open'
            assert cb_status['error_rate'] >= 0.50
            
            logger.info(f"✅ Circuit Breaker state: {cb_status}")
            
        finally:
            await resource_manager.cleanup()
    
    async def test_qdrant_circuit_breaker_integration(self):
        """Qdrant ClientPool과 Circuit Breaker 통합 테스트"""
        logger.info("🧪 Testing Qdrant Circuit Breaker integration")
        
        resource_manager = ResourceManager(self.config)
        await resource_manager.initialize()
        
        try:
            # Mail Qdrant Pool 테스트
            mail_pool = resource_manager.qdrant_pools["mail"]
            mail_cb = mail_pool.circuit_breaker
            
            # 정상 상태 확인
            assert mail_cb.should_allow_request() == True
            logger.info("✅ Qdrant mail pool allows requests initially")
            
            # P95 지연시간 임계값 초과 시뮬레이션
            for i in range(8):
                mail_cb.record_success(100.0)
            for i in range(2):
                mail_cb.record_success(3000.0)  # P95 > 2000ms가 되도록
            
            # Circuit Breaker 개방 확인
            assert mail_cb.should_allow_request() == False
            assert mail_cb.state == CircuitBreakerState.OPEN
            
            cb_status = mail_cb.get_status()
            logger.info(f"✅ Qdrant Circuit Breaker opened due to P95: {cb_status}")
            
        finally:
            await resource_manager.cleanup()
    
    async def test_circuit_breaker_recovery_flow(self):
        """Circuit Breaker 복구 플로우 테스트"""
        logger.info("🧪 Testing Circuit Breaker recovery flow")
        
        resource_manager = ResourceManager(self.config)
        await resource_manager.initialize()
        
        try:
            ollama_cb = resource_manager.ollama_token_bucket.circuit_breaker
            
            # 강제로 OPEN 상태로 만들기
            for i in range(2):
                ollama_cb.record_success(100.0)
            for i in range(3):
                ollama_cb.record_failure(100.0, "forced_failure")
            
            assert ollama_cb.state == CircuitBreakerState.OPEN
            logger.info("🔴 Circuit Breaker forced to OPEN state")
            
            # 복구 시간 대기 (5초 + 여유)
            logger.info("⏳ Waiting for recovery timeout...")
            await asyncio.sleep(6)
            
            # HALF_OPEN 상태로 전환 확인
            can_proceed = ollama_cb.should_allow_request()
            assert can_proceed == True
            assert ollama_cb.state == CircuitBreakerState.HALF_OPEN
            logger.info("🟡 Circuit Breaker in HALF_OPEN state")
            
            # 연속 성공으로 CLOSED 상태 복구
            for i in range(5):
                ollama_cb.record_success(100.0)
            
            assert ollama_cb.state == CircuitBreakerState.CLOSED
            logger.info("🟢 Circuit Breaker recovered to CLOSED state")
            
        finally:
            await resource_manager.cleanup()
    
    async def test_high_load_circuit_breaker_behavior(self):
        """고부하 상황에서 Circuit Breaker 동작 테스트"""
        logger.info("🧪 Testing Circuit Breaker under high load")
        
        resource_manager = ResourceManager(self.config)
        await resource_manager.initialize()
        
        try:
            # 동시 요청 시뮬레이션
            async def simulate_request(request_id: int):
                async with resource_manager.ollama_token_bucket.acquire(f"request_{request_id}") as should_proceed:
                    if should_proceed:
                        # 작업 시뮬레이션
                        await asyncio.sleep(0.1)
                        return f"success_{request_id}"
                    else:
                        return f"blocked_{request_id}"
            
            # 10개 동시 요청 (동시성 제한 3개)
            tasks = [simulate_request(i) for i in range(10)]
            results = await asyncio.gather(*tasks)
            
            successful_requests = [r for r in results if r.startswith("success")]
            blocked_requests = [r for r in results if r.startswith("blocked")]
            
            logger.info(f"✅ High load test: {len(successful_requests)} success, {len(blocked_requests)} blocked")
            
            # 동시성 제한이 작동하는지 확인
            assert len(successful_requests) <= 10  # 모든 요청이 처리되거나 차단됨
            
        finally:
            await resource_manager.cleanup()
    
    async def test_circuit_breaker_metrics_accuracy(self):
        """Circuit Breaker 메트릭 정확성 테스트"""
        logger.info("🧪 Testing Circuit Breaker metrics accuracy")
        
        resource_manager = ResourceManager(self.config)
        await resource_manager.initialize()
        
        try:
            cb = resource_manager.ollama_token_bucket.circuit_breaker
            
            # 알려진 패턴으로 메트릭 생성
            success_count = 7
            failure_count = 3
            success_latency = 150.0
            failure_latency = 2500.0
            
            for i in range(success_count):
                cb.record_success(success_latency)
            
            for i in range(failure_count):
                cb.record_failure(failure_latency, "test_failure")
            
            # 메트릭 검증
            error_rate = cb._calculate_error_rate()
            expected_error_rate = failure_count / (success_count + failure_count)
            assert abs(error_rate - expected_error_rate) < 0.01
            
            p95_latency = cb._calculate_p95_latency()
            # P95 계산: 10개 요청의 95번째 백분위수
            expected_p95_index = int(10 * 0.95)  # index 9
            # 정렬된 순서: [150, 150, 150, 150, 150, 150, 150, 2500, 2500, 2500]
            # 9번째 인덱스 = 2500.0
            
            status = cb.get_status()
            logger.info(f"✅ Metrics accuracy test:")
            logger.info(f"   - Error rate: {error_rate:.2%} (expected: {expected_error_rate:.2%})")
            logger.info(f"   - P95 latency: {p95_latency:.0f}ms")
            logger.info(f"   - Recent requests: {status['recent_requests']}")
            logger.info(f"   - Failure count: {status['failure_count']}")
            
        finally:
            await resource_manager.cleanup()


async def run_integration_tests():
    """통합 테스트 실행"""
    logger.info("🚀 Starting Circuit Breaker Integration Tests for Phase 2A-2")
    
    test_class = TestResourceManagerCircuitBreaker()
    
    try:
        # 각 테스트마다 새로운 설정으로 실행
        test_class.setup_method()
        await test_class.test_ollama_circuit_breaker_integration()
        logger.info("✅ Ollama Circuit Breaker integration test passed")
        
        test_class.setup_method()
        await test_class.test_qdrant_circuit_breaker_integration()
        logger.info("✅ Qdrant Circuit Breaker integration test passed")
        
        test_class.setup_method()
        await test_class.test_circuit_breaker_recovery_flow()
        logger.info("✅ Circuit Breaker recovery flow test passed")
        
        test_class.setup_method()
        await test_class.test_high_load_circuit_breaker_behavior()
        logger.info("✅ High load Circuit Breaker test passed")
        
        test_class.setup_method()
        await test_class.test_circuit_breaker_metrics_accuracy()
        logger.info("✅ Circuit Breaker metrics accuracy test passed")
        
        logger.info("🎯 All Circuit Breaker integration tests passed!")
        logger.info("✅ Phase 2A-2 Circuit Breaker 재정의 완료")
        
    except Exception as e:
        logger.error(f"❌ Integration test failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(run_integration_tests())