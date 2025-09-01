@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

REM ================================================================================================
REM  HD현대미포 Gauss-1 RAG System - 전체 서비스 중지 스크립트
REM ================================================================================================

title HD Gauss-1 Service Terminator

echo ============================================================
echo   HD현대미포 Gauss-1 RAG System - 서비스 중지
echo ============================================================
echo.

set KILLED=0

REM 서비스별 프로세스 종료
echo [1/5] GUI 애플리케이션 종료 중...
taskkill /im pythonw.exe /f >nul 2>&1
if not errorlevel 1 (
    echo    ✓ GUI 프로세스 종료됨 (pythonw.exe)
    set /a KILLED+=1
) else (
    echo    → GUI 프로세스 없음
)

echo [2/5] Python 프로세스 종료 중...
taskkill /im python.exe /f >nul 2>&1
if not errorlevel 1 (
    echo    ✓ Python 프로세스 종료됨 (python.exe)
    set /a KILLED+=1
) else (
    echo    → Python 프로세스 없음
)

echo [3/5] Qdrant 서버 종료 중...
taskkill /im qdrant.exe /f >nul 2>&1
if not errorlevel 1 (
    echo    ✓ Qdrant 서버 종료됨 (qdrant.exe)
    set /a KILLED+=1
) else (
    echo    → Qdrant 서버 없음
)

echo [4/5] Ollama 서버 종료 중...
taskkill /im ollama.exe /f >nul 2>&1
if not errorlevel 1 (
    echo    ✓ Ollama 서버 종료됨 (ollama.exe)
    set /a KILLED+=1
) else (
    echo    → Ollama 서버 없음
)

echo [5/5] Backend API 서버 종료 중...
REM uvicorn 프로세스 찾기 (명령줄에 uvicorn이 포함된 python 프로세스)
for /f "tokens=2" %%p in ('wmic process where "commandline like '%%uvicorn%%backend.main%%'" get processid /value 2^>nul ^| findstr "ProcessId"') do (
    set PID=%%p
    if not "!PID!"=="" (
        taskkill /pid !PID! /f >nul 2>&1
        echo    ✓ Backend API 서버 종료됨 (PID: !PID!)
        set /a KILLED+=1
    )
)

REM 웹 서버 종료 (http.server)
for /f "tokens=2" %%p in ('wmic process where "commandline like '%%http.server%%'" get processid /value 2^>nul ^| findstr "ProcessId"') do (
    set PID=%%p
    if not "!PID!"=="" (
        taskkill /pid !PID! /f >nul 2>&1
        echo    ✓ 프론트엔드 웹 서버 종료됨 (PID: !PID!)
        set /a KILLED+=1
    )
)

echo.

REM 포트 정리 확인
echo 포트 사용 현황 확인 중...
for /f "tokens=2" %%p in ('netstat -ano ^| findstr ":6333" ^| findstr "LISTENING"') do (
    echo    ⚠ 포트 6333 여전히 사용 중: %%p
)
for /f "tokens=2" %%p in ('netstat -ano ^| findstr ":8080" ^| findstr "LISTENING"') do (
    echo    ⚠ 포트 8080 여전히 사용 중: %%p
)
for /f "tokens=2" %%p in ('netstat -ano ^| findstr ":8001" ^| findstr "LISTENING"') do (
    echo    ⚠ 포트 8001 여전히 사용 중: %%p
)
for /f "tokens=2" %%p in ('netstat -ano ^| findstr ":11434" ^| findstr "LISTENING"') do (
    echo    ⚠ 포트 11434 여전히 사용 중: %%p
)

echo.
echo ============================================================
if %KILLED% GTR 0 (
    echo   ✅ %KILLED%개 서비스가 중지되었습니다.
) else (
    echo   ℹ️ 실행 중인 서비스가 없었습니다.
)
echo ============================================================
echo.
echo 중지된 서비스:
echo   • HD Gauss-1 GUI 애플리케이션
echo   • Backend API 서버 (FastAPI)
echo   • Qdrant 벡터 데이터베이스
echo   • Ollama LLM 서버
echo   • 프론트엔드 웹 서버
echo.
echo 서비스를 다시 시작하려면:
echo   scripts\run.bat 실행
echo.

REM 임시 파일 정리 (선택사항)
echo 임시 파일을 정리하시겠습니까? (Y/N)
set /p CLEANUP=선택: 
if /i "!CLEANUP!"=="Y" (
    echo 임시 파일 정리 중...
    if exist logs\*.tmp del /q logs\*.tmp >nul 2>&1
    if exist data\*.lock del /q data\*.lock >nul 2>&1
    echo ✓ 임시 파일 정리 완료
)

echo.
echo [완료] 모든 작업이 완료되었습니다.
timeout /t 3 /nobreak >nul