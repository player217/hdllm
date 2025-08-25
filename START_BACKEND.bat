@echo off
echo === Backend Server Starting ===
echo.

cd /d "%~dp0"

:: Check virtual environment
if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found!
    echo Please run INSTALL.bat first.
    pause
    exit /b 1
)

:: Set environment variables
set RAG_MAIL_QDRANT_HOST=127.0.0.1
set RAG_MAIL_QDRANT_PORT=6333
set RAG_DOC_QDRANT_HOST=127.0.0.1
set RAG_DOC_QDRANT_PORT=6333

:: Start backend server
echo Starting backend server on port 8080...
venv\Scripts\python.exe run_backend_direct.py