@echo off
setlocal ENABLEDELAYEDEXPANSION
chcp 65001 >nul 2>&1

REM HD Gauss-1 통합 설치 프로그램 빌드 스크립트
REM 모든 바이너리를 포함한 완전 독립 실행형 패키지 생성

echo ============================================================
echo   HD현대미포 Gauss-1 RAG System
echo   독립 실행형 설치 프로그램 빌드
echo ============================================================
echo.

REM 변수 설정
set PROJECT_ROOT=%~dp0..\..
set DEPLOYMENT_DIR=%PROJECT_ROOT%\deployment
set OUTPUT_DIR=%DEPLOYMENT_DIR%\HDGauss1_Standalone_v1.0
set SCRIPTS_DIR=%DEPLOYMENT_DIR%\scripts
set BUILD_DATE=%date:~0,4%%date:~5,2%%date:~8,2%

REM 색상 설정
set RED=[91m
set GREEN=[92m
set YELLOW=[93m
set BLUE=[94m
set MAGENTA=[95m
set CYAN=[96m
set WHITE=[97m
set RESET=[0m

echo %CYAN%[정보] 프로젝트 루트: %PROJECT_ROOT%%RESET%
echo %CYAN%[정보] 출력 디렉토리: %OUTPUT_DIR%%RESET%
echo.

REM ===== 1단계: 환경 확인 =====
echo %BLUE%[1/10] 시스템 환경 확인 중...%RESET%

REM Python 확인
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo %RED%[오류] Python이 설치되지 않았습니다.%RESET%
    exit /b 1
)
echo %GREEN%✓ Python 확인 완료%RESET%

REM PyInstaller 확인
pyinstaller --version >nul 2>&1
if %errorlevel% neq 0 (
    echo %YELLOW%[경고] PyInstaller가 없습니다. 설치 중...%RESET%
    pip install pyinstaller
)
echo %GREEN%✓ PyInstaller 확인 완료%RESET%

REM ===== 2단계: 디렉토리 구조 생성 =====
echo.
echo %BLUE%[2/10] 디렉토리 구조 생성 중...%RESET%

if exist "%OUTPUT_DIR%" (
    echo %YELLOW%[경고] 기존 디렉토리 삭제 중...%RESET%
    rmdir /S /Q "%OUTPUT_DIR%"
)

mkdir "%OUTPUT_DIR%"
mkdir "%OUTPUT_DIR%\components"
mkdir "%OUTPUT_DIR%\components\app"
mkdir "%OUTPUT_DIR%\components\python"
mkdir "%OUTPUT_DIR%\components\qdrant"
mkdir "%OUTPUT_DIR%\components\ollama"
mkdir "%OUTPUT_DIR%\components\models"
mkdir "%OUTPUT_DIR%\components\models\bge-m3"
mkdir "%OUTPUT_DIR%\components\dependencies"
mkdir "%OUTPUT_DIR%\components\data"
mkdir "%OUTPUT_DIR%\scripts"
mkdir "%OUTPUT_DIR%\docs"
mkdir "%OUTPUT_DIR%\logs"

echo %GREEN%✓ 디렉토리 구조 생성 완료%RESET%

REM ===== 3단계: PyInstaller 스펙 파일 생성 =====
echo.
echo %BLUE%[3/10] PyInstaller 스펙 파일 생성 중...%RESET%

REM GUI 애플리케이션 스펙
set GUI_SPEC=%DEPLOYMENT_DIR%\hdllm.spec
echo # -*- mode: python ; coding: utf-8 -*- > "%GUI_SPEC%"
echo. >> "%GUI_SPEC%"
echo block_cipher = None >> "%GUI_SPEC%"
echo. >> "%GUI_SPEC%"
echo a = Analysis( >> "%GUI_SPEC%"
echo     ['%PROJECT_ROOT%\\src\\HDLLM.py'], >> "%GUI_SPEC%"
echo     pathex=['%PROJECT_ROOT%\\src'], >> "%GUI_SPEC%"
echo     binaries=[], >> "%GUI_SPEC%"
echo     datas=[ >> "%GUI_SPEC%"
echo         ('%PROJECT_ROOT%\\src\\parsers', 'parsers'), >> "%GUI_SPEC%"
echo         ('%PROJECT_ROOT%\\config.json', '.'), >> "%GUI_SPEC%"
echo     ], >> "%GUI_SPEC%"
echo     hiddenimports=[ >> "%GUI_SPEC%"
echo         'PySide6', 'PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets', >> "%GUI_SPEC%"
echo         'sentence_transformers', 'transformers', 'torch', >> "%GUI_SPEC%"
echo         'qdrant_client', 'langchain_huggingface', >> "%GUI_SPEC%"
echo         'tika', 'openpyxl', 'xlwings', 'extract_msg', >> "%GUI_SPEC%"
echo         'customtkinter', 'tqdm', >> "%GUI_SPEC%"
echo     ], >> "%GUI_SPEC%"
echo     hookspath=[], >> "%GUI_SPEC%"
echo     hooksconfig={}, >> "%GUI_SPEC%"
echo     runtime_hooks=[], >> "%GUI_SPEC%"
echo     excludes=['matplotlib', 'notebook', 'jupyter'], >> "%GUI_SPEC%"
echo     win_no_prefer_redirects=False, >> "%GUI_SPEC%"
echo     win_private_assemblies=False, >> "%GUI_SPEC%"
echo     cipher=block_cipher, >> "%GUI_SPEC%"
echo     noarchive=False, >> "%GUI_SPEC%"
echo ) >> "%GUI_SPEC%"
echo. >> "%GUI_SPEC%"
echo pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher) >> "%GUI_SPEC%"
echo. >> "%GUI_SPEC%"
echo exe = EXE( >> "%GUI_SPEC%"
echo     pyz, >> "%GUI_SPEC%"
echo     a.scripts, >> "%GUI_SPEC%"
echo     a.binaries, >> "%GUI_SPEC%"
echo     a.zipfiles, >> "%GUI_SPEC%"
echo     a.datas, >> "%GUI_SPEC%"
echo     [], >> "%GUI_SPEC%"
echo     name='hdllm', >> "%GUI_SPEC%"
echo     debug=False, >> "%GUI_SPEC%"
echo     bootloader_ignore_signals=False, >> "%GUI_SPEC%"
echo     strip=False, >> "%GUI_SPEC%"
echo     upx=False, >> "%GUI_SPEC%"
echo     upx_exclude=[], >> "%GUI_SPEC%"
echo     runtime_tmpdir=None, >> "%GUI_SPEC%"
echo     console=False, >> "%GUI_SPEC%"
echo     disable_windowed_traceback=False, >> "%GUI_SPEC%"
echo     argv_emulation=False, >> "%GUI_SPEC%"
echo     target_arch=None, >> "%GUI_SPEC%"
echo     codesign_identity=None, >> "%GUI_SPEC%"
echo     entitlements_file=None, >> "%GUI_SPEC%"
echo ) >> "%GUI_SPEC%"

REM Backend 서버 스펙
set BACKEND_SPEC=%DEPLOYMENT_DIR%\backend.spec
echo # -*- mode: python ; coding: utf-8 -*- > "%BACKEND_SPEC%"
echo. >> "%BACKEND_SPEC%"
echo block_cipher = None >> "%BACKEND_SPEC%"
echo. >> "%BACKEND_SPEC%"
echo a = Analysis( >> "%BACKEND_SPEC%"
echo     ['%PROJECT_ROOT%\\backend\\main.py'], >> "%BACKEND_SPEC%"
echo     pathex=['%PROJECT_ROOT%\\backend'], >> "%BACKEND_SPEC%"
echo     binaries=[], >> "%BACKEND_SPEC%"
echo     datas=[ >> "%BACKEND_SPEC%"
echo         ('%PROJECT_ROOT%\\backend\\security.py', '.'), >> "%BACKEND_SPEC%"
echo         ('%PROJECT_ROOT%\\config.json', '.'), >> "%BACKEND_SPEC%"
echo     ], >> "%BACKEND_SPEC%"
echo     hiddenimports=[ >> "%BACKEND_SPEC%"
echo         'fastapi', 'uvicorn', 'uvicorn.loops.auto', >> "%BACKEND_SPEC%"
echo         'uvicorn.protocols.http', 'uvicorn.protocols.http.auto', >> "%BACKEND_SPEC%"
echo         'uvicorn.protocols.websockets', 'uvicorn.protocols.websockets.auto', >> "%BACKEND_SPEC%"
echo         'uvicorn.lifespan', 'uvicorn.lifespan.on', >> "%BACKEND_SPEC%"
echo         'qdrant_client', 'langchain_huggingface', >> "%BACKEND_SPEC%"
echo         'httpx', 'aiohttp', 'starlette', >> "%BACKEND_SPEC%"
echo         'pydantic', 'typing_extensions', >> "%BACKEND_SPEC%"
echo     ], >> "%BACKEND_SPEC%"
echo     hookspath=[], >> "%BACKEND_SPEC%"
echo     hooksconfig={}, >> "%BACKEND_SPEC%"
echo     runtime_hooks=[], >> "%BACKEND_SPEC%"
echo     excludes=['matplotlib', 'notebook', 'jupyter'], >> "%BACKEND_SPEC%"
echo     win_no_prefer_redirects=False, >> "%BACKEND_SPEC%"
echo     win_private_assemblies=False, >> "%BACKEND_SPEC%"
echo     cipher=block_cipher, >> "%BACKEND_SPEC%"
echo     noarchive=False, >> "%BACKEND_SPEC%"
echo ) >> "%BACKEND_SPEC%"
echo. >> "%BACKEND_SPEC%"
echo pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher) >> "%BACKEND_SPEC%"
echo. >> "%BACKEND_SPEC%"
echo exe = EXE( >> "%BACKEND_SPEC%"
echo     pyz, >> "%BACKEND_SPEC%"
echo     a.scripts, >> "%BACKEND_SPEC%"
echo     a.binaries, >> "%BACKEND_SPEC%"
echo     a.zipfiles, >> "%BACKEND_SPEC%"
echo     a.datas, >> "%BACKEND_SPEC%"
echo     [], >> "%BACKEND_SPEC%"
echo     name='backend', >> "%BACKEND_SPEC%"
echo     debug=False, >> "%BACKEND_SPEC%"
echo     bootloader_ignore_signals=False, >> "%BACKEND_SPEC%"
echo     strip=False, >> "%BACKEND_SPEC%"
echo     upx=False, >> "%BACKEND_SPEC%"
echo     upx_exclude=[], >> "%BACKEND_SPEC%"
echo     runtime_tmpdir=None, >> "%BACKEND_SPEC%"
echo     console=True, >> "%BACKEND_SPEC%"
echo     disable_windowed_traceback=False, >> "%BACKEND_SPEC%"
echo     argv_emulation=False, >> "%BACKEND_SPEC%"
echo     target_arch=None, >> "%BACKEND_SPEC%"
echo     codesign_identity=None, >> "%BACKEND_SPEC%"
echo     entitlements_file=None, >> "%BACKEND_SPEC%"
echo ) >> "%BACKEND_SPEC%"

echo %GREEN%✓ 스펙 파일 생성 완료%RESET%

REM ===== 4단계: PyInstaller 빌드 =====
echo.
echo %BLUE%[4/10] PyInstaller로 실행 파일 빌드 중...%RESET%

cd /d "%DEPLOYMENT_DIR%"

echo %CYAN%GUI 애플리케이션 빌드 중...%RESET%
pyinstaller "%GUI_SPEC%" --clean --noconfirm
if %errorlevel% neq 0 (
    echo %RED%[오류] GUI 빌드 실패%RESET%
    exit /b 1
)

echo %CYAN%Backend 서버 빌드 중...%RESET%
pyinstaller "%BACKEND_SPEC%" --clean --noconfirm
if %errorlevel% neq 0 (
    echo %RED%[오류] Backend 빌드 실패%RESET%
    exit /b 1
)

echo %GREEN%✓ 실행 파일 빌드 완료%RESET%

REM ===== 5단계: 실행 파일 복사 =====
echo.
echo %BLUE%[5/10] 실행 파일 복사 중...%RESET%

copy "%DEPLOYMENT_DIR%\dist\hdllm.exe" "%OUTPUT_DIR%\components\app\" >nul
copy "%DEPLOYMENT_DIR%\dist\backend.exe" "%OUTPUT_DIR%\components\app\" >nul

echo %GREEN%✓ 실행 파일 복사 완료%RESET%

REM ===== 6단계: 프론트엔드 파일 복사 =====
echo.
echo %BLUE%[6/10] 프론트엔드 파일 복사 중...%RESET%

xcopy "%PROJECT_ROOT%\frontend" "%OUTPUT_DIR%\components\app\frontend\" /E /I /Y /Q >nul

echo %GREEN%✓ 프론트엔드 파일 복사 완료%RESET%

REM ===== 7단계: 바이너리 수집 =====
echo.
echo %BLUE%[7/10] 외부 바이너리 수집 중...%RESET%

echo %YELLOW%PowerShell 스크립트 실행 중...%RESET%
powershell -ExecutionPolicy Bypass -File "%SCRIPTS_DIR%\collect_binaries.ps1" -OutputPath "%OUTPUT_DIR%" -Force

echo %GREEN%✓ 바이너리 수집 완료%RESET%

REM ===== 8단계: 실행 스크립트 생성 =====
echo.
echo %BLUE%[8/10] 실행 스크립트 생성 중...%RESET%

REM RUN.bat 생성
set RUN_BAT=%OUTPUT_DIR%\RUN.bat
(
echo @echo off
echo setlocal ENABLEDELAYEDEXPANSION
echo chcp 65001 ^>nul 2^>^&1
echo.
echo title HD현대미포 Gauss-1 RAG System
echo.
echo echo ============================================================
echo echo   HD현대미포 Gauss-1 RAG System 시작
echo echo ============================================================
echo echo.
echo.
echo set ROOT=%%~dp0
echo cd /d "%%ROOT%%"
echo.
echo REM Qdrant 시작
echo echo [1/4] Qdrant 벡터 DB 시작 중...
echo start /B "" "%%ROOT%%components\qdrant\qdrant.exe" --storage-dir "%%ROOT%%components\data\storage"
echo timeout /t 3 /nobreak ^>nul
echo.
echo REM Ollama 시작
echo echo [2/4] Ollama LLM 서버 시작 중...
echo set OLLAMA_MODELS=%%ROOT%%components\ollama\models
echo start /B "" "%%ROOT%%components\ollama\ollama.exe" serve
echo timeout /t 3 /nobreak ^>nul
echo.
echo REM Backend API 시작
echo echo [3/4] Backend API 서버 시작 중...
echo start /B "" "%%ROOT%%components\app\backend.exe"
echo timeout /t 5 /nobreak ^>nul
echo.
echo REM GUI 애플리케이션 시작
echo echo [4/4] GUI 애플리케이션 시작 중...
echo start "" "%%ROOT%%components\app\hdllm.exe"
echo.
echo echo.
echo echo ============================================================
echo echo   ✅ 모든 서비스가 시작되었습니다!
echo echo ============================================================
echo echo.
echo echo 웹 인터페이스: http://localhost:8001
echo echo API 문서: http://localhost:8080/docs
echo echo.
echo echo 종료하려면 이 창을 닫으세요.
echo echo.
echo pause ^>nul
) > "%RUN_BAT%"

echo %GREEN%✓ 실행 스크립트 생성 완료%RESET%

REM ===== 9단계: 문서 파일 생성 =====
echo.
echo %BLUE%[9/10] 문서 파일 생성 중...%RESET%

REM README.txt 생성
set README=%OUTPUT_DIR%\docs\README.txt
(
echo HD현대미포 Gauss-1 RAG System
echo ===============================
echo.
echo 버전: 1.0.0
echo 빌드 날짜: %BUILD_DATE%
echo.
echo [시스템 요구사항]
echo - Windows 10/11 64-bit
echo - RAM: 최소 8GB ^(권장 16GB^)
echo - 저장공간: 20GB 이상
echo - CPU: Intel i5 이상
echo.
echo [실행 방법]
echo 1. RUN.bat 더블클릭
echo 2. 모든 서비스 자동 시작
echo 3. GUI 애플리케이션 자동 실행
echo.
echo [주요 기능]
echo - 문서 임베딩 및 검색
echo - 자연어 질의응답
echo - 한국어 특화 처리
echo.
echo [문제 해결]
echo TROUBLESHOOTING.txt 파일 참조
echo.
echo [기술 지원]
echo 선각기술부 내선: xxxx
echo 이메일: tech-support@hdmipo.com
) > "%README%"

REM TROUBLESHOOTING.txt 생성
set TROUBLESHOOT=%OUTPUT_DIR%\docs\TROUBLESHOOTING.txt
(
echo HD Gauss-1 문제 해결 가이드
echo ===========================
echo.
echo [문제 1] DLL 파일을 찾을 수 없음
echo 해결: components\dependencies\vcredist_x64.exe 실행
echo.
echo [문제 2] 포트 충돌
echo 해결: 
echo - netstat -an ^| findstr :8080
echo - netstat -an ^| findstr :6333
echo - 사용 중인 프로그램 종료
echo.
echo [문제 3] 메모리 부족
echo 해결:
echo - 최소 8GB RAM 확인
echo - 다른 프로그램 종료
echo - 가상 메모리 증가
echo.
echo [문제 4] Ollama 모델 로딩 실패
echo 해결:
echo - components\ollama\ollama.exe pull gemma3:4b
echo.
echo [로그 위치]
echo logs\ 폴더 확인
) > "%TROUBLESHOOT%"

echo %GREEN%✓ 문서 파일 생성 완료%RESET%

REM ===== 10단계: 패키지 정보 =====
echo.
echo %BLUE%[10/10] 패키지 정보 수집 중...%RESET%

REM 크기 계산
for /f "usebackq" %%A in (`powershell "(Get-ChildItem -Path '%OUTPUT_DIR%' -Recurse | Measure-Object -Property Length -Sum).Sum / 1GB"`) do set SIZE=%%A

echo.
echo %MAGENTA%============================================================%RESET%
echo %GREEN%   ✅ 빌드 완료!%RESET%
echo %MAGENTA%============================================================%RESET%
echo.
echo %WHITE%출력 디렉토리:%RESET% %OUTPUT_DIR%
echo %WHITE%패키지 크기:%RESET% 약 %SIZE:~0,4% GB
echo %WHITE%빌드 날짜:%RESET% %BUILD_DATE%
echo.
echo %YELLOW%다음 단계:%RESET%
echo 1. Ollama 바이너리 수동 추가 필요
echo 2. BGE-M3 및 Gemma3:4b 모델 다운로드 필요
echo 3. NSIS로 최종 설치 프로그램 생성
echo.

pause