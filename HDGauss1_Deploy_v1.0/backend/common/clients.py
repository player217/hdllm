"""
Common Client Wrappers with Standardized Interfaces
Author: Claude Code
Date: 2025-01-27
Description: Phase 2C - Unified client interfaces for external services
"""

import asyncio
import time
import logging
from typing import List, Dict, Any, Optional, Generator, AsyncGenerator
from abc import ABC, abstractmethod
import aiohttp
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .schemas import (
    Document, Vector, SearchRequest, SearchResponse,
    EmbeddingRequest, EmbeddingResponse, StatusType, ComponentStatus
)
from .utils import retry_with_backoff, Timer

logger = logging.getLogger(__name__)


class BaseClient(ABC):
    """
    Abstract base client with common functionality
    """
    
    def __init__(self, host: str, port: int, timeout: int = 30):
        """
        Initialize base client
        
        Args:
            host: Service host
            port: Service port
            timeout: Request timeout in seconds
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self.base_url = f"http://{host}:{port}"
        self._session = None
        self._connected = False
    
    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to service"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to service"""
        pass
    
    @abstractmethod
    async def health_check(self) -> ComponentStatus:
        """Check service health"""
        pass
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.disconnect()
    
    @property
    def is_connected(self) -> bool:
        """Check if client is connected"""
        return self._connected


class QdrantClientWrapper(BaseClient):
    """
    Wrapper for Qdrant client with standardized interface
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6333,
        grpc_port: int = 6334,
        timeout: int = 30,
        collection_name: str = "my_documents"
    ):
        """
        Initialize Qdrant client wrapper
        
        Args:
            host: Qdrant host
            port: HTTP port
            grpc_port: gRPC port
            timeout: Request timeout
            collection_name: Default collection
        """
        super().__init__(host, port, timeout)
        self.grpc_port = grpc_port
        self.collection_name = collection_name
        self.client = None
    
    async def connect(self) -> bool:
        """Connect to Qdrant"""
        try:
            self.client = QdrantClient(
                host=self.host,
                port=self.port,
                timeout=self.timeout,
                grpc_port=self.grpc_port,
                prefer_grpc=True
            )
            
            # Test connection
            collections = self.client.get_collections()
            self._connected = True
            logger.info(f"✅ Connected to Qdrant at {self.host}:{self.port}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to Qdrant: {e}")
            self._connected = False
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from Qdrant"""
        if self.client:
            self.client.close()
            self._connected = False
            logger.info("Disconnected from Qdrant")
    
    async def health_check(self) -> ComponentStatus:
        """Check Qdrant health"""
        try:
            with Timer() as timer:
                info = self.client.get_collection(self.collection_name)
            
            return ComponentStatus(
                name="qdrant",
                status=StatusType.HEALTHY,
                message=f"Collection '{self.collection_name}' available",
                metrics={
                    "vectors_count": info.vectors_count,
                    "indexed_vectors_count": info.indexed_vectors_count,
                    "response_time_ms": timer.elapsed_ms
                }
            )
            
        except Exception as e:
            return ComponentStatus(
                name="qdrant",
                status=StatusType.UNHEALTHY,
                message=str(e),
                metrics={}
            )
    
    @retry_with_backoff(max_retries=3)
    async def search(self, request: SearchRequest) -> SearchResponse:
        """
        Search vectors with retry logic
        
        Args:
            request: Search request
            
        Returns:
            Search response
        """
        if not self._connected:
            await self.connect()
        
        with Timer() as timer:
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=request.query if isinstance(request.query, list) else None,
                limit=request.limit,
                score_threshold=request.threshold,
                with_payload=True,
                with_vectors=request.include_vectors
            )
        
        # Convert to response model
        documents = []
        for result in results:
            doc = Document(
                id=str(result.id),
                source_type=result.payload.get("source_type", "doc"),
                content=result.payload.get("text", ""),
                score=result.score,
                metadata={
                    "file_name": result.payload.get("file_name"),
                    "file_path": result.payload.get("file_path"),
                    "author": result.payload.get("author")
                }
            )
            
            if request.include_vectors and result.vector:
                doc.vector = Vector(
                    vector=result.vector,
                    dimension=len(result.vector),
                    model_name="unknown"
                )
            
            documents.append(doc)
        
        return SearchResponse(
            request_id=request.request_id,
            documents=documents,
            total_results=len(documents),
            latency_ms=timer.elapsed_ms
        )
    
    async def upsert(
        self,
        vectors: List[List[float]],
        payloads: List[Dict[str, Any]],
        ids: Optional[List[str]] = None
    ) -> bool:
        """
        Upsert vectors to collection
        
        Args:
            vectors: Embedding vectors
            payloads: Vector payloads
            ids: Vector IDs
            
        Returns:
            Success status
        """
        if not self._connected:
            await self.connect()
        
        if ids is None:
            ids = [str(i) for i in range(len(vectors))]
        
        points = [
            PointStruct(id=id_, vector=vector, payload=payload)
            for id_, vector, payload in zip(ids, vectors, payloads)
        ]
        
        operation_info = self.client.upsert(
            collection_name=self.collection_name,
            points=points,
            wait=True
        )
        
        return operation_info.status == "completed"
    
    def get_collection_info(self) -> Dict[str, Any]:
        """Get collection information"""
        if not self._connected:
            return {}
        
        info = self.client.get_collection(self.collection_name)
        return {
            "vectors_count": info.vectors_count,
            "indexed_vectors_count": info.indexed_vectors_count,
            "points_count": info.points_count,
            "segments_count": info.segments_count,
            "status": info.status
        }


