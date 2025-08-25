"""
Authentication Routes for HD현대미포 Gauss-1 RAG System
Author: Claude Code
Date: 2024-01-22
Description: JWT authentication endpoints
"""

from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from security_config import (
    UserLogin,
    create_access_token,
    verify_password,
    get_password_hash,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS
)

# Create router
router = APIRouter(prefix="/auth", tags=["authentication"])

# Temporary user database (replace with actual database in production)
USERS_DB = {
    "admin": {
        "username": "admin",
        "hashed_password": get_password_hash("admin1234"),
        "full_name": "Administrator",
        "email": "admin@hdmipoeng.com",
        "is_active": True,
        "is_admin": True
    },
    "user": {
        "username": "user",
        "hashed_password": get_password_hash("user1234"),
        "full_name": "Regular User",
        "email": "user@hdmipoeng.com",
        "is_active": True,
        "is_admin": False
    }
}


def authenticate_user(username: str, password: str):
    """Authenticate user with username and password"""
    user = USERS_DB.get(username)
    if not user:
        return False
    if not verify_password(password, user["hashed_password"]):
        return False
    return user


@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Login endpoint for OAuth2 password flow
    
    Returns:
        - access_token: JWT token for authentication
        - token_type: Always "bearer"
        - expires_in: Token expiration time in seconds
    """
    user = authenticate_user(form_data.username, form_data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"], "email": user["email"]},
        expires_delta=access_token_expires
    )
    
    # Create refresh token
    refresh_token_expires = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    refresh_token = create_access_token(
        data={"sub": user["username"], "type": "refresh"},
        expires_delta=refresh_token_expires
    )
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }


@router.post("/login/simple")
async def login_simple(user_data: UserLogin):
    """
    Simple login endpoint with JSON body
    
    Args:
        user_data: UserLogin model with username and password
    
    Returns:
        - access_token: JWT token for authentication
        - token_type: Always "bearer"
    """
    user = authenticate_user(user_data.username, user_data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"], "email": user["email"]},
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "username": user["username"],
        "full_name": user["full_name"],
        "is_admin": user.get("is_admin", False)
    }


@router.post("/refresh")
async def refresh_token(refresh_token: str):
    """
    Refresh access token using refresh token
    
    Args:
        refresh_token: Valid refresh token
    
    Returns:
        - access_token: New JWT access token
        - token_type: Always "bearer"
    """
    # Verify refresh token
    try:
        from jose import jwt
        from security_config import SECRET_KEY, ALGORITHM
        
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        token_type = payload.get("type")
        
        if username is None or token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        
        # Check if user still exists and is active
        user = USERS_DB.get(username)
        if not user or not user.get("is_active", False):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        # Create new access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user["username"], "email": user["email"]},
            expires_delta=access_token_expires
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )


@router.get("/verify")
async def verify_token(current_user: str = Depends(get_current_user)):
    """
    Verify if the current token is valid
    
    Returns:
        - valid: True if token is valid
        - username: Current user's username
    """
    from security_config import get_current_user
    
    return {
        "valid": True,
        "username": current_user
    }


@router.post("/logout")
async def logout(current_user: str = Depends(get_current_user)):
    """
    Logout endpoint (client should discard token)
    
    Note: Since JWTs are stateless, actual logout is handled client-side
    by removing the token from storage. This endpoint can be used to
    log the logout event or blacklist the token if needed.
    """
    from security_config import get_current_user
    
    # In production, you might want to:
    # 1. Add token to a blacklist
    # 2. Log the logout event
    # 3. Clear any server-side session data
    
    return {
        "message": "Successfully logged out",
        "username": current_user
    }