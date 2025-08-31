# ================================================================
# HD현대미포 Gauss-1 RAG System - 오프라인 설치 스크립트
# Docker 불가 PC용 완전 독립 실행형 배포판
# ================================================================

param(
    [switch]$Force,
    [switch]$SkipVC,
    [switch]$Silent
)

# 관리자 권한 확인
if (-NOT ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    if (-not $Silent) {
        Write-Warning "이 스크립트는 관리자 권한이 필요합니다. 관리자 권한으로 다시 실행해주세요."
        Write-Host "Press any key to exit..."
        $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    }
    exit 1
}

# 환경 변수 로드
$envFile = Join-Path $PSScriptRoot "..\\.env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match "^([^#=]+)=(.*)$") {
            [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2], "Process")
        }
    }
    Write-Host "✅ 환경 설정 파일 로드됨" -ForegroundColor Green
} else {
    Write-Error ".env 파일을 찾을 수 없습니다."
    exit 1
}

$rootPath = Split-Path $PSScriptRoot -Parent
$pythonPath = Join-Path $rootPath $env:PY_EMBED_ROOT
$pythonExe = Join-Path $pythonPath "python.exe"

Write-Host "🚀 HD현대미포 Gauss-1 RAG 시스템 설치 시작" -ForegroundColor Cyan
Write-Host "설치 경로: $rootPath" -ForegroundColor Yellow

# 1. Visual C++ Redistributable 확인 및 설치
if (-not $SkipVC) {
    Write-Host "`n📦 Visual C++ Redistributable 확인 중..." -ForegroundColor Yellow
    
    $vcRedist = Get-ItemProperty "HKLM:SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64" -ErrorAction SilentlyContinue
    if ($vcRedist -and $vcRedist.Installed -eq 1) {
        Write-Host "✅ Visual C++ Redistributable 이미 설치됨" -ForegroundColor Green
    } else {
        Write-Host "⚠️ Visual C++ Redistributable 필요" -ForegroundColor Yellow
        
        $vcRedistUrl = "https://aka.ms/vs/17/release/vc_redist.x64.exe"
        $vcRedistPath = Join-Path $env:TEMP "vc_redist.x64.exe"
        
        try {
            Write-Host "다운로드 중: $vcRedistUrl" -ForegroundColor Yellow
            Invoke-WebRequest -Uri $vcRedistUrl -OutFile $vcRedistPath -UseBasicParsing
            
            Write-Host "Visual C++ Redistributable 설치 중..." -ForegroundColor Yellow
            Start-Process -FilePath $vcRedistPath -ArgumentList "/quiet" -Wait
            Write-Host "✅ Visual C++ Redistributable 설치 완료" -ForegroundColor Green
            
            Remove-Item $vcRedistPath -ErrorAction SilentlyContinue
        } catch {
            Write-Warning "Visual C++ Redistributable 자동 설치 실패: $_"
            Write-Host "수동으로 다음 URL에서 다운로드하여 설치해주세요:" -ForegroundColor Yellow
            Write-Host $vcRedistUrl -ForegroundColor Cyan
        }
    }
}

# 2. Python 임베디드 검증
Write-Host "`n🐍 Python 임베디드 검증 중..." -ForegroundColor Yellow

if (-not (Test-Path $pythonExe)) {
    Write-Error "Python 실행 파일을 찾을 수 없습니다: $pythonExe"
    Write-Host "bin/python311/ 폴더에 Python 임베디드를 압축 해제해주세요."
    exit 1
}

try {
    $pythonVersion = & $pythonExe --version 2>&1
    Write-Host "✅ Python 버전: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Error "Python 실행 실패: $_"
    exit 1
}

# 3. Python 패키지 검증 및 설치
Write-Host "`n📦 Python 패키지 검증 중..." -ForegroundColor Yellow

$requirementsPath = Join-Path $rootPath "backend\requirements.lock.txt"
if (-not (Test-Path $requirementsPath)) {
    Write-Error "requirements.lock.txt 파일을 찾을 수 없습니다."
    exit 1
}

# pip 업그레이드
Write-Host "pip 업그레이드 중..." -ForegroundColor Yellow
& $pythonExe -m pip install --upgrade pip --quiet

