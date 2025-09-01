@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

REM ================================================================================================
REM  HD현대미포 Gauss-1 RAG System - 완전 독립 실행형 배포판 v1.0
REM  Docker 불가 PC용 - 모든 바이너리/모델 포함 오프라인 패키지
REM ================================================================================================

title HD현대미포 Gauss-1 RAG System - Standalone v1.0

echo ============================================================
echo   HD현대미포 Gauss-1 RAG System v1.0
echo   🚀 완전 독립 실행형 (Docker 불필요)
echo ============================================================
echo.

REM ── 루트 디렉토리 기준 설정 ───────────────────────────────
set ROOT=%~dp0..
cd /d "%ROOT%"

REM 필수 파일 존재 확인
if not exist ".env" (
    echo [ERROR] .env 파일이 없습니다. 배포 패키지가 불완전합니다.
    pause
    exit /b 1
)

REM ── .env 로드 ───────────────────────────────────────────
for /f "usebackq tokens=1,2 delims==" %%A in (".env") do (
    if not "%%A"=="" if not "%%B"=="" set "%%A=%%B"
)

REM ── PATH/환경 구성 (임베디드 파이썬 + 모델 캐시) ────────
set "PYTHON=%ROOT%\%PY_EMBED_ROOT%\python.exe"
set "PYTHONW=%ROOT%\%PY_EMBED_ROOT%\pythonw.exe"
set "HF_HOME=%ROOT%\%HF_HOME%"
set "TRANSFORMERS_CACHE=%ROOT%\%TRANSFORMERS_CACHE%"
set "OLLAMA_MODELS=%ROOT%\%OLLAMA_MODELS%"

REM 임베디드 Python 경로를 PATH에 추가
set "PATH=%ROOT%\%PY_EMBED_ROOT%;%PATH%"

echo [1/5] 환경 설정 완료
echo    Python: %PYTHON%
echo    Models: %OLLAMA_MODELS%
echo    Cache:  %HF_HOME%
echo.

REM ── Qdrant 실시간 포트 사용 여부 확인 ───────────────────
echo [2/5] Qdrant 벡터 DB 시작...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /r ":6333 .*LISTENING" 2^>nul') do set "QPROC=%%p"
if not defined QPROC (
    if exist "%ROOT%\%QDRANT_BIN%" (
        echo    → Qdrant 시작 중 (포트 6333)...
        start "Qdrant Server" /min "%ROOT%\%QDRANT_BIN%" --config-path "%ROOT%\bin\qdrant\qdrant.yaml"
        timeout /t 3 /nobreak >nul
        echo    ✓ Qdrant 서버 시작됨
    ) else (
        echo    ✗ Qdrant 바이너리 없음: %ROOT%\%QDRANT_BIN%
        echo    → 패키지가 불완전하거나 손상되었습니다.
    )
) else (
    echo    → Qdrant 이미 실행 중 (PID: %QPROC%)
)
echo.

REM ── Ollama 실행 확인 (models 경로 지정) ─────────────────
echo [3/5] Ollama LLM 서버 시작...
tasklist | find /i "ollama.exe" >nul 2>&1
if errorlevel 1 (
    if exist "%ROOT%\%OLLAMA_BIN%" (
        echo    → Ollama 시작 중 (포트 11434)...
        start "Ollama Server" /min cmd /c "set OLLAMA_MODELS=%OLLAMA_MODELS% && "%ROOT%\%OLLAMA_BIN%" serve"
        timeout /t 3 /nobreak >nul
        echo    ✓ Ollama 서버 시작됨
    ) else (
        echo    ✗ Ollama 바이너리 없음: %ROOT%\%OLLAMA_BIN%
        echo    → 패키지가 불완전하거나 손상되었습니다.
    )
) else (
    echo    → Ollama 이미 실행 중
)
echo.

REM ── Backend (Uvicorn) ───────────────────────────────────
echo [4/5] Backend API 서버 시작...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /r ":%APP_PORT% .*LISTENING" 2^>nul') do set "BPROC=%%p"
if not defined BPROC (
    if exist "%PYTHON%" (
        echo    → FastAPI 서버 시작 중 (포트 %APP_PORT%)...
        start "Backend API" /min "%PYTHON%" -m uvicorn backend.main:app --host 0.0.0.0 --port %APP_PORT% --env-file .env
        timeout /t 5 /nobreak >nul
        echo    ✓ Backend API 서버 시작됨
    ) else (
        echo    ✗ Python 실행 파일 없음: %PYTHON%
        echo    → 임베디드 Python이 설치되지 않았습니다.
        pause
        exit /b 1
    )
) else (
    echo    → Backend API 이미 실행 중 (PID: %BPROC%)
)
echo.

REM ── GUI (정상 운영은 pythonw로 무소음) ──────────────────
echo [5/5] GUI 애플리케이션 시작...
if exist "%PYTHONW%" (
    if exist "src\HDLLM.py" (
        echo    → GUI 애플리케이션 시작 중...
        start "HD Gauss-1 GUI" "%PYTHONW%" "src\HDLLM.py"
        timeout /t 2 /nobreak >nul
        echo    ✓ GUI 애플리케이션 시작됨
    ) else (
        echo    ✗ GUI 소스 파일 없음: src\HDLLM.py
        echo    → 패키지가 불완전합니다.
    )
) else (
    echo    ✗ pythonw.exe 없음: %PYTHONW%
    echo    → 임베디드 Python이 설치되지 않았습니다.
)
echo.

echo ============================================================
echo   🎉 HD현대미포 Gauss-1 RAG System 시작 완료!
echo ============================================================
echo.
echo 📋 시스템 상태:
echo   🌐 웹 인터페이스: http://localhost:8001 (수동 시작 필요)
echo   🔌 API 서버: http://localhost:%APP_PORT%
echo   📚 API 문서: http://localhost:%APP_PORT%/docs
echo   💊 상태 확인: http://localhost:%APP_PORT%/status
echo.
echo 🔄 듀얼 Qdrant 라우팅:
echo   🏠 Personal: %QDRANT_PERSONAL_HOST%:%QDRANT_PERSONAL_PORT% (로컬)
echo   🏢 Department: %QDRANT_DEPT_HOST%:%QDRANT_DEPT_PORT% (원격)
echo   ⚙️ 기본값: %DEFAULT_DB_SCOPE%
echo.
echo 🛠️ 관리 도구:
echo   • 디버그 실행: scripts\run_gui_debug.bat
echo   • 서비스 중지: scripts\stop.bat
echo   • 시스템 점검: scripts\self_check.ps1
echo   • 단독 테스트: scripts\run_qdrant.bat, scripts\run_ollama.bat
echo.
echo 📖 도움말:
echo   • README_DEPLOY.md 참조
echo   • 문제 발생 시 logs\ 폴더 확인
echo.

REM 프론트엔드 수동 시작 안내
echo 웹 인터페이스를 시작하시겠습니까? (Y/N)
set /p STARTFRONTEND=선택: 
if /i "!STARTFRONTEND!"=="Y" (
    if exist "frontend\index.html" (
        echo 프론트엔드 서버 시작 중...
        start "Frontend Server" /min "%PYTHON%" -m http.server 8001 -d frontend
        timeout /t 2 >nul
        echo ✓ 웹 서버 시작됨: http://localhost:8001
    ) else (
        echo ✗ 프론트엔드 파일 없음
    )
)

echo.
echo [완료] 모든 서비스가 백그라운드에서 실행 중입니다.
echo        이 창을 닫아도 서비스는 계속 동작합니다.
echo        종료하려면 scripts\stop.bat을 실행하세요.
echo.
pause
exit /b 0