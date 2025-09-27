# tray_launcher_wrapper.py - 컴파일된 실행파일을 위한 래퍼
"""
이 파일은 컴파일 시 실제 경로 처리를 담당합니다.
PyInstaller로 컴파일 시 외부 리소스 경로를 올바르게 찾도록 합니다.
"""

import os
import sys
import subprocess
from pathlib import Path

def get_base_path():
    """실행 파일의 기본 경로를 반환"""
    if getattr(sys, 'frozen', False):
        # PyInstaller로 컴파일된 경우
        if hasattr(sys, '_MEIPASS'):
            # 임시 폴더가 아닌 실행파일이 있는 디렉토리를 기준으로
            return Path(sys.executable).parent
        return Path(sys.executable).parent
    else:
        # 일반 Python 스크립트로 실행되는 경우
        return Path(__file__).parent

def run_service(service_name, command, cwd=None, env=None):
    """서비스 실행 헬퍼"""
    base_path = get_base_path()
    
    # 경로를 절대 경로로 변환
    if isinstance(command, list):
        command = [str(base_path / cmd) if not Path(cmd).is_absolute() else cmd for cmd in command]
    
    if cwd:
        cwd = base_path / cwd if not Path(cwd).is_absolute() else cwd
    
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd or base_path,
            env=env or os.environ.copy(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )
        return process
    except Exception as e:
        print(f"Failed to start {service_name}: {e}")
        return None

# 컴파일 시 포함될 설정
COMPILED_CONFIG = {
    "use_relative_paths": True,
    "base_path_mode": "executable_dir"
}