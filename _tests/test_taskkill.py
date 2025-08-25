#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test taskkill functionality
"""
import subprocess
import time
import sys

print("Testing taskkill command...")

# Start notepad
process = subprocess.Popen(['notepad.exe'])
print(f"Started notepad.exe with PID: {process.pid}")
time.sleep(2)

# Try different taskkill approaches
print("\nTrying taskkill with /T /F /PID...")
result = subprocess.run(
    ['taskkill', '/T', '/F', '/PID', str(process.pid)],
    capture_output=True,
    text=True
)

print(f"Exit code: {result.returncode}")
print(f"Stdout: {result.stdout}")
print(f"Stderr: {result.stderr}")

if result.returncode == 0:
    print("SUCCESS: Process terminated")
else:
    print("FAILED: Trying regular terminate()...")
    process.terminate()
    time.sleep(1)
    
print("\nTest completed!")