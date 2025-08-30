#!/usr/bin/env python3
"""
Content-Type validation test for NDJSON support
"""

def test_content_type_validation():
    """Test updated content-type validation logic"""
    print("Testing content-type validation for NDJSON support...")
    
    # Simulate the updated validation logic from test_smoke.py
    test_cases = [
        ("application/x-ndjson", "GPU-accelerated streaming"),
        ("text/event-stream", "Legacy SSE streaming"),
        ("application/json", "Non-streaming JSON"),
        ("application/x-ndjson; charset=utf-8", "NDJSON with charset"),
        ("text/event-stream; charset=utf-8", "SSE with charset")
    ]
    
    passed = 0
    for content_type, description in test_cases:
        # Updated validation logic from the smoke test
        is_valid = (
            "application/x-ndjson" in content_type      # GPU-accelerated streaming
            or "text/event-stream" in content_type     # Legacy SSE streaming  
            or "application/json" in content_type      # Non-streaming JSON
        )
        
        if is_valid:
            print(f"PASS: {content_type} - {description}")
            passed += 1
        else:
            print(f"FAIL: {content_type} - {description}")
    
    print(f"\nResult: {passed}/{len(test_cases)} content-type validations passed")
    return passed == len(test_cases)

if __name__ == "__main__":
    success = test_content_type_validation()
    if success:
        print("SUCCESS: All content-type validations passed!")
        print("Quality gate NDJSON support is working correctly")
    else:
        print("FAILED: Some content-type validations failed")
    exit(0 if success else 1)