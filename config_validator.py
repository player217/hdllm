"""
Configuration Validator Module for HD현대미포 Gauss-1 RAG System
Author: Claude Code
Date: 2025-01-26
Description: Centralized configuration validation with fallback mechanisms
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import requests
from qdrant_client import QdrantClient

logger = logging.getLogger(__name__)

@dataclass
class ValidationResult:
    """Configuration validation result"""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    applied_defaults: Dict[str, Any] = field(default_factory=dict)

class ConfigValidator:
    """
    Configuration validator with fallback mechanisms.
    Ensures system can start even with incomplete configuration.
    """
    
    # Required configuration keys with their default values
    REQUIRED_CONFIG = {
        "RAG_OLLAMA_URL": "http://127.0.0.1:11434/api/chat",
        "RAG_MAIL_QDRANT_HOST": "127.0.0.1",
        "RAG_MAIL_QDRANT_PORT": "6333",
        "RAG_DOC_QDRANT_HOST": "127.0.0.1", 
        "RAG_DOC_QDRANT_PORT": "6333",
        "RAG_DEBUG": "false",
        "RAG_VERBOSE": "false"
    }
    
    # Optional configuration with defaults
    OPTIONAL_CONFIG = {
        "JWT_SECRET_KEY": None,  # Will generate if missing
        "API_KEY_NAME": "X-API-Key",
        "RATE_LIMIT_REQUESTS_PER_MINUTE": "60",
        "CORS_ALLOWED_ORIGINS": "http://localhost:3000,http://127.0.0.1:3000"
    }
    
    def __init__(self, project_root: Path = None):
        self.project_root = project_root or Path(__file__).parent
        self.config_file = self.project_root / "config.json"
        self.env_files = [
            self.project_root / ".env",
            self.project_root / ".env.local",
            self.project_root / ".env.development"
        ]
    
    def validate_all(self) -> ValidationResult:
        """Validate all configuration sources and apply defaults"""
        result = ValidationResult(is_valid=True)
        
        # Step 1: Load and validate config.json
        config_result = self._validate_config_file()
        result.errors.extend(config_result.errors)
        result.warnings.extend(config_result.warnings)
        
        # Step 2: Validate environment variables
        env_result = self._validate_environment()
        result.errors.extend(env_result.errors)
        result.warnings.extend(env_result.warnings)
        result.applied_defaults.update(env_result.applied_defaults)
        
        # Step 3: Validate external services
        services_result = self._validate_external_services()
        result.warnings.extend(services_result.warnings)
        
        # Step 4: Apply critical defaults if needed
        defaults_result = self._apply_critical_defaults()
        result.applied_defaults.update(defaults_result.applied_defaults)
        
        # Determine final validation status
        result.is_valid = len(result.errors) == 0
        
        if result.applied_defaults:
            logger.info(f"✅ Applied {len(result.applied_defaults)} default configurations")
            
        if result.warnings:
            logger.warning(f"⚠️ {len(result.warnings)} configuration warnings")
            
        if result.errors:
            logger.error(f"❌ {len(result.errors)} configuration errors")
        else:
            logger.info("✅ Configuration validation passed")
            
        return result
    
    def _validate_config_file(self) -> ValidationResult:
        """Validate config.json file"""
        result = ValidationResult(is_valid=True)
        
        if not self.config_file.exists():
            result.warnings.append(f"config.json not found at {self.config_file}")
            return result
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                
            # Basic structure validation
            if not isinstance(config_data, dict):
                result.errors.append("config.json must be a JSON object")
                
            logger.info(f"✅ config.json loaded successfully with {len(config_data)} entries")
            
        except json.JSONDecodeError as e:
            result.errors.append(f"Invalid JSON in config.json: {e}")
        except Exception as e:
            result.errors.append(f"Error reading config.json: {e}")
            
        return result
    
    def _validate_environment(self) -> ValidationResult:
        """Validate and set environment variables"""
        result = ValidationResult(is_valid=True)
        
        # Load .env files if they exist
        for env_file in self.env_files:
            if env_file.exists():
                self._load_env_file(env_file)
                logger.info(f"✅ Loaded environment from {env_file.name}")
        
        # Validate required environment variables
        for key, default_value in self.REQUIRED_CONFIG.items():
            current_value = os.getenv(key)
            
            if not current_value:
                os.environ[key] = str(default_value)
                result.applied_defaults[key] = default_value
                result.warnings.append(f"Applied default for {key}: {default_value}")
            else:
                logger.debug(f"✅ Environment variable {key} is set")
        
        # Set optional configuration
        for key, default_value in self.OPTIONAL_CONFIG.items():
            if key not in os.environ and default_value is not None:
                os.environ[key] = str(default_value)
                result.applied_defaults[key] = default_value
                
        return result
    
    def _validate_external_services(self) -> ValidationResult:
        """Check external service connectivity"""
        result = ValidationResult(is_valid=True)
        
        # Check Qdrant connectivity
        qdrant_result = self._check_qdrant_connection()
        if not qdrant_result["connected"]:
            result.warnings.append(f"Qdrant not accessible: {qdrant_result['error']}")
            result.warnings.append("System will run with limited RAG functionality")
        
        # Check Ollama connectivity  
        ollama_result = self._check_ollama_connection()
        if not ollama_result["connected"]:
            result.warnings.append(f"Ollama not accessible: {ollama_result['error']}")
            result.warnings.append("System will run without LLM generation")
            
        return result
    
    def _check_qdrant_connection(self) -> Dict[str, Any]:
        """Check if Qdrant is accessible"""
        try:
            host = os.getenv("RAG_MAIL_QDRANT_HOST", "127.0.0.1")
            port = int(os.getenv("RAG_MAIL_QDRANT_PORT", "6333"))
            
            client = QdrantClient(host=host, port=port, timeout=5.0)
            collections = client.get_collections()
            
            return {
                "connected": True,
                "host": host,
                "port": port,
                "collections": len(collections.collections) if hasattr(collections, 'collections') else 0
            }
        except Exception as e:
            return {
                "connected": False,
                "error": str(e),
                "host": host,
                "port": port
            }
    
    def _check_ollama_connection(self) -> Dict[str, Any]:
        """Check if Ollama is accessible"""
        try:
            url = os.getenv("RAG_OLLAMA_URL", "http://127.0.0.1:11434/api/chat")
            base_url = url.replace("/api/chat", "")
            
            response = requests.get(f"{base_url}/api/tags", timeout=5)
            response.raise_for_status()
            
            models = response.json().get("models", [])
            
            return {
                "connected": True,
                "url": url,
                "models": len(models)
            }
        except Exception as e:
            return {
                "connected": False,
                "error": str(e),
                "url": url
            }
    
    def _apply_critical_defaults(self) -> ValidationResult:
        """Apply critical default configurations"""
        result = ValidationResult(is_valid=True)
        
        # Generate JWT secret if missing
        if not os.getenv("JWT_SECRET_KEY"):
            import secrets
            secret_key = secrets.token_urlsafe(32)
            os.environ["JWT_SECRET_KEY"] = secret_key
            result.applied_defaults["JWT_SECRET_KEY"] = "[GENERATED]"
            logger.info("🔑 Generated JWT secret key")
        
        # Ensure logs directory exists
        logs_dir = self.project_root / "logs"
        if not logs_dir.exists():
            logs_dir.mkdir(exist_ok=True)
            logger.info(f"📁 Created logs directory: {logs_dir}")
        
        return result
    
    def _load_env_file(self, env_file: Path):
        """Load environment variables from .env file"""
        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"\'')
                        
                        # Don't override existing environment variables
                        if key not in os.environ:
                            os.environ[key] = value
        except Exception as e:
            logger.warning(f"Error loading {env_file}: {e}")
    
    def generate_env_template(self) -> str:
        """Generate .env.template file content"""
        template = """# HD현대미포 Gauss-1 RAG System Environment Configuration
