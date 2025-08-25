"""
Security Module Tests for HD현대미포 Gauss-1 RAG System
Author: Claude Code
Date: 2024-01-22
"""

import unittest
import sys
import os
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from security_config import (
    QuestionRequest,
    EnhancedPIIMasker,
    sanitize_file_path,
    validate_json_input,
    create_access_token,
    verify_password,
    get_password_hash
)


class TestInputValidation(unittest.TestCase):
    """Test input validation and sanitization"""
    
    def test_valid_question_request(self):
        """Test valid question request"""
        req = QuestionRequest(
            question="선각기술부는 무엇인가요?",
            source="mail",
            model="gemma3:4b"
        )
        self.assertEqual(req.question, "선각기술부는 무엇인가요?")
    
    def test_sql_injection_prevention(self):
        """Test SQL injection prevention"""
        with self.assertRaises(ValueError):
            QuestionRequest(
                question="test'; DROP TABLE users; --",
                source="mail"
            )
    
    def test_question_length_validation(self):
        """Test question length limits"""
        # Too short
        with self.assertRaises(ValueError):
            QuestionRequest(question="", source="mail")
        
        # Too long
        with self.assertRaises(ValueError):
            QuestionRequest(question="x" * 2001, source="mail")
    
    def test_source_validation(self):
        """Test source field validation"""
        # Valid sources
        req1 = QuestionRequest(question="test", source="mail")
        req2 = QuestionRequest(question="test", source="doc")
        
        # Invalid source
        with self.assertRaises(ValueError):
            QuestionRequest(question="test", source="invalid")


class TestPIIMasking(unittest.TestCase):
    """Test PII detection and masking"""
    
    def setUp(self):
        self.masker = EnhancedPIIMasker()
    
    def test_korean_ssn_masking(self):
        """Test Korean SSN masking"""
        text = "내 주민번호는 990101-1234567 입니다"
        masked = self.masker.mask(text)
        self.assertIn("[KOREAN_SSN_", masked)
        self.assertNotIn("990101-1234567", masked)
    
    def test_phone_number_masking(self):
        """Test phone number masking"""
        text = "연락처: 010-1234-5678"
        masked = self.masker.mask(text)
        self.assertIn("[KOREAN_PHONE_", masked)
        self.assertNotIn("010-1234-5678", masked)
    
    def test_email_masking(self):
        """Test email masking"""
        text = "이메일: test@hdmipoeng.com"
        masked = self.masker.mask(text)
        self.assertIn("[EMAIL_", masked)
        self.assertNotIn("test@hdmipoeng.com", masked)
    
    def test_multiple_pii_masking(self):
        """Test masking multiple PII types"""
        text = "홍길동 010-1234-5678 test@email.com 990101-1234567"
        masked = self.masker.mask(text)
        
        # Check all PII is masked
        self.assertNotIn("010-1234-5678", masked)
        self.assertNotIn("test@email.com", masked)
        self.assertNotIn("990101-1234567", masked)
    
    def test_pii_detection(self):
        """Test PII detection"""
        text = "연락처: 010-1234-5678, 이메일: test@hdmipoeng.com"
        detected = self.masker.detect_pii(text)
        
        self.assertIn("korean_phone", detected)
        self.assertIn("email", detected)
        self.assertEqual(detected["korean_phone"], ["010-1234-5678"])
        self.assertEqual(detected["email"], ["test@hdmipoeng.com"])


class TestAuthentication(unittest.TestCase):
    """Test authentication functions"""
    
    def test_password_hashing(self):
        """Test password hashing and verification"""
        password = "test_password_123"
        hashed = get_password_hash(password)
        
        # Hash should be different from original
        self.assertNotEqual(password, hashed)
        
        # Verification should work
        self.assertTrue(verify_password(password, hashed))
        self.assertFalse(verify_password("wrong_password", hashed))
    
    def test_jwt_token_creation(self):
        """Test JWT token creation"""
        token = create_access_token({"sub": "testuser"})
        
        # Token should be a string
        self.assertIsInstance(token, str)
        
        # Token should have three parts (header.payload.signature)
        parts = token.split(".")
        self.assertEqual(len(parts), 3)


class TestPathSanitization(unittest.TestCase):
    """Test file path sanitization"""
    
    def test_directory_traversal_prevention(self):
        """Test prevention of directory traversal attacks"""
        dangerous_paths = [
            "../../../etc/passwd",
            "~/sensitive/file",
            "//etc//passwd",
            "..\\..\\windows\\system32"
        ]
        
        for path in dangerous_paths:
            sanitized = sanitize_file_path(path)
            self.assertNotIn("..", sanitized)
            self.assertNotIn("~", sanitized)
    
    def test_forbidden_path_prevention(self):
        """Test prevention of access to system directories"""
        forbidden_paths = [
            "/etc/passwd",
            "/usr/bin/bash",
            "/sys/kernel",
            "/proc/meminfo"
        ]
        
        for path in forbidden_paths:
            with self.assertRaises(ValueError):
                sanitize_file_path(path)


class TestJSONValidation(unittest.TestCase):
    """Test JSON input validation"""
    
    def test_shallow_json(self):
        """Test validation of shallow JSON"""
        data = {"key1": "value1", "key2": 123}
        validated = validate_json_input(data)
        self.assertEqual(data, validated)
    
    def test_deep_nesting_prevention(self):
        """Test prevention of deeply nested JSON"""
        # Create deeply nested JSON
        data = {"level1": {}}
        current = data["level1"]
        for i in range(15):
            current[f"level{i+2}"] = {}
            current = current[f"level{i+2}"]
        
        with self.assertRaises(ValueError):
            validate_json_input(data, max_depth=10)
    
    def test_nested_arrays(self):
        """Test validation of nested arrays"""
        data = {
            "array": [
                {"nested": [1, 2, 3]},
                {"nested": [4, 5, 6]}
            ]
        }
        validated = validate_json_input(data)
        self.assertEqual(data, validated)


if __name__ == "__main__":
    unittest.main()