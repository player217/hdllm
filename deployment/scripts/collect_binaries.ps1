# HD Gauss-1 바이너리 수집 스크립트
# PowerShell 7+ 권장

param(
    [string]$OutputPath = ".\HDGauss1_Standalone_v1.0",
    [switch]$DownloadModels = $false,
    [switch]$Force = $false
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "Continue"

# 색상 출력 함수
function Write-ColorOutput {
    param([string]$Text, [string]$Color = "White")
    Write-Host $Text -ForegroundColor $Color
}

# 디렉토리 생성 함수
function Ensure-Directory {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
        Write-ColorOutput "✓ 디렉토리 생성: $Path" "Green"
    }
}

# 다운로드 함수
function Download-File {
    param(
        [string]$Url,
        [string]$OutputFile,
        [string]$Description
    )
    
    if (Test-Path $OutputFile -and -not $Force) {
        Write-ColorOutput "⚠ 이미 존재: $Description" "Yellow"
        return
    }
    
    Write-ColorOutput "⬇ 다운로드 중: $Description" "Cyan"
    try {
        $ProgressPreference = 'SilentlyContinue'
        Invoke-WebRequest -Uri $Url -OutFile $OutputFile -UseBasicParsing
        $ProgressPreference = 'Continue'
        Write-ColorOutput "✓ 완료: $Description" "Green"
    } catch {
        Write-ColorOutput "✗ 실패: $Description - $_" "Red"
        throw
    }
}

Write-ColorOutput "`n==========================================" "Magenta"
Write-ColorOutput "   HD Gauss-1 바이너리 수집 시작" "Magenta"
Write-ColorOutput "==========================================`n" "Magenta"

# 기본 디렉토리 구조 생성
Write-ColorOutput "[1/7] 디렉토리 구조 생성 중..." "White"
$directories = @(
    "$OutputPath",
    "$OutputPath\components",
    "$OutputPath\components\app",
    "$OutputPath\components\python",
    "$OutputPath\components\qdrant",
    "$OutputPath\components\ollama",
    "$OutputPath\components\models",
    "$OutputPath\components\models\bge-m3",
    "$OutputPath\components\dependencies",
    "$OutputPath\components\data",
    "$OutputPath\scripts",
    "$OutputPath\docs",
    "$OutputPath\temp"
)

foreach ($dir in $directories) {
    Ensure-Directory $dir
}

# Python 3.11 임베디드 다운로드
Write-ColorOutput "`n[2/7] Python 3.11 임베디드 배포판 다운로드 중..." "White"
$pythonUrl = "https://www.python.org/ftp/python/3.11.7/python-3.11.7-embed-amd64.zip"
$pythonZip = "$OutputPath\temp\python-3.11.7-embed-amd64.zip"

Download-File -Url $pythonUrl -OutputFile $pythonZip -Description "Python 3.11.7 (약 15MB)"

if (Test-Path $pythonZip) {
    Write-ColorOutput "압축 해제 중..." "Gray"
    Expand-Archive -Path $pythonZip -DestinationPath "$OutputPath\components\python" -Force
    
    # pip 활성화
    $pthFile = "$OutputPath\components\python\python311._pth"
    if (Test-Path $pthFile) {
        $content = Get-Content $pthFile
        $content = $content -replace "#import site", "import site"
        Set-Content -Path $pthFile -Value $content
        Write-ColorOutput "✓ pip 활성화 완료" "Green"
    }
}

# Qdrant 다운로드
Write-ColorOutput "`n[3/7] Qdrant 벡터 DB 다운로드 중..." "White"
$qdrantVersion = "v1.7.4"
$qdrantUrl = "https://github.com/qdrant/qdrant/releases/download/$qdrantVersion/qdrant-x86_64-pc-windows-msvc.zip"
$qdrantZip = "$OutputPath\temp\qdrant.zip"

Download-File -Url $qdrantUrl -OutputFile $qdrantZip -Description "Qdrant $qdrantVersion (약 50MB)"

if (Test-Path $qdrantZip) {
    Write-ColorOutput "압축 해제 중..." "Gray"
    Expand-Archive -Path $qdrantZip -DestinationPath "$OutputPath\components\qdrant" -Force
    Write-ColorOutput "✓ Qdrant 설치 완료" "Green"
}

# Ollama 다운로드
Write-ColorOutput "`n[4/7] Ollama LLM 서버 다운로드 중..." "White"
$ollamaUrl = "https://github.com/ollama/ollama/releases/latest/download/OllamaSetup.exe"
$ollamaSetup = "$OutputPath\temp\OllamaSetup.exe"

Download-File -Url $ollamaUrl -OutputFile $ollamaSetup -Description "Ollama 설치 파일 (약 500MB)"

# Ollama 포터블 추출 (수동 필요)
Write-ColorOutput "⚠ Ollama는 수동 추출이 필요합니다:" "Yellow"
Write-ColorOutput "  1. $ollamaSetup 실행" "Gray"
Write-ColorOutput "  2. $OutputPath\components\ollama 에 설치" "Gray"
Write-ColorOutput "  3. 설치 완료 후 이 스크립트 재실행" "Gray"

# Visual C++ Redistributable 다운로드
Write-ColorOutput "`n[5/7] Visual C++ Redistributable 다운로드 중..." "White"
$vcredistUrl = "https://aka.ms/vs/17/release/vc_redist.x64.exe"
$vcredistExe = "$OutputPath\components\dependencies\vcredist_x64.exe"