# Copy this file to .env and configure your specific values

# === REQUIRED CONFIGURATION ===
# Ollama LLM Service
RAG_OLLAMA_URL=http://127.0.0.1:11434/api/chat

# Qdrant Vector Database (Mail)
RAG_MAIL_QDRANT_HOST=127.0.0.1
RAG_MAIL_QDRANT_PORT=6333

# Qdrant Vector Database (Documents)  
RAG_DOC_QDRANT_HOST=127.0.0.1
RAG_DOC_QDRANT_PORT=6333

# === OPTIONAL CONFIGURATION ===
# Debug and Logging
RAG_DEBUG=false
RAG_VERBOSE=false

# Security Configuration
JWT_SECRET_KEY=your-secret-key-here
API_KEY_NAME=X-API-Key

# CORS Configuration (comma-separated)
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Rate Limiting
RATE_LIMIT_REQUESTS_PER_MINUTE=60

# === GITHUB INTEGRATION (Keep in CLAUDE.md) ===
# GitHub repository and token info should remain in CLAUDE.md
# Do not store sensitive tokens in .env files that might be committed

# === PRODUCTION OVERRIDES ===
# Uncomment and configure for production deployment
# RAG_OLLAMA_URL=https://your-ollama-instance.com/api/chat
# RAG_MAIL_QDRANT_HOST=your-qdrant-host.com
# CORS_ALLOWED_ORIGINS=https://your-domain.com
"""
        return template
    
    def create_env_template_file(self) -> bool:
        """Create .env.template file if it doesn't exist"""
        template_file = self.project_root / ".env.template"
        
        if template_file.exists():
            logger.info(f"✅ .env.template already exists")
            return True
            
        try:
            template_content = self.generate_env_template()
            with open(template_file, 'w', encoding='utf-8') as f:
                f.write(template_content)
            logger.info(f"✅ Created .env.template at {template_file}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to create .env.template: {e}")
            return False

def validate_startup_config() -> ValidationResult:
    """
    Main function to validate configuration at application startup.
    Call this before initializing the FastAPI app.
    """
    validator = ConfigValidator()
    
    # Create .env.template if needed
    validator.create_env_template_file()
    
    # Validate all configuration
    result = validator.validate_all()
    
    if not result.is_valid:
        logger.error("❌ Configuration validation failed")
        logger.error("Errors found:")
        for error in result.errors:
            logger.error(f"  - {error}")
            
        # Still try to start with warnings
        logger.warning("⚠️ Attempting to start with partial configuration")
    
    return result

if __name__ == "__main__":
    # Test the validator
    logging.basicConfig(level=logging.INFO)
    result = validate_startup_config()
    
    print(f"\n🔍 Validation Result:")
    print(f"Valid: {result.is_valid}")
    print(f"Errors: {len(result.errors)}")
    print(f"Warnings: {len(result.warnings)}")
    print(f"Applied Defaults: {len(result.applied_defaults)}")