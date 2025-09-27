@echo off
setlocal
chcp 65001 >nul

:: -------------------------------------------------
:: 설정
:: -------------------------------------------------
:: 1. 프로젝트 폴더 (tray_launcher.py가 있는 위치)
set "PROJECT_DIR=C:\Users\h000000\Documents\LLM_UI_APP"

:: 2. 실행할 파이썬 스크립트
set "SCRIPT_NAME=tray_launcher.py"

:: 3. 프로젝트 전용 venv 파이썬 경로
set "VENV_PYTHON=%PROJECT_DIR%\venv\Scripts\pythonw.exe"


:: -------------------------------------------------
:: 실행 코드
:: -------------------------------------------------
if not exist "%VENV_PYTHON%" (
    echo [FATAL] 프로젝트 venv의 pythonw.exe를 찾을 수 없습니다.
    echo 먼저 INSTALL.bat을 실행해서 venv를 생성하세요.
    pause
    exit /b
)

echo ======================================================
echo  Starting LLMPY Vector Studio Tray Launcher...
echo ======================================================
echo Using interpreter: %VENV_PYTHON%
echo Script: %PROJECT_DIR%\%SCRIPT_NAME%
echo ------------------------------------------------------

:: 콘솔창 닫고 백그라운드로 실행
start "TrayLauncher" "%VENV_PYTHON%" "%PROJECT_DIR%\%SCRIPT_NAME%"

endlocal
exit
