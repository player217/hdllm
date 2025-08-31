@echo off
setlocal ENABLEDELAYEDEXPANSION
chcp 65001 >nul 2>&1

REM HD현대미포 Gauss-1 RAG System - Enhanced Smart Runner
REM Version: 3.0 - Path-Independent & Smart Network Switching
REM Date: 2025-08-31

title HD현대미포 Gauss-1 RAG System - Smart Runner

echo ============================================================
echo   HD현대미포 Gauss-1 RAG System - 스마트 실행기 v3.0
echo ============================================================
echo.

REM 경로 설정 (스크립트 위치 기준으로 루트 디렉터리 자동 감지)
set SCRIPT_PATH=%~dp0
set ROOT=%SCRIPT_PATH:~0,-9%
if "%ROOT:~-1%"=="\" set ROOT=%ROOT:~0,-1%
cd /d "%ROOT%"

echo 🔧 실행 디렉터리: %ROOT%
echo.

REM .env 파일 로드
if exist ".env" (
    echo [INFO] .env 파일에서 환경 변수 로드 중...
    for /f "usebackq tokens=1,2 delims==" %%A in (".env") do (
        set "line=%%A"
        if not "!line:~0,1!"=="#" if not "!line!"=="" (
            set "%%A=%%B"
            echo    - %%A=%%B
        )
    )
    echo.
) else (
    echo [WARNING] .env 파일이 없습니다. 기본값을 사용합니다.
    set QDRANT_MODE=auto
    set REMOTE_QDRANT_HOST=10.150.104.37
    set REMOTE_QDRANT_PORT=6333
    set LOCAL_QDRANT_PORT=6333
    set APP_PORT=8080
    set FRONTEND_PORT=8001
    echo.
)

REM 환경 변수 기본값 설정
if not defined QDRANT_MODE set QDRANT_MODE=auto
if not defined REMOTE_QDRANT_HOST set REMOTE_QDRANT_HOST=10.150.104.37
if not defined REMOTE_QDRANT_PORT set REMOTE_QDRANT_PORT=6333
if not defined LOCAL_QDRANT_PORT set LOCAL_QDRANT_PORT=6333
if not defined APP_PORT set APP_PORT=8080
if not defined FRONTEND_PORT set FRONTEND_PORT=8001

echo [1/6] 가상환경 활성화...
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] 가상환경이 없습니다. 먼저 scripts\install.ps1을 실행하세요.
    echo          또는 INSTALL.bat을 실행하세요.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat
if !errorlevel! neq 0 (
    echo [ERROR] 가상환경 활성화 실패
    pause
    exit /b 1
)
echo    ✅ 가상환경 활성화 완료
echo.

echo [2/6] Qdrant 벡터 DB 스마트 연결...

REM 현재 실행 중인 Qdrant 확인 
set QDRANT_RUNNING=false
set QDRANT_LOCAL=false
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":%LOCAL_QDRANT_PORT%" ^| findstr "LISTENING" 2^>nul') do (
    set QDRANT_RUNNING=true
    set LOCAL_PID=%%p
)

if "%QDRANT_RUNNING%"=="true" (
    echo    ✅ 로컬 Qdrant 이미 실행 중 (PID: !LOCAL_PID!, 포트: %LOCAL_QDRANT_PORT%)
    set QDRANT_LOCAL=true
) else (
    REM Qdrant 연결 모드 결정
    if /i "%QDRANT_MODE%"=="local" (
        echo    🔧 강제 로컬 모드로 설정됨
        call :StartLocalQdrant
    ) else if /i "%QDRANT_MODE%"=="remote" (
        echo    🌐 강제 원격 모드로 설정됨
        call :TestRemoteQdrant
    ) else if /i "%QDRANT_MODE%"=="auto" (
        echo    🤖 자동 모드: 원격 서버 연결 테스트 중...
        call :TestRemoteQdrant
        if !REMOTE_OK! neq 1 (
            echo    ⚡ 원격 연결 실패, 로컬 Qdrant 시작으로 전환
            call :StartLocalQdrant
        )
    )
)

