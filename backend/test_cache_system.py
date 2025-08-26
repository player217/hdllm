"""
Cache System Test Suite for HD현대미포 Gauss-1 RAG System
Author: Claude Code
Date: 2025-01-26
Description: Phase 2B-1 - 캐시 키/무효화 명세 (버전 전략) 테스트
"""

import asyncio
import time
import logging
from typing import List, Dict, Any
from cache_manager import (
    CacheConfig, MultiLevelCacheManager, CacheVersion,
    VersionedCacheKey, MemoryCache
)
from rag_cache_layer import (
    RAGCacheManager, SearchResult, LLMResponse,
    RAGCacheNamespaces
)

# 테스트용 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestVersionedCacheKey:
    """캐시 키 버전 관리 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        self.config = CacheConfig()
        self.key_manager = VersionedCacheKey(self.config)
    
    def test_content_hash_versioning(self):
        """내용 기반 해시 버전 테스트"""
        logger.info("🧪 Testing content hash versioning")
        
        # 동일한 데이터는 동일한 키 생성
        data1 = {"query": "테스트 질문", "params": {"limit": 3}}
        data2 = {"query": "테스트 질문", "params": {"limit": 3}}
        
        key1 = self.key_manager.generate_key("test", "item1", data1, CacheVersion.CONTENT_HASH)
        key2 = self.key_manager.generate_key("test", "item1", data2, CacheVersion.CONTENT_HASH)
        
        assert key1 == key2
        
        # 다른 데이터는 다른 키 생성
        data3 = {"query": "다른 질문", "params": {"limit": 3}}
        key3 = self.key_manager.generate_key("test", "item1", data3, CacheVersion.CONTENT_HASH)
        
        assert key1 != key3
        
        logger.info("✅ Content hash versioning test passed")
    
    def test_timestamp_versioning(self):
        """시간 기반 버전 테스트"""
        logger.info("🧪 Testing timestamp versioning")
        
        key1 = self.key_manager.generate_key("test", "item1", None, CacheVersion.TIMESTAMP)
        time.sleep(1)
        key2 = self.key_manager.generate_key("test", "item1", None, CacheVersion.TIMESTAMP)
        
        # 시간이 다르므로 다른 키
        assert key1 != key2
        
        # 키 파싱 테스트
        base_key1, version1 = self.key_manager.parse_key(key1)
        base_key2, version2 = self.key_manager.parse_key(key2)
        
        assert base_key1 == base_key2 == "test:item1"
        assert version1 != version2
        
        logger.info("✅ Timestamp versioning test passed")
    
    def test_key_parsing(self):
        """키 파싱 테스트"""
        logger.info("🧪 Testing key parsing")
        
        key = self.key_manager.generate_key("namespace", "identifier", {"data": "test"})
        base_key, version = self.key_manager.parse_key(key)
        
        assert base_key == "namespace:identifier"
        assert len(version) > 0
        
        # 버전이 없는 키
        simple_key = "namespace:identifier"
        base_key2, version2 = self.key_manager.parse_key(simple_key)
        
        assert base_key2 == simple_key
        assert version2 == ""
        
        logger.info("✅ Key parsing test passed")

class TestMemoryCache:
    """메모리 캐시 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        self.config = CacheConfig(memory_max_size=3, memory_ttl_seconds=1)
        self.cache = MemoryCache(self.config)
    
    def test_basic_operations(self):
        """기본 캐시 연산 테스트"""
        logger.info("🧪 Testing basic memory cache operations")
        
        # 저장 및 조회
        assert self.cache.set("key1", "value1", "v1") == True
        entry = self.cache.get("key1")
        
        assert entry is not None
        assert entry.value == "value1"
        assert entry.version == "v1"
        
        # 존재하지 않는 키
        assert self.cache.get("nonexistent") is None
        
        logger.info("✅ Basic memory cache operations test passed")
    
    def test_lru_eviction(self):
        """LRU 제거 테스트"""
        logger.info("🧪 Testing LRU eviction")
        
        # 최대 크기까지 채우기
        self.cache.set("key1", "value1", "v1")
        self.cache.set("key2", "value2", "v2")
        self.cache.set("key3", "value3", "v3")
        
        # 크기 확인
        assert len(self.cache.cache) == 3
        
        # 하나 더 추가하면 가장 오래된 것 제거
        self.cache.set("key4", "value4", "v4")
        assert len(self.cache.cache) == 3
        assert self.cache.get("key1") is None  # 가장 오래된 것 제거됨
        assert self.cache.get("key4") is not None  # 새로운 것 존재
        
        logger.info("✅ LRU eviction test passed")
    
    def test_ttl_expiration(self):
        """TTL 만료 테스트"""
        logger.info("🧪 Testing TTL expiration")
        
        # 짧은 TTL로 저장
        self.cache.set("expiring_key", "expiring_value", "v1", ttl=1)
        
        # 즉시 조회 - 존재
        entry = self.cache.get("expiring_key")
        assert entry is not None
        
        # TTL 대기
        time.sleep(1.1)
        
        # 만료 후 조회 - 제거됨
        entry = self.cache.get("expiring_key")
        assert entry is None
        
        logger.info("✅ TTL expiration test passed")
    
    def test_pattern_deletion(self):
        """패턴 기반 삭제 테스트"""
        logger.info("🧪 Testing pattern-based deletion")
        
        # 여러 키 저장
        self.cache.set("user:1:profile", "profile1", "v1")
        self.cache.set("user:2:profile", "profile2", "v1")
        self.cache.set("system:config", "config", "v1")
        
        # 패턴 매칭 삭제
        deleted = self.cache.delete_by_pattern(r"user:.*:profile")
        assert deleted == 2
        
        # 확인
        assert self.cache.get("user:1:profile") is None
        assert self.cache.get("user:2:profile") is None
        assert self.cache.get("system:config") is not None
        
        logger.info("✅ Pattern-based deletion test passed")

