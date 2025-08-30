"""
Request ID Propagation Test Suite
Author: Claude Code
Date: 2025-01-28
Description: Tests for P1-3 request ID correlation in logging system
"""
import pytest
import json
import sys
import os
from unittest.mock import patch
import asyncio

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fastapi.testclient import TestClient


class TestRequestId:
    """Test suite for request ID propagation"""
    
    @pytest.fixture
    def client(self):
        """Create test client with fresh app instance"""
        # Import here to ensure fresh app state
        from backend.main import app
        return TestClient(app)
    
    def test_request_id_generation(self, client):
        """Request ID 자동 생성 테스트"""
        response = client.get("/health")
        
        assert response.status_code == 200
        assert "x-request-id" in response.headers
        
        # UUID v4 format check
        request_id = response.headers["x-request-id"]
        assert len(request_id) == 36  # Standard UUID length
        assert request_id.count('-') == 4  # UUID has 4 dashes
    
    def test_request_id_propagation(self, client):
        """Request ID 전파 테스트"""
        custom_id = "test-request-12345"
        
        response = client.get(
            "/health",
            headers={"x-request-id": custom_id}
        )
        
        assert response.status_code == 200
        assert response.headers["x-request-id"] == custom_id
    
    def test_request_id_in_status_endpoint(self, client):
        """Status 엔드포인트에서 Request ID 테스트"""
        custom_id = "status-check-999"
        
        response = client.get(
            "/status",
            headers={"x-request-id": custom_id}
        )
        
        assert response.status_code == 200
        assert response.headers["x-request-id"] == custom_id
        
        # Check response source header
        assert "x-response-source" in response.headers
    
    def test_source_extraction_from_query(self, client):
        """Query 파라미터에서 소스 추출 테스트"""
        response = client.get(
            "/status?source=mail",
            headers={"x-request-id": "test-123"}
        )
        
        assert response.status_code == 200
        assert response.headers["x-response-source"] == "mail"
        
        response = client.get(
            "/status?source=doc",
            headers={"x-request-id": "test-456"}
        )
        
        assert response.status_code == 200
        assert response.headers["x-response-source"] == "doc"
    
    def test_multiple_request_ids_isolated(self, client):
        """여러 요청의 Request ID 격리 테스트"""
        ids = []
        for i in range(5):
            response = client.get("/health")
            request_id = response.headers["x-request-id"]
            ids.append(request_id)
        
        # All IDs should be unique
        assert len(ids) == len(set(ids))
    
    def test_request_id_with_error(self, client):
        """에러 발생 시 Request ID 유지 테스트"""
        custom_id = "error-test-789"
        
        # Request non-existent endpoint
        response = client.get(
            "/non-existent-endpoint",
            headers={"x-request-id": custom_id}
        )
        
        assert response.status_code == 404
        assert response.headers["x-request-id"] == custom_id
    
    @pytest.mark.asyncio
    async def test_request_id_in_async_context(self):
        """비동기 컨텍스트에서 Request ID 테스트"""
        from backend.common.logging import (
            request_id_ctx, set_request_context, clear_request_context
        )
        
        # Set context
        test_id = "async-test-123"
        set_request_context(test_id, "mail", "test_namespace")
        
        # Check context is set
        assert request_id_ctx.get() == test_id
        
        # Simulate async operation
        await asyncio.sleep(0.01)
        
        # Context should persist
        assert request_id_ctx.get() == test_id
        
        # Clear context
        clear_request_context()
        assert request_id_ctx.get() == "-"
    
    def test_request_id_format_in_logs(self):
        """로그 포맷에 Request ID 포함 테스트"""
        import logging
        import io
        from backend.common.logging import setup_logging, request_id_ctx
        
        # Setup logging with JSON format
        setup_logging(format_type="json", redact_pii=True)
        
        # Set request context
        from backend.common.logging import set_request_context
        set_request_context("log-test-456", "mail", "test_namespace")
        
        # Capture log output
        log_capture = io.StringIO()
        handler = logging.StreamHandler(log_capture)
        
        # Add JSON formatter
        from backend.common.logging import JsonFormatter, PiiRedactor
        handler.setFormatter(JsonFormatter())
        handler.addFilter(PiiRedactor())
        
        logger = logging.getLogger("test_logger")
        logger.handlers = [handler]
        logger.setLevel(logging.INFO)
        
        # Log a message
        logger.info("Test message with request ID")
        
        # Parse JSON log
        log_output = log_capture.getvalue()
        log_data = json.loads(log_output.strip())
        
        assert log_data["request_id"] == "log-test-456"
        assert log_data["source"] == "mail"
        assert log_data["namespace"] == "test_namespace"
        assert log_data["message"] == "Test message with request ID"
    
    def test_request_id_with_pii_masking(self):
        """Request ID와 PII 마스킹 동시 테스트"""
        import logging
        import io
        from backend.common.logging import setup_logging, set_request_context
        
        # Setup logging
        setup_logging(format_type="json", redact_pii=True)
        
        # Set request context
        set_request_context("pii-test-789", "doc", "secure_namespace")
        
        # Capture log output
        log_capture = io.StringIO()
        handler = logging.StreamHandler(log_capture)
        
        from backend.common.logging import JsonFormatter, PiiRedactor
        handler.setFormatter(JsonFormatter())
        handler.addFilter(PiiRedactor())
        
        logger = logging.getLogger("pii_test")
        logger.handlers = [handler]
        logger.setLevel(logging.INFO)
        
        # Log message with PII
        logger.info("User email: test@example.com, phone: 010-1234-5678")
        
        # Parse JSON log
        log_output = log_capture.getvalue()
        log_data = json.loads(log_output.strip())
        
        # Check request ID is present
        assert log_data["request_id"] == "pii-test-789"
        
        # Check PII is masked
        assert "***@***.***" in log_data["message"]
        assert "010-****-****" in log_data["message"]
        assert "test@example.com" not in log_data["message"]
        assert "010-1234-5678" not in log_data["message"]


