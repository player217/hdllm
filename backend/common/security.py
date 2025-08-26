"""
Security utilities for CORS and input validation
Author: Claude Code
Date: 2025-01-27
Description: P0 Security implementation - CORS allowlist and validation
"""

import os
from typing import List, Dict, Any


def _parse_csv_env(key: str) -> List[str]:
    """Parse CSV environment variable into list"""
    raw = os.getenv(key, "")
    vals = [v.strip() for v in raw.split(",") if v.strip()]
    return vals


def cors_kwargs() -> Dict[str, Any]:
    """Generate CORS middleware configuration with allowlist enforcement"""
    origins = _parse_csv_env("ALLOWED_ORIGINS")
    
    # 기본값(개발): 로컬 UI 포트만 허용
    if not origins:
        origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
    
    return {
        "allow_origins": origins,
        "allow_credentials": True,
        "allow_methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        "allow_headers": ["*"],
        "max_age": 600,
    }