"""
Pydantic Schemas for API Request/Response
Author: Claude Code
Date: 2025-01-27
Description: Phase 2C - Common data models and validation schemas
"""

from typing import List, Dict, Any, Optional, Union, Literal
from pydantic import BaseModel, Field, validator, root_validator, ConfigDict
from datetime import datetime
from enum import Enum
import uuid
import re
from backend.common.validators import sanitize_basic, assert_safe


# Enums
class SourceType(str, Enum):
    """Document source types"""
    MAIL = "mail"
    DOCUMENT = "doc"
    ATTACHMENT = "attachment"
    WEB = "web"


class ModelType(str, Enum):
    """LLM model types"""
    GEMMA3_4B = "gemma3:4b"
    GEMMA3_8B = "gemma3:8b"
    LLAMA3 = "llama3"
    MISTRAL = "mistral"


class StatusType(str, Enum):
    """System status types"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ResponseStatus(str, Enum):
    """API response status"""
    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"


# Base Models
class BaseRequest(BaseModel):
    """Base request model with common fields"""
    request_id: Optional[str] = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique request identifier"
    )
    timestamp: Optional[datetime] = Field(
        default_factory=datetime.utcnow,
        description="Request timestamp"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "request_id": "550e8400-e29b-41d4-a716-446655440000",
                "timestamp": "2024-01-22T10:30:00Z"
            }
        }
    )


class BaseResponse(BaseModel):
    """Base response model with common fields"""
    status: ResponseStatus = Field(
        default=ResponseStatus.SUCCESS,
        description="Response status"
    )
    request_id: str = Field(
        description="Original request ID"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Response timestamp"
    )
    latency_ms: Optional[float] = Field(
        default=None,
        description="Processing time in milliseconds"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "success",
                "request_id": "550e8400-e29b-41d4-a716-446655440000",
                "timestamp": "2024-01-22T10:30:01Z",
                "latency_ms": 1234.56
            }
        }
    )


# Data Models
class Metadata(BaseModel):
    """Document metadata"""
    file_name: Optional[str] = None
    file_path: Optional[str] = None
    author: Optional[str] = None
    created_date: Optional[datetime] = None
    modified_date: Optional[datetime] = None
    department: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    custom_fields: Dict[str, Any] = Field(default_factory=dict)


class Chunk(BaseModel):
    """Text chunk with metadata"""
    text: str = Field(
        min_length=1,
        max_length=10000,
        description="Chunk text content"
    )
    chunk_index: int = Field(
        ge=0,
        description="Chunk index in document"
    )
    total_chunks: int = Field(
        ge=1,
        description="Total number of chunks"
    )
    metadata: Optional[Metadata] = None
    
    @validator('text')
    def validate_text(cls, v):
        """Validate and clean text"""
        v = v.strip()
        if not v:
            raise ValueError("Text cannot be empty")
        # Basic sanitization
        v = v.replace('\x00', '')  # Remove null bytes
        return v


class Vector(BaseModel):
    """Embedding vector with metadata"""
    vector: List[float] = Field(
        description="Embedding vector"
    )
    dimension: int = Field(
        ge=1,
        description="Vector dimension"
    )
    model_name: str = Field(
        description="Embedding model name"
    )
    
    @validator('vector')
    def validate_vector(cls, v, values):
        """Validate vector dimension"""
        if 'dimension' in values and len(v) != values['dimension']:
            raise ValueError(f"Vector dimension mismatch: expected {values['dimension']}, got {len(v)}")
        return v


class Document(BaseModel):
    """Document model"""
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Document ID"
    )
    source_type: SourceType = Field(
        description="Document source type"
    )
    content: str = Field(
        min_length=1,
        description="Document content"
    )
    chunks: List[Chunk] = Field(
        default_factory=list,
        description="Document chunks"
    )
    metadata: Metadata = Field(
        default_factory=Metadata,
        description="Document metadata"
    )
    vector: Optional[Vector] = None
    score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Relevance score"
    )


# Request Models
class SearchRequest(BaseRequest):
    """Search request model"""
    query: str = Field(
        min_length=1,
        max_length=2000,
        description="Search query"
    )
    
    @validator('query')
    def validate_query(cls, v):
        """Validate and sanitize query"""
        # Remove null bytes
        v = v.replace('\x00', '')
        # Check for SQL injection patterns
        sql_patterns = [
            r"(DROP|DELETE|INSERT|UPDATE|EXEC|EXECUTE)",
            r"(--|;|'|\"|\*|\||\\)"
        ]
        for pattern in sql_patterns:
            if re.search(pattern, v, re.IGNORECASE):
                raise ValueError("Invalid characters in query")
        return v.strip()
    source: SourceType = Field(
        default=SourceType.MAIL,
        description="Search source"
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Result limit"
    )
    threshold: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Similarity threshold"
    )
    filters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Search filters"
    )
    include_vectors: bool = Field(
        default=False,
        description="Include vectors in response"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "선각기술부 회의록",
                "source": "mail",
                "limit": 10,
                "threshold": 0.3
            }
        }
    )


class EmbeddingRequest(BaseRequest):
    """Embedding generation request"""
    texts: List[str] = Field(
        min_length=1,
        max_length=100,
        description="Texts to embed"
    )
    model_name: str = Field(
        default="BAAI/bge-m3",
        description="Embedding model name"
    )
    normalize: bool = Field(
        default=True,
        description="Normalize embeddings"
    )
    batch_size: int = Field(
        default=32,
        ge=1,
        le=256,
        description="Batch size for processing"
    )
    
    @validator('texts')
    def validate_texts(cls, v):
        """Validate texts"""
        for text in v:
            if not text.strip():
                raise ValueError("Empty text in list")
        return v


class DocumentRequest(BaseRequest):
    """Document processing request"""
    file_path: str = Field(
        description="Document file path"
    )
    source_type: SourceType = Field(
        default=SourceType.DOCUMENT,
        description="Document source type"
    )
    chunk_size: int = Field(
        default=1000,
        ge=100,
        le=5000,
        description="Chunk size in characters"
    )
    chunk_overlap: int = Field(
        default=200,
        ge=0,
        le=500,
        description="Chunk overlap in characters"
    )
    extract_metadata: bool = Field(
        default=True,
        description="Extract document metadata"
    )


class ChatRequest(BaseRequest):
    """Chat/RAG request model"""
    question: str = Field(
        min_length=1,
        max_length=2000,
        description="User question"
    )
    
    @validator('question')
    def validate_question(cls, v: str):
        """Validate and sanitize question using common validators"""
        v = sanitize_basic(v)
        assert_safe(v)
        return v
    source: SourceType = Field(
        default=SourceType.MAIL,
        description="Knowledge source"
    )
    model: ModelType = Field(
        default=ModelType.GEMMA3_4B,
        description="LLM model"
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Generation temperature"
    )
    max_tokens: int = Field(
        default=2000,
        ge=1,
        le=8000,
        description="Maximum tokens to generate"
    )
    stream: bool = Field(
        default=True,
        description="Stream response"
    )
    include_sources: bool = Field(
        default=True,
        description="Include source documents"
    )


# Enhanced Request Models for Pipeline
class AskRequest(BaseRequest):
    """Enhanced ask request with pipeline support"""
    query: str = Field(min_length=1, max_length=2000, description="Search query")
    source: SourceType = Field(default=SourceType.MAIL, description="Data source")
    model: ModelType = Field(default=ModelType.GEMMA3_4B, description="LLM model")
    top_k: int = Field(default=10, ge=1, le=100, description="Number of results")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Search filters")
    stream: bool = Field(default=False, description="Enable streaming response")
    
    @root_validator(pre=True)
    def _compat_question_alias(cls, values):
        """Backward compatibility: accept 'question' field and map to 'query'
        
        This validator ensures existing clients sending {"question": "..."} 
        continue to work while new clients can use {"query": "..."}.
        The 'question' field is consumed and replaced with 'query'.
        """
        if "query" not in values and "question" in values:
            values["query"] = values.pop("question")
        return values
    
    @validator('query')
    def validate_query(cls, v: str):
        """Validate and sanitize query using common validators"""
        v = sanitize_basic(v)
        assert_safe(v)
        return v

class IngestRequest(BaseRequest):
    """Document ingestion request for async processing"""
    path: str = Field(description="File path to ingest")
    source: SourceType = Field(default=SourceType.DOCUMENT, description="Document source")
    chunk_size: int = Field(default=1000, ge=100, le=5000, description="Chunk size")
    chunk_overlap: int = Field(default=200, ge=0, le=500, description="Chunk overlap")
    batch_size: int = Field(default=256, ge=32, le=1024, description="Batch size for processing")
    extract_metadata: bool = Field(default=True, description="Extract document metadata")

# Response Models
class SearchResponse(BaseResponse):
    """Search response model"""
    documents: List[Document] = Field(
        description="Search results"
    )
    total_results: int = Field(
        ge=0,
        description="Total number of results"
    )
    query_vector: Optional[List[float]] = Field(
        default=None,
        description="Query embedding vector"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "success",
                "documents": [],
                "total_results": 0
            }
        }
    )


class EmbeddingResponse(BaseResponse):
    """Embedding response model"""
    embeddings: List[Vector] = Field(
        description="Generated embeddings"
    )
    model_name: str = Field(
        description="Model used"
    )
    dimension: int = Field(
        ge=1,
        description="Embedding dimension"
    )
    total_tokens: Optional[int] = Field(
        default=None,
        description="Total tokens processed"
    )


class DocumentResponse(BaseResponse):
    """Document processing response"""
    document: Document = Field(
        description="Processed document"
    )
    chunks_created: int = Field(
        ge=0,
        description="Number of chunks created"
    )
    vectors_generated: int = Field(
        ge=0,
        description="Number of vectors generated"
    )
    processing_time_ms: float = Field(
        ge=0,
        description="Processing time in milliseconds"
    )


class ChatResponse(BaseResponse):
    """Chat/RAG response model"""
    answer: str = Field(
        description="Generated answer"
    )
    sources: List[Document] = Field(
        default_factory=list,
        description="Source documents"
    )
    model: str = Field(
        description="Model used"
    )
    tokens_used: Optional[int] = Field(
        default=None,
        description="Tokens consumed"
    )
    context_used: Optional[str] = Field(
        default=None,
        description="Context used for generation"
    )


class ErrorResponse(BaseResponse):
    """Error response model"""
    status: Literal[ResponseStatus.ERROR] = ResponseStatus.ERROR
    error_code: str = Field(
        description="Error code"
    )
    error_message: str = Field(
        description="Error message"
    )
    error_details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional error details"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "error",
                "error_code": "SEARCH_FAILED",
                "error_message": "Vector search failed",
                "error_details": {
                    "reason": "Qdrant connection timeout"
                }
            }
        }
    )


# System Status Models
class ComponentStatus(BaseModel):
    """Component status model"""
    name: str = Field(
        description="Component name"
    )
    status: StatusType = Field(
        description="Component status"
    )
    message: Optional[str] = Field(
        default=None,
        description="Status message"
    )
    metrics: Dict[str, Any] = Field(
        default_factory=dict,
        description="Component metrics"
    )
    last_check: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last health check time"
    )


class SystemStatus(BaseModel):
    """System status model"""
    overall_status: StatusType = Field(
        description="Overall system status"
    )
    components: List[ComponentStatus] = Field(
        description="Component statuses"
    )
    version: str = Field(
        default="1.0.0",
        description="System version"
    )
    uptime_seconds: float = Field(
        ge=0,
        description="System uptime"
    )
    
    @validator('overall_status', always=True)
    def calculate_overall_status(cls, v, values):
        """Calculate overall status from components"""
        if 'components' not in values:
            return v
            
        components = values['components']
        if not components:
            return StatusType.UNKNOWN
            
        unhealthy_count = sum(1 for c in components if c.status == StatusType.UNHEALTHY)
        degraded_count = sum(1 for c in components if c.status == StatusType.DEGRADED)
        
        if unhealthy_count > 0:
            return StatusType.UNHEALTHY
        elif degraded_count > 0:
            return StatusType.DEGRADED
        else:
            return StatusType.HEALTHY


class HealthCheck(BaseModel):
    """Health check response"""
    status: StatusType = Field(
        description="Health status"
    )
    checks: Dict[str, bool] = Field(
        description="Individual health checks"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Check timestamp"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "checks": {
                    "database": True,
                    "cache": True,
                    "embeddings": True
                },
                "timestamp": "2024-01-22T10:30:00Z"
            }
        }
    )


# Generic API Response Wrapper
class APIResponse(BaseModel):
    """Generic API response wrapper"""
    success: bool = Field(
        description="Request success status"
    )
    data: Optional[Any] = Field(
        default=None,
        description="Response data"
    )
    error: Optional[ErrorResponse] = Field(
        default=None,
        description="Error details if failed"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Response metadata"
    )
    
    @validator('error', always=True)
    def validate_error(cls, v, values):
        """Ensure error is set when success is False"""
        if 'success' in values and not values['success'] and v is None:
            raise ValueError("Error must be provided when success is False")
        return v
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "data": {"result": "example"},
                "error": None,
                "metadata": {
                    "version": "1.0.0",
                    "server": "hdllm-01"
                }
            }
        }
    )