REM 환경 변수 동적 설정
if "%QDRANT_LOCAL%"=="true" (
    set RAG_MAIL_QDRANT_HOST=127.0.0.1
    set RAG_MAIL_QDRANT_PORT=%LOCAL_QDRANT_PORT%
    set RAG_DOC_QDRANT_HOST=127.0.0.1
    set RAG_DOC_QDRANT_PORT=%LOCAL_QDRANT_PORT%
    echo    🏠 로컬 Qdrant 사용: 127.0.0.1:%LOCAL_QDRANT_PORT%
) else (
    set RAG_MAIL_QDRANT_HOST=%REMOTE_QDRANT_HOST%
    set RAG_MAIL_QDRANT_PORT=%REMOTE_QDRANT_PORT%
    set RAG_DOC_QDRANT_HOST=%REMOTE_QDRANT_HOST%
    set RAG_DOC_QDRANT_PORT=%REMOTE_QDRANT_PORT%
    echo    🌐 원격 Qdrant 사용: %REMOTE_QDRANT_HOST%:%REMOTE_QDRANT_PORT%
)
echo.

echo [3/6] Ollama LLM 서비스 확인...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":11434" ^| findstr "LISTENING" 2^>nul') do set OPID=%%p
if not defined OPID (
    where ollama >nul 2>&1
    if !errorlevel! equ 0 (
        echo    🚀 Ollama 서비스 시작 중...
        start "Ollama Server" /MIN ollama serve
        timeout /t 5 /nobreak >nul
        echo    ✅ Ollama 서비스 시작됨
    ) else if exist "bin\ollama\ollama.exe" (
        echo    🚀 포터블 Ollama 서비스 시작 중...
        start "Ollama Server" /MIN "bin\ollama\ollama.exe" serve
        timeout /t 5 /nobreak >nul
        echo    ✅ 포터블 Ollama 서비스 시작됨
    ) else (
        echo    ⚠️  Ollama가 설치되지 않았습니다. LLM 기능이 제한될 수 있습니다.
        echo         설치 방법: https://ollama.ai/download
    )
) else (
    echo    ✅ Ollama 이미 실행 중 (PID: !OPID!)
)
echo.

echo [4/6] Backend API 서버 시작...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":%APP_PORT%" ^| findstr "LISTENING" 2^>nul') do set BPID=%%p
if not defined BPID (
    echo    🚀 FastAPI 서버 시작 중 (포트 %APP_PORT%)...
    
    REM 환경 변수를 임시 배치 파일로 생성
    echo set RAG_MAIL_QDRANT_HOST=!RAG_MAIL_QDRANT_HOST! > temp_env.bat
    echo set RAG_MAIL_QDRANT_PORT=!RAG_MAIL_QDRANT_PORT! >> temp_env.bat
    echo set RAG_DOC_QDRANT_HOST=!RAG_DOC_QDRANT_HOST! >> temp_env.bat
    echo set RAG_DOC_QDRANT_PORT=!RAG_DOC_QDRANT_PORT! >> temp_env.bat
    
    REM Backend 시작
    start "Backend API" cmd /k "call temp_env.bat && cd backend && python -m uvicorn main:app --host 0.0.0.0 --port %APP_PORT% --reload"
    timeout /t 6 /nobreak >nul
    
    REM 임시 파일 삭제
    del temp_env.bat 2>nul
    
    echo    ✅ Backend API 서버 시작됨
) else (
    echo    ✅ Backend API 이미 실행 중 (PID: !BPID!)
)
echo.

echo [5/6] Frontend 웹 서버 시작...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":%FRONTEND_PORT%" ^| findstr "LISTENING" 2^>nul') do set FPID=%%p
if not defined FPID (
    echo    🚀 웹 서버 시작 중 (포트 %FRONTEND_PORT%)...
    start "Frontend Server" /MIN cmd /k "cd frontend && python -m http.server %FRONTEND_PORT%"
    timeout /t 3 /nobreak >nul
    echo    ✅ Frontend 웹 서버 시작됨
) else (
    echo    ✅ Frontend 이미 실행 중 (PID: !FPID!)
)
echo.

echo [6/6] 선택적 GUI 애플리케이션...
if exist "src\HDLLM.py" (
    echo GUI 애플리케이션을 시작하시겠습니까? (Y/N)
    set /p RUNGUI=입력: 
    if /i "!RUNGUI!"=="Y" (
        echo    🚀 GUI 애플리케이션 시작 중...
        start "GUI Application" "%ROOT%\venv\Scripts\pythonw.exe" "%ROOT%\src\HDLLM.py"
        echo    ✅ GUI 애플리케이션 시작됨
    )
) else (
    echo    ⚠️  GUI 애플리케이션 파일(src\HDLLM.py)을 찾을 수 없습니다
)
echo.

