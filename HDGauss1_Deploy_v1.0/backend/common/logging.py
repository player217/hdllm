"""
Enhanced logging system with PII masking and structured output
Author: Claude Code
Date: 2025-01-28
Description: P1-3 - Structured logging with PII protection and request correlation
"""
import logging
import re
import json
import hashlib
from typing import Any, Dict, Optional, Pattern, Tuple, List
from contextvars import ContextVar
from datetime import datetime

# Request context variables for correlation
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")
source_ctx: ContextVar[str] = ContextVar("source", default="-")
namespace_ctx: ContextVar[str] = ContextVar("namespace", default="-")
scope_ctx: ContextVar[str] = ContextVar("scope", default="personal")  # Dual routing scope

class PiiRedactor(logging.Filter):
    """
    PII masking filter for Korean and international sensitive data
    Extends patterns from security_config.py for logging protection
    """
    
    # Comprehensive PII patterns with Korean support
    PATTERNS: List[Tuple[Pattern, str]] = [
        # Korean Personal Information
        (re.compile(r'\b\d{6}[-\s]?[1-4]\d{6}\b'), '******-*******'),  # 주민등록번호
        (re.compile(r'\b01[0-9][-\s]?\d{3,4}[-\s]?\d{4}\b'), '010-****-****'),  # 휴대폰
        (re.compile(r'\b0[2-6][0-9]?[-\s]?\d{3,4}[-\s]?\d{4}\b'), '0**-****-****'),  # 일반전화
        
        # Financial Information
        (re.compile(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'), '****-****-****-****'),  # Credit card
        (re.compile(r'\b\d{3,6}[-\s]?\d{2,6}[-\s]?\d{1,6}[-\s]?\d{1,6}\b'), '***-****-****'),  # Account
        (re.compile(r'\b\d{3}[-\s]?\d{2}[-\s]?\d{5}\b'), '***-**-*****'),  # Business number
        
        # Email and Network
        (re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'), '***@***.***'),  # Email
        (re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'), '***.***.***.***'),  # IP address
        
        # HD Hyundai Specific
        (re.compile(r'\bHD\d{6,8}\b'), 'HD******'),  # Employee ID
        (re.compile(r'\bDOC-\d{4}-\d{6}\b'), 'DOC-****-******'),  # Document ID
        
        # Additional Korean formats
        (re.compile(r'\b\d{4,6}[-\s]?\d{1,2}[-\s]?\d{1,2}\b'), '****-**-**'),  # Date formats that might be birth dates
        (re.compile(r'[가-힣]{2,4}\s*\d{4,8}'), '***_****'),  # Name with numbers (potential ID)
    ]
    
    def __init__(self, enabled: bool = True):
        super().__init__()
        self.enabled = enabled
        self.masked_count = 0  # Track masking operations
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter and mask PII in log records"""
        if self.enabled:
            # Mask message
            msg = str(record.getMessage())
            original_msg = msg
            
            for pattern, replacement in self.PATTERNS:
                msg = pattern.sub(replacement, msg)
            
            # Count masks applied
            if msg != original_msg:
                self.masked_count += 1
            
            record.msg = msg
            
            # Mask args if present
            if hasattr(record, 'args') and record.args:
                masked_args = []
                for arg in record.args:
                    arg_str = str(arg)
                    for pattern, replacement in self.PATTERNS:
                        arg_str = pattern.sub(replacement, arg_str)
                    masked_args.append(arg_str)
                record.args = tuple(masked_args)
        
        # Add context information
        record.request_id = request_id_ctx.get()
        record.source = source_ctx.get()
        record.namespace = namespace_ctx.get()
        
        return True

class JsonFormatter(logging.Formatter):
    """Structured JSON log formatter for analysis and monitoring"""
    
    def format(self, record: logging.LogRecord) -> str:
        """Convert log record to structured JSON"""
        
        # Core fields
        log_obj = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": self._safe_get_message(record),
            "request_id": getattr(record, "request_id", "-"),
            "scope": scope_ctx.get(),  # Add scope for dual routing
        }
        
        # Optional context fields
        if hasattr(record, "source") and record.source != "-":
            log_obj["source"] = record.source
        if hasattr(record, "namespace") and record.namespace != "-":
            log_obj["namespace"] = record.namespace
            
        # Location information
        log_obj["location"] = {
            "file": record.pathname,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Exception information
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        
        # Additional context
        if hasattr(record, "extra_context"):
            log_obj["context"] = record.extra_context
            
        return json.dumps(log_obj, ensure_ascii=False, default=str)
    
    def _safe_get_message(self, record: logging.LogRecord) -> str:
        """Safely get message from log record, handling formatting errors"""
        try:
            return record.getMessage()
        except (TypeError, ValueError) as e:
            # Fallback for string formatting errors
            return f"[LOG_FORMAT_ERROR] {record.msg} (args: {record.args}) - Error: {str(e)}"

class TextFormatter(logging.Formatter):
    """Human-readable text formatter with request ID"""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format with request ID included"""
        request_id = getattr(record, "request_id", "-")
        source = getattr(record, "source", "")
        scope = scope_ctx.get()  # Get scope for dual routing
        
        # Build format string
        if source and source != "-":
            prefix = f"[{request_id}][{source}]"
        else:
            prefix = f"[{request_id}]"
            
        record.msg = f"{prefix} {record.msg}"
        return super().format(record)

class AuditLogger:
    """Security audit logger for compliance and monitoring"""
    
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.logger = logging.getLogger("security.audit")
        self.logger.setLevel(logging.INFO)
        
    def log_search(
        self,
        source: str,
        namespace: str,
        query_hash: str,  # Hash instead of raw query
        limit: int,
        threshold: float,
        result_count: int,
        latency_ms: float
    ):
        """Log vector search operations"""
        if not self.enabled:
            return
            
        self.logger.info(
            "VECTOR_SEARCH",
            extra={
                "extra_context": {
                    "event_type": "vector_search",
                    "source": source,
                    "namespace": namespace,
                    "query_hash": query_hash,
                    "limit": limit,
                    "threshold": threshold,
                    "result_count": result_count,
                    "latency_ms": latency_ms,
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }
            }
        )
    
    def log_access(
        self,
        resource: str,
        action: str,
        result: str,
        user_id: Optional[str] = None
    ):
        """Log resource access for security audit"""
        if not self.enabled:
            return
            
        self.logger.info(
            "RESOURCE_ACCESS",
            extra={
                "extra_context": {
                    "event_type": "resource_access",
                    "resource": resource,
                    "action": action,
                    "result": result,
                    "user_id": user_id or "anonymous",
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }
            }
        )
    
    def log_auth(
        self,
        event: str,  # login, logout, failed_auth
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        reason: Optional[str] = None
    ):
        """Log authentication events"""
        if not self.enabled:
            return
            
        # Mask IP if provided
        if ip_address:
            ip_address = re.sub(r'\d+\.\d+\.\d+\.\d+', '***.***.***.***', ip_address)
            
        self.logger.info(
            f"AUTH_{event.upper()}",
            extra={
                "extra_context": {
                    "event_type": f"auth_{event}",
                    "user_id": user_id or "unknown",
                    "ip_address": ip_address,
                    "reason": reason,
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }
            }
        )

def setup_logging(
    level: str = "INFO",
    format_type: str = "json",
    redact_pii: bool = True,
    audit_enabled: bool = True
) -> AuditLogger:
    """
    Configure unified logging system
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_type: Output format ('json' or 'text')
        redact_pii: Enable PII masking
        audit_enabled: Enable security audit logging
        
    Returns:
        AuditLogger instance for security events
    """
    
    # Configure root logger
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper()))
    
    # Clear existing handlers
    root.handlers.clear()
    
    # Create console handler
    handler = logging.StreamHandler()
    
    # Add PII Redactor filter
    pii_filter = PiiRedactor(enabled=redact_pii)
    handler.addFilter(pii_filter)
    
    # Set formatter
    if format_type == "json":
        formatter = JsonFormatter()
    else:
        formatter = TextFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    handler.setFormatter(formatter)
    
    root.addHandler(handler)
    
    # Create and configure audit logger
    audit_logger = AuditLogger(enabled=audit_enabled)
    
    # Also add file handler for audit logs
    if audit_enabled:
        import os
        os.makedirs("logs", exist_ok=True)
        audit_handler = logging.FileHandler(
            f"logs/audit_{datetime.now().strftime('%Y%m%d')}.log",
            encoding='utf-8'
        )
        audit_handler.setFormatter(JsonFormatter())
        audit_handler.addFilter(pii_filter)
        audit_logger.logger.addHandler(audit_handler)
    
    logger = logging.getLogger(__name__)
    logger.info(f"Logging system initialized: level={level}, format={format_type}, pii_redaction={redact_pii}, audit={audit_enabled}")
    
    return audit_logger

def get_query_hash(query: str) -> str:
    """Generate hash of query text for privacy protection"""
    return hashlib.sha256(query.encode()).hexdigest()[:16]

def set_request_context(request_id: str, source: str = "-", namespace: str = "-", scope: str = None):
    """Set context variables for current request"""
    request_id_ctx.set(request_id)
    source_ctx.set(source)
    namespace_ctx.set(namespace)
    
    # Set scope if provided (for dual routing)
    if scope:
        scope_ctx.set(scope)

def clear_request_context():
    """Clear context variables"""
    request_id_ctx.set("-")
    source_ctx.set("-")
    namespace_ctx.set("-")
    scope_ctx.set("personal")  # Reset to default scope

# Utility function for testing
def get_masked_count(logger_name: str = "") -> int:
    """Get count of masked PII entries (for testing/monitoring)"""
    for handler in logging.getLogger(logger_name).handlers:
        for filter in handler.filters:
            if isinstance(filter, PiiRedactor):
                return filter.masked_count
    return 0

# --- Metrics (P1-4) ---
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, CONTENT_TYPE_LATEST, generate_latest
import os

_METRICS_ENABLED = os.getenv("METRICS_ENABLED", "true").lower() == "true"
_METRICS_NS = os.getenv("METRICS_NAMESPACE", "rag")

registry = CollectorRegistry()

# HTTP Metrics
REQ_COUNT = Counter(
    f"{_METRICS_NS}_http_requests_total",
    "HTTP requests",
    ["method", "path", "status"],
    registry=registry,
)
REQ_LATENCY = Histogram(
    f"{_METRICS_NS}_http_request_duration_seconds",
    "HTTP request latency seconds",
    ["method", "path"],
    registry=registry,
)

# Business Metrics
RAG_REQ = Counter(
    f"{_METRICS_NS}_rag_requests_total",
    "RAG requests",
    ["source", "result"],
    registry=registry,
)
EMBED_LAT = Histogram(
    f"{_METRICS_NS}_embed_seconds",
    "Embedding latency seconds",
    ["backend"],
    registry=registry,
)
SEARCH_LAT = Histogram(
    f"{_METRICS_NS}_search_seconds",
    "Vector search latency seconds",
    ["backend", "source"],
    registry=registry,
)
QDRANT_ERR = Counter(
    f"{_METRICS_NS}_qdrant_errors_total",
    "Qdrant errors",
    ["type"],
    registry=registry,
)

# Cache Metrics (additional)
CACHE_HITS = Counter(
    f"{_METRICS_NS}_cache_hits_total",
    "Cache hits",
    ["cache_type"],
    registry=registry,
)
CACHE_MISSES = Counter(
    f"{_METRICS_NS}_cache_misses_total",
    "Cache misses",
    ["cache_type"],
    registry=registry,
)

# Active Connections
ACTIVE_CONNECTIONS = Gauge(
    f"{_METRICS_NS}_active_connections",
    "Active connections",
    registry=registry,
)

# LLM Token Metrics
LLM_TOKENS = Counter(
    f"{_METRICS_NS}_llm_tokens_total",
    "LLM tokens used",
    ["model", "type"],  # type: prompt/completion
    registry=registry,
)

def prometheus_app(scope):
    """Minimal ASGI app for /metrics endpoint"""
    async def app(receive, send):
        if not _METRICS_ENABLED:
            body = b"metrics disabled"
            await send({"type": "http.response.start", "status": 404, "headers": []})
            await send({"type": "http.response.body", "body": body})
            return
        output = generate_latest(registry)
        await send({"type": "http.response.start", "status": 200,
                    "headers": [(b"content-type", CONTENT_TYPE_LATEST.encode())]})
        await send({"type": "http.response.body", "body": output})
    return app