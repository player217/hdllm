# TT Launcher 시작 프로그램 등록 스크립트

$WshShell = New-Object -ComObject WScript.Shell
$startupFolder = [System.Environment]::GetFolderPath('Startup')
$shortcutPath = Join-Path $startupFolder "TT Launcher.lnk"
$targetPath = "C:\Users\lseun\Documents\LMM_UI_APP\dist\tray_launcher.exe"
$workingDir = "C:\Users\lseun\Documents\LMM_UI_APP"

Write-Host "========================================"
Write-Host " TT Launcher 시작 프로그램 등록"
Write-Host "========================================"
Write-Host ""

# 기존 바로가기 확인 및 삭제
if (Test-Path $shortcutPath) {
    Write-Host "기존 바로가기 삭제 중..."
    Remove-Item $shortcutPath -Force
}

# exe 파일 존재 확인
if (!(Test-Path $targetPath)) {
    Write-Host "❌ 실행 파일을 찾을 수 없습니다: $targetPath"
    exit 1
}

# 바로가기 생성
Write-Host "바로가기 생성 중..."
$Shortcut = $WshShell.CreateShortcut($shortcutPath)
$Shortcut.TargetPath = $targetPath
$Shortcut.WorkingDirectory = $workingDir
$Shortcut.IconLocation = $targetPath
$Shortcut.Description = "TT Application Launcher"
$Shortcut.Save()

# 결과 확인
if (Test-Path $shortcutPath) {
    Write-Host "✅ 바로가기 생성 성공!"
    Write-Host "   위치: $shortcutPath"
    Write-Host "   대상: $targetPath"
    Write-Host ""
    Write-Host "다음 부팅 시 자동으로 실행됩니다."
    
    # 시작 폴더 열기
    Start-Process $startupFolder
} else {
    Write-Host "❌ 바로가기 생성 실패"
}

Write-Host ""
Write-Host "========================================"