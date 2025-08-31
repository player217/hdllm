"""
Security Configuration Module for HD현대미포 Gauss-1 RAG System
Author: Claude Code
Date: 2024-01-22
Description: Centralized security settings and authentication handlers
"""

import os
import re
import secrets
import hashlib
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, Field, validator
from fastapi import HTTPException, Security, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from jose import JWTError, jwt
from passlib.context import CryptContext


# =============================================================================
# Security Constants
# =============================================================================

# JWT Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# API Key Configuration
API_KEY_NAME = "X-API-Key"
API_KEYS = {
    # Generate secure API keys for production
    "dev_key_001": "development",
    "prod_key_001": "production"
}

# CORS Configuration
CORS_CONFIG = {
    "allow_origins": [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:8001",
        "http://127.0.0.1:8001"
    ],
    "allow_credentials": True,
    "allow_methods": ["GET", "POST", "OPTIONS"],
    "allow_headers": ["Content-Type", "Authorization", "X-API-Key"],
    "max_age": 3600
}

# Rate Limiting Configuration
RATE_LIMIT_CONFIG = {
    "requests_per_minute": 60,
    "requests_per_hour": 1000,
    "burst_size": 10
}


# =============================================================================
# Security Models
# =============================================================================

class QuestionRequest(BaseModel):
    """Validated question request model"""
    question: str = Field(..., min_length=1, max_length=2000, description="User question")
    source: str = Field("mail", pattern="^(mail|doc)$", description="Data source")
    model: str = Field("gemma3:4b", pattern="^[a-zA-Z0-9:._-]+$", description="LLM model")
    
    @validator('question')
    def sanitize_question(cls, v):
        """Prevent SQL injection and dangerous patterns"""
        # Remove potential SQL injection patterns
        dangerous_patterns = [
            r"(DROP|DELETE|INSERT|UPDATE|EXEC|EXECUTE)\s",
            r"(--|;|'|\"|\/\*|\*\/|xp_|sp_|0x)",
            r"(UNION|SELECT|FROM|WHERE)\s.*\s(SELECT|FROM|WHERE)",
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, v, re.IGNORECASE):
                raise ValueError(f"Invalid characters or patterns detected in question")
        
        # Additional Korean-specific validation
        if len(v.strip()) == 0:
            raise ValueError("Question cannot be empty")
            
        return v.strip()
    
    @validator('model')
    def validate_model(cls, v):
        """Validate model name format"""
        allowed_models = ["gemma3:4b", "llama2:7b", "mistral:7b"]
        if v not in allowed_models:
            raise ValueError(f"Model {v} not in allowed list")
        return v


class TokenData(BaseModel):
    """JWT Token data model"""
    username: Optional[str] = None
    user_id: Optional[str] = None
    exp: Optional[datetime] = None


class UserLogin(BaseModel):
    """User login request model"""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=100)


# =============================================================================
# PII Masking Utilities
# =============================================================================

class EnhancedPIIMasker:
    """Enhanced PII detection and masking for Korean text"""
    
    patterns = {
        # Korean patterns
        "korean_ssn": r"\d{6}[-\s]?[1-4]\d{6}",  # 주민등록번호
        "korean_phone": r"01[0-9][-\s]?\d{3,4}[-\s]?\d{4}",  # 휴대폰
        "korean_tel": r"0[2-6][0-9]?[-\s]?\d{3,4}[-\s]?\d{4}",  # 일반전화
        "korean_bizno": r"\d{3}[-\s]?\d{2}[-\s]?\d{5}",  # 사업자번호
        
        # Financial patterns
        "card_number": r"\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}",
        "account_number": r"\d{3,6}[-\s]?\d{2,6}[-\s]?\d{1,6}[-\s]?\d{1,6}",
        
        # Personal info patterns
        "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "ip_address": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
        
        # HD현대 specific patterns
        "employee_id": r"HD\d{6,8}",
        "doc_id": r"DOC-\d{4}-\d{6}",
    }
    
    def mask(self, text: str) -> str:
        """Mask all PII in text"""
        masked_text = text
        
        for pattern_name, pattern in self.patterns.items():
            def replacer(match):
                # Keep partial info for debugging
                matched = match.group()
                if len(matched) > 4:
                    return f"[{pattern_name.upper()}_***{matched[-3:]}]"
                else:
                    return f"[{pattern_name.upper()}_MASKED]"
            
            masked_text = re.sub(pattern, replacer, masked_text, flags=re.IGNORECASE)
        
        return masked_text
    
    def detect_pii(self, text: str) -> Dict[str, List[str]]:
        """Detect PII patterns in text"""
        detected = {}
        
        for pattern_name, pattern in self.patterns.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                detected[pattern_name] = matches
        
        return detected