Ensure-Directory "$OutputPath\components\dependencies"
Download-File -Url $vcredistUrl -OutputFile $vcredistExe -Description "VC++ Redistributable (약 25MB)"

# 모델 다운로드 (선택적)
if ($DownloadModels) {
    Write-ColorOutput "`n[6/7] AI 모델 다운로드 중..." "White"
    
    # BGE-M3 모델 다운로드 스크립트 생성
    $downloadModelScript = @'
import os
import sys
from huggingface_hub import snapshot_download

def download_bge_m3(output_path):
    print("BGE-M3 모델 다운로드 중...")
    try:
        snapshot_download(
            repo_id="BAAI/bge-m3",
            local_dir=output_path,
            local_dir_use_symlinks=False,
            ignore_patterns=["*.msgpack", "*.h5", "*.safetensors", "*.onnx", "flax_model.msgpack", "rust_model.ot"]
        )
        print("✓ BGE-M3 모델 다운로드 완료")
    except Exception as e:
        print(f"✗ BGE-M3 모델 다운로드 실패: {e}")
        sys.exit(1)

if __name__ == "__main__":
    output_path = sys.argv[1] if len(sys.argv) > 1 else "./models/bge-m3"
    download_bge_m3(output_path)
'@
    
    $scriptPath = "$OutputPath\temp\download_models.py"
    Set-Content -Path $scriptPath -Value $downloadModelScript
    
    Write-ColorOutput "BGE-M3 모델 다운로드 중 (약 1.5GB)..." "Cyan"
    Write-ColorOutput "⚠ huggingface-hub 패키지 필요: pip install huggingface-hub" "Yellow"
    
    # Gemma3:4b 모델 다운로드 안내
    Write-ColorOutput "`n⚠ Gemma3:4b 모델 다운로드:" "Yellow"
    Write-ColorOutput "  1. Ollama 설치 후 실행: ollama pull gemma3:4b" "Gray"
    Write-ColorOutput "  2. 모델 위치: %USERPROFILE%\.ollama\models" "Gray"
    Write-ColorOutput "  3. $OutputPath\components\ollama\models 로 복사" "Gray"
}

# 의존성 패키지 수집
Write-ColorOutput "`n[7/7] Python 패키지 의존성 준비 중..." "White"

# requirements.txt 생성
$requirements = @"
fastapi==0.104.1
uvicorn[standard]==0.24.0
qdrant-client==1.7.0
langchain-huggingface==0.0.3
torch==2.1.0+cpu
torchvision==0.16.0+cpu
torchaudio==2.1.0+cpu
requests==2.31.0
pywin32==306
python-multipart==0.0.6
sentence-transformers==2.2.2
transformers==4.36.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
prometheus-client==0.20.0
pytest==7.4.3
pytest-asyncio==0.21.1
asgi-lifespan==2.1.0
httpx==0.25.2
sentencepiece==0.1.99
tika==2.6.0
openpyxl==3.1.2
xlwings==0.30.13
extract-msg==0.47.0
PySide6==6.6.1
tqdm==4.66.1
langchain==0.1.0
langchain-community==0.0.10
customtkinter==5.2.1
"@

$reqPath = "$OutputPath\requirements.txt"
Set-Content -Path $reqPath -Value $requirements
Write-ColorOutput "✓ requirements.txt 생성 완료" "Green"

# 패키지 설치 스크립트
$installPackagesScript = @"
@echo off
echo Python 패키지 설치 중...
set PYTHONPATH=$OutputPath\components\dependencies\site-packages

REM pip 설치
python -m ensurepip
python -m pip install --upgrade pip

REM 패키지 설치 (CPU 버전)
pip install --no-deps -r requirements.txt --target "%PYTHONPATH%"
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu --target "%PYTHONPATH%"

echo 완료!
pause
"@

$installScript = "$OutputPath\scripts\install_packages.bat"
Set-Content -Path $installScript -Value $installPackagesScript
Write-ColorOutput "✓ 패키지 설치 스크립트 생성: $installScript" "Green"

# 정리
Write-ColorOutput "`n정리 중..." "Gray"
if (Test-Path "$OutputPath\temp" -and -not $DownloadModels) {
    # temp 폴더는 모델 다운로드 시 필요하므로 옵션에 따라 처리
    Write-ColorOutput "⚠ temp 폴더 유지 (수동 작업 필요)" "Yellow"
}

# 완료 메시지
Write-ColorOutput "`n==========================================" "Magenta"
Write-ColorOutput "   ✅ 바이너리 수집 완료!" "Green"
Write-ColorOutput "==========================================" "Magenta"

Write-ColorOutput "`n다음 단계:" "White"
Write-ColorOutput "1. Ollama 수동 설치 필요" "Yellow"
Write-ColorOutput "2. 모델 다운로드: -DownloadModels 플래그 사용" "Yellow"
Write-ColorOutput "3. Python 패키지 설치: $installScript 실행" "Yellow"
Write-ColorOutput "4. PyInstaller로 exe 빌드" "Yellow"

Write-ColorOutput "`n출력 경로: $OutputPath" "Cyan"

# 크기 정보
$size = (Get-ChildItem -Path $OutputPath -Recurse | Measure-Object -Property Length -Sum).Sum / 1GB
Write-ColorOutput "현재 크기: $([math]::Round($size, 2)) GB" "Gray"