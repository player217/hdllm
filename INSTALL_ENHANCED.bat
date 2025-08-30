@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1

:: HD현대미포 LLM RAG System - Enhanced One-Click Installer
:: Version 2.0 - Auto-download capabilities
:: Date: 2025-01-30

echo ============================================================
echo   HD현대미포 LLM RAG System - 원클릭 설치 프로그램 v2.0
echo ============================================================
echo.

:: Set working directory
cd /d "%~dp0"
set "ROOT_DIR=%cd%"
set "BIN_DIR=%ROOT_DIR%\bin"
set "VENV_DIR=%ROOT_DIR%\venv"

:: Create necessary directories
echo [1/8] 필요한 폴더 생성 중...
if not exist "%BIN_DIR%" mkdir "%BIN_DIR%"
if not exist "logs" mkdir "logs"
if not exist "storage" mkdir "storage"
if not exist "chunk_outputs" mkdir "chunk_outputs"
if not exist "email_attachments" mkdir "email_attachments"
echo     ✓ 폴더 생성 완료
echo.

:: ===== Python 3.11+ Check and Install =====
echo [2/8] Python 3.11+ 확인 및 설치...
python --version 2>nul | findstr /R "3\.1[1-9]" >nul
if errorlevel 1 (
    echo     Python 3.11+ 가 없습니다. 자동 설치를 시작합니다...
    
    :: Check if installer already exists
    if not exist "%BIN_DIR%\python-3.11.9-amd64.exe" (
        echo     Python 3.11.9 다운로드 중... (약 25MB)
        powershell -Command "& {
            $ProgressPreference = 'SilentlyContinue'
            try {
                Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile '%BIN_DIR%\python-3.11.9-amd64.exe'
                Write-Host '    ✓ 다운로드 완료' -ForegroundColor Green
            } catch {
                Write-Host '    ✗ 다운로드 실패: ' $_.Exception.Message -ForegroundColor Red
                exit 1
            }
        }"
    )
    
    echo     Python 설치 중... (관리자 권한 필요)
    "%BIN_DIR%\python-3.11.9-amd64.exe" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
    
    :: Refresh PATH
    set "PATH=%PATH%;%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts"
    
    :: Verify installation
    python --version >nul 2>&1
    if errorlevel 1 (
        echo     ✗ Python 설치 실패. 수동으로 설치해주세요.
        echo     다운로드: https://www.python.org/downloads/
        pause
        exit /b 1
    )
    echo     ✓ Python 3.11 설치 완료
) else (
    echo     ✓ Python 3.11+ 이미 설치됨
    python --version
)
echo.

:: ===== Virtual Environment Setup =====
echo [3/8] 가상환경 설정...
if exist "%VENV_DIR%" (
    echo     기존 가상환경 발견. 재사용합니다.
) else (
    echo     새 가상환경 생성 중...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo     ✗ 가상환경 생성 실패
        pause
        exit /b 1
    )
    echo     ✓ 가상환경 생성 완료
)

:: Activate virtual environment
call "%VENV_DIR%\Scripts\activate.bat"
echo     ✓ 가상환경 활성화
echo.

:: ===== Pip Upgrade and Dependencies =====
echo [4/8] Python 패키지 설치...
echo     pip 업그레이드 중...
python -m pip install --upgrade pip --quiet

echo     필수 패키지 설치 중... (5-10분 소요)
if exist "requirements.txt" (
    pip install -r requirements.txt --quiet
) else (
    :: Create minimal requirements.txt
    (
        echo fastapi==0.104.1
        echo uvicorn[standard]==0.24.0
        echo qdrant-client==1.7.0
        echo sentence-transformers
        echo torch
        echo langchain-huggingface==0.0.3
        echo requests==2.31.0
        echo pywin32==306
        echo python-multipart==0.0.6
        echo transformers
        echo sentencepiece
        echo tika
        echo openpyxl
        echo xlwings
        echo extract-msg
        echo PySide6
        echo tqdm
        echo langchain
        echo langchain-community
    ) > requirements.txt
    pip install -r requirements.txt --quiet
)
echo     ✓ 패키지 설치 완료
echo.

