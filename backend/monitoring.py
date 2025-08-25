"""
Monitoring and Metrics Collection for HD현대미포 Gauss-1 RAG System
Author: Claude Code
Date: 2024-01-22
Description: Prometheus metrics, logging, and system monitoring
"""

import time
import psutil
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from functools import wraps
import asyncio

from prometheus_client import (
    Counter, Histogram, Gauge, Summary,
    generate_latest, CONTENT_TYPE_LATEST,
    CollectorRegistry
)
from fastapi import Request, Response
from fastapi.responses import PlainTextResponse

logger = logging.getLogger(__name__)

# =============================================================================
# Metrics Registry
# =============================================================================

# Create custom registry to avoid conflicts
registry = CollectorRegistry()

# =============================================================================
# Prometheus Metrics
# =============================================================================

# Request metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status'],
    registry=registry
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    registry=registry
)

http_request_size_bytes = Summary(
    'http_request_size_bytes',
    'HTTP request size in bytes',
    ['method', 'endpoint'],
    registry=registry
)

http_response_size_bytes = Summary(
    'http_response_size_bytes',
    'HTTP response size in bytes',
    ['method', 'endpoint'],
    registry=registry
)

# WebSocket metrics
websocket_connections_active = Gauge(
    'websocket_connections_active',
    'Number of active WebSocket connections',
    registry=registry
)

websocket_messages_total = Counter(
    'websocket_messages_total',
    'Total WebSocket messages',
    ['direction', 'type'],
    registry=registry
)

# RAG metrics
rag_requests_total = Counter(
    'rag_requests_total',
    'Total RAG requests',
    ['source', 'model'],
    registry=registry
)

rag_request_duration_seconds = Histogram(
    'rag_request_duration_seconds',
    'RAG request duration in seconds',
    ['source', 'model'],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
    registry=registry
)

embedding_generation_duration_seconds = Histogram(
    'embedding_generation_duration_seconds',
    'Embedding generation duration in seconds',
    registry=registry
)

vector_search_duration_seconds = Histogram(
    'vector_search_duration_seconds',
    'Vector search duration in seconds',
    ['collection'],
    registry=registry
)

llm_generation_duration_seconds = Histogram(
    'llm_generation_duration_seconds',
    'LLM generation duration in seconds',
    ['model'],
    registry=registry
)

# Cache metrics
cache_hits_total = Counter(
    'cache_hits_total',
    'Total cache hits',
    ['cache_type'],
    registry=registry
)

cache_misses_total = Counter(
    'cache_misses_total',
    'Total cache misses',
    ['cache_type'],
    registry=registry
)

cache_size = Gauge(
    'cache_size',
    'Current cache size',
    ['cache_type'],
    registry=registry
)

# System metrics
system_cpu_usage_percent = Gauge(
    'system_cpu_usage_percent',
    'System CPU usage percentage',
    registry=registry
)

system_memory_usage_percent = Gauge(
    'system_memory_usage_percent',
    'System memory usage percentage',
    registry=registry
)

system_disk_usage_percent = Gauge(
    'system_disk_usage_percent',
    'System disk usage percentage',
    ['mount_point'],
    registry=registry
)

process_cpu_usage_percent = Gauge(
    'process_cpu_usage_percent',
    'Process CPU usage percentage',
    registry=registry
)

process_memory_usage_bytes = Gauge(
    'process_memory_usage_bytes',
    'Process memory usage in bytes',
    registry=registry
)

# Error metrics
errors_total = Counter(
    'errors_total',
    'Total errors',
    ['error_type', 'endpoint'],
    registry=registry
)

# =============================================================================
# Metrics Middleware
# =============================================================================

class MetricsMiddleware:
    """
    Middleware for collecting HTTP metrics
    """
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            start_time = time.time()
            
            # Extract request info
            method = scope["method"]
            path = scope["path"]
            
            # Capture request size
            if "content-length" in dict(scope["headers"]):
                request_size = int(dict(scope["headers"])[b"content-length"])
                http_request_size_bytes.labels(method=method, endpoint=path).observe(request_size)
            
            # Process request
            async def send_wrapper(message):
                if message["type"] == "http.response.start":
                    # Capture status code
                    status = message["status"]
                    
                    # Record request metrics
                    duration = time.time() - start_time
                    http_requests_total.labels(
                        method=method,
                        endpoint=path,
                        status=status
                    ).inc()
                    http_request_duration_seconds.labels(
                        method=method,
                        endpoint=path
                    ).observe(duration)
                
                await send(message)
            
            await self.app(scope, receive, send_wrapper)
        else:
            await self.app(scope, receive, send)


# =============================================================================
# Metrics Decorators
# =============================================================================

def track_time(metric: Histogram, **labels):
    """
    Decorator to track function execution time
    
    Args:
        metric: Prometheus Histogram metric
        **labels: Static labels for the metric
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            with metric.labels(**labels).time():
                return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            with metric.labels(**labels).time():
                return func(*args, **kwargs)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


def count_calls(metric: Counter, **labels):
    """
    Decorator to count function calls
    
    Args:
        metric: Prometheus Counter metric
        **labels: Static labels for the metric
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            metric.labels(**labels).inc()
            return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            metric.labels(**labels).inc()
            return func(*args, **kwargs)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


