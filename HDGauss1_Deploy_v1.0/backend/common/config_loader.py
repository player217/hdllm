"""
JSON-based configuration loader for HD현대미포 Gauss-1 RAG System
Provides centralized configuration management with environment variable fallback support.
"""

import json
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class QdrantEndpoint:
    """Qdrant endpoint configuration"""
    host: str
    port: int
    timeout: float = 30.0
    description: str = ""
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QdrantEndpoint':
        return cls(
            host=str(data.get('host', '127.0.0.1')),
            port=int(data.get('port', 6333)),
            timeout=float(data.get('timeout', 30.0)),
            description=str(data.get('description', ''))
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'host': self.host,
            'port': self.port,
            'timeout': self.timeout,
            'description': self.description
        }

class ConfigLoader:
    """JSON configuration loader with environment variable fallback"""
    
    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        """
        Initialize config loader
        
        Args:
            config_path: Path to config.json file. If None, searches in project root.
        """
        if config_path is None:
            # Search for config.json in project root
            current_dir = Path(__file__).parent.parent.parent  # backend/common -> backend -> root
            self.config_path = current_dir / "config.json"
        else:
            self.config_path = Path(config_path)
        
        self._config_cache: Optional[Dict[str, Any]] = None
        self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from JSON file"""
        try:
            if not self.config_path.exists():
                logger.warning(f"Config file not found at {self.config_path}, using defaults")
                self._config_cache = {}
                return
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config_cache = json.load(f)
            
            logger.info(f"✅ Configuration loaded from {self.config_path}")
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON in config file {self.config_path}: {e}")
            self._config_cache = {}
        except Exception as e:
            logger.error(f"❌ Failed to load config file {self.config_path}: {e}")
            self._config_cache = {}
    
    def get_qdrant_endpoints(self) -> Dict[str, QdrantEndpoint]:
        """
        Get Qdrant endpoints configuration
        
        Returns:
            Dictionary mapping scope names to QdrantEndpoint objects
        """
        if not self._config_cache:
            return self._get_default_qdrant_endpoints()
        
        endpoints_config = self._config_cache.get('qdrant_endpoints', {})
        if not endpoints_config:
            logger.warning("No qdrant_endpoints found in config, using defaults")
            return self._get_default_qdrant_endpoints()
        
        endpoints = {}
        for scope, config in endpoints_config.items():
            try:
                endpoints[scope] = QdrantEndpoint.from_dict(config)
                logger.debug(f"📍 Loaded {scope} endpoint: {endpoints[scope].host}:{endpoints[scope].port}")
            except Exception as e:
                logger.error(f"❌ Failed to parse {scope} endpoint config: {e}")
                continue
        
        return endpoints
    
    def _get_default_qdrant_endpoints(self) -> Dict[str, QdrantEndpoint]:
        """Get default Qdrant endpoints with environment variable fallback"""
        return {
            'personal': QdrantEndpoint(
                host=os.getenv('QDRANT_PERSONAL_HOST', '127.0.0.1'),
                port=int(os.getenv('QDRANT_PERSONAL_PORT', '6333')),
                timeout=float(os.getenv('QDRANT_PERSONAL_TIMEOUT', '15.0')),
                description='Personal Qdrant instance'
            ),
            'dept': QdrantEndpoint(
                host=os.getenv('QDRANT_DEPT_HOST', '10.150.104.37'),
                port=int(os.getenv('QDRANT_DEPT_PORT', '6333')),
                timeout=float(os.getenv('QDRANT_DEPT_TIMEOUT', '20.0')),
                description='Department Qdrant instance'
            )
        }
    
    def get_endpoint(self, scope: str) -> Optional[QdrantEndpoint]:
        """
        Get specific Qdrant endpoint by scope
        
        Args:
            scope: Endpoint scope (personal/dept)
            
        Returns:
            QdrantEndpoint object or None if not found
        """
        endpoints = self.get_qdrant_endpoints()
        return endpoints.get(scope)
    
    def get_config_value(self, key: str, default: Any = None, env_var: Optional[str] = None) -> Any:
        """
        Get configuration value with environment variable fallback
        
        Args:
            key: Configuration key (supports dot notation for nested keys)
            default: Default value if key not found
            env_var: Environment variable name for fallback
            
        Returns:
            Configuration value
        """
        # Check environment variable first if provided
        if env_var and env_var in os.environ:
            return os.environ[env_var]
        
        # Navigate nested keys
        if not self._config_cache:
            return default
        
        value = self._config_cache
        for part in key.split('.'):
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return default
        
        return value
    
    def reload_config(self) -> None:
        """Reload configuration from file"""
        self._config_cache = None
        self._load_config()
    
    def validate_qdrant_endpoints(self) -> bool:
        """
        Validate Qdrant endpoints configuration
        
        Returns:
            True if all endpoints are valid, False otherwise
        """
        endpoints = self.get_qdrant_endpoints()
        
        if not endpoints:
            logger.error("❌ No Qdrant endpoints configured")
            return False
        
        required_scopes = {'personal', 'dept'}
        configured_scopes = set(endpoints.keys())
        
        missing_scopes = required_scopes - configured_scopes
        if missing_scopes:
            logger.error(f"❌ Missing required Qdrant endpoints: {missing_scopes}")
            return False
        
        # Validate each endpoint
        for scope, endpoint in endpoints.items():
            if not endpoint.host:
                logger.error(f"❌ Invalid host for {scope} endpoint")
                return False
            
            if not (1 <= endpoint.port <= 65535):
                logger.error(f"❌ Invalid port {endpoint.port} for {scope} endpoint")
                return False
            
            if endpoint.timeout <= 0:
                logger.error(f"❌ Invalid timeout {endpoint.timeout} for {scope} endpoint")
                return False
        
        logger.info("✅ All Qdrant endpoints are valid")
        return True
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get configuration summary for debugging"""
        endpoints = self.get_qdrant_endpoints()
        
        return {
            'config_file': str(self.config_path),
            'file_exists': self.config_path.exists(),
            'endpoints_configured': len(endpoints),
            'endpoints': {
                scope: {
                    'host': ep.host,
                    'port': ep.port,
                    'timeout': ep.timeout,
                    'description': ep.description
                }
                for scope, ep in endpoints.items()
            }
        }

# Global config loader instance
_config_loader: Optional[ConfigLoader] = None

def get_config_loader() -> ConfigLoader:
    """Get global config loader instance (singleton)"""
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader()
    return _config_loader

def get_qdrant_endpoint(scope: str) -> Optional[QdrantEndpoint]:
    """Convenience function to get Qdrant endpoint"""
    return get_config_loader().get_endpoint(scope)