@echo off
setlocal ENABLEDELAYEDEXPANSION
chcp 65001 >nul 2>&1

REM 모든 서비스 중지 스크립트

title HD현대미포 Gauss-1 - 서비스 중지

echo ============================================================
echo   HD현대미포 Gauss-1 RAG System - 서비스 중지
echo ============================================================
echo.

echo [1/5] Qdrant 서버 중지 중...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":6333" ^| findstr "LISTENING"') do (
    echo    -^> Qdrant 프로세스 중지 (PID: %%p)
    taskkill /PID %%p /F >nul 2>&1
)
echo    -^> Qdrant 중지 완료

echo [2/5] Ollama 서버 중지 중...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":11434" ^| findstr "LISTENING"') do (
    echo    -^> Ollama 프로세스 중지 (PID: %%p)
    taskkill /PID %%p /F >nul 2>&1
)
echo    -^> Ollama 중지 완료

echo [3/5] Backend API 서버 중지 중...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8080" ^| findstr "LISTENING"') do (
    echo    -^> Backend API 프로세스 중지 (PID: %%p)
    taskkill /PID %%p /F >nul 2>&1
)
echo    -^> Backend API 중지 완료

echo [4/5] Frontend 웹 서버 중지 중...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8001" ^| findstr "LISTENING"') do (
    echo    -^> Frontend 프로세스 중지 (PID: %%p)
    taskkill /PID %%p /F >nul 2>&1
)
echo    -^> Frontend 중지 완료

echo [5/5] GUI 애플리케이션 중지 중...
taskkill /IM "python.exe" /FI "WINDOWTITLE eq GUI Application*" >nul 2>&1
taskkill /IM "pythonw.exe" /FI "WINDOWTITLE eq GUI Application*" >nul 2>&1
echo    -^> GUI 애플리케이션 중지 완료

echo.
echo ============================================================
echo   ✅ 모든 서비스가 중지되었습니다
echo ============================================================
echo.

echo 포트 상태 확인:
netstat -ano | findstr ":6333 :8080 :8001 :11434" | findstr "LISTENING" && (
    echo ⚠️ 일부 서비스가 여전히 실행 중입니다.
) || (
    echo ✅ 모든 포트가 해제되었습니다.
)

echo.
echo 다시 시작하려면 RUN.bat을 실행하세요.
pause