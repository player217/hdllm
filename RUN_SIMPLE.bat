@echo off
title HD현대미포 Gauss-1 RAG System - 간편 실행

echo ============================================================
echo   HD현대미포 Gauss-1 RAG System - 간편 실행기
echo ============================================================
echo.

REM 프로젝트 루트로 이동
cd /d %~dp0

REM 가상환경 활성화
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
    echo [OK] 가상환경 활성화
) else (
    echo [ERROR] 가상환경이 없습니다. install.ps1을 먼저 실행하세요.
    pause
    exit /b 1
)

REM 백엔드 서버 시작
echo.
echo [1/3] Backend API 서버 시작 (포트 8080)...
start "Backend API" cmd /c "cd /d %~dp0 && call venv\Scripts\activate.bat && cd backend && python -m uvicorn main:app --host 0.0.0.0 --port 8080 --reload"
timeout /t 3 /nobreak >nul

REM 프론트엔드 서버 시작
echo [2/3] Frontend 웹 서버 시작 (포트 8001)...
start "Frontend Server" cmd /c "cd /d %~dp0 && call venv\Scripts\activate.bat && cd frontend && python -m http.server 8001"
timeout /t 2 /nobreak >nul

REM GUI 시작 (선택사항)
echo [3/3] GUI 애플리케이션을 시작하시겠습니까? (Y/N)
set /p RUNGUI=선택: 
if /i "%RUNGUI%"=="Y" (
    start "GUI Application" "%~dp0venv\Scripts\pythonw.exe" "%~dp0src\HDLLM.py"
    echo [OK] GUI 애플리케이션 시작됨
)

echo.
echo ============================================================
echo   시스템이 시작되었습니다!
echo ============================================================
echo.
echo 접속 주소:
echo   웹 인터페이스: http://localhost:8001
echo   API 서버: http://localhost:8080
echo   API 문서: http://localhost:8080/docs
echo.
echo 브라우저 열기 (Y/N)?
set /p OPENBROWSER=선택: 
if /i "%OPENBROWSER%"=="Y" (
    start http://localhost:8001
)

echo.
echo 종료하려면 stop.bat을 실행하세요.
echo 이 창을 닫아도 서비스는 계속 실행됩니다.
echo.
pause