class OllamaClientWrapper(BaseClient):
    """
    Wrapper for Ollama LLM client with standardized interface
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 11434,
        timeout: int = 60,
        model: str = "gemma3:4b"
    ):
        """
        Initialize Ollama client wrapper
        
        Args:
            host: Ollama host
            port: Ollama port
            timeout: Request timeout
            model: Default model
        """
        super().__init__(host, port, timeout)
        self.model = model
    
    async def connect(self) -> bool:
        """Connect to Ollama"""
        try:
            if not self._session:
                self._session = aiohttp.ClientSession()
            
            # Test connection
            async with self._session.get(
                f"{self.base_url}/api/tags",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                if response.status == 200:
                    self._connected = True
                    logger.info(f"✅ Connected to Ollama at {self.host}:{self.port}")
                    return True
                    
        except Exception as e:
            logger.error(f"❌ Failed to connect to Ollama: {e}")
            self._connected = False
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from Ollama"""
        if self._session:
            await self._session.close()
            self._session = None
            self._connected = False
            logger.info("Disconnected from Ollama")
    
    async def health_check(self) -> ComponentStatus:
        """Check Ollama health"""
        try:
            with Timer() as timer:
                async with self._session.get(
                    f"{self.base_url}/api/tags",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    data = await response.json()
                    models = [m["name"] for m in data.get("models", [])]
            
            return ComponentStatus(
                name="ollama",
                status=StatusType.HEALTHY if self.model in models else StatusType.DEGRADED,
                message=f"Model '{self.model}' {'available' if self.model in models else 'not found'}",
                metrics={
                    "available_models": models,
                    "response_time_ms": timer.elapsed_ms
                }
            )
            
        except Exception as e:
            return ComponentStatus(
                name="ollama",
                status=StatusType.UNHEALTHY,
                message=str(e),
                metrics={}
            )
    
    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        stream: bool = False
    ) -> AsyncGenerator[str, None]:
        """
        Generate text with Ollama
        
        Args:
            prompt: Input prompt
            temperature: Generation temperature
            max_tokens: Maximum tokens
            stream: Stream response
            
        Yields:
            Generated text chunks
        """
        if not self._connected:
            await self.connect()
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream
        }
        
        async with self._session.post(
            f"{self.base_url}/api/generate",
            json=payload,
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        ) as response:
            if stream:
                async for line in response.content:
                    if line:
                        try:
                            import json
                            data = json.loads(line)
                            if "response" in data:
                                yield data["response"]
                        except:
                            continue
            else:
                data = await response.json()
                yield data.get("response", "")
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        stream: bool = False
    ) -> AsyncGenerator[str, None]:
        """
        Chat with Ollama
        
        Args:
            messages: Chat messages
            temperature: Generation temperature
            stream: Stream response
            
        Yields:
            Response chunks
        """
        if not self._connected:
            await self.connect()
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream
        }
        
        async with self._session.post(
            f"{self.base_url}/api/chat",
            json=payload,
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        ) as response:
            if stream:
                async for line in response.content:
                    if line:
                        try:
                            import json
                            data = json.loads(line)
                            if "message" in data:
                                yield data["message"].get("content", "")
                        except:
                            continue
            else:
                data = await response.json()
                if "message" in data:
                    yield data["message"].get("content", "")
    
    async def list_models(self) -> List[str]:
        """List available models"""
        if not self._connected:
            await self.connect()
        
        async with self._session.get(
            f"{self.base_url}/api/tags"
        ) as response:
            data = await response.json()
            return [m["name"] for m in data.get("models", [])]


