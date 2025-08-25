@echo off
echo === LLM RAG System 시작 ===
echo.

cd /d "%~dp0"

:: 환경변수 설정
set RAG_MAIL_QDRANT_HOST=127.0.0.1
set RAG_MAIL_QDRANT_PORT=6333
set RAG_DOC_QDRANT_HOST=127.0.0.1
set RAG_DOC_QDRANT_PORT=6333

:: 백엔드 시작
echo [1] 백엔드 서버 시작...
if exist "venv\Scripts\uvicorn.exe" (
    start "Backend Server" cmd /k "cd backend && ..\venv\Scripts\uvicorn.exe main:app --host 0.0.0.0 --port 8080 --reload"
) else (
    start "Backend Server" cmd /k "venv\Scripts\python.exe run_backend_direct.py"
)

:: 3초 대기
timeout /t 3 /nobreak >nul

:: 프론트엔드 시작
echo [2] 프론트엔드 서버 시작...
start "Frontend Server" cmd /k "cd frontend && ..\venv\Scripts\python.exe -m http.server 8001"

:: 3초 대기
timeout /t 3 /nobreak >nul

:: GUI 시작
echo [3] GUI 프로그램 시작...
start "GUI Application" cmd /k "venv\Scripts\python.exe src\HDLLM.py"

echo.
echo === 모든 서비스가 시작되었습니다 ===
echo.
echo - 백엔드: http://localhost:8080
echo - 프론트엔드: http://localhost:8001
echo - GUI: 별도 창에서 실행 중
echo.
echo 브라우저에서 http://localhost:8001 접속하세요.
echo.
pause