@echo off
chcp 65001 >nul
setlocal

echo ======================================================
echo  Starting LLM RAG Backend Server...
echo ======================================================
echo.

:: 가상환경 활성화
if exist "%~dp0venv\Scripts\activate.bat" (
    call "%~dp0venv\Scripts\activate.bat"
) else (
    echo [오류] 가상환경을 찾을 수 없습니다. INSTALL.bat을 먼저 실행하세요.
    pause
    exit /b
)

:: Set environment variables for mail/doc Qdrant separation
:: Modify these values for your environment
set RAG_MAIL_QDRANT_HOST=127.0.0.1
set RAG_MAIL_QDRANT_PORT=6333
set RAG_DOC_QDRANT_HOST=127.0.0.1
set RAG_DOC_QDRANT_PORT=6333
set RAG_OLLAMA_URL=http://127.0.0.1:11434/api/chat

:: Navigate to project root
cd /d "%~dp0"

:: Check if uvicorn.exe exists in venv
if exist "%~dp0venv\Scripts\uvicorn.exe" (
    echo Using uvicorn.exe from virtual environment
    cd backend
    "%~dp0venv\Scripts\uvicorn.exe" main:app --host 0.0.0.0 --port 8080 --reload
) else (
    echo Using Python to run backend directly
    "%~dp0venv\Scripts\python.exe" run_backend_direct.py
)

pause