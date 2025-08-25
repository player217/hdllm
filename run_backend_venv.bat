@echo off
chcp 65001 >nul 2>&1
setlocal

echo ======================================================
echo  LLM RAG Backend - Virtual Environment Direct Run
echo ======================================================
echo.

:: 스크립트 디렉토리로 이동
cd /d "%~dp0"
echo [INFO] Current directory: %cd%
echo.

:: 가상환경 확인
if not exist ".\venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found!
    echo Please run INSTALL.bat first.
    pause
    exit /b 1
)

:: 환경 변수 설정
set RAG_MAIL_QDRANT_HOST=127.0.0.1
set RAG_MAIL_QDRANT_PORT=6333
set RAG_DOC_QDRANT_HOST=10.150.104.21
set RAG_DOC_QDRANT_PORT=6333
set RAG_OLLAMA_URL=http://127.0.0.1:11434/api/chat
set RAG_PORT=8080

echo [INFO] Environment settings:
echo   - Mail Qdrant: %RAG_MAIL_QDRANT_HOST%:%RAG_MAIL_QDRANT_PORT%
echo   - Doc Qdrant: %RAG_DOC_QDRANT_HOST%:%RAG_DOC_QDRANT_PORT%
echo   - Ollama: %RAG_OLLAMA_URL%
echo   - Backend Port: %RAG_PORT%
echo.

:: 백엔드 디렉토리로 이동
cd backend

echo [INFO] Starting backend with virtual environment Python...
echo   - Python: ..\venv\Scripts\python.exe
echo   - Script: main.py
echo.

:: 직접 Python으로 main.py 실행
..\venv\Scripts\python.exe main.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Backend exited with error code: %errorlevel%
    pause
    exit /b %errorlevel%
)

pause