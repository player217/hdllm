@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

title TT - Frontend Server

:: 프로젝트 루트 경로 설정
set "PROJECT_ROOT=%~dp0"
set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"

echo ======================================================
echo  TT - Frontend Server Starting
echo ======================================================
echo.
echo  Frontend Server: http://localhost:8001
echo  Project Root: %PROJECT_ROOT%
echo  Serving from: %PROJECT_ROOT%\frontend
echo.

:: frontend 폴더 존재 확인
if not exist "%PROJECT_ROOT%\frontend" (
    echo [ERROR] Frontend directory not found: %PROJECT_ROOT%\frontend
    exit /b 1
)

:: 가상환경 Python 존재 확인
if not exist "%PROJECT_ROOT%\venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment Python not found: %PROJECT_ROOT%\venv\Scripts\python.exe
    exit /b 1
)

:: frontend 폴더로 이동
cd /d "%PROJECT_ROOT%\frontend"

:: 가상환경의 Python을 사용하여 HTTP 서버 실행
echo Starting HTTP server on port 8001...
"%PROJECT_ROOT%\venv\Scripts\python.exe" -m http.server 8001