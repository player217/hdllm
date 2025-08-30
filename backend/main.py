import os
import re
import logging
import json
import uuid
import datetime
import urllib.parse
import time
from collections import deque
from contextlib import asynccontextmanager
from textwrap import dedent
from pathlib import Path
import hashlib

import torch
import requests
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import Response, StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from qdrant_client import QdrantClient, models
from langchain_huggingface import HuggingFaceEmbeddings

# Import GPU acceleration components  
from backend.pipeline.async_pipeline import AsyncPipeline
from backend.common.schemas import AskRequest, IngestRequest
from backend.common.security import cors_kwargs
from backend.common.logging import (
    request_id_ctx, source_ctx, namespace_ctx,
    setup_logging, get_query_hash, set_request_context, clear_request_context,
    # P1-4: Metrics imports
    REQ_COUNT, REQ_LATENCY, RAG_REQ, EMBED_LAT, SEARCH_LAT, QDRANT_ERR,
    CACHE_HITS, CACHE_MISSES, ACTIVE_CONNECTIONS, LLM_TOKENS, prometheus_app
)
from backend.common.config_loader import get_config_loader, QdrantEndpoint

# --------------------------------------------------------------------------
# 1. Enhanced Logging Setup with PII Protection (P1-3)
# --------------------------------------------------------------------------
# Initialize structured logging with PII masking
audit_logger = setup_logging(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format_type=os.getenv("LOG_FORMAT", "json"),
    redact_pii=os.getenv("LOG_REDACT_PII", "true").lower() == "true",
    audit_enabled=os.getenv("SECURITY_AUDIT_ENABLED", "true").lower() == "true"
)

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# 2. 전역 변수 및 설정
# --------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
EMBEDDING_MODEL_DEFAULT_PATH = PROJECT_ROOT / "src" / "bin" / "bge-m3-local"

# 디버그 모드 설정
DEBUG_MODE = os.getenv("RAG_DEBUG", "false").lower() == "true"
VERBOSE_LOGGING = os.getenv("RAG_VERBOSE", "false").lower() == "true"

if DEBUG_MODE:
    logger.setLevel(logging.DEBUG)
    logger.info("🔍 DEBUG MODE ENABLED")
if VERBOSE_LOGGING:
    logger.info("📝 VERBOSE LOGGING ENABLED")

try:
    import pythoncom
    import win32com.client
    WIN_COM_AVAILABLE = True
except ImportError:
    WIN_COM_AVAILABLE = False

class AppConfig:
    """애플리케이션 설정을 관리합니다."""
    def __init__(self):
        # Initialize config loader
        self._config_loader = get_config_loader()
        self._qdrant_endpoints = None
        self._load_qdrant_endpoints()
    
    def _load_qdrant_endpoints(self):
        """Load Qdrant endpoints from JSON configuration"""
        try:
            self._qdrant_endpoints = self._config_loader.get_qdrant_endpoints()
            logger.info(f"✅ Loaded {len(self._qdrant_endpoints)} Qdrant endpoints from JSON config")
        except Exception as e:
            logger.error(f"❌ Failed to load Qdrant endpoints from JSON config: {e}")
            self._qdrant_endpoints = {}
    
    def get_qdrant_endpoint(self, scope: str) -> QdrantEndpoint:
        """Get Qdrant endpoint configuration for specific scope"""
        if self._qdrant_endpoints and scope in self._qdrant_endpoints:
            return self._qdrant_endpoints[scope]
        
        # Fallback to environment variables
        logger.warning(f"⚠️ Using environment variable fallback for {scope} Qdrant endpoint")
        if scope == 'personal':
            return QdrantEndpoint(
                host=os.getenv('QDRANT_PERSONAL_HOST', '127.0.0.1'),
                port=int(os.getenv('QDRANT_PERSONAL_PORT', '6333')),
                timeout=float(os.getenv('QDRANT_PERSONAL_TIMEOUT', '15.0')),
                description='Personal Qdrant (env fallback)'
            )
        elif scope == 'dept':
            return QdrantEndpoint(
                host=os.getenv('QDRANT_DEPT_HOST', '10.150.104.37'),
                port=int(os.getenv('QDRANT_DEPT_PORT', '6333')),
                timeout=float(os.getenv('QDRANT_DEPT_TIMEOUT', '20.0')),
                description='Department Qdrant (env fallback)'
            )
        else:
            # Default fallback
            return QdrantEndpoint(
                host='127.0.0.1',
                port=6333,
                timeout=30.0,
                description=f'Default Qdrant for {scope}'
            )
    
    # Basic application settings
    EMBEDDING_MODEL_PATH: str = str(EMBEDDING_MODEL_DEFAULT_PATH)
    OLLAMA_API_URL: str = os.getenv("RAG_OLLAMA_URL", "http://127.0.0.1:11434/api/chat")
    
    # 컬렉션 네임스페이스 분리 - 보안·분리 설계 핵심
    # Note: Collection names are now dynamically generated via ResourceManager.get_default_collection_name()
    # This provides centralized collection naming and better maintainability
    
    # 레거시 호환성 (JSON 설정으로 대체 예정)
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_SCORE_THRESHOLD: float = 0.30  # Lowered threshold to find more results
    QDRANT_SEARCH_LIMIT: int = 3  # Reduce to 3 for faster processing
    QDRANT_TIMEOUT: float = 30.0
    QDRANT_SEARCH_PARAMS: dict = {
        "hnsw_ef": 128,  # Increase for better accuracy (default: 128)
        "exact": False   # Use approximate search for speed
    }
    
    # 분리된 Qdrant 인스턴스 설정 - JSON 설정으로 대체됨
    @property
    def MAIL_QDRANT_HOST(self) -> str:
        personal_ep = self.get_qdrant_endpoint('personal')
        return personal_ep.host
    
    @property
    def MAIL_QDRANT_PORT(self) -> int:
        personal_ep = self.get_qdrant_endpoint('personal')
        return personal_ep.port
        
    @property
    def MAIL_QDRANT_TIMEOUT(self) -> float:
        personal_ep = self.get_qdrant_endpoint('personal')
        return personal_ep.timeout
    
    @property
    def DOC_QDRANT_HOST(self) -> str:
        dept_ep = self.get_qdrant_endpoint('dept')
        return dept_ep.host
        
    @property 
    def DOC_QDRANT_PORT(self) -> int:
        dept_ep = self.get_qdrant_endpoint('dept')
        return dept_ep.port
        
    @property
    def DOC_QDRANT_TIMEOUT(self) -> float:
        dept_ep = self.get_qdrant_endpoint('dept')
        return dept_ep.timeout
    
    DEFAULT_LLM_MODEL: str = "gemma3:4b"
    LLM_TIMEOUT: int = 60
    GREETINGS: list[str] = ["안녕", "안녕하세요", "ㅎㅇ", "하이", "반가워", "반갑습니다"]

config = AppConfig()
app_state = {}
dialog_cache: deque[tuple[str, str]] = deque(maxlen=3)

# Embedding cache with LRU (Least Recently Used) eviction
# P1-6: Cache size now configurable via environment variable
embedding_cache = {}
MAX_CACHE_SIZE = int(os.getenv("EMBED_CACHE_MAX", "512"))


