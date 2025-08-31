# PowerShell Execution Policy 체크 및 설정
param(
    [switch]$Force,
    [switch]$DebugMode,
    [string]$QdrantScope = "personal"
)

# 관리자 권한 체크
function Test-Administrator {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# 진행률 표시
$totalSteps = 8
$currentStep = 0

function Show-Progress {
    param($message)
    $script:currentStep++
    Write-Host "[$script:currentStep/$totalSteps] $message" -ForegroundColor Green
    Write-Progress -Activity "HD현대미포 Gauss-1 RAG System 설치" -Status $message -PercentComplete (($script:currentStep / $totalSteps) * 100)
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "   HD현대미포 Gauss-1 RAG System - 원클릭 설치" -ForegroundColor Cyan
Write-Host "   Version: 2.1 - Dual Qdrant Routing" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 시작 전 체크
if (-not (Test-Administrator)) {
    Write-Host "⚠️ 관리자 권한이 필요합니다. PowerShell을 관리자로 실행해주세요." -ForegroundColor Yellow
    if (-not $Force) {
        pause
        exit 1
    }
}

# 현재 디렉토리 설정
$ROOT = Get-Location
Write-Host "📁 작업 디렉토리: $ROOT" -ForegroundColor Blue

try {
    # 1) Python 및 가상환경 체크
    Show-Progress "Python 환경 체크 및 가상환경 생성"
    
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        Write-Host "❌ Python이 설치되지 않았습니다." -ForegroundColor Red
        Write-Host "Python 3.8+ 설치 후 다시 실행해주세요." -ForegroundColor Yellow
        exit 1
    }
    
    $pythonVersion = python --version
    Write-Host "✅ $pythonVersion 감지" -ForegroundColor Green
    
    if (-not (Test-Path "venv")) {
        python -m venv venv
        Write-Host "✅ 가상환경 생성 완료" -ForegroundColor Green
    } else {
        Write-Host "✅ 기존 가상환경 발견" -ForegroundColor Green
    }
    
    # 가상환경 활성화
    & "venv\Scripts\Activate.ps1"
    
    # 2) 의존성 설치
    Show-Progress "Python 패키지 설치"
    
    if (Test-Path "requirements.txt") {
        pip install -r requirements.txt --upgrade
        Write-Host "✅ requirements.txt 패키지 설치 완료" -ForegroundColor Green
    } else {
        Write-Host "⚠️ requirements.txt를 찾을 수 없습니다." -ForegroundColor Yellow
    }
    
    # 3) Qdrant 설치 및 실행
    Show-Progress "Qdrant 벡터 DB 설치"
    
    $qdrantPath = "bin\qdrant"
    if (-not (Test-Path $qdrantPath)) {
        Write-Host "📥 Qdrant 다운로드 중..." -ForegroundColor Yellow
        New-Item -ItemType Directory -Force -Path "bin" | Out-Null
        
        # Qdrant 바이너리 다운로드 (Windows x64)
        $qdrantUrl = "https://github.com/qdrant/qdrant/releases/latest/download/qdrant-x86_64-pc-windows-msvc.zip"
        $qdrantZip = "bin\qdrant.zip"
        
        try {
            Invoke-WebRequest -Uri $qdrantUrl -OutFile $qdrantZip -UseBasicParsing
            Expand-Archive -Path $qdrantZip -DestinationPath "bin" -Force
            Remove-Item $qdrantZip
            Write-Host "✅ Qdrant 설치 완료" -ForegroundColor Green
        } catch {
            Write-Host "⚠️ Qdrant 자동 다운로드 실패. 수동 설치 필요" -ForegroundColor Yellow
            Write-Host "https://github.com/qdrant/qdrant/releases 에서 Windows 버전 다운로드" -ForegroundColor Yellow
        }
    } else {
        Write-Host "✅ Qdrant 이미 설치됨" -ForegroundColor Green
    }
    
    # 4) Ollama 체크
    Show-Progress "Ollama LLM 서버 체크"
    
    if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
        Write-Host "⚠️ Ollama가 설치되지 않았습니다." -ForegroundColor Yellow
        Write-Host "https://ollama.ai 에서 Ollama 설치 후 다시 실행해주세요." -ForegroundColor Yellow
        Write-Host "또는 bin\ollama\ 폴더에 ollama.exe 파일을 배치해주세요." -ForegroundColor Yellow
    } else {
        Write-Host "✅ Ollama 설치 확인" -ForegroundColor Green
        
        # gemma3:4b 모델 체크
        $models = ollama list
        if ($models -match "gemma3:4b") {
            Write-Host "✅ gemma3:4b 모델 준비됨" -ForegroundColor Green
        } else {
            Write-Host "📥 gemma3:4b 모델 다운로드 중..." -ForegroundColor Yellow
            ollama pull gemma3:4b
        }
    }
    
    # 5) 환경 변수 설정
    Show-Progress "환경 설정 업데이트"
    
    if (Test-Path ".env") {
        Write-Host "✅ .env 파일 발견" -ForegroundColor Green
        
        # 스코프 설정 업데이트
        $envContent = Get-Content ".env"
        $newEnvContent = $envContent | ForEach-Object {
            if ($_ -match "^DEFAULT_QDRANT_SCOPE=") {
                "DEFAULT_QDRANT_SCOPE=$QdrantScope"
            } else {
                $_
            }
        }
        $newEnvContent | Set-Content ".env"
        Write-Host "✅ 기본 Qdrant 스코프: $QdrantScope" -ForegroundColor Green
    } else {
        Write-Host "⚠️ .env 파일을 찾을 수 없습니다." -ForegroundColor Yellow
    }
    
    # 6) 디렉토리 생성
    Show-Progress "필요 디렉토리 생성"
    
    $requiredDirs = @("storage", "storage\qdrant", "logs", "backend\logs")
    foreach ($dir in $requiredDirs) {
        if (-not (Test-Path $dir)) {
            New-Item -ItemType Directory -Force -Path $dir | Out-Null
            Write-Host "📁 $dir 디렉토리 생성" -ForegroundColor Blue
        }
    }
    
    # 7) 권한 설정
    Show-Progress "파일 권한 설정"
    
    if (Test-Path "RUN.bat") {
        Write-Host "✅ RUN.bat 실행 가능" -ForegroundColor Green
    }
    
    if (Test-Path "bin\qdrant\qdrant.exe") {
        Write-Host "✅ Qdrant 실행 파일 준비" -ForegroundColor Green
    }
    
    # 8) 설치 완료 및 테스트
    Show-Progress "설치 완료 및 상태 체크"
    
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "   🎉 설치가 완료되었습니다!" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host ""
    
    Write-Host "🚀 실행 방법:" -ForegroundColor Yellow
    Write-Host "   1. RUN.bat 더블클릭" -ForegroundColor White
    Write-Host "   2. 또는 PowerShell에서: .\RUN.bat" -ForegroundColor White
    Write-Host ""
    
    Write-Host "🌐 접속 주소:" -ForegroundColor Yellow
    Write-Host "   • 웹 인터페이스: http://localhost:8001" -ForegroundColor White
    Write-Host "   • API 서버: http://localhost:8080" -ForegroundColor White
    Write-Host "   • API 문서: http://localhost:8080/docs" -ForegroundColor White
    Write-Host ""
    
    Write-Host "🎯 Dual Qdrant 라우팅:" -ForegroundColor Yellow
    Write-Host "   • 개인 PC: 127.0.0.1:6333" -ForegroundColor White
    Write-Host "   • 부서 서버: 10.150.104.37:6333" -ForegroundColor White
    Write-Host "   • 현재 기본값: $QdrantScope" -ForegroundColor White
    Write-Host ""
    
    if ($DebugMode) {
        Write-Host "🔧 디버그 도구:" -ForegroundColor Yellow
        Write-Host "   • run_gui_debug.bat - GUI 디버그 모드" -ForegroundColor White
        Write-Host "   • stop.bat - 모든 서비스 중지" -ForegroundColor White
        Write-Host ""
    }
    
    # 바로 실행 옵션
    $runNow = Read-Host "지금 바로 실행하시겠습니까? (Y/N)"
    if ($runNow -eq "Y" -or $runNow -eq "y") {
        Write-Host "🚀 시스템 시작 중..." -ForegroundColor Green
        & ".\RUN.bat"
    } else {
        Write-Host "✨ 준비 완료! RUN.bat를 실행해 시작하세요." -ForegroundColor Green
    }

} catch {
    Write-Host "❌ 설치 중 오류가 발생했습니다:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    
    if ($DebugMode) {
        Write-Host ""
        Write-Host "디버그 정보:" -ForegroundColor Yellow
        Write-Host $_.ScriptStackTrace -ForegroundColor Gray
    }
    
    Write-Host ""
    Write-Host "해결 방법:" -ForegroundColor Yellow
    Write-Host "1. PowerShell을 관리자로 실행" -ForegroundColor White
    Write-Host "2. 인터넷 연결 확인" -ForegroundColor White
    Write-Host "3. Python 3.8+ 설치 확인" -ForegroundColor White
    Write-Host "4. -Force 옵션으로 재시도" -ForegroundColor White
    
    pause
    exit 1
} finally {
    Write-Progress -Activity "설치 완료" -Completed
}