echo ============================================================
echo   🎉 모든 서비스가 시작되었습니다!
echo ============================================================
echo.
echo 📊 서비스 상태:
if "%QDRANT_LOCAL%"=="true" (
    echo   🏠 Qdrant: 로컬 (127.0.0.1:%LOCAL_QDRANT_PORT%)
) else (
    echo   🌐 Qdrant: 원격 (%REMOTE_QDRANT_HOST%:%REMOTE_QDRANT_PORT%)
)
echo   ⚡ Backend API: http://localhost:%APP_PORT%
echo   🌐 웹 인터페이스: http://localhost:%FRONTEND_PORT%
echo   📚 API 문서: http://localhost:%APP_PORT%/docs
echo   ❤️  시스템 상태: http://localhost:%APP_PORT%/status
echo.
echo 🔗 접속 링크:
echo   메인 페이지: http://localhost:%FRONTEND_PORT%
echo   관리 페이지: http://localhost:%APP_PORT%/docs
echo.
echo 💡 사용법:
echo   - 이 창을 닫으면 GUI는 종료되지만 서비스는 계속 실행됩니다
echo   - 모든 서비스 종료: scripts\stop.bat 실행
echo   - 문제 발생 시: logs\ 폴더의 로그 파일을 확인하세요
echo.

REM 브라우저 자동 열기
echo 브라우저를 자동으로 여시겠습니까? (Y/N)
set /p OPENBROWSER=입력: 
if /i "!OPENBROWSER!"=="Y" (
    echo    🌐 브라우저 열기...
    start http://localhost:%FRONTEND_PORT%
)

echo.
echo [실행 완료] 아무 키나 눌러서 이 창을 닫을 수 있습니다...
echo              (서비스는 백그라운드에서 계속 실행됩니다)
pause >nul
exit /b 0

REM ======================== 함수 정의 ========================

:TestRemoteQdrant
echo    🔍 원격 Qdrant 연결 테스트: %REMOTE_QDRANT_HOST%:%REMOTE_QDRANT_PORT%
powershell -Command "try { $tcpClient = New-Object System.Net.Sockets.TcpClient; $connect = $tcpClient.BeginConnect('%REMOTE_QDRANT_HOST%', %REMOTE_QDRANT_PORT%, $null, $null); $wait = $connect.AsyncWaitHandle.WaitOne(3000, $false); if ($wait) { $tcpClient.EndConnect($connect); $tcpClient.Close(); exit 0 } else { $tcpClient.Close(); exit 1 } } catch { exit 1 }" >nul 2>&1
if !errorlevel! equ 0 (
    echo    ✅ 원격 Qdrant 연결 성공
    set REMOTE_OK=1
) else (
    echo    ❌ 원격 Qdrant 연결 실패
    set REMOTE_OK=0
)
goto :eof

:StartLocalQdrant
echo    🚀 로컬 Qdrant 시작 중...
set QDRANT_STARTED=false

REM 다양한 Qdrant 경로 확인
if exist "bin\qdrant\qdrant.exe" (
    if not exist "data\qdrant" mkdir "data\qdrant"
    start "Qdrant Server" /MIN "bin\qdrant\qdrant.exe" --storage-dir "%ROOT%\data\qdrant"
    echo    ✅ 포터블 Qdrant 시작됨 (저장 위치: data\qdrant)
    set QDRANT_STARTED=true
    set QDRANT_LOCAL=true
) else if exist "src\bin\qdrant.exe" (
    start "Qdrant Server" /MIN "src\bin\qdrant.exe"
    echo    ✅ 기존 Qdrant 시작됨 (레거시 경로)
    set QDRANT_STARTED=true  
    set QDRANT_LOCAL=true
) else (
    echo    ❌ 로컬 Qdrant 실행 파일을 찾을 수 없습니다
    echo       다음 중 하나를 수행하세요:
    echo       1. scripts\install.ps1 실행 (자동 다운로드)
    echo       2. bin\qdrant\qdrant.exe 수동 배치
    echo       3. 원격 Qdrant 서버 사용
)

REM Qdrant 시작 대기
if "%QDRANT_STARTED%"=="true" (
    echo    ⏳ Qdrant 초기화 대기 중...
    timeout /t 5 /nobreak >nul
    
    REM 포트 확인
    for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":%LOCAL_QDRANT_PORT%" ^| findstr "LISTENING" 2^>nul') do (
        echo    ✅ Qdrant 정상 시작 확인됨 (PID: %%p)
    )
)
goto :eof