@echo off
setlocal ENABLEDELAYEDEXPANSION
chcp 65001 >nul 2>&1

REM HD현대미포 Gauss-1 RAG System - Enhanced Runner with Dual Routing
REM Version: 2.2 - One-Click Install/Run + Debugging
REM Date: 2025-01-26

title HD현대미포 Gauss-1 RAG System - Dual Qdrant

echo ============================================================
echo   HD현대미포 Gauss-1 RAG System - 통합 실행기 v2.2
echo   🎯 Dual Qdrant Routing (Personal + Department)
echo ============================================================
echo.

REM 환경 변수 로드
set ROOT=%~dp0
cd /d "%ROOT%"

REM 디버그 모드 체크
set DEBUG_MODE=false
if "%1"=="--debug" set DEBUG_MODE=true
if "%1"=="-d" set DEBUG_MODE=true

REM 설정 파일 체크
if not exist ".env" (
    echo [ERROR] .env 파일이 없습니다. install.ps1을 먼저 실행하세요.
    echo.
    echo 해결 방법:
    echo   1^) PowerShell 관리자 모드로 실행
    echo   2^) .\install.ps1 실행
    echo   3^) 설치 완료 후 다시 시도
    pause
    exit /b 1
)

echo [1/7] 환경 설정 확인...
REM .env에서 기본 스코프 읽기
for /f "tokens=2 delims==" %%a in ('findstr "DEFAULT_QDRANT_SCOPE" .env') do set DEFAULT_SCOPE=%%a
if not defined DEFAULT_SCOPE set DEFAULT_SCOPE=personal
echo    -^> 기본 Qdrant 스코프: !DEFAULT_SCOPE!

REM 1) 가상환경 활성화
echo [2/7] Python 가상환경 확인...
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] 가상환경이 없습니다. install.ps1을 먼저 실행하세요.
    pause
    exit /b 1
)
call venv\Scripts\activate.bat
echo    -^> 가상환경 활성화 완료
echo.

REM 2) 필수 디렉토리 생성
echo [3/7] 필수 디렉토리 생성...
if not exist "storage\qdrant" mkdir "storage\qdrant"
if not exist "logs" mkdir "logs"
if not exist "backend\logs" mkdir "backend\logs"
echo    -^> 디렉토리 준비 완료
echo.

REM 3) Qdrant 서버 시작 (Personal PC - 로컬)
echo [4/7] Personal Qdrant 서버 시작 (127.0.0.1:6333)...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":6333" ^| findstr "LISTENING"') do set QPID=%%p
if not defined QPID (
    if exist "bin\qdrant\qdrant.exe" (
        start "Personal Qdrant Server" /B "bin\qdrant\qdrant.exe" --storage-dir "%ROOT%storage\qdrant"
        echo    -^> Personal Qdrant 시작됨 (로컬 저장소)
    ) else if exist "src\bin\qdrant.exe" (
        start "Personal Qdrant Server" /B "src\bin\qdrant.exe"
        echo    -^> Personal Qdrant 시작됨 (레거시 경로)
    ) else (
        echo    -^> Personal Qdrant 바이너리 없음. install.ps1 실행 권장
    )
    timeout /t 3 /nobreak >nul
) else (
    echo    -^> Personal Qdrant 이미 실행 중 (PID: !QPID!)
)

REM Department Qdrant 연결 테스트
echo    -^> Department Qdrant 연결 테스트 (10.150.104.37:6333)...
ping -n 1 -w 1000 10.150.104.37 >nul 2>&1
if !errorlevel! equ 0 (
    echo    -^> Department Server 연결 가능 ✓
) else (
    echo    -^> Department Server 연결 불가 (Personal만 사용)
)
echo.

REM 4) Ollama LLM 서버 시작
echo [5/7] Ollama LLM 서버 시작...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":11434" ^| findstr "LISTENING"') do set OPID=%%p
if not defined OPID (
    where ollama >nul 2>&1
    if !errorlevel! equ 0 (
        start "Ollama Server" /B ollama serve
        echo    -^> Ollama 시작됨 (시스템 설치)
    ) else if exist "bin\ollama\ollama.exe" (
        start "Ollama Server" /B "bin\ollama\ollama.exe" serve
        echo    -^> Ollama 시작됨 (로컬 바이너리)
    ) else (
        echo    -^> Ollama 미설치. LLM 기능이 제한됩니다.
        echo         설치: https://ollama.ai
    )
    timeout /t 3 /nobreak >nul
) else (
    echo    -^> Ollama 이미 실행 중 (PID: !OPID!)
)
echo.

