"""
Cache Manager with Versioning Strategy for HD현대미포 Gauss-1 RAG System
Author: Claude Code
Date: 2025-01-26
Description: Phase 2B-1 - 캐시 키/무효화 명세 (버전 전략) 구현
"""

import os
import time
import json
import hashlib
import asyncio
import logging
from typing import Dict, Optional, Any, List, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import OrderedDict
import threading
from contextlib import asynccontextmanager

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

logger = logging.getLogger(__name__)

class CacheLevel(Enum):
    """캐시 레벨 정의"""
    MEMORY = "memory"        # 메모리 캐시 (가장 빠름)
    REDIS = "redis"          # Redis 캐시 (분산 가능)
    PERSISTENT = "persistent" # 디스크 캐시 (영구 보관)

class CacheVersion(Enum):
    """캐시 버전 전략"""
    CONTENT_HASH = "content_hash"      # 내용 기반 해시
    TIMESTAMP = "timestamp"            # 시간 기반 버전
    SEMANTIC = "semantic"              # 의미론적 버전 (v1.0.0)
    INCREMENTAL = "incremental"        # 증분 버전 (1, 2, 3...)

@dataclass
class CacheConfig:
    """캐시 설정"""
    # 기본 설정
    enable_memory_cache: bool = True
    enable_redis_cache: bool = True
    enable_persistent_cache: bool = False
    
    # 메모리 캐시 설정
    memory_max_size: int = int(os.getenv("CACHE_MEMORY_MAX_SIZE", "1000"))
    memory_ttl_seconds: int = int(os.getenv("CACHE_MEMORY_TTL", "3600"))  # 1시간
    
    # Redis 캐시 설정
    redis_url: str = os.getenv("CACHE_REDIS_URL", "redis://localhost:6379")
    redis_ttl_seconds: int = int(os.getenv("CACHE_REDIS_TTL", "86400"))    # 24시간
    redis_key_prefix: str = os.getenv("CACHE_REDIS_PREFIX", "hdllm:cache:")
    
    # 버전 전략
    default_version_strategy: CacheVersion = CacheVersion.CONTENT_HASH
    version_separator: str = "#v#"
    
    # 무효화 설정
    auto_cleanup_interval: int = int(os.getenv("CACHE_CLEANUP_INTERVAL", "300"))  # 5분
    batch_invalidation_size: int = int(os.getenv("CACHE_BATCH_INVALIDATION", "100"))

@dataclass
class CacheEntry:
    """캐시 엔트리"""
    key: str
    value: Any
    version: str
    created_at: float
    accessed_at: float
    ttl: int
    level: CacheLevel
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_expired(self) -> bool:
        """만료 여부 확인"""
        if self.ttl <= 0:  # TTL이 0이면 무제한
            return False
        return time.time() - self.created_at > self.ttl
    
    @property
    def age_seconds(self) -> float:
        """캐시 나이 (초)"""
        return time.time() - self.created_at
    
    def touch(self):
        """접근 시간 업데이트"""
        self.accessed_at = time.time()

class VersionedCacheKey:
    """버전 기반 캐시 키 관리"""
    
    def __init__(self, config: CacheConfig):
        self.config = config
        
    def generate_key(self, namespace: str, identifier: str, 
                    data: Any = None, strategy: CacheVersion = None) -> str:
        """버전 기반 키 생성"""
        strategy = strategy or self.config.default_version_strategy
        version = self._generate_version(data, strategy)
        
        # 키 형식: namespace:identifier#v#version
        base_key = f"{namespace}:{identifier}"
        versioned_key = f"{base_key}{self.config.version_separator}{version}"
        
        return versioned_key
    
    def parse_key(self, key: str) -> Tuple[str, str]:
        """키에서 기본키와 버전 분리"""
        if self.config.version_separator in key:
            base_key, version = key.rsplit(self.config.version_separator, 1)
            return base_key, version
        return key, ""
    
    def _generate_version(self, data: Any, strategy: CacheVersion) -> str:
        """버전 생성 전략별 구현"""
        if strategy == CacheVersion.CONTENT_HASH:
            if data is not None:
                content_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
                hash_result = hashlib.md5(content_str.encode()).hexdigest()[:8]
                logger.debug(f"Content hash: '{content_str}' -> {hash_result}")
                return hash_result
            time_hash = hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
            logger.debug(f"Time-based hash: {time_hash}")
            return time_hash
        
        elif strategy == CacheVersion.TIMESTAMP:
            return str(int(time.time()))
        
        elif strategy == CacheVersion.SEMANTIC:
            # 기본 semantic version (실제로는 외부에서 주입받아야 함)
            return "1.0.0"
        
        elif strategy == CacheVersion.INCREMENTAL:
            # 증분 버전 (실제로는 데이터베이스나 카운터 사용)
            return str(int(time.time()) % 1000000)  # 간단한 구현
        
        return "default"

