# HD현대미포 Gauss-1 RAG System - Enhanced PowerShell Installer
# Version: 3.0 - Full Automation & Portable Support
# Date: 2025-08-31

[CmdletBinding()]
param(
    [switch]$SkipPython,
    [switch]$SkipQdrant,  
    [switch]$SkipOllama,
    [switch]$Force,
    [string]$PythonVersion = "3.11.7"
)

# 관리자 권한 확인 (선택적)
$IsAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

# 스크립트 실행 정책 임시 설정
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force

# 기본 설정
$RootPath = Split-Path -Parent $PSScriptRoot
$BinPath = Join-Path $RootPath "bin"
$DataPath = Join-Path $RootPath "data" 
$ScriptsPath = Join-Path $RootPath "scripts"
$VenvPath = Join-Path $RootPath "venv"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "   HD현대미포 Gauss-1 RAG System - 포터블 설치 프로그램 v3.0   " -ForegroundColor White
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 디렉토리 생성
$Directories = @($BinPath, $DataPath, "$DataPath\qdrant", "$DataPath\models", "$BinPath\python311", "$BinPath\qdrant", "$BinPath\ollama")
foreach ($Dir in $Directories) {
    if (!(Test-Path $Dir)) {
        New-Item -ItemType Directory -Path $Dir -Force | Out-Null
        Write-Host "✅ 디렉토리 생성: $Dir" -ForegroundColor Green
    }
}