# 패키지 설치
Write-Host "필수 패키지 설치 중..." -ForegroundColor Yellow
try {
    & $pythonExe -m pip install -r $requirementsPath --quiet --no-warn-script-location
    Write-Host "✅ Python 패키지 설치 완료" -ForegroundColor Green
} catch {
    Write-Error "Python 패키지 설치 실패: $_"
    Write-Host "오프라인 환경의 경우 다음 명령을 실행해보세요:"
    Write-Host "pip install -r backend\requirements.lock.txt --find-links .\wheels --no-index" -ForegroundColor Cyan
    exit 1
}

# 4. 바이너리 파일 검증
Write-Host "`n🔧 바이너리 파일 검증 중..." -ForegroundColor Yellow

$requiredBinaries = @{
    "bin\qdrant\qdrant.exe" = "Qdrant 벡터 데이터베이스"
    "bin\ollama\ollama.exe" = "Ollama LLM 서버"
}

foreach ($binary in $requiredBinaries.GetEnumerator()) {
    $binaryPath = Join-Path $rootPath $binary.Key
    if (Test-Path $binaryPath) {
        Write-Host "✅ $($binary.Value) 확인됨" -ForegroundColor Green
    } else {
        Write-Warning "❌ $($binary.Value) 누락: $($binary.Key)"
        Write-Host "다음 위치에서 다운로드하여 설치해주세요:" -ForegroundColor Yellow
        if ($binary.Key -like "*qdrant*") {
            Write-Host "Qdrant: https://github.com/qdrant/qdrant/releases" -ForegroundColor Cyan
        } elseif ($binary.Key -like "*ollama*") {
            Write-Host "Ollama: https://github.com/ollama/ollama/releases" -ForegroundColor Cyan
        }
    }
}

# 5. 모델 캐시 확인
Write-Host "`n🤖 AI 모델 캐시 확인 중..." -ForegroundColor Yellow

$modelPaths = @{
    "models\embeddings\bge-m3" = "BGE-M3 임베딩 모델"
    "models\ollama\gemma3-4b" = "Gemma3-4b 언어 모델"
}

foreach ($model in $modelPaths.GetEnumerator()) {
    $modelPath = Join-Path $rootPath $model.Key
    if (Test-Path $modelPath) {
        $fileCount = (Get-ChildItem $modelPath -Recurse -File | Measure-Object).Count
        Write-Host "✅ $($model.Value) 확인됨 ($fileCount 파일)" -ForegroundColor Green
    } else {
        Write-Warning "⚠️ $($model.Value) 캐시 없음: $($model.Key)"
        Write-Host "첫 실행 시 자동으로 다운로드됩니다 (인터넷 연결 필요)" -ForegroundColor Yellow
    }
}

# 6. 포트 사용 확인
Write-Host "`n🌐 포트 사용 확인 중..." -ForegroundColor Yellow

$requiredPorts = @(6333, 6334, 8080, 8001, 11434)
foreach ($port in $requiredPorts) {
    $connection = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    if ($connection) {
        Write-Warning "⚠️ 포트 $port 이미 사용 중 (PID: $($connection.OwningProcess))"
        $processName = (Get-Process -Id $connection.OwningProcess -ErrorAction SilentlyContinue).ProcessName
        Write-Host "   프로세스: $processName" -ForegroundColor Yellow
    } else {
        Write-Host "✅ 포트 $port 사용 가능" -ForegroundColor Green
    }
}

# 7. 데이터 디렉토리 생성
Write-Host "`n📁 데이터 디렉토리 설정 중..." -ForegroundColor Yellow

$dataDirs = @(
    "data\qdrant",
    "logs",
    "models\embeddings",
    "models\ollama"
)

foreach ($dir in $dataDirs) {
    $dirPath = Join-Path $rootPath $dir
    if (-not (Test-Path $dirPath)) {
        New-Item -ItemType Directory -Path $dirPath -Force | Out-Null
        Write-Host "✅ 디렉토리 생성: $dir" -ForegroundColor Green
    }
}

# 8. 권한 설정
Write-Host "`n🔐 권한 설정 중..." -ForegroundColor Yellow

$executablePaths = @(
    $pythonExe,
    (Join-Path $rootPath $env:QDRANT_BIN),
    (Join-Path $rootPath $env:OLLAMA_BIN)
)

