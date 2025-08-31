@echo off
setlocal ENABLEDELAYEDEXPANSION
chcp 65001 >nul 2>&1

REM GUI 디버그 실행 스크립트
REM GUI 오류 메시지를 콘솔에서 직접 확인

title HD현대미포 Gauss-1 - GUI 디버그 모드

echo ============================================================
echo   HD현대미포 Gauss-1 GUI 디버그 모드
echo   콘솔에서 오류 메시지를 직접 확인할 수 있습니다
echo ============================================================
echo.

set ROOT=%~dp0
cd /d "%ROOT%"

REM 가상환경 체크
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] 가상환경을 찾을 수 없습니다.
    echo install.ps1을 먼저 실행하세요.
    pause
    exit /b 1
)

REM 가상환경 활성화
echo [1] 가상환경 활성화...
call venv\Scripts\activate.bat
echo.

REM Python 환경 정보
echo [2] Python 환경 정보:
python --version
echo 설치된 주요 패키지:
pip list | findstr -i "pyside6 qdrant fastapi"
echo.

REM GUI 애플리케이션 실행 (콘솔 출력 모드)
echo [3] GUI 애플리케이션 시작 중...
echo     ※ 오류 발생 시 이 창에서 메시지를 확인하세요
echo     ※ 창을 닫으려면 Ctrl+C를 누르세요
echo.

REM 디버그 환경 변수 설정
set RAG_DEBUG=true
set RAG_VERBOSE=true
set PYTHONUNBUFFERED=1

REM GUI 실행 (python.exe 사용으로 콘솔 출력 표시)
echo [시작] GUI 디버그 모드 실행...
echo ============================================================
"%ROOT%venv\Scripts\python.exe" "%ROOT%src\HDLLM.py" --debug

echo ============================================================
echo [종료] GUI 애플리케이션이 종료되었습니다.
echo.

if %ERRORLEVEL% neq 0 (
    echo [ERROR] GUI 실행 중 오류가 발생했습니다 (종료 코드: %ERRORLEVEL%)
    echo.
    echo 일반적인 해결 방법:
    echo   1^) 필요한 패키지 재설치: pip install -r requirements.txt
    echo   2^) .env 파일 설정 확인
    echo   3^) Python 버전 확인 (3.8+ 필요)
    echo   4^) PySide6 관련 오류 시: pip install --upgrade PySide6
    echo.
) else (
    echo [SUCCESS] GUI가 정상적으로 종료되었습니다.
)

pause