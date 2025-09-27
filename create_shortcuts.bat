@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

title TT - 바로가기 아이콘 생성

cd /d "%~dp0"
set PROJECT_ROOT=%~dp0

echo ======================================================
echo  TT - 바로가기 아이콘 생성 스크립트
echo ======================================================
echo.
echo 이 스크립트는 BAT 파일들의 커스텀 아이콘이 적용된 바로가기를 생성합니다.
echo.

:: PowerShell 스크립트를 임시로 생성
echo [INFO] PowerShell 스크립트 생성 중...
(
echo # TT 시스템 바로가기 생성 스크립트
echo $WshShell = New-Object -ComObject WScript.Shell
echo $ProjectRoot = "%PROJECT_ROOT%"
echo.
echo # INSTALL.bat 바로가기
echo Write-Host "INSTALL.bat 바로가기 생성 중..."
echo $Shortcut = $WshShell.CreateShortcut("$ProjectRoot\TT 설치.lnk"^)
echo $Shortcut.TargetPath = "$ProjectRoot\INSTALL.bat"
echo $Shortcut.WorkingDirectory = $ProjectRoot
echo $Shortcut.IconLocation = "$ProjectRoot\assets\install_icon.ico,0"
echo $Shortcut.Description = "TT 시스템 통합 설치"
echo $Shortcut.Save(^)
echo.
echo # run.bat 바로가기  
echo Write-Host "run.bat 바로가기 생성 중..."
echo $Shortcut = $WshShell.CreateShortcut("$ProjectRoot\TT 실행.lnk"^)
echo $Shortcut.TargetPath = "$ProjectRoot\run.bat"
echo $Shortcut.WorkingDirectory = $ProjectRoot
echo $Shortcut.IconLocation = "$ProjectRoot\assets\run_icon.ico,0"
echo $Shortcut.Description = "TT 시스템 GUI 실행"
echo $Shortcut.Save(^)
echo.
echo # tray_launcher.exe 바로가기 (컴파일 후^)
echo if (Test-Path "$ProjectRoot\dist\tray_launcher.exe"^) {
echo     Write-Host "tray_launcher.exe 바로가기 생성 중..."
echo     $Shortcut = $WshShell.CreateShortcut("$ProjectRoot\TT 트레이.lnk"^)
echo     $Shortcut.TargetPath = "$ProjectRoot\dist\tray_launcher.exe"
echo     $Shortcut.WorkingDirectory = $ProjectRoot
echo     $Shortcut.IconLocation = "$ProjectRoot\assets\app_icon.ico,0"
echo     $Shortcut.Description = "TT 시스템 트레이 런처"
echo     $Shortcut.Save(^)
echo } else {
echo     Write-Host "tray_launcher.exe를 찾을 수 없습니다. 먼저 build_tray_launcher.bat를 실행하세요." -ForegroundColor Yellow
echo }
echo.
echo # build_tray_launcher.bat 바로가기
echo Write-Host "build_tray_launcher.bat 바로가기 생성 중..."
echo $Shortcut = $WshShell.CreateShortcut("$ProjectRoot\TT 컴파일.lnk"^)
echo $Shortcut.TargetPath = "$ProjectRoot\build_tray_launcher.bat"
echo $Shortcut.WorkingDirectory = $ProjectRoot
echo $Shortcut.IconLocation = "$ProjectRoot\assets\app_icon.ico,0"
echo $Shortcut.Description = "TT 트레이 런처 컴파일"
echo $Shortcut.Save(^)
echo.
echo Write-Host "모든 바로가기 생성 완료!" -ForegroundColor Green
) > create_shortcuts_temp.ps1

:: PowerShell 실행 정책 확인 후 스크립트 실행
echo [INFO] PowerShell 스크립트 실행 중...
powershell -ExecutionPolicy Bypass -File "create_shortcuts_temp.ps1"

if %errorlevel% equ 0 (
    echo.
    echo ======================================================
    echo  바로가기 생성 완료!
    echo ======================================================
    echo.
    echo 생성된 바로가기:
    if exist "TT 설치.lnk" echo   ✓ TT 설치.lnk (INSTALL.bat^)
    if exist "TT 실행.lnk" echo   ✓ TT 실행.lnk (run.bat^)
    if exist "TT 컴파일.lnk" echo   ✓ TT 컴파일.lnk (build_tray_launcher.bat^)
    if exist "TT 트레이.lnk" echo   ✓ TT 트레이.lnk (tray_launcher.exe^)
    echo.
    echo 이제 이 바로가기들을 사용하여 커스텀 아이콘이 적용된
    echo 프로그램들을 실행할 수 있습니다!
    echo.
    echo 바탕화면이나 시작 메뉴에 복사하여 사용하세요.
) else (
    echo [ERROR] 바로가기 생성 중 오류가 발생했습니다.
    echo         PowerShell 실행 정책이나 권한을 확인하세요.
)

:: 임시 파일 정리
if exist "create_shortcuts_temp.ps1" del "create_shortcuts_temp.ps1" >nul 2>&1

echo.
pause