foreach ($exePath in $executablePaths) {
    if (Test-Path $exePath) {
        try {
            # Windows Defender 예외 추가 시도
            Add-MpPreference -ExclusionPath $exePath -ErrorAction SilentlyContinue
            Write-Host "✅ Windows Defender 예외 추가: $(Split-Path $exePath -Leaf)" -ForegroundColor Green
        } catch {
            Write-Host "⚠️ Windows Defender 예외 추가 실패: $(Split-Path $exePath -Leaf)" -ForegroundColor Yellow
        }
    }
}

# 9. 방화벽 규칙 추가
Write-Host "`n🔥 방화벽 규칙 설정 중..." -ForegroundColor Yellow

$firewallRules = @{
    "HDGauss1-Qdrant-HTTP" = @{Port=6333; Description="HD현대미포 Gauss-1 Qdrant HTTP"}
    "HDGauss1-Qdrant-gRPC" = @{Port=6334; Description="HD현대미포 Gauss-1 Qdrant gRPC"}
    "HDGauss1-Backend" = @{Port=8080; Description="HD현대미포 Gauss-1 Backend API"}
    "HDGauss1-Frontend" = @{Port=8001; Description="HD현대미포 Gauss-1 Frontend"}
    "HDGauss1-Ollama" = @{Port=11434; Description="HD현대미포 Gauss-1 Ollama"}
}

foreach ($rule in $firewallRules.GetEnumerator()) {
    try {
        $existing = Get-NetFirewallRule -DisplayName $rule.Key -ErrorAction SilentlyContinue
        if (-not $existing) {
            New-NetFirewallRule -DisplayName $rule.Key -Direction Inbound -Protocol TCP -LocalPort $rule.Value.Port -Action Allow -Description $rule.Value.Description | Out-Null
            Write-Host "✅ 방화벽 규칙 추가: $($rule.Key)" -ForegroundColor Green
        } else {
            Write-Host "✅ 방화벽 규칙 이미 존재: $($rule.Key)" -ForegroundColor Green
        }
    } catch {
        Write-Warning "방화벽 규칙 추가 실패: $($rule.Key) - $_"
    }
}

# 10. 바탕화면 바로가기 생성
Write-Host "`n🖥️ 바탕화면 바로가기 생성 중..." -ForegroundColor Yellow

$desktopPath = [System.Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktopPath "HD현대미포 Gauss-1.lnk"
$runBatPath = Join-Path $rootPath "scripts\run.bat"

try {
    $WshShell = New-Object -comObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut($shortcutPath)
    $Shortcut.TargetPath = $runBatPath
    $Shortcut.WorkingDirectory = $rootPath
    $Shortcut.Description = "HD현대미포 Gauss-1 RAG 시스템"
    $Shortcut.Save()
    Write-Host "✅ 바탕화면 바로가기 생성됨" -ForegroundColor Green
} catch {
    Write-Warning "바탕화면 바로가기 생성 실패: $_"
}

# 11. 설치 완료 요약
Write-Host "`n🎉 설치 완료!" -ForegroundColor Green
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan

Write-Host "`n📋 설치 요약:" -ForegroundColor Yellow
Write-Host "   • Python 임베디드: ✅ 설치 완료"
Write-Host "   • 필수 패키지: ✅ 설치 완료"
Write-Host "   • 방화벽 규칙: ✅ 설정 완료"
Write-Host "   • 바탕화면 바로가기: ✅ 생성 완료"

Write-Host "`n🚀 실행 방법:" -ForegroundColor Yellow
Write-Host "   1. 바탕화면의 'HD현대미포 Gauss-1' 바로가기 실행"
Write-Host "   2. 또는 scripts\run.bat 실행"
Write-Host "   3. 웹 인터페이스: http://localhost:8001"
Write-Host "   4. API 문서: http://localhost:8080/docs"

Write-Host "`n🔧 문제 해결:" -ForegroundColor Yellow
Write-Host "   • 진단: scripts\self_check.ps1 실행"
Write-Host "   • 디버그: scripts\run_gui_debug.bat 실행"
Write-Host "   • 중지: scripts\stop.bat 실행"

Write-Host "`n📞 지원:" -ForegroundColor Yellow
Write-Host "   HD현대미포 선각기술부"
Write-Host "   README_DEPLOY.md 문서 참고"

if (-not $Silent) {
    Write-Host "`nPress any key to exit..." -ForegroundColor Gray
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

Write-Host "✨ 설치 스크립트 완료" -ForegroundColor Cyan