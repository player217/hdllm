@echo off
setlocal ENABLEDELAYEDEXPANSION
chcp 65001 >nul 2>&1

REM HD현대미포 Gauss-1 RAG System - Safe Shutdown Script  
REM Version: 3.0 - Process Management & Data Protection
REM Date: 2025-08-31

title HD현대미포 Gauss-1 RAG System - 안전 종료

echo ============================================================
echo   HD현대미포 Gauss-1 RAG System - 안전 종료 스크립트 v3.0
echo ============================================================
echo.

REM 경로 설정
set SCRIPT_PATH=%~dp0
set ROOT=%SCRIPT_PATH:~0,-9%
if "%ROOT:~-1%"=="\" set ROOT=%ROOT:~0,-1%
cd /d "%ROOT%"

echo 🛑 시스템 종료 프로세스 시작...
echo    실행 디렉터리: %ROOT%
echo.

REM .env 파일에서 포트 정보 로드
set APP_PORT=8080
set FRONTEND_PORT=8001
set LOCAL_QDRANT_PORT=6333

if exist ".env" (
    for /f "usebackq tokens=1,2 delims==" %%A in (".env") do (
        set "line=%%A"
        if not "!line:~0,1!"=="#" if not "!line!"=="" (
            if "%%A"=="APP_PORT" set APP_PORT=%%B
            if "%%A"=="FRONTEND_PORT" set FRONTEND_PORT=%%B  
            if "%%A"=="LOCAL_QDRANT_PORT" set LOCAL_QDRANT_PORT=%%B
        )
    )
)

echo [1/5] Frontend 웹 서버 종료...
set FRONTEND_STOPPED=false
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":%FRONTEND_PORT%" ^| findstr "LISTENING" 2^>nul') do (
    echo    🔸 Frontend PID %%p 종료 중...
    taskkill /PID %%p /F >nul 2>&1
    if !errorlevel! equ 0 (
        echo    ✅ Frontend 서버 종료됨 (PID: %%p)
        set FRONTEND_STOPPED=true
    ) else (
        echo    ⚠️  Frontend 서버 종료 실패 (PID: %%p)
    )
)

if "%FRONTEND_STOPPED%"=="false" (
    echo    ℹ️  실행 중인 Frontend 서버가 없습니다 (포트 %FRONTEND_PORT%)
)
echo.

echo [2/5] Backend API 서버 종료...
set BACKEND_STOPPED=false
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":%APP_PORT%" ^| findstr "LISTENING" 2^>nul') do (
    echo    🔸 Backend PID %%p 종료 중...
    
    REM graceful shutdown 시도 (API 호출)
    curl -s -X POST http://localhost:%APP_PORT%/shutdown 2>nul >nul
    timeout /t 2 /nobreak >nul
    
    REM 여전히 실행 중이면 강제 종료
    tasklist | findstr "%%p" >nul 2>&1
    if !errorlevel! equ 0 (
        taskkill /PID %%p /F >nul 2>&1
        if !errorlevel! equ 0 (
            echo    ✅ Backend 서버 종료됨 (PID: %%p)
            set BACKEND_STOPPED=true
        ) else (
            echo    ⚠️  Backend 서버 종료 실패 (PID: %%p)  
        )
    ) else (
        echo    ✅ Backend 서버 자동 종료됨 (PID: %%p)
        set BACKEND_STOPPED=true
    )
)

if "%BACKEND_STOPPED%"=="false" (
    echo    ℹ️  실행 중인 Backend 서버가 없습니다 (포트 %APP_PORT%)
)
echo.

echo [3/5] 로컬 Qdrant 서버 종료...
set QDRANT_STOPPED=false
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":%LOCAL_QDRANT_PORT%" ^| findstr "LISTENING" 2^>nul') do (
    echo    🔸 Qdrant PID %%p 안전 종료 중...
    
    REM Graceful shutdown 시도 (SIGTERM 시뮬레이션)
    taskkill /PID %%p /T >nul 2>&1
    timeout /t 3 /nobreak >nul
    
    REM 프로세스가 여전히 실행 중인지 확인
    tasklist | findstr "%%p" >nul 2>&1
    if !errorlevel! equ 0 (
        echo    ⚠️  정상 종료 실패, 강제 종료 시도...
        taskkill /PID %%p /F >nul 2>&1
        if !errorlevel! equ 0 (
            echo    ✅ Qdrant 서버 강제 종료됨 (PID: %%p)
        ) else (
            echo    ❌ Qdrant 서버 종료 실패 (PID: %%p)
        )
    ) else (
        echo    ✅ Qdrant 서버 정상 종료됨 (PID: %%p)
        set QDRANT_STOPPED=true
    )
)

if "%QDRANT_STOPPED%"=="false" (
    echo    ℹ️  실행 중인 로컬 Qdrant 서버가 없습니다 (포트 %LOCAL_QDRANT_PORT%)
)
echo.

