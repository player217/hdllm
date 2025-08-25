@echo off
chcp 65001 >nul

echo ======================================================
echo  Starting LLM RAG Frontend Server...
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

:: Navigate to frontend directory
cd /d "%~dp0frontend"

:: Start Python HTTP server
echo Starting HTTP server on http://localhost:8001
echo Open http://localhost:8001 in your browser
python -m http.server 8001

pause