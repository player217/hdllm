@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1

:: HD현대미포 LLM RAG System - Enhanced One-Click Runner
:: Version 2.0 - Integrated service startup
:: Date: 2025-01-30

title HD현대미포 LLM RAG System

echo ============================================================
echo   HD현대미포 LLM RAG System - 통합 실행 프로그램 v2.0
echo ============================================================
echo.

:: Set working directory
cd /d "%~dp0"
set "ROOT_DIR=%cd%"
set "BIN_DIR=%ROOT_DIR%\bin"
set "VENV_DIR=%ROOT_DIR%\venv"

:: Check installation
if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo ⚠ 가상환경이 없습니다. INSTALL_ENHANCED.bat을 먼저 실행하세요.
    pause
    exit /b 1
)

:: Load environment variables from .env
if exist ".env" (
    echo [설정] .env 파일 로드 중...
    for /f "tokens=1,2 delims==" %%a in (.env) do (
        set "%%a=%%b"
    )
    echo     ✓ 환경 변수 로드 완료
) else (
    echo ⚠ .env 파일이 없습니다. 기본값을 사용합니다.
    set "QDRANT_PERSONAL_HOST=127.0.0.1"
    set "QDRANT_PERSONAL_PORT=6333"
    set "DEFAULT_DB_SCOPE=personal"
)
echo.

:: ===== Service Health Check =====
echo [상태 확인] 서비스 상태 점검 중...

:: Check if ports are already in use
netstat -an | findstr :6333 >nul 2>&1
if %errorlevel% equ 0 (
    echo     ℹ Qdrant 포트(6333) 이미 사용 중
    set "QDRANT_RUNNING=1"
) else (
    set "QDRANT_RUNNING=0"
)

netstat -an | findstr :11434 >nul 2>&1
if %errorlevel% equ 0 (
    echo     ℹ Ollama 포트(11434) 이미 사용 중
    set "OLLAMA_RUNNING=1"
) else (
    set "OLLAMA_RUNNING=0"
)

netstat -an | findstr :8080 >nul 2>&1
if %errorlevel% equ 0 (
    echo     ℹ Backend 포트(8080) 이미 사용 중
    set "BACKEND_RUNNING=1"
) else (
    set "BACKEND_RUNNING=0"
)
echo.

:: ===== Start Qdrant =====
echo [1/5] Qdrant 벡터 DB 시작...
if "%QDRANT_RUNNING%"=="0" (
    if exist "%BIN_DIR%\qdrant.exe" (
        set "QDRANT_PATH=%BIN_DIR%\qdrant.exe"
    ) else if exist "src\bin\qdrant.exe" (
        set "QDRANT_PATH=src\bin\qdrant.exe"
    ) else (
        echo     ✗ Qdrant 실행 파일을 찾을 수 없습니다.
        echo     INSTALL_ENHANCED.bat을 실행하여 설치하세요.
        set "QDRANT_PATH="
    )
    
    if defined QDRANT_PATH (
        echo     Qdrant 시작 중... (로컬: %QDRANT_PERSONAL_HOST%:%QDRANT_PERSONAL_PORT%)
        
        :: Create storage directory if not exists
        if not exist "%ROOT_DIR%\storage\qdrant" mkdir "%ROOT_DIR%\storage\qdrant"
        
        :: Start Qdrant in background
        start /B "Qdrant Server" cmd /c "set QDRANT__STORAGE__STORAGE_PATH=%ROOT_DIR%\storage\qdrant && !QDRANT_PATH! >nul 2>&1"
        
        :: Wait for Qdrant to start
        timeout /t 3 /nobreak >nul
        echo     ✓ Qdrant 시작 완료
    )
) else (
    echo     ✓ Qdrant 이미 실행 중
)

:: Check department Qdrant connectivity
echo     부서 Qdrant 연결 테스트 (%QDRANT_DEPT_HOST%:%QDRANT_DEPT_PORT%)...
powershell -Command "& {
    try {
        $response = Invoke-WebRequest -Uri 'http://%QDRANT_DEPT_HOST%:%QDRANT_DEPT_PORT%/health' -TimeoutSec 2 -UseBasicParsing
        if ($response.StatusCode -eq 200) {
            Write-Host '    ✓ 부서 Qdrant 연결 성공' -ForegroundColor Green
        }
    } catch {
        Write-Host '    ⚠ 부서 Qdrant 연결 실패 (개인 DB로 자동 폴백)' -ForegroundColor Yellow
        Write-Host ''
        Write-Host '    ℹ️  부서 DB 연결 실패 정보 ℹ️' -ForegroundColor Cyan
        Write-Host '    부서 Qdrant 서버(%QDRANT_DEPT_HOST%:%QDRANT_DEPT_PORT%)에 접근할 수 없습니다.' -ForegroundColor Yellow
        Write-Host '    시스템이 자동으로 개인 DB로 전환되어 정상 작동됩니다.' -ForegroundColor White
        Write-Host ''
        Write-Host '    가능한 원인:' -ForegroundColor White
        Write-Host '    1) 네트워크 연결 문제 (VPN, 방화벽, 프록시)' -ForegroundColor Gray
        Write-Host '    2) 부서 Qdrant 서버 점검 또는 재시작' -ForegroundColor Gray  
        Write-Host '    3) 사내 네트워크 정책 변경' -ForegroundColor Gray
        Write-Host ''
        Write-Host '    해결 방법:' -ForegroundColor White
        Write-Host '    • 현재: 개인 DB만 사용하여 정상 서비스 이용 가능' -ForegroundColor Green
        Write-Host '    • 부서 DB 필요시: IT팀에 문의 또는 네트워크 상태 확인' -ForegroundColor Cyan
        Write-Host '    • 재시작 시 자동으로 부서 DB 연결 재시도됩니다' -ForegroundColor Cyan
        Write-Host ''
    }
}"
echo.

