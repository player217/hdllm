@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

REM ================================================================================================
REM  HD현대미포 Gauss-1 RAG System - Ollama 단독 실행 스크립트 (테스트용)
REM ================================================================================================

title HD Gauss-1 - Ollama Server Test

echo ============================================================
echo   HD Gauss-1 Ollama 서버 단독 실행 (테스트용)
echo ============================================================
echo.

set ROOT=%~dp0..
cd /d "%ROOT%"

REM .env 로드
for /f "usebackq tokens=1,2 delims==" %%A in (".env") do (
    if not "%%A"=="" if not "%%B"=="" set "%%A=%%B"
)

set "OLLAMA_EXE=%ROOT%\%OLLAMA_BIN%"
set "MODELS_DIR=%ROOT%\%OLLAMA_MODELS%"

echo 설정 정보:
echo   실행 파일: %OLLAMA_EXE%
echo   모델 경로: %MODELS_DIR%
echo   포트: 11434 (기본값)
echo.

REM 실행 파일 확인
if not exist "%OLLAMA_EXE%" (
    echo [ERROR] Ollama 실행 파일을 찾을 수 없습니다.
    echo         파일: %OLLAMA_EXE%
    echo.
    echo 해결 방법:
    echo   1. bin\ollama\ 폴더에 ollama.exe가 있는지 확인
    echo   2. 배포 패키지가 완전한지 확인
    echo   3. Ollama 공식 설치 파일 다운로드 및 설치
    echo.
    pause
    exit /b 1
)

REM 모델 디렉토리 생성
if not exist "%MODELS_DIR%" (
    echo 모델 디렉토리 생성: %MODELS_DIR%
    mkdir "%MODELS_DIR%" 2>nul
)

REM 포트 사용 확인
tasklist | find /i "ollama.exe" >nul 2>&1
if not errorlevel 1 (
    echo [WARNING] Ollama 서버가 이미 실행 중입니다.
    echo.
    tasklist | findstr /i "ollama"
    echo.
    echo 계속하시겠습니까? 기존 프로세스와 충돌할 수 있습니다. (Y/N)
    set /p CONTINUE=선택: 
    if /i "!CONTINUE!" NEQ "Y" (
        echo 실행을 취소합니다.
        pause
        exit /b 0
    )
)

REM 환경 변수 설정
set "OLLAMA_MODELS=%MODELS_DIR%"

echo 모델 캐시 확인:
if exist "%MODELS_DIR%\gemma3-4b" (
    echo   ✓ gemma3:4b 모델 캐시 발견
    dir "%MODELS_DIR%\gemma3-4b" /b 2>nul
) else (
    echo   ⚠ gemma3:4b 모델 캐시 없음
    echo     첫 실행 시 자동으로 다운로드됩니다.
    echo     (인터넷 연결 필요 - 약 2.5GB)
)

echo.
echo ============================================================
echo   🚀 Ollama 서버를 시작합니다...
echo ============================================================
echo.
echo 사용 가능한 명령어:
echo   • ollama list          - 설치된 모델 목록
echo   • ollama pull gemma3:4b - 모델 다운로드
echo   • ollama run gemma3:4b  - 모델 실행 테스트
echo.
echo 종료하려면 Ctrl+C를 누르세요.
echo.

REM Ollama 서버 시작 (포그라운드 실행)
"%OLLAMA_EXE%" serve

echo.
echo ============================================================
echo   Ollama 서버가 종료되었습니다.
echo ============================================================
pause