# --------------------------------------------------------------------------
# 3. FastAPI 생명주기 및 앱 초기화
# --------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 시작 시 모델 및 클라이언트 로드, 종료 시 정리"""
    logger.info("🚀 애플리케이션 시작...")
    logger.info(f"📦 Backend Version: 1.0.4 - Enhanced Security & Stability")
    logger.info(f"🕐 Start Time: {datetime.datetime.now().isoformat()}")
    
    # Step 1: Configuration Validation (Critical for stability)
    try:
        from config_validator import validate_startup_config
        validation_result = validate_startup_config()
        
        if not validation_result.is_valid:
            logger.warning("⚠️ Configuration validation failed, but continuing with defaults")
            for error in validation_result.errors:
                logger.error(f"  - {error}")
        
        if validation_result.applied_defaults:
            logger.info(f"🔧 Applied {len(validation_result.applied_defaults)} default configurations")
            
        logger.info("✅ Configuration validation completed")
    except Exception as e:
        logger.warning(f"⚠️ Configuration validation failed: {e}")
        logger.info("Continuing with existing configuration...")
    
    # P1-6: Enhanced device and batch configuration with GPU support
    device_type = "cuda" if torch.cuda.is_available() else "cpu"
    final_device = os.getenv("EMBED_DEVICE", device_type)
    batch_size = int(os.getenv("EMBED_BATCH", "32"))
    
    # Determine optimal dtype based on device
    dtype_str = os.getenv("EMBED_DTYPE", "float16" if final_device == "cuda" else "float32")
    if dtype_str == "float16" and final_device == "cuda":
        torch_dtype = torch.float16
        logger.info(f"🚀 GPU FP16 acceleration enabled")
    else:
        torch_dtype = torch.float32
    
    logger.info(f"✅ 실행 디바이스: {final_device.upper()} (Batch: {batch_size}, Dtype: {dtype_str})")

    try:
        # HuggingFaceEmbeddings doesn't support torch_dtype directly
        model_kwargs = {
            "device": final_device
        }
        
        # GPU-specific optimizations
        if final_device == "cuda":
            batch_size = int(os.getenv("EMBED_BATCH", "64"))  # Larger batch for GPU
            
        app_state["embeddings"] = HuggingFaceEmbeddings(
            model_name=config.EMBEDDING_MODEL_PATH,
            model_kwargs=model_kwargs,
            encode_kwargs={
                "normalize_embeddings": True,
                "batch_size": batch_size,
                "show_progress_bar": False
            }
        )
        logger.info(f"✅ 임베딩 모델 로드 성공 (device={final_device}, batch={batch_size}, dtype={dtype_str})")
    except Exception as e:
        logger.error(f"❌ 임베딩 모델 로드 실패: {e}", exc_info=True)

    try:
        # 보안 강화된 Qdrant 클라이언트 초기화 (ResourceManager 초기화 후 업데이트됨)
        try:
            from qdrant_security_config import DEFAULT_SECURITY_CONFIG, create_secure_qdrant_clients
            
            app_state["qdrant_security_config"] = DEFAULT_SECURITY_CONFIG
            app_state["qdrant_clients"] = create_secure_qdrant_clients(DEFAULT_SECURITY_CONFIG)
            
            # 연결 상태 확인
            successful_connections = len(app_state["qdrant_clients"])
            logger.info(f"✅ {successful_connections}/2 보안 Qdrant 클라이언트 연결 성공 (임시 설정)")
            logger.info(f"🔐 임시 컬렉션 네임스페이스 분리: {DEFAULT_SECURITY_CONFIG.collection_namespaces}")
            logger.info("ℹ️ ResourceManager 초기화 후 동적 설정으로 업데이트됩니다")
            
        except ImportError:
            logger.error(f"❌ Qdrant 보안 설정 모듈을 찾을 수 없습니다. 기본 클라이언트로 대체합니다.")
            # 기본 클라이언트 설정 (레거시 호환성)
            app_state["qdrant_clients"] = {
                "mail": QdrantClient(host=config.MAIL_QDRANT_HOST, port=config.MAIL_QDRANT_PORT, timeout=15.0),
                "doc": QdrantClient(host=config.DOC_QDRANT_HOST, port=config.DOC_QDRANT_PORT, timeout=20.0)
            }
        except Exception as e:
            logger.error(f"❌ 보안 Qdrant 클라이언트 초기화 실패: {e}")
            # 레거시 대체
            app_state["qdrant_clients"] = {
                "mail": QdrantClient(host=config.MAIL_QDRANT_HOST, port=config.MAIL_QDRANT_PORT),
                "doc": QdrantClient(host=config.DOC_QDRANT_HOST, port=config.DOC_QDRANT_PORT)
            }
        
        # 보안·분리 컬렉션 상태 확인 (ResourceManager 통합)
        if DEBUG_MODE:
            for source_type, client in app_state["qdrant_clients"].items():
                try:
                    collections = client.get_collections()
                    
                    # ResourceManager를 통한 동적 컬렉션명 획득
                    resource_manager = app_state.get("resource_manager")
                    expected_collection = None
                    if resource_manager:
                        try:
                            expected_collection = resource_manager.get_default_collection_name(source_type, "my_documents")
                        except Exception as rm_error:
                            logger.warning(f"Failed to get collection name from ResourceManager: {rm_error}")
                            # Fallback to legacy naming
                            legacy_namespaces = {"mail": "mail_my_documents", "doc": "doc_my_documents"}
                            expected_collection = legacy_namespaces.get(source_type)
                    else:
                        # Legacy fallback
                        legacy_namespaces = {"mail": "mail_my_documents", "doc": "doc_my_documents"}
                        expected_collection = legacy_namespaces.get(source_type)
                    
                    logger.debug(f"📊 {source_type.upper()} Qdrant 컬렉션 상태 (기대: {expected_collection}):")
                    
                    for col in collections.collections:
                        try:
                            info = client.get_collection(col.name)
                            is_expected = "[✅]" if col.name == expected_collection else "[⚠️]"
                            logger.debug(f"  {is_expected} Collection '{col.name}': vectors={info.vectors_count}, indexed={info.indexed_vectors_count}")
                        except:
                            logger.debug(f"  [❌] Collection '{col.name}': info unavailable")
                            
                    # 기대되는 컬렉션이 없는 경우 경고
                    collection_names = [col.name for col in collections.collections]
                    if expected_collection and expected_collection not in collection_names:
                        logger.warning(f"⚠️ Expected collection '{expected_collection}' not found in {source_type} Qdrant")
                        
                except Exception as e:
                    logger.warning(f"  - {source_type} Qdrant 상태 확인 실패: {e}")
    except Exception as e:
        logger.error(f"❌ Qdrant 클라이언트 연결 실패: {e}", exc_info=True)

    # Phase 2A-1: ResourceManager 초기화
    try:
        from backend.resource_manager import get_resource_manager, ResourceManager
        # Use ResourceManager.from_env() for GPU support
        resource_manager = ResourceManager.from_env()
        app_state["resource_manager"] = resource_manager
        logger.info("🎛️ ResourceManager with GPU acceleration initialized")
        
        # Initialize QdrantRouter for dual routing with JSON configuration
        from backend.common.qdrant_router import QdrantRouter, QdrantConfig
        
        # Get endpoints from JSON configuration
        personal_endpoint = config.get_qdrant_endpoint('personal')
        dept_endpoint = config.get_qdrant_endpoint('dept')
        
        logger.info(f"📍 Personal Qdrant: {personal_endpoint.host}:{personal_endpoint.port}")
        logger.info(f"📍 Department Qdrant: {dept_endpoint.host}:{dept_endpoint.port}")
        
        router = QdrantRouter(
            env_name=os.getenv("QDRANT_ENV", "dev"),
            namespace_pattern=os.getenv(
                "NAMESPACE_PATTERN",
                "{scope}_{env}_{source}_my_documents"
            ),
            personal_cfg=QdrantConfig(
                host=personal_endpoint.host,
                port=personal_endpoint.port,
                timeout=personal_endpoint.timeout,
                scope="personal"
            ),
            dept_cfg=QdrantConfig(
                host=dept_endpoint.host,
                port=dept_endpoint.port,
                timeout=dept_endpoint.timeout,
                scope="dept"
            ),
            secure_factory=None  # Will use standard QdrantClient for now
        )
        
        # Store in app state and pass to resource manager
        app_state["qdrant_router"] = router
        resource_manager.qdrant_router = router
        logger.info("🔀 QdrantRouter initialized for dual routing (personal/dept)")
        
        # Phase 2A-1.5: 스타트업 컬렉션 검증 (Fail-Fast 원칙)
        try:
            logger.info("🔍 Starting collection validation (Fail-Fast startup check)...")
            validation_result = await resource_manager.startup_vector_dim_check(
                sources=["mail", "doc"],
                base_name="my_documents",
                auto_create=False  # 프로덕션에서는 자동 생성하지 않음
            )
            
            if validation_result["overall_status"] == "success":
                logger.info("✅ Collection validation passed successfully")
                logger.info(f"📊 Validation summary:")
                for source, info in validation_result["collection_status"].items():
                    if info["status"] == "ok":
                        logger.info(f"  • {source}: Collection exists, dimension={info['dimension']}, vectors={info.get('vector_count', 'N/A')}")
                    else:
                        logger.warning(f"  • {source}: {info['status']} - {info.get('message', '')}")
                        
                # 임베딩 차원 확인
                if "embedding_dimension" in validation_result:
                    logger.info(f"🔢 Detected embedding dimension: {validation_result['embedding_dimension']}")
                    
            elif validation_result["overall_status"] == "warning":
                logger.warning("⚠️ Collection validation completed with warnings")
                logger.warning(f"🚨 Issues found: {len(validation_result.get('issues', []))}")
                for issue in validation_result.get("issues", []):
                    logger.warning(f"  • {issue}")
                logger.info("Application will continue, but some features may be limited")
                
            else:  # error status
                logger.error("❌ Collection validation FAILED - Application startup aborted")
                logger.error(f"🚨 Critical issues found: {len(validation_result.get('issues', []))}")
                for issue in validation_result.get("issues", []):
                    logger.error(f"  • {issue}")
                
                # Fail-Fast: 컬렉션 문제 시 애플리케이션 시작 중단
                raise RuntimeError(
                    f"Collection validation failed: {validation_result.get('summary', 'Unknown error')}. "
                    "Please check Qdrant setup and collection configuration."
                )
                
        except Exception as collection_error:
            logger.error(f"❌ Collection validation error: {collection_error}")
            if "Collection validation failed" in str(collection_error):
                # 검증 실패는 치명적 오류로 처리
                raise
            else:
                # 기타 오류는 경고로 처리하고 계속 진행
                logger.warning("⚠️ Collection validation encountered an error, continuing with legacy behavior")
                logger.warning("This may cause runtime failures during RAG operations")
        
        # Phase 2A-2: AsyncPipeline 초기화
        app_state["async_pipeline"] = AsyncPipeline(
            resource_manager=resource_manager,
            max_concurrent=resource_manager.config.app_max_concurrency,
            max_queue_size=resource_manager.config.queue_max
        )
        
        # 큐 시스템 시작 (중요: 워커들이 작업을 처리할 수 있도록)
        await app_state["async_pipeline"].start_queue()
        logger.info("🚀 AsyncPipeline with TaskQueue system initialized")
        
        # Phase 2A-3: ResourceManager 기반 보안 설정 업데이트
        try:
            from qdrant_security_config import create_default_security_config, create_secure_qdrant_clients
            
            # ResourceManager를 사용하여 동적 보안 설정 생성
            updated_security_config = create_default_security_config(resource_manager)
            app_state["qdrant_security_config"] = updated_security_config
            
            # 새로운 설정으로 Qdrant 클라이언트 재생성
            updated_clients = create_secure_qdrant_clients(updated_security_config)
            app_state["qdrant_clients"] = updated_clients
            
            # P1-2 전 임시 bridge: ResourceManager에 clients 연결
            class _ClientRegistry:
                def __init__(self, clients_map):
                    self._clients = clients_map
                def get_qdrant_client(self, source):
                    return self._clients.get(source)
            
            resource_manager.clients = _ClientRegistry(updated_clients)
            
            logger.info("✅ ResourceManager 기반 보안 설정으로 업데이트 완료")
            logger.info(f"🔐 동적 컬렉션 네임스페이스: {updated_security_config.collection_namespaces}")
            
        except Exception as security_update_error:
            logger.warning(f"⚠️ 보안 설정 업데이트 실패: {security_update_error}")
            logger.info("기존 설정을 유지합니다")
        
    except ImportError:
        logger.warning("⚠️ ResourceManager not available - using legacy approach")
    except Exception as e:
        logger.error(f"❌ ResourceManager initialization failed: {e}")
        # ResourceManager 초기화 실패는 애플리케이션 시작을 중단
        raise
    
    yield
    
    logger.info("🌙 애플리케이션 종료...")
    
    # AsyncPipeline TaskQueue 정리
    if "async_pipeline" in app_state:
        try:
            await app_state["async_pipeline"].stop_queue()
            logger.info("✅ TaskQueue stopped gracefully")
        except Exception as e:
            logger.error(f"❌ TaskQueue stop failed: {e}")
    
    # ResourceManager 정리
    if "resource_manager" in app_state:
        try:
            await app_state["resource_manager"].cleanup()
            logger.info("✅ ResourceManager cleanup completed")
        except Exception as e:
            logger.error(f"❌ ResourceManager cleanup failed: {e}")
    
    app_state.clear()
    dialog_cache.clear()

