# ================================================================================================
#  HD현대미포 Gauss-1 RAG System - 시스템 자가 진단 스크립트
#  배포 패키지 완정성, 포트 충돌, 모델 캐시 확인
# ================================================================================================

param(
    [switch]$Detailed = $false,  # 상세 검사 모드
    [switch]$Fix = $false        # 자동 수정 시도
)

$ErrorActionPreference = "Continue"
$Host.UI.RawUI.WindowTitle = "HD Gauss-1 Self Check"

Write-Host "============================================================" -ForegroundColor Magenta
Write-Host "   HD현대미포 Gauss-1 RAG System - 자가 진단" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Magenta
Write-Host ""

# 진단 결과 저장
$results = @{
    "Essential Files" = @()
    "Port Conflicts" = @()
    "Model Cache" = @()
    "Permissions" = @()
    "System Info" = @()
}

# 루트 디렉토리 설정
$rootPath = Split-Path -Parent $PSScriptRoot
Set-Location $rootPath

Write-Host "[1/6] 필수 파일 존재 확인..." -ForegroundColor Yellow

# 필수 파일 목록
$requiredFiles = @(
    ".env",
    "bin/python311/python.exe", 
    "bin/qdrant/qdrant.exe",
    "bin/ollama/ollama.exe",
    "backend/main.py",
    "src/HDLLM.py"
)

$missingFiles = @()
foreach ($file in $requiredFiles) {
    if (Test-Path $file) {
        Write-Host "   ✓ $file" -ForegroundColor Green
        $results["Essential Files"] += "OK: $file"
    } else {
        Write-Host "   ✗ $file" -ForegroundColor Red
        $missingFiles += $file
        $results["Essential Files"] += "MISSING: $file"
    }
}

if ($missingFiles.Count -gt 0) {
    Write-Host ""
    Write-Host "[ERROR] 필수 파일이 누락되었습니다:" -ForegroundColor Red
    foreach ($file in $missingFiles) {
        Write-Host "  • $file" -ForegroundColor Red
    }
    Write-Host ""
}

Write-Host ""
Write-Host "[2/6] 포트 충돌 검사..." -ForegroundColor Yellow

# 포트 확인
$ports = @(6333, 8080, 8001, 11434)
$conflicts = @()

foreach ($port in $ports) {
    try {
        $connections = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
        if ($connections) {
            foreach ($conn in $connections) {
                $process = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
                if ($process) {
                    Write-Host "   ⚠ Port $port : $($process.ProcessName) (PID: $($process.Id))" -ForegroundColor Yellow
                    $results["Port Conflicts"] += "Port $port used by $($process.ProcessName) (PID: $($process.Id))"
                    $conflicts += $port
                }
            }
        } else {
            Write-Host "   ✓ Port $port : Available" -ForegroundColor Green
            $results["Port Conflicts"] += "Port $port: Available"
        }
    } catch {
        Write-Host "   ? Port $port : Cannot check" -ForegroundColor Gray
        $results["Port Conflicts"] += "Port $port: Check failed"
    }
}

Write-Host ""
Write-Host "[3/6] 모델 캐시 확인..." -ForegroundColor Yellow

# BGE-M3 모델 확인
$bgeM3Path = "models/embeddings/bge-m3"
if (Test-Path $bgeM3Path) {
    $bgeFiles = Get-ChildItem $bgeM3Path -Recurse -File | Measure-Object Length -Sum
    $bgeSizeMB = [math]::Round($bgeFiles.Sum / 1MB, 1)
    Write-Host "   ✓ BGE-M3 embedding model: $bgeSizeMB MB" -ForegroundColor Green
    $results["Model Cache"] += "BGE-M3: $bgeSizeMB MB"
} else {
    Write-Host "   ⚠ BGE-M3 embedding model cache not found" -ForegroundColor Yellow
    Write-Host "     경로: $bgeM3Path" -ForegroundColor Gray
    $results["Model Cache"] += "BGE-M3: Not found"
}

# Gemma3:4b 모델 확인  
$gemmaPath = "models/ollama"
if (Test-Path $gemmaPath) {
    $gemmaFiles = Get-ChildItem $gemmaPath -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum
    if ($gemmaFiles.Count -gt 0) {
        $gemmaSizeGB = [math]::Round($gemmaFiles.Sum / 1GB, 2)
        Write-Host "   ✓ Gemma3:4b model cache: $gemmaSizeGB GB" -ForegroundColor Green
        $results["Model Cache"] += "Gemma3:4b: $gemmaSizeGB GB"
    } else {
        Write-Host "   ⚠ Gemma3:4b model cache empty or not found" -ForegroundColor Yellow
        $results["Model Cache"] += "Gemma3:4b: Empty/Not found"
    }
} else {
    Write-Host "   ⚠ Ollama model directory not found" -ForegroundColor Yellow
    Write-Host "     경로: $gemmaPath" -ForegroundColor Gray  
    $results["Model Cache"] += "Gemma3:4b: Directory not found"
}

Write-Host ""
Write-Host "[4/6] 권한 및 쓰기 접근 확인..." -ForegroundColor Yellow

