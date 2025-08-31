# ================================================================
# HD현대미포 Gauss-1 RAG System - 무결성 검증 스크립트
# SHA256 해시 검증으로 파일 무결성 확인
# ================================================================

param(
    [switch]$GenerateHashes,
    [switch]$Detailed,
    [string]$HashFile = "file_hashes.json"
)

$rootPath = Split-Path $PSScriptRoot -Parent
$hashFilePath = Join-Path $rootPath $HashFile

# 색상 출력 함수
function Write-ColorText($text, $color) {
    Write-Host $text -ForegroundColor $color
}

function Write-Status($message, $status) {
    switch ($status) {
        "OK" { Write-Host "✅ $message" -ForegroundColor Green }
        "FAIL" { Write-Host "❌ $message" -ForegroundColor Red }
        "WARN" { Write-Host "⚠️ $message" -ForegroundColor Yellow }
        "INFO" { Write-Host "ℹ️ $message" -ForegroundColor Cyan }
    }
}

# 해시 계산 함수
function Get-FileHashSHA256($filePath) {
    if (Test-Path $filePath) {
        try {
            $hash = Get-FileHash -Path $filePath -Algorithm SHA256
            return $hash.Hash
        } catch {
            Write-Warning "해시 계산 실패: $filePath - $_"
            return $null
        }
    }
    return $null
}

Write-ColorText "🔍 HD현대미포 Gauss-1 RAG 시스템 무결성 검증" "Cyan"
Write-ColorText "검증 경로: $rootPath" "Yellow"
Write-Host ""

# 검증 대상 파일 목록
$criticalFiles = @{
    # 실행 스크립트
    "scripts\run.bat" = "메인 실행 스크립트"
    "scripts\run_gui_debug.bat" = "GUI 디버그 스크립트"
    "scripts\stop.bat" = "전체 중지 스크립트"
    "scripts\run_qdrant.bat" = "Qdrant 테스트 스크립트"
    "scripts\run_ollama.bat" = "Ollama 테스트 스크립트"
    "scripts\self_check.ps1" = "시스템 자가진단 스크립트"
    "scripts\install_offline.ps1" = "오프라인 설치 스크립트"
    
    # 설정 파일
    ".env" = "환경 설정 파일"
    "bin\qdrant\qdrant.yaml" = "Qdrant 설정 파일"
    "manifest.json" = "패키지 매니페스트"
    
    # 핵심 애플리케이션
    "backend\main.py" = "FastAPI 메인 서버"
    "backend\resource_manager.py" = "리소스 관리자"
    "backend\security.py" = "보안 미들웨어"
    "backend\security_config.py" = "보안 설정"
    "backend\requirements.lock.txt" = "Python 의존성 락파일"
    
    # GUI 애플리케이션
    "src\HDLLM.py" = "메인 GUI 애플리케이션"
    "src\ui_user_tab.py" = "사용자 인터페이스 탭"
    "src\parsers\01_seongak_parser.py" = "선각 회의록 파서"
    "src\parsers\02_default_parser.py" = "기본 문서 파서"
    
    # 웹 인터페이스
    "frontend\index.html" = "웹 UI 메인 페이지"
    "frontend\favicon.ico" = "웹 파비콘"
}

# 바이너리 파일들 (선택적 검증)
$binaryFiles = @{
    "bin\python311\python.exe" = "Python 실행파일"
    "bin\qdrant\qdrant.exe" = "Qdrant 벡터 DB"
    "bin\ollama\ollama.exe" = "Ollama LLM 서버"
}

# 모델 파일들 (크기만 확인)
$modelDirectories = @{
    "models\embeddings\bge-m3" = "BGE-M3 임베딩 모델"
    "models\ollama\gemma3-4b" = "Gemma3-4b 언어 모델"
}