# =============================================================================
# System Metrics Collector
# =============================================================================

class SystemMetricsCollector:
    """
    Collects system-level metrics
    """
    
    def __init__(self, interval: int = 30):
        """
        Initialize system metrics collector
        
        Args:
            interval: Collection interval in seconds
        """
        self.interval = interval
        self.running = False
        self.task = None
    
    async def start(self):
        """Start collecting system metrics"""
        self.running = True
        self.task = asyncio.create_task(self._collect_loop())
        logger.info(f"System metrics collection started (interval: {self.interval}s)")
    
    async def stop(self):
        """Stop collecting system metrics"""
        self.running = False
        if self.task:
            await self.task
        logger.info("System metrics collection stopped")
    
    async def _collect_loop(self):
        """Main collection loop"""
        while self.running:
            try:
                self.collect_metrics()
                await asyncio.sleep(self.interval)
            except Exception as e:
                logger.error(f"Error collecting system metrics: {e}")
                await asyncio.sleep(self.interval)
    
    def collect_metrics(self):
        """Collect current system metrics"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            system_cpu_usage_percent.set(cpu_percent)
            
            # Memory usage
            memory = psutil.virtual_memory()
            system_memory_usage_percent.set(memory.percent)
            
            # Disk usage
            for partition in psutil.disk_partitions():
                if partition.mountpoint:
                    try:
                        usage = psutil.disk_usage(partition.mountpoint)
                        system_disk_usage_percent.labels(
                            mount_point=partition.mountpoint
                        ).set(usage.percent)
                    except PermissionError:
                        pass
            
            # Process metrics
            process = psutil.Process()
            process_cpu_usage_percent.set(process.cpu_percent())
            process_memory_usage_bytes.set(process.memory_info().rss)
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")


# =============================================================================
# Metrics Endpoint
# =============================================================================

async def metrics_endpoint(request: Request) -> Response:
    """
    Prometheus metrics endpoint
    
    Returns metrics in Prometheus text format
    """
    metrics = generate_latest(registry)
    return Response(content=metrics, media_type=CONTENT_TYPE_LATEST)


# =============================================================================
# Monitoring Service
# =============================================================================

class MonitoringService:
    """
    Central monitoring service
    """
    
    def __init__(self):
        self.system_collector = SystemMetricsCollector()
        self.start_time = datetime.now()
    
    async def start(self):
        """Start monitoring services"""
        await self.system_collector.start()
        logger.info("Monitoring service started")
    
    async def stop(self):
        """Stop monitoring services"""
        await self.system_collector.stop()
        logger.info("Monitoring service stopped")
    
    def get_health(self) -> Dict[str, Any]:
        """
        Get service health status
        
        Returns:
            Health status dictionary
        """
        uptime = datetime.now() - self.start_time
        
        return {
            "status": "healthy",
            "uptime_seconds": uptime.total_seconds(),
            "uptime_human": str(uptime),
            "metrics": {
                "http_requests": http_requests_total._value.sum(),
                "websocket_connections": websocket_connections_active._value.get(),
                "errors": errors_total._value.sum(),
            },
            "system": {
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage('/').percent,
            },
            "timestamp": datetime.now().isoformat()
        }
    
    def record_rag_request(
        self,
        source: str,
        model: str,
        duration: float,
        success: bool = True
    ):
        """Record RAG request metrics"""
        rag_requests_total.labels(source=source, model=model).inc()
        rag_request_duration_seconds.labels(source=source, model=model).observe(duration)
        
        if not success:
            errors_total.labels(error_type="rag_error", endpoint="/ask").inc()
    
    def record_cache_access(self, cache_type: str, hit: bool):
        """Record cache access"""
        if hit:
            cache_hits_total.labels(cache_type=cache_type).inc()
        else:
            cache_misses_total.labels(cache_type=cache_type).inc()
    
    def update_cache_size(self, cache_type: str, size: int):
        """Update cache size metric"""
        cache_size.labels(cache_type=cache_type).set(size)


# =============================================================================
# Global Monitoring Instance
# =============================================================================

monitoring_service = MonitoringService()


# =============================================================================
# Utility Functions
# =============================================================================

def get_metrics_summary() -> Dict[str, Any]:
    """
    Get summary of all metrics
    
    Returns:
        Dictionary with metric summaries
    """
    return {
        "http": {
            "total_requests": http_requests_total._value.sum(),
            "avg_duration": http_request_duration_seconds._sum.sum() / max(1, http_request_duration_seconds._count.sum()),
        },
        "websocket": {
            "active_connections": websocket_connections_active._value.get(),
            "total_messages": websocket_messages_total._value.sum(),
        },
        "rag": {
            "total_requests": rag_requests_total._value.sum(),
            "avg_duration": rag_request_duration_seconds._sum.sum() / max(1, rag_request_duration_seconds._count.sum()),
        },
        "cache": {
            "hit_rate": cache_hits_total._value.sum() / max(1, cache_hits_total._value.sum() + cache_misses_total._value.sum()),
            "total_hits": cache_hits_total._value.sum(),
            "total_misses": cache_misses_total._value.sum(),
        },
        "errors": {
            "total": errors_total._value.sum(),
        }
    }