class TikaClientWrapper(BaseClient):
    """
    Wrapper for Apache Tika client
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 9998,
        timeout: int = 30
    ):
        """
        Initialize Tika client wrapper
        
        Args:
            host: Tika host
            port: Tika port
            timeout: Request timeout
        """
        super().__init__(host, port, timeout)
    
    async def connect(self) -> bool:
        """Connect to Tika"""
        try:
            if not self._session:
                self._session = aiohttp.ClientSession()
            
            # Test connection
            async with self._session.get(
                f"{self.base_url}/tika",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                if response.status == 200:
                    self._connected = True
                    logger.info(f"✅ Connected to Tika at {self.host}:{self.port}")
                    return True
                    
        except Exception as e:
            logger.error(f"❌ Failed to connect to Tika: {e}")
            self._connected = False
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from Tika"""
        if self._session:
            await self._session.close()
            self._session = None
            self._connected = False
            logger.info("Disconnected from Tika")
    
    async def health_check(self) -> ComponentStatus:
        """Check Tika health"""
        try:
            with Timer() as timer:
                async with self._session.get(
                    f"{self.base_url}/tika",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    status_code = response.status
            
            return ComponentStatus(
                name="tika",
                status=StatusType.HEALTHY if status_code == 200 else StatusType.UNHEALTHY,
                message=f"HTTP {status_code}",
                metrics={
                    "response_time_ms": timer.elapsed_ms
                }
            )
            
        except Exception as e:
            return ComponentStatus(
                name="tika",
                status=StatusType.UNHEALTHY,
                message=str(e),
                metrics={}
            )
    
    async def extract_text(self, file_path: str) -> str:
        """
        Extract text from file
        
        Args:
            file_path: Path to file
            
        Returns:
            Extracted text
        """
        if not self._connected:
            await self.connect()
        
        with open(file_path, 'rb') as f:
            file_content = f.read()
        
        headers = {
            'Accept': 'text/plain',
            'Content-Type': 'application/octet-stream'
        }
        
        async with self._session.put(
            f"{self.base_url}/tika",
            data=file_content,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        ) as response:
            if response.status == 200:
                return await response.text()
            else:
                raise Exception(f"Tika extraction failed with status {response.status}")
    
    async def extract_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Extract metadata from file
        
        Args:
            file_path: Path to file
            
        Returns:
            File metadata
        """
        if not self._connected:
            await self.connect()
        
        with open(file_path, 'rb') as f:
            file_content = f.read()
        
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/octet-stream'
        }
        
        async with self._session.put(
            f"{self.base_url}/meta",
            data=file_content,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        ) as response:
            if response.status == 200:
                return await response.json()
            else:
                raise Exception(f"Tika metadata extraction failed with status {response.status}")
    
    async def detect_language(self, text: str) -> str:
        """
        Detect text language
        
        Args:
            text: Input text
            
        Returns:
            Language code
        """
        if not self._connected:
            await self.connect()
        
        async with self._session.put(
            f"{self.base_url}/language",
            data=text.encode('utf-8'),
            headers={'Content-Type': 'text/plain'},
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        ) as response:
            if response.status == 200:
                return await response.text()
            else:
                raise Exception(f"Language detection failed with status {response.status}")


# Example usage
async def test_clients():
    """Test client wrappers"""
    
    # Test Qdrant client
    async with QdrantClientWrapper() as qdrant:
        health = await qdrant.health_check()
        print(f"Qdrant health: {health.status}")
        
        # Test search
        request = SearchRequest(
            query="test query",
            source="doc",
            limit=5
        )
        # response = await qdrant.search(request)
        # print(f"Search results: {len(response.documents)}")
    
    # Test Ollama client
    async with OllamaClientWrapper() as ollama:
        health = await ollama.health_check()
        print(f"Ollama health: {health.status}")
        
        # Test generation
        async for chunk in ollama.generate("Hello, how are you?", stream=True):
            print(chunk, end="")
        print()
    
    # Test Tika client
    async with TikaClientWrapper() as tika:
        health = await tika.health_check()
        print(f"Tika health: {health.status}")


if __name__ == "__main__":
    asyncio.run(test_clients())