:: ===== Qdrant Installation =====
echo [5/8] Qdrant 벡터 DB 설치...
if exist "%BIN_DIR%\qdrant.exe" (
    echo     ✓ Qdrant 이미 설치됨
) else (
    echo     Qdrant 다운로드 중... (약 50MB)
    powershell -Command "& {
        $ProgressPreference = 'SilentlyContinue'
        try {
            # Get latest Qdrant release URL
            $release = Invoke-RestMethod -Uri 'https://api.github.com/repos/qdrant/qdrant/releases/latest'
            $asset = $release.assets | Where-Object { $_.name -like '*windows*x86_64*' } | Select-Object -First 1
            if ($asset) {
                Invoke-WebRequest -Uri $asset.browser_download_url -OutFile '%BIN_DIR%\qdrant.zip'
                Expand-Archive -Path '%BIN_DIR%\qdrant.zip' -DestinationPath '%BIN_DIR%' -Force
                Remove-Item '%BIN_DIR%\qdrant.zip'
                Write-Host '    ✓ Qdrant 다운로드 완료' -ForegroundColor Green
            } else {
                Write-Host '    ✗ Qdrant 다운로드 URL을 찾을 수 없습니다' -ForegroundColor Red
            }
        } catch {
            Write-Host '    ✗ Qdrant 다운로드 실패: ' $_.Exception.Message -ForegroundColor Red
            Write-Host '' 
            Write-Host '    ⚠️  오프라인 모드 안내 ⚠️' -ForegroundColor Yellow
            Write-Host '    네트워크 연결이 불안정하거나 방화벽으로 인해 다운로드가 실패했습니다.' -ForegroundColor Yellow
            Write-Host '    다음 중 한 가지 방법을 선택하세요:' -ForegroundColor White
            Write-Host ''
            Write-Host '    1) 네트워크 연결 확인 후 다시 실행' -ForegroundColor Cyan  
            Write-Host '    2) 수동 설치: https://github.com/qdrant/qdrant/releases' -ForegroundColor Cyan
            Write-Host '       - qdrant-x86_64-pc-windows-msvc.zip 다운로드' -ForegroundColor Gray
            Write-Host '       - bin 폴더에 압축 해제' -ForegroundColor Gray
            Write-Host '    3) 개인 DB만 사용하여 오프라인 모드로 계속 진행' -ForegroundColor Cyan
            Write-Host ''
        }
    }"
)
echo.

:: ===== Ollama Installation =====
echo [6/8] Ollama LLM 서버 설치...
where ollama >nul 2>&1
if %errorlevel% equ 0 (
    echo     ✓ Ollama 이미 설치됨
) else (
    echo     Ollama 설치 프로그램 다운로드 중... (약 130MB)
    if not exist "%BIN_DIR%\OllamaSetup.exe" (
        powershell -Command "& {
            $ProgressPreference = 'SilentlyContinue'
            try {
                Invoke-WebRequest -Uri 'https://ollama.com/download/OllamaSetup.exe' -OutFile '%BIN_DIR%\OllamaSetup.exe'
                Write-Host '    ✓ 다운로드 완료' -ForegroundColor Green
            } catch {
                Write-Host '    ✗ Ollama 다운로드 실패: ' $_.Exception.Message -ForegroundColor Red
                Write-Host ''
                Write-Host '    ⚠️  오프라인 모드 안내 ⚠️' -ForegroundColor Yellow
                Write-Host '    네트워크 연결 문제로 Ollama 다운로드가 실패했습니다.' -ForegroundColor Yellow
                Write-Host '    다음 중 한 가지 방법을 선택하세요:' -ForegroundColor White
                Write-Host ''
                Write-Host '    1) 네트워크 연결 확인 후 다시 실행' -ForegroundColor Cyan
                Write-Host '    2) 수동 설치: https://ollama.com/download' -ForegroundColor Cyan  
                Write-Host '       - OllamaSetup.exe 다운로드 및 설치' -ForegroundColor Gray
                Write-Host '    3) 로컬 LLM 없이 임베딩만 사용하여 계속 진행' -ForegroundColor Cyan
                Write-Host ''
            }
        }"
    )
    
    echo     Ollama 설치 중... (관리자 권한 필요)
    "%BIN_DIR%\OllamaSetup.exe" /S
    
    :: Wait for installation
    timeout /t 5 /nobreak >nul
    
    :: Verify installation
    where ollama >nul 2>&1
    if %errorlevel% neq 0 (
        echo     ⚠ Ollama 자동 설치 실패. 수동 설치 안내
        echo.
        echo     📋 Ollama 수동 설치 가이드:
        echo     1. https://ollama.com/download 접속
        echo     2. Windows용 OllamaSetup.exe 다운로드
        echo     3. 다운로드한 파일을 관리자 권한으로 실행
        echo     4. 설치 완료 후 이 스크립트 재실행
        echo.
        echo     💡 설치 후 확인 방법:
        echo     - 명령 프롬프트에서 'ollama --version' 입력
        echo     - 정상적이면 버전 정보가 출력됩니다
        echo.
    ) else (
        echo     ✓ Ollama 설치 완료
    )
)

:: Download gemma model
echo     Gemma3 모델 다운로드 중... (약 2.6GB, 첫 실행시만)
ollama pull gemma:3b 2>nul
if %errorlevel% equ 0 (
    echo     ✓ Gemma3 모델 준비 완료
) else (
    echo     ⚠ 모델 다운로드 실패. 수동 다운로드 안내
    echo.
    echo     📥 Gemma3 모델 수동 다운로드 방법:
    echo     1. 시스템 설치 완료 후 RUN_ENHANCED.bat 실행
    echo     2. 명령 프롬프트에서 직접 실행: ollama pull gemma:3b
    echo     3. 또는 대안 모델 사용: ollama pull llama3:8b
    echo.
    echo     💡 참고사항:
    echo     - 모델 크기: Gemma3=2.6GB, Llama3=4.7GB
    echo     - 인터넷 연결 필요 (첫 다운로드시만)
    echo     - 시스템은 모델 없이도 임베딩 기능 사용 가능
    echo.
)
echo.

