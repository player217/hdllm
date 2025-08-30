"""
Dual Qdrant Routing System
Author: Claude Code
Date: 2025-01-29
Description: Dynamic routing between personal and department Qdrant instances
"""

import os
import asyncio
import logging
import time
from typing import Dict, Optional, Any, List, Union
from dataclasses import dataclass
from contextvars import ContextVar
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

logger = logging.getLogger(__name__)

# Context variable for scope
scope_ctx: ContextVar[str] = ContextVar("scope", default="personal")

@dataclass
class QdrantConfig:
    """Configuration for a Qdrant instance"""
    host: str
    port: int
    timeout: float = 30.0
    scope: str = "personal"
    
    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

class QdrantRouter:
    """
    Manages multiple Qdrant clients and routes requests based on scope
    """
    
    def __init__(
        self,
        env_name: str,
        namespace_pattern: str,
        personal_cfg: QdrantConfig,
        dept_cfg: QdrantConfig,
        secure_factory=None
    ):
        """
        Initialize router with dual Qdrant configurations
        
        Args:
            env_name: Environment name (dev, prod, etc.)
            namespace_pattern: Pattern for namespace generation
            personal_cfg: Personal Qdrant configuration
            dept_cfg: Department Qdrant configuration
            secure_factory: Factory function for SecureQdrantClient
        """
        self.env_name = env_name
        self.namespace_pattern = namespace_pattern
        self.configs = {
            "personal": personal_cfg,
            "dept": dept_cfg
        }
        
        # Compatibility mode configuration
        self.compat_enabled = os.getenv("NAMESPACE_COMPAT_ENABLED", "false").lower() == "true"
        self.compat_fallback = os.getenv("NAMESPACE_COMPAT_FALLBACK", "").split(",")
        self.compat_fallback = [name.strip() for name in self.compat_fallback if name.strip()]
        
        # Initialize client pool
        self.clients: Dict[str, Any] = {}
        self._initialize_clients(secure_factory)
        
        # Health status cache
        self._health_cache = {}
        self._health_cache_ttl = 30  # seconds
        self._last_health_check = {}
        
        # Import metrics if available
        self.metrics_enabled = False
        try:
            from backend.common.logging import SEARCH_LAT, QDRANT_ERR
            self.SEARCH_LAT = SEARCH_LAT
            self.QDRANT_ERR = QDRANT_ERR
            self.metrics_enabled = True
        except ImportError:
            logger.info("Metrics not available, running without metrics")
        
    def _initialize_clients(self, secure_factory):
        """Initialize Qdrant clients for each scope"""
        for scope, cfg in self.configs.items():
            try:
                if secure_factory:
                    # Try to use secure client if factory provided
                    try:
                        from backend.vector.qdrant_extensions import SecureQdrantClient
                        client = secure_factory(
                            host=cfg.host,
                            port=cfg.port,
                            timeout=cfg.timeout,
                            scope=scope
                        )
                    except Exception as e:
                        logger.warning(f"SecureQdrantClient not available for {scope}, using standard: {e}")
                        client = QdrantClient(
                            host=cfg.host,
                            port=cfg.port,
                            timeout=cfg.timeout
                        )
                else:
                    # Fallback to standard client
                    client = QdrantClient(
                        host=cfg.host,
                        port=cfg.port,
                        timeout=cfg.timeout
                    )
                
                self.clients[scope] = client
                logger.info(f"Initialized {scope} Qdrant client: {cfg.host}:{cfg.port}")
                
            except Exception as e:
                logger.error(f"Failed to initialize {scope} client: {e}")
                self.clients[scope] = None
    
    def get_client(self, scope: Optional[str] = None) -> Optional[Any]:
        """
        Get Qdrant client for specified scope
        
        Args:
            scope: Target scope (personal/dept), uses context if not provided
            
        Returns:
            Qdrant client or None if unavailable
        """
        if scope is None:
            scope = scope_ctx.get()
        
        client = self.clients.get(scope)
        
        # Fallback logic if primary client unavailable
        if client is None and os.getenv("QDRANT_DEPT_FALLBACK"):
            fallback_scope = os.getenv("QDRANT_DEPT_FALLBACK")
            logger.warning(f"Falling back from {scope} to {fallback_scope}")
            client = self.clients.get(fallback_scope)
            
            # Record fallback in metrics if available
            if client and self.metrics_enabled:
                self.QDRANT_ERR.labels(type="fallback", scope=scope).inc()
        
        return client
    
    def get_namespace(self, scope: str, source: str) -> str:
        """
        Generate namespace based on pattern with compatibility mode support
        
        Args:
            scope: Scope (personal/dept)
            source: Source type (mail/doc)
            
        Returns:
            Generated namespace string (or compatible fallback if enabled)
        """
        # Generate primary namespace
        namespace = self.namespace_pattern.format(
            scope=scope,
            env=self.env_name,
            source=source
        )
        
        # If compatibility mode is enabled, check for existing collections
        if self.compat_enabled and self.compat_fallback:
            client = self.get_client(scope)
            if client:
                try:
                    # Get list of existing collections
                    collections = client.get_collections()
                    collection_names = [col.name for col in collections.collections]
                    
                    # Check if primary namespace exists
                    if namespace in collection_names:
                        logger.debug(f"Using primary namespace: {namespace}")
                        return namespace
                    
                    # Check compatibility fallback names
                    for fallback_name in self.compat_fallback:
                        if fallback_name in collection_names:
                            logger.info(f"Using compatibility fallback namespace: {fallback_name} (primary: {namespace})")
                            return fallback_name
                    
                    # If no existing collection found, use primary namespace
                    logger.debug(f"No existing collection found, using primary namespace: {namespace}")
                    
                except Exception as e:
                    logger.warning(f"Error checking collections for compatibility: {e}")
        
        logger.debug(f"Generated namespace: {namespace}")
        return namespace
    
    async def health_check(self, scope: Optional[str] = None) -> Dict[str, Any]:
        """
        Check health of Qdrant instance(s)
        
        Args:
            scope: Specific scope to check, or None for all
            
        Returns:
            Health status dictionary
        """
        results = {}
        current_time = time.time()
        
        scopes_to_check = [scope] if scope else list(self.clients.keys())
        
        for check_scope in scopes_to_check:
            # Check cache first
            last_check = self._last_health_check.get(check_scope, 0)
            if current_time - last_check < self._health_cache_ttl:
                cached = self._health_cache.get(check_scope)
                if cached:
                    results[check_scope] = cached
                    continue
            
            client = self.clients.get(check_scope)
            cfg = self.configs.get(check_scope)
            
            if not client:
                status = {
                    "status": "unavailable",
                    "host": cfg.host if cfg else "unknown",
                    "port": cfg.port if cfg else 0,
                    "error": "Client not initialized"
                }
                results[check_scope] = status
                continue
            
            try:
                # Attempt to get collections as health check
                if hasattr(client, 'get_collections'):
                    collections = await asyncio.wait_for(
                        asyncio.to_thread(client.get_collections),
                        timeout=5.0
                    )
                    
                    status = {
                        "status": "healthy",
                        "host": cfg.host,
                        "port": cfg.port,
                        "collections": len(collections.collections),
                        "namespace_prefix": f"{check_scope}_{self.env_name}_"
                    }
                else:
                    # SecureQdrantClient or other client type
                    status = {
                        "status": "healthy",
                        "host": cfg.host,
                        "port": cfg.port,
                        "type": "secure",
                        "namespace_prefix": f"{check_scope}_{self.env_name}_"
                    }
                    
            except asyncio.TimeoutError:
                status = {
                    "status": "timeout",
                    "host": cfg.host,
                    "port": cfg.port,
                    "error": "Health check timed out"
                }
                
            except Exception as e:
                status = {
                    "status": "unhealthy",
                    "host": cfg.host,
                    "port": cfg.port,
                    "error": str(e)
                }
            
            # Cache the result
            results[check_scope] = status
            self._health_cache[check_scope] = status
            self._last_health_check[check_scope] = current_time
        
        return results
    
    async def get_aggregated_status(self) -> Dict[str, Any]:
        """Get aggregated status for all Qdrant instances"""
        health_results = await self.health_check()
        
        healthy_count = sum(
            1 for status in health_results.values() 
            if status.get("status") == "healthy"
        )
        
        return {
            "qdrant": health_results,
            "namespaces_configured": len(self.configs),
            "namespaces_healthy": healthy_count,
            "routing_enabled": True,
            "default_scope": os.getenv("DEFAULT_DB_SCOPE", "personal")
        }