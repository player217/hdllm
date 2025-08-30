"""
Circuit Breaker Test Suite for HD현대미포 Gauss-1 RAG System
Author: Claude Code  
Date: 2025-01-26
Description: Phase 2A-2 - Circuit Breaker 재정의 (에러율·P95·큐 길이 기반) 검증
"""

import asyncio
import time
import logging
from typing import List
from backend.resource_manager import CircuitBreaker, ResourceConfig, CircuitBreakerState, RequestMetrics

# 테스트용 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestCircuitBreakerOperationalMetrics:
    """운영 지표 기반 Circuit Breaker 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        self.config = ResourceConfig(
            cb_error_threshold=0.20,    # 20% 에러율
            cb_p95_threshold_ms=5000,   # P95 5초  
            cb_queue_threshold=64,      # 큐 길이 64
            cb_window_seconds=30,       # 30초 윈도우
            cb_recovery_seconds=10      # 10초 후 반개방
        )
        self.cb = CircuitBreaker("test_cb", self.config)
    
    def test_error_rate_trigger(self):
        """에러율 20% 초과 시 Circuit Breaker 개방 테스트"""
        logger.info("🧪 Testing error rate trigger (20% threshold)")
        
        # 정상 요청 80개
        for i in range(80):
            self.cb.record_success(100.0)
        
        # 에러 요청 19개 (총 99개 중 19.19% = 임계값 미만)
        for i in range(19):
            self.cb.record_failure(100.0, "test_error")
        
        # 임계값 미만이므로 요청 허용되어야 함
        assert self.cb.should_allow_request() == True
        
        # 에러 1개 더 추가 (총 100개 중 20% = 임계값 도달)
        self.cb.record_failure(100.0, "test_error")
        
        # 임계값 도달로 Circuit Breaker 개방되어야 함
        assert self.cb.should_allow_request() == False
        assert self.cb.state == CircuitBreakerState.OPEN
        
        status = self.cb.get_status()
        logger.info(f"✅ Error rate trigger test passed: {status['error_rate']:.2%} > 20%")
    
    def test_p95_latency_trigger(self):
        """P95 지연시간 5000ms 이상 시 Circuit Breaker 개방 테스트"""
        logger.info("🧪 Testing P95 latency trigger (5000ms threshold)")
        
        # 100개 요청 - 먼저 90개는 빠른 응답 (100ms)
        for i in range(90):
            self.cb.record_success(100.0)
        
        # 91-95번째도 빠른 응답 (P95 index = int(100 * 0.95) = 95, 즉 96번째 값)
        for i in range(5):
            self.cb.record_success(100.0)
        
        # 96-99번째는 느린 응답 (4999ms - 아직 임계값 미만)
        for i in range(4):
            self.cb.record_success(4999.0)
        
        # 100번째 요청 전 P95 확인 (95번째 요청이 P95이므로 100ms)
        current_p95 = self.cb._calculate_p95_latency()
        logger.info(f"Current P95 before threshold test: {current_p95:.0f}ms")
        assert self.cb.should_allow_request() == True
        
        # 100번째 요청을 5001ms로 추가 (이제 P95는 4999ms가 됨)
        self.cb.record_success(5001.0)
        
        # P95가 아직 4999ms이므로 허용되어야 함
        p95_after_100 = self.cb._calculate_p95_latency()
        logger.info(f"P95 after 100 requests: {p95_after_100:.0f}ms")
        assert self.cb.should_allow_request() == True
        
        # 추가로 6개 더 느린 요청을 추가해서 P95를 올림
        for i in range(6):
            self.cb.record_success(6000.0)
        
        # 이제 P95가 5000ms 이상이 됨
        final_p95 = self.cb._calculate_p95_latency()
        logger.info(f"Final P95 after adding more slow requests: {final_p95:.0f}ms")
        
        # P95 >= 5000ms로 Circuit Breaker 개방
        assert self.cb.should_allow_request() == False
        assert self.cb.state == CircuitBreakerState.OPEN
        
        status = self.cb.get_status()
        logger.info(f"✅ P95 latency trigger test passed: {status['p95_latency_ms']:.0f}ms >= 5000ms")
    
    def test_queue_length_trigger(self):
        """큐 길이 64 초과 시 Circuit Breaker 개방 테스트"""
        logger.info("🧪 Testing queue length trigger (64 threshold)")
        
        # 큐 길이가 임계값 미달일 때
        assert self.cb.should_allow_request(current_queue_size=63) == True
        assert self.cb.state == CircuitBreakerState.CLOSED
        
        # 큐 길이가 임계값 초과일 때
        assert self.cb.should_allow_request(current_queue_size=64) == False
        assert self.cb.state == CircuitBreakerState.OPEN
        
        logger.info("✅ Queue length trigger test passed: queue=64 >= 64 threshold")
    
    def test_recovery_mechanism(self):
        """복구 메커니즘 테스트"""
        logger.info("🧪 Testing recovery mechanism (OPEN -> HALF_OPEN -> CLOSED)")
        
        # Circuit Breaker를 강제로 OPEN 상태로
        self.cb.state = CircuitBreakerState.OPEN
        self.cb.last_failure_time = time.time() - 11  # 11초 전 실패 (복구 시간 10초 초과)
        
        # 복구 시간 초과 후 요청 → HALF_OPEN 상태로 전환
        assert self.cb.should_allow_request() == True
        assert self.cb.state == CircuitBreakerState.HALF_OPEN
        
        # HALF_OPEN에서 연속 성공 5회
        for i in range(5):
            self.cb.record_success(100.0)
        
        # 5회 연속 성공 후 CLOSED 상태로 전환 확인
        assert self.cb.state == CircuitBreakerState.CLOSED
        logger.info("✅ Recovery mechanism test passed: OPEN -> HALF_OPEN -> CLOSED")
    
    def test_half_open_failure(self):
        """HALF_OPEN 상태에서 실패 시 OPEN 복귀 테스트"""
        logger.info("🧪 Testing half-open failure scenario")
        
        # HALF_OPEN 상태로 설정
        self.cb.state = CircuitBreakerState.HALF_OPEN
        
        # 실패 기록
        self.cb.record_failure(100.0, "half_open_test_failure")
        
        # 다시 OPEN 상태로 복귀 확인
        assert self.cb.state == CircuitBreakerState.OPEN
        logger.info("✅ Half-open failure test passed: HALF_OPEN -> OPEN on failure")
    
    def test_metrics_window_cleanup(self):
        """메트릭 윈도우 정리 테스트"""
        logger.info("🧪 Testing metrics window cleanup")
        
        # 오래된 메트릭 생성 (31초 전)
        old_time = time.time() - 31
        old_metric = RequestMetrics(
            timestamp=old_time,
            duration_ms=100.0,
            success=True
        )
        self.cb.metrics.append(old_metric)
        
        # 최근 메트릭 생성
        self.cb.record_success(100.0)
        
        # 정리 전 메트릭 개수
        count_before = len(self.cb.metrics)
        
        # 정리 실행
        self.cb._clean_old_metrics()
        
        # 정리 후 메트릭 개수 (오래된 것 제거됨)
        count_after = len(self.cb.metrics)
        
        assert count_after < count_before
        logger.info(f"✅ Metrics cleanup test passed: {count_before} -> {count_after} metrics")
    
    def test_complex_scenario(self):
        """복합 시나리오 테스트: 다양한 조건 조합"""
        logger.info("🧪 Testing complex scenario with multiple conditions")
        
        # 시나리오 1: 에러율은 낮지만 P95가 높음
        for i in range(90):
            self.cb.record_success(100.0)  # 빠른 성공
        for i in range(10):
            self.cb.record_success(6000.0)  # 느린 성공 (P95 올림)
        
        # P95 초과로 인한 개방
        assert self.cb.should_allow_request() == False
        assert self.cb.state == CircuitBreakerState.OPEN
        
        # 새로운 Circuit Breaker로 리셋
        self.cb = CircuitBreaker("test_cb_2", self.config)
        
        # 시나리오 2: 에러율과 큐 길이 모두 임계값 초과
        for i in range(70):
            self.cb.record_success(100.0)
        for i in range(30):
            self.cb.record_failure(100.0, "multiple_condition_error")
        
        # 에러율(30%) + 큐 길이(70) 모두 초과
        assert self.cb.should_allow_request(current_queue_size=70) == False
        assert self.cb.state == CircuitBreakerState.OPEN
        
        logger.info("✅ Complex scenario test passed")


class TestCircuitBreakerIntegration:
    """ResourceManager와의 통합 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        self.config = ResourceConfig()
        
    async def test_integration_with_ollama_token_bucket(self):
        """OllamaTokenBucket과의 통합 테스트"""
        logger.info("🧪 Testing Circuit Breaker integration with OllamaTokenBucket")
        
        from backend.resource_manager import OllamaTokenBucket
        
        # OllamaTokenBucket 생성
        token_bucket = OllamaTokenBucket(self.config)
        
        # Circuit Breaker 생성
        cb = CircuitBreaker("ollama_cb", self.config)
        
        # 정상적인 토큰 획득 시뮬레이션
        async with token_bucket.acquire("test_request") as should_proceed:
            if should_proceed and cb.should_allow_request(token_bucket.queue_size):
                # 성공적인 요청 처리
                start_time = time.time()
                await asyncio.sleep(0.1)  # 실제 작업 시뮬레이션
                end_time = time.time()
                
                cb.record_success((end_time - start_time) * 1000)
                logger.info("✅ Successful request recorded")
            else:
                logger.info("⚠️ Request blocked by Circuit Breaker or Token Bucket")
        
        status = cb.get_status()
        assert status['recent_requests'] > 0
        logger.info("✅ Integration test passed")