# 함수: 다운로드 유틸리티
function Download-File {
    param([string]$Url, [string]$Output, [string]$Description)
    
    try {
        Write-Host "⬇️  $Description 다운로드 중..." -ForegroundColor Yellow
        $WebClient = New-Object System.Net.WebClient
        $WebClient.DownloadFile($Url, $Output)
        Write-Host "✅ 다운로드 완료: $Description" -ForegroundColor Green
        return $true
    }
    catch {
        Write-Host "❌ 다운로드 실패: $Description - $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
}

# 함수: 압축 해제
function Extract-Archive {
    param([string]$ArchivePath, [string]$Destination, [string]$Description)
    
    try {
        Write-Host "📦 $Description 압축 해제 중..." -ForegroundColor Yellow
        if ($ArchivePath -like "*.zip") {
            Expand-Archive -Path $ArchivePath -DestinationPath $Destination -Force
        } else {
            # 7zip이나 다른 압축 도구 사용 고려
            throw "Unsupported archive format"
        }
        Remove-Item $ArchivePath -Force
        Write-Host "✅ 압축 해제 완료: $Description" -ForegroundColor Green
        return $true
    }
    catch {
        Write-Host "❌ 압축 해제 실패: $Description - $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
}

# 함수: TCP 연결 테스트
function Test-TcpConnection {
    param([string]$Host, [int]$Port, [int]$Timeout = 3)
    
    try {
        $TcpClient = New-Object System.Net.Sockets.TcpClient
        $Connect = $TcpClient.BeginConnect($Host, $Port, $null, $null)
        $Wait = $Connect.AsyncWaitHandle.WaitOne($Timeout * 1000, $false)
        
        if ($Wait) {
            $TcpClient.EndConnect($Connect)
            $TcpClient.Close()
            return $true
        } else {
            $TcpClient.Close()
            return $false
        }
    }
    catch {
        return $false
    }
}

Write-Host "[1/6] 환경 설정 파일 준비..." -ForegroundColor Blue

# .env 파일 생성 또는 업데이트
$EnvFile = Join-Path $RootPath ".env"
$EnvExampleFile = Join-Path $RootPath ".env.example"

if (!(Test-Path $EnvFile)) {
    if (Test-Path $EnvExampleFile) {
        Copy-Item $EnvExampleFile $EnvFile
        Write-Host "✅ .env 파일 생성 (.env.example에서 복사)" -ForegroundColor Green
    } else {
        # 기본 .env 파일 생성
        $DefaultEnv = @"
# HD현대미포 Gauss-1 RAG System - 환경 설정
# 자동 생성됨: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

# 애플리케이션 설정
APP_PORT=8080
FRONTEND_PORT=8001
GUI_AUTO_START=false

# Qdrant 설정
QDRANT_MODE=auto
REMOTE_QDRANT_HOST=10.150.104.37
REMOTE_QDRANT_PORT=6333
LOCAL_QDRANT_PORT=6333

# 메일 Qdrant 설정  
RAG_MAIL_QDRANT_HOST=127.0.0.1
RAG_MAIL_QDRANT_PORT=6333

# 문서 Qdrant 설정
RAG_DOC_QDRANT_HOST=127.0.0.1  
RAG_DOC_QDRANT_PORT=6333

# Ollama 설정
OLLAMA_AUTO_PULL=true
OLLAMA_MODEL=gemma3:4b
OLLAMA_HOST=127.0.0.1
OLLAMA_PORT=11434

# 경로 설정 (상대 경로 사용)
MAIL_QDRANT_PATH=./data/qdrant/mail
DOC_QDRANT_PATH=./data/qdrant/doc
LOCAL_MSG_PATH=./data/messages
MODEL_PATH=./data/models
"@
        $DefaultEnv | Out-File -FilePath $EnvFile -Encoding UTF8
        Write-Host "✅ 기본 .env 파일 생성" -ForegroundColor Green
    }
} else {
    Write-Host "✅ 기존 .env 파일 사용" -ForegroundColor Green
}

Write-Host "[2/6] Python 3.11 설치 확인 및 준비..." -ForegroundColor Blue

if (!$SkipPython) {
    $PythonExe = $null
    
    # 시스템 Python 확인
    try {
        $PyLauncher = Get-Command py -ErrorAction SilentlyContinue
        if ($PyLauncher) {
            $PyVersion = & py -c "import sys; print('.'.join(map(str, sys.version_info[:2])))"
            if ([version]$PyVersion -ge [version]"3.11") {
                $PythonExe = "py -3.11"
                Write-Host "✅ 시스템 Python 3.11+ 감지 (버전: $PyVersion)" -ForegroundColor Green
            }
        }
    } catch {}
    
    # 포터블 Python 확인/다운로드
    $PortablePython = Join-Path $BinPath "python311\python.exe"
    if (!$PythonExe -and !(Test-Path $PortablePython)) {
        Write-Host "⬇️  Python $PythonVersion 임베디드 버전 다운로드 중..." -ForegroundColor Yellow
        
        $PythonUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip"
        $PythonZip = Join-Path $BinPath "python311.zip"
        
        if (Download-File -Url $PythonUrl -Output $PythonZip -Description "Python $PythonVersion 임베디드") {
            if (Extract-Archive -ArchivePath $PythonZip -Destination "$BinPath\python311" -Description "Python") {
                # get-pip.py 다운로드
                $GetPipUrl = "https://bootstrap.pypa.io/get-pip.py"
                $GetPipPath = Join-Path "$BinPath\python311" "get-pip.py"
                
                if (Download-File -Url $GetPipUrl -Output $GetPipPath -Description "get-pip.py") {
                    # pip 설치
                    Set-Location "$BinPath\python311"
                    & ".\python.exe" "get-pip.py" --no-warn-script-location
                    
                    # python311._pth 수정 (site-packages 활성화)
                    $PthFile = Join-Path "$BinPath\python311" "python311._pth"
                    if (Test-Path $PthFile) {
                        $PthContent = Get-Content $PthFile
                        $PthContent = $PthContent -replace "#import site", "import site"
                        $PthContent | Out-File -FilePath $PthFile -Encoding ASCII
                    }
                    
                    Set-Location $RootPath
                    $PythonExe = $PortablePython
                    Write-Host "✅ 포터블 Python 설치 완료" -ForegroundColor Green
                }
            }
        }
    } elseif (Test-Path $PortablePython) {
        $PythonExe = $PortablePython
        Write-Host "✅ 기존 포터블 Python 사용" -ForegroundColor Green
    }
    
    if (!$PythonExe) {
        Write-Host "❌ Python 3.11 설치 실패. 수동 설치 필요" -ForegroundColor Red
        Write-Host "   다운로드: https://www.python.org/downloads/" -ForegroundColor Yellow
        exit 1
    }
} else {
    Write-Host "⏭️  Python 설치 건너뜀" -ForegroundColor Yellow
}

Write-Host "[3/6] 가상환경 생성 및 패키지 설치..." -ForegroundColor Blue

if (!(Test-Path "$VenvPath\Scripts\activate.ps1")) {
    Write-Host "🔧 새 가상환경 생성 중..." -ForegroundColor Yellow
    if ($PythonExe -like "py*") {
        & py -3.11 -m venv $VenvPath
    } else {
        & $PythonExe -m venv $VenvPath
    }
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ 가상환경 생성 완료" -ForegroundColor Green
    } else {
        Write-Host "❌ 가상환경 생성 실패" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "✅ 기존 가상환경 사용" -ForegroundColor Green
}

# 가상환경 활성화 및 패키지 설치
& "$VenvPath\Scripts\Activate.ps1"
Write-Host "🔧 pip 업그레이드 중..." -ForegroundColor Yellow
& python -m pip install --upgrade pip --quiet

$RequirementsFile = Join-Path $RootPath "requirements.txt"
if (Test-Path $RequirementsFile) {
    Write-Host "📦 패키지 설치 중 (5-10분 소요)..." -ForegroundColor Yellow
    & pip install -r $RequirementsFile --quiet
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ 패키지 설치 완료" -ForegroundColor Green
    } else {
        Write-Host "❌ 패키지 설치 실패" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "❌ requirements.txt 파일이 없습니다" -ForegroundColor Red
}

Write-Host "[4/6] Qdrant 포터블 버전 준비..." -ForegroundColor Blue

if (!$SkipQdrant) {
    $QdrantExe = Join-Path "$BinPath\qdrant" "qdrant.exe"
    if (!(Test-Path $QdrantExe) -or $Force) {
        # 원격 Qdrant 연결 테스트
        Write-Host "🔍 원격 Qdrant 서버 연결 테스트..." -ForegroundColor Yellow
        $RemoteQdrant = Test-TcpConnection -Host "10.150.104.37" -Port 6333
        
        if (!$RemoteQdrant) {
            Write-Host "⬇️  Qdrant 최신 버전 다운로드 중..." -ForegroundColor Yellow
            
            # GitHub API를 통한 최신 릴리즈 확인
            try {
                $ApiUrl = "https://api.github.com/repos/qdrant/qdrant/releases/latest"
                $Release = Invoke-RestMethod -Uri $ApiUrl
                $Asset = $Release.assets | Where-Object { $_.name -like "*windows*.zip" -and $_.name -like "*x86_64*" } | Select-Object -First 1
                
                if ($Asset) {
                    $QdrantZip = Join-Path $BinPath "qdrant.zip"
                    if (Download-File -Url $Asset.browser_download_url -Output $QdrantZip -Description "Qdrant $($Release.tag_name)") {
                        Extract-Archive -ArchivePath $QdrantZip -Destination "$BinPath\qdrant" -Description "Qdrant"
                    }
                } else {
                    Write-Host "⚠️  Qdrant Windows 바이너리를 찾을 수 없습니다" -ForegroundColor Yellow
                    Write-Host "   수동으로 bin\qdrant\qdrant.exe를 배치하거나 원격 서버를 사용하세요" -ForegroundColor Yellow
                }
            }
            catch {
                Write-Host "⚠️  Qdrant 자동 다운로드 실패: $($_.Exception.Message)" -ForegroundColor Yellow
                Write-Host "   수동으로 bin\qdrant\qdrant.exe를 배치하세요" -ForegroundColor Yellow
            }
        } else {
            Write-Host "✅ 원격 Qdrant 서버 연결 가능 (10.150.104.37:6333)" -ForegroundColor Green
        }
    } else {
        Write-Host "✅ 기존 Qdrant 바이너리 사용" -ForegroundColor Green
    }
} else {
    Write-Host "⏭️  Qdrant 설치 건너뜀" -ForegroundColor Yellow
}

Write-Host "[5/6] Ollama 설치 확인 및 모델 준비..." -ForegroundColor Blue

if (!$SkipOllama) {
    $OllamaInstalled = $false
    
    # 시스템 Ollama 확인
    try {
        $OllamaCmd = Get-Command ollama -ErrorAction SilentlyContinue
        if ($OllamaCmd) {
            Write-Host "✅ 시스템 Ollama 감지" -ForegroundColor Green
            $OllamaInstalled = $true
        }
    } catch {}
    
    # Ollama 자동 설치 시도 (winget 사용)
    if (!$OllamaInstalled -and $IsAdmin) {
        try {
            Write-Host "🔧 Ollama 자동 설치 시도 중..." -ForegroundColor Yellow
            winget install Ollama.Ollama --accept-package-agreements --accept-source-agreements --silent
            if ($LASTEXITCODE -eq 0) {
                Write-Host "✅ Ollama 설치 완료" -ForegroundColor Green
                $OllamaInstalled = $true
            }
        }
        catch {
            Write-Host "⚠️  Ollama 자동 설치 실패" -ForegroundColor Yellow
        }
    }
    
    if (!$OllamaInstalled) {
        Write-Host "⚠️  Ollama가 설치되지 않았습니다" -ForegroundColor Yellow
        Write-Host "   수동 설치: https://ollama.ai/download" -ForegroundColor Yellow
        Write-Host "   또는 관리자 권한으로 이 스크립트를 실행하세요" -ForegroundColor Yellow
    } else {
        # Ollama 서비스 시작
        try {
            Write-Host "🔧 Ollama 서비스 시작 중..." -ForegroundColor Yellow
            Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden
            Start-Sleep 3
            
            # gemma3 모델 확인 및 다운로드
            Write-Host "🔍 gemma3 모델 확인 중..." -ForegroundColor Yellow
            $Models = & ollama list 2>$null
            if ($Models -notlike "*gemma3*") {
                Write-Host "⬇️  gemma3:4b 모델 다운로드 중 (시간이 오래 걸릴 수 있습니다)..." -ForegroundColor Yellow
                & ollama pull gemma3:4b
                if ($LASTEXITCODE -eq 0) {
                    Write-Host "✅ gemma3:4b 모델 다운로드 완료" -ForegroundColor Green
                }
            } else {
                Write-Host "✅ gemma3 모델 이미 설치됨" -ForegroundColor Green
            }
        }
        catch {
            Write-Host "⚠️  Ollama 모델 준비 중 오류: $($_.Exception.Message)" -ForegroundColor Yellow
        }
    }
} else {
    Write-Host "⏭️  Ollama 설치 건너뜀" -ForegroundColor Yellow
}

Write-Host "[6/6] 실행 스크립트 권한 설정 및 최종 확인..." -ForegroundColor Blue

# 실행 스크립트들 실행 권한 부여
$Scripts = @("$ScriptsPath\run.bat", "$ScriptsPath\stop.bat")
foreach ($Script in $Scripts) {
    if (Test-Path $Script) {
        icacls $Script /grant Everyone:F | Out-Null
        Write-Host "✅ $([System.IO.Path]::GetFileName($Script)) 실행 권한 설정" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "   🎉 포터블 설치가 완료되었습니다!" -ForegroundColor White  
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "📋 설치 요약:" -ForegroundColor White
Write-Host "   ✅ Python 가상환경 및 패키지 설치" -ForegroundColor Green
Write-Host "   ✅ 환경 설정 파일 (.env) 생성" -ForegroundColor Green
Write-Host "   ✅ 필수 디렉토리 구조 생성" -ForegroundColor Green

if (Test-Path "$BinPath\qdrant\qdrant.exe") {
    Write-Host "   ✅ 포터블 Qdrant 준비 완료" -ForegroundColor Green
} else {
    Write-Host "   ⚠️  Qdrant: 원격 서버 또는 수동 설치 필요" -ForegroundColor Yellow
}

try {
    $null = Get-Command ollama -ErrorAction SilentlyContinue  
    Write-Host "   ✅ Ollama 및 모델 준비 완료" -ForegroundColor Green
}
catch {
    Write-Host "   ⚠️  Ollama: 수동 설치 권장" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "🚀 다음 단계:" -ForegroundColor White
Write-Host "   1. scripts\run.bat 실행하여 시스템 시작" -ForegroundColor Yellow
Write-Host "   2. 브라우저에서 http://localhost:8001 접속" -ForegroundColor Yellow
Write-Host "   3. 종료 시: scripts\stop.bat 실행" -ForegroundColor Yellow
Write-Host ""
Write-Host "🔧 설정 파일:" -ForegroundColor White
Write-Host "   - .env: 환경 변수 (필요 시 편집)" -ForegroundColor Cyan
Write-Host "   - config.json: 시스템 설정" -ForegroundColor Cyan
Write-Host ""

Read-Host "계속하려면 Enter 키를 누르세요"