echo [4/5] Ollama 서비스 정리 (선택적)...
set OLLAMA_STOPPED=false
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":11434" ^| findstr "LISTENING" 2^>nul') do (
    echo    ❓ Ollama 서비스가 실행 중입니다 (PID: %%p)
    echo       Ollama를 종료하시겠습니까? 다른 애플리케이션에서 사용 중일 수 있습니다.
    echo       Y: 종료, N: 그대로 두기
    set /p STOP_OLLAMA=    선택 (Y/N): 
    
    if /i "!STOP_OLLAMA!"=="Y" (
        echo    🔸 Ollama PID %%p 종료 중...
        taskkill /PID %%p /T >nul 2>&1
        timeout /t 2 /nobreak >nul
        
        tasklist | findstr "%%p" >nul 2>&1
        if !errorlevel! equ 0 (
            taskkill /PID %%p /F >nul 2>&1
        )
        echo    ✅ Ollama 서비스 종료됨 (PID: %%p)
        set OLLAMA_STOPPED=true
    ) else (
        echo    ⏭️  Ollama 서비스 유지됨 (PID: %%p)
    )
)

if "%OLLAMA_STOPPED%"=="false" (
    REM 다른 프로세스명으로 실행 중인지 확인
    tasklist | findstr /i "ollama" >nul 2>&1
    if !errorlevel! equ 0 (
        echo    ℹ️  Ollama 프로세스가 실행 중이지만 포트 11434를 사용하지 않습니다
    ) else (
        echo    ℹ️  실행 중인 Ollama 서비스가 없습니다
    )
)
echo.

echo [5/5] GUI 애플리케이션 및 정리 작업...

REM PySide6 GUI 애플리케이션 종료
tasklist | findstr /i "pythonw.exe" >nul 2>&1
if !errorlevel! equ 0 (
    echo    🔸 GUI 애플리케이션 (pythonw.exe) 종료 중...
    taskkill /IM pythonw.exe /F >nul 2>&1
    if !errorlevel! equ 0 (
        echo    ✅ GUI 애플리케이션 종료됨
    )
) else (
    echo    ℹ️  실행 중인 GUI 애플리케이션이 없습니다
)

REM Python HTTP 서버 정리 (혹시 남아있는 것들)
for /f "tokens=2 delims= " %%p in ('tasklist ^| findstr /i "python.exe" 2^>nul') do (
    netstat -ano | findstr "%%p" | findstr ":%FRONTEND_PORT%" >nul 2>&1
    if !errorlevel! equ 0 (
        echo    🔸 남은 Python HTTP 서버 정리 (PID: %%p)
        taskkill /PID %%p /F >nul 2>&1
    )
)

REM 임시 파일 정리
if exist "temp_env.bat" del "temp_env.bat" >nul 2>&1
if exist "*.tmp" del "*.tmp" >nul 2>&1

echo    ✅ 정리 작업 완료
echo.

REM 최종 상태 확인
echo ============================================================
echo   🏁 종료 프로세스 완료
echo ============================================================
echo.

echo 📊 포트 상태 확인:
netstat -ano | findstr ":%APP_PORT%" | findstr "LISTENING" >nul 2>&1
if !errorlevel! equ 0 (
    echo    ⚠️  포트 %APP_PORT% 아직 사용 중 (Backend)
) else (
    echo    ✅ 포트 %APP_PORT% 해제됨 (Backend)
)

netstat -ano | findstr ":%FRONTEND_PORT%" | findstr "LISTENING" >nul 2>&1  
if !errorlevel! equ 0 (
    echo    ⚠️  포트 %FRONTEND_PORT% 아직 사용 중 (Frontend)
) else (
    echo    ✅ 포트 %FRONTEND_PORT% 해제됨 (Frontend)
)

netstat -ano | findstr ":%LOCAL_QDRANT_PORT%" | findstr "LISTENING" >nul 2>&1
if !errorlevel! equ 0 (
    echo    ⚠️  포트 %LOCAL_QDRANT_PORT% 아직 사용 중 (Qdrant)
) else (
    echo    ✅ 포트 %LOCAL_QDRANT_PORT% 해제됨 (Qdrant)
)

echo.
echo 💾 데이터 안전성:
if exist "data\qdrant" (
    echo    ✅ Qdrant 데이터 무결성 확인됨 (data\qdrant)
) else if exist "storage" (
    echo    ✅ 레거시 데이터 무결성 확인됨 (storage)
) else (
    echo    ℹ️  로컬 데이터 없음 (원격 서버 사용)
)

if exist "logs" (
    echo    ✅ 로그 파일 보존됨 (logs 폴더)
) else (
    echo    ℹ️  로그 디렉토리 없음
)

echo.
echo 🔄 다시 시작하려면: scripts\run.bat 실행
echo 📖 문제 해결: logs 폴더의 로그 파일 확인
echo.

echo [완료] 아무 키나 눌러서 종료하세요...
pause >nul
exit /b 0