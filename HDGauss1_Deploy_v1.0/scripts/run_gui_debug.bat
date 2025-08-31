@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

REM ================================================================================================
REM  HD현대미포 Gauss-1 RAG System - GUI 디버그 실행 스크립트
REM  에러 확인 및 로그 캡처용
REM ================================================================================================

title HD Gauss-1 GUI Debug Mode

echo ============================================================
echo   HD Gauss-1 GUI 디버그 모드
echo   에러 로그를 캡처하여 문제를 진단합니다
echo ============================================================
echo.

set ROOT=%~dp0..
cd /d "%ROOT%"

REM .env 로드
for /f "usebackq tokens=1,2 delims==" %%A in (".env") do (
    if not "%%A"=="" if not "%%B"=="" set "%%A=%%B"
)

REM Python 경로 설정
set "PYTHON=%ROOT%\%PY_EMBED_ROOT%\python.exe"
set "HF_HOME=%ROOT%\%HF_HOME%"
set "TRANSFORMERS_CACHE=%ROOT%\%TRANSFORMERS_CACHE%"
set "OLLAMA_MODELS=%ROOT%\%OLLAMA_MODELS%"

REM 로그 디렉토리 생성
if not exist logs mkdir logs

echo [INFO] Python 실행 파일: %PYTHON%
echo [INFO] 모델 캐시 경로: %HF_HOME%
echo [INFO] GUI 소스 파일: src\HDLLM.py
echo.

REM Python 실행 파일 확인
if not exist "%PYTHON%" (
    echo [ERROR] Python 실행 파일을 찾을 수 없습니다.
    echo         경로: %PYTHON%
    echo.
    echo 해결 방법:
    echo   1. bin\python311\ 폴더에 임베디드 Python이 설치되었는지 확인
    echo   2. .env 파일의 PY_EMBED_ROOT 경로 확인
    echo   3. install_offline.ps1 스크립트 실행
    echo.
    pause
    exit /b 1
)

REM GUI 소스 파일 확인
if not exist "src\HDLLM.py" (
    echo [ERROR] GUI 소스 파일을 찾을 수 없습니다.
    echo         파일: src\HDLLM.py
    echo.
    pause
    exit /b 1
)

echo [시작] GUI 애플리케이션을 디버그 모드로 실행합니다...
echo        모든 출력과 에러는 로그 파일에 기록됩니다.
echo.
echo 로그 파일:
echo   • stdout: logs\gui_stdout.log
echo   • stderr: logs\gui_stderr.log
echo.

REM GUI 실행 (콘솔 출력과 파일 로깅 동시)
"%PYTHON%" "src\HDLLM.py" 2>&1 | tee logs\gui_debug.log

echo.
echo ============================================================
echo   GUI 애플리케이션이 종료되었습니다.
echo ============================================================
echo.

REM 에러 로그 확인
if exist "logs\gui_debug.log" (
    echo 로그 파일 크기:
    for %%F in ("logs\gui_debug.log") do echo   %%~nF%%~xF: %%~zF bytes
    echo.
    
    REM 에러 키워드 검색
    findstr /i "error exception traceback failed" logs\gui_debug.log >nul 2>&1
    if not errorlevel 1 (
        echo [주의] 로그에서 에러가 발견되었습니다:
        echo.
        findstr /i "error exception traceback failed" logs\gui_debug.log
        echo.
        echo 자세한 내용은 logs\gui_debug.log 파일을 확인하세요.
    ) else (
        echo [정보] 심각한 에러는 발견되지 않았습니다.
    )
) else (
    echo [경고] 로그 파일이 생성되지 않았습니다.
    echo         GUI가 즉시 종료되었을 수 있습니다.
)

echo.
echo 로그 파일을 지금 확인하시겠습니까? (Y/N)
set /p VIEWLOG=선택: 
if /i "!VIEWLOG!"=="Y" (
    if exist "logs\gui_debug.log" (
        echo.
        echo ==================== 로그 내용 (마지막 50줄) ====================
        tail -50 logs\gui_debug.log 2>nul || (
            REM tail이 없는 경우 대안
            powershell "Get-Content logs\gui_debug.log | Select-Object -Last 50"
        )
        echo ================================================================
    )
)

echo.
echo [완료] 디버그 세션이 종료되었습니다.
echo        문제가 지속되면 logs\ 폴더의 파일들을 확인하거나
echo        기술지원팀에 로그 파일을 제공하세요.
echo.
pause