# Initialize base FastAPI app
app = FastAPI(lifespan=lifespan)

# Phase 2A-2: Circuit Breaker Dashboard Integration
try:
    from circuit_breaker_dashboard import router as dashboard_router
    app.include_router(dashboard_router)
    logger.info("🔧 Circuit Breaker Dashboard registered")
except ImportError as e:
    logger.warning(f"⚠️ Circuit Breaker Dashboard not available: {e}")

# Import security configuration (MANDATORY FOR PRODUCTION)
try:
    from security_config import (
        CORS_CONFIG, 
        QuestionRequest, 
        EnhancedPIIMasker,
        get_current_user,
        SecurityMiddleware,
        sanitize_log_message
    )
    SECURITY_ENABLED = True
    logger.info("🛡️ Security module loaded successfully")
except ImportError:
    logger.error("❌ Security module not found! This is a critical security risk")
    logger.warning("⚠️ Falling back to restricted configuration")
    SECURITY_ENABLED = False
    # Use secure CORS configuration from common security module
    CORS_CONFIG = cors_kwargs()

# Phase 3 Integration - Apply comprehensive enhancements
try:
    from integration import create_integrated_app
    
    # Transform app with Phase 3 integration
    app = create_integrated_app(
        existing_app=app,
        enable_security=SECURITY_ENABLED,
        development_mode=DEBUG_MODE
    )
    logger.info("✅ Phase 3 integration applied successfully")
    
    # Legacy middleware for compatibility (already handled in integration)
    PHASE3_INTEGRATED = True
    
except ImportError as e:
    logger.warning(f"Phase 3 integration not available: {e}")
    PHASE3_INTEGRATED = False
    
    # Fallback to legacy configuration with MANDATORY security
    app.add_middleware(CORSMiddleware, **CORS_CONFIG)
    logger.info(f"🔒 CORS middleware configured: {len(CORS_CONFIG['allow_origins'])} origins allowed")
    
    # MANDATORY security middleware (always enabled for protection)
    if SECURITY_ENABLED:
        app.add_middleware(SecurityMiddleware)
        logger.info("🛡️ Security middleware activated")
        
        # Include authentication routes
        try:
            from auth_routes import router as auth_router
            app.include_router(auth_router)
            logger.info("🔑 Authentication routes loaded successfully")
        except ImportError:
            logger.warning("⚠️ Authentication routes not available")
    else:
        logger.error("❌ Running without security middleware - PRODUCTION RISK!")
        logger.warning("Please ensure security_config.py is available")


