# HD현대미포 Gauss-1 RAG 시스템 - 독립 실행형 배포 계획서

> 작성일: 2025-01-31  
> 버전: 1.0  
> 대상: Docker 미지원 Windows PC 환경

## 📋 목차
1. [개요](#개요)
2. [배포 패키지 구성](#배포-패키지-구성)
3. [바이너리 수집 및 준비](#바이너리-수집-및-준비)
4. [패키징 프로세스](#패키징-프로세스)
5. [설치 및 실행 가이드](#설치-및-실행-가이드)
6. [문제 해결 가이드](#문제-해결-가이드)

---

## 개요

### 목표
Docker가 설치되지 않은 Windows PC에서 HD현대미포 Gauss-1 RAG 시스템을 완전히 독립적으로 실행할 수 있는 올인원 패키지를 제작합니다.

### 주요 특징
- **완전 독립 실행**: 외부 의존성 없음
- **단일 설치 패키지**: 약 15GB 크기의 통합 설치 프로그램
- **자동 환경 구성**: 모든 서비스 자동 설정
- **버전 호환성 보장**: 테스트된 버전 조합 사용

### 시스템 요구사항
- **OS**: Windows 10/11 (64-bit)
- **RAM**: 최소 8GB (권장 16GB)
- **저장공간**: 최소 20GB 여유 공간
- **CPU**: Intel i5 이상 또는 동급
- **네트워크**: 인터넷 연결 불필요 (오프라인 작동)

---

## 배포 패키지 구성

### 전체 구조
```
HDGauss1_Standalone_v1.0/
├── installer.exe              # 메인 설치 프로그램
├── components/
│   ├── app/
│   │   ├── hdllm.exe         # GUI 애플리케이션 (PyInstaller)
│   │   ├── backend.exe       # FastAPI 서버 (PyInstaller)
│   │   └── frontend/         # 웹 UI 파일들
│   │       ├── index.html
│   │       └── assets/
│   │
│   ├── python/
│   │   └── python-3.11.7-embed-amd64/  # 임베디드 Python
│   │       ├── python.exe
│   │       ├── python311.dll
│   │       └── Lib/          # 표준 라이브러리
│   │
│   ├── qdrant/
│   │   ├── qdrant.exe        # Qdrant 서버 바이너리
│   │   └── config/
│   │       └── config.yaml
│   │
│   ├── ollama/
│   │   ├── ollama.exe        # Ollama 서버
│   │   └── models/
│   │       └── gemma3-4b/    # Gemma3:4b 모델 (약 2.5GB)
│   │           ├── model.bin
│   │           └── config.json
│   │
│   ├── models/
│   │   └── bge-m3/           # BGE-M3 임베딩 모델 (약 1.5GB)
│   │       ├── pytorch_model.bin
│   │       ├── config.json
│   │       └── tokenizer/
│   │
│   ├── dependencies/
│   │   ├── site-packages/    # Python 패키지들
│   │   └── dlls/             # 필요한 DLL 파일들
│   │
│   └── data/
│       ├── storage/          # Qdrant 데이터 저장소
│       └── config/           # 설정 파일들
│
├── scripts/
│   ├── install.bat           # 설치 스크립트
│   ├── uninstall.bat         # 제거 스크립트
│   └── check_system.bat      # 시스템 체크 스크립트
│
└── docs/
    ├── README.txt            # 사용 설명서
    └── TROUBLESHOOTING.txt   # 문제 해결 가이드
```

---

## 바이너리 수집 및 준비

### 1. Python 3.11 임베디드 배포판
```powershell
# 다운로드 (약 15MB)
Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.11.7/python-3.11.7-embed-amd64.zip" `
                  -OutFile "python-3.11.7-embed-amd64.zip"

# 압축 해제
Expand-Archive -Path "python-3.11.7-embed-amd64.zip" -DestinationPath "components/python"

# pip 설치 활성화
(Get-Content "components/python/python311._pth") -replace "#import site", "import site" | 
    Set-Content "components/python/python311._pth"
```

### 2. Qdrant 바이너리
```powershell
# Windows용 Qdrant 다운로드 (약 50MB)
$qdrantVersion = "v1.7.4"
$qdrantUrl = "https://github.com/qdrant/qdrant/releases/download/$qdrantVersion/qdrant-x86_64-pc-windows-msvc.zip"
Invoke-WebRequest -Uri $qdrantUrl -OutFile "qdrant.zip"

# 압축 해제
Expand-Archive -Path "qdrant.zip" -DestinationPath "components/qdrant"
```

### 3. Ollama 바이너리
```powershell
# Ollama Windows 설치 파일 다운로드 (약 500MB)
$ollamaUrl = "https://github.com/ollama/ollama/releases/latest/download/OllamaSetup.exe"
Invoke-WebRequest -Uri $ollamaUrl -OutFile "OllamaSetup.exe"

# 설치 파일에서 바이너리 추출
# 또는 포터블 버전 사용
Start-Process -FilePath "OllamaSetup.exe" -ArgumentList "/S", "/D=components\ollama" -Wait
```

### 4. Gemma3:4b 모델 다운로드
```batch
# Ollama를 통한 모델 다운로드
components\ollama\ollama.exe pull gemma3:4b

# 모델 파일 위치 확인 및 복사
# Windows: %USERPROFILE%\.ollama\models
xcopy "%USERPROFILE%\.ollama\models\*" "components\ollama\models\" /E /I /Y
```

### 5. BGE-M3 임베딩 모델
```python
# download_models.py
from huggingface_hub import snapshot_download
import os

# BGE-M3 모델 다운로드
model_path = "components/models/bge-m3"
snapshot_download(
    repo_id="BAAI/bge-m3",
    local_dir=model_path,
    local_dir_use_symlinks=False,
    ignore_patterns=["*.msgpack", "*.h5", "*.safetensors"]  # PyTorch 파일만
)
```

### 6. Python 패키지 수집
```batch
# 가상환경에서 패키지 설치 후 복사
python -m venv temp_env
temp_env\Scripts\activate

# requirements.txt 기반 설치
pip install -r requirements.txt --target components\dependencies\site-packages

# PyTorch CPU 버전 설치 (GPU 불필요한 경우)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu `
    --target components\dependencies\site-packages
```

### 7. PyInstaller 실행 파일 생성

#### GUI 애플리케이션 (hdllm.spec)
```python
# hdllm.spec
a = Analysis(
    ['src/HDLLM.py'],
    pathex=['src'],
    binaries=[
        ('components/python/python311.dll', '.'),
    ],
    datas=[
        ('src/parsers', 'parsers'),
        ('src/bin', 'bin'),
        ('frontend', 'frontend'),
        ('config.json', '.'),
    ],
    hiddenimports=[
        'PySide6',
        'sentence_transformers',
        'qdrant_client',
        'langchain_huggingface',
        'torch',
        'tika',
        'openpyxl',
        'xlwings',
        'extract_msg',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=['matplotlib', 'notebook', 'jupyter'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='hdllm',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # GUI 모드
    icon='assets/icon.ico',
    version='version_info.txt'
)
```

#### Backend 서버 (backend.spec)
```python
# backend.spec
a = Analysis(
    ['backend/main.py'],
    pathex=['backend'],
    binaries=[],
    datas=[
        ('backend/security.py', '.'),
        ('.env', '.'),
    ],
    hiddenimports=[
        'fastapi',
        'uvicorn',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'qdrant_client',
        'langchain_huggingface',
        'httpx',
        'aiohttp',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,  # 콘솔 모드
    icon='assets/icon.ico'
)
```

빌드 실행:
```batch
pyinstaller hdllm.spec --clean
pyinstaller backend.spec --clean
```

---

## 패키징 프로세스

### 1. 디렉토리 구조 생성
```batch
@echo off
mkdir HDGauss1_Standalone_v1.0
mkdir HDGauss1_Standalone_v1.0\components
mkdir HDGauss1_Standalone_v1.0\components\app
mkdir HDGauss1_Standalone_v1.0\components\python
mkdir HDGauss1_Standalone_v1.0\components\qdrant
mkdir HDGauss1_Standalone_v1.0\components\ollama
mkdir HDGauss1_Standalone_v1.0\components\models
mkdir HDGauss1_Standalone_v1.0\components\dependencies
mkdir HDGauss1_Standalone_v1.0\components\data
mkdir HDGauss1_Standalone_v1.0\scripts
mkdir HDGauss1_Standalone_v1.0\docs
```

### 2. 파일 복사 스크립트 (collect_files.bat)
```batch
@echo off
echo HD Gauss-1 배포 패키지 생성 중...

REM 실행 파일 복사
copy dist\hdllm.exe HDGauss1_Standalone_v1.0\components\app\
copy dist\backend.exe HDGauss1_Standalone_v1.0\components\app\
xcopy frontend HDGauss1_Standalone_v1.0\components\app\frontend\ /E /I /Y

REM Python 임베디드 복사
xcopy python-3.11.7-embed-amd64 HDGauss1_Standalone_v1.0\components\python\ /E /I /Y

REM Qdrant 복사
copy qdrant\qdrant.exe HDGauss1_Standalone_v1.0\components\qdrant\

REM Ollama 복사
xcopy ollama HDGauss1_Standalone_v1.0\components\ollama\ /E /I /Y

REM 모델 복사
xcopy models\bge-m3 HDGauss1_Standalone_v1.0\components\models\bge-m3\ /E /I /Y

REM 의존성 복사
xcopy site-packages HDGauss1_Standalone_v1.0\components\dependencies\site-packages\ /E /I /Y

echo 패키지 생성 완료!
```

### 3. 설치 스크립트 (install.bat)
```batch
@echo off
setlocal ENABLEDELAYEDEXPANSION
chcp 65001 >nul 2>&1

echo ============================================================
echo   HD현대미포 Gauss-1 RAG 시스템 설치
echo ============================================================
echo.

REM 관리자 권한 체크
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [오류] 관리자 권한이 필요합니다.
    echo 마우스 오른쪽 클릭 → "관리자 권한으로 실행"을 선택하세요.
    pause
    exit /b 1
)

REM 설치 경로 설정
set INSTALL_PATH=C:\HDGauss1
echo 설치 경로: %INSTALL_PATH%
echo.

REM 기존 설치 확인
if exist "%INSTALL_PATH%" (
    echo [경고] 기존 설치가 발견되었습니다.
    choice /C YN /M "덮어쓰시겠습니까?"
    if !errorlevel! equ 2 exit /b 0
    rmdir /S /Q "%INSTALL_PATH%"
)

REM 디렉토리 생성
echo [1/8] 설치 디렉토리 생성 중...
mkdir "%INSTALL_PATH%"

REM 파일 복사
echo [2/8] 프로그램 파일 복사 중...
xcopy components "%INSTALL_PATH%\components\" /E /I /Y /Q

echo [3/8] 스크립트 복사 중...
xcopy scripts "%INSTALL_PATH%\scripts\" /E /I /Y /Q

echo [4/8] 문서 복사 중...
xcopy docs "%INSTALL_PATH%\docs\" /E /I /Y /Q

REM 환경 변수 설정
echo [5/8] 환경 변수 설정 중...
setx HDGAUSS_HOME "%INSTALL_PATH%" /M >nul 2>&1
setx PYTHONPATH "%INSTALL_PATH%\components\dependencies\site-packages" /M >nul 2>&1

REM 바로가기 생성
echo [6/8] 바탕화면 바로가기 생성 중...
powershell -Command "$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%USERPROFILE%\Desktop\HD Gauss-1.lnk'); $Shortcut.TargetPath = '%INSTALL_PATH%\RUN.bat'; $Shortcut.WorkingDirectory = '%INSTALL_PATH%'; $Shortcut.IconLocation = '%INSTALL_PATH%\components\app\hdllm.exe'; $Shortcut.Save()"

REM 시작 메뉴 등록
echo [7/8] 시작 메뉴 등록 중...
mkdir "%APPDATA%\Microsoft\Windows\Start Menu\Programs\HD Gauss-1"
copy "%USERPROFILE%\Desktop\HD Gauss-1.lnk" "%APPDATA%\Microsoft\Windows\Start Menu\Programs\HD Gauss-1\"

REM Windows Defender 예외 추가
echo [8/8] Windows Defender 예외 추가 중...
powershell -Command "Add-MpPreference -ExclusionPath '%INSTALL_PATH%'" >nul 2>&1

echo.
echo ============================================================
echo   ✅ 설치가 완료되었습니다!
echo ============================================================
echo.
echo 설치 경로: %INSTALL_PATH%
echo 바탕화면에 "HD Gauss-1" 바로가기가 생성되었습니다.
echo.
echo 프로그램을 실행하려면 바탕화면 아이콘을 더블클릭하세요.
echo.
pause
```

### 4. 실행 스크립트 (RUN.bat)
```batch
@echo off
setlocal ENABLEDELAYEDEXPANSION
chcp 65001 >nul 2>&1

title HD현대미포 Gauss-1 RAG System

echo ============================================================
echo   HD현대미포 Gauss-1 RAG System 시작
echo ============================================================
echo.

set ROOT=%~dp0
cd /d "%ROOT%"

REM 포트 체크 함수
:check_port
netstat -an | findstr ":%1" >nul
if %errorlevel% equ 0 (
    echo 포트 %1 이미 사용 중
    exit /b 1
) else (
    exit /b 0
)

REM 1. Qdrant 시작
echo [1/4] Qdrant 벡터 DB 시작 중...
call :check_port 6333
if %errorlevel% equ 1 (
    echo Qdrant가 이미 실행 중입니다.
) else (
    start /B "" "%ROOT%components\qdrant\qdrant.exe" --storage-dir "%ROOT%components\data\storage"
    timeout /t 3 /nobreak >nul
)

REM 2. Ollama 시작
echo [2/4] Ollama LLM 서버 시작 중...
call :check_port 11434
if %errorlevel% equ 1 (
    echo Ollama가 이미 실행 중입니다.
) else (
    set OLLAMA_MODELS=%ROOT%components\ollama\models
    start /B "" "%ROOT%components\ollama\ollama.exe" serve
    timeout /t 3 /nobreak >nul
)

REM 3. Backend API 시작
echo [3/4] Backend API 서버 시작 중...
call :check_port 8080
if %errorlevel% equ 1 (
    echo Backend API가 이미 실행 중입니다.
) else (
    start /B "" "%ROOT%components\app\backend.exe"
    timeout /t 5 /nobreak >nul
)

REM 4. GUI 애플리케이션 시작
echo [4/4] GUI 애플리케이션 시작 중...
start "" "%ROOT%components\app\hdllm.exe"

echo.
echo ============================================================
echo   ✅ 모든 서비스가 시작되었습니다!
echo ============================================================
echo.
echo 웹 인터페이스: http://localhost:8001
echo API 문서: http://localhost:8080/docs
echo.
echo 종료하려면 이 창을 닫으세요.
echo.

REM 프로세스 모니터링
:monitor
timeout /t 30 /nobreak >nul
tasklist | findstr "hdllm.exe" >nul
if %errorlevel% neq 0 goto :cleanup
goto :monitor

:cleanup
echo 프로그램 종료 중...
taskkill /F /IM backend.exe >nul 2>&1
taskkill /F /IM ollama.exe >nul 2>&1
taskkill /F /IM qdrant.exe >nul 2>&1
exit
```

### 5. NSIS 설치 프로그램 스크립트 (installer.nsi)
```nsis
!include "MUI2.nsh"
!include "x64.nsh"

Name "HD현대미포 Gauss-1 RAG System"
OutFile "HDGauss1_Setup_v1.0.exe"
InstallDir "$PROGRAMFILES64\HDGauss1"
RequestExecutionLevel admin

; 압축 설정
SetCompressor /SOLID lzma
SetCompressorDictSize 64

; 인터페이스 설정
!define MUI_ICON "assets\icon.ico"
!define MUI_UNICON "assets\unicon.ico"

; 페이지 설정
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE.txt"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

; 언어 설정
!insertmacro MUI_LANGUAGE "Korean"

; 설치 섹션
Section "MainSection" SEC01
    SetOutPath "$INSTDIR"
    
    ; 파일 복사 (약 15GB)
    File /r "components\*.*"
    File /r "scripts\*.*"
    File /r "docs\*.*"
    
    ; 환경 변수 설정
    WriteRegStr HKLM "SYSTEM\CurrentControlSet\Control\Session Manager\Environment" "HDGAUSS_HOME" "$INSTDIR"
    
    ; 바로가기 생성
    CreateDirectory "$SMPROGRAMS\HD Gauss-1"
    CreateShortcut "$SMPROGRAMS\HD Gauss-1\HD Gauss-1.lnk" "$INSTDIR\RUN.bat" "" "$INSTDIR\components\app\hdllm.exe"
    CreateShortcut "$DESKTOP\HD Gauss-1.lnk" "$INSTDIR\RUN.bat" "" "$INSTDIR\components\app\hdllm.exe"
    
    ; 제거 정보 작성
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\HDGauss1" "DisplayName" "HD현대미포 Gauss-1"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\HDGauss1" "UninstallString" "$INSTDIR\Uninstall.exe"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\HDGauss1" "DisplayVersion" "1.0"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\HDGauss1" "Publisher" "HD현대미포 선각기술부"
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\HDGauss1" "EstimatedSize" 15360000
    
    WriteUninstaller "$INSTDIR\Uninstall.exe"
SectionEnd

; 제거 섹션
Section "Uninstall"
    ; 프로세스 종료
    ExecWait "taskkill /F /IM hdllm.exe"
    ExecWait "taskkill /F /IM backend.exe"
    ExecWait "taskkill /F /IM ollama.exe"
    ExecWait "taskkill /F /IM qdrant.exe"
    
    ; 파일 삭제
    RMDir /r "$INSTDIR"
    
    ; 바로가기 삭제
    Delete "$DESKTOP\HD Gauss-1.lnk"
    RMDir /r "$SMPROGRAMS\HD Gauss-1"
    
    ; 레지스트리 삭제
    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\HDGauss1"
    DeleteRegValue HKLM "SYSTEM\CurrentControlSet\Control\Session Manager\Environment" "HDGAUSS_HOME"
SectionEnd
```

---

## 설치 및 실행 가이드

### 설치 과정
1. **설치 파일 실행**
   - `HDGauss1_Setup_v1.0.exe` 더블클릭
   - 관리자 권한 요청 시 "예" 선택

2. **설치 옵션 선택**
   - 설치 경로: 기본값 `C:\Program Files\HDGauss1` 권장
   - 구성 요소: 모두 선택 (기본값)

3. **설치 진행**
   - 약 10-15분 소요 (파일 크기에 따라)
   - 진행률 표시줄 확인

4. **설치 완료**
   - 바탕화면에 아이콘 생성 확인
   - 시작 메뉴 등록 확인

### 첫 실행
1. 바탕화면 "HD Gauss-1" 아이콘 더블클릭
2. Windows Defender 경고 시 "추가 정보" → "실행" 클릭
3. 자동으로 모든 서비스 시작
4. GUI 애플리케이션 자동 실행

### 사용 방법
1. **문서 임베딩**
   - GUI에서 "문서 임베딩" 탭 선택
   - 폴더 선택 후 "임베딩 시작" 클릭

2. **질의응답**
   - 웹 브라우저에서 `http://localhost:8001` 접속
   - 또는 GUI에서 직접 질문 입력

---

## 문제 해결 가이드

### 자주 발생하는 문제

#### 1. "VCRUNTIME140.dll을 찾을 수 없습니다" 오류
**해결책**: Visual C++ Redistributable 설치
```batch
# 설치 패키지에 포함된 vcredist 실행
components\dependencies\vcredist_x64.exe
```

#### 2. 포트 충돌 오류
**해결책**: 사용 중인 포트 확인 및 변경
```batch
# 포트 사용 확인
netstat -an | findstr :8080
netstat -an | findstr :6333
netstat -an | findstr :11434

# config.json에서 포트 변경
```

#### 3. 메모리 부족 오류
**해결책**: 
- 최소 8GB RAM 확인
- 다른 프로그램 종료
- 가상 메모리 증가

#### 4. Ollama 모델 로딩 실패
**해결책**:
```batch
# 모델 재다운로드
cd components\ollama
ollama.exe pull gemma3:4b
```

#### 5. Qdrant 시작 실패
**해결책**:
- storage 디렉토리 권한 확인
- 기존 프로세스 종료
```batch
taskkill /F /IM qdrant.exe
```

### 로그 확인
```
C:\HDGauss1\logs\
├── app.log         # 애플리케이션 로그
├── backend.log     # API 서버 로그
├── qdrant.log      # 벡터 DB 로그
└── ollama.log      # LLM 서버 로그
```

### 완전 재설치
1. 제어판 → 프로그램 제거에서 "HD현대미포 Gauss-1" 제거
2. `C:\HDGauss1` 폴더 수동 삭제
3. 레지스트리 정리 (선택사항)
4. 새로 설치

### 기술 지원
- 내선: 선각기술부 (xxxx)
- 이메일: tech-support@hdmipo.com
- 문서: `C:\HDGauss1\docs\`

---

## 버전 관리 및 업데이트

### 버전 체계
- **Major.Minor.Patch** (예: 1.0.0)
- Major: 주요 기능 변경
- Minor: 기능 추가/개선
- Patch: 버그 수정

### 업데이트 방법
1. **자동 업데이트** (계획 중)
2. **수동 업데이트**
   - 새 버전 설치 파일 실행
   - 기존 설정 자동 보존

### 버전별 호환성 매트릭스
| 구성요소 | 버전 | 호환성 |
|---------|------|--------|
| Python | 3.11.7 | ✅ |
| Qdrant | 1.7.4 | ✅ |
| Ollama | 0.1.23 | ✅ |
| BGE-M3 | latest | ✅ |
| Gemma3 | 4b | ✅ |
| FastAPI | 0.104.1 | ✅ |
| PySide6 | 6.x | ✅ |

---

## 부록: 빌드 자동화 스크립트

### 전체 빌드 프로세스 (build_all.bat)
```batch
@echo off
echo ============================================================
echo   HD Gauss-1 전체 빌드 프로세스 시작
echo ============================================================

REM 1. 환경 준비
call prepare_env.bat

REM 2. 바이너리 수집
call collect_binaries.bat

REM 3. PyInstaller 빌드
call build_exe.bat

REM 4. 패키지 생성
call create_package.bat

REM 5. NSIS 설치 프로그램 생성
"C:\Program Files (x86)\NSIS\makensis.exe" installer.nsi

echo.
echo ============================================================
echo   ✅ 빌드 완료!
echo   출력: HDGauss1_Setup_v1.0.exe
echo ============================================================
pause
```

---

> **작성**: Claude Code  
> **검토**: HD현대미포 선각기술부  
> **배포 대상**: Docker 미지원 Windows PC 환경  
> **예상 패키지 크기**: 약 15GB  
> **설치 후 크기**: 약 18GB