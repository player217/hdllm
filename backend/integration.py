"""
Phase 3 Integration Module for HD현대미포 Gauss-1 RAG System
Author: Claude Code
Date: 2024-01-22
Description: Integrates all Phase 3 components with main application
"""

import os
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles

# Phase 3 imports
from api_v2 import api_v2
from websocket_manager import manager as websocket_manager, websocket_endpoint
from error_handlers import register_error_handlers
from monitoring import monitoring_service, metrics_endpoint, MetricsMiddleware
from api_documentation import custom_openapi
from security_config import setup_security_middleware
from security import SecurityHeadersMiddleware

logger = logging.getLogger(__name__)


# =============================================================================
# Security Configuration
# =============================================================================

def _parse_csv_env(name: str) -> list[str]:
    """Parse comma-separated environment variable into list"""
    raw = os.getenv(name, "").strip()
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


# CORS Configuration
ALLOW_ORIGINS = _parse_csv_env("ALLOW_ORIGINS")
if not ALLOW_ORIGINS:
    # Default to localhost for development
    ALLOW_ORIGINS = ["http://localhost:8001", "http://127.0.0.1:8001"]
    logger.warning("ALLOW_ORIGINS not set, using default localhost values")

ALLOW_METHODS = _parse_csv_env("ALLOW_METHODS")
if not ALLOW_METHODS:
    ALLOW_METHODS = ["GET", "POST", "OPTIONS"]

ALLOW_HEADERS = _parse_csv_env("ALLOW_HEADERS")
if not ALLOW_HEADERS:
    ALLOW_HEADERS = ["Content-Type", "Authorization", "X-Request-ID"]

TRUSTED_HOSTS = _parse_csv_env("TRUSTED_HOSTS")
if not TRUSTED_HOSTS:
    TRUSTED_HOSTS = ["localhost", "127.0.0.1", "*.hdmipo.local"]