class TestAuditLogging:
    """Test audit logging functionality"""
    
    def test_audit_search_log(self):
        """검색 감사 로그 테스트"""
        from backend.common.logging import setup_logging, get_query_hash
        
        audit_logger = setup_logging(
            format_type="json",
            audit_enabled=True
        )
        
        # Log a search event
        query = "선각기술부 회의록"
        query_hash = get_query_hash(query)
        
        audit_logger.log_search(
            source="mail",
            namespace="test_namespace",
            query_hash=query_hash,
            limit=10,
            threshold=0.3,
            result_count=5,
            latency_ms=123.45
        )
        
        # Verify query is not in hash
        assert query not in query_hash
        assert len(query_hash) == 16
    
    def test_audit_access_log(self):
        """접근 감사 로그 테스트"""
        from backend.common.logging import setup_logging
        
        audit_logger = setup_logging(
            format_type="json",
            audit_enabled=True
        )
        
        # Log an access event
        audit_logger.log_access(
            resource="/api/ask",
            action="POST",
            result="success",
            user_id="user123"
        )
        
        # Log should be created without error
        assert audit_logger.enabled is True
    
    def test_audit_auth_log(self):
        """인증 감사 로그 테스트"""
        from backend.common.logging import setup_logging
        
        audit_logger = setup_logging(
            format_type="json",
            audit_enabled=True
        )
        
        # Log auth events
        audit_logger.log_auth(
            event="login",
            user_id="user456",
            ip_address="192.168.0.1",
            reason="successful authentication"
        )
        
        audit_logger.log_auth(
            event="failed_auth",
            user_id="unknown",
            ip_address="10.0.0.1",
            reason="invalid credentials"
        )
        
        assert audit_logger.enabled is True
    
    def test_audit_disabled(self):
        """감사 로그 비활성화 테스트"""
        from backend.common.logging import setup_logging
        
        audit_logger = setup_logging(
            format_type="json",
            audit_enabled=False
        )
        
        assert audit_logger.enabled is False
        
        # These should not raise errors even when disabled
        audit_logger.log_search(
            source="mail",
            namespace="test",
            query_hash="test123",
            limit=10,
            threshold=0.3,
            result_count=0,
            latency_ms=0
        )
        
        audit_logger.log_access(
            resource="/test",
            action="GET",
            result="success"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])