class MemoryCache:
    """메모리 기반 LRU 캐시"""
    
    def __init__(self, config: CacheConfig):
        self.config = config
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self.lock = threading.RLock()
        self.stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "sets": 0
        }
    
    def get(self, key: str) -> Optional[CacheEntry]:
        """캐시에서 값 조회"""
        with self.lock:
            if key in self.cache:
                entry = self.cache[key]
                if entry.is_expired:
                    del self.cache[key]
                    self.stats["misses"] += 1
                    return None
                
                # LRU 업데이트
                self.cache.move_to_end(key)
                entry.touch()
                self.stats["hits"] += 1
                return entry
            
            self.stats["misses"] += 1
            return None
    
    def set(self, key: str, value: Any, version: str, ttl: int = None) -> bool:
        """캐시에 값 저장"""
        with self.lock:
            ttl = ttl or self.config.memory_ttl_seconds
            
            entry = CacheEntry(
                key=key,
                value=value,
                version=version,
                created_at=time.time(),
                accessed_at=time.time(),
                ttl=ttl,
                level=CacheLevel.MEMORY
            )
            
            # 기존 항목 제거 및 새 항목 추가
            if key in self.cache:
                del self.cache[key]
            
            self.cache[key] = entry
            self.stats["sets"] += 1
            
            # 크기 제한 확인 및 LRU 제거
            self._evict_if_needed()
            
            return True
    
    def delete(self, key: str) -> bool:
        """캐시에서 항목 삭제"""
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                return True
            return False
    
    def delete_by_pattern(self, pattern: str) -> int:
        """패턴으로 항목들 삭제"""
        import re
        deleted_count = 0
        
        with self.lock:
            keys_to_delete = []
            for key in self.cache.keys():
                if re.match(pattern, key):
                    keys_to_delete.append(key)
            
            for key in keys_to_delete:
                del self.cache[key]
                deleted_count += 1
        
        return deleted_count
    
    def clear(self) -> int:
        """모든 캐시 삭제"""
        with self.lock:
            count = len(self.cache)
            self.cache.clear()
            return count
    
    def cleanup_expired(self) -> int:
        """만료된 항목 정리"""
        expired_keys = []
        
        with self.lock:
            for key, entry in self.cache.items():
                if entry.is_expired:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self.cache[key]
        
        return len(expired_keys)
    
    def _evict_if_needed(self):
        """필요시 LRU 제거"""
        while len(self.cache) > self.config.memory_max_size:
            # 가장 오래된 항목 제거
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
            self.stats["evictions"] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """캐시 통계"""
        with self.lock:
            total_requests = self.stats["hits"] + self.stats["misses"]
            hit_rate = self.stats["hits"] / total_requests if total_requests > 0 else 0
            
            return {
                "level": "memory",
                "size": len(self.cache),
                "max_size": self.config.memory_max_size,
                "hit_rate": hit_rate,
                **self.stats
            }