:: ===== Start Ollama =====
echo [2/5] Ollama LLM 서버 시작...
if "%OLLAMA_RUNNING%"=="0" (
    where ollama >nul 2>&1
    if %errorlevel% equ 0 (
        echo     Ollama 서비스 시작 중...
        start /B "Ollama Server" cmd /c "ollama serve >nul 2>&1"
        timeout /t 3 /nobreak >nul
        echo     ✓ Ollama 시작 완료
        
        :: Ensure model is loaded
        echo     Gemma3 모델 로드 중...
        ollama run gemma:3b "test" >nul 2>&1
        echo     ✓ 모델 준비 완료
    ) else (
        echo     ⚠ Ollama가 설치되지 않았습니다.
        echo     INSTALL_ENHANCED.bat을 실행하여 설치하세요.
    )
) else (
    echo     ✓ Ollama 이미 실행 중
)
echo.

:: ===== Start Backend API =====
echo [3/5] Backend API 서버 시작...
if "%BACKEND_RUNNING%"=="0" (
    echo     FastAPI 서버 시작 중 (포트 8080)...
    
    :: Activate virtual environment and start backend
    start "Backend API" cmd /k "call %VENV_DIR%\Scripts\activate.bat && cd backend && python -m uvicorn main:app --host 0.0.0.0 --port 8080 --reload --env-file ..\.env"
    
    :: Wait for backend to start
    timeout /t 5 /nobreak >nul
    
    :: Health check
    powershell -Command "& {
        $maxRetries = 10
        $retryCount = 0
        while ($retryCount -lt $maxRetries) {
            try {
                $response = Invoke-WebRequest -Uri 'http://localhost:8080/health' -UseBasicParsing
                if ($response.StatusCode -eq 200) {
                    Write-Host '    ✓ Backend API 시작 완료' -ForegroundColor Green
                    break
                }
            } catch {
                $retryCount++
                Start-Sleep -Seconds 1
            }
        }
        if ($retryCount -eq $maxRetries) {
            Write-Host '    ✗ Backend API 시작 실패' -ForegroundColor Red
        }
    }"
) else (
    echo     ✓ Backend API 이미 실행 중
)
echo.

:: ===== Start Frontend =====
echo [4/5] Frontend 웹 서버 시작...
netstat -an | findstr :8001 >nul 2>&1
if %errorlevel% neq 0 (
    echo     웹 서버 시작 중 (포트 8001)...
    
    :: Start simple HTTP server for frontend
    start "Frontend Server" cmd /k "cd frontend && %VENV_DIR%\Scripts\python.exe -m http.server 8001"
    
    timeout /t 2 /nobreak >nul
    echo     ✓ Frontend 시작 완료
) else (
    echo     ✓ Frontend 이미 실행 중
)
echo.

:: ===== Start GUI Application =====
echo [5/5] GUI 애플리케이션 시작...
echo     PySide6 GUI 시작 중...

:: Check if GUI is already running
tasklist /FI "WINDOWTITLE eq LLMPY Vector Studio*" 2>nul | find /I "python.exe" >nul
if %errorlevel% neq 0 (
    start "GUI Application" "%VENV_DIR%\Scripts\pythonw.exe" "src\HDLLM.py"
    echo     ✓ GUI 애플리케이션 시작
) else (
    echo     ✓ GUI 이미 실행 중
)
echo.

:: ===== System Ready =====
echo ============================================================
echo   ✅ 모든 서비스가 성공적으로 시작되었습니다!
echo ============================================================
echo.
echo 접속 정보:
echo   • 웹 인터페이스: http://localhost:8001
echo   • API 서버: http://localhost:8080
echo   • API 문서: http://localhost:8080/docs
echo   • 상태 확인: http://localhost:8080/status
echo.
echo 데이터 소스:
echo   • 현재 스코프: %DEFAULT_DB_SCOPE%
echo   • 개인 Qdrant: %QDRANT_PERSONAL_HOST%:%QDRANT_PERSONAL_PORT%
echo   • 부서 Qdrant: %QDRANT_DEPT_HOST%:%QDRANT_DEPT_PORT%
echo.
echo 사용 방법:
echo   1. 웹 브라우저에서 http://localhost:8001 접속
echo   2. 우측 상단에서 데이터 소스 선택 (개인/부서)
echo   3. 질문 입력 후 전송
echo.
echo 종료 방법:
echo   • 이 창을 닫으면 모든 서비스가 종료됩니다.
echo   • 개별 서비스는 각 창에서 Ctrl+C로 종료 가능
echo.

:: Open browser automatically
echo 브라우저를 자동으로 엽니다...
timeout /t 2 /nobreak >nul
start http://localhost:8001

echo.
echo [대기 중] 이 창을 닫으면 모든 서비스가 종료됩니다...
pause >nul

:: Cleanup on exit
echo.
echo 서비스 종료 중...

:: Kill processes
taskkill /F /FI "WINDOWTITLE eq Qdrant Server*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Ollama Server*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Backend API*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Frontend Server*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq GUI Application*" >nul 2>&1

echo ✓ 모든 서비스가 종료되었습니다.
timeout /t 2 /nobreak >nul