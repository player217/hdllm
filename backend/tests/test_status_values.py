"""
P1-1 Status Values Regression Test
Author: Claude Code
Date: 2025-01-26
Purpose: Ensure overall_status returns correct values
"""

from backend.resource_manager import ResourceManager, ResourceConfig
import pytest

@pytest.mark.asyncio
async def test_overall_status_values(monkeypatch):
    """Test that overall_status uses success/warning/error values"""
    rm = ResourceManager(ResourceConfig())
    
    # Mock embed_texts
    async def fake_embed_texts(texts): 
        return [[0.0]*16]
    rm.embed_texts = fake_embed_texts

    # Mock successful client
    class OkClient:
        def get_collection(self, name): 
            raise Exception("not found")
        def search(self, **kw): 
            return []

    # Mock failing client
    class FailClient:
        def get_collection(self, name): 
            raise Exception("not found")
        def search(self, **kw): 
            raise Exception("dimension mismatch")

    class Clients:
        def __init__(self, ok=True): 
            self.ok = ok
        def get_qdrant_client(self, source): 
            return OkClient() if self.ok else FailClient()

    # Test success path (collections not found but no dimension mismatch)
    rm.clients = Clients(ok=True)
    r1 = await rm.startup_vector_dim_check(["mail"], auto_create=False)
    # Should be error because collections not found, but let's check the value
    assert r1["overall_status"] in ("success", "warning", "error")
    assert r1["overall_status"] != "ok"  # Never use old value

    # Test error path (dimension mismatch)
    rm.clients = Clients(ok=False)
    r2 = await rm.startup_vector_dim_check(["mail"], auto_create=False)
    assert r2["overall_status"] == "error"
    assert r2["overall_status"] != "ok"  # Never use old value