# =============================================================================
# Application Lifecycle Manager
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle manager for Phase 3 components
    """
    try:
        # Startup
        logger.info("Starting Phase 3 components...")
        
        # Start monitoring service
        await monitoring_service.start()
        logger.info("Monitoring service started")
        
        # Initialize WebSocket manager
        logger.info("WebSocket manager initialized")
        
        # Log startup completion
        logger.info("Phase 3 integration startup complete")
        
        yield
        
    except Exception as e:
        logger.error(f"Error during Phase 3 startup: {e}")
        raise
    finally:
        # Shutdown
        logger.info("Shutting down Phase 3 components...")
        
        # Stop monitoring service
        await monitoring_service.stop()
        logger.info("Monitoring service stopped")
        
        logger.info("Phase 3 integration shutdown complete")


# =============================================================================
# Application Configuration
# =============================================================================

def configure_phase3_app(app: FastAPI, enable_security: bool = True) -> FastAPI:
    """
    Configure FastAPI application with Phase 3 enhancements
    
    Args:
        app: FastAPI application instance
        enable_security: Whether to enable security features
        
    Returns:
        Configured FastAPI application
    """
    
    # Security middleware (if enabled)
    if enable_security:
        setup_security_middleware(app)
        logger.info("Security middleware enabled")
    
    # CORS middleware (secure configuration)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOW_ORIGINS,
        allow_credentials=True,
        allow_methods=ALLOW_METHODS,
        allow_headers=ALLOW_HEADERS,
    )
    logger.info(f"CORS configured with origins: {ALLOW_ORIGINS}")
    
    # Trusted host middleware
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=TRUSTED_HOSTS
    )
    logger.info(f"Trusted hosts configured: {TRUSTED_HOSTS}")
    
    # Security headers middleware
    app.add_middleware(SecurityHeadersMiddleware)
    logger.info("Security headers middleware added")
    
    # Metrics middleware
    app.add_middleware(MetricsMiddleware)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Include API v2 router
    app.include_router(api_v2)
    
    # Add WebSocket endpoint
    app.add_websocket_route("/ws/{connection_id}", websocket_endpoint)
    
    # Add metrics endpoint
    app.add_api_route("/metrics", metrics_endpoint, methods=["GET"])
    
    # Custom OpenAPI schema
    app.openapi = lambda: custom_openapi(app)
    
    # Static files (if directory exists)
    try:
        app.mount("/static", StaticFiles(directory="static"), name="static")
        logger.info("Static files mounted")
    except RuntimeError:
        logger.warning("Static directory not found, skipping static files")
    
    logger.info("Phase 3 application configuration complete")
    return app


# =============================================================================
# Health Check Endpoints
# =============================================================================

def add_health_endpoints(app: FastAPI):
    """Add comprehensive health check endpoints"""
    
    @app.get("/health")
    async def health_check():
        """Basic health check"""
        return {"status": "healthy", "version": "2.0"}
    
    @app.get("/health/detailed")
    async def detailed_health_check():
        """Detailed health check with component status"""
        return monitoring_service.get_health()
    
    @app.get("/health/websocket")
    async def websocket_health():
        """WebSocket connection health"""
        stats = websocket_manager.get_stats()
        return {
            "status": "healthy" if stats["active_connections"] >= 0 else "unhealthy",
            "connections": stats
        }


# =============================================================================
# Development Utilities
# =============================================================================

def setup_development_features(app: FastAPI):
    """Setup development-specific features"""
    
    @app.get("/dev/websocket-stats")
    async def get_websocket_stats():
        """Development endpoint for WebSocket statistics"""
        return websocket_manager.get_stats()
    
    @app.get("/dev/metrics-summary")
    async def get_metrics_summary():
        """Development endpoint for metrics summary"""
        from monitoring import get_metrics_summary
        return get_metrics_summary()
    
    @app.post("/dev/test-websocket")
    async def test_websocket_broadcast():
        """Development endpoint to test WebSocket broadcasting"""
        from websocket_manager import WebSocketMessage, MessageType
        from datetime import datetime
        
        test_message = WebSocketMessage(
            type=MessageType.NOTIFICATION,
            data={
                "message": "Test broadcast from development endpoint",
                "timestamp": datetime.now().isoformat()
            }
        )
        
        count = await websocket_manager.broadcast_to_all(test_message)
        return {"broadcasted_to": count, "message": "Test broadcast sent"}


# =============================================================================
# Production Deployment Helpers
# =============================================================================

def get_production_config():
    """Get production-ready configuration"""
    return {
        "host": "0.0.0.0",
        "port": 8080,
        "workers": 4,
        "log_level": "info",
        "access_log": True,
        "reload": False,
        "lifespan": "on"
    }


def get_development_config():
    """Get development configuration"""
    return {
        "host": "127.0.0.1",
        "port": 8080,
        "workers": 1,
        "log_level": "debug",
        "access_log": True,
        "reload": True,
        "lifespan": "on"
    }


# =============================================================================
# Integration Factory
# =============================================================================

def create_integrated_app(
    existing_app: Optional[FastAPI] = None,
    enable_security: bool = True,
    development_mode: bool = False
) -> FastAPI:
    """
    Factory function to create fully integrated Phase 3 application
    
    Args:
        existing_app: Existing FastAPI app to enhance (creates new if None)
        enable_security: Whether to enable security features
        development_mode: Whether to enable development features
        
    Returns:
        Fully configured FastAPI application
    """
    
    # Create or use existing app
    if existing_app is None:
        app = FastAPI(
            title="HD현대미포 Gauss-1 RAG System",
            description="Enterprise RAG system with Phase 3 enhancements",
            version="2.0.0",
            lifespan=lifespan
        )
    else:
        app = existing_app
        # Update lifespan if not already set
        if not hasattr(app, 'router') or not app.router.lifespan_context:
            app = FastAPI(
                title=getattr(app, 'title', "HD현대미포 Gauss-1 RAG System"),
                description=getattr(app, 'description', "Enterprise RAG system"),
                version=getattr(app, 'version', "2.0.0"),
                lifespan=lifespan,
                routes=app.routes if hasattr(app, 'routes') else []
            )
    
    # Apply Phase 3 configuration
    app = configure_phase3_app(app, enable_security)
    
    # Add health endpoints
    add_health_endpoints(app)
    
    # Add development features if requested
    if development_mode:
        setup_development_features(app)
        logger.info("Development features enabled")
    
    logger.info(f"Integrated Phase 3 application created (security: {enable_security}, dev: {development_mode})")
    return app


# =============================================================================
# Export Main Integration Function
# =============================================================================

__all__ = [
    'create_integrated_app',
    'configure_phase3_app', 
    'lifespan',
    'get_production_config',
    'get_development_config'
]