# --------------------------------------------------------------------------
# 4. Request ID Middleware for correlation (P1-3)
# --------------------------------------------------------------------------
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """
    Request ID middleware for distributed tracing, correlation and metrics (P1-4)
    - Generates or extracts request ID from headers
    - Sets context variables for logging
    - Adds response headers for client correlation
    - Collects HTTP metrics for monitoring
    """
    
    # P1-4: Start timing for latency metrics
    start_time = time.perf_counter()
    
    # Extract or generate request ID
    request_id = request.headers.get("x-request-id")
    if not request_id:
        request_id = str(uuid.uuid4())
    
    # Extract source from query params or path
    source = request.query_params.get("source", "unknown")
    if "/mail" in str(request.url):
        source = "mail"
    elif "/doc" in str(request.url):
        source = "doc"
    
    # Extract scope for dual routing (Header > Query > Default)
    scope = (
        request.headers.get("x-qdrant-scope") or
        request.query_params.get("db_scope") or
        os.getenv("DEFAULT_DB_SCOPE", "personal")
    )
    
    # Validate scope
    if scope not in ["personal", "dept"]:
        logger.warning(f"Invalid scope '{scope}', falling back to personal")
        scope = "personal"
    
    # Set context for logging with scope
    set_request_context(request_id, source, "-", scope)
    
    # Add scope to request state for later use
    request.state.scope = scope
    
    # P1-4: Track active connections
    ACTIVE_CONNECTIONS.inc()
    
    try:
        # Process request
        response = await call_next(request)
        
        # Add correlation headers
        response.headers["x-request-id"] = request_id
        response.headers["x-response-source"] = source
        response.headers["x-used-scope"] = scope  # Add scope for client verification
        
        # Add fallback header if fallback was used
        if getattr(request.state, "fallback_used", False):
            response.headers["x-fallback-used"] = "true"
        
        # P1-4: Record metrics
        duration = time.perf_counter() - start_time
        path = str(request.url.path)
        method = request.method
        status = response.status_code
        
        # Skip metrics endpoint itself to avoid recursion
        if path != "/metrics":
            REQ_COUNT.labels(method=method, path=path, status=str(status)).inc()
            REQ_LATENCY.labels(method=method, path=path).observe(duration)
        
        # Log access for audit
        if audit_logger.enabled:
            audit_logger.log_access(
                resource=path,
                action=method,
                result="success",
                user_id=request.headers.get("x-user-id")
            )
        
        return response
        
    except Exception as e:
        # P1-4: Record error metrics
        duration = time.perf_counter() - start_time
        path = str(request.url.path)
        method = request.method
        
        if path != "/metrics":
            REQ_COUNT.labels(method=method, path=path, status="500").inc()
            REQ_LATENCY.labels(method=method, path=path).observe(duration)
        
        logger.error(f"Request failed: {str(e)}")
        
        # Log failure for audit
        if audit_logger.enabled:
            audit_logger.log_access(
                resource=path,
                action=method,
                result="error",
                user_id=request.headers.get("x-user-id")
            )
        raise
        
    finally:
        # P1-4: Decrement active connections
        ACTIVE_CONNECTIONS.dec()
        # Clear context
        clear_request_context()


# --------------------------------------------------------------------------
# 5. 핵심 로직 함수 (이전 섹션 4를 5로 변경)
# --------------------------------------------------------------------------

def _get_current_namespace_mapping():
    """현재 ResourceManager 설정에 따른 네임스페이스 매핑을 반환합니다."""
    resource_manager = app_state.get("resource_manager")
    if resource_manager:
        try:
            # ResourceManager를 통한 동적 매핑 생성
            return {
                "mail": resource_manager.get_default_collection_name("mail", "my_documents"),
                "doc": resource_manager.get_default_collection_name("doc", "my_documents")
            }
        except Exception as e:
            logger.warning(f"Failed to get namespace mapping from ResourceManager: {e}")
    
    # Fallback to legacy mapping
    return {
        "mail": "mail_my_documents", 
        "doc": "doc_my_documents"
    }


def format_context(payload: dict) -> str:
    """검색된 컨텍스트를 LLM 프롬프트에 맞게 포맷합니다."""
    source_type = payload.get("source_type")
    raw_text = payload.get("text", "") or payload.get("body", "")
    raw_text = raw_text.strip()
    
    # Limit context length for faster processing
    MAX_CONTEXT_LENGTH = 500
    if len(raw_text) > MAX_CONTEXT_LENGTH:
        raw_text = raw_text[:MAX_CONTEXT_LENGTH] + "..."
    
    if VERBOSE_LOGGING:
        logger.debug(f"format_context - source_type: {source_type}")
        logger.debug(f"format_context - available fields: {list(payload.keys())}")

    if source_type in ["email_body", "email_attachment"]:
        is_attachment = source_type == 'email_attachment'
        attachment_info = f"- 첨부파일명: {payload.get('file_name', 'N/A')}\n" if is_attachment else ""
        
        # [수정] 제목과 날짜를 유연하게 가져오도록 변경
        title = payload.get("mail_subject") or payload.get("subject", "N/A")
        date = payload.get("sent_date") or payload.get("date", "N/A")
        
        if VERBOSE_LOGGING:
            logger.debug(f"format_context - title: {title[:50] if title != 'N/A' else 'N/A'}")
            logger.debug(f"format_context - date: {date}")
            if title == "N/A":
                logger.warning(f"format_context - Missing title field. Available: {list(payload.keys())}")
            if date == "N/A":
                logger.warning(f"format_context - Missing date field. Available: {list(payload.keys())}")

        return dedent(f"""\
            [참고자료: 이메일 {'첨부파일' if is_attachment else '본문'}]
            - 제목: {title}
            - 보낸 사람: {payload.get('sender', 'N/A')}
            - 날짜: {date}
            {attachment_info}- 내용:
            {raw_text}""").strip()
    
    return f"[참고자료: 기타]\n{raw_text}"

async def stream_llm_response(prompt: str, model: str, request_id: str):
    """Stream LLM response via ResourceManager"""
    logger.info(f"[{request_id}] LLM streaming via ResourceManager (model: {model})...")
    
    try:
        rm = app_state["resource_manager"]
        async_gen = await rm.generate_llm_response(prompt, model, stream=True)
        async for token in async_gen:
            # NDJSON/SSE 어떤 형식이든 상위에서 래핑하므로 여기선 텍스트만 토스
            yield token
    except Exception as e:
        logger.error(f"[{request_id}] LLM 스트리밍 실패: {e}")
        yield "답변 생성 중 오류가 발생했습니다."

