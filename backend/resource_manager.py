"""
Resource Manager Module for HD현대미포 Gauss-1 RAG System
Author: Claude Code
Date: 2025-01-26
Description: 현실적인 리소스 관리 - Ollama 동시성 토큰 버킷 + Qdrant 클라이언트 풀링
"""

import os
import asyncio
import logging
import time
from typing import Dict, Optional, Any, List, Union
from dataclasses import dataclass, field
from collections import deque
from contextlib import asynccontextmanager
import httpx
import threading
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)

class CircuitBreakerState(Enum):
    CLOSED = "closed"      # 정상 동작
    OPEN = "open"          # 장애 상태
    HALF_OPEN = "half_open"  # 복구 시도

@dataclass
class ResourceConfig:
    """리소스 관리 설정"""
    # Ollama 동시성 제어
    ollama_max_concurrency: int = int(os.getenv("OLLAMA_MAX_CONCURRENCY", "8"))
    ollama_endpoint: str = os.getenv("OLLAMA_ENDPOINT", "http://127.0.0.1:11434")
    
    # HTTP 클라이언트 설정
    http_timeout_ms: int = int(os.getenv("HTTP_TIMEOUT_MS", "3000"))
    http_max_keepalive: int = int(os.getenv("HTTP_MAX_KEEPALIVE", "20"))
    
    # 재시도 정책
    retry_max: int = int(os.getenv("RETRY_MAX", "3"))
    retry_backoff_ms: int = int(os.getenv("RETRY_BACKOFF_MS", "200"))
    
    # Circuit Breaker 설정 (현실적 기준)
    cb_error_threshold: float = float(os.getenv("CB_ERROR_THRESHOLD", "0.20"))  # 20% 에러율
    cb_p95_threshold_ms: int = int(os.getenv("CB_P95_THRESHOLD_MS", "5000"))   # P95 5초
    cb_queue_threshold: int = int(os.getenv("CB_QUEUE_THRESHOLD", "64"))       # 큐 길이 64
    cb_window_seconds: int = int(os.getenv("CB_WINDOW_SECONDS", "30"))         # 30초 윈도우
    cb_recovery_seconds: int = int(os.getenv("CB_RECOVERY_SECONDS", "10"))     # 10초 후 반개방
    
    # 큐 관리
    queue_max_size: int = int(os.getenv("QUEUE_MAX_SIZE", "64"))

@dataclass
class RequestMetrics:
    """요청 메트릭 데이터"""
    timestamp: float
    duration_ms: float
    success: bool
    error: Optional[str] = None

