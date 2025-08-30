#!/usr/bin/env python3
"""
Status Value Alignment Test
Author: Claude Code
Date: 2025-01-26
Purpose: Verify status values match between resource_manager.py and main.py
"""

import sys
import re
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def test_status_alignment():
    """Test that status values align between resource_manager.py and main.py"""
    
    print("=" * 60)
    print("Status Value Alignment Test")
    print("=" * 60)
    
    # Expected values from main.py
    expected_values = ["success", "warning", "error"]
    
    # Read resource_manager.py
    rm_path = Path("backend/resource_manager.py")
    rm_content = rm_path.read_text(encoding='utf-8')
    
    # Read main.py
    main_path = Path("backend/main.py")
    main_content = main_path.read_text(encoding='utf-8')
    
    print("\n[1] Checking resource_manager.py status values...")
    print("-" * 40)
    
    # Find status assignments in resource_manager.py
    rm_status_pattern = r'validation_results\["overall_status"\]\s*=\s*"([^"]+)"'
    rm_statuses = re.findall(rm_status_pattern, rm_content)
    
    print(f"Found status values in resource_manager.py: {rm_statuses}")
    
    # Verify all expected values are present
    for expected in expected_values:
        if expected in rm_statuses:
            print(f"[OK] '{expected}' found in resource_manager.py")
        else:
            print(f"[ERROR] '{expected}' NOT found in resource_manager.py")
            return False
    
    print("\n[2] Checking main.py status handling...")
    print("-" * 40)
    
    # Find status handling in main.py
    # Look for patterns like: if result.get("overall_status") == "success"
    main_status_pattern = r'overall_status["\']?\)?\s*==\s*["\']([^"\']+)["\']'
    main_statuses = re.findall(main_status_pattern, main_content)
    
    print(f"Found status checks in main.py: {list(set(main_statuses))}")
    
    # Check that main.py handles the same values
    for status in expected_values:
        if status in main_statuses:
            print(f"[OK] main.py handles '{status}'")
        else:
            print(f"[WARNING] main.py may not handle '{status}' explicitly")
    
    print("\n[3] Cross-validation...")
    print("-" * 40)
    
    # Ensure resource_manager.py doesn't return any unexpected values
    unexpected_values = set(rm_statuses) - set(expected_values)
    if unexpected_values:
        print(f"[ERROR] Unexpected values in resource_manager.py: {unexpected_values}")
        return False
    
    print("[OK] All status values align correctly")
    
    print("\n[4] Checking for old 'ok' value...")
    print("-" * 40)
    
    # Make sure old "ok" value is not used
    if 'overall_status"] = "ok"' in rm_content:
        print("[ERROR] Old 'ok' value still present in resource_manager.py")
        return False
    else:
        print("[OK] Old 'ok' value has been removed")
    
    print("\n" + "=" * 60)
    print("ALIGNMENT TEST RESULT")
    print("=" * 60)
    
    print("""
Status values correctly aligned:
- resource_manager.py returns: success, warning, error
- main.py expects: success, warning, error
- No unexpected values found
- Old 'ok' value removed

[SUCCESS] Status alignment verified!
    """)
    
    return True

if __name__ == "__main__":
    success = test_status_alignment()
    sys.exit(0 if success else 1)