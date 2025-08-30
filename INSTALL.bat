@echo off
setlocal ENABLEDELAYEDEXPANSION
chcp 65001 >nul 2>&1

REM HD현대미포 Gauss-1 RAG System - Enhanced Installer
REM Version: 2.1 - Portable/Offline Support
REM Date: 2025-01-30

echo ============================================================
echo   HD현대미포 Gauss-1 RAG System - 설치 프로그램 v2.1
echo ============================================================
echo.

REM 0) 기준 경로
set ROOT=%~dp0
cd /d "%ROOT%"

echo [1/6] .env 준비...
if not exist ".env" (
    if exist ".env.example" (
        copy /y ".env.example" ".env" >nul
        echo    -^> .env 생성 완료
    ) else if exist ".env.template" (
        copy /y ".env.template" ".env" >nul
        echo    -^> .env 생성 완료 (template 기반)
    ) else (
        echo    -^> .env.example 이 없어 .env를 생성하지 못했습니다. 수동 확인 필요.
    )
) else (
    echo    -^> .env 파일 이미 존재
)

echo [2/6] Python 3.11 확인...
where py 2>nul | findstr /i "py.exe" >nul && ( set PYOK=1 ) || ( set PYOK=0 )
if "!PYOK!"=="1" (
    for /f "tokens=2 delims= " %%v in ('py -V') do set PYVER=%%v
    echo    -^> 파이썬 런처 감지(py). 버전: !PYVER!
    set PYEXE=py -3.11
) else (
    REM 포터블 파이썬 확인
    if exist "bin\python311\python.exe" (
        set PATH=%ROOT%bin\python311;%ROOT%bin\python311\Scripts;%PATH%
        set PYEXE=%ROOT%bin\python311\python.exe
        echo    -^> 포터블 Python 3.11 사용
    ) else (
        REM 시스템 Python 확인
        python --version 2>nul | findstr /R "3\.1[1-9]" >nul
        if !errorlevel! equ 0 (
            set PYEXE=python
            echo    -^> 시스템 Python 3.11+ 감지
        ) else (
            echo    -^> Python 3.11 없음. 다음 중 하나를 수행하세요:
            echo       1. Python 3.11+ 설치: https://www.python.org/downloads/
            echo       2. bin\python311 폴더에 포터블 파이썬 배치
            pause
            exit /b 1
        )
    )
)

REM Python 실행 테스트
!PYEXE! -c "print('Python OK')" >nul 2>&1
if !errorlevel! neq 0 (
    echo    -^> Python 실행 실패. 설치를 확인하세요.
    pause
    exit /b 1
)

echo [3/6] 가상환경 생성...
if not exist "venv" (
    echo    -^> 새 가상환경 생성 중...
    !PYEXE! -m venv venv
    if !errorlevel! neq 0 (
        echo    -^> 가상환경 생성 실패
        pause
        exit /b 1
    )
    echo    -^> 가상환경 생성 완료
) else (
    echo    -^> 기존 가상환경 사용
)

REM 가상환경 활성화
call venv\Scripts\activate.bat
if !errorlevel! neq 0 (
    echo    -^> 가상환경 활성화 실패
    pause
    exit /b 1
)

echo [4/6] pip 업그레이드 및 패키지 설치...
echo    -^> pip 업그레이드 중...
python -m pip install --upgrade pip --quiet

echo    -^> 필수 패키지 설치 중... (5-10분 소요)
if exist "requirements.txt" (
    pip install -r requirements.txt --quiet
    if !errorlevel! neq 0 (
        echo    -^> 패키지 설치 실패. 인터넷 연결을 확인하세요.
        pause
        exit /b 1
    )
) else (
    echo    -^> requirements.txt 없음. 생성 중...
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
        echo aiofiles
        echo prometheus-client
    ) > requirements.txt
    pip install -r requirements.txt --quiet
)
echo    -^> 패키지 설치 완료

echo [5/6] Qdrant/Ollama 준비...
REM Qdrant 포터블 확인
if exist "bin\qdrant\qdrant.exe" (
    echo    -^> 포터블 Qdrant 감지
) else if exist "src\bin\qdrant.exe" (
    echo    -^> 기존 Qdrant 경로 사용
) else (
    echo    -^> Qdrant 실행 파일 없음. 다음 중 하나를 수행하세요:
    echo       1. bin\qdrant\qdrant.exe 배치 (포터블 버전)
    echo       2. INSTALL_ENHANCED.bat 실행 (자동 다운로드)
)

REM Ollama 확인
where ollama >nul 2>&1
if !errorlevel! equ 0 (
    echo    -^> 시스템 Ollama 감지
) else (
    if exist "bin\ollama\ollama.exe" (
        echo    -^> 포터블 Ollama 사용
    ) else (
        echo    -^> Ollama 미설치. 시스템에 설치하거나 bin\ollama 폴더에 배치
    )
)

echo [6/6] 모델 자원 확인...
if exist "bin\models\bge-m3-local" (
    echo    -^> 로컬 임베딩 모델 감지
) else if exist "src\bin\bge-m3-local" (
    echo    -^> 기존 모델 경로 사용
) else (
    echo    -^> BGE-M3 모델 없음. 첫 실행 시 자동 다운로드됨
)

REM 필요한 폴더 생성
if not exist "src\bin" mkdir "src\bin"
if not exist "chunk_outputs" mkdir "chunk_outputs"
if not exist "email_attachments" mkdir "email_attachments"
if not exist "logs" mkdir "logs"
if not exist "storage" mkdir "storage"
if not exist "bin" mkdir "bin"

echo.
echo ============================================================
echo   ✅ 설치가 완료되었습니다!
echo ============================================================
echo.
echo 다음 단계:
echo   1. run.bat 실행하여 시스템 시작
echo   2. 브라우저에서 http://localhost:8001 접속
echo.
echo 설정 파일:
echo   - .env: 환경 변수 설정
echo   - config.json: 시스템 설정
echo.
pause
exit /b 0