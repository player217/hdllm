@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo ======================================================
echo  시작 프로그램 등록 테스트
echo ======================================================
echo.

:: 프로젝트 경로 설정
cd /d "%~dp0"
set "PROJECT_ROOT=%~dp0"
set "STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"

echo [1/4] 기존 바로가기 확인...
if exist "!STARTUP_FOLDER!\TT Launcher.lnk" (
    echo     기존 바로가기가 있습니다. 삭제 중...
    del "!STARTUP_FOLDER!\TT Launcher.lnk" >nul 2>&1
    echo     삭제 완료
) else (
    echo     기존 바로가기 없음
)

echo.
echo [2/4] VBScript로 바로가기 생성 중...

:: VBScript 파일 생성
echo Set WshShell = CreateObject^("WScript.Shell"^) > "%TEMP%\test_shortcut.vbs"
echo Set Shortcut = WshShell.CreateShortcut^("!STARTUP_FOLDER!\TT Launcher.lnk"^) >> "%TEMP%\test_shortcut.vbs"
echo Shortcut.TargetPath = "!PROJECT_ROOT!dist\tray_launcher.exe" >> "%TEMP%\test_shortcut.vbs"
echo Shortcut.WorkingDirectory = "!PROJECT_ROOT!" >> "%TEMP%\test_shortcut.vbs"
echo Shortcut.IconLocation = "!PROJECT_ROOT!dist\tray_launcher.exe" >> "%TEMP%\test_shortcut.vbs"
echo Shortcut.Description = "TT Application Launcher" >> "%TEMP%\test_shortcut.vbs"
echo Shortcut.Save >> "%TEMP%\test_shortcut.vbs"
echo. >> "%TEMP%\test_shortcut.vbs"
echo WScript.Echo "Shortcut created successfully!" >> "%TEMP%\test_shortcut.vbs"

:: VBScript 실행
cscript //nologo "%TEMP%\test_shortcut.vbs"
set CREATE_RESULT=!errorlevel!
echo     VBScript 실행 결과: !CREATE_RESULT!

:: 임시 파일 삭제
del "%TEMP%\test_shortcut.vbs" >nul 2>&1

echo.
echo [3/4] 결과 확인...
if exist "!STARTUP_FOLDER!\TT Launcher.lnk" (
    echo     ✅ 바로가기 생성 성공!
    echo     위치: !STARTUP_FOLDER!\TT Launcher.lnk
    
    :: 바로가기 속성 확인
    echo.
    echo     바로가기 속성:
    powershell -Command "$sh = New-Object -ComObject WScript.Shell; $sc = $sh.CreateShortcut('!STARTUP_FOLDER!\TT Launcher.lnk'); Write-Host '     - 대상:' $sc.TargetPath; Write-Host '     - 작업 폴더:' $sc.WorkingDirectory; Write-Host '     - 설명:' $sc.Description"
) else (
    echo     ❌ 바로가기 생성 실패!
    echo     에러 코드: !CREATE_RESULT!
)

echo.
echo [4/4] 시작 폴더 열기...
echo     시작 프로그램 폴더를 엽니다...
start "" "!STARTUP_FOLDER!"

echo.
echo ======================================================
echo  테스트 완료!
echo ======================================================
echo.
echo  결과:
if exist "!STARTUP_FOLDER!\TT Launcher.lnk" (
    echo  - ✅ 바로가기가 시작 폴더에 생성되었습니다.
    echo  - 다음 부팅 시 TT가 자동으로 시작됩니다.
) else (
    echo  - ❌ 바로가기 생성에 실패했습니다.
    echo  - 수동으로 등록이 필요합니다.
)
echo.
pause

endlocal