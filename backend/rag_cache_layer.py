"""
RAG-Specific Cache Layer for HD현대미포 Gauss-1 RAG System
Author: Claude Code  
Date: 2025-01-26
Description: Phase 2B-1 - RAG 시스템을 위한 전용 캐시 레이어 구현
"""

import json
import hashlib
import logging
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from cache_manager import (
    MultiLevelCacheManager, CacheConfig, CacheVersion, 
    get_cache_manager
)

logger = logging.getLogger(__name__)

@dataclass
class EmbeddingCacheEntry:
    """임베딩 캐시 엔트리"""
    query: str
    embedding: List[float]
    model_name: str
    model_version: str
    created_at: float
    
@dataclass
class SearchResult:
    """검색 결과"""
    query: str
    documents: List[Dict[str, Any]]
    embeddings: List[float]
    similarity_scores: List[float]
    search_params: Dict[str, Any]
    cached: bool = False

@dataclass
class LLMResponse:
    """LLM 응답"""
    prompt: str
    response: str
    model_name: str
    parameters: Dict[str, Any]
    tokens_used: int
    cached: bool = False

class RAGCacheNamespaces:
    """RAG 캐시 네임스페이스 정의"""
    EMBEDDINGS = "rag:embeddings"
    VECTOR_SEARCH = "rag:vector_search"
    LLM_RESPONSES = "rag:llm_responses"
    DOCUMENT_METADATA = "rag:doc_metadata"
    USER_SESSIONS = "rag:user_sessions"
    SYSTEM_CONFIG = "rag:system_config"

