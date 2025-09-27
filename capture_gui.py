#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GUI 상태 스크린샷 캡처
"""

import subprocess
import time
from pathlib import Path
import requests

def capture_gui_screenshot():
    """GUI 스크린샷 캡처"""
    print("Capturing GUI Screenshot...")
    
    # Chrome 경로들
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Users\%USERNAME%\AppData\Local\Google\Chrome\Application\chrome.exe"
    ]
    
    chrome_path = None
    for path in chrome_paths:
        expanded_path = Path(path.replace('%USERNAME%', Path.home().name))
        if expanded_path.exists():
            chrome_path = str(expanded_path)
            break
    
    if not chrome_path:
        print("   Chrome not found - cannot capture screenshot")
        return False
    
    # 먼저 GUI 접근 가능한지 확인
    try:
        response = requests.get("http://localhost:8001", timeout=5)
        print(f"   GUI accessibility: {response.status_code}")
    except:
        print("   GUI not accessible at localhost:8001")
        return False
    
    # 스크린샷 경로
    screenshot_path = Path("C:/Users/lseun/Documents/LMM_UI_APP/.playwright-mcp/final-gui-state.png")
    screenshot_path.parent.mkdir(exist_ok=True)
    
    try:
        # Chrome headless 스크린샷
        cmd = [
            chrome_path,
            "--headless",
            "--disable-gpu",
            "--disable-software-rasterizer",
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--window-size=1920,1080",
            f"--screenshot={screenshot_path}",
            "http://localhost:8001"
        ]
        
        print(f"   Running: {' '.join(cmd[:3])} ... (with screenshot)")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if screenshot_path.exists():
            print(f"   Screenshot saved: {screenshot_path}")
            print(f"   File size: {screenshot_path.stat().st_size} bytes")
            return True
        else:
            print(f"   Screenshot failed. Return code: {result.returncode}")
            if result.stderr:
                print(f"   Error: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("   Screenshot timed out")
        return False
    except Exception as e:
        print(f"   Screenshot error: {e}")
        return False

def main():
    print("Final GUI State Capture")
    print("=" * 30)
    
    success = capture_gui_screenshot()
    
    if success:
        print("\nSuccess: GUI screenshot captured!")
        print("Check: .playwright-mcp/final-gui-state.png")
    else:
        print("\nFailed: Could not capture GUI screenshot")
        print("Please manually verify GUI at http://localhost:8001")
    
    return success

if __name__ == "__main__":
    main()