class RedisCache:
    """Redis 기반 분산 캐시"""
    
    def __init__(self, config: CacheConfig):
        self.config = config
        self.redis_client: Optional[redis.Redis] = None
        self.stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "errors": 0
        }
    
    async def initialize(self):
        """Redis 연결 초기화"""
        if not REDIS_AVAILABLE:
            logger.warning("🔴 Redis not available, skipping Redis cache")
            return
        
        try:
            self.redis_client = redis.from_url(
                self.config.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True
            )
            
            # 연결 테스트
            await self.redis_client.ping()
            logger.info("✅ Redis cache initialized")
            
        except Exception as e:
            logger.error(f"❌ Redis initialization failed: {e}")
            self.redis_client = None
    
    async def get(self, key: str) -> Optional[CacheEntry]:
        """Redis에서 값 조회"""
        if not self.redis_client:
            return None
        
        try:
            redis_key = f"{self.config.redis_key_prefix}{key}"
            raw_data = await self.redis_client.get(redis_key)
            
            if raw_data:
                entry_data = json.loads(raw_data)
                entry = CacheEntry(
                    key=entry_data["key"],
                    value=entry_data["value"],
                    version=entry_data["version"],
                    created_at=entry_data["created_at"],
                    accessed_at=time.time(),  # 현재 시간으로 업데이트
                    ttl=entry_data["ttl"],
                    level=CacheLevel.REDIS,
                    metadata=entry_data.get("metadata", {})
                )
                
                self.stats["hits"] += 1
                return entry
            
            self.stats["misses"] += 1
            return None
            
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            self.stats["errors"] += 1
            return None
    
    async def set(self, key: str, value: Any, version: str, ttl: int = None) -> bool:
        """Redis에 값 저장"""
        if not self.redis_client:
            return False
        
        try:
            ttl = ttl or self.config.redis_ttl_seconds
            redis_key = f"{self.config.redis_key_prefix}{key}"
            
            entry_data = {
                "key": key,
                "value": value,
                "version": version,
                "created_at": time.time(),
                "accessed_at": time.time(),
                "ttl": ttl,
                "metadata": {}
            }
            
            await self.redis_client.setex(
                redis_key,
                ttl,
                json.dumps(entry_data, ensure_ascii=False)
            )
            
            self.stats["sets"] += 1
            return True
            
        except Exception as e:
            logger.error(f"Redis set error: {e}")
            self.stats["errors"] += 1
            return False
    
    async def delete(self, key: str) -> bool:
        """Redis에서 항목 삭제"""
        if not self.redis_client:
            return False
        
        try:
            redis_key = f"{self.config.redis_key_prefix}{key}"
            result = await self.redis_client.delete(redis_key)
            return result > 0
            
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            self.stats["errors"] += 1
            return False
    
    async def delete_by_pattern(self, pattern: str) -> int:
        """패턴으로 Redis 항목들 삭제"""
        if not self.redis_client:
            return 0
        
        try:
            redis_pattern = f"{self.config.redis_key_prefix}{pattern}"
            keys = await self.redis_client.keys(redis_pattern)
            
            if keys:
                deleted = await self.redis_client.delete(*keys)
                return deleted
            
            return 0
            
        except Exception as e:
            logger.error(f"Redis delete by pattern error: {e}")
            self.stats["errors"] += 1
            return 0
    
    async def clear(self) -> int:
        """모든 캐시 삭제 (prefix 기준)"""
        if not self.redis_client:
            return 0
        
        try:
            pattern = f"{self.config.redis_key_prefix}*"
            keys = await self.redis_client.keys(pattern)
            
            if keys:
                deleted = await self.redis_client.delete(*keys)
                return deleted
            
            return 0
            
        except Exception as e:
            logger.error(f"Redis clear error: {e}")
            self.stats["errors"] += 1
            return 0
    
    async def cleanup(self):
        """Redis 연결 종료"""
        if self.redis_client:
            await self.redis_client.close()
    
    def get_stats(self) -> Dict[str, Any]:
        """Redis 캐시 통계"""
        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = self.stats["hits"] / total_requests if total_requests > 0 else 0
        
        return {
            "level": "redis",
            "connected": self.redis_client is not None,
            "hit_rate": hit_rate,
            **self.stats
        }