def search_qdrant(question: str, request_id: str, client: QdrantClient, config: AppConfig, source: str = "mail", request: Request = None) -> tuple[str, list[dict]]:
    """Qdrant에서 관련 문서를 검색합니다."""
    import time
    start_time = time.time()
    
    embeddings = app_state.get("embeddings")
    if not client or not embeddings:
        logger.warning(f"[{request_id}] Qdrant client or embeddings not available")
        return "", []

    # 쿼리 정규화 및 벡터 생성
    normalized_query = question.lower().strip()
    logger.debug(f"[{request_id}] Query normalization: '{question}' -> '{normalized_query}'")
    
    # 특정 키워드 감지 (디버깅용)
    if "르꼬끄" in question:
        logger.info(f"[{request_id}] 🔍 Special keyword '르꼬끄' detected in query")
    
    # Check embedding cache first
    cache_key = hashlib.md5(normalized_query.encode()).hexdigest()
    if cache_key in embedding_cache:
        query_vector = embedding_cache[cache_key]
        logger.debug(f"[{request_id}] 🎯 Using cached embedding for query")
        # P1-4: Record cache hit
        CACHE_HITS.labels(cache_type="embedding").inc()
    else:
        # P1-4: Start embedding timing
        embed_start = time.perf_counter()
        
        # P1-6: Use inference_mode for better performance
        if hasattr(torch, 'inference_mode'):
            with torch.inference_mode():
                query_vector = embeddings.embed_query(normalized_query)
        else:
            query_vector = embeddings.embed_query(normalized_query)
        
        # P1-4: Record embedding latency
        EMBED_LAT.labels(backend="huggingface").observe(time.perf_counter() - embed_start)
        # P1-4: Record cache miss
        CACHE_MISSES.labels(cache_type="embedding").inc()
        
        # Add to cache with size limit
        if len(embedding_cache) >= MAX_CACHE_SIZE:
            # Remove oldest item (simple FIFO for now)
            oldest_key = next(iter(embedding_cache))
            del embedding_cache[oldest_key]
        
        embedding_cache[cache_key] = query_vector
        logger.debug(f"[{request_id}] 💾 Cached new embedding (cache size: {len(embedding_cache)})")
    
    logger.debug(f"[{request_id}] Query vector created - dimension: {len(query_vector)}")

    # 보안·분리 설계: 소스별 전용 컬렉션 검색 (ResourceManager 통합)
    resource_manager = app_state.get("resource_manager")
    if resource_manager:
        try:
            collection_name = resource_manager.get_default_collection_name(source, "my_documents")
            logger.debug(f"[{request_id}] 🏷️ Collection name from ResourceManager: {collection_name}")
        except Exception as e:
            logger.error(f"[{request_id}] ❌ Failed to get collection name from ResourceManager: {e}")
            return "", []
    else:
        # Fallback to legacy naming for backward compatibility
        legacy_namespaces = {"mail": "mail_my_documents", "doc": "doc_my_documents"}
        collection_name = legacy_namespaces.get(source)
        if not collection_name:
            logger.error(f"[{request_id}] ❌ 지원되지 않는 소스 타입: {source}")
            return "", []
        logger.warning(f"[{request_id}] ⚠️ Using legacy collection naming: {collection_name}")
    
    all_hits = []
    try:
        logger.info(f"[{request_id}] 🔎 Searching namespace-separated collection: '{collection_name}' (source: {source})")
        logger.debug(f"[{request_id}] Search params - limit: {config.QDRANT_SEARCH_LIMIT}, threshold: {config.QDRANT_SCORE_THRESHOLD}")
        
        # ResourceManager 통합 검색 사용 (P1-2)
        try:
            import asyncio
            
            # P1-4: Start search timing
            search_start = time.perf_counter()
            
            # ResourceManager의 통합 검색 메서드 사용
            if asyncio.iscoroutinefunction(resource_manager.search_vectors):
                # 비동기 호출을 동기적으로 실행
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    search_results = loop.run_until_complete(
                        resource_manager.search_vectors(
                            source_type=source,
                            query_vector=query_vector,
                            limit=config.QDRANT_SEARCH_LIMIT,
                            score_threshold=config.QDRANT_SCORE_THRESHOLD,
                            with_payload=True,
                            with_vectors=False,
                            search_params=models.SearchParams(**config.QDRANT_SEARCH_PARAMS),
                            request=request
                        )
                    )
                finally:
                    loop.close()
            else:
                search_results = resource_manager.search_vectors(
                    source_type=source,
                    query_vector=query_vector,
                    limit=config.QDRANT_SEARCH_LIMIT,
                    score_threshold=config.QDRANT_SCORE_THRESHOLD,
                    with_payload=True,
                    with_vectors=False,
                    search_params=models.SearchParams(**config.QDRANT_SEARCH_PARAMS),
                    request=request
                )
            
            # P1-4: Record search latency
            SEARCH_LAT.labels(backend="qdrant", source=source).observe(time.perf_counter() - search_start)
            
            # 결과 형식 변환 (ResourceManager 형식 → Qdrant 형식)
            hits = []
            for result in search_results:
                hit = type('ScoredPoint', (), {})()
                hit.id = result.get('id', '')
                hit.score = result.get('score', 0.0)
                hit.payload = result.get('payload', {})
                hits.append(hit)
                
        except Exception as e:
            logger.error(f"ResourceManager search failed, falling back: {e}")
            # P1-4: Record Qdrant error
            QDRANT_ERR.labels(type="search_error").inc()
            # 폴백: 기존 방식 사용
            if hasattr(client, 'search') and hasattr(client, 'config'):
                hits = client.search(
                    query_vector=query_vector,
                    limit=config.QDRANT_SEARCH_LIMIT,
                    score_threshold=config.QDRANT_SCORE_THRESHOLD,
                    search_params=models.SearchParams(**config.QDRANT_SEARCH_PARAMS)
                )
            else:
                hits = client.search(
                    collection_name=collection_name,
                    query_vector=query_vector,
                    limit=config.QDRANT_SEARCH_LIMIT,
                    score_threshold=config.QDRANT_SCORE_THRESHOLD,
                    search_params=models.SearchParams(**config.QDRANT_SEARCH_PARAMS)
                )
        
        if hits:
            logger.info(f"[{request_id}] ✅ Found {len(hits)} hits in '{collection_name}'")
            if DEBUG_MODE:
                for i, hit in enumerate(hits[:5], 1):  # 상위 5개만 상세 로깅
                    logger.debug(f"[{request_id}]   Hit {i}: score={hit.score:.4f}, id={hit.id}")
                    logger.debug(f"[{request_id}]   Metadata keys: {list(hit.payload.keys())}")
                    if VERBOSE_LOGGING:
                        # 메타데이터 일부 출력 (텍스트 제외)
                        meta_preview = {k: v for k, v in hit.payload.items() if k != 'text' and k != 'embedding'}
                        logger.debug(f"[{request_id}]   Metadata preview: {meta_preview}")
        else:
            logger.warning(f"[{request_id}] ⚠️ No hits found in '{collection_name}' (threshold: {config.QDRANT_SCORE_THRESHOLD})")
        
        all_hits.extend(hits)
    except Exception as e:
        logger.error(f"[{request_id}] ❌ 컬렉션 '{collection_name}' 검색 실패: {e}", exc_info=DEBUG_MODE)
        # 보안 강화: 예외 상황에서도 빈 결과 반환
        return "", []

    if not all_hits:
        logger.warning(f"[{request_id}] ❌ No hits found in collection '{collection_name}'")
        return "", []

    # Audit log for vector search
    query_hash = get_query_hash(normalized_query)
    audit_logger.log_search(
        source=source,
        namespace=collection_name,
        query_hash=query_hash,
        limit=config.QDRANT_SEARCH_LIMIT,
        threshold=config.QDRANT_SCORE_THRESHOLD,
        result_count=len(all_hits),
        latency_ms=(time.time() - start_time) * 1000
    )

    # 중복 제거 및 정렬
    logger.info(f"[{request_id}] 📊 Total hits before deduplication: {len(all_hits)}")
    unique_hits = {hit.id: hit for hit in sorted(all_hits, key=lambda x: x.score, reverse=True)}.values()
    logger.info(f"[{request_id}] 📊 Total hits after deduplication: {len(unique_hits)}")
    
    top_hits = sorted(list(unique_hits), key=lambda x: x.score, reverse=True)[:config.QDRANT_SEARCH_LIMIT]
    logger.info(f"[{request_id}] 📊 Final top hits selected: {len(top_hits)}")
    
    # 상세한 검색 결과 출력
    logger.info(f"[{request_id}] " + "=" * 60)
    logger.info(f"[{request_id}] 🔍 QDRANT 검색 결과 상세")
    logger.info(f"[{request_id}] " + "=" * 60)
    
    for i, hit in enumerate(top_hits, 1):
        title = hit.payload.get("mail_subject") or hit.payload.get("subject", "N/A")
        date = hit.payload.get("sent_date") or hit.payload.get("date", "N/A")
        sender = hit.payload.get("sender", "N/A")
        text = hit.payload.get("text", "")
        text_preview = text[:300] + "..." if len(text) > 300 else text
        
        logger.info(f"[{request_id}] 📄 문서 {i}:")
        logger.info(f"[{request_id}]   점수: {hit.score:.4f}")
        logger.info(f"[{request_id}]   제목: {title}")
        logger.info(f"[{request_id}]   발신자: {sender}")
        logger.info(f"[{request_id}]   날짜: {date}")
        logger.info(f"[{request_id}]   텍스트 미리보기:")
        logger.info(f"[{request_id}]   {text_preview}")
        logger.info(f"[{request_id}] " + "-" * 40)
        
        if DEBUG_MODE and hit.score < 0.6:
            logger.warning(f"[{request_id}]   ⚠️ Low score detected: {hit.score:.4f}")

    contexts = [format_context(hit.payload) for hit in top_hits]
    
    # 포맷팅된 컨텍스트 로깅
    if VERBOSE_LOGGING and contexts:
        logger.info(f"[{request_id}] " + "=" * 60)
        logger.info(f"[{request_id}] 📝 포맷팅된 컨텍스트")
        logger.info(f"[{request_id}] " + "=" * 60)
        for i, ctx in enumerate(contexts, 1):
            logger.info(f"[{request_id}] 컨텍스트 {i}:")
            logger.info(f"[{request_id}] {ctx[:500]}..." if len(ctx) > 500 else f"[{request_id}] {ctx}")
            logger.info(f"[{request_id}] " + "-" * 40)
    
    references = []
    for hit in top_hits:
        if source == "mail":
            # 메일 모드: 메일 링크 처리
            link_value = hit.payload.get("link")
            if link_value:
                # Debug logging for link
                logger.info(f"[{request_id}] Found mail link: {link_value[:50]}...")
                
                ref_title = hit.payload.get("mail_subject") or hit.payload.get("subject", "N/A")
                ref_date = hit.payload.get("sent_date") or hit.payload.get("date", "N/A")
                references.append({
                    "title": ref_title,
                    "date": ref_date,
                    "sender": hit.payload.get("sender", "N/A"),
                    "link": link_value,
                    "entry_id": hit.payload.get("entry_id") or hit.payload.get("mail_id"),
                    "display_url": hit.payload.get("display_url"),
                    "type": "mail"
                })
            else:
                logger.warning(f"[{request_id}] No link found in mail payload. Available keys: {list(hit.payload.keys())}")
        else:  # source == "doc"
            # 문서 모드: 파일 경로 처리
            # 파일 경로는 다양한 필드명으로 저장될 수 있음
            file_path = (hit.payload.get("file_path") or 
                        hit.payload.get("document_path") or 
                        hit.payload.get("path") or 
                        hit.payload.get("link"))
            
            if file_path:
                # 문서 제목 추출
                doc_title = (hit.payload.get("title") or 
                           hit.payload.get("document_name") or 
                           hit.payload.get("filename") or 
                           hit.payload.get("name") or 
                           "문서")
                
                # 문서 날짜 추출
                doc_date = (hit.payload.get("created_date") or 
                          hit.payload.get("modified_date") or 
                          hit.payload.get("date") or 
                          "N/A")
                
                references.append({
                    "title": doc_title,
                    "date": doc_date,
                    "path": file_path,
                    "type": "document"
                })

    return "\n\n---\n\n".join(contexts), references