REM 5) 백엔드 API 서버 시작
echo [6/7] Backend API 서버 시작 (Dual Routing 지원)...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8080" ^| findstr "LISTENING"') do set BPID=%%p
if not defined BPID (
    echo    -^> FastAPI 서버 시작 중 (포트 8080)...
    
    REM 환경 파일 우선순위
    if exist ".env" (
        if "%DEBUG_MODE%"=="true" (
            start "Backend API (Debug)" cmd /k "cd /d "%ROOT%" && call venv\Scripts\activate.bat && cd backend && python -m uvicorn main:app --host 0.0.0.0 --port 8080 --reload --env-file ..\.env --log-level debug"
            echo    -^> Backend API 시작됨 (DEBUG 모드)
        ) else (
            start "Backend API" cmd /c "cd /d "%ROOT%" && call venv\Scripts\activate.bat && cd backend && python -m uvicorn main:app --host 0.0.0.0 --port 8080 --reload --env-file ..\.env"
            echo    -^> Backend API 시작됨 (PRODUCTION 모드)
        )
    ) else if exist ".env.test" (
        start "Backend API" cmd /c "cd /d "%ROOT%" && call venv\Scripts\activate.bat && cd backend && python -m uvicorn main:app --host 0.0.0.0 --port 8080 --reload --env-file ..\.env.test"
        echo    -^> Backend API 시작됨 (.env.test)
    ) else (
        start "Backend API" cmd /c "cd /d "%ROOT%" && call venv\Scripts\activate.bat && cd backend && python -m uvicorn main:app --host 0.0.0.0 --port 8080 --reload"
        echo    -^> Backend API 시작됨 (기본 설정)
    )
    
    timeout /t 5 /nobreak >nul
) else (
    echo    -^> Backend API 이미 실행 중 (PID: !BPID!)
)
echo.

REM 6) 프론트엔드 웹 서버 시작
echo [7/7] Frontend 웹 서버 시작...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8001" ^| findstr "LISTENING"') do set FPID=%%p
if not defined FPID (
    echo    -^> 웹 서버 시작 중 (포트 8001)...
    start "Frontend Server" cmd /c "cd /d "%ROOT%" && call venv\Scripts\activate.bat && cd frontend && python -m http.server 8001"
    timeout /t 2 /nobreak >nul
) else (
    echo    -^> Frontend 이미 실행 중 (PID: !FPID!)
)
echo.

REM GUI 애플리케이션 실행 선택
echo GUI 애플리케이션을 실행하시겠습니까? (Y/N)
set /p RUNGUI=선택: 
if /i "!RUNGUI!"=="Y" (
    echo GUI 애플리케이션 시작 중...
    
    if "%DEBUG_MODE%"=="true" (
        echo [DEBUG] GUI 디버그 모드로 실행...
        start "GUI Application (Debug)" "%ROOT%venv\Scripts\python.exe" "%ROOT%src\HDLLM.py" --debug
        echo    -^> GUI 디버그 모드 실행 (콘솔 출력 표시)
    ) else (
        start "GUI Application" "%ROOT%venv\Scripts\pythonw.exe" "%ROOT%src\HDLLM.py"
        echo    -^> GUI 애플리케이션 실행 (백그라운드)
    )
)

echo.
echo ============================================================
echo   🎉 모든 서비스가 시작되었습니다!
echo ============================================================
echo.
echo 접속 주소:
echo   🌐 웹 인터페이스: http://localhost:8001
echo   🔌 API 서버: http://localhost:8080
echo   📚 API 문서: http://localhost:8080/docs
echo   💊 상태 확인: http://localhost:8080/status
echo.
echo Dual Qdrant 라우팅:
echo   🏠 Personal PC: 127.0.0.1:6333 (로컬)
echo   🏢 Department: 10.150.104.37:6333 (원격)
echo   ⚙️ 현재 기본값: !DEFAULT_SCOPE!
echo.
echo 사용법:
echo   • 웹 인터페이스에서 우상단 버튼으로 범위 선택
echo   • GUI에서 'Qdrant DB 설정' 탭에서 범위 변경
echo   • 이 창을 닫으면 GUI만 남고 웹서비스는 계속 실행
echo.
echo 디버그:
echo   • GUI 오류 확인: run_gui_debug.bat 실행
echo   • 모든 서비스 중지: stop.bat 실행
echo.

REM 브라우저 열기
echo 브라우저를 여시겠습니까? (Y/N)
set /p OPENBROWSER=선택: 
if /i "!OPENBROWSER!"=="Y" (
    start http://localhost:8001
)

echo.
echo [완료] 아무 키나 누르면 종료됩니다...
echo        (서비스들은 백그라운드에서 계속 실행됩니다)
pause >nul

REM 정상 종료
exit /b 0