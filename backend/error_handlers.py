"""
Unified Error Handling System for HD현대미포 Gauss-1 RAG System
Author: Claude Code
Date: 2024-01-22
Description: Centralized error handling, logging, and monitoring
"""

import sys
import traceback
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


# =============================================================================
# Error Types and Codes
# =============================================================================

class ErrorCode(str, Enum):
    """Standard error codes"""
    # Client errors (4xx)
    VALIDATION_ERROR = "VALIDATION_ERROR"
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    BAD_REQUEST = "BAD_REQUEST"
    CONFLICT = "CONFLICT"
    
    # Server errors (5xx)
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    DATABASE_ERROR = "DATABASE_ERROR"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    
    # Business logic errors
    INSUFFICIENT_CONTEXT = "INSUFFICIENT_CONTEXT"
    MODEL_NOT_AVAILABLE = "MODEL_NOT_AVAILABLE"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    INVALID_CONFIGURATION = "INVALID_CONFIGURATION"


class APIError(Exception):
    """
    Custom API exception with detailed error information
    """
    def __init__(
        self,
        status_code: int,
        error_code: ErrorCode,
        message: str,
        detail: Optional[Any] = None,
        internal_message: Optional[str] = None
    ):
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        self.detail = detail
        self.internal_message = internal_message or message
        super().__init__(self.message)


# =============================================================================
# Error Response Builder
# =============================================================================

class ErrorResponseBuilder:
    """Build standardized error responses"""
    
    @staticmethod
    def build(
        request: Request,
        status_code: int,
        error_code: str,
        message: str,
        detail: Optional[Any] = None,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build error response dictionary
        
        Args:
            request: FastAPI request object
            status_code: HTTP status code
            error_code: Error code from ErrorCode enum
            message: User-facing error message
            detail: Additional error details
            request_id: Request ID for tracking
            
        Returns:
            Standardized error response dictionary
        """
        return {
            "success": False,
            "error": {
                "code": error_code,
                "message": message,
                "detail": detail,
                "timestamp": datetime.now().isoformat(),
                "path": str(request.url.path) if request else None,
                "method": request.method if request else None,
            },
            "request_id": request_id or getattr(request.state, "request_id", None),
            "version": "2.0"
        }


# =============================================================================
# Exception Handlers
# =============================================================================

async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """
    Handle custom API errors
    """
    # Log internal message (may contain sensitive info)
    logger.error(
        f"API Error: {exc.internal_message}",
        extra={
            "status_code": exc.status_code,
            "error_code": exc.error_code,
            "path": request.url.path,
            "method": request.method
        }
    )
    
    # Return sanitized response
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponseBuilder.build(
            request=request,
            status_code=exc.status_code,
            error_code=exc.error_code,
            message=exc.message,
            detail=exc.detail
        )
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Handle FastAPI HTTP exceptions
    """
    # Map status codes to error codes
    error_code_map = {
        400: ErrorCode.BAD_REQUEST,
        401: ErrorCode.AUTHENTICATION_ERROR,
        403: ErrorCode.AUTHORIZATION_ERROR,
        404: ErrorCode.NOT_FOUND,
        409: ErrorCode.CONFLICT,
        429: ErrorCode.RATE_LIMIT_EXCEEDED,
        500: ErrorCode.INTERNAL_ERROR,
        503: ErrorCode.SERVICE_UNAVAILABLE,
    }
    
    error_code = error_code_map.get(exc.status_code, ErrorCode.INTERNAL_ERROR)
    
    logger.error(f"HTTP Exception: {exc.detail}", extra={"status_code": exc.status_code})
    
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponseBuilder.build(
            request=request,
            status_code=exc.status_code,
            error_code=error_code.value,
            message=exc.detail,
            detail=getattr(exc, "headers", None)
        )
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Handle request validation errors
    """
    # Format validation errors
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })
    
    logger.warning(f"Validation error: {errors}", extra={"path": request.url.path})
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponseBuilder.build(
            request=request,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code=ErrorCode.VALIDATION_ERROR.value,
            message="Validation failed",
            detail=errors
        )
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle unexpected exceptions
    """
    # Log full traceback
    logger.error(
        f"Unhandled exception: {exc}",
        exc_info=True,
        extra={
            "path": request.url.path,
            "method": request.method,
            "traceback": traceback.format_exc()
        }
    )
    
    # Don't expose internal errors in production
    if logger.level <= logging.DEBUG:
        detail = {
            "exception": str(exc),
            "type": type(exc).__name__
        }
    else:
        detail = None
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponseBuilder.build(
            request=request,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code=ErrorCode.INTERNAL_ERROR.value,
            message="An internal error occurred",
            detail=detail
        )
    )


