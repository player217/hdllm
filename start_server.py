#!/usr/bin/env python3
"""
Production Server Startup Script for HD현대미포 Gauss-1 RAG System
Author: Claude Code  
Date: 2024-01-22
Description: Production-ready server startup with comprehensive configuration
"""

import os
import sys
import logging
import argparse
import signal
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any

# Add backend directory to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

# Import after path setup
try:
    import uvicorn
    from uvicorn.config import Config
    from uvicorn.server import Server
except ImportError:
    print("Error: uvicorn not installed. Run: pip install uvicorn")
    sys.exit(1)


# =============================================================================
# Configuration Management
# =============================================================================

class ServerConfig:
    """Server configuration management"""
    
    def __init__(self):
        # Server settings
        self.host = os.getenv("RAG_HOST", "0.0.0.0")
        self.port = int(os.getenv("RAG_PORT", "8080"))
        self.workers = int(os.getenv("RAG_WORKERS", "1"))  # Single worker for development
        self.reload = os.getenv("RAG_RELOAD", "false").lower() == "true"
        
        # Application settings
        self.app_module = os.getenv("RAG_APP_MODULE", "backend.main:app")
        self.log_level = os.getenv("RAG_LOG_LEVEL", "info")
        self.access_log = os.getenv("RAG_ACCESS_LOG", "true").lower() == "true"
        
        # SSL settings (for production)
        self.ssl_keyfile = os.getenv("RAG_SSL_KEYFILE")
        self.ssl_certfile = os.getenv("RAG_SSL_CERTFILE")
        
        # Performance settings
        self.loop = os.getenv("RAG_LOOP", "auto")
        self.http = os.getenv("RAG_HTTP", "auto")
        self.ws = os.getenv("RAG_WS", "auto")
        self.lifespan = os.getenv("RAG_LIFESPAN", "auto")
        
        # Environment
        self.environment = os.getenv("RAG_ENVIRONMENT", "development")
        
    def get_uvicorn_config(self) -> Dict[str, Any]:
        """Get uvicorn configuration dictionary"""
        config = {
            "app": self.app_module,
            "host": self.host,
            "port": self.port,
            "log_level": self.log_level,
            "access_log": self.access_log,
            "loop": self.loop,
            "http": self.http,
            "ws": self.ws,
            "lifespan": self.lifespan,
        }
        
        # Production settings
        if self.environment == "production":
            config.update({
                "workers": max(1, self.workers),  # Minimum 1 worker
                "reload": False,
                "debug": False,
            })
        else:
            config.update({
                "workers": 1,
                "reload": self.reload,
                "debug": True,
            })
        
        # SSL configuration
        if self.ssl_keyfile and self.ssl_certfile:
            config.update({
                "ssl_keyfile": self.ssl_keyfile,
                "ssl_certfile": self.ssl_certfile,
            })
            print(f"SSL ENABLED: {self.ssl_certfile}")
        
        return config


# =============================================================================
# Environment Validation
# =============================================================================

def validate_environment():
    """Validate required environment and dependencies"""
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("ERROR: Python 3.8+ required")
        sys.exit(1)
    
    # Check backend directory
    backend_dir = Path(__file__).parent / "backend"
    if not backend_dir.exists():
        print(f"ERROR: Backend directory not found: {backend_dir}")
        sys.exit(1)
    
    # Check main.py
    main_py = backend_dir / "main.py"
    if not main_py.exists():
        print(f"ERROR: main.py not found: {main_py}")
        sys.exit(1)
    
    # Check Phase 3 modules (optional)
    phase3_modules = [
        "integration.py",
        "api_v2.py", 
        "websocket_manager.py",
        "error_handlers.py",
        "monitoring.py"
    ]
    
    missing_modules = []
    for module in phase3_modules:
        if not (backend_dir / module).exists():
            missing_modules.append(module)
    
    if missing_modules:
        print(f"WARNING: Phase 3 modules missing: {', '.join(missing_modules)}")
        print("   Server will run in legacy mode")
    else:
        print("SUCCESS: Phase 3 modules detected")
    
    print("SUCCESS: Environment validation passed")


# =============================================================================
# Logging Configuration
# =============================================================================

