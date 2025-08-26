"""
Extended RAG Cache with Version Strategy Integration
Author: Claude Code
Date: 2025-01-27
Description: Phase 2B-2 - Extends existing cache system with version strategies
"""

import logging
from typing import Optional, Dict, Any, List
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag_cache_layer import RAGCacheManager, SearchResult, LLMResponse
from cache_manager import CacheVersion
from .version_strategies import (
    VersionInfo, 
    EmbedderVersionStrategy,
    QueryVersionStrategy,
    ModelVersionStrategy,
    HierarchicalVersionStrategy
)

logger = logging.getLogger(__name__)


class ExtendedRAGCache(RAGCacheManager):
    """Extended RAG Cache with enhanced version management"""
    
    def __init__(self):
        super().__init__()
        
        # Initialize version strategies
        self.embedder_strategy = EmbedderVersionStrategy()
        self.query_strategy = QueryVersionStrategy()
        self.model_strategy = ModelVersionStrategy()
        self.hierarchical_strategy = HierarchicalVersionStrategy()
        
        # Current version info (can be loaded from config)
        self.current_version = VersionInfo()
        
        # Extended namespaces for versioned data
        self.EMBEDDINGS_V2 = "rag:embeddings:v2"
        self.QUERY_V2 = "rag:query:v2"
        self.MODEL_V2 = "rag:model:v2"
    
    async def get_embedding_with_versions(
        self,
        text: str,
        version_info: Optional[VersionInfo] = None
    ) -> Optional[List[float]]:
        """
        Get embedding with version strategy
        Integrates with existing cache system while adding version awareness
        """
        version_info = version_info or self.current_version
        
        # Generate versioned key
        version_key = self.embedder_strategy.generate_version_key(text, version_info)
        
        # Build version data for existing cache system
        version_data = {
            "text": text,
            "embedder_id": version_info.embedder_id,
            "embedder_ver": version_info.embedder_ver,
            "preprocess_ver": version_info.preprocess_ver
        }
        
        # Use existing cache manager with extended namespace
        cached_embedding = await self.cache_manager.get(
            self.EMBEDDINGS_V2,
            version_key,
            version_data=version_data,
            strategy=CacheVersion.CONTENT_HASH
        )
        
        if cached_embedding:
            logger.debug(f"🎯 Version-aware embedding cache HIT: {version_key[:30]}...")
            return cached_embedding.get("embedding")
        
        logger.debug(f"❌ Version-aware embedding cache MISS: {version_key[:30]}...")
        return None
    
    async def set_embedding_with_versions(
        self,
        text: str,
        embedding: List[float],
        version_info: Optional[VersionInfo] = None,
        ttl: int = 86400  # 24 hours default
    ) -> str:
        """
        Set embedding with version strategy
        """
        version_info = version_info or self.current_version
        
        # Generate versioned key
        version_key = self.embedder_strategy.generate_version_key(text, version_info)
        
        # Build cache entry with version metadata
        cache_entry = {
            "text": text,
            "embedding": embedding,
            "embedder_id": version_info.embedder_id,
            "embedder_ver": version_info.embedder_ver,
            "preprocess_ver": version_info.preprocess_ver,
            "embedding_dim": len(embedding)
        }
        
        version_data = {
            "text": text,
            "embedder_id": version_info.embedder_id,
            "embedder_ver": version_info.embedder_ver,
            "preprocess_ver": version_info.preprocess_ver
        }
        
        # Store using existing cache manager
        cached_key = await self.cache_manager.set(
            self.EMBEDDINGS_V2,
            version_key,
            cache_entry,
            version_data=version_data,
            strategy=CacheVersion.CONTENT_HASH,
            ttl=ttl
        )
        
        logger.debug(f"💾 Version-aware embedding cached: {version_key[:30]}...")
        return cached_key
    
    async def get_query_result_with_versions(
        self,
        query: str,
        source: str,
        topk: int,
        filter_str: str,
        version_info: Optional[VersionInfo] = None
    ) -> Optional[SearchResult]:
        """
        Get query result with version strategy
        """
        version_info = version_info or self.current_version
        
        # Generate query cache key with version
        cache_key = f"Q:{source}:{query}:{topk}:{filter_str}"
        version_key = self.query_strategy.generate_version_key(cache_key, version_info)
        
        version_data = {
            "query": query,
            "source": source,
            "rerank_ver": version_info.rerank_ver,
            "pipeline_ver": version_info.pipeline_ver
        }
        
        # Retrieve from cache
        cached_result = await self.cache_manager.get(
            self.QUERY_V2,
            version_key,
            version_data=version_data,
            strategy=CacheVersion.CONTENT_HASH
        )
        
        if cached_result:
            logger.debug(f"🔍 Version-aware query cache HIT: {version_key[:30]}...")
            return SearchResult(
                query=cached_result["query"],
                documents=cached_result["documents"],
                embeddings=cached_result.get("embeddings", []),
                similarity_scores=cached_result["similarity_scores"],
                search_params=cached_result["search_params"],
                cached=True
            )
        
        return None
    
    async def invalidate_by_version_change(
        self,
        old_version: VersionInfo,
        new_version: VersionInfo
    ) -> Dict[str, int]:
        """
        Invalidate caches based on version changes
        Uses hierarchical invalidation strategy
        """
        invalidated = {}
        
        # Check embedder version changes
        if self.embedder_strategy.should_invalidate(old_version, new_version):
            count = await self.cache_manager.invalidate_namespace(self.EMBEDDINGS_V2)
            invalidated["embeddings"] = count
            logger.info(f"🧹 Invalidated {count} embeddings due to version change")
        
        # Check query version changes
        if self.query_strategy.should_invalidate(old_version, new_version):
            count = await self.cache_manager.invalidate_namespace(self.QUERY_V2)
            invalidated["queries"] = count
            logger.info(f"🧹 Invalidated {count} query results due to version change")
        
        # Check model version changes
        if self.model_strategy.should_invalidate(old_version, new_version):
            count = await self.cache_manager.invalidate_namespace(self.MODEL_V2)
            invalidated["models"] = count
            logger.info(f"🧹 Invalidated {count} model outputs due to version change")
        
        # Update current version
        self.current_version = new_version
        
        return invalidated
    
    def update_version(self, **kwargs) -> VersionInfo:
        """
        Update current version info
        
        Example:
            cache.update_version(embedder_ver="v1.1", preprocess_ver="pp.v2")
        """
        for key, value in kwargs.items():
            if hasattr(self.current_version, key):
                setattr(self.current_version, key, value)
        
        logger.info(f"📌 Version updated: {self.current_version}")
        return self.current_version
    
    async def get_cache_stats_with_versions(self) -> Dict[str, Any]:
        """
        Get cache statistics including version information
        """
        base_stats = await self.get_rag_cache_stats()
        
        version_stats = {
            "current_version": {
                "embedder_id": self.current_version.embedder_id,
                "embedder_ver": self.current_version.embedder_ver,
                "preprocess_ver": self.current_version.preprocess_ver,
                "rerank_ver": self.current_version.rerank_ver,
                "pipeline_ver": self.current_version.pipeline_ver
            },
            "extended_namespaces": {
                "embeddings_v2": self.EMBEDDINGS_V2,
                "query_v2": self.QUERY_V2,
                "model_v2": self.MODEL_V2
            }
        }
        
        return {**base_stats, "version_info": version_stats}