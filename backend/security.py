"""
Security utilities and middleware for HD현대미포 RAG System
Author: Claude Code
Date: 2024-01-22
Description: Security headers, input sanitization, and protection utilities
"""

import re
import unicodedata
from typing import Optional
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses"""
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self'"
        )
        
        # Remove server header
        response.headers.pop("Server", None)
        
        return response


def sanitize_text(text: str, max_length: Optional[int] = None) -> str:
    """
    Sanitize text input to prevent XSS and injection attacks
    
    Args:
        text: Input text to sanitize
        max_length: Optional maximum length
        
    Returns:
        Sanitized text
    """
    if not text:
        return ""
    
    # Remove null bytes
    text = text.replace('\x00', '')
    
    # Strip control characters
    text = strip_control_chars(text)
    
    # Remove dangerous HTML/script tags
    dangerous_patterns = [
        r'<script[^>]*>.*?</script>',
        r'<iframe[^>]*>.*?</iframe>',
        r'<object[^>]*>.*?</object>',
        r'<embed[^>]*>.*?</embed>',
        r'javascript:',
        r'on\w+\s*=',  # Event handlers
        r'<img[^>]+src[\\s]*=[\\s]*["\']javascript:',
    ]
    
    for pattern in dangerous_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.DOTALL)
    
    # Escape HTML entities
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('"', '&quot;')
    text = text.replace("'", '&#x27;')
    
    # Apply length limit if specified
    if max_length and len(text) > max_length:
        text = text[:max_length]
    
    return text.strip()


def strip_control_chars(text: str) -> str:
    """
    Remove control characters from text
    
    Args:
        text: Input text
        
    Returns:
        Text with control characters removed
    """
    if not text:
        return ""
    
    # Remove all control characters except common whitespace
    allowed_chars = ['\t', '\n', '\r']
    return ''.join(
        char for char in text 
        if unicodedata.category(char)[0] != 'C' or char in allowed_chars
    )


def validate_sql_input(text: str) -> bool:
    """
    Check if text contains potential SQL injection patterns
    
    Args:
        text: Input text to validate
        
    Returns:
        False if suspicious patterns detected, True otherwise
    """
    if not text:
        return True
    
    # Common SQL injection patterns
    sql_patterns = [
        r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|EXECUTE|UNION|FROM|WHERE)\b)",
        r"(--|#|/\*|\*/)",  # SQL comments
        r"('[\"`;])",  # Quote characters
        r"(\bOR\b.*=.*)",  # OR conditions
        r"(\bAND\b.*=.*)",  # AND conditions
        r"(xp_|sp_)",  # System stored procedures
        r"(0x[0-9a-fA-F]+)",  # Hex encoding
    ]
    
    text_upper = text.upper()
    for pattern in sql_patterns:
        if re.search(pattern, text_upper):
            return False
    
    return True


def validate_path_traversal(path: str) -> bool:
    """
    Check if path contains directory traversal attempts
    
    Args:
        path: File path to validate
        
    Returns:
        False if traversal patterns detected, True otherwise
    """
    if not path:
        return True
    
    # Path traversal patterns
    traversal_patterns = [
        r"\.\./",  # Unix style
        r"\.\.\\",  # Windows style
        r"%2e%2e",  # URL encoded
        r"\.\.%2f",  # Mixed encoding
        r"/\.\./",  # Hidden traversal
    ]
    
    path_lower = path.lower()
    for pattern in traversal_patterns:
        if re.search(pattern, path_lower):
            return False
    
    # Check for absolute paths trying to escape
    if path.startswith('/') or (len(path) > 1 and path[1] == ':'):
        return False
    
    return True


def validate_command_injection(text: str) -> bool:
    """
    Check if text contains potential command injection patterns
    
    Args:
        text: Input text to validate
        
    Returns:
        False if suspicious patterns detected, True otherwise
    """
    if not text:
        return True
    
    # Command injection patterns
    command_patterns = [
        r"[;&|`$]",  # Shell metacharacters
        r"\$\(",  # Command substitution
        r"`.*`",  # Backtick execution
        r">\s*/dev/",  # Redirection to devices
        r"nc\s+-",  # Netcat
        r"wget\s+",  # File download
        r"curl\s+",  # File download
        r"/bin/",  # Direct binary execution
        r"cmd\.exe",  # Windows command
        r"powershell",  # PowerShell
    ]
    
    text_lower = text.lower()
    for pattern in command_patterns:
        if re.search(pattern, text_lower):
            return False
    
    return True


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent directory traversal and other attacks
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    if not filename:
        return "unnamed"
    
    # Remove path components
    filename = filename.replace('/', '_')
    filename = filename.replace('\\', '_')
    filename = filename.replace('..', '_')
    
    # Remove special characters
    filename = re.sub(r'[^\w\s\-\.]', '', filename)
    
    # Limit length
    max_length = 255
    if len(filename) > max_length:
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        if ext:
            name = name[:max_length - len(ext) - 1]
            filename = f"{name}.{ext}"
        else:
            filename = filename[:max_length]
    
    return filename or "unnamed"