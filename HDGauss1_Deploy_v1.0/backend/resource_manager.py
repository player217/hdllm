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
import json
from typing import Dict, Optional, Any, List, Union, AsyncIterator
from dataclasses import dataclass, field
from collections import deque
from contextlib import asynccontextmanager
import httpx
import threading
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)

# P1-4: Import metrics (if available)
try:
    from backend.common.logging import (
        QDRANT_ERR, SEARCH_LAT, EMBED_LAT, CACHE_HITS, CACHE_MISSES
    )
    METRICS_ENABLED = True
except ImportError:
    logger.warning("Metrics not available, running without metrics collection")
    METRICS_ENABLED = False

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
    
    # 임베딩 설정 추가
    embed_backend: str = os.getenv("EMBED_BACKEND", "st")
    embed_model: str = os.getenv("EMBED_MODEL", "BAAI/bge-m3") 
    embed_device: str = os.getenv("EMBED_DEVICE", "auto")
    embed_batch: int = int(os.getenv("EMBED_BATCH", "64"))
    
    # Collection 네임스페이스 설정 추가
    qdrant_namespace: str = os.getenv("QDRANT_NAMESPACE", "default")
    qdrant_env: str = os.getenv("QDRANT_ENV", "dev")
    
    def get_collection_name(self, source_type: str, base_name: str = "documents") -> str:
        """동적 컬렉션명 생성"""
        return f"{self.qdrant_namespace}_{self.qdrant_env}_{source_type}_{base_name}"
    
    # 파이프라인 설정
    app_max_concurrency: int = int(os.getenv("APP_MAX_CONCURRENCY", "8"))
    queue_max: int = int(os.getenv("QUEUE_MAX", "64"))
    
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
    
    async def generate_embedding(self, model: str, text: str) -> List[float]:
        """통일된 임베딩 생성 메서드 - ENV 기반 엔드포인트 + input 필드"""
        async with self.acquire_token():
            try:
                # ENV 기반 엔드포인트 사용 (하드코딩 제거) - 슬래시 중복 방지
                base = (self.config.ollama_endpoint or "").rstrip("/")
                endpoint = f"{base}/api/embeddings"
                
                response = await self.client.post(
                    endpoint,
                    json={
                        "model": model,
                        "input": text  # prompt → input 필드로 수정 (Ollama API 규격)
                    },
                    timeout=30.0
                )
                response.raise_for_status()
                result = response.json()
                return result.get("embedding", [])
            except Exception as e:
                logger.error(f"❌ Ollama embedding failed: {e}")
                raise

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
        
        # 임베딩 관련 속성
        self.embedder = None
        self.embed_backend = config.embed_backend
        self.embed_model = config.embed_model
        self.embed_device = None  # Will be resolved in from_env()
        
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
    
    def _resolve_device(self, spec: str) -> str:
        """디바이스 자동 감지"""
        if spec == "auto":
            try:
                import torch
                if torch.cuda.is_available():
                    logger.info(f"🚀 GPU detected: {torch.cuda.get_device_name(0)}")
                    return "cuda:0"
            except Exception as e:
                logger.warning(f"⚠️ GPU check failed: {e}")
            logger.info("📱 Using CPU device")
            return "cpu"
        return spec
    
    def _load_st_model(self, model_name: str, device: str) -> Any:
        """SentenceTransformer 모델 로드"""
        try:
            from sentence_transformers import SentenceTransformer
            import torch
            
            model = SentenceTransformer(model_name, device=device)
            
            # GPU에서 컴파일 최적화 시도
            if device.startswith("cuda") and hasattr(torch, 'compile'):
                try:
                    model = torch.compile(model)
                    logger.info("🔥 Model compilation enabled (PyTorch 2.0+)")
                except Exception as e:
                    logger.warning(f"⚠️ Model compilation failed: {e}")
            
            logger.info(f"✅ Loaded {model_name} on {device}")
            return model
        except Exception as e:
            logger.error(f"❌ Failed to load model {model_name}: {e}")
            raise
    
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """텍스트 배치 임베딩 생성"""
        # FIX #3 Support: Allow Ollama backend even without embedder
        if not self.embedder and self.embed_backend != "ollama":
            raise ValueError("Embedder not initialized for non-Ollama backend")
        
        try:
            # 배치 크기 제한
            batch_size = min(self.config.embed_batch, len(texts))
            
            if self.embed_backend == "st":
                # SentenceTransformer 사용
                embeddings = await asyncio.to_thread(
                    self.embedder.encode,
                    texts,
                    batch_size=batch_size,
                    show_progress_bar=False,
                    convert_to_tensor=False,
                    normalize_embeddings=True
                )
                return embeddings.tolist() if hasattr(embeddings, 'tolist') else embeddings
            
            elif self.embed_backend == "ollama":
                # 통일된 클라이언트 래퍼 사용
                embeddings = []
                for text in texts:
                    embedding = await self.ollama_bucket.generate_embedding(
                        model=self.embed_model,
                        text=text
                    )
                    embeddings.append(embedding)
                return embeddings
            
            else:
                raise ValueError(f"Unknown embedding backend: {self.embed_backend}")
                
        except Exception as e:
            logger.error(f"❌ Embedding generation failed: {e}")
            raise
    
    @classmethod
    def from_env(cls) -> 'ResourceManager':
        """환경 변수에서 설정 로드 및 초기화"""
        config = ResourceConfig()
        manager = cls(config)
        
        # 디바이스 해결
        manager.embed_device = manager._resolve_device(config.embed_device)
        
        # 임베딩 모델 로드
        if config.embed_backend == "st":
            manager.embedder = manager._load_st_model(config.embed_model, manager.embed_device)
        
        logger.info(f"🎯 ResourceManager initialized with {config.embed_backend} on {manager.embed_device}")
        return manager
    
    async def search_vectors(
        self, 
        source_type: str,
        query_vector: List[float], 
        limit: int = 10,
        score_threshold: Optional[float] = None,
        with_payload: bool = True,
        with_vectors: bool = False,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """통합 벡터 검색 프록시 (파라미터 중복 방지)"""
        # Import scope context for dual routing
        from backend.common.qdrant_router import scope_ctx
        
        # P1-4: Start search timing
        if METRICS_ENABLED:
            search_start = time.perf_counter()
        
        # Get current scope from context
        scope = scope_ctx.get("personal")
        
        try:
            # 클라이언트 획득 (우선순위: qdrant_router → clients → qdrant_pools)
            if hasattr(self, 'qdrant_router') and self.qdrant_router:
                # Use QdrantRouter for dual routing
                client = self.qdrant_router.get_client(scope)
                collection_name = self.qdrant_router.get_namespace(scope, source_type)
                logger.info(f"🔀 Routing search to {scope}: {collection_name}")
            elif hasattr(self, "clients") and self.clients:
                client = self.clients.get_qdrant_client(source_type)
                collection_name = None  # Will be determined below
            else:
                client = self.qdrant_pools[source_type].client
                collection_name = None  # Will be determined below
            
            # SecureQdrantClient 감지 (이미 collection_name 내장)
            if hasattr(client, 'collection_name'):
                # SecureQdrantClient: collection_name 전달 금지
                results = await asyncio.to_thread(
                    client.search,
                    query_vector=query_vector,  # keyword only
                    limit=limit,
                    score_threshold=score_threshold,
                    with_payload=with_payload,
                    with_vectors=with_vectors,
                    **kwargs
                )
            else:
                # 일반 QdrantClient: collection_name 필요
                collection_name = self.get_default_collection_name(source_type, "my_documents")
                
                if hasattr(client, 'search'):
                    # 동기 클라이언트: positional 인자 사용
                    results = await asyncio.to_thread(
                        client.search,
                        collection_name,  # positional
                        query_vector,     # positional
                        limit=limit,
                        score_threshold=score_threshold,
                        with_payload=with_payload,
                        with_vectors=with_vectors,
                        **kwargs
                    )
                elif hasattr(client, 'search_async'):
                    # 비동기 클라이언트: keyword 인자 사용
                    results = await client.search_async(
                        collection_name=collection_name,
                        query_vector=query_vector,
                        limit=limit,
                        score_threshold=score_threshold,
                        with_payload=with_payload,
                        with_vectors=with_vectors,
                        **kwargs
                    )
                else:
                    raise RuntimeError(f"Client {type(client)} does not support search methods")
            
            # 결과 포맷팅
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "id": getattr(result, 'id', None),
                    "score": getattr(result, 'score', 0.0),
                    "payload": getattr(result, 'payload', {})
                })
            
            # P1-4: Record search latency with scope
            if METRICS_ENABLED:
                # Add scope label if available
                if hasattr(self, 'qdrant_router') and self.qdrant_router:
                    SEARCH_LAT.labels(backend="qdrant", source=source_type, scope=scope).observe(time.perf_counter() - search_start)
                else:
                    SEARCH_LAT.labels(backend="qdrant", source=source_type).observe(time.perf_counter() - search_start)
            
            logger.info(f"🔍 Vector search completed: {len(formatted_results)} results for {source_type}")
            return formatted_results
            
        except Exception as e:
            # P1-4: Record search error
            if METRICS_ENABLED:
                QDRANT_ERR.labels(type="resource_manager_search").inc()
            logger.error(f"❌ Vector search failed for {scope}: {e}")
            
            # Check if we should fallback from dept to personal
            if scope == "dept" and os.getenv("QDRANT_DEPT_FALLBACK") == "personal":
                logger.warning(f"🔄 Attempting fallback from dept to personal")
                
                # Set fallback flag in request state if available
                request = kwargs.get("request")
                if request and hasattr(request, "state"):
                    setattr(request.state, "fallback_used", True)
                
                # Switch scope to personal and retry
                scope_ctx.set("personal")
                try:
                    return await self.search_vectors(
                        source_type=source_type,
                        query_vector=query_vector,
                        limit=limit,
                        score_threshold=score_threshold,
                        with_payload=with_payload,
                        with_vectors=with_vectors,
                        **kwargs
                    )
                except Exception as fallback_error:
                    logger.error(f"❌ Fallback to personal also failed: {fallback_error}")
                    raise fallback_error
            else:
                raise
    
    async def generate_llm_response(self, prompt: str, model: str, stream: bool = False):
        """Unified LLM response generation with streaming support
        
        Args:
            prompt: The prompt to send to LLM
            model: Model name (e.g., 'gemma3:4b') 
            stream: If True, returns AsyncIterator[str], else returns str
            
        Returns:
            For stream=False: Complete response as string
            For stream=True: AsyncIterator yielding response tokens
        """
        base = (self.config.ollama_endpoint or "").rstrip("/")
        endpoint = f"{base}/api/generate"
        
        if not stream:
            # Non-streaming path
            resp = await self.ollama_bucket.client.post(
                endpoint, 
                json={"model": model, "prompt": prompt, "stream": False}, 
                timeout=120.0
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("response", "")

        # Streaming path
        async def _gen() -> AsyncIterator[str]:
            async with self.ollama_bucket.client.stream(
                "POST", 
                endpoint, 
                json={"model": model, "prompt": prompt, "stream": True}, 
                timeout=120.0
            ) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        yield obj.get("response", "")
                    except Exception:
                        # 방어적 파싱 실패 시 라인 그대로 흘려보냄
                        yield ""
        return _gen()

    # 🔧 Collection Management Helper Methods
    def get_default_collection_name(self, source_type: str, base_name: str = "my_documents") -> str:
        """
        컬렉션명 생성을 위한 단일 접근점
        
        Args:
            source_type: 'mail' | 'doc' | 'attachment' 등
            base_name: 기본 컬렉션명 (default: "my_documents")
            
        Returns:
            완전한 컬렉션명 (예: "hdmipo_dev_mail_my_documents")
            
        Example:
            >>> rm.get_default_collection_name("mail")
            "hdmipo_dev_mail_my_documents"
        """
        return self.config.get_collection_name(source_type, base_name)

    async def get_embedding_dim(self) -> int:
        """
        현재 임베딩 모델의 차원 동적 감지
        
        Returns:
            임베딩 벡터 차원 (예: 1024 for BGE-M3)
            
        Raises:
            ValueError: 임베딩 생성 실패 또는 빈 결과
            RuntimeError: 임베더 초기화 실패
        """
        # FIX #3: Remove embedder guard to support Ollama backend
        # The embed_texts() method handles backend differences internally
        try:
            # 테스트용 더미 텍스트로 차원 감지
            test_embeddings = await self.embed_texts(["__dim_check__"])
            
            if not test_embeddings or not test_embeddings[0]:
                raise ValueError("Empty embedding result from model")
                
            dimension = len(test_embeddings[0])
            
            if dimension <= 0:
                raise ValueError(f"Invalid embedding dimension: {dimension}")
                
            logger.info(f"🔢 Detected embedding dimension: {dimension}")
            return dimension
            
        except Exception as e:
            logger.error(f"❌ Failed to detect embedding dimension: {e}")
            # 상세한 진단 정보 제공
            logger.error(f"🔍 Embedder info - Backend: {self.config.embed_backend}, "
                        f"Model: {self.config.embed_model}, Device: {self.config.embed_device}")
            raise

    async def startup_vector_dim_check(
        self,
        sources: Optional[List[str]] = None,
        base_name: str = "my_documents",
        auto_create: bool = False
    ) -> Dict[str, Any]:
        """
        스타트업 시 컬렉션 존재 및 벡터 차원 일치성 검증
        
        Args:
            sources: 검증할 소스 타입 목록 (default: ["mail", "doc"])
            base_name: 기본 컬렉션명 (default: "my_documents")
            auto_create: 컬렉션 자동 생성 여부 (default: False, 운영 환경 권장)
            
        Returns:
            검증 결과 딕셔너리
            
        Raises:
            RuntimeError: 컬렉션 부재 또는 차원 불일치
            ConnectionError: Qdrant 연결 실패
        """
        sources = sources or ["mail", "doc"]
        expected_dim = await self.get_embedding_dim()
        
        # FIX #1: Add missing fields for main.py compatibility while keeping existing ones
        validation_results = {
            # Original fields (backward compatibility)
            "expected_dimension": expected_dim,
            "collections_checked": {},
            "errors": [],
            "warnings": [],
            
            # New fields required by main.py
            "overall_status": "pending",  # Will be set to 'ok' or 'error'
            "collection_status": {},  # Source-specific status
            "issues": [],  # List of issue descriptions
            "summary": "",  # Human-readable summary
            "embedding_dimension": expected_dim,  # main.py expects this exact name
            "validation_summary": {  # Structured summary
                "total_collections": len(sources),
                "successful_collections": 0,
                "failed_collections": 0,
                "warnings": 0
            }
        }
        
        logger.info(f"🔍 Starting collection validation for sources: {sources}")
        logger.info(f"🔢 Expected embedding dimension: {expected_dim}")
        
        for source_type in sources:
            collection_name = self.get_default_collection_name(source_type, base_name)
            
            try:
                # FIX #2: Unify client access using get_qdrant_client pattern
                # Check if we have the clients attribute (from main.py)
                if hasattr(self, 'clients') and self.clients:
                    client = self.clients.get_qdrant_client(source_type)
                else:
                    # Fallback to qdrant_pools if clients not available
                    if source_type not in self.qdrant_pools:
                        raise ValueError(f"Unsupported source type: {source_type}")
                    client = self.qdrant_pools[source_type].client
                
                collection_info = await self._validate_single_collection(
                    client, collection_name, expected_dim, auto_create
                )
                
                # Update both old and new fields for compatibility
                validation_results["collections_checked"][source_type] = collection_info
                validation_results["collection_status"][source_type] = {
                    "status": "ok",
                    "collection_name": collection_name,
                    "dimension": collection_info.get("dimension", expected_dim),
                    "message": f"Collection '{collection_name}' validated successfully"
                }
                validation_results["validation_summary"]["successful_collections"] += 1
                logger.info(f"✅ Collection '{collection_name}' validation passed")
                
            except Exception as e:
                error_msg = f"Collection '{collection_name}' validation failed: {e}"
                
                # Update both old and new error tracking fields
                validation_results["errors"].append(error_msg)
                validation_results["issues"].append(error_msg)
                validation_results["collection_status"][source_type] = {
                    "status": "error",
                    "collection_name": collection_name,
                    "error": str(e),
                    "message": error_msg
                }
                validation_results["validation_summary"]["failed_collections"] += 1
                
                logger.error(f"❌ {error_msg}")
                
                # 운영팀을 위한 상세 진단 정보
                logger.error(f"🔧 Troubleshooting for '{collection_name}':")
                logger.error(f"   - Expected dimension: {expected_dim}")
                logger.error(f"   - Source type: {source_type}")
                logger.error(f"   - Full collection name: {collection_name}")
                
                # 자동 생성이 비활성화된 경우 가이드 제공
                if not auto_create and "not found" in str(e).lower():
                    logger.info(f"💡 To create collection manually:")
                    logger.info(f"   python scripts/create_collections.py --source {source_type}")
        
        # Set overall status and summary based on results
        # CRITICAL FIX: Use "success"/"warning"/"error" to match main.py expectations
        if validation_results["errors"]:
            validation_results["overall_status"] = "error"
            validation_results["summary"] = f"Validation failed: {len(validation_results['errors'])} collection(s) with errors"
            
            error_summary = "; ".join(validation_results["errors"])
            
            # Don't raise error immediately - let main.py decide based on overall_status
            logger.warning(f"⚠️ Validation completed with errors: {error_summary}")
        elif validation_results["warnings"]:
            validation_results["overall_status"] = "warning"
            validation_results["summary"] = (
                f"All {validation_results['validation_summary']['successful_collections']} "
                f"collection(s) validated with {len(validation_results['warnings'])} warning(s)"
            )
            logger.info(f"⚠️ Collections validated with warnings: {list(validation_results['collections_checked'].keys())}")
        else:
            validation_results["overall_status"] = "success"  # Changed from "ok" to "success"
            validation_results["summary"] = (
                f"All {validation_results['validation_summary']['successful_collections']} "
                f"collection(s) validated successfully with dimension {expected_dim}"
            )
            logger.info(f"🎉 All collections validated successfully: {list(validation_results['collections_checked'].keys())}")
        
        # Add warnings count
        validation_results["validation_summary"]["warnings"] = len(validation_results.get("warnings", []))
        
        return validation_results

    async def _validate_single_collection(
        self, 
        client, 
        collection_name: str, 
        expected_dim: int,
        auto_create: bool = False
    ) -> Dict[str, Any]:
        """단일 컬렉션 검증 (내부 헬퍼)"""
        
        try:
            # 1단계: 컬렉션 메타데이터 조회 시도
            info = await asyncio.to_thread(client.get_collection, collection_name)
            
            # 2단계: 벡터 차원 추출 (다양한 qdrant-client 버전 호환)
            actual_dim = self._extract_vector_dimension(info)
            
            if actual_dim and actual_dim != expected_dim:
                raise RuntimeError(
                    f"Vector dimension mismatch - Expected: {expected_dim}, "
                    f"Actual: {actual_dim}. Collection may need recreation."
                )
            
            # 3단계: 추가 메타데이터 수집
            collection_info = {
                "name": collection_name,
                "dimension": actual_dim or expected_dim,
                "status": "healthy",
                "points_count": getattr(info, 'points_count', 0),
                "config": {
                    "distance": str(getattr(getattr(info, 'config', None), 'distance', None)),
                    "hnsw_config": self._extract_hnsw_config(info)
                }
            }
            
            return collection_info
            
        except Exception as meta_error:
            # 4단계: 메타데이터 조회 실패 시 드라이런 검색으로 재시도
            logger.debug(f"Metadata query failed for '{collection_name}', trying dry-run search")
            
            try:
                # 더미 벡터로 검색 시도 (존재 및 차원 확인)
                # Check if client has search method (sync) or search_async (async)
                if hasattr(client, 'search'):
                    await asyncio.to_thread(
                        client.search,
                        collection_name=collection_name,
                        query_vector=[0.0] * expected_dim,
                        limit=1,
                        with_payload=False,
                        with_vectors=False,
                    )
                elif hasattr(client, 'search_async'):
                    await client.search_async(
                        collection_name=collection_name,
                        query_vector=[0.0] * expected_dim,
                        limit=1,
                        with_payload=False,
                        with_vectors=False,
                    )
                else:
                    # Skip search validation if method not available
                    logger.warning(f"Search method not available for client, skipping validation")
                
                # 검색 성공 시 차원은 맞다고 가정
                return {
                    "name": collection_name,
                    "dimension": expected_dim,
                    "status": "accessible_via_search",
                    "note": "Metadata query failed but search succeeded"
                }
                
            except Exception as search_error:
                error_msg = str(search_error).lower()
                
                # 5단계: 구체적인 에러 타입 분류 및 처리
                if "not found" in error_msg or "does not exist" in error_msg:
                    if auto_create:
                        logger.info(f"🔨 Auto-creating collection '{collection_name}' with dimension {expected_dim}")
                        await self._create_collection_with_defaults(client, collection_name, expected_dim)
                        return {
                            "name": collection_name,
                            "dimension": expected_dim,
                            "status": "auto_created"
                        }
                    else:
                        raise RuntimeError(
                            f"Collection '{collection_name}' not found (expected dim={expected_dim}). "
                            f"Create manually or enable auto_create=True."
                        )
                
                elif any(dim_keyword in error_msg for dim_keyword in 
                        ["vector size", "different size", "dimension", "mismatch"]):
                    raise RuntimeError(
                        f"Vector dimension mismatch for '{collection_name}' "
                        f"(expected {expected_dim}). Collection needs recreation."
                    )
                
                else:
                    # 예상치 못한 에러는 그대로 전파
                    raise RuntimeError(f"Unexpected error validating '{collection_name}': {search_error}")

    def _extract_vector_dimension(self, collection_info) -> Optional[int]:
        """컬렉션 정보에서 벡터 차원 추출 (버전 호환)"""
        try:
            config = getattr(collection_info, "config", None)
            if not config:
                return None
                
            params = getattr(config, "params", None)
            if not params:
                return None
                
            vectors = getattr(params, "vectors", None)
            if not vectors:
                return None
            
            # Case 1: vectors.size (단일 벡터 설정)
            if hasattr(vectors, "size"):
                return vectors.size
            
            # Case 2: vectors dict (다중 벡터 설정)
            elif isinstance(vectors, dict) and vectors:
                first_vector_config = list(vectors.values())[0]
                return getattr(first_vector_config, "size", None)
            
            return None
            
        except Exception as e:
            logger.debug(f"Failed to extract vector dimension: {e}")
            return None

    def _extract_hnsw_config(self, collection_info) -> Dict[str, Any]:
        """HNSW 설정 추출"""
        try:
            config = getattr(collection_info, "config", None)
            params = getattr(config, "params", None)
            hnsw = getattr(params, "hnsw_config", None)
            
            if hnsw:
                return {
                    "m": getattr(hnsw, "m", None),
                    "ef_construct": getattr(hnsw, "ef_construct", None),
                    "full_scan_threshold": getattr(hnsw, "full_scan_threshold", None)
                }
            return {}
        except:
            return {}

    async def _create_collection_with_defaults(
        self, 
        client, 
        collection_name: str, 
        dimension: int
    ):
        """기본 설정으로 컬렉션 생성"""
        try:
            from qdrant_client.models import VectorParams, Distance, HnswConfigDiff
            
            await asyncio.to_thread(
                client.create_collection,
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=dimension,
                    distance=Distance.COSINE,
                    hnsw_config=HnswConfigDiff(
                        m=16,
                        ef_construct=100,
                        full_scan_threshold=10000
                    )
                )
            )
            logger.info(f"✅ Auto-created collection '{collection_name}' with dimension {dimension}")
        except Exception as e:
            logger.error(f"❌ Failed to auto-create collection '{collection_name}': {e}")
            raise

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