class RAGCacheManager:
    """RAG 전용 캐시 관리자"""
    
    def __init__(self):
        self.cache_manager: Optional[MultiLevelCacheManager] = None
        self.embedding_model_version = "bge-m3-v1.0"  # 임베딩 모델 버전
    
    async def initialize(self):
        """RAG 캐시 매니저 초기화"""
        self.cache_manager = await get_cache_manager()
        logger.info("🎯 RAG Cache Manager initialized")
    
    # ============================================================================
    # 임베딩 캐시 관리
    # ============================================================================
    
    async def get_embedding(self, query: str, model_name: str = None) -> Optional[List[float]]:
        """임베딩 캐시에서 조회"""
        model_name = model_name or self.embedding_model_version
        
        # 쿼리 정규화
        normalized_query = self._normalize_query(query)
        cache_key = f"{normalized_query}:{model_name}"
        
        cached_entry = await self.cache_manager.get(
            RAGCacheNamespaces.EMBEDDINGS,
            cache_key,
            version_data={"query": normalized_query, "model": model_name},
            strategy=CacheVersion.CONTENT_HASH
        )
        
        if cached_entry and isinstance(cached_entry, dict):
            logger.debug(f"🎯 Embedding cache HIT: {normalized_query[:50]}...")
            return cached_entry.get("embedding")
        
        logger.debug(f"❌ Embedding cache MISS: {normalized_query[:50]}...")
        return None
    
    async def set_embedding(self, query: str, embedding: List[float], 
                           model_name: str = None, ttl: int = 3600) -> str:
        """임베딩 캐시에 저장"""
        model_name = model_name or self.embedding_model_version
        
        normalized_query = self._normalize_query(query)
        cache_key = f"{normalized_query}:{model_name}"
        
        cache_entry = {
            "query": normalized_query,
            "embedding": embedding,
            "model_name": model_name,
            "model_version": self.embedding_model_version,
            "created_at": datetime.now().timestamp(),
            "embedding_dim": len(embedding)
        }
        
        cached_key = await self.cache_manager.set(
            RAGCacheNamespaces.EMBEDDINGS,
            cache_key,
            cache_entry,
            version_data={"query": normalized_query, "model": model_name},
            strategy=CacheVersion.CONTENT_HASH,
            ttl=ttl
        )
        
        logger.debug(f"💾 Embedding cached: {normalized_query[:50]}...")
        return cached_key
    
    # ============================================================================
    # 벡터 검색 캐시 관리  
    # ============================================================================
    
    async def get_vector_search_result(self, query: str, search_params: Dict[str, Any], 
                                     source: str = "mail") -> Optional[SearchResult]:
        """벡터 검색 결과 캐시 조회"""
        cache_key = self._generate_search_cache_key(query, search_params, source)
        
        cached_result = await self.cache_manager.get(
            RAGCacheNamespaces.VECTOR_SEARCH,
            cache_key,
            version_data={"query": query, "params": search_params},
            strategy=CacheVersion.CONTENT_HASH
        )
        
        if cached_result:
            logger.debug(f"🔍 Vector search cache HIT: {query[:50]}...")
            
            # SearchResult 객체로 변환
            return SearchResult(
                query=cached_result["query"],
                documents=cached_result["documents"],
                embeddings=cached_result.get("embeddings", []),
                similarity_scores=cached_result["similarity_scores"],
                search_params=cached_result["search_params"],
                cached=True
            )
        
        logger.debug(f"❌ Vector search cache MISS: {query[:50]}...")
        return None
    
    async def set_vector_search_result(self, search_result: SearchResult, 
                                     source: str = "mail", ttl: int = 1800) -> str:
        """벡터 검색 결과 캐시 저장"""
        cache_key = self._generate_search_cache_key(
            search_result.query, 
            search_result.search_params, 
            source
        )
        
        cache_entry = {
            "query": search_result.query,
            "documents": search_result.documents,
            "embeddings": search_result.embeddings,
            "similarity_scores": search_result.similarity_scores,
            "search_params": search_result.search_params,
            "source": source,
            "cached_at": datetime.now().timestamp(),
            "result_count": len(search_result.documents)
        }
        
        cached_key = await self.cache_manager.set(
            RAGCacheNamespaces.VECTOR_SEARCH,
            cache_key,
            cache_entry,
            version_data={"query": search_result.query, "params": search_result.search_params},
            strategy=CacheVersion.CONTENT_HASH,
            ttl=ttl
        )
        
        logger.debug(f"💾 Vector search result cached: {search_result.query[:50]}...")
        return cached_key
    
    # ============================================================================
    # LLM 응답 캐시 관리
    # ============================================================================
    
    async def get_llm_response(self, prompt: str, model_name: str, 
                              parameters: Dict[str, Any]) -> Optional[LLMResponse]:
        """LLM 응답 캐시 조회"""
        cache_key = self._generate_llm_cache_key(prompt, model_name, parameters)
        
        cached_response = await self.cache_manager.get(
            RAGCacheNamespaces.LLM_RESPONSES,
            cache_key,
            version_data={"prompt": prompt, "model": model_name, "params": parameters},
            strategy=CacheVersion.CONTENT_HASH
        )
        
        if cached_response:
            logger.debug(f"🤖 LLM response cache HIT: {prompt[:50]}...")
            
            return LLMResponse(
                prompt=cached_response["prompt"],
                response=cached_response["response"],
                model_name=cached_response["model_name"],
                parameters=cached_response["parameters"],
                tokens_used=cached_response.get("tokens_used", 0),
                cached=True
            )
        
        logger.debug(f"❌ LLM response cache MISS: {prompt[:50]}...")
        return None
    
    async def set_llm_response(self, llm_response: LLMResponse, ttl: int = 7200) -> str:
        """LLM 응답 캐시 저장"""
        cache_key = self._generate_llm_cache_key(
            llm_response.prompt,
            llm_response.model_name,
            llm_response.parameters
        )
        
        cache_entry = {
            "prompt": llm_response.prompt,
            "response": llm_response.response,
            "model_name": llm_response.model_name,
            "parameters": llm_response.parameters,
            "tokens_used": llm_response.tokens_used,
            "cached_at": datetime.now().timestamp(),
            "response_length": len(llm_response.response)
        }
        
        cached_key = await self.cache_manager.set(
            RAGCacheNamespaces.LLM_RESPONSES,
            cache_key,
            cache_entry,
            version_data={
                "prompt": llm_response.prompt,
                "model": llm_response.model_name,
                "params": llm_response.parameters
            },
            strategy=CacheVersion.CONTENT_HASH,
            ttl=ttl
        )
        
        logger.debug(f"💾 LLM response cached: {llm_response.prompt[:50]}...")
        return cached_key
    
    # ============================================================================
    # 문서 메타데이터 캐시 관리
    # ============================================================================
    
    async def get_document_metadata(self, document_id: str, source: str) -> Optional[Dict[str, Any]]:
        """문서 메타데이터 캐시 조회"""
        cache_key = f"{source}:{document_id}"
        
        return await self.cache_manager.get(
            RAGCacheNamespaces.DOCUMENT_METADATA,
            cache_key,
            version_data={"doc_id": document_id, "source": source},
            strategy=CacheVersion.INCREMENTAL
        )
    
    async def set_document_metadata(self, document_id: str, source: str, 
                                   metadata: Dict[str, Any], ttl: int = 86400) -> str:
        """문서 메타데이터 캐시 저장"""
        cache_key = f"{source}:{document_id}"
        
        return await self.cache_manager.set(
            RAGCacheNamespaces.DOCUMENT_METADATA,
            cache_key,
            metadata,
            version_data={"doc_id": document_id, "source": source},
            strategy=CacheVersion.INCREMENTAL,
            ttl=ttl
        )
    
    # ============================================================================
    # 사용자 세션 캐시 관리
    # ============================================================================
    
    async def get_user_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """사용자 세션 캐시 조회"""
        return await self.cache_manager.get(
            RAGCacheNamespaces.USER_SESSIONS,
            session_id,
            version_data={"session_id": session_id},
            strategy=CacheVersion.TIMESTAMP
        )
    
    async def set_user_session(self, session_id: str, session_data: Dict[str, Any], 
                              ttl: int = 3600) -> str:
        """사용자 세션 캐시 저장"""
        return await self.cache_manager.set(
            RAGCacheNamespaces.USER_SESSIONS,
            session_id,
            session_data,
            version_data={"session_id": session_id},
            strategy=CacheVersion.TIMESTAMP,
            ttl=ttl
        )
    
    # ============================================================================
    # 캐시 무효화 관리
    # ============================================================================
    
    async def invalidate_embeddings(self, model_name: str = None) -> int:
        """임베딩 모델 변경 시 관련 캐시 무효화"""
        if model_name:
            # 특정 모델의 임베딩만 무효화 - 패턴 기반으로 직접 처리
            deleted_count = 0
            
            # 메모리 캐시에서 패턴 매칭 삭제
            if self.cache_manager.memory_cache:
                pattern = f"{RAGCacheNamespaces.EMBEDDINGS}:.*:{model_name}#v#.*$"
                deleted_count += self.cache_manager.memory_cache.delete_by_pattern(pattern)
            
            # Redis 캐시에서 패턴 매칭 삭제
            if self.cache_manager.redis_cache:
                pattern = f"{RAGCacheNamespaces.EMBEDDINGS}:*:{model_name}*"
                deleted_count += await self.cache_manager.redis_cache.delete_by_pattern(pattern)
            
            logger.info(f"Invalidated embeddings for model {model_name}: {deleted_count} entries")
            return deleted_count
        else:
            # 모든 임베딩 캐시 무효화
            return await self.cache_manager.invalidate_namespace(RAGCacheNamespaces.EMBEDDINGS)
    
    async def invalidate_vector_search(self, source: str = None) -> int:
        """벡터 검색 캐시 무효화"""
        if source:
            # 특정 소스만 무효화 (복잡한 패턴이므로 네임스페이스 전체)
            return await self.cache_manager.invalidate_namespace(RAGCacheNamespaces.VECTOR_SEARCH)
        else:
            return await self.cache_manager.invalidate_namespace(RAGCacheNamespaces.VECTOR_SEARCH)
    
    async def invalidate_llm_responses(self, model_name: str = None) -> int:
        """LLM 응답 캐시 무효화"""
        if model_name:
            # 특정 모델의 응답만 무효화 (복잡한 구현 필요)
            return await self.cache_manager.invalidate_namespace(RAGCacheNamespaces.LLM_RESPONSES)
        else:
            return await self.cache_manager.invalidate_namespace(RAGCacheNamespaces.LLM_RESPONSES)
    
    async def invalidate_user_sessions(self, older_than_hours: int = 24) -> int:
        """오래된 사용자 세션 무효화"""
        # 시간 기반 무효화는 자동 TTL에 의존
        return await self.cache_manager.invalidate_namespace(RAGCacheNamespaces.USER_SESSIONS)
    
    async def invalidate_all_rag_cache(self) -> Dict[str, int]:
        """모든 RAG 캐시 무효화"""
        results = {}
        
        for namespace in [
            RAGCacheNamespaces.EMBEDDINGS,
            RAGCacheNamespaces.VECTOR_SEARCH,
            RAGCacheNamespaces.LLM_RESPONSES,
            RAGCacheNamespaces.DOCUMENT_METADATA,
            RAGCacheNamespaces.USER_SESSIONS
        ]:
            count = await self.cache_manager.invalidate_namespace(namespace)
            results[namespace] = count
        
        logger.info(f"🧹 All RAG cache invalidated: {results}")
        return results
    
    # ============================================================================
    # 통계 및 모니터링
    # ============================================================================
    
    async def get_rag_cache_stats(self) -> Dict[str, Any]:
        """RAG 캐시 통계"""
        base_stats = self.cache_manager.get_stats()
        
        # RAG 특화 통계 추가
        rag_stats = {
            "rag_cache_version": "1.0.0",
            "embedding_model_version": self.embedding_model_version,
            "namespaces": [
                RAGCacheNamespaces.EMBEDDINGS,
                RAGCacheNamespaces.VECTOR_SEARCH,
                RAGCacheNamespaces.LLM_RESPONSES,
                RAGCacheNamespaces.DOCUMENT_METADATA,
                RAGCacheNamespaces.USER_SESSIONS
            ]
        }
        
        return {**base_stats, "rag_specific": rag_stats}
    
    # ============================================================================
    # 내부 유틸리티 함수
    # ============================================================================
    
    def _normalize_query(self, query: str) -> str:
        """쿼리 정규화"""
        # 공백 정리, 소문자 변환, 특수문자 제거
        normalized = query.strip().lower()
        normalized = ' '.join(normalized.split())  # 연속 공백 제거
        return normalized
    
    def _generate_search_cache_key(self, query: str, search_params: Dict[str, Any], 
                                  source: str) -> str:
        """벡터 검색 캐시 키 생성"""
        normalized_query = self._normalize_query(query)
        
        # 검색 파라미터를 정렬된 문자열로 변환
        sorted_params = json.dumps(search_params, sort_keys=True)
        
        key_components = [normalized_query, sorted_params, source]
        combined_key = "|".join(key_components)
        
        # 키가 너무 길면 해시 사용
        if len(combined_key) > 200:
            return hashlib.md5(combined_key.encode()).hexdigest()
        
        return combined_key.replace(" ", "_").replace(":", "_")
    
    def _generate_llm_cache_key(self, prompt: str, model_name: str, 
                               parameters: Dict[str, Any]) -> str:
        """LLM 캐시 키 생성"""
        # 프롬프트 해시 (너무 길 수 있음)
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:16]
        
        # 파라미터 해시
        params_str = json.dumps(parameters, sort_keys=True)
        params_hash = hashlib.md5(params_str.encode()).hexdigest()[:8]
        
        return f"{model_name}:{prompt_hash}:{params_hash}"

# 전역 RAG 캐시 매니저 인스턴스
_rag_cache_manager: Optional[RAGCacheManager] = None

async def get_rag_cache_manager() -> RAGCacheManager:
    """글로벌 RAG 캐시 매니저 인스턴스 반환"""
    global _rag_cache_manager
    
    if _rag_cache_manager is None:
        _rag_cache_manager = RAGCacheManager()
        await _rag_cache_manager.initialize()
    
    return _rag_cache_manager