"""
PII Masking Test Suite
Author: Claude Code
Date: 2025-01-28
Description: Tests for P1-3 PII masking in logging system
"""
import pytest
import logging
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from backend.common.logging import PiiRedactor, JsonFormatter, setup_logging, get_query_hash


class TestPiiMasking:
    """Test suite for PII masking functionality"""
    
    def test_korean_ssn_masking(self):
        """주민등록번호 마스킹 테스트"""
        redactor = PiiRedactor()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="사용자 주민번호: 901234-1234567", args=(), exc_info=None
        )
        redactor.filter(record)
        assert "******-*******" in record.msg
        assert "901234-1234567" not in record.msg
        assert record.request_id == "-"  # Default value
    
    def test_phone_masking(self):
        """휴대폰번호 마스킹 테스트"""
        redactor = PiiRedactor()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="연락처: 010-1234-5678, 일반전화: 02-1234-5678", args=(), exc_info=None
        )
        redactor.filter(record)
        assert "010-****-****" in record.msg
        assert "0**-****-****" in record.msg
        assert "010-1234-5678" not in record.msg
        assert "02-1234-5678" not in record.msg
    
    def test_email_masking(self):
        """이메일 마스킹 테스트"""
        redactor = PiiRedactor()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="이메일 주소: user@hdmipoship.com, test@example.org", args=(), exc_info=None
        )
        redactor.filter(record)
        assert "***@***.***" in record.msg
        assert "user@hdmipoship.com" not in record.msg
        assert "test@example.org" not in record.msg
    
    def test_employee_id_masking(self):
        """사번 마스킹 테스트"""
        redactor = PiiRedactor()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="사번: HD12345678 문서번호: DOC-2024-123456", args=(), exc_info=None
        )
        redactor.filter(record)
        assert "HD******" in record.msg
        assert "DOC-****-******" in record.msg
        assert "HD12345678" not in record.msg
        assert "DOC-2024-123456" not in record.msg
    
    def test_financial_info_masking(self):
        """금융정보 마스킹 테스트"""
        redactor = PiiRedactor()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="카드: 1234-5678-9012-3456, 계좌: 123-45-67890", args=(), exc_info=None
        )
        redactor.filter(record)
        assert "****-****-****-****" in record.msg
        assert "***-****-****" in record.msg
        assert "1234-5678-9012-3456" not in record.msg
        assert "123-45-67890" not in record.msg
    
    def test_ip_address_masking(self):
        """IP 주소 마스킹 테스트"""
        redactor = PiiRedactor()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="접속 IP: 192.168.0.1, 외부 IP: 123.456.789.012", args=(), exc_info=None
        )
        redactor.filter(record)
        assert "***.***.***.***" in record.msg
        assert "192.168.0.1" not in record.msg
        assert "123.456.789.012" not in record.msg
    
    def test_business_number_masking(self):
        """사업자번호 마스킹 테스트"""
        redactor = PiiRedactor()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="사업자번호: 123-45-67890", args=(), exc_info=None
        )
        redactor.filter(record)
        assert "***-**-*****" in record.msg
        assert "123-45-67890" not in record.msg
    
    def test_multiple_pii_masking(self):
        """복합 PII 마스킹 테스트"""
        redactor = PiiRedactor()
        msg = """
        사용자 정보:
        - 이름: 홍길동
        - 주민번호: 901234-1234567
        - 전화: 010-1234-5678
        - 이메일: hong@example.com
        - 사번: HD12345678
        - IP: 192.168.0.100
        """
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg=msg, args=(), exc_info=None
        )
        redactor.filter(record)
        
        # Check all PII is masked
        assert "******-*******" in record.msg
        assert "010-****-****" in record.msg
        assert "***@***.***" in record.msg
        assert "HD******" in record.msg
        assert "***.***.***.***" in record.msg
        
        # Check original values are gone
        assert "901234-1234567" not in record.msg
        assert "010-1234-5678" not in record.msg
        assert "hong@example.com" not in record.msg
        assert "HD12345678" not in record.msg
        assert "192.168.0.100" not in record.msg
    
    def test_disabled_redactor(self):
        """비활성화된 PII 마스킹 테스트"""
        redactor = PiiRedactor(enabled=False)
        original_msg = "주민번호: 901234-1234567"
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg=original_msg, args=(), exc_info=None
        )
        redactor.filter(record)
        assert record.msg == original_msg  # No masking when disabled
    
    def test_args_masking(self):
        """포맷 인자 마스킹 테스트"""
        redactor = PiiRedactor()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="User %s has email %s", 
            args=("HD12345678", "user@example.com"), 
            exc_info=None
        )
        redactor.filter(record)
        assert record.args[0] == "HD******"
        assert record.args[1] == "***@***.***"
    
    def test_query_hash(self):
        """쿼리 해시 테스트"""
        query = "선각기술부 회의록"
        hash1 = get_query_hash(query)
        hash2 = get_query_hash(query)
        hash3 = get_query_hash("다른 쿼리")
        
        assert hash1 == hash2  # Same query produces same hash
        assert hash1 != hash3  # Different queries produce different hashes
        assert len(hash1) == 16  # Hash is 16 characters
        assert query not in hash1  # Original query not in hash


