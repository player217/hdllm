@echo off
REM Collection Creation Batch Script for HD현대미포 Gauss-1 RAG System
REM Author: Claude Code
REM Date: 2025-01-26

echo.
echo ========================================
echo  HD현대미포 Gauss-1 컬렉션 생성 스크립트
echo ========================================
echo.

REM 현재 디렉토리를 스크립트가 있는 디렉토리로 변경
cd /d "%~dp0"
cd ..

REM 가상환경 활성화
if exist "venv\Scripts\activate.bat" (
    echo [INFO] 가상환경 활성화 중...
    call venv\Scripts\activate.bat
) else (
    echo [WARNING] 가상환경을 찾을 수 없습니다. 시스템 Python을 사용합니다.
)

REM Python 스크립트 실행
echo [INFO] 컬렉션 생성 시작...
echo.

python scripts\create_collections.py %*

REM 종료 코드 저장
set EXIT_CODE=%ERRORLEVEL%

echo.
echo ========================================
if %EXIT_CODE% == 0 (
    echo  ✅ 생성 완료 - 모든 컬렉션 생성 성공
) else if %EXIT_CODE% == 1 (
    echo  ❌ 생성 실패 - 시스템 설정 확인 필요
) else if %EXIT_CODE% == 2 (
    echo  ⚠️  일부 생성 실패 - 로그 확인 필요
) else (
    echo  ❓ 알 수 없는 상태 코드: %EXIT_CODE%
)
echo ========================================
echo.

REM 대화형 모드에서는 키 입력 대기
if "%1" == "" (
    echo 아무 키나 누르면 종료합니다...
    pause > nul
)

exit /b %EXIT_CODE%