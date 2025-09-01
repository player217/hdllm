@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

REM ================================================================================================
REM  HD현대미포 Gauss-1 RAG System - Qdrant 단독 실행 스크립트 (테스트용)
REM ================================================================================================

title HD Gauss-1 - Qdrant Server Test

echo ============================================================
echo   HD Gauss-1 Qdrant 서버 단독 실행 (테스트용)
echo ============================================================
echo.

set ROOT=%~dp0..
cd /d "%ROOT%"

REM .env 로드
for /f "usebackq tokens=1,2 delims==" %%A in (".env") do (
    if not "%%A"=="" if not "%%B"=="" set "%%A=%%B"
)

set "QDRANT_EXE=%ROOT%\%QDRANT_BIN%"
set "QDRANT_CONFIG=%ROOT%\bin\qdrant\qdrant.yaml"
set "STORAGE_DIR=%ROOT%\data\qdrant"

echo 설정 정보:
echo   실행 파일: %QDRANT_EXE%
echo   설정 파일: %QDRANT_CONFIG%
echo   저장 경로: %STORAGE_DIR%
echo   포트: 6333 (기본값)
echo.

REM 실행 파일 확인
if not exist "%QDRANT_EXE%" (
    echo [ERROR] Qdrant 실행 파일을 찾을 수 없습니다.
    echo         파일: %QDRANT_EXE%
    echo.
    echo 해결 방법:
    echo   1. bin\qdrant\ 폴더에 qdrant.exe가 있는지 확인
    echo   2. 배포 패키지가 완전한지 확인
    echo   3. install_offline.ps1 스크립트 실행
    echo.
    pause
    exit /b 1
)

REM 설정 파일 확인
if not exist "%QDRANT_CONFIG%" (
    echo [WARNING] Qdrant 설정 파일을 찾을 수 없습니다.
    echo           기본 설정으로 실행됩니다.
    echo           파일: %QDRANT_CONFIG%
    echo.
    set CONFIG_ARG=
) else (
    set CONFIG_ARG=--config-path "%QDRANT_CONFIG%"
)

REM 저장 디렉토리 생성
if not exist "%STORAGE_DIR%" (
    echo 저장 디렉토리 생성: %STORAGE_DIR%
    mkdir "%STORAGE_DIR%" 2>nul
)

REM 포트 사용 확인
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /r ":6333 .*LISTENING" 2^>nul') do (
    echo [WARNING] 포트 6333이 이미 사용 중입니다. (PID: %%p)
    echo.
    tasklist | findstr "%%p"
    echo.
    echo 계속하시겠습니까? 기존 프로세스와 충돌할 수 있습니다. (Y/N)
    set /p CONTINUE=선택: 
    if /i "!CONTINUE!" NEQ "Y" (
        echo 실행을 취소합니다.
        pause
        exit /b 0
    )
)

echo.
echo ============================================================
echo   🚀 Qdrant 서버를 시작합니다...
echo ============================================================
echo.
echo 종료하려면 Ctrl+C를 누르세요.
echo.

REM Qdrant 서버 시작 (포그라운드 실행)
"%QDRANT_EXE%" %CONFIG_ARG% --storage-dir "%STORAGE_DIR%"

echo.
echo ============================================================
echo   Qdrant 서버가 종료되었습니다.
echo ============================================================
pause