class CircuitBreaker:
    """
    현실적인 Circuit Breaker - 에러율·P95·큐 길이 기반
    CPU/RAM 기준이 아닌 운영 지표 기반으로 재설계
    """
    
    def __init__(self, name: str, config: ResourceConfig):
        self.name = name
        self.config = config
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0
        self.metrics: deque[RequestMetrics] = deque(maxlen=1000)  # 최근 1000개 요청
        self.lock = threading.Lock()
        
        logger.info(f"🔧 Circuit Breaker '{name}' initialized with realistic thresholds")
        
    def _clean_old_metrics(self):
        """오래된 메트릭 정리"""
        cutoff = time.time() - self.config.cb_window_seconds
        while self.metrics and self.metrics[0].timestamp < cutoff:
            self.metrics.popleft()
    
    def _calculate_error_rate(self) -> float:
        """최근 윈도우 내 에러율 계산"""
        if not self.metrics:
            return 0.0
        
        total = len(self.metrics)
        errors = sum(1 for m in self.metrics if not m.success)
        return errors / total if total > 0 else 0.0
    
    def _calculate_p95_latency(self) -> float:
        """P95 지연시간 계산"""
        if not self.metrics:
            return 0.0
        
        durations = sorted([m.duration_ms for m in self.metrics])
        p95_index = int(len(durations) * 0.95)
        return durations[p95_index] if durations else 0.0
    
    def should_allow_request(self, current_queue_size: int = 0) -> bool:
        """요청 허용 여부 결정"""
        with self.lock:
            self._clean_old_metrics()
            
            if self.state == CircuitBreakerState.OPEN:
                # 복구 시간 확인
                if time.time() - self.last_failure_time > self.config.cb_recovery_seconds:
                    self.state = CircuitBreakerState.HALF_OPEN
                    logger.info(f"🔄 Circuit Breaker '{self.name}' entering HALF_OPEN state")
                    return True
                return False
            
            if self.state == CircuitBreakerState.HALF_OPEN:
                # 반개방 상태에서는 샘플 요청만 허용
                return True
            
            # CLOSED 상태: 현실적 지표 기반 판단
            error_rate = self._calculate_error_rate()
            p95_latency = self._calculate_p95_latency()
            
            # 개방 조건 확인
            should_open = (
                error_rate >= self.config.cb_error_threshold or
                p95_latency >= self.config.cb_p95_threshold_ms or
                current_queue_size >= self.config.cb_queue_threshold
            )
            
            if should_open:
                self.state = CircuitBreakerState.OPEN
                self.last_failure_time = time.time()
                logger.warning(
                    f"🚨 Circuit Breaker '{self.name}' OPENED: "
                    f"error_rate={error_rate:.2%}, p95={p95_latency:.0f}ms, queue={current_queue_size}"
                )
                return False
            
            return True
    
    def record_success(self, duration_ms: float):
        """성공 기록"""
        with self.lock:
            self.metrics.append(RequestMetrics(
                timestamp=time.time(),
                duration_ms=duration_ms,
                success=True
            ))
            
            if self.state == CircuitBreakerState.HALF_OPEN:
                # 반개방에서 연속 성공 시 닫기
                recent_successes = sum(1 for m in list(self.metrics)[-5:] if m.success)
                if recent_successes >= 5:
                    self.state = CircuitBreakerState.CLOSED
                    self.failure_count = 0
                    logger.info(f"✅ Circuit Breaker '{self.name}' CLOSED (recovered)")
    
    def record_failure(self, duration_ms: float, error: str):
        """실패 기록"""
        with self.lock:
            self.metrics.append(RequestMetrics(
                timestamp=time.time(),
                duration_ms=duration_ms,
                success=False,
                error=error[:100]  # 에러 메시지 길이 제한
            ))
            
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.state == CircuitBreakerState.HALF_OPEN:
                # 반개방에서 실패 시 다시 개방
                self.state = CircuitBreakerState.OPEN
                logger.warning(f"🔴 Circuit Breaker '{self.name}' back to OPEN (half-open failed)")
    
    def get_status(self) -> Dict[str, Any]:
        """현재 상태 반환"""
        with self.lock:
            self._clean_old_metrics()
            return {
                "name": self.name,
                "state": self.state.value,
                "error_rate": self._calculate_error_rate(),
                "p95_latency_ms": self._calculate_p95_latency(),
                "recent_requests": len(self.metrics),
                "failure_count": self.failure_count,
                "last_failure": datetime.fromtimestamp(self.last_failure_time).isoformat() if self.last_failure_time else None
            }

class OllamaTokenBucket:
    """
    Ollama 동시성 토큰 버킷 관리
    - 파이썬 객체 풀링이 아닌 단일 인스턴스 + 앱 레벨 동시성 제한
    """
    
    def __init__(self, config: ResourceConfig):
        self.config = config
        self.semaphore = asyncio.Semaphore(config.ollama_max_concurrency)
        self.active_requests = 0
        self.queue_size = 0
        self.lock = asyncio.Lock()
        self.circuit_breaker = CircuitBreaker("ollama", config)
        
        # HTTP 클라이언트 (재사용)
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(config.http_timeout_ms / 1000.0),
            limits=httpx.Limits(
                max_keepalive_connections=config.http_max_keepalive,
                max_connections=config.http_max_keepalive * 2,
                keepalive_expiry=30.0
            )
        )
        
        logger.info(f"🎯 Ollama Token Bucket initialized: concurrency={config.ollama_max_concurrency}")
    
    @asynccontextmanager
    async def acquire_token(self):
        """토큰 획득 및 반환"""
        async with self.lock:
            self.queue_size += 1
        
        # Circuit Breaker 확인
        if not self.circuit_breaker.should_allow_request(self.queue_size):
            async with self.lock:
                self.queue_size -= 1
            raise Exception(f"Circuit breaker OPEN for Ollama service")
        
        try:
            await self.semaphore.acquire()
            async with self.lock:
                self.queue_size -= 1
                self.active_requests += 1
            
            yield
            
        finally:
            async with self.lock:
                self.active_requests -= 1
            self.semaphore.release()
    
    async def generate_with_retry(self, prompt: str, model: str = "gemma3:4b") -> str:
        """재시도 정책이 포함된 LLM 생성"""
        for attempt in range(self.config.retry_max):
            start_time = time.time()
            
            try:
                async with self.acquire_token():
                    response = await self._call_ollama_api(prompt, model)
                    
                duration_ms = (time.time() - start_time) * 1000
                self.circuit_breaker.record_success(duration_ms)
                return response
                
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                self.circuit_breaker.record_failure(duration_ms, str(e))
                
                if attempt < self.config.retry_max - 1:
                    # 지수 백오프
                    delay = self.config.retry_backoff_ms * (2 ** attempt) / 1000.0
                    logger.warning(f"🔄 Ollama retry {attempt + 1}/{self.config.retry_max} after {delay:.1f}s: {e}")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"❌ Ollama failed after {self.config.retry_max} attempts: {e}")
                    raise
    
    async def _call_ollama_api(self, prompt: str, model: str) -> str:
        """실제 Ollama API 호출"""
        try:
            response = await self.client.post(
                f"{self.config.ollama_endpoint}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False
                }
            )
            response.raise_for_status()
            
            result = response.json()
            return result.get("response", "")
            
        except httpx.TimeoutException:
            raise Exception("Ollama request timeout")
        except httpx.HTTPError as e:
            raise Exception(f"Ollama HTTP error: {e}")
        except Exception as e:
            raise Exception(f"Ollama API error: {e}")
    
    async def get_status(self) -> Dict[str, Any]:
        """토큰 버킷 상태 반환"""
        async with self.lock:
            return {
                "max_concurrency": self.config.ollama_max_concurrency,
                "active_requests": self.active_requests,
                "queue_size": self.queue_size,
                "available_tokens": self.semaphore._value,
                "circuit_breaker": self.circuit_breaker.get_status()
            }
    
    async def cleanup(self):
        """리소스 정리"""
        await self.client.aclose()

