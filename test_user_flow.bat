@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo ======================================================
echo  TT 애플리케이션 - 전체 사용자 플로우 테스트
echo ======================================================
echo.
echo 이 테스트는 사용자가 처음 설치부터 시작하여
echo 애플리케이션을 사용하는 전체 과정을 시뮬레이션합니다.
echo.
pause

cd /d "%~dp0"
set "PROJECT_ROOT=%~dp0"

echo.
echo ======================================================
echo  STEP 1: 설치 프로세스 시뮬레이션
echo ======================================================
echo.
echo [시나리오] 사용자가 처음 INSTALL.bat을 실행합니다.
echo.

:: 1. 시작 프로그램 확인
echo [1-1] 시작 프로그램 등록 확인...
set "STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
if exist "!STARTUP_FOLDER!\TT Launcher.lnk" (
    echo     ✅ 시작 프로그램에 등록됨
    
    :: 바로가기 속성 확인
    powershell -Command "$sh = New-Object -ComObject WScript.Shell; $sc = $sh.CreateShortcut('!STARTUP_FOLDER!\TT Launcher.lnk'); Write-Host '     - 대상:' $sc.TargetPath"
) else (
    echo     ❌ 시작 프로그램에 등록되지 않음
    echo     [재시도] VBScript로 등록 시도...
    
    :: VBScript 파일 생성
    echo Set WshShell = CreateObject^("WScript.Shell"^) > "%TEMP%\fix_shortcut.vbs"
    echo Set Shortcut = WshShell.CreateShortcut^("!STARTUP_FOLDER!\TT Launcher.lnk"^) >> "%TEMP%\fix_shortcut.vbs"
    echo Shortcut.TargetPath = "!PROJECT_ROOT!dist\tray_launcher.exe" >> "%TEMP%\fix_shortcut.vbs"
    echo Shortcut.WorkingDirectory = "!PROJECT_ROOT!" >> "%TEMP%\fix_shortcut.vbs"
    echo Shortcut.IconLocation = "!PROJECT_ROOT!dist\tray_launcher.exe" >> "%TEMP%\fix_shortcut.vbs"
    echo Shortcut.Description = "TT Application Launcher" >> "%TEMP%\fix_shortcut.vbs"
    echo Shortcut.Save >> "%TEMP%\fix_shortcut.vbs"
    
    cscript //nologo "%TEMP%\fix_shortcut.vbs" 2>nul
    del "%TEMP%\fix_shortcut.vbs" >nul 2>&1
    
    if exist "!STARTUP_FOLDER!\TT Launcher.lnk" (
        echo     ✅ 시작 프로그램 등록 성공!
    )
)

:: 2. 필수 파일 확인
echo.
echo [1-2] 필수 파일 확인...
set ERROR_COUNT=0

if exist "dist\tray_launcher.exe" (
    echo     ✅ tray_launcher.exe 존재
) else (
    echo     ❌ tray_launcher.exe 없음
    set /a ERROR_COUNT+=1
)

if exist "config.json" (
    echo     ✅ config.json 존재
) else (
    echo     ❌ config.json 없음
    set /a ERROR_COUNT+=1
)

if exist "venv\Scripts\python.exe" (
    echo     ✅ Python 가상환경 존재
) else (
    echo     ❌ Python 가상환경 없음
    set /a ERROR_COUNT+=1
)

if exist "ollama_utils.py" (
    echo     ✅ ollama_utils.py 존재
) else (
    echo     ❌ ollama_utils.py 없음
    set /a ERROR_COUNT+=1
)

echo.
echo ======================================================
echo  STEP 2: 시스템 트레이 실행 테스트
echo ======================================================
echo.
echo [시나리오] 사용자가 컴퓨터를 재부팅했습니다.
echo            시작 프로그램에서 TT가 자동 실행됩니다.
echo.

:: tray_launcher가 이미 실행 중인지 확인
echo [2-1] 기존 tray_launcher 프로세스 확인...
tasklist | findstr /i "tray_launcher.exe" >nul
if %errorlevel% equ 0 (
    echo     ⚠️ tray_launcher가 이미 실행 중입니다.
) else (
    echo     tray_launcher가 실행되지 않음 - 테스트로 실행합니다.
    echo.
    echo [2-2] 시스템 트레이 애플리케이션 시작...
    start "" "dist\tray_launcher.exe"
    timeout /t 3 /nobreak >nul
    
    tasklist | findstr /i "tray_launcher.exe" >nul
    if !errorlevel! equ 0 (
        echo     ✅ 시스템 트레이에서 실행 중
        echo     시스템 트레이를 확인하세요!
    ) else (
        echo     ❌ 시스템 트레이 실행 실패
    )
)

