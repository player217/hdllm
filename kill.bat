@echo off
setlocal ENABLEDELAYEDEXPANSION
chcp 65001 >nul 2>&1

REM HD현대미포 Gauss-1 RAG System - Process Terminator
REM Version: 1.0 - Clean Shutdown Utility
REM Date: 2025-01-30

title HD현대미포 Gauss-1 - 종료

echo ============================================================
echo   HD현대미포 Gauss-1 RAG System - 프로세스 종료
echo ============================================================
echo.
echo 관련 프로세스를 종료합니다...
echo.

REM Qdrant 종료
echo [1/5] Qdrant 종료 중...
for /f "tokens=2 delims=," %%p in ('tasklist /fi "imagename eq qdrant.exe" /fo csv 2^>nul ^| findstr /i "qdrant.exe"') do (
    set PID=%%~p
    if defined PID (
        taskkill /pid !PID! /f >nul 2>&1
        echo    -^> Qdrant 종료됨 (PID: !PID!)
    )
)
if not defined PID echo    -^> Qdrant 실행 중이 아님

REM Ollama 종료
echo [2/5] Ollama 종료 중...
set PID=
for /f "tokens=2 delims=," %%p in ('tasklist /fi "imagename eq ollama.exe" /fo csv 2^>nul ^| findstr /i "ollama.exe"') do (
    set PID=%%~p
    if defined PID (
        taskkill /pid !PID! /f >nul 2>&1
        echo    -^> Ollama 종료됨 (PID: !PID!)
    )
)
if not defined PID echo    -^> Ollama 실행 중이 아님

REM Python/Uvicorn 백엔드 종료
echo [3/5] Backend API 종료 중...
set FOUND=0
for /f "tokens=2" %%p in ('wmic process where "commandline like '%%uvicorn%%main:app%%'" get processid 2^>nul ^| findstr /r "[0-9]"') do (
    taskkill /pid %%p /f >nul 2>&1
    echo    -^> Backend API 종료됨 (PID: %%p)
    set FOUND=1
)
if !FOUND!==0 echo    -^> Backend API 실행 중이 아님

REM Python HTTP Server (Frontend) 종료
echo [4/5] Frontend 서버 종료 중...
set FOUND=0
for /f "tokens=2" %%p in ('wmic process where "commandline like '%%http.server%%8001%%'" get processid 2^>nul ^| findstr /r "[0-9]"') do (
    taskkill /pid %%p /f >nul 2>&1
    echo    -^> Frontend 서버 종료됨 (PID: %%p)
    set FOUND=1
)
if !FOUND!==0 echo    -^> Frontend 서버 실행 중이 아님

REM GUI 애플리케이션 종료
echo [5/5] GUI 애플리케이션 종료 중...
set FOUND=0
for /f "tokens=2" %%p in ('wmic process where "commandline like '%%HDLLM.py%%'" get processid 2^>nul ^| findstr /r "[0-9]"') do (
    taskkill /pid %%p /f >nul 2>&1
    echo    -^> GUI 종료됨 (PID: %%p)
    set FOUND=1
)
if !FOUND!==0 echo    -^> GUI 실행 중이 아님

REM 포트 확인
echo.
echo 포트 상태 확인 중...
netstat -an | findstr ":6333" >nul 2>&1
if !errorlevel! equ 0 (
    echo    ⚠ 포트 6333 아직 사용 중
) else (
    echo    ✓ 포트 6333 해제됨
)

netstat -an | findstr ":8080" >nul 2>&1
if !errorlevel! equ 0 (
    echo    ⚠ 포트 8080 아직 사용 중
) else (
    echo    ✓ 포트 8080 해제됨
)

netstat -an | findstr ":8001" >nul 2>&1
if !errorlevel! equ 0 (
    echo    ⚠ 포트 8001 아직 사용 중
) else (
    echo    ✓ 포트 8001 해제됨
)

netstat -an | findstr ":11434" >nul 2>&1
if !errorlevel! equ 0 (
    echo    ⚠ 포트 11434 아직 사용 중
) else (
    echo    ✓ 포트 11434 해제됨
)

echo.
echo ============================================================
echo   ✅ 프로세스 종료 완료
echo ============================================================
echo.
pause
exit /b 0