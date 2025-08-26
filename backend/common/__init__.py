"""
Common Utilities and Schemas for HD현대미포 Gauss-1 RAG System
"""

from .schemas import (
    # Request models
    SearchRequest,
    EmbeddingRequest,
    DocumentRequest,
    
    # Response models
    APIResponse,
    SearchResponse,
    EmbeddingResponse,
    DocumentResponse,
    ErrorResponse,
    
    # Data models
    Document,
    Chunk,
    Vector,
    Metadata,
    
    # Status models
    SystemStatus,
    ComponentStatus,
    HealthCheck
)

from .clients import (
    BaseClient,
    QdrantClientWrapper,
    OllamaClientWrapper,
    TikaClientWrapper
)

from .utils import (
    generate_request_id,
    calculate_hash,
    normalize_text,
    validate_vector,
    Timer,
    retry_with_backoff
)

__all__ = [
    # Schemas
    'SearchRequest',
    'EmbeddingRequest',
    'DocumentRequest',
    'APIResponse',
    'SearchResponse',
    'EmbeddingResponse',
    'DocumentResponse',
    'ErrorResponse',
    'Document',
    'Chunk',
    'Vector',
    'Metadata',
    'SystemStatus',
    'ComponentStatus',
    'HealthCheck',
    
    # Clients
    'BaseClient',
    'QdrantClientWrapper',
    'OllamaClientWrapper',
    'TikaClientWrapper',
    
    # Utils
    'generate_request_id',
    'calculate_hash',
    'normalize_text',
    'validate_vector',
    'Timer',
    'retry_with_backoff'
]