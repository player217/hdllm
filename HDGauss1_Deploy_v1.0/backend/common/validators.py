"""
Input validation utilities for security hardening
Author: Claude Code  
Date: 2025-01-27
Description: P0 unified validation for Ask/Chat request schemas
"""

import re
from typing import List


# Security patterns for injection detection
_SQL_PATTERNS: List[str] = [
    r"(?:\b)(DROP|DELETE|INSERT|UPDATE|EXEC|EXECUTE)(?:\b)",
    r"--|;|\*|\||\\",
]

_XSS_PATTERNS: List[str] = [
    r"<\s*script\b", 
    r"on\w+\s*=", 
    r"javascript:"
]


def sanitize_basic(text: str) -> str:
    """Basic sanitization: remove null bytes and trim whitespace"""
    return text.replace("\x00", "").strip()


def assert_safe(text: str) -> None:
    """Assert text is safe from common injection attacks
    
    Raises:
        ValueError: If potentially malicious patterns are detected
    """
    for pattern in _SQL_PATTERNS + _XSS_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            raise ValueError("Invalid characters in input")