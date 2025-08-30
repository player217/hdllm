@echo off
setlocal ENABLEDELAYEDEXPANSION
chcp 65001 >nul 2>&1

REM HD현대미포 Gauss-1 RAG System - Enhanced Runner
REM Version: 2.1 - Smart Port Detection & Process Management
REM Date: 2025-01-30

title HD현대미포 Gauss-1 RAG System

echo ============================================================
echo   HD현대미포 Gauss-1 RAG System - 실행 프로그램 v2.1
echo ============================================================
echo.

REM 기준 경로
set ROOT=%~dp0
cd /d "%ROOT%"

REM 1) 가상환경 활성화
echo [1/5] 가상환경 확인...
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] 가상환경이 없습니다. 먼저 install.bat 을 실행하세요.
    pause
    exit /b 1
)
call venv\Scripts\activate.bat
echo    -^> 가상환경 활성화 완료
echo.

REM 2) 로컬 Qdrant 가동(개인용) - 이미 떠있으면 건너뜀
echo [2/5] Qdrant 벡터 DB 시작...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":6333" ^| findstr "LISTENING"') do set QPID=%%p
if not defined QPID (
    if exist "bin\qdrant\qdrant.exe" (
        start "Qdrant Server" /B "bin\qdrant\qdrant.exe" --storage-dir "%ROOT%storage\qdrant"
        echo    -^> Qdrant 시작 중 (포터블 버전)...
    ) else if exist "src\bin\qdrant.exe" (
        start "Qdrant Server" /B "src\bin\qdrant.exe"
        echo    -^> Qdrant 시작 중 (기존 경로)...
    ) else (
        echo    -^> Qdrant 실행 파일 없음. 설치를 확인하세요.
    )
    timeout /t 3 /nobreak >nul
) else (
    echo    -^> Qdrant 이미 실행 중 (PID: !QPID!)
)
echo.

REM 3) Ollama 서버 시작
echo [3/5] Ollama LLM 서버 시작...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":11434" ^| findstr "LISTENING"') do set OPID=%%p
if not defined OPID (
    where ollama >nul 2>&1
    if !errorlevel! equ 0 (
        start "Ollama Server" /B ollama serve
        echo    -^> Ollama 시작 중...
    ) else if exist "bin\ollama\ollama.exe" (
        start "Ollama Server" /B "bin\ollama\ollama.exe" serve
        echo    -^> Ollama 시작 중 (포터블 버전)...
    ) else (
        echo    -^> Ollama 미설치. LLM 기능이 제한됩니다.
    )
    timeout /t 3 /nobreak >nul
) else (
    echo    -^> Ollama 이미 실행 중 (PID: !OPID!)
)
echo.

REM 4) 백엔드 API 서버 시작
echo [4/5] Backend API 서버 시작...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8080" ^| findstr "LISTENING"') do set BPID=%%p
if not defined BPID (
    echo    -^> FastAPI 서버 시작 중 (포트 8080)...
    
    REM .env 파일 확인
    if exist ".env" (
        start "Backend API" cmd /k "cd backend && python -m uvicorn main:app --host 0.0.0.0 --port 8080 --reload --env-file ..\.env"
    ) else if exist ".env.test" (
        start "Backend API" cmd /k "cd backend && python -m uvicorn main:app --host 0.0.0.0 --port 8080 --reload --env-file ..\.env.test"
    ) else (
        start "Backend API" cmd /k "cd backend && python -m uvicorn main:app --host 0.0.0.0 --port 8080 --reload"
    )
    
    timeout /t 5 /nobreak >nul
) else (
    echo    -^> Backend API 이미 실행 중 (PID: !BPID!)
)
echo.

REM 5) 프론트엔드 서버 시작
echo [5/5] Frontend 웹 서버 시작...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8001" ^| findstr "LISTENING"') do set FPID=%%p
if not defined FPID (
    echo    -^> 웹 서버 시작 중 (포트 8001)...
    start "Frontend Server" cmd /k "cd frontend && python -m http.server 8001"
    timeout /t 2 /nobreak >nul
) else (
    echo    -^> Frontend 이미 실행 중 (PID: !FPID!)
)
echo.

REM 선택: GUI 애플리케이션 시작
echo GUI 애플리케이션을 시작하시겠습니까? (Y/N)
set /p RUNGUI=선택: 
if /i "!RUNGUI!"=="Y" (
    echo GUI 애플리케이션 시작 중...
    start "GUI Application" "%ROOT%venv\Scripts\pythonw.exe" "%ROOT%src\HDLLM.py"
)

echo.
echo ============================================================
echo   