class TestMultiLevelCacheManager:
    """다층 캐시 매니저 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        self.config = CacheConfig(
            enable_memory_cache=True,
            enable_redis_cache=False,  # Redis 없이 테스트
            memory_max_size=10,
            memory_ttl_seconds=3600
        )
    
    async def test_multi_level_operations(self):
        """다층 캐시 연산 테스트"""
        logger.info("🧪 Testing multi-level cache operations")
        
        cache_manager = MultiLevelCacheManager(self.config)
        await cache_manager.initialize()
        
        try:
            # 저장
            test_data = {"data": "test_data"}
            key = await cache_manager.set("test", "item1", test_data)
            assert key is not None
            
            # 조회 (동일한 버전 데이터로)
            value = await cache_manager.get("test", "item1", test_data)
            assert value == test_data
            
            # 삭제
            deleted = await cache_manager.delete("test", "item1")
            assert deleted >= 0
            
            # 삭제 후 조회
            value = await cache_manager.get("test", "item1", test_data)
            assert value is None
            
        finally:
            await cache_manager.cleanup()
        
        logger.info("✅ Multi-level cache operations test passed")
    
    async def test_namespace_invalidation(self):
        """네임스페이스 무효화 테스트"""
        logger.info("🧪 Testing namespace invalidation")
        
        cache_manager = MultiLevelCacheManager(self.config)
        await cache_manager.initialize()
        
        try:
            # 여러 네임스페이스에 데이터 저장
            await cache_manager.set("test1", "item1", "value1")
            await cache_manager.set("test1", "item2", "value2")
            await cache_manager.set("test2", "item1", "value3")
            
            # test1 네임스페이스 무효화
            deleted = await cache_manager.invalidate_namespace("test1")
            assert deleted >= 0
            
            # 확인
            value1 = await cache_manager.get("test1", "item1", "value1")
            value2 = await cache_manager.get("test1", "item2", "value2")
            value3 = await cache_manager.get("test2", "item1", "value3")
            
            assert value1 is None
            assert value2 is None
            assert value3 == "value3"  # 다른 네임스페이스는 유지
            
        finally:
            await cache_manager.cleanup()
        
        logger.info("✅ Namespace invalidation test passed")

class TestRAGCacheManager:
    """RAG 캐시 매니저 테스트"""
    
    def setup_method(self):
        """테스트 설정"""
        pass
    
    async def test_embedding_cache(self):
        """임베딩 캐시 테스트"""
        logger.info("🧪 Testing embedding cache")
        
        rag_cache = RAGCacheManager()
        await rag_cache.initialize()
        
        # 임베딩 저장
        query = "테스트 질문입니다"
        embedding = [0.1, 0.2, 0.3, 0.4, 0.5] * 200  # 1000차원 벡터 시뮬레이션
        
        cache_key = await rag_cache.set_embedding(query, embedding, "bge-m3-test")
        assert cache_key is not None
        
        # 임베딩 조회
        cached_embedding = await rag_cache.get_embedding(query, "bge-m3-test")
        assert cached_embedding == embedding
        
        # 다른 쿼리는 캐시 미스
        other_embedding = await rag_cache.get_embedding("다른 질문", "bge-m3-test")
        assert other_embedding is None
        
        logger.info("✅ Embedding cache test passed")
    
    async def test_vector_search_cache(self):
        """벡터 검색 캐시 테스트"""
        logger.info("🧪 Testing vector search cache")
        
        rag_cache = RAGCacheManager()
        await rag_cache.initialize()
        
        # 검색 결과 생성
        search_params = {"limit": 2, "threshold": 0.8}
        search_result = SearchResult(
            query="테스트 검색",
            documents=[
                {"id": "doc1", "content": "문서 내용 1", "score": 0.95},
                {"id": "doc2", "content": "문서 내용 2", "score": 0.87}
            ],
            embeddings=[0.1, 0.2, 0.3],
            similarity_scores=[0.95, 0.87],
            search_params=search_params
        )
        
        # 검색 결과 캐시 저장
        cache_key = await rag_cache.set_vector_search_result(search_result, "mail")
        assert cache_key is not None
        
        # 검색 결과 캐시 조회 (정확히 동일한 파라미터로)
        cached_result = await rag_cache.get_vector_search_result(
            "테스트 검색",
            search_params,
            "mail"
        )
        
        assert cached_result is not None
        assert cached_result.cached == True
        assert len(cached_result.documents) == 2
        assert cached_result.similarity_scores == [0.95, 0.87]
        
        logger.info("✅ Vector search cache test passed")
    
    async def test_llm_response_cache(self):
        """LLM 응답 캐시 테스트"""
        logger.info("🧪 Testing LLM response cache")
        
        rag_cache = RAGCacheManager()
        await rag_cache.initialize()
        
        # LLM 응답 생성
        llm_response = LLMResponse(
            prompt="안녕하세요, 테스트입니다.",
            response="안녕하세요! 무엇을 도와드릴까요?",
            model_name="gemma3:4b",
            parameters={"temperature": 0.7, "max_tokens": 100},
            tokens_used=25
        )
        
        # LLM 응답 캐시 저장
        cache_key = await rag_cache.set_llm_response(llm_response)
        assert cache_key is not None
        
        # LLM 응답 캐시 조회
        cached_response = await rag_cache.get_llm_response(
            "안녕하세요, 테스트입니다.",
            "gemma3:4b",
            {"temperature": 0.7, "max_tokens": 100}
        )
        
        assert cached_response is not None
        assert cached_response.cached == True
        assert cached_response.response == "안녕하세요! 무엇을 도와드릴까요?"
        assert cached_response.tokens_used == 25
        
        logger.info("✅ LLM response cache test passed")
    
    async def test_cache_invalidation(self):
        """RAG 캐시 무효화 테스트"""
        logger.info("🧪 Testing RAG cache invalidation")
        
        rag_cache = RAGCacheManager()
        await rag_cache.initialize()
        
        # 다양한 캐시 데이터 저장
        await rag_cache.set_embedding("질문1", [0.1, 0.2], "model1")
        await rag_cache.set_embedding("질문2", [0.3, 0.4], "model1")
        await rag_cache.set_document_metadata("doc1", "mail", {"title": "문서1"})
        
        # 임베딩 캐시 무효화
        deleted = await rag_cache.invalidate_embeddings("model1")
        assert deleted >= 0
        
        # 확인
        embedding = await rag_cache.get_embedding("질문1", "model1")
        assert embedding is None
        
        # 문서 메타데이터는 유지
        metadata = await rag_cache.get_document_metadata("doc1", "mail")
        assert metadata == {"title": "문서1"}
        
        logger.info("✅ RAG cache invalidation test passed")
    
    async def test_cache_statistics(self):
        """캐시 통계 테스트"""
        logger.info("🧪 Testing cache statistics")
        
        rag_cache = RAGCacheManager()
        await rag_cache.initialize()
        
        # 데이터 저장
        await rag_cache.set_embedding("질문", [0.1, 0.2], "model")
        await rag_cache.set_document_metadata("doc", "mail", {"data": "test"})
        
        # 통계 조회
        stats = await rag_cache.get_rag_cache_stats()
        
        assert "timestamp" in stats
        assert "levels" in stats
        assert "rag_specific" in stats
        assert stats["rag_specific"]["rag_cache_version"] == "1.0.0"
        
        logger.info("✅ Cache statistics test passed")

async def run_cache_tests():
    """캐시 시스템 테스트 실행"""
    logger.info("🚀 Starting Cache System Test Suite for Phase 2B-1")
    
    # 키 버전 관리 테스트
    test_key = TestVersionedCacheKey()
    test_key.setup_method()
    test_key.test_content_hash_versioning()
    test_key.test_timestamp_versioning()
    test_key.test_key_parsing()
    
    # 메모리 캐시 테스트
    test_memory = TestMemoryCache()
    test_memory.setup_method()
    test_memory.test_basic_operations()
    
    test_memory.setup_method()  # 리셋
    test_memory.test_lru_eviction()
    
    test_memory.setup_method()  # 리셋
    test_memory.test_ttl_expiration()
    
    test_memory.setup_method()  # 리셋
    test_memory.test_pattern_deletion()
    
    # 다층 캐시 매니저 테스트
    test_multi = TestMultiLevelCacheManager()
    test_multi.setup_method()
    await test_multi.test_multi_level_operations()
    
    test_multi.setup_method()  # 리셋
    await test_multi.test_namespace_invalidation()
    
    # RAG 캐시 매니저 테스트
    test_rag = TestRAGCacheManager()
    test_rag.setup_method()
    await test_rag.test_embedding_cache()
    
    test_rag.setup_method()  # 리셋
    await test_rag.test_vector_search_cache()
    
    test_rag.setup_method()  # 리셋
    await test_rag.test_llm_response_cache()
    
    test_rag.setup_method()  # 리셋
    await test_rag.test_cache_invalidation()
    
    test_rag.setup_method()  # 리셋
    await test_rag.test_cache_statistics()
    
    logger.info("✅ All cache system tests passed!")
    logger.info("🎯 Phase 2B-1 Cache key/invalidation specifications with versioning strategy complete")

if __name__ == "__main__":
    asyncio.run(run_cache_tests())