# =============================================================================
# Authentication Handlers
# =============================================================================

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate password hash"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)) -> TokenData:
    """Verify JWT token"""
    token = credentials.credentials
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Could not validate credentials",
            )
        return TokenData(username=username)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )


def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """Verify API key"""
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API key required"
        )
    
    if api_key not in API_KEYS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key"
        )
    
    return API_KEYS[api_key]


# Optional: Combined authentication (API key OR JWT)
def get_current_user(
    api_key: Optional[str] = Security(api_key_header),
    token: Optional[HTTPAuthorizationCredentials] = Security(security)
) -> str:
    """Get current user from API key or JWT token"""
    # Try API key first
    if api_key and api_key in API_KEYS:
        return f"api_key_user_{API_KEYS[api_key]}"
    
    # Try JWT token
    if token:
        token_data = verify_token(token)
        return token_data.username
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Authentication required"
    )


# =============================================================================
# Security Middleware
# =============================================================================

class SecurityMiddleware:
    """Custom security middleware for additional checks"""
    
    def __init__(self, app):
        self.app = app
        self.rate_limiter = {}
    
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            # Extract client IP
            client_ip = None
            for header_name, header_value in scope["headers"]:
                if header_name == b"x-forwarded-for":
                    client_ip = header_value.decode().split(",")[0].strip()
                    break
            
            if not client_ip:
                client_ip = scope["client"][0] if scope["client"] else "unknown"
            
            # Rate limiting check
            current_time = datetime.now()
            if client_ip in self.rate_limiter:
                requests = self.rate_limiter[client_ip]
                # Clean old requests
                requests = [r for r in requests if (current_time - r).seconds < 60]
                
                if len(requests) >= RATE_LIMIT_CONFIG["requests_per_minute"]:
                    response = Response(content="Rate limit exceeded", status_code=429)
                    await response(scope, receive, send)
                    return
                
                requests.append(current_time)
                self.rate_limiter[client_ip] = requests
            else:
                self.rate_limiter[client_ip] = [current_time]
        
        await self.app(scope, receive, send)


# =============================================================================
# Input Sanitization
# =============================================================================

def sanitize_file_path(path: str) -> str:
    """Sanitize file paths to prevent directory traversal"""
    # Remove any directory traversal attempts
    path = path.replace("..", "")
    path = path.replace("~/", "")
    path = path.replace("//", "/")
    
    # Ensure path doesn't start with system directories
    forbidden_prefixes = ["/etc", "/usr", "/bin", "/sbin", "/sys", "/proc"]
    for prefix in forbidden_prefixes:
        if path.startswith(prefix):
            raise ValueError(f"Access to {prefix} is forbidden")
    
    return path


def validate_json_input(data: dict, max_depth: int = 10) -> dict:
    """Validate JSON input to prevent deep nesting attacks"""
    def check_depth(obj, current_depth=0):
        if current_depth > max_depth:
            raise ValueError(f"JSON nesting depth exceeds maximum of {max_depth}")
        
        if isinstance(obj, dict):
            for value in obj.values():
                check_depth(value, current_depth + 1)
        elif isinstance(obj, list):
            for item in obj:
                check_depth(item, current_depth + 1)
    
    check_depth(data)
    return data


# =============================================================================
# Logging Security
# =============================================================================

def sanitize_log_message(message: str) -> str:
    """Sanitize log messages to prevent log injection"""
    # Remove newlines and carriage returns
    message = message.replace('\n', ' ').replace('\r', ' ')
    
    # Mask PII
    masker = EnhancedPIIMasker()
    message = masker.mask(message)
    
    return message


# =============================================================================
# Security Middleware Setup
# =============================================================================

def setup_security_middleware(app):
    """Setup security middleware for the application"""
    # Add security headers middleware
    app.add_middleware(SecurityMiddleware)
    
    # Add CORS middleware
    from fastapi.middleware.cors import CORSMiddleware
    app.add_middleware(CORSMiddleware, **CORS_CONFIG)
    
    return app