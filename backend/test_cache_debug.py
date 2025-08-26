"""
Cache Debug Test for HD현대미포 Gauss-1 RAG System
"""

import asyncio
import logging
from cache_manager import MultiLevelCacheManager, CacheConfig

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def debug_cache():
    config = CacheConfig(
        enable_memory_cache=True,
        enable_redis_cache=False,
        memory_max_size=10
    )
    
    cache_manager = MultiLevelCacheManager(config)
    await cache_manager.initialize()
    
    try:
        # 데이터 준비
        test_data = {"data": "test_value"}
        
        # 저장
        logger.info("🔧 Setting cache data...")
        import json
        logger.info(f"Set data JSON: {json.dumps(test_data, sort_keys=True)}")
        key = await cache_manager.set("test_namespace", "test_id", test_data)
        logger.info(f"Generated key: {key}")
        
        # 조회 시도 1: 동일한 데이터로
        logger.info("🔍 Retrieving with same data...")
        logger.info(f"Get data JSON: {json.dumps(test_data, sort_keys=True)}")
        value1 = await cache_manager.get("test_namespace", "test_id", test_data)
        logger.info(f"Retrieved value1: {value1}")
        
        # 직접 키 생성 테스트
        key_manager = cache_manager.key_manager
        set_key = key_manager.generate_key("test_namespace", "test_id", test_data)
        get_key = key_manager.generate_key("test_namespace", "test_id", test_data)
        logger.info(f"Direct key generation - Set: {set_key}, Get: {get_key}, Equal: {set_key == get_key}")
        
        # 조회 시도 2: 다른 데이터로 (캐시 미스 예상)
        logger.info("🔍 Retrieving with different data...")
        different_data = {"data": "different_value"}
        value2 = await cache_manager.get("test_namespace", "test_id", different_data)
        logger.info(f"Retrieved value2: {value2}")
        
        # 메모리 캐시 직접 확인
        if cache_manager.memory_cache:
            logger.info(f"Memory cache size: {len(cache_manager.memory_cache.cache)}")
            for k, v in cache_manager.memory_cache.cache.items():
                logger.info(f"Cache entry: {k} -> {v.value}")
        
        # 통계 확인
        stats = cache_manager.get_stats()
        logger.info(f"Cache stats: {stats}")
        
    finally:
        await cache_manager.cleanup()

if __name__ == "__main__":
    asyncio.run(debug_cache())