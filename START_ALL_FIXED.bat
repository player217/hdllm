@echo off
echo === LLM RAG System Start ===
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
echo [1] Starting Backend Server...
start "Backend Server" cmd /k "venv\Scripts\python.exe run_backend_direct.py"

:: Wait for backend to start
echo Waiting for backend to start...
timeout /t 5 /nobreak >nul

:: Start frontend server
echo [2] Starting Frontend Server...
start "Frontend Server" cmd /k "cd frontend && ..\venv\Scripts\python.exe -m http.server 8001"

:: Wait for frontend to start
timeout /t 3 /nobreak >nul

:: Start GUI application
echo [3] Starting GUI Application...
start "GUI Application" cmd /k "venv\Scripts\python.exe src\HDLLM.py"

echo.
echo === All services started ===
echo.
echo - Backend: http://localhost:8080
echo - Frontend: http://localhost:8001
echo - GUI: Running in separate window
echo.
echo Open http://localhost:8001 in your browser
echo.
pause