class TestCircuitBreakerMetrics:
    """Circuit Breaker 메트릭 정확성 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        self.config = ResourceConfig()
        self.cb = CircuitBreaker("metrics_test", self.config)
    
    def test_error_rate_calculation(self):
        """에러율 계산 정확성 테스트"""
        logger.info("🧪 Testing error rate calculation accuracy")
        
        # 정확히 25% 에러율 생성
        for i in range(75):
            self.cb.record_success(100.0)
        for i in range(25):
            self.cb.record_failure(100.0, "test_error")
        
        error_rate = self.cb._calculate_error_rate()
        expected_rate = 25.0 / 100.0
        
        assert abs(error_rate - expected_rate) < 0.01
        logger.info(f"✅ Error rate calculation accurate: {error_rate:.2%} ≈ {expected_rate:.2%}")
    
    def test_p95_calculation(self):
        """P95 계산 정확성 테스트"""
        logger.info("🧪 Testing P95 latency calculation accuracy")
        
        # 알려진 분포로 테스트 (1-100ms)
        for i in range(1, 101):
            self.cb.record_success(float(i))
        
        p95 = self.cb._calculate_p95_latency()
        # 100개 요청의 P95 index = int(100 * 0.95) = 95, 즉 index 95 = 96번째 값
        expected_p95 = 96.0
        
        assert abs(p95 - expected_p95) < 1.0
        logger.info(f"✅ P95 calculation accurate: {p95:.0f}ms ≈ {expected_p95:.0f}ms")


def run_circuit_breaker_tests():
    """Circuit Breaker 테스트 실행"""
    logger.info("🚀 Starting Circuit Breaker Test Suite for Phase 2A-2")
    
    # 기본 테스트
    test_operational = TestCircuitBreakerOperationalMetrics()
    test_operational.setup_method()
    
    test_operational.test_error_rate_trigger()
    
    test_operational.setup_method()  # 리셋
    test_operational.test_p95_latency_trigger()
    
    test_operational.setup_method()  # 리셋
    test_operational.test_queue_length_trigger()
    
    test_operational.setup_method()  # 리셋
    test_operational.test_recovery_mechanism()
    
    test_operational.setup_method()  # 리셋
    test_operational.test_half_open_failure()
    
    test_operational.setup_method()  # 리셋
    test_operational.test_metrics_window_cleanup()
    
    test_operational.setup_method()  # 리셋
    test_operational.test_complex_scenario()
    
    # 메트릭 정확성 테스트
    test_metrics = TestCircuitBreakerMetrics()
    test_metrics.setup_method()
    test_metrics.test_error_rate_calculation()
    
    test_metrics.setup_method()  # 리셋
    test_metrics.test_p95_calculation()
    
    logger.info("✅ All Circuit Breaker tests passed!")
    logger.info("🎯 Phase 2A-2 Circuit Breaker validation complete")


if __name__ == "__main__":
    run_circuit_breaker_tests()