class TestJsonFormatter:
    """Test JSON log formatting"""
    
    def test_json_format_basic(self):
        """기본 JSON 포맷 테스트"""
        import json
        
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test.module", level=logging.INFO, 
            pathname="test.py", lineno=10,
            msg="Test message", args=(), exc_info=None,
            func="test_function"
        )
        record.request_id = "test-123"
        record.source = "mail"
        record.namespace = "test_namespace"
        
        output = formatter.format(record)
        data = json.loads(output)
        
        assert data["level"] == "INFO"
        assert data["logger"] == "test.module"
        assert data["message"] == "Test message"
        assert data["request_id"] == "test-123"
        assert data["source"] == "mail"
        assert data["namespace"] == "test_namespace"
        assert "timestamp" in data
        assert "location" in data
        assert data["location"]["file"] == "test.py"
        assert data["location"]["line"] == 10
        assert data["location"]["function"] == "test_function"
    
    def test_json_format_with_exception(self):
        """예외 정보 포함 JSON 포맷 테스트"""
        import json
        
        formatter = JsonFormatter()
        try:
            raise ValueError("Test error")
        except ValueError:
            import sys
            record = logging.LogRecord(
                name="test", level=logging.ERROR, 
                pathname="test.py", lineno=10,
                msg="Error occurred", args=(), 
                exc_info=sys.exc_info(),
                func="test_function"
            )
            record.request_id = "-"
            
            output = formatter.format(record)
            data = json.loads(output)
            
            assert data["level"] == "ERROR"
            assert "exception" in data
            assert "ValueError: Test error" in data["exception"]


class TestLoggingSetup:
    """Test logging setup function"""
    
    def test_setup_logging_json(self):
        """JSON 로깅 설정 테스트"""
        audit_logger = setup_logging(
            level="INFO",
            format_type="json",
            redact_pii=True,
            audit_enabled=True
        )
        
        assert audit_logger is not None
        assert audit_logger.enabled is True
        
        # Test that logger is configured
        logger = logging.getLogger("test")
        assert logger.level <= logging.INFO
    
    def test_setup_logging_text(self):
        """텍스트 로깅 설정 테스트"""
        audit_logger = setup_logging(
            level="DEBUG",
            format_type="text",
            redact_pii=False,
            audit_enabled=False
        )
        
        assert audit_logger is not None
        assert audit_logger.enabled is False
        
        logger = logging.getLogger("test")
        assert logger.level <= logging.DEBUG


if __name__ == "__main__":
    pytest.main([__file__, "-v"])