class QdrantClientPool:
    """
    Qdrant 클라이언트 풀 - httpx Keep-Alive 기반
    커넥션 상한 + 타임아웃/재시도 공통화
    """
    
    def __init__(self, source_type: str, config: ResourceConfig):
        self.source_type = source_type
        self.config = config
        
        # 환경변수에서 URL 로드
        if source_type == "mail":
            self.base_url = os.getenv("MAIL_QDRANT_URL", "http://127.0.0.1:6333")
        elif source_type == "doc":
            self.base_url = os.getenv("DOC_QDRANT_URL", "http://10.0.0.12:6333")
        else:
            raise ValueError(f"Unknown source type: {source_type}")
        
        # HTTP 클라이언트 설정
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(config.http_timeout_ms / 1000.0),
            limits=httpx.Limits(
                max_keepalive_connections=config.http_max_keepalive,
                max_connections=config.http_max_keepalive * 2,
                keepalive_expiry=30.0
            )
        )
        
        self.circuit_breaker = CircuitBreaker(f"qdrant_{source_type}", config)
        
        logger.info(f"🔗 Qdrant Client Pool [{source_type}] → {self.base_url}")
    
    async def search_with_retry(self, collection_name: str, query_vector: List[float], 
                               limit: int = 3, score_threshold: float = 0.3) -> List[Dict]:
        """재시도 정책이 포함된 벡터 검색"""
        for attempt in range(self.config.retry_max):
            start_time = time.time()
            
            try:
                # Circuit Breaker 확인
                if not self.circuit_breaker.should_allow_request():
                    raise Exception(f"Circuit breaker OPEN for Qdrant {self.source_type}")
                
                response = await self._search_qdrant(collection_name, query_vector, limit, score_threshold)
                
                duration_ms = (time.time() - start_time) * 1000
                self.circuit_breaker.record_success(duration_ms)
                return response
                
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                self.circuit_breaker.record_failure(duration_ms, str(e))
                
                if attempt < self.config.retry_max - 1:
                    delay = self.config.retry_backoff_ms * (2 ** attempt) / 1000.0
                    logger.warning(f"🔄 Qdrant {self.source_type} retry {attempt + 1}/{self.config.retry_max} after {delay:.1f}s: {e}")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"❌ Qdrant {self.source_type} failed after {self.config.retry_max} attempts: {e}")
                    raise
    
    async def _search_qdrant(self, collection_name: str, query_vector: List[float], 
                           limit: int, score_threshold: float) -> List[Dict]:
        """실제 Qdrant API 호출"""
        try:
            response = await self.client.post(
                f"/collections/{collection_name}/points/search",
                json={
                    "vector": query_vector,
                    "limit": limit,
                    "score_threshold": score_threshold,
                    "with_payload": True,
                    "with_vector": False
                }
            )
            response.raise_for_status()
            
            result = response.json()
            return result.get("result", [])
            
        except httpx.TimeoutException:
            raise Exception(f"Qdrant {self.source_type} timeout")
        except httpx.HTTPError as e:
            raise Exception(f"Qdrant {self.source_type} HTTP error: {e}")
        except Exception as e:
            raise Exception(f"Qdrant {self.source_type} API error: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """헬스체크"""
        try:
            start_time = time.time()
            response = await self.client.get("/")
            duration_ms = (time.time() - start_time) * 1000
            
            return {
                "source_type": self.source_type,
                "url": self.base_url,
                "healthy": response.status_code == 200,
                "response_time_ms": duration_ms,
                "circuit_breaker": self.circuit_breaker.get_status()
            }
        except Exception as e:
            return {
                "source_type": self.source_type,
                "url": self.base_url,
                "healthy": False,
                "error": str(e),
                "circuit_breaker": self.circuit_breaker.get_status()
            }
    
    async def cleanup(self):
        """리소스 정리"""
        await self.client.aclose()

class ResourceManager:
    """
    통합 리소스 관리자 - 현실적 설계
    - Ollama: 단일 인스턴스 + 토큰 버킷
    - Qdrant: HTTP 클라이언트 풀링
    - Circuit Breaker: 운영 지표 기반
    """
    
    def __init__(self, config: Optional[ResourceConfig] = None):
        self.config = config or ResourceConfig()
        
        # Ollama 토큰 버킷
        self.ollama_bucket = OllamaTokenBucket(self.config)
        
        # Qdrant 클라이언트 풀
        self.qdrant_pools: Dict[str, QdrantClientPool] = {}
        for source_type in ["mail", "doc"]:
            try:
                self.qdrant_pools[source_type] = QdrantClientPool(source_type, self.config)
            except Exception as e:
                logger.error(f"❌ Failed to initialize Qdrant pool for {source_type}: {e}")
        
        logger.info(f"🎛️ ResourceManager initialized with realistic design")
        logger.info(f"   📊 Ollama concurrency: {self.config.ollama_max_concurrency}")
        logger.info(f"   🔗 Qdrant pools: {list(self.qdrant_pools.keys())}")
        logger.info(f"   ⏱️ Timeouts: {self.config.http_timeout_ms}ms")
        logger.info(f"   🔄 Retries: {self.config.retry_max} with {self.config.retry_backoff_ms}ms backoff")
    
    async def generate_llm_response(self, prompt: str, model: str = "gemma3:4b") -> str:
        """LLM 응답 생성 (토큰 버킷 + Circuit Breaker)"""
        return await self.ollama_bucket.generate_with_retry(prompt, model)
    
    async def search_vectors(self, source_type: str, collection_name: str, 
                           query_vector: List[float], limit: int = 3, 
                           score_threshold: float = 0.3) -> List[Dict]:
        """벡터 검색 (풀링 + Circuit Breaker)"""
        if source_type not in self.qdrant_pools:
            raise ValueError(f"Unknown source type: {source_type}")
        
        pool = self.qdrant_pools[source_type]
        return await pool.search_with_retry(collection_name, query_vector, limit, score_threshold)
    
    async def get_system_status(self) -> Dict[str, Any]:
        """전체 시스템 상태 반환"""
        status = {
            "timestamp": datetime.now().isoformat(),
            "resource_manager": "v2.0.0-realistic",
            "ollama": await self.ollama_bucket.get_status(),
            "qdrant_pools": {}
        }
        
        for source_type, pool in self.qdrant_pools.items():
            status["qdrant_pools"][source_type] = await pool.health_check()
        
        return status
    
    async def cleanup(self):
        """전체 리소스 정리"""
        logger.info("🧹 ResourceManager cleanup started")
        
        # Ollama 정리
        await self.ollama_bucket.cleanup()
        
        # Qdrant 풀 정리
        for pool in self.qdrant_pools.values():
            await pool.cleanup()
        
        logger.info("✅ ResourceManager cleanup completed")

# 전역 인스턴스 (싱글톤 패턴)
_resource_manager: Optional[ResourceManager] = None

async def get_resource_manager() -> ResourceManager:
    """전역 리소스 매니저 반환"""
    global _resource_manager
    if _resource_manager is None:
        _resource_manager = ResourceManager()
    return _resource_manager

async def cleanup_resources():
    """전역 리소스 정리"""
    global _resource_manager
    if _resource_manager:
        await _resource_manager.cleanup()
        _resource_manager = None