# 해시 파일 생성 모드
if ($GenerateHashes) {
    Write-Status "해시 파일 생성 모드 시작" "INFO"
    
    $hashData = @{
        "generated_at" = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
        "version" = "1.0.0"
        "files" = @{}
        "binaries" = @{}
        "models" = @{}
    }
    
    # 핵심 파일 해시 생성
    Write-Status "핵심 파일 해시 계산 중..." "INFO"
    foreach ($file in $criticalFiles.GetEnumerator()) {
        $filePath = Join-Path $rootPath $file.Key
        $hash = Get-FileHashSHA256 $filePath
        if ($hash) {
            $hashData.files[$file.Key] = @{
                "hash" = $hash
                "description" = $file.Value
                "size" = (Get-Item $filePath).Length
            }
            Write-Status "✓ $($file.Key)" "OK"
        } else {
            Write-Status "✗ $($file.Key) - 파일 없음" "WARN"
        }
    }
    
    # 바이너리 파일 해시 생성
    Write-Status "바이너리 파일 해시 계산 중..." "INFO"
    foreach ($binary in $binaryFiles.GetEnumerator()) {
        $filePath = Join-Path $rootPath $binary.Key
        $hash = Get-FileHashSHA256 $filePath
        if ($hash) {
            $hashData.binaries[$binary.Key] = @{
                "hash" = $hash
                "description" = $binary.Value
                "size" = (Get-Item $filePath).Length
                "version" = try { (Get-Item $filePath).VersionInfo.ProductVersion } catch { "Unknown" }
            }
            Write-Status "✓ $($binary.Key)" "OK"
        } else {
            Write-Status "✗ $($binary.Key) - 파일 없음" "WARN"
        }
    }
    
    # 모델 디렉토리 정보 수집
    Write-Status "모델 디렉토리 정보 수집 중..." "INFO"
    foreach ($modelDir in $modelDirectories.GetEnumerator()) {
        $dirPath = Join-Path $rootPath $modelDir.Key
        if (Test-Path $dirPath) {
            $files = Get-ChildItem $dirPath -Recurse -File
            $totalSize = ($files | Measure-Object -Property Length -Sum).Sum
            $fileCount = $files.Count
            
            $hashData.models[$modelDir.Key] = @{
                "description" = $modelDir.Value
                "file_count" = $fileCount
                "total_size" = $totalSize
                "last_modified" = (Get-Item $dirPath).LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss")
            }
            Write-Status "✓ $($modelDir.Key) - $fileCount 파일, $([math]::Round($totalSize/1MB, 2))MB" "OK"
        } else {
            Write-Status "✗ $($modelDir.Key) - 디렉토리 없음" "WARN"
        }
    }
    
    # 해시 파일 저장
    try {
        $hashData | ConvertTo-Json -Depth 4 | Out-File $hashFilePath -Encoding UTF8
        Write-Status "해시 파일 생성 완료: $HashFile" "OK"
    } catch {
        Write-Status "해시 파일 저장 실패: $_" "FAIL"
        exit 1
    }
    
    return
}

# 해시 검증 모드
if (-not (Test-Path $hashFilePath)) {
    Write-Status "해시 파일이 없습니다: $HashFile" "WARN"
    Write-Status "해시 파일을 생성하려면 -GenerateHashes 옵션을 사용하세요." "INFO"
    Write-Status "예: .\verify_hashes.ps1 -GenerateHashes" "INFO"
    return
}

# 해시 파일 로드
try {
    $savedHashes = Get-Content $hashFilePath -Encoding UTF8 | ConvertFrom-Json
    Write-Status "해시 파일 로드됨 (생성일: $($savedHashes.generated_at))" "INFO"
} catch {
    Write-Status "해시 파일 로드 실패: $_" "FAIL"
    exit 1
}

Write-Host ""
Write-Status "무결성 검증 시작..." "INFO"

$verificationResults = @{
    "passed" = 0
    "failed" = 0
    "missing" = 0
    "total" = 0
}

# 핵심 파일 검증
Write-Status "핵심 파일 검증 중..." "INFO"
Write-Host ""

foreach ($file in $savedHashes.files.PSObject.Properties) {
    $filePath = Join-Path $rootPath $file.Name
    $savedData = $file.Value
    $verificationResults.total++
    
    if (-not (Test-Path $filePath)) {
        Write-Status "$($file.Name) - 파일 누락" "FAIL"
        $verificationResults.missing++
        continue
    }
    
    $currentHash = Get-FileHashSHA256 $filePath
    if (-not $currentHash) {
        Write-Status "$($file.Name) - 해시 계산 실패" "FAIL"
        $verificationResults.failed++
        continue
    }
    
    if ($currentHash -eq $savedData.hash) {
        if ($Detailed) {
            Write-Status "$($file.Name) - 무결성 확인" "OK"
        }
        $verificationResults.passed++
    } else {
        Write-Status "$($file.Name) - 해시 불일치" "FAIL"
        if ($Detailed) {
            Write-Host "   예상: $($savedData.hash)"
            Write-Host "   실제: $currentHash"
        }
        $verificationResults.failed++
    }
}

