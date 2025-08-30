"""
P1-1 Startup Validation Regression Test
Author: Claude Code
Date: 2025-01-26
Purpose: Ensure startup_vector_dim_check schema remains correct
"""

import pytest
from backend.resource_manager import ResourceManager, ResourceConfig

@pytest.mark.asyncio
async def test_startup_vector_dim_check_schema(monkeypatch):
    """Test that startup_vector_dim_check returns all required fields"""
    cfg = ResourceConfig()
    rm = ResourceManager(cfg)

    # Mock embed_texts to avoid real embedding model requirement
    async def fake_embed_texts(texts): 
        return [[0.0]*1024]
    rm.embed_texts = fake_embed_texts

    # Mock Qdrant client
    class DummyClient:
        def get_collection(self, name): 
            raise Exception("not found")
        def search(self, **kwargs): 
            return []

    class DummyClients:
        def get_qdrant_client(self, source): 
            return DummyClient()
    
    rm.clients = DummyClients()

    # Run validation
    result = await rm.startup_vector_dim_check(
        sources=["mail","doc"], 
        auto_create=False
    )

    # Assert required fields exist
    assert "overall_status" in result
    assert result["overall_status"] in ["success", "warning", "error"]
    
    assert "collection_status" in result
    assert all(s in result["collection_status"] for s in ["mail","doc"])
    
    assert "embedding_dimension" in result
    assert result["embedding_dimension"] > 0
    
    assert "validation_summary" in result
    assert "issues" in result
    assert "summary" in result
    
    # Check backward compatibility fields
    assert "expected_dimension" in result
    assert "collections_checked" in result
    assert "errors" in result
    assert "warnings" in result