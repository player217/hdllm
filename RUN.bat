@echo off
chcp 65001 >nul 2>&1
setlocal

:: --- PYTHONPATH 환경 변수 초기화 ---
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
if not exist ".\venv\Scripts\python.exe" (
    echo [FATAL ERROR] Virtual environment not found. Please run INSTALL.bat first.
    pause
    exit /b
)
echo   -^> Virtual environment check: PASSED
echo.

:: --- 3. 파이썬 스크립트 직접 실행 ---
echo [INFO] Running the Python GUI script...
echo   -^> Command: venv\Scripts\python.exe src\HDLLM.py
echo ------------------------------------------------------
echo.

.\venv\Scripts\python.exe .\src\HDLLM.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Python script exited with error code: %errorlevel%
    echo.
)

echo.
echo ------------------------------------------------------
echo [DEBUG] Python script has finished. Press any key to exit.
pause