# 바이너리 파일 검증
if ($savedHashes.binaries -and $savedHashes.binaries.PSObject.Properties.Count -gt 0) {
    Write-Host ""
    Write-Status "바이너리 파일 검증 중..." "INFO"
    
    foreach ($binary in $savedHashes.binaries.PSObject.Properties) {
        $filePath = Join-Path $rootPath $binary.Name
        $savedData = $binary.Value
        $verificationResults.total++
        
        if (-not (Test-Path $filePath)) {
            Write-Status "$($binary.Name) - 바이너리 누락" "FAIL"
            $verificationResults.missing++
            continue
        }
        
        $currentHash = Get-FileHashSHA256 $filePath
        if (-not $currentHash) {
            Write-Status "$($binary.Name) - 해시 계산 실패" "FAIL"
            $verificationResults.failed++
            continue
        }
        
        if ($currentHash -eq $savedData.hash) {
            if ($Detailed) {
                Write-Status "$($binary.Name) - 바이너리 무결성 확인" "OK"
            }
            $verificationResults.passed++
        } else {
            Write-Status "$($binary.Name) - 바이너리 해시 불일치" "FAIL"
            $verificationResults.failed++
        }
    }
}

# 모델 디렉토리 검증
if ($savedHashes.models -and $savedHashes.models.PSObject.Properties.Count -gt 0) {
    Write-Host ""
    Write-Status "모델 디렉토리 검증 중..." "INFO"
    
    foreach ($model in $savedHashes.models.PSObject.Properties) {
        $dirPath = Join-Path $rootPath $model.Name
        $savedData = $model.Value
        
        if (-not (Test-Path $dirPath)) {
            Write-Status "$($model.Name) - 모델 디렉토리 누락" "WARN"
            continue
        }
        
        $files = Get-ChildItem $dirPath -Recurse -File
        $currentFileCount = $files.Count
        $currentTotalSize = ($files | Measure-Object -Property Length -Sum).Sum
        
        if ($currentFileCount -eq $savedData.file_count -and $currentTotalSize -eq $savedData.total_size) {
            if ($Detailed) {
                Write-Status "$($model.Name) - 모델 무결성 확인 ($currentFileCount 파일)" "OK"
            }
        } else {
            Write-Status "$($model.Name) - 모델 파일 불일치" "WARN"
            if ($Detailed) {
                Write-Host "   예상: $($savedData.file_count) 파일, $([math]::Round($savedData.total_size/1MB, 2))MB"
                Write-Host "   실제: $currentFileCount 파일, $([math]::Round($currentTotalSize/1MB, 2))MB"
            }
        }
    }
}

# 검증 결과 요약
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Status "무결성 검증 완료" "INFO"
Write-Host ""

Write-ColorText "📊 검증 결과:" "Yellow"
Write-Host "   • 전체 파일: $($verificationResults.total)" -ForegroundColor White
Write-Host "   • 통과: $($verificationResults.passed)" -ForegroundColor Green
Write-Host "   • 실패: $($verificationResults.failed)" -ForegroundColor Red
Write-Host "   • 누락: $($verificationResults.missing)" -ForegroundColor Yellow

$successRate = if ($verificationResults.total -gt 0) { 
    [math]::Round(($verificationResults.passed / $verificationResults.total) * 100, 1) 
} else { 0 }

Write-Host "   • 성공률: $successRate%" -ForegroundColor $(if ($successRate -eq 100) { "Green" } elseif ($successRate -ge 90) { "Yellow" } else { "Red" })

# 최종 결과
if ($verificationResults.failed -eq 0 -and $verificationResults.missing -eq 0) {
    Write-Host ""
    Write-Status "🎉 모든 파일의 무결성이 확인되었습니다!" "OK"
    $exitCode = 0
} elseif ($verificationResults.failed -gt 0) {
    Write-Host ""
    Write-Status "⚠️ 일부 파일의 무결성에 문제가 있습니다." "FAIL"
    Write-Status "배포 패키지를 다시 확인하거나 재설치하세요." "INFO"
    $exitCode = 1
} else {
    Write-Host ""
    Write-Status "⚠️ 일부 파일이 누락되었습니다." "WARN"
    Write-Status "설치를 완료하거나 누락된 파일을 추가하세요." "INFO"
    $exitCode = 2
}

Write-Host ""
Write-Status "권장 사항:" "INFO"
Write-Host "   • 정기적으로 무결성 검증을 실행하세요"
Write-Host "   • 파일 변경 후에는 새로운 해시를 생성하세요"
Write-Host "   • 중요한 변경사항은 백업을 생성하세요"

exit $exitCode