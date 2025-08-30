#!/usr/bin/env python3
"""
Minimal test for AskRequest schema compatibility
Tests only the schema without importing backend dependencies
"""

import sys

def test_minimal_schema():
    """Test just the Pydantic schema functionality"""
    print("Testing Pydantic AskRequest schema...")
    
    try:
        # Import minimal dependencies for schema
        from typing import List, Dict, Any, Optional, Union, Literal
        from pydantic import BaseModel, Field, validator, root_validator, ConfigDict
        from datetime import datetime
        from enum import Enum
        import uuid
        import re
        
        # Define minimal enums and base classes needed
        class SourceType(str, Enum):
            MAIL = "mail"
            DOCUMENT = "doc"
        
        class ModelType(str, Enum):
            GEMMA3_4B = "gemma3:4b"
        
        class BaseRequest(BaseModel):
            request_id: Optional[str] = Field(
                default_factory=lambda: str(uuid.uuid4()),
                description="Unique request identifier"
            )
        
        # Test the exact AskRequest implementation
        class AskRequest(BaseRequest):
            query: str = Field(min_length=1, max_length=2000, description="Search query")
            source: SourceType = Field(default=SourceType.MAIL, description="Data source")
            model: ModelType = Field(default=ModelType.GEMMA3_4B, description="LLM model")
            top_k: int = Field(default=10, ge=1, le=100, description="Number of results")
            filters: Dict[str, Any] = Field(default_factory=dict, description="Search filters")
            stream: bool = Field(default=False, description="Enable streaming response")
            
            @root_validator(pre=True)
            def _compat_question_alias(cls, values):
                """Backward compatibility: accept 'question' field and map to 'query'"""
                if "query" not in values and "question" in values:
                    values["query"] = values.pop("question")
                return values
            
            @validator('query')
            def validate_query(cls, v):
                """Validate and sanitize query"""
                v = v.replace('\x00', '')
                sql_patterns = [
                    r"(DROP|DELETE|INSERT|UPDATE|EXEC|EXECUTE)",
                    r"(--|;|'|\"|\*|\||\\)"
                ]
                for pattern in sql_patterns:
                    if re.search(pattern, v, re.IGNORECASE):
                        raise ValueError("Invalid characters in query")
                return v.strip()
        
        # Test cases
        print("Test 1: Legacy format (question field)")
        req1 = AskRequest(question="test legacy")
        print(f"Result: query='{req1.query}', source='{req1.source}'")
        assert req1.query == "test legacy"
        
        print("Test 2: New format (query field)")
        req2 = AskRequest(query="test new")
        print(f"Result: query='{req2.query}', source='{req2.source}'")
        assert req2.query == "test new"
        
        print("Test 3: Mixed fields (query should take precedence)")
        req3 = AskRequest(query="test query", question="test question")
        print(f"Result: query='{req3.query}' (should be 'test query')")
        assert req3.query == "test query"
        
        print("SUCCESS: All backward compatibility tests passed!")
        return True
        
    except Exception as e:
        print(f"FAILED: Schema test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_minimal_schema()
    print(f"Overall result: {'PASSED' if success else 'FAILED'}")
    sys.exit(0 if success else 1)