# --------------------------------------------------------------------------
# 5. API 엔드포인트
# --------------------------------------------------------------------------
@app.get("/")
def root():
    """API 루트 엔드포인트 - API 정보 제공"""
    return {
        "name": "Gauss-1 Backend API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "GET /": "API information",
            "GET /health": "Health check",
            "GET /status": "Service status check",
            "POST /ask": "RAG question answering",
            "GET /open_mail": "Open mail in Outlook (Windows only)"
        },
        "description": "HD현대미포 선각기술부 RAG 시스템 백엔드"
    }

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/status")
async def status():
    """보안·분리 설계가 적용된 시스템 상태 확인 (Dual Routing 포함)"""
    import asyncio
    import aiohttp
    
    async def ping_async(url, timeout=1.0):
        """비동기로 서비스 상태를 체크합니다."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                    return response.status == 200
        except Exception:
            return False
    
    # Check if QdrantRouter is available for dual routing
    router = app_state.get("qdrant_router")
    if router:
        # Get aggregated status from router
        router_status = await router.get_aggregated_status()
    else:
        router_status = None
    
    # 기본 서비스 상태 확인 (legacy compatibility)
    ollama_url = config.OLLAMA_API_URL.replace("/api/chat", "/")
    qdrant_mail_url = f"http://{config.MAIL_QDRANT_HOST}:{config.MAIL_QDRANT_PORT}/"
    qdrant_doc_url = f"http://{config.DOC_QDRANT_HOST}:{config.DOC_QDRANT_PORT}/"
    
    basic_results = await asyncio.gather(
        ping_async(ollama_url),
        ping_async(qdrant_mail_url),
        ping_async(qdrant_doc_url),
        return_exceptions=True
    )
    
    # 보안 클라이언트 상태 확인
    security_status = {}
    if "qdrant_clients" in app_state:
        for source_type, client in app_state["qdrant_clients"].items():
            try:
                if hasattr(client, 'health_check'):
                    # SecureQdrantClient 사용
                    health_info = client.health_check()
                    security_status[f"secure_{source_type}"] = {
                        "connected": health_info.get("connection_ok", False),
                        "collection_exists": health_info.get("collection_exists", False),
                        "namespace": health_info.get("collection_namespace", "unknown"),
                        "vectors_count": health_info.get("vectors_count", 0),
                        "security_enabled": True
                    }
                else:
                    # 레거시 클라이언트 사용
                    collections = client.get_collections()
                    security_status[f"legacy_{source_type}"] = {
                        "connected": True,
                        "collections_count": len(collections.collections),
                        "security_enabled": False
                    }
            except Exception as e:
                security_status[f"error_{source_type}"] = {
                    "connected": False,
                    "error": str(e)[:100],  # 에러 메시지 길이 제한
                    "security_enabled": False
                }
    
    # 보안 설정 정보
    security_config_info = {}
    if "qdrant_security_config" in app_state:
        sec_config = app_state["qdrant_security_config"]
        security_config_info = {
            "namespaces_configured": len(sec_config.collection_namespaces),
            "allowed_sources": sec_config.allowed_sources,
            "max_search_limit": sec_config.max_search_limit,
            "audit_logging": sec_config.audit_logging,
            "ssl_enabled": sec_config.enable_ssl
        }
    
    status_response = {
        # 기본 서비스 상태
        "fastapi": True,
        "ollama": basic_results[0] if not isinstance(basic_results[0], Exception) else False,
        "qdrant_mail": basic_results[1] if not isinstance(basic_results[1], Exception) else False,
        "qdrant_doc": basic_results[2] if not isinstance(basic_results[2], Exception) else False,
        
        # 보안·분리 설계 상태
        "security_clients": security_status,
        "security_config": security_config_info,
        "namespace_separation": _get_current_namespace_mapping(),
        
        # 시스템 정보
        "timestamp": datetime.datetime.now().isoformat(),
        "version": "2.0.0-security",
        "phase": "2A-0 보안·분리 설계 적용됨"
    }
    
    # Add dual routing status if available
    if router_status:
        status_response.update(router_status)
    
    return status_response


# --------------------------------------------------------------------------
# P1-4: Metrics endpoint for Prometheus monitoring
# --------------------------------------------------------------------------
@app.get("/metrics")
async def get_metrics(request: Request):
    """
    Prometheus metrics endpoint (P1-4)
    - Security: Only accessible from localhost for security
    - Returns metrics in Prometheus text format
    """
    from prometheus_client import generate_latest
    from fastapi.responses import PlainTextResponse
    
    # Security check: only allow localhost access
    client_host = request.client.host if request.client else None
    if client_host not in ["127.0.0.1", "localhost", "::1"]:
        raise HTTPException(status_code=403, detail="Metrics only accessible from localhost")
    
    # Generate metrics using the registry from logging module
    from backend.common.logging import registry
    metrics = generate_latest(registry)
    
    return PlainTextResponse(content=metrics.decode('utf-8'), media_type="text/plain; version=0.0.4")


@app.post("/open_file")
async def open_file(request: Request):
    """파일 경로를 받아서 파일을 엽니다 (부서 문서용)."""
    try:
        body = await request.json()
        file_path = body.get("file_path", "")
        
        logger.info(f"받은 파일 경로: {file_path}")
        
        if not file_path:
            raise HTTPException(status_code=400, detail="파일 경로가 비어있습니다.")
        
        # Handle various path formats
        # Remove quotes if present
        file_path = file_path.strip('"').strip("'")
        
        # Handle file:// URLs
        if file_path.startswith('file:///'):
            # Convert file:///C:/path to C:/path
            file_path = file_path[8:]  # Remove 'file:///'
        elif file_path.startswith('file://'):
            # Convert file://path to path
            file_path = file_path[7:]  # Remove 'file://'
        
        # Convert forward slashes to backslashes for Windows
        if os.name == 'nt':
            file_path = file_path.replace('/', '\\')
        
        logger.info(f"처리된 파일 경로: {file_path}")
        
        # Check if file exists
        if os.path.exists(file_path):
            if os.name == 'nt':
                # Windows에서 os.startfile 사용
                os.startfile(file_path)
                logger.info(f"파일 열기 성공: {file_path}")
                return {"status": "success", "message": "파일을 열었습니다."}
            else:
                # Non-Windows 시스템에서는 지원하지 않음
                raise HTTPException(status_code=501, detail="파일 열기는 Windows 환경에서만 지원됩니다.")
        else:
            logger.error(f"파일을 찾을 수 없습니다: {file_path}")
            raise HTTPException(status_code=404, detail=f"파일을 찾을 수 없습니다: {file_path}")
                
    except HTTPException:
        # HTTPException은 그대로 다시 발생
        raise
    except Exception as e:
        logger.error(f"파일 열기 실패: {e}")
        raise HTTPException(status_code=500, detail=f"파일 열기 중 오류 발생: {str(e)}")

@app.post("/open-mail")
async def open_mail(request: Request):
    """통합된 메일/파일 열기 엔드포인트 (POST 방식)"""
    import webbrowser
    
    body = await request.json()
    
    # 다양한 키 이름 지원
    entry_id = body.get("entry_id") or body.get("id") or body.get("link_key", "")
    display_url = body.get("display_url") or body.get("link") or body.get("url", "")
    
    # link_key가 있으면 디코딩
    if entry_id:
        entry_id = urllib.parse.unquote(entry_id)
    
    # 1. file:/// 스키마 처리
    if entry_id and entry_id.startswith("file:///"):
        try:
            path = urllib.parse.unquote(entry_id[8:])
            if os.path.exists(path):
                os.startfile(path)
                return {"ok": True, "via": "file", "path": path}
            else:
                raise FileNotFoundError(f"파일을 찾을 수 없습니다: {path}")
        except Exception as e:
            logger.error(f"파일 열기 실패: {e}")
            raise HTTPException(status_code=400, detail=str(e))
    
    # 2. HTTP(S) 웹 링크 처리
    if display_url and display_url.startswith(("http://", "https://")):
        try:
            webbrowser.open(display_url)
            return {"ok": True, "via": "web", "url": display_url}
        except Exception as e:
            logger.error(f"웹 링크 열기 실패: {e}")
    
    # 3. outlook:// 스키마 처리
    if entry_id and entry_id.startswith("outlook://"):
        if not WIN_COM_AVAILABLE:
            raise HTTPException(status_code=501, detail="Outlook 연동이 필요합니다(Windows/pywin32).")
        
        pythoncom.CoInitialize()
        try:
            mapi_id = entry_id[10:]  # outlook:// 제거
            outlook = win32com.client.Dispatch("Outlook.Application")
            mapi_ns = outlook.GetNamespace("MAPI")
            item = mapi_ns.GetItemFromID(mapi_id)
            item.Display(True)
            return {"ok": True, "via": "outlook", "entry_id": mapi_id}
        except Exception as e:
            logger.error(f"Outlook 메일 열기 실패: {e}")
            raise HTTPException(status_code=500, detail=f"Outlook 메일 열기 실패: {e}")
        finally:
            pythoncom.CoUninitialize()
    
    # 4. 일반 EntryID 처리 (outlook:// 없이)
    if entry_id and not entry_id.startswith(("file://", "http://", "https://")):
        if not WIN_COM_AVAILABLE:
            raise HTTPException(status_code=501, detail="Outlook 연동이 필요합니다(Windows/pywin32).")
        
        pythoncom.CoInitialize()
        try:
            outlook = win32com.client.Dispatch("Outlook.Application")
            mapi_ns = outlook.GetNamespace("MAPI")
            item = mapi_ns.GetItemFromID(entry_id)
            item.Display(True)
            return {"ok": True, "via": "mapi", "entry_id": entry_id}
        except Exception as e:
            logger.error(f"MAPI 메일 열기 실패: {e}")
            raise HTTPException(status_code=500, detail=f"MAPI 메일 열기 실패: {e}")
        finally:
            pythoncom.CoUninitialize()
    
    # 아무것도 제공되지 않은 경우
    raise HTTPException(status_code=400, detail="entry_id 또는 display_url이 필요합니다.")

@app.post("/ask")
async def ask(ask_request: AskRequest, request: Request):
    """GPU 가속 RAG 답변을 스트리밍합니다."""
    request_id = ask_request.request_id
    logger.info(f"🚀 GPU RAG REQUEST START: {request_id}")

    try:
        # P1-4: Start RAG timing
        rag_start = time.perf_counter()
        
        # AsyncPipeline 사용 여부 확인
        async_pipeline = app_state.get("async_pipeline")
        if async_pipeline:
            # GPU 가속 경로
            result = await ask_with_gpu_acceleration(ask_request, async_pipeline, request)
            # P1-4: Record successful RAG request
            RAG_REQ.labels(source=ask_request.source.value, result="success").inc()
            return result
        else:
            # 레거시 경로 (기존 코드 유지)
            result = await ask_legacy(ask_request, request)
            # P1-4: Record successful RAG request
            RAG_REQ.labels(source=ask_request.source.value, result="success").inc()
            return result
    
    except Exception as e:
        # P1-4: Record failed RAG request
        RAG_REQ.labels(source=ask_request.source.value, result="error").inc()
        logger.error(f"❌ RAG request failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


async def ask_with_gpu_acceleration(ask_request: AskRequest, pipeline: AsyncPipeline, request: Request):
    """GPU 가속을 사용한 새로운 RAG 엔드포인트"""
    request_id = ask_request.request_id
    
    # 인사말 체크
    if any(greet in ask_request.query for greet in config.GREETINGS):
        async def greeting_stream():
            yield json.dumps({
                "status": "completed",
                "content": "안녕하세요! 무엇을 도와드릴까요?", 
                "references": [],
                "metadata": {"request_id": request_id, "gpu_accelerated": True}
            }, ensure_ascii=False)
        return StreamingResponse(greeting_stream(), media_type="application/x-ndjson")
    
    try:
        # GPU 가속 검색 실행
        search_result = await pipeline.run_search(
            query=ask_request.query,
            source_type=ask_request.source.value,
            limit=ask_request.top_k,
            score_threshold=0.3
        )
        
        results = search_result["results"]
        metadata = search_result["metadata"]
        
        logger.info(f"[{request_id}] ⚡ GPU search completed: {metadata['total_time_ms']:.1f}ms on {metadata['device']}")
        
        if not results:
            async def no_context_stream():
                yield json.dumps({
                    "status": "completed",
                    "content": "관련 정보를 찾을 수 없습니다.",
                    "references": [],
                    "metadata": metadata
                }, ensure_ascii=False)
            return StreamingResponse(no_context_stream(), media_type="application/x-ndjson")
        
        # 컨텍스트 구성
        context_parts = []
        references = []
        
        for i, result in enumerate(results[:3], 1):
            payload = result.get("payload", {})
            text = payload.get("text", "")[:500]  # 500자 제한
            
            if ask_request.source.value == "mail":
                subject = payload.get("mail_subject", "제목 없음")
                sender = payload.get("sender", "발송자 미상")
                context_parts.append(f"메일 {i}: {subject}\n발송자: {sender}\n내용: {text}")
                
                references.append({
                    "title": f"{subject} ({sender})",
                    "link": payload.get("link", ""),
                    "type": "mail"
                })
            else:
                doc_name = payload.get("document_name", "문서명 미상")
                context_parts.append(f"문서 {i}: {doc_name}\n내용: {text}")
                
                references.append({
                    "title": doc_name,
                    "link": payload.get("document_path", ""),
                    "type": "document"
                })
        
        context_text = "\n\n".join(context_parts)
        
        # 소스별 프롬프트 생성
        if ask_request.source.value == "mail":
            system_prompt = dedent(f"""\
                당신은 HD현대미포 선각기술부의 메일 검색 비서입니다.
                반드시 한국어로 간결하게 답변하세요.
                
                질문: {ask_request.query}

                참고 메일:
                {context_text}
                
                답변 규칙:
                - 한국어로만 답변
                - 600자 이내로 답변  
                - 불릿 포인트 5개 이내
                - 핵심만 간결하게
                - 참고 메일을 바탕으로 답변
                - 링크, URL, 이메일 주소 포함 금지""")
        else:
            system_prompt = dedent(f"""\
                당신은 HD현대미포 선각기술부의 문서 검색 비서입니다.
                반드시 한국어로 간결하게 답변하세요.
                
                질문: {ask_request.query}

                참고 문서:
                {context_text}
                
                답변 규칙:
                - 한국어로만 답변
                - 600자 이내로 답변
                - 불릿 포인트 5개 이내
                - 핵심만 간결하게
                - 참고 문서를 바탕으로 답변
                - 링크, URL, 파일 경로 포함 금지""")
        
        # ResourceManager를 통한 LLM 응답 생성
        resource_manager = pipeline.resource_manager
        
        async def gpu_accelerated_stream():
            try:
                # LLM 스트리밍 응답
                response = await resource_manager.generate_llm_response(system_prompt, ask_request.model.value)
                
                # 응답을 청크로 나누어 스트리밍
                chunks = response.split()
                for i, chunk in enumerate(chunks):
                    if i == len(chunks) - 1:  # 마지막 청크
                        yield json.dumps({
                            "status": "completed",
                            "content": chunk + " ",
                            "references": references,
                            "metadata": {
                                **metadata,
                                "request_id": request_id,
                                "model": request.model.value,
                                "total_results": len(results)
                            }
                        }, ensure_ascii=False)
                    else:
                        yield json.dumps({
                            "status": "streaming", 
                            "content": chunk + " ",
                            "references": []
                        }, ensure_ascii=False)
                        
            except Exception as e:
                logger.error(f"❌ LLM streaming failed: {e}")
                yield json.dumps({
                    "status": "error",
                    "content": "응답 생성 중 오류가 발생했습니다.",
                    "references": references,
                    "metadata": metadata
                }, ensure_ascii=False)
        
        return StreamingResponse(gpu_accelerated_stream(), media_type="application/x-ndjson")
        
    except Exception as e:
        logger.error(f"❌ GPU RAG failed: {e}")
        error_msg = str(e)  # Capture error message in parent scope
        async def error_stream():
            yield json.dumps({
                "status": "error",
                "content": f"GPU 가속 RAG 처리 중 오류가 발생했습니다: {error_msg}",
                "references": [],
                "metadata": {"request_id": request_id, "error": True}
            }, ensure_ascii=False)
        return StreamingResponse(error_stream(), media_type="application/x-ndjson")


async def ask_legacy(ask_request: AskRequest, request: Request):
    """레거시 RAG 엔드포인트 (GPU 미사용)"""
    request_id = ask_request.request_id
    
    try:
        if not all(k in app_state for k in ["embeddings", "qdrant_clients"]):
            raise HTTPException(status_code=503, detail="서비스가 준비되지 않았습니다.")
        
        logger.info(f"[{request_id}] 📨 Legacy Question: {ask_request.query}")
        logger.info(f"[{request_id}] 📁 Source: {ask_request.source.value}")
        
        client = app_state["qdrant_clients"][ask_request.source.value]
        context_text, references = search_qdrant(ask_request.query, request_id, client, config, ask_request.source.value, request)
        
        if not context_text:
            logger.warning(f"[{request_id}] ⚠️ No context found for question: {ask_request.query}")
        else:
            logger.info(f"[{request_id}] ✅ Context prepared with {len(references)} references")
        
        # source에 따른 메타프롬프트 분리
        if ask_request.source.value == "mail":
            final_prompt = dedent(f"""\
                당신은 HD현대미포 선각기술부의 메일 검색 비서입니다.
                반드시 한국어로 간결하게 답변하세요.
                
                질문: {ask_request.query}

                참고 메일:
                {context_text or "참고 자료 없음"}
                
                답변 규칙:
                - 한국어로만 답변
                - 600자 이내로 답변
                - 불릿 포인트 5개 이내
                - 핵심만 간결하게
                - 참고 메일이 제공된 경우 반드시 해당 내용을 바탕으로 답변
                - 참고 메일이 "참고 자료 없음"인 경우에만 "관련 메일을 찾을 수 없습니다" 응답
                - 중요: 답변에는 링크, URL, 이메일 주소를 절대 포함하지 마세요
                - 중요: "링크", "URL", "http", "mailto" 등의 단어를 답변에 사용하지 마세요""")
        else:  # source == "doc"
            final_prompt = dedent(f"""\
                당신은 HD현대미포 선각기술부의 문서 검색 비서입니다.
                반드시 한국어로 간결하게 답변하세요.
                
                질문: {ask_request.query}

                참고 문서:
                {context_text or "참고 자료 없음"}
                
                답변 규칙:
                - 한국어로만 답변
                - 600자 이내로 답변
                - 불릿 포인트 5개 이내
                - 핵심만 간결하게
                - 참고 문서가 제공된 경우 반드시 해당 내용을 바탕으로 답변
                - 참고 문서가 "참고 자료 없음"인 경우에만 "관련 문서를 찾을 수 없습니다" 응답
                - 중요: 답변에는 링크, URL, 파일 경로를 절대 포함하지 마세요
                - 중요: "링크", "URL", "http", "file://" 등의 단어를 답변에 사용하지 마세요""")

        # Ollama로 전송되는 최종 프롬프트 로깅
        if DEBUG_MODE:
            logger.info(f"[{request_id}] " + "=" * 60)
            logger.info(f"[{request_id}] 📮 OLLAMA 프롬프트")
            logger.info(f"[{request_id}] " + "=" * 60)
            # 프롬프트를 줄 단위로 출력 (너무 길어서)
            prompt_lines = final_prompt.split('\n')
            for line in prompt_lines[:50]:  # 처음 50줄만
                if line.strip():
                    logger.info(f"[{request_id}] {line}")
            if len(prompt_lines) > 50:
                logger.info(f"[{request_id}] ... (총 {len(prompt_lines)}줄, 나머지 생략)")
            logger.info(f"[{request_id}] " + "=" * 60)

        async def response_generator():
            full_answer = ""
            async for chunk in stream_llm_response(final_prompt, ask_request.model.value, request_id):
                full_answer += chunk
                yield json.dumps({"answer_chunk": chunk}) + "\n"
            
            yield json.dumps({"references": references}) + "\n"
            
            # dialog_cache.append((request.query, full_answer))  # Commented out for now
            
            # LLM 최종 답변 로깅
            if DEBUG_MODE:
                logger.info(f"[{request_id}] " + "=" * 60)
                logger.info(f"[{request_id}] 💬 LLM 최종 답변")
                logger.info(f"[{request_id}] " + "=" * 60)
                logger.info(f"[{request_id}] {full_answer}")
                logger.info(f"[{request_id}] " + "=" * 60)

        return StreamingResponse(response_generator(), media_type="application/x-ndjson")

    except Exception as e:
        logger.error(f"[{request_id}] Legacy RAG 엔드포인트에서 오류 발생: {e}", exc_info=True)
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail="An internal server error occurred.")
    finally:
        logger.info(f"--- Legacy RAG REQUEST END: {request_id} ---")


# --------------------------------------------------------------------------
# 6. Qdrant 상태 체크 엔드포인트
# --------------------------------------------------------------------------
@app.get("/api/v2/system/qdrant/status")
async def check_qdrant_status():
    """Qdrant 서버 상태 확인"""
    try:
        from qdrant_client import QdrantClient
        client = QdrantClient(host="127.0.0.1", port=6333, timeout=5.0)
        
        # 컬렉션 목록 가져오기
        collections = client.get_collections()
        collection_count = len(collections.collections) if hasattr(collections, 'collections') else 0
        
        return {
            "connected": True,
            "collections": collection_count,
            "host": "127.0.0.1",
            "port": 6333,
            "status": "online"
        }
    except Exception as e:
        logger.warning(f"Qdrant 연결 실패: {e}")
        return {
            "connected": False,
            "error": str(e),
            "message": "Qdrant 서버에 연결할 수 없습니다. Qdrant가 실행 중인지 확인하세요.",
            "host": "127.0.0.1",
            "port": 6333,
            "status": "offline"
        }

# --------------------------------------------------------------------------
# 7. 서버 실행
# --------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("RAG_PORT", "8080"))  # 기본 포트를 8080으로
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")