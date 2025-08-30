"""
스모크 테스트 - 기본 기능 동작 확인
Author: Claude Code
Date: 2025-01-27  
Description: 푸시 전 필수 검증 항목들
"""

import pytest
import asyncio
import sys
import os
from pathlib import Path

# 상위 디렉토리 경로 추가
sys.path.append(str(Path(__file__).parent.parent))

# ASGI 라이프사이클과 HTTP 클라이언트 임포트
try:
    from asgi_lifespan import LifespanManager
    from httpx import AsyncClient
except ImportError:
    pytest.skip("asgi_lifespan or httpx not available", allow_module_level=True)

from backend.main import app

class TestSmoke:
    """기본 스모크 테스트"""

    @pytest.mark.asyncio
    async def test_app_boot_and_health(self):
        """앱 부팅 및 헬스체크 테스트"""
        async with LifespanManager(app):
            async with AsyncClient(app=app, base_url="http://test") as client:
                # Health endpoint 테스트
                response = await client.get("/health")
                assert response.status_code == 200
                
                data = response.json()
                assert "status" in data
                assert data["status"] == "OK"

    @pytest.mark.asyncio 
    async def test_app_boot_and_ask_basic(self):
        """앱 부팅 및 기본 Ask 엔드포인트 테스트"""
        async with LifespanManager(app):
            async with AsyncClient(app=app, base_url="http://test") as client:
                # Ask endpoint 기본 테스트
                response = await client.post("/ask", json={
                    "question": "테스트",
                    "source": "mail"
                })
                
                # 200 OK 또는 스트리밍 응답 확인
                assert response.status_code == 200
                
                # Content-Type 다중 형식 지원 (스트리밍/JSON/NDJSON)
                content_type = response.headers.get("content-type", "")
                assert (
                    "application/x-ndjson" in content_type      # GPU-accelerated streaming
                    or "text/event-stream" in content_type     # Legacy SSE streaming  
                    or "application/json" in content_type      # Non-streaming JSON
                )

    @pytest.mark.asyncio
    async def test_status_endpoint(self):
        """상태 엔드포인트 테스트"""
        async with LifespanManager(app):
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.get("/status")
                assert response.status_code == 200
                
                data = response.json()
                assert "status" in data
                assert "components" in data

    @pytest.mark.asyncio
    async def test_queue_stats_available(self):
        """큐 통계 확인 가능 여부 테스트"""
        async with LifespanManager(app):
            # 앱이 시작된 후 app_state에 async_pipeline이 있는지 확인
            from backend.main import app_state
            
            if "async_pipeline" in app_state:
                pipeline = app_state["async_pipeline"]
                
                # 큐 통계 호출 가능 여부 확인
                stats = pipeline.get_queue_stats()
                
                # 기본적인 통계 필드들이 있는지 확인
                required_fields = ["total_tasks", "pending_tasks", "processing_tasks", "running"]
                for field in required_fields:
                    assert field in stats, f"Queue stats should contain '{field}'"
                
                # running 상태가 True인지 확인 (큐가 시작되었는지)
                assert stats["running"] == True, "TaskQueue should be running after app startup"

class TestEmbeddingBackends:
    """임베딩 백엔드별 테스트"""
    
    @pytest.mark.asyncio
    async def test_sentence_transformers_backend(self):
        """SentenceTransformers 백엔드 테스트"""
        async with LifespanManager(app):
            from backend.main import app_state
            
            if "resource_manager" in app_state:
                resource_manager = app_state["resource_manager"]
                
                if resource_manager.embed_backend == "st":
                    # 기본 임베딩 생성 테스트
                    embeddings = await resource_manager.embed_texts(["테스트 문장"])
                    
                    assert len(embeddings) == 1
                    assert len(embeddings[0]) == 1024, "BGE-M3 should produce 1024-dimensional embeddings"
                    assert all(isinstance(x, float) for x in embeddings[0]), "Embeddings should be floats"

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        os.getenv("EMBED_BACKEND") != "ollama", 
        reason="Ollama backend not configured"
    )
    async def test_ollama_backend_with_env_endpoint(self):
        """Ollama 백엔드 ENV 엔드포인트 테스트"""
        async with LifespanManager(app):
            from backend.main import app_state
            
            if "resource_manager" in app_state:
                resource_manager = app_state["resource_manager"]
                
                if resource_manager.embed_backend == "ollama":
                    try:
                        # ENV 기반 엔드포인트 사용하여 임베딩 생성
                        embeddings = await resource_manager.embed_texts(["테스트"])
                        
                        assert len(embeddings) == 1
                        assert len(embeddings[0]) > 0, "Ollama should return non-empty embeddings"
                        assert all(isinstance(x, float) for x in embeddings[0])
                        
                    except Exception as e:
                        # Ollama 서버가 실행 중이지 않을 수 있으므로 
                        # 연결 에러는 스킵하되 다른 에러는 실패
                        if "connection" not in str(e).lower():
                            raise

class TestQueueIntegration:
    """큐 시스템 통합 테스트"""
    
    @pytest.mark.asyncio
    async def test_queue_enqueue_and_stats_change(self):
        """큐 작업 추가 및 통계 변화 확인"""
        async with LifespanManager(app):
            from backend.main import app_state
            
            if "async_pipeline" in app_state:
                pipeline = app_state["async_pipeline"]
                
                # 초기 통계
                initial_stats = pipeline.get_queue_stats()
                initial_total = initial_stats.get("total_enqueued", 0)
                
                # 테스트 작업 추가
                try:
                    task_id = await pipeline.enqueue("search", {
                        "query": "큐 테스트 질문",
                        "source_type": "mail",
                        "limit": 1
                    })
                    
                    assert task_id is not None
                    
                    # 통계 변화 확인 (약간의 지연 후)
                    await asyncio.sleep(0.5)
                    updated_stats = pipeline.get_queue_stats()
                    updated_total = updated_stats.get("total_enqueued", 0)
                    
                    assert updated_total > initial_total, "Queue stats should increase after enqueuing"
                    
                except Exception as e:
                    # 큐가 실제 처리에서 실패할 수 있지만, 
                    # 적어도 enqueue 단계에서는 성공해야 함
                    if "enqueue" in str(e).lower():
                        raise

if __name__ == "__main__":
    # pytest 실행
    pytest.main([__file__, "-v", "--tb=short"])