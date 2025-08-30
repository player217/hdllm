"""
Qdrant Security Configuration Module for HD현대미포 Gauss-1 RAG System
Author: Claude Code
Date: 2025-01-26
Description: 보안·분리 설계를 위한 Qdrant 보안 설정 및 접근 제어
"""

import os
import logging
from typing import Dict, Optional, List
from dataclasses import dataclass
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import UnexpectedResponse

logger = logging.getLogger(__name__)

@dataclass
class QdrantSecurityConfig:
    """Qdrant 보안 설정"""
    # 컬렉션 네임스페이스 분리
    collection_namespaces: Dict[str, str]
    
    # 접근 제어
    allowed_sources: List[str] = None
    max_search_limit: int = 10
    max_timeout: float = 30.0
    
    # 보안 강화
    enable_ssl: bool = False
    api_key: Optional[str] = None
    cert_path: Optional[str] = None
    
    # 감사 로깅
    audit_logging: bool = True
    sensitive_fields: List[str] = None
    
    def __post_init__(self):
        if self.allowed_sources is None:
            self.allowed_sources = ['mail', 'doc']
        if self.sensitive_fields is None:
            self.sensitive_fields = ['text', 'embedding', 'content']

class SecureQdrantClient:
    """
    보안 강화된 Qdrant 클라이언트 래퍼
    - 컬렉션 네임스페이스 분리
    - 접근 제어 및 권한 검증
    - 감사 로깅
    - 민감정보 보호
    """
    
    def __init__(self, source_type: str, config: QdrantSecurityConfig, **client_kwargs):
        self.source_type = source_type
        self.config = config
        
        # 소스 타입 검증
        if source_type not in config.allowed_sources:
            raise ValueError(f"Unauthorized source type: {source_type}")
        
        # 컬렉션 네임스페이스 확인
        self.collection_name = config.collection_namespaces.get(source_type)
        if not self.collection_name:
            raise ValueError(f"No collection namespace defined for source: {source_type}")
        
        # 보안 강화된 클라이언트 초기화
        secure_kwargs = self._apply_security_config(client_kwargs)
        self.client = QdrantClient(**secure_kwargs)
        
        logger.info(f"🔐 Secure Qdrant client initialized for source '{source_type}' -> collection '{self.collection_name}'")
        
    def _apply_security_config(self, client_kwargs: dict) -> dict:
        """보안 설정 적용"""
        secure_kwargs = client_kwargs.copy()
        
        # SSL/TLS 설정
        if self.config.enable_ssl:
            secure_kwargs['https'] = True
            if self.config.cert_path:
                secure_kwargs['cert'] = self.config.cert_path
        
        # API 키 인증
        if self.config.api_key:
            secure_kwargs['api_key'] = self.config.api_key
        
        # 타임아웃 제한
        if 'timeout' not in secure_kwargs or secure_kwargs['timeout'] > self.config.max_timeout:
            secure_kwargs['timeout'] = self.config.max_timeout
            
        return secure_kwargs
    
    def _audit_log(self, operation: str, details: dict = None):
        """감사 로깅"""
        if self.config.audit_logging:
            safe_details = self._sanitize_for_audit(details) if details else {}
            logger.info(f"🔍 AUDIT: {operation} on {self.source_type}.{self.collection_name} - {safe_details}")
    
    def _sanitize_for_audit(self, data: dict) -> dict:
        """감사 로그용 민감정보 제거"""
        if not isinstance(data, dict):
            return {}
        
        sanitized = {}
        for key, value in data.items():
            if key in self.config.sensitive_fields:
                sanitized[key] = f"[REDACTED_{len(str(value))}chars]"
            elif isinstance(value, (str, int, float, bool)):
                sanitized[key] = value
            elif isinstance(value, list):
                sanitized[key] = f"[LIST_{len(value)}items]"
            else:
                sanitized[key] = f"[{type(value).__name__}]"
        
        return sanitized
    
    def search(self, query_vector: List[float], limit: int = None, 
               score_threshold: float = None, **kwargs) -> List:
        """보안 강화된 벡터 검색"""
        
        # 검색 제한 적용
        if limit is None or limit > self.config.max_search_limit:
            limit = self.config.max_search_limit
            logger.warning(f"⚠️ Search limit capped at {self.config.max_search_limit}")
        
        # 감사 로깅
        search_params = {
            "limit": limit,
            "score_threshold": score_threshold,
            "query_vector_dim": len(query_vector)
        }
        self._audit_log("VECTOR_SEARCH", search_params)
        
        try:
            # 네임스페이스 분리된 컬렉션에서만 검색
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=limit,
                score_threshold=score_threshold,
                **kwargs
            )
            
            self._audit_log("SEARCH_SUCCESS", {"results_count": len(results)})
            return results
            
        except UnexpectedResponse as e:
            self._audit_log("SEARCH_ERROR", {"error": str(e)[:200]})
            raise
        except Exception as e:
            self._audit_log("SEARCH_FAILURE", {"error": str(e)[:200]})
            raise
    
    def get_collection_info(self) -> dict:
        """컬렉션 정보 조회 (민감정보 제외)"""
        try:
            info = self.client.get_collection(self.collection_name)
            
            # 민감정보가 아닌 기본 정보만 반환
            safe_info = {
                "name": info.config.name if hasattr(info, 'config') else self.collection_name,
                "status": info.status if hasattr(info, 'status') else 'unknown',
                "vectors_count": info.vectors_count if hasattr(info, 'vectors_count') else 0,
                "indexed_vectors_count": info.indexed_vectors_count if hasattr(info, 'indexed_vectors_count') else 0,
                "points_count": info.points_count if hasattr(info, 'points_count') else 0
            }
            
            self._audit_log("COLLECTION_INFO_ACCESS", {"collection": self.collection_name})
            return safe_info
            
        except Exception as e:
            self._audit_log("COLLECTION_INFO_ERROR", {"error": str(e)[:200]})
            raise
    
    def health_check(self) -> Dict[str, any]:
        """보안된 헬스체크"""
        try:
            # 기본 연결 확인
            collections = self.client.get_collections()
            
            # 전용 컬렉션 존재 확인
            collection_names = [col.name for col in collections.collections]
            collection_exists = self.collection_name in collection_names
            
            health_status = {
                "source_type": self.source_type,
                "collection_namespace": self.collection_name,
                "collection_exists": collection_exists,
                "connection_ok": True,
                "security_config_applied": True
            }
            
            if collection_exists:
                # 컬렉션 기본 정보 추가
                collection_info = self.get_collection_info()
                health_status.update({
                    "vectors_count": collection_info.get("vectors_count", 0),
                    "status": collection_info.get("status", "unknown")
                })
            
            self._audit_log("HEALTH_CHECK", health_status)
            return health_status
            
        except Exception as e:
            error_status = {
                "source_type": self.source_type,
                "collection_namespace": self.collection_name,
                "connection_ok": False,
                "error": str(e)[:200]
            }
            self._audit_log("HEALTH_CHECK_FAILED", error_status)
            return error_status

