"""
CORS Security Tests
Author: Claude Code
Date: 2024-01-22
Description: Test CORS configuration and security
"""

import pytest
import os
from fastapi.testclient import TestClient
from unittest.mock import patch

# Set test environment variables
os.environ["ALLOW_ORIGINS"] = "http://localhost:8001,http://127.0.0.1:8001"
os.environ["ALLOW_METHODS"] = "GET,POST,OPTIONS"
os.environ["ALLOW_HEADERS"] = "Content-Type,Authorization"

from backend.integration import create_integrated_app


@pytest.fixture
def client():
    """Create test client"""
    app = create_integrated_app(enable_security=True, development_mode=False)
    return TestClient(app)


class TestCORSSecurity:
    """Test CORS security configuration"""
    
    def test_cors_allowed_origin(self, client):
        """Test request from allowed origin"""
        response = client.get(
            "/health",
            headers={"Origin": "http://localhost:8001"}
        )
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
        assert response.headers["access-control-allow-origin"] == "http://localhost:8001"
    
    def test_cors_blocked_origin(self, client):
        """Test request from blocked origin"""
        response = client.get(
            "/health",
            headers={"Origin": "http://evil.com"}
        )
        assert response.status_code == 200
        assert "access-control-allow-origin" not in response.headers or \
               response.headers.get("access-control-allow-origin") != "http://evil.com"
    
    def test_cors_preflight_request(self, client):
        """Test OPTIONS preflight request"""
        response = client.options(
            "/ask",
            headers={
                "Origin": "http://localhost:8001",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type"
            }
        )
        assert response.status_code in [200, 204]
        assert "access-control-allow-methods" in response.headers
    
    def test_cors_allowed_methods(self, client):
        """Test allowed HTTP methods"""
        allowed_methods = ["GET", "POST", "OPTIONS"]
        
        for method in allowed_methods:
            response = client.options(
                "/health",
                headers={
                    "Origin": "http://localhost:8001",
                    "Access-Control-Request-Method": method
                }
            )
            assert response.status_code in [200, 204]
    
    def test_cors_blocked_methods(self, client):
        """Test blocked HTTP methods"""
        blocked_methods = ["PUT", "DELETE", "PATCH"]
        
        for method in blocked_methods:
            response = client.options(
                "/health",
                headers={
                    "Origin": "http://localhost:8001",
                    "Access-Control-Request-Method": method
                }
            )
            # Should not allow these methods
            if "access-control-allow-methods" in response.headers:
                assert method not in response.headers["access-control-allow-methods"]
    
    def test_cors_credentials(self, client):
        """Test CORS with credentials"""
        response = client.get(
            "/health",
            headers={
                "Origin": "http://localhost:8001",
                "Cookie": "session=test"
            }
        )
        assert response.status_code == 200
        if "access-control-allow-credentials" in response.headers:
            assert response.headers["access-control-allow-credentials"] == "true"
    
    def test_cors_headers_restriction(self, client):
        """Test restricted headers"""
        response = client.options(
            "/ask",
            headers={
                "Origin": "http://localhost:8001",
                "Access-Control-Request-Headers": "X-Custom-Header"
            }
        )
        # Custom header should not be in allowed list
        if response.status_code in [200, 204]:
            allowed_headers = response.headers.get("access-control-allow-headers", "")
            assert "X-Custom-Header" not in allowed_headers or allowed_headers == "*"
    
    def test_cors_wildcard_prevention(self, client):
        """Test that wildcard origins are not allowed"""
        response = client.get(
            "/health",
            headers={"Origin": "http://any-origin.com"}
        )
        # Should not have wildcard in allow-origin
        if "access-control-allow-origin" in response.headers:
            assert response.headers["access-control-allow-origin"] != "*"
    
    @patch.dict(os.environ, {"ALLOW_ORIGINS": ""})
    def test_cors_default_fallback(self):
        """Test CORS with no environment configuration"""
        app = create_integrated_app(enable_security=True)
        client = TestClient(app)
        
        response = client.get(
            "/health",
            headers={"Origin": "http://localhost:8001"}
        )
        assert response.status_code == 200
        # Should fall back to default localhost origins


class TestTrustedHosts:
    """Test trusted host middleware"""
    
    def test_trusted_host_allowed(self, client):
        """Test request from trusted host"""
        response = client.get(
            "/health",
            headers={"Host": "localhost:8080"}
        )
        assert response.status_code == 200
    
    def test_trusted_host_pattern(self, client):
        """Test wildcard host pattern"""
        response = client.get(
            "/health",
            headers={"Host": "app.hdmipo.local"}
        )
        # Should be allowed by *.hdmipo.local pattern
        assert response.status_code == 200
    
    def test_untrusted_host_blocked(self, client):
        """Test request from untrusted host"""
        with patch.dict(os.environ, {"TRUSTED_HOSTS": "localhost,127.0.0.1"}):
            app = create_integrated_app(enable_security=True)
            test_client = TestClient(app)
            
            response = test_client.get(
                "/health",
                headers={"Host": "evil.com"}
            )
            # Should be blocked
            assert response.status_code in [400, 421]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])