# 쓰기 권한 확인 
$testDirs = @("data/qdrant", "logs", "models/embeddings")
foreach ($dir in $testDirs) {
    if (-not (Test-Path $dir)) {
        try {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
            Write-Host "   ✓ Created directory: $dir" -ForegroundColor Green
            $results["Permissions"] += "Created: $dir"
        } catch {
            Write-Host "   ✗ Cannot create directory: $dir" -ForegroundColor Red
            $results["Permissions"] += "Failed to create: $dir"
        }
    }
    
    # 쓰기 테스트
    $testFile = "$dir/.write_test"
    try {
        "test" | Out-File -FilePath $testFile -Encoding UTF8
        Remove-Item $testFile -Force
        Write-Host "   ✓ Write access: $dir" -ForegroundColor Green
        $results["Permissions"] += "Write OK: $dir"
    } catch {
        Write-Host "   ✗ No write access: $dir" -ForegroundColor Red
        $results["Permissions"] += "Write Failed: $dir"
    }
}

Write-Host ""
Write-Host "[5/6] 시스템 정보 수집..." -ForegroundColor Yellow

# 시스템 정보
$systemInfo = @{
    "OS" = (Get-CimInstance -ClassName Win32_OperatingSystem).Caption
    "Version" = (Get-CimInstance -ClassName Win32_OperatingSystem).Version
    "Architecture" = $env:PROCESSOR_ARCHITECTURE
    "RAM (GB)" = [math]::Round((Get-CimInstance -ClassName Win32_PhysicalMemory | Measure-Object Capacity -Sum).Sum / 1GB, 1)
    "Free Disk (GB)" = [math]::Round((Get-WmiObject -Class Win32_LogicalDisk -Filter "DeviceID='C:'").FreeSpace / 1GB, 1)
}

foreach ($key in $systemInfo.Keys) {
    Write-Host "   $key : $($systemInfo[$key])" -ForegroundColor Cyan
    $results["System Info"] += "$key : $($systemInfo[$key])"
}

Write-Host ""
Write-Host "[6/6] 종합 진단 결과..." -ForegroundColor Yellow

# 종합 평가
$criticalIssues = $missingFiles.Count + ($results["Permissions"] | Where-Object { $_ -like "*Failed*" }).Count
$warnings = ($results["Model Cache"] | Where-Object { $_ -like "*Not found*" -or $_ -like "*Empty*" }).Count + $conflicts.Count

Write-Host ""
Write-Host "============================================================" -ForegroundColor Magenta

if ($criticalIssues -eq 0 -and $warnings -eq 0) {
    Write-Host "   ✅ 시스템 상태: 양호" -ForegroundColor Green
    Write-Host "   모든 검사를 통과했습니다." -ForegroundColor Green
} elseif ($criticalIssues -eq 0) {
    Write-Host "   ⚠️ 시스템 상태: 주의 ($warnings개 경고)" -ForegroundColor Yellow
    Write-Host "   기본 기능은 정상 작동하지만 일부 최적화가 필요합니다." -ForegroundColor Yellow
} else {
    Write-Host "   ❌ 시스템 상태: 문제 ($criticalIssues개 심각, $warnings개 경고)" -ForegroundColor Red  
    Write-Host "   즉시 조치가 필요한 문제가 있습니다." -ForegroundColor Red
}

Write-Host "============================================================" -ForegroundColor Magenta
Write-Host ""

# 자동 수정 제안
if ($Fix -and ($criticalIssues -gt 0 -or $warnings -gt 0)) {
    Write-Host "자동 수정을 시도하시겠습니까? (Y/N): " -ForegroundColor Yellow -NoNewline
    $response = Read-Host
    
    if ($response -eq 'Y' -or $response -eq 'y') {
        Write-Host "자동 수정 시도 중..." -ForegroundColor Yellow
        
        # 누락된 디렉토리 생성
        foreach ($dir in @("logs", "data/qdrant", "models/embeddings", "models/ollama")) {
            if (-not (Test-Path $dir)) {
                New-Item -ItemType Directory -Path $dir -Force | Out-Null
                Write-Host "   ✓ 디렉토리 생성: $dir" -ForegroundColor Green
            }
        }
        
        Write-Host "자동 수정 완료." -ForegroundColor Green
    }
}

# 상세 모드
if ($Detailed) {
    Write-Host ""
    Write-Host "=== 상세 진단 결과 ===" -ForegroundColor Cyan
    foreach ($category in $results.Keys) {
        Write-Host ""
        Write-Host "[$category]" -ForegroundColor Yellow
        foreach ($item in $results[$category]) {
            Write-Host "  $item" -ForegroundColor Gray
        }
    }
}

# 권장 사항
Write-Host ""
Write-Host "권장 사항:" -ForegroundColor Cyan
if ($missingFiles.Count -gt 0) {
    Write-Host "  • scripts\install_offline.ps1 실행하여 누락 파일 복구" -ForegroundColor White
}
if ($conflicts.Count -gt 0) {
    Write-Host "  • scripts\stop.bat 실행하여 포트 충돌 해결" -ForegroundColor White  
}
if (($results["Model Cache"] | Where-Object { $_ -like "*Not found*" }).Count -gt 0) {
    Write-Host "  • 모델 캐시 수동 다운로드 또는 첫 실행 시 자동 다운로드 대기" -ForegroundColor White
}

Write-Host ""
Write-Host "다음 단계:" -ForegroundColor Cyan
Write-Host "  1. scripts\run_gui_debug.bat으로 실행 테스트" -ForegroundColor White
Write-Host "  2. 문제 발생 시 logs\ 폴더 확인" -ForegroundColor White  
Write-Host "  3. README_DEPLOY.md 문서 참조" -ForegroundColor White

Write-Host ""
Write-Host "[완료] 자가 진단이 완료되었습니다." -ForegroundColor Green