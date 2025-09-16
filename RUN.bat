@echo off
setlocal

:: --- [수정] PYTHONPATH 환경 변수 초기화 ---
:: 시스템의 다른 파이썬 경로와 충돌하는 것을 방지합니다.
set PYTHONPATH=

title LLMPY Vector Studio - RUN

echo ======================================================
echo  Starting LLMPY Vector Studio...
echo ======================================================
echo.

:: --- 1. 스크립트 디렉토리로 이동 ---
cd /d "%~dp0"
echo [INFO] Current directory: %cd%
echo.

:: --- 2. 가상환경 확인 ---
echo [INFO] Checking for virtual environment...
if not exist ".\venv\Scripts\activate.bat" (
    echo [FATAL ERROR] Virtual environment not found. Please run INSTALL.bat first.
    pause
    exit /b
)
echo   -> Virtual environment check: PASSED
echo.

:: --- 3. 가상환경 활성화 ---
echo [INFO] Activating virtual environment...
call .\venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo [FATAL ERROR] Failed to activate virtual environment!
    pause
    exit /b
)
echo   -> Environment activated successfully.
echo.

:: --- 4. 파이썬 스크립트 실행 ---
echo [INFO] Running the Python GUI script...
echo   -> Command: python .\src\HDLLM.py
echo ------------------------------------------------------
echo.

python .\src\HDLLM.py

echo.
echo ------------------------------------------------------
echo [DEBUG] Python script has finished. Press any key to exit.
pause

6.runall.py 백엔드, 프론트엔드 호스팅.(qdrant는 아님. qdrant는 gui에서 호스팅)
import subprocess
import time
from pathlib import Path
import sys

# 1. 스크립트의 위치를 기준으로 프로젝트의 기본 경로들을 설정합니다.
project_root = Path(__file__).parent.resolve()
backend_dir = project_root / "backend"
activate_script = project_root / "venv" / "Scripts" / "activate.bat"

# 2. Ollama 서버 실행
ollama_command = (
    "set OLLAMA_NUM_GPU_LAYERS=100 && "
    "set OLLAMA_HOST=0.0.0.0 && "
    "set OLLAMA_ORIGINS=[\"*\"] && "
    "ollama serve"
)
subprocess.Popen(
    ["cmd.exe", "/k", ollama_command],
    creationflags=subprocess.CREATE_NEW_CONSOLE
)
print("✅ Ollama 서버 시작됨")
time.sleep(4)

# 3. FastAPI 백엔드 실행
if not activate_script.exists() or not backend_dir.exists():
    print("❌ 오류: 'venv' 또는 'backend' 폴더를 찾을 수 없습니다.")
    print(f"    - venv 경로: {activate_script}")
    print(f"    - backend 경로: {backend_dir}")
    sys.exit(1)

# [수정] f-string 내부의 경로 변수 주변 큰따옴표 제거
fastapi_command = (
    f'call {activate_script} && '
    f'cd /d {backend_dir} && '
    "uvicorn main:app --host 0.0.0.0 --port 8080"
)
subprocess.Popen(
    ["cmd.exe", "/k", fastapi_command],
    creationflags=subprocess.CREATE_NEW_CONSOLE
)
print("✅ FastAPI 백엔드 서버 시작됨")
time.sleep(6)

# 4. HTML 서버 실행
subprocess.Popen(["start", "", "http_server.bat"], shell=True)
print("✅ HTML 프론트엔드 서버 시작됨")

print("\n🚀 모든 서버가 시작되었습니다.")