class MultiLevelCacheManager:
    """다층 캐시 관리자"""
    
    def __init__(self, config: CacheConfig = None):
        self.config = config or CacheConfig()
        self.key_manager = VersionedCacheKey(self.config)
        
        # 캐시 레벨 초기화
        self.memory_cache = MemoryCache(self.config) if self.config.enable_memory_cache else None
        self.redis_cache = RedisCache(self.config) if self.config.enable_redis_cache else None
        
        # 정리 작업 스케줄러
        self._cleanup_task = None
        self._running = False
    
    async def initialize(self):
        """캐시 매니저 초기화"""
        logger.info("🚀 Initializing Multi-Level Cache Manager")
        
        if self.redis_cache:
            await self.redis_cache.initialize()
        
        # 자동 정리 작업 시작
        if self.config.auto_cleanup_interval > 0:
            self._running = True
            self._cleanup_task = asyncio.create_task(self._auto_cleanup())
        
        logger.info("✅ Multi-Level Cache Manager initialized")
    
    async def get(self, namespace: str, identifier: str, 
                 version_data: Any = None, strategy: CacheVersion = None) -> Optional[Any]:
        """다층 캐시에서 값 조회"""
        # version_data가 None이면 기본적으로 식별자 기반 키 생성을 시도하지만,
        # 이는 set과 일치하지 않으므로 None으로 유지하여 일관성 확보
        key = self.key_manager.generate_key(namespace, identifier, version_data, strategy)
        
        # L1: Memory Cache
        if self.memory_cache:
            entry = self.memory_cache.get(key)
            if entry:
                logger.debug(f"Cache HIT (Memory): {key}")
                return entry.value
        
        # L2: Redis Cache
        if self.redis_cache:
            entry = await self.redis_cache.get(key)
            if entry:
                logger.debug(f"Cache HIT (Redis): {key}")
                
                # Memory에 승격
                if self.memory_cache:
                    self.memory_cache.set(key, entry.value, entry.version)
                
                return entry.value
        
        logger.debug(f"Cache MISS: {key}")
        return None
    
    async def set(self, namespace: str, identifier: str, value: Any,
                 version_data: Any = None, strategy: CacheVersion = None, 
                 ttl: int = None) -> str:
        """다층 캐시에 값 저장"""
        # version_data가 None이면 value를 사용 (기본 동작)
        if version_data is None:
            version_data = value
        key = self.key_manager.generate_key(namespace, identifier, version_data, strategy)
        _, version = self.key_manager.parse_key(key)
        
        # 모든 레벨에 저장
        success_levels = []
        
        if self.memory_cache:
            if self.memory_cache.set(key, value, version, ttl):
                success_levels.append("memory")
        
        if self.redis_cache:
            if await self.redis_cache.set(key, value, version, ttl):
                success_levels.append("redis")
        
        logger.debug(f"Cache SET ({','.join(success_levels)}): {key}")
        return key
    
    async def delete(self, namespace: str, identifier: str) -> int:
        """특정 키의 모든 버전 삭제"""
        base_pattern = f"{namespace}:{identifier}"
        deleted_count = 0
        
        # 패턴 매칭으로 모든 버전 삭제
        if self.memory_cache:
            deleted_count += self.memory_cache.delete_by_pattern(f"{base_pattern}.*")
        
        if self.redis_cache:
            deleted_count += await self.redis_cache.delete_by_pattern(f"{base_pattern}*")
        
        logger.info(f"Cache DELETE: {base_pattern} ({deleted_count} entries)")
        return deleted_count
    
    async def invalidate_by_version(self, namespace: str, old_version: str) -> int:
        """특정 버전 이하의 캐시 무효화"""
        pattern = f"{namespace}:.*{self.config.version_separator}{old_version}"
        deleted_count = 0
        
        if self.memory_cache:
            deleted_count += self.memory_cache.delete_by_pattern(pattern)
        
        if self.redis_cache:
            deleted_count += await self.redis_cache.delete_by_pattern(pattern.replace(".*", "*"))
        
        logger.info(f"Cache INVALIDATE by version: {namespace} <= {old_version} ({deleted_count} entries)")
        return deleted_count
    
    async def invalidate_namespace(self, namespace: str) -> int:
        """네임스페이스 전체 무효화"""
        pattern = f"{namespace}:*"
        deleted_count = 0
        
        if self.memory_cache:
            deleted_count += self.memory_cache.delete_by_pattern(f"{namespace}:.*")
        
        if self.redis_cache:
            deleted_count += await self.redis_cache.delete_by_pattern(pattern)
        
        logger.info(f"Cache INVALIDATE namespace: {namespace} ({deleted_count} entries)")
        return deleted_count
    
    async def clear_all(self) -> Dict[str, int]:
        """모든 캐시 삭제"""
        cleared = {}
        
        if self.memory_cache:
            cleared["memory"] = self.memory_cache.clear()
        
        if self.redis_cache:
            cleared["redis"] = await self.redis_cache.clear()
        
        logger.info(f"Cache CLEAR ALL: {cleared}")
        return cleared
    
    def get_stats(self) -> Dict[str, Any]:
        """캐시 통계"""
        stats = {
            "timestamp": datetime.now().isoformat(),
            "levels": {}
        }
        
        if self.memory_cache:
            stats["levels"]["memory"] = self.memory_cache.get_stats()
        
        if self.redis_cache:
            stats["levels"]["redis"] = self.redis_cache.get_stats()
        
        return stats
    
    async def _auto_cleanup(self):
        """자동 정리 작업"""
        while self._running:
            try:
                if self.memory_cache:
                    expired_count = self.memory_cache.cleanup_expired()
                    if expired_count > 0:
                        logger.debug(f"🧹 Memory cache cleanup: {expired_count} expired entries")
                
                await asyncio.sleep(self.config.auto_cleanup_interval)
                
            except Exception as e:
                logger.error(f"Cache cleanup error: {e}")
                await asyncio.sleep(60)  # 1분 대기 후 재시도
    
    async def cleanup(self):
        """캐시 매니저 종료"""
        logger.info("🧹 Cleaning up Multi-Level Cache Manager")
        
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        if self.redis_cache:
            await self.redis_cache.cleanup()
        
        logger.info("✅ Multi-Level Cache Manager cleanup complete")

# 전역 캐시 매니저 인스턴스
_cache_manager: Optional[MultiLevelCacheManager] = None

async def get_cache_manager() -> MultiLevelCacheManager:
    """글로벌 캐시 매니저 인스턴스 반환"""
    global _cache_manager
    
    if _cache_manager is None:
        config = CacheConfig()
        _cache_manager = MultiLevelCacheManager(config)
        await _cache_manager.initialize()
    
    return _cache_manager

@asynccontextmanager
async def cache_context():
    """캐시 컨텍스트 매니저"""
    cache_manager = await get_cache_manager()
    try:
        yield cache_manager
    finally:
        # 컨텍스트 종료시 정리는 하지 않음 (글로벌 인스턴스)
        pass