def create_secure_qdrant_clients(config: QdrantSecurityConfig) -> Dict[str, SecureQdrantClient]:
    """보안 강화된 Qdrant 클라이언트들 생성"""
    clients = {}
    
    for source_type in config.allowed_sources:
        try:
            # 소스별 연결 설정
            if source_type == 'mail':
                client_config = {
                    'host': os.getenv('RAG_MAIL_QDRANT_HOST', '127.0.0.1'),
                    'port': int(os.getenv('RAG_MAIL_QDRANT_PORT', '6333')),
                    'timeout': 15.0,
                    'prefer_grpc': True
                }
            elif source_type == 'doc':
                client_config = {
                    'host': os.getenv('RAG_DOC_QDRANT_HOST', '127.0.0.1'),
                    'port': int(os.getenv('RAG_DOC_QDRANT_PORT', '6333')),
                    'timeout': 20.0,
                    'prefer_grpc': True
                }
            else:
                logger.warning(f"⚠️ Unknown source type: {source_type}")
                continue
            
            clients[source_type] = SecureQdrantClient(source_type, config, **client_config)
            logger.info(f"✅ Secure client created for {source_type}")
            
        except Exception as e:
            logger.error(f"❌ Failed to create secure client for {source_type}: {e}")
    
    return clients

# 동적 보안 설정 생성 함수
def create_default_security_config(resource_manager=None):
    """ResourceManager를 사용하여 동적으로 보안 설정을 생성합니다."""
    collection_namespaces = {}
    
    if resource_manager:
        try:
            # ResourceManager를 통한 동적 컬렉션명 생성
            collection_namespaces = {
                "mail": resource_manager.get_default_collection_name("mail", "my_documents"),
                "doc": resource_manager.get_default_collection_name("doc", "my_documents")
            }
        except Exception as e:
            logger.warning(f"Failed to get collection names from ResourceManager: {e}")
            # Fallback to legacy naming
            collection_namespaces = {
                "mail": "mail_my_documents",
                "doc": "doc_my_documents"
            }
    else:
        # Legacy fallback when ResourceManager is not available
        collection_namespaces = {
            "mail": "mail_my_documents",
            "doc": "doc_my_documents"
        }
    
    return QdrantSecurityConfig(
        collection_namespaces=collection_namespaces,
        allowed_sources=["mail", "doc"],
        max_search_limit=10,
        max_timeout=30.0,
        enable_ssl=False,  # 로컬 환경에서는 비활성화
        api_key=None,      # 환경변수에서 로드하려면 os.getenv('QDRANT_API_KEY')
        audit_logging=True,
        sensitive_fields=["text", "embedding", "content", "original_text"]
    )

# 기본 보안 설정 (Legacy fallback)
DEFAULT_SECURITY_CONFIG = create_default_security_config()