def setup_logging(log_level: str = "info"):
    """Setup production logging"""
    
    # Create logs directory
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(logs_dir / "server.log", encoding='utf-8')
        ]
    )
    
    # Configure uvicorn logger
    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_logger.handlers = []
    
    print(f"LOGGING CONFIGURED: {log_level}")


# =============================================================================
# Process Management
# =============================================================================

class ServerManager:
    """Manages server lifecycle"""
    
    def __init__(self, config: ServerConfig):
        self.config = config
        self.server: Optional[Server] = None
        self._shutdown_event = asyncio.Event()
    
    def setup_signal_handlers(self):
        """Setup graceful shutdown signal handlers"""
        
        def signal_handler(signum, frame):
            print(f"\nRECEIVED SIGNAL {signum}, initiating graceful shutdown...")
            self._shutdown_event.set()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        if hasattr(signal, 'SIGHUP'):
            signal.signal(signal.SIGHUP, signal_handler)
    
    async def start_server(self):
        """Start the server with configuration"""
        
        # Create uvicorn config
        uvicorn_config = self.config.get_uvicorn_config()
        
        # Create server instance
        config = Config(**uvicorn_config)
        self.server = Server(config)
        
        print("STARTING HD현대미포 Gauss-1 RAG Server...")
        print(f"   Host: {self.config.host}")
        print(f"   Port: {self.config.port}")
        print(f"   Environment: {self.config.environment}")
        print(f"   Workers: {self.config.workers}")
        print(f"   SSL: {'Enabled' if self.config.ssl_keyfile else 'Disabled'}")
        
        # Start server
        try:
            await self.server.serve()
        except Exception as e:
            print(f"SERVER ERROR: {e}")
            raise
    
    async def shutdown(self):
        """Graceful server shutdown"""
        if self.server:
            print("SHUTTING DOWN SERVER...")
            self.server.should_exit = True
            await self.server.shutdown()
            print("SERVER SHUTDOWN COMPLETE")


# =============================================================================
# Main Entry Point
# =============================================================================

async def run_server(args):
    """Run the server with configuration"""
    
    # Setup environment
    if args.environment:
        os.environ["RAG_ENVIRONMENT"] = args.environment
    
    if args.port:
        os.environ["RAG_PORT"] = str(args.port)
    
    if args.host:
        os.environ["RAG_HOST"] = args.host
    
    if args.workers:
        os.environ["RAG_WORKERS"] = str(args.workers)
    
    if args.reload:
        os.environ["RAG_RELOAD"] = "true"
    
    # Create server configuration
    config = ServerConfig()
    
    # Setup logging
    setup_logging(config.log_level)
    
    # Create server manager
    manager = ServerManager(config)
    manager.setup_signal_handlers()
    
    # Start server
    try:
        await manager.start_server()
    except KeyboardInterrupt:
        print("\nKEYBOARD INTERRUPT RECEIVED")
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        return 1
    finally:
        await manager.shutdown()
    
    return 0


def main():
    """Main entry point"""
    
    parser = argparse.ArgumentParser(
        description="HD현대미포 Gauss-1 RAG Server Startup Script"
    )
    
    parser.add_argument(
        "--host", 
        default=None,
        help="Server host (default: from environment or 0.0.0.0)"
    )
    
    parser.add_argument(
        "--port", 
        type=int, 
        default=None,
        help="Server port (default: from environment or 8080)"
    )
    
    parser.add_argument(
        "--workers", 
        type=int, 
        default=None,
        help="Number of worker processes (default: 1)"
    )
    
    parser.add_argument(
        "--environment", 
        choices=["development", "production"],
        help="Runtime environment"
    )
    
    parser.add_argument(
        "--reload", 
        action="store_true",
        help="Enable auto-reload (development only)"
    )
    
    parser.add_argument(
        "--validate-only", 
        action="store_true",
        help="Only validate environment and exit"
    )
    
    args = parser.parse_args()
    
    # Validate environment
    validate_environment()
    
    if args.validate_only:
        print("VALIDATION COMPLETE, EXITING")
        return 0
    
    # Run server
    try:
        return asyncio.run(run_server(args))
    except KeyboardInterrupt:
        print("\nINTERRUPTED")
        return 130
    except Exception as e:
        print(f"STARTUP FAILED: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())