:: ===== BGE-M3 Embedding Model =====
echo [7/8] BGE-M3 임베딩 모델 확인...
if exist "%BIN_DIR%\bge-m3-local\model.safetensors" (
    echo     ✓ BGE-M3 모델 이미 설치됨
) else (
    if exist "src\bin\bge-m3-local\model.safetensors" (
        echo     기존 모델을 bin 폴더로 이동 중...
        xcopy /E /I /Y "src\bin\bge-m3-local" "%BIN_DIR%\bge-m3-local" >nul
        echo     ✓ 모델 이동 완료
    ) else (
        echo     ⚠ BGE-M3 모델이 없습니다. 자동 다운로드 중... (약 2GB)
        python -c "from sentence_transformers import SentenceTransformer; model = SentenceTransformer('BAAI/bge-m3'); model.save('%BIN_DIR%\\bge-m3-local')"
        if %errorlevel% equ 0 (
            echo     ✓ BGE-M3 모델 다운로드 완료
        ) else (
            echo     ✗ 모델 다운로드 실패. 인터넷 연결을 확인하세요.
        )
    )
)
echo.

:: ===== Configuration Files =====
echo [8/8] 설정 파일 생성...

:: Create .env file if not exists
if not exist ".env" (
    (
        echo # HD현대미포 LLM RAG System Configuration
        echo # Generated by INSTALL_ENHANCED.bat
        echo.
        echo # === 기본 설정 ===
        echo PYTHONIOENCODING=utf-8
        echo.
        echo # === 임베딩 설정 ===
        echo EMBED_BACKEND=st
        echo EMBED_MODEL=%BIN_DIR%\bge-m3-local
        echo EMBED_DEVICE=cpu
        echo EMBED_BATCH=32
        echo.
        echo # === Ollama 설정 ===
        echo OLLAMA_HOST=127.0.0.1
        echo OLLAMA_PORT=11434
        echo OLLAMA_ENDPOINT=http://127.0.0.1:11434
        echo.
        echo # === Qdrant 설정 (Dual Routing) ===
        echo # 개인 (로컬) Qdrant
        echo QDRANT_PERSONAL_HOST=127.0.0.1
        echo QDRANT_PERSONAL_PORT=6333
        echo QDRANT_PERSONAL_TIMEOUT=15
        echo.
        echo # 부서 Qdrant
        echo QDRANT_DEPT_HOST=10.150.104.37
        echo QDRANT_DEPT_PORT=6333
        echo QDRANT_DEPT_TIMEOUT=20
        echo.
        echo # 라우팅 설정
        echo DEFAULT_DB_SCOPE=personal
        echo QDRANT_DEPT_FALLBACK=personal
        echo NAMESPACE_PATTERN={scope}_{env}_{source}_my_documents
        echo QDRANT_ENV=prod
        echo.
        echo # === 보안 설정 ===
        echo ALLOWED_ORIGINS=http://localhost:8080,http://localhost:8001
        echo LOG_LEVEL=INFO
        echo LOG_REDACT_PII=true
        echo.
        echo # === 성능 최적화 ===
        echo EMBED_CACHE_MAX=512
        echo NORMALIZE_EMBEDDINGS=true
        echo QDRANT_HNSW_EF=128
        echo METRICS_ENABLED=true
    ) > .env
    echo     ✓ .env 파일 생성 완료
) else (
    echo     ✓ .env 파일 이미 존재
)

:: Update config.json for new bin location
if not exist "config.json" (
    (
        echo {
        echo   "mail_qdrant_path": "%USERPROFILE%\\Documents\\qdrant_mail",
        echo   "doc_qdrant_path": "%USERPROFILE%\\Documents\\qdrant_document",
        echo   "local_msg_path": "",
        echo   "bin_path": "%BIN_DIR%",
        echo   "auto_start_qdrant": true,
        echo   "auto_start_backend": true,
        echo   "minimize_to_tray": true
        echo }
    ) > config.json
    echo     ✓ config.json 생성 완료
) else (
    echo     ✓ config.json 이미 존재
)
echo.

:: ===== Installation Complete =====
echo ============================================================
echo   ✅ 설치가 완료되었습니다!
echo ============================================================
echo.
echo 설치된 구성요소:
echo   • Python 3.11+ (가상환경)
echo   • Qdrant 벡터 DB
echo   • Ollama LLM 서버
echo   • BGE-M3 임베딩 모델
echo   • 모든 Python 패키지
echo.
echo 다음 단계:
echo   1. RUN_ENHANCED.bat 실행하여 시스템 시작
echo   2. 브라우저에서 http://localhost:8001 접속
echo   3. 데이터 소스 선택 (개인/부서)
echo.
echo 환경 설정:
echo   • 개인 Qdrant: localhost:6333
echo   • 부서 Qdrant: 10.150.104.37:6333
echo   • 기본 스코프: personal
echo.
pause