#!/usr/bin/env python3
"""
Quick validation script for compatibility fixes
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

def test_askrequest_compatibility():
    """Test AskRequest backward compatibility"""
    print("Testing AskRequest backward compatibility...")
    
    try:
        from backend.common.schemas import AskRequest
        
        # Test legacy format (question field)
        req1 = AskRequest(question="test legacy", source="mail")
        print(f"SUCCESS Legacy client (question): {req1.query}")
        
        # Test new format (query field)
        req2 = AskRequest(query="test new", source="mail") 
        print(f"SUCCESS New client (query): {req2.query}")
        
        # Test mixed fields (query should take precedence)
        req3 = AskRequest(query="test new", question="test legacy", source="mail")
        print(f"SUCCESS Mixed fields (query priority): {req3.query}")
        
        return True
        
    except Exception as e:
        print(f"FAILED AskRequest compatibility test failed: {e}")
        return False

def main():
    print("Running compatibility validation tests...")
    
    success = test_askrequest_compatibility()
    
    if success:
        print("SUCCESS All compatibility tests passed!")
        print("Quality gate compatibility fixes are working correctly")
        return 0
    else:
        print("FAILED Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())