# =============================================================================
# Error Context Manager
# =============================================================================

class ErrorContext:
    """
    Context manager for consistent error handling in functions
    
    Usage:
        async with ErrorContext("operation_name") as ctx:
            # Your code here
            pass
    """
    
    def __init__(self, operation: str, request_id: Optional[str] = None):
        self.operation = operation
        self.request_id = request_id
        self.start_time = None
    
    async def __aenter__(self):
        self.start_time = datetime.now()
        logger.debug(f"Starting {self.operation}", extra={"request_id": self.request_id})
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        duration = (datetime.now() - self.start_time).total_seconds()
        
        if exc_type is None:
            logger.debug(
                f"Completed {self.operation} in {duration:.2f}s",
                extra={"request_id": self.request_id, "duration": duration}
            )
        else:
            logger.error(
                f"Failed {self.operation} after {duration:.2f}s: {exc_val}",
                exc_info=(exc_type, exc_val, exc_tb),
                extra={"request_id": self.request_id, "duration": duration}
            )
        
        # Don't suppress exceptions
        return False


# =============================================================================
# Error Recovery Strategies
# =============================================================================

class ErrorRecovery:
    """
    Strategies for recovering from errors
    """
    
    @staticmethod
    async def with_retry(
        func,
        max_attempts: int = 3,
        backoff_factor: float = 2.0,
        exceptions: tuple = (Exception,)
    ):
        """
        Retry a function with exponential backoff
        
        Args:
            func: Async function to retry
            max_attempts: Maximum number of attempts
            backoff_factor: Multiplier for backoff time
            exceptions: Tuple of exceptions to catch
            
        Returns:
            Result of successful function call
            
        Raises:
            Last exception if all attempts fail
        """
        import asyncio
        
        last_exception = None
        
        for attempt in range(max_attempts):
            try:
                return await func()
            except exceptions as e:
                last_exception = e
                if attempt < max_attempts - 1:
                    wait_time = backoff_factor ** attempt
                    logger.warning(
                        f"Attempt {attempt + 1} failed, retrying in {wait_time}s: {e}"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"All {max_attempts} attempts failed")
        
        raise last_exception
    
    @staticmethod
    async def with_fallback(primary_func, fallback_func):
        """
        Try primary function, fall back to secondary on failure
        
        Args:
            primary_func: Primary async function
            fallback_func: Fallback async function
            
        Returns:
            Result from primary or fallback function
        """
        try:
            return await primary_func()
        except Exception as e:
            logger.warning(f"Primary function failed, using fallback: {e}")
            return await fallback_func()
    
    @staticmethod
    async def with_timeout(func, timeout: float):
        """
        Execute function with timeout
        
        Args:
            func: Async function to execute
            timeout: Timeout in seconds
            
        Returns:
            Result of function
            
        Raises:
            TimeoutError if function doesn't complete in time
        """
        import asyncio
        
        try:
            return await asyncio.wait_for(func(), timeout=timeout)
        except asyncio.TimeoutError:
            raise APIError(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                error_code=ErrorCode.TIMEOUT_ERROR,
                message=f"Operation timed out after {timeout} seconds"
            )


# =============================================================================
# Register Error Handlers
# =============================================================================

def register_error_handlers(app):
    """
    Register all error handlers with FastAPI app
    
    Args:
        app: FastAPI application instance
    """
    app.add_exception_handler(APIError, api_error_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(ValidationError, validation_error_handler)
    app.add_exception_handler(Exception, general_exception_handler)
    
    logger.info("Error handlers registered successfully")