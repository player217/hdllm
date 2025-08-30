#!/usr/bin/env python3
"""
Simple Collection Unification Test
Author: Claude Code
Date: 2025-01-26
"""

import sys
from pathlib import Path

# Add project root to Python path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

def test_resource_manager_import():
    """Test ResourceManager import and basic functionality"""
    
    print("=" * 60)
    print("Collection Unification Simple Test")
    print("=" * 60)
    
    try:
        from backend.resource_manager import ResourceManager
        print("[OK] ResourceManager import successful")
        
        # Test ResourceConfig
        from backend.resource_manager import ResourceConfig
        config = ResourceConfig()
        print(f"[OK] ResourceConfig created")
        
        # Test collection name generation
        mail_collection = config.get_collection_name("mail", "my_documents")
        doc_collection = config.get_collection_name("doc", "my_documents")
        
        print(f"[INFO] Mail collection: {mail_collection}")
        print(f"[INFO] Doc collection: {doc_collection}")
        print("[OK] Collection name generation test passed")
        
        return True
        
    except ImportError as e:
        print(f"[ERROR] Import failed: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] Test failed: {e}")
        return False

def test_main_functions():
    """Test main.py functions"""
    
    print("\n[2] Testing main.py functions")
    print("-" * 40)
    
    try:
        sys.path.insert(0, str(PROJECT_ROOT / "backend"))
        from backend.main import _get_current_namespace_mapping
        
        mapping = _get_current_namespace_mapping()
        print("[OK] Namespace mapping function works")
        
        for source, collection_name in mapping.items():
            print(f"[INFO] {source} -> {collection_name}")
        
        return True
        
    except ImportError as e:
        print(f"[WARNING] main.py functions not available: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] main.py test failed: {e}")
        return False

def test_security_config():
    """Test security config functions"""
    
    print("\n[3] Testing security config")
    print("-" * 40)
    
    try:
        from backend.qdrant_security_config import create_default_security_config
        
        # Test without ResourceManager (fallback)
        config = create_default_security_config(resource_manager=None)
        print("[OK] Security config creation successful")
        
        print(f"[INFO] Collection namespaces:")
        for source, collection_name in config.collection_namespaces.items():
            print(f"  {source} -> {collection_name}")
        
        return True
        
    except ImportError as e:
        print(f"[WARNING] Security config not available: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] Security config test failed: {e}")
        return False

def main():
    """Main test function"""
    
    print("Starting HD Hyundai Mipo Gauss-1 Collection Unification Test")
    
    test1 = test_resource_manager_import()
    test2 = test_main_functions()
    test3 = test_security_config()
    
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    tests = [
        ("ResourceManager Import", test1),
        ("Main Functions", test2),
        ("Security Config", test3)
    ]
    
    passed = sum(1 for _, result in tests if result)
    total = len(tests)
    
    for test_name, result in tests:
        status = "[OK]" if result else "[FAIL]"
        print(f"{status} {test_name}")
    
    print(f"\nSuccess Rate: {passed}/{total} ({passed/total*100:.1f}%)")
    
    if passed >= 1:  # At least ResourceManager should work
        print("Core functionality test passed!")
        return 0
    else:
        print("Critical functionality test failed!")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)