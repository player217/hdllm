"""
Version Strategy Extensions for Cache System
Author: Claude Code
Date: 2025-01-27
Description: Phase 2B-2 - Enhanced version strategies for cache invalidation
"""

import hashlib
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class VersionInfo:
    """Version information container"""
    embedder_id: str = "bge-m3"
    embedder_ver: str = "v1.0"
    preprocess_ver: str = "pp.v1"
    rerank_ver: str = "rank.v1"
    pipeline_ver: str = "pipe.v1"


class VersionStrategy(ABC):
    """Abstract base class for version strategies"""
    
    @abstractmethod
    def generate_version_key(self, base_key: str, version_info: VersionInfo) -> str:
        """Generate versioned cache key"""
        pass
    
    @abstractmethod
    def should_invalidate(self, old_version: VersionInfo, new_version: VersionInfo) -> bool:
        """Check if cache should be invalidated based on version change"""
        pass
    
    def normalize_text(self, text: str) -> str:
        """Normalize text for consistent key generation"""
        return " ".join(text.strip().lower().split())
    
    def sha256(self, text: str) -> str:
        """Generate SHA256 hash of text"""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()


class EmbedderVersionStrategy(VersionStrategy):
    """Version strategy for embedder cache"""
    
    def generate_version_key(self, base_key: str, version_info: VersionInfo) -> str:
        """
        Generate embedder-specific cache key
        Format: EMBED:{text_hash}:{embedder_id}:{preprocess_ver}:{embedder_ver}
        """
        normalized = self.normalize_text(base_key)
        text_hash = self.sha256(normalized)[:16]  # Use first 16 chars for brevity
        
        return f"EMBED:{text_hash}:{version_info.embedder_id}:{version_info.preprocess_ver}:{version_info.embedder_ver}"
    
    def should_invalidate(self, old_version: VersionInfo, new_version: VersionInfo) -> bool:
        """
        Invalidate if embedder, preprocessor, or embedder version changes
        """
        return (
            old_version.embedder_id != new_version.embedder_id or
            old_version.preprocess_ver != new_version.preprocess_ver or
            old_version.embedder_ver != new_version.embedder_ver
        )


class QueryVersionStrategy(VersionStrategy):
    """Version strategy for query cache"""
    
    def generate_version_key(self, base_key: str, version_info: VersionInfo) -> str:
        """
        Generate query-specific cache key
        Format: QUERY:{query_hash}:{rerank_ver}:{pipeline_ver}
        """
        normalized = self.normalize_text(base_key)
        query_hash = self.sha256(normalized)[:16]
        
        return f"QUERY:{query_hash}:{version_info.rerank_ver}:{version_info.pipeline_ver}"
    
    def should_invalidate(self, old_version: VersionInfo, new_version: VersionInfo) -> bool:
        """
        Invalidate if reranking or pipeline version changes
        """
        return (
            old_version.rerank_ver != new_version.rerank_ver or
            old_version.pipeline_ver != new_version.pipeline_ver
        )


class ModelVersionStrategy(VersionStrategy):
    """Version strategy for model output cache"""
    
    def __init__(self, model_name: str = "gemma3:4b"):
        self.model_name = model_name
    
    def generate_version_key(self, base_key: str, version_info: VersionInfo) -> str:
        """
        Generate model-specific cache key
        Format: MODEL:{model_name}:{model_ver}:{params_sig}
        """
        params_sig = self.sha256(f"{version_info.embedder_ver}:{version_info.pipeline_ver}")[:8]
        return f"MODEL:{self.model_name}:{version_info.embedder_ver}:{params_sig}"
    
    def should_invalidate(self, old_version: VersionInfo, new_version: VersionInfo) -> bool:
        """
        Invalidate if any model-related version changes
        """
        return (
            old_version.embedder_ver != new_version.embedder_ver or
            old_version.pipeline_ver != new_version.pipeline_ver
        )


class HierarchicalVersionStrategy(VersionStrategy):
    """Hierarchical version strategy with cascading invalidation"""
    
    def __init__(self):
        self.hierarchy = {
            "preprocess_ver": 3,  # Highest priority
            "embedder_ver": 2,
            "rerank_ver": 1,
            "pipeline_ver": 0   # Lowest priority
        }
    
    def generate_version_key(self, base_key: str, version_info: VersionInfo) -> str:
        """Generate hierarchical version key"""
        components = [
            f"H:{self.sha256(base_key)[:12]}",
            f"P{version_info.preprocess_ver}",
            f"E{version_info.embedder_ver}",
            f"R{version_info.rerank_ver}",
            f"L{version_info.pipeline_ver}"
        ]
        return ":".join(components)
    
    def should_invalidate(self, old_version: VersionInfo, new_version: VersionInfo) -> bool:
        """
        Hierarchical invalidation - higher level changes invalidate all lower levels
        """
        old_levels = {
            "preprocess_ver": old_version.preprocess_ver,
            "embedder_ver": old_version.embedder_ver,
            "rerank_ver": old_version.rerank_ver,
            "pipeline_ver": old_version.pipeline_ver
        }
        
        new_levels = {
            "preprocess_ver": new_version.preprocess_ver,
            "embedder_ver": new_version.embedder_ver,
            "rerank_ver": new_version.rerank_ver,
            "pipeline_ver": new_version.pipeline_ver
        }
        
        # Check each level in hierarchy order
        for level, priority in sorted(self.hierarchy.items(), key=lambda x: x[1], reverse=True):
            if old_levels[level] != new_levels[level]:
                return True
        
        return False