"""
API Documentation Module for HD현대미포 Gauss-1 RAG System
Author: Claude Code
Date: 2024-01-22
Description: OpenAPI/Swagger documentation generation and customization
"""

from typing import Dict, Any
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html


# =============================================================================
# OpenAPI Schema Customization
# =============================================================================

def custom_openapi(app: FastAPI) -> Dict[str, Any]:
    """
    Generate custom OpenAPI schema
    
    Args:
        app: FastAPI application instance
        
    Returns:
        OpenAPI schema dictionary
    """
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="HD현대미포 Gauss-1 RAG System API",
        version="2.0.0",
        description="""
# HD현대미포 선각기술부 RAG 시스템 API

## 개요
HD현대미포 선각기술부의 문서 검색 및 질의응답을 위한 RAG (Retrieval-Augmented Generation) 시스템 API입니다.

## 주요 기능
- 🔍 **의미 기반 검색**: 한국어 문서에 대한 고급 검색
- 💬 **AI 질의응답**: GPT 기반 자연어 응답
- 📄 **문서 관리**: 문서 업로드, 인덱싱, 관리
- 🔄 **실시간 통신**: WebSocket을 통한 실시간 업데이트
- 🔐 **보안**: JWT 기반 인증 및 API 키 지원

## 인증 방법

### JWT Bearer Token
```
Authorization: Bearer <your-jwt-token>
```

### API Key
```
X-API-Key: <your-api-key>
```

## Rate Limiting
- 일반 사용자: 100 requests/minute
- Premium 사용자: 1000 requests/minute

## 응답 형식
모든 응답은 다음 표준 형식을 따릅니다:
```json
{
    "success": true,
    "data": {},
    "error": null,
    "timestamp": "2024-01-22T10:00:00Z",
    "request_id": "uuid",
    "version": "2.0"
}
```

## 에러 코드
| Code | Description |
|------|-------------|
| VALIDATION_ERROR | 입력 검증 실패 |
| AUTHENTICATION_ERROR | 인증 실패 |
| AUTHORIZATION_ERROR | 권한 부족 |
| NOT_FOUND | 리소스를 찾을 수 없음 |
| RATE_LIMIT_EXCEEDED | 요청 제한 초과 |
| INTERNAL_ERROR | 서버 내부 오류 |

## 문의
- Email: tech@hdmipoeng.com
- Documentation: https://docs.hdmipoeng.com
        """,
        routes=app.routes,
        tags=[
            {
                "name": "authentication",
                "description": "사용자 인증 관련 엔드포인트"
            },
            {
                "name": "chat",
                "description": "채팅 및 RAG 관련 엔드포인트"
            },
            {
                "name": "documents",
                "description": "문서 관리 엔드포인트"
            },
            {
                "name": "search",
                "description": "검색 관련 엔드포인트"
            },
            {
                "name": "admin",
                "description": "관리자 기능 엔드포인트"
            },
            {
                "name": "monitoring",
                "description": "시스템 모니터링 엔드포인트"
            }
        ],
        servers=[
            {
                "url": "http://localhost:8080",
                "description": "Local development server"
            },
            {
                "url": "https://api.hdmipoeng.com",
                "description": "Production server"
            }
        ]
    )
    
    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT Bearer token authentication"
        },
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "API key authentication"
        }
    }
    
    # Add example schemas
    openapi_schema["components"]["schemas"]["ErrorResponse"] = {
        "type": "object",
        "properties": {
            "success": {
                "type": "boolean",
                "example": False
            },
            "error": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "example": "VALIDATION_ERROR"
                    },
                    "message": {
                        "type": "string",
                        "example": "Validation failed"
                    },
                    "detail": {
                        "type": "object",
                        "example": {}
                    },
                    "timestamp": {
                        "type": "string",
                        "format": "date-time"
                    }
                }
            },
            "request_id": {
                "type": "string",
                "format": "uuid"
            },
            "version": {
                "type": "string",
                "example": "2.0"
            }
        }
    }
    
    openapi_schema["components"]["schemas"]["StandardResponse"] = {
        "type": "object",
        "properties": {
            "success": {
                "type": "boolean",
                "example": True
            },
            "data": {
                "type": "object",
                "example": {}
            },
            "error": {
                "type": "object",
                "nullable": True
            },
            "timestamp": {
                "type": "string",
                "format": "date-time"
            },
            "request_id": {
                "type": "string",
                "format": "uuid"
            },
            "version": {
                "type": "string",
                "example": "2.0"
            }
        }
    }
    
    # Add global security (can be overridden per endpoint)
    openapi_schema["security"] = [
        {"BearerAuth": []},
        {"ApiKeyAuth": []}
    ]
    
    # Add external documentation
    openapi_schema["externalDocs"] = {
        "description": "Full API documentation",
        "url": "https://docs.hdmipoeng.com/api"
    }
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


# =============================================================================
# Custom Documentation Pages
# =============================================================================

async def get_swagger_ui(*, dark: bool = False) -> str:
    """
    Get custom Swagger UI HTML
    
    Args:
        dark: Enable dark mode
        
    Returns:
        HTML string for Swagger UI
    """
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="HD현대미포 Gauss-1 API - Swagger UI",
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
        swagger_ui_parameters={
            "deepLinking": True,
            "persistAuthorization": True,
            "displayOperationId": True,
            "defaultModelsExpandDepth": 1,
            "defaultModelExpandDepth": 1,
            "displayRequestDuration": True,
            "filter": True,
            "showExtensions": True,
            "showCommonExtensions": True,
            "syntaxHighlight.theme": "monokai" if dark else "agate",
            "tryItOutEnabled": True,
            "requestSnippetsEnabled": True,
            "requestSnippets": {
                "generators": {
                    "curl_bash": {
                        "title": "cURL (bash)",
                        "syntax": "bash"
                    },
                    "curl_powershell": {
                        "title": "cURL (PowerShell)",
                        "syntax": "powershell"
                    },
                    "python": {
                        "title": "Python (requests)",
                        "syntax": "python"
                    },
                    "javascript": {
                        "title": "JavaScript (fetch)",
                        "syntax": "javascript"
                    }
                }
            }
        }
    )


async def get_redoc() -> str:
    """
    Get ReDoc HTML
    
    Returns:
        HTML string for ReDoc
    """
    return get_redoc_html(
        openapi_url="/openapi.json",
        title="HD현대미포 Gauss-1 API - ReDoc",
        redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js",
    )


# =============================================================================
# API Examples
# =============================================================================

API_EXAMPLES = {
    "ask": {
        "summary": "RAG 질의응답 예제",
        "description": "선각기술부 관련 질문",
        "value": {
            "question": "선각기술부의 주요 업무는 무엇인가요?",
            "source": "mail",
            "model": "gemma3:4b",
            "context_limit": 3,
            "temperature": 0.3,
            "stream": True
        }
    },
    "search": {
        "summary": "의미 검색 예제",
        "description": "회의록 검색",
        "value": {
            "query": "2024년 1월 안전 회의",
            "search_type": "semantic",
            "filters": {
                "date_from": "2024-01-01",
                "date_to": "2024-01-31",
                "document_type": "meeting"
            },
            "limit": 10
        }
    },
    "document_upload": {
        "summary": "문서 업로드 예제",
        "description": "PDF 문서 업로드",
        "value": {
            "filename": "meeting_notes_2024.pdf",
            "content_type": "application/pdf",
            "tags": ["meeting", "2024", "safety"],
            "metadata": {
                "department": "선각기술부",
                "author": "홍길동",
                "date": "2024-01-22"
            }
        }
    }
}


# =============================================================================
# API Version Management
# =============================================================================

class APIVersionManager:
    """
    Manage API versions and compatibility
    """
    
    def __init__(self):
        self.versions = {
            "1.0": {
                "status": "deprecated",
                "deprecation_date": "2024-03-01",
                "sunset_date": "2024-06-01",
                "migration_guide": "https://docs.hdmipoeng.com/migration/v1-to-v2"
            },
            "2.0": {
                "status": "current",
                "release_date": "2024-01-22",
                "features": [
                    "Standardized response format",
                    "WebSocket support",
                    "Enhanced security",
                    "Prometheus metrics"
                ]
            },
            "3.0": {
                "status": "planned",
                "expected_date": "2024-06-01",
                "features": [
                    "GraphQL support",
                    "Multi-language support",
                    "Advanced analytics"
                ]
            }
        }
        
        self.current_version = "2.0"
        self.supported_versions = ["1.0", "2.0"]
    
    def get_version_info(self, version: str = None) -> Dict[str, Any]:
        """
        Get information about API version
        
        Args:
            version: Version string (default: current)
            
        Returns:
            Version information dictionary
        """
        if version is None:
            version = self.current_version
        
        if version not in self.versions:
            return {
                "error": f"Unknown version: {version}",
                "supported_versions": self.supported_versions
            }
        
        return {
            "version": version,
            "info": self.versions[version],
            "current": version == self.current_version,
            "supported": version in self.supported_versions
        }
    
    def check_compatibility(self, client_version: str) -> bool:
        """
        Check if client version is compatible
        
        Args:
            client_version: Client's API version
            
        Returns:
            True if compatible, False otherwise
        """
        return client_version in self.supported_versions
    
    def get_deprecation_headers(self, version: str) -> Dict[str, str]:
        """
        Get deprecation headers for response
        
        Args:
            version: API version
            
        Returns:
            Dictionary of headers to add
        """
        headers = {}
        
        if version in self.versions and self.versions[version]["status"] == "deprecated":
            info = self.versions[version]
            headers["Deprecation"] = f"version={version}"
            headers["Sunset"] = info.get("sunset_date", "")
            headers["Link"] = f'<{info.get("migration_guide", "")}>; rel="deprecation"'
        
        return headers


# =============================================================================
# API Metadata
# =============================================================================

API_METADATA = {
    "name": "HD현대미포 Gauss-1 RAG System API",
    "version": "2.0.0",
    "description": "Enterprise RAG system for HD Hyundai MIPO",
    "contact": {
        "name": "선각기술부",
        "email": "tech@hdmipoeng.com",
        "url": "https://hdmipoeng.com"
    },
    "license": {
        "name": "Proprietary",
        "url": "https://hdmipoeng.com/license"
    },
    "terms_of_service": "https://hdmipoeng.com/terms",
    "documentation": "https://docs.hdmipoeng.com",
    "status_page": "https://status.hdmipoeng.com"
}


# Create global version manager
version_manager = APIVersionManager()