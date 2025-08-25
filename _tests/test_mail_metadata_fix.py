#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test script to verify mail metadata field fix
"""

import sys
import os
from pathlib import Path

print("=" * 60)
print("Mail Metadata Field Fix Verification")
print("=" * 60)

# Check the HDLLM.py file for the fixes
hdllm_path = Path("src/HDLLM.py")
if hdllm_path.exists():
    with open(hdllm_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print("\n1. Checking .msg file metadata fix...")
    # Check for sent_date in .msg handling
    if '"sent_date": msg.date' in content:
        print("   [OK] .msg files now include 'sent_date' field")
    else:
        print("   [FAIL] .msg files missing 'sent_date' field")
    
    # Check that both fields exist
    if '"sent_date": msg.date' in content and '"date": msg.date' in content:
        print("   [OK] .msg files have both 'sent_date' and 'date' for compatibility")
    else:
        print("   [WARN] .msg files may not have both fields")
    
    print("\n2. Checking .eml file metadata fix...")
    # Check for sent_date in .eml handling
    if '"sent_date": eml_data[\'date\']' in content:
        print("   [OK] .eml files now include 'sent_date' field")
    else:
        print("   [FAIL] .eml files missing 'sent_date' field")
    
    # Check that both fields exist
    if '"sent_date": eml_data[\'date\']' in content and '"date": eml_data[\'date\']' in content:
        print("   [OK] .eml files have both 'sent_date' and 'date' for compatibility")
    else:
        print("   [WARN] .eml files may not have both fields")
    
    print("\n3. Checking live Outlook embedding metadata fix...")
    # Check for sent_date in live embedding
    if '"sent_date":' in content and 'SentOn.strftime' in content:
        print("   [OK] Live Outlook embedding now includes 'sent_date' field")
    else:
        print("   [FAIL] Live Outlook embedding missing 'sent_date' field")
    
    print("\n4. Checking backend compatibility...")
    # Count occurrences of sent_date to ensure all three places are fixed
    sent_date_count = content.count('"sent_date":')
    if sent_date_count >= 3:
        print(f"   [OK] Found {sent_date_count} occurrences of 'sent_date' field")
    else:
        print(f"   [WARN] Only found {sent_date_count} occurrences of 'sent_date' field (expected at least 3)")

else:
    print("   [FAIL] HDLLM.py not found")

print("\n" + "=" * 60)
print("Fix Summary")
print("=" * 60)

print("""
The metadata field fix has been applied to ensure compatibility between
the embedding process and the backend search functionality.

Key Changes:
1. Added 'sent_date' field to all email metadata (backend expects this)
2. Kept 'date' field for backward compatibility
3. Applied to .msg files, .eml files, and live Outlook embedding

What to do next:
1. Clear the existing Qdrant collection or use "Fresh Start" option
2. Re-embed your email files
3. Test the search functionality with queries like "르꼬끄"
4. The search should now find and return the embedded emails

Note: The backend (main.py) already handles both field names:
   date = payload.get("sent_date") or payload.get("date", "N/A")
So this fix ensures the data is stored with the expected field names.
""")

print("=" * 60)