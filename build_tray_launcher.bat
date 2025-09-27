@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

:: PYTHONPATH 초기화
set PYTHONPATH=

title TT - Tray Launcher 컴파일

cd /d "%~dp0"
set PROJECT_ROOT=%~dp0

echo ======================================================
echo  TT - Tray Launcher 컴파일 스크립트
echo ======================================================
echo.

:: --- 1. 가상환경 확인 ---
echo [1/6] 가상환경 확인 중...
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] 가상환경을 찾을 수 없습니다.
    echo         먼저 INSTALL.bat를 실행하여 환경을 설정하세요.
    goto :error
)
echo   ✓ 가상환경 확인 완료

:: --- 2. 가상환경 활성화 ---
echo [2/6] 가상환경 활성화 중...
call .\venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo [ERROR] 가상환경 활성화 실패
    goto :error
)
echo   ✓ 가상환경 활성화 완료

:: --- 3. 필수 파일 확인 ---
echo [3/6] 필수 파일 확인 중...
set MISSING_FILES=0

if not exist "tray_launcher.py" (
    echo   [ERROR] tray_launcher.py 파일을 찾을 수 없습니다.
    set MISSING_FILES=1
)

if not exist "tray_launcher.spec" (
    echo   [ERROR] tray_launcher.spec 파일을 찾을 수 없습니다.
    set MISSING_FILES=1
)

if not exist "assets\tray_icon.ico" (
    echo   [WARNING] assets\tray_icon.ico 파일을 찾을 수 없습니다. 기본 아이콘이 사용됩니다.
)

if not exist "assets\app_icon.ico" (
    echo   [WARNING] assets\app_icon.ico 파일을 찾을 수 없습니다. 기본 아이콘이 사용됩니다.
)

if %MISSING_FILES% equ 1 (
    echo [ERROR] 필수 파일이 누락되었습니다.
    goto :error
)
echo   ✓ 필수 파일 확인 완료

:: --- 4. 이전 빌드 정리 ---
echo [4/6] 이전 빌드 정리 중...
if exist "build" (
    echo   이전 build 폴더 삭제 중...
    rmdir /s /q "build" >nul 2>&1
)
if exist "dist" (
    echo   이전 dist 폴더 삭제 중...
    rmdir /s /q "dist" >nul 2>&1
)
echo   ✓ 빌드 정리 완료

:: --- 5. PyInstaller 실행 ---
echo [5/6] PyInstaller로 컴파일 중...
echo   이 작업은 몇 분 정도 소요됩니다. 잠시만 기다려주세요...
echo.

pyinstaller tray_launcher.spec --clean --noconfirm

if %errorlevel% neq 0 (
    echo [ERROR] 컴파일 실패!
    echo         오류 메시지를 확인하고 문제를 해결하세요.
    goto :error
)

:: --- 6. 결과 확인 ---
echo [6/6] 컴파일 결과 확인 중...

if exist "dist\tray_launcher.exe" (
    echo   ✓ 컴파일 성공!
    echo.
    echo ======================================================
    echo  컴파일 완료!
    echo ======================================================
    echo.
    echo 생성된 파일:
    echo   - dist\tray_launcher.exe
    echo.
    
    :: 파일 크기 확인
    for %%A in ("dist\tray_launcher.exe") do (
        set SIZE=%%~zA
    )
    echo 파일 크기: !SIZE! bytes
    echo.
    
    echo 다음 단계:
    echo 1. dist\tray_launcher.exe 실행하여 테스트
    echo 2. 정상 동작 확인
    echo 3. 필요시 프로젝트 루트로 파일 복사
    echo.
    
    :: 실행 가능 여부 테스트 제안
    echo 테스트를 위해 tray_launcher.exe를 실행하시겠습니까? (Y/N)
    set /p CHOICE="선택: "
    if /i "%CHOICE%"=="Y" (
        echo.
        echo 테스트 실행 중... (Ctrl+C로 중단 가능)
        start "" "dist\tray_launcher.exe"
        timeout /t 3 >nul
        echo 테스트가 시작되었습니다. 시스템 트레이를 확인하세요.
    )
) else (
    echo [ERROR] dist\tray_launcher.exe 파일이 생성되지 않았습니다.
    echo         컴파일 중 오류가 발생했을 가능성이 있습니다.
    goto :error
)

goto :end

:error
echo.
echo ======================================================
echo  컴파일 실패!
echo ======================================================
echo.
echo 문제 해결 방법:
echo 1. INSTALL.bat가 정상적으로 완료되었는지 확인
echo 2. 가상환경이 올바르게 설정되었는지 확인
echo 3. 필수 파일들이 모두 존재하는지 확인
echo 4. 바이러스 백신이 컴파일을 차단하지 않는지 확인
echo.

:end
echo.
pause