echo.
echo ======================================================
echo  STEP 3: Ollama 모델 확인
echo ======================================================
echo.
echo [시나리오] 애플리케이션이 LLM 모델을 사용하려고 합니다.
echo.

:: config.json에서 모델명 읽기
echo [3-1] 설정된 기본 모델 확인...
for /f "delims=" %%i in ('powershell -Command "(Get-Content config.json -Raw | ConvertFrom-Json).ollama.default_model" 2^>nul') do set MODEL_NAME=%%i
echo     설정된 모델: !MODEL_NAME!

echo.
echo [3-2] Ollama 서비스 상태 확인...
ollama list >nul 2>&1
if %errorlevel% equ 0 (
    echo     ✅ Ollama 서비스 실행 중
    
    echo.
    echo [3-3] 모델 설치 상태 확인...
    ollama list 2>nul | findstr "!MODEL_NAME!" >nul
    if !errorlevel! equ 0 (
        echo     ✅ !MODEL_NAME! 모델이 설치되어 있음
    ) else (
        echo     ❌ !MODEL_NAME! 모델이 설치되지 않음
        echo     run_all.py 실행 시 자동으로 다운로드됩니다.
    )
) else (
    echo     ⚠️ Ollama 서비스가 실행되지 않음
    echo     run_all.py 실행 시 자동으로 시작됩니다.
)

echo.
echo ======================================================
echo  STEP 4: 백엔드 및 프론트엔드 접근성 테스트
echo ======================================================
echo.
echo [시나리오] 사용자가 웹 인터페이스에 접속합니다.
echo.

echo [4-1] 백엔드 서버 (포트 8080) 확인...
powershell -Command "try { $response = Invoke-WebRequest -Uri 'http://localhost:8080/health' -UseBasicParsing -TimeoutSec 2; Write-Host '     ✅ 백엔드 서버 응답 정상' } catch { Write-Host '     ⚠️ 백엔드 서버가 응답하지 않음' }"

echo.
echo [4-2] 프론트엔드 서버 (포트 8001) 확인...
powershell -Command "try { $response = Invoke-WebRequest -Uri 'http://localhost:8001' -UseBasicParsing -TimeoutSec 2; Write-Host '     ✅ 프론트엔드 서버 응답 정상' } catch { Write-Host '     ⚠️ 프론트엔드 서버가 응답하지 않음' }"

echo.
echo ======================================================
echo  테스트 결과 요약
echo ======================================================
echo.

if !ERROR_COUNT! equ 0 (
    echo ✅ 모든 필수 파일이 존재합니다.
) else (
    echo ❌ !ERROR_COUNT!개의 필수 파일이 누락되었습니다.
)

if exist "!STARTUP_FOLDER!\TT Launcher.lnk" (
    echo ✅ 시작 프로그램 등록 완료
) else (
    echo ❌ 시작 프로그램 등록 실패
)

tasklist | findstr /i "tray_launcher.exe" >nul
if %errorlevel% equ 0 (
    echo ✅ 시스템 트레이 실행 중
) else (
    echo ❌ 시스템 트레이 실행되지 않음
)

echo.
echo ======================================================
echo  사용자 가이드
echo ======================================================
echo.
echo 1. 시스템 트레이 아이콘 확인:
echo    - 작업 표시줄 오른쪽 시스템 트레이에 TT 아이콘이 있어야 합니다.
echo    - 아이콘을 우클릭하면 메뉴가 나타납니다.
echo.
echo 2. 웹 인터페이스 접속:
echo    - 브라우저에서: http://localhost:8001
echo    - API 문서: http://localhost:8080/docs
echo.
echo 3. 재부팅 후 자동 실행:
echo    - 컴퓨터를 재부팅하면 TT가 자동으로 시작됩니다.
echo    - 시작 폴더: Win+R → shell:startup
echo.
echo ======================================================
echo.
pause

endlocal