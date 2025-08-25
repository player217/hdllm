@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo ======================================================
echo  LLM RAG 시스템 설치 스크립트
echo ======================================================
echo.

:: Python 버전 확인
echo 1. Python 버전을 확인합니다...
python --version >nul 2>&1
if errorlevel 1 (
    echo [오류] Python이 설치되어 있지 않습니다.
    echo Python 3.11 이상을 설치해주세요.
    pause
    exit /b 1
)

python --version

:: 가상환경 생성
echo.
echo 2. 가상환경을 생성합니다...
if exist "venv" (
    echo 기존 가상환경이 발견되었습니다. 삭제하고 새로 생성합니까? (Y/N)
    set /p choice=
    if /i "!choice!"=="Y" (
        echo 기존 가상환경을 삭제합니다...
        rmdir /s /q venv
        python -m venv venv
    ) else (
        echo 기존 가상환경을 유지합니다.
    )
) else (
    python -m venv venv
)

:: 가상환경 활성화
echo.
echo 3. 가상환경을 활성화합니다...
call venv\Scripts\activate.bat

:: pip 업그레이드
echo.
echo 4. pip를 최신 버전으로 업그레이드합니다...
python -m pip install --upgrade pip

:: 필수 패키지 설치
echo.
echo 5. 필수 패키지를 설치합니다...
echo    이 과정은 시간이 좀 걸릴 수 있습니다...
echo.

:: requirements.txt 파일이 있으면 사용
if exist "requirements.txt" (
    echo requirements.txt 파일을 사용하여 패키지를 설치합니다...
    pip install -r requirements.txt
) else (
    echo requirements.txt 파일이 없습니다. 개별 패키지를 설치합니다...
    
    :: 백엔드 관련
    echo [1/10] FastAPI 및 웹 서버 패키지...
    pip install fastapi==0.104.1 uvicorn[standard]==0.24.0 python-multipart==0.0.6
    
    echo [2/10] Qdrant 클라이언트...
    pip install qdrant-client==1.7.0
    
    echo [3/10] 임베딩 모델 관련...
    pip install langchain-huggingface==0.0.3 sentence-transformers
    
    echo [4/10] PyTorch (CPU 버전)...
    pip install torch==2.1.0 --index-url https://download.pytorch.org/whl/cpu
    
    echo [5/10] 문서 처리 관련...
    pip install tika openpyxl xlwings extract-msg
    
    echo [6/10] GUI 프레임워크...
    pip install PySide6
    
    echo [7/10] Windows 통합...
    pip install pywin32==306
    
    echo [8/10] 유틸리티...
    pip install requests==2.31.0 tqdm
    
    echo [9/10] Transformers 및 한국어 처리...
    pip install transformers sentencepiece
    
    echo [10/10] Langchain...
    pip install langchain
)

:: 폴더 구조 생성
echo.
echo 6. 필요한 폴더를 생성합니다...
if not exist "src\bin" mkdir "src\bin"
if not exist "chunk_outputs" mkdir "chunk_outputs"
if not exist "email_attachments" mkdir "email_attachments"
if not exist "logs" mkdir "logs"

:: 기본 설정 파일 생성
echo.
echo 7. 기본 설정 파일을 생성합니다...

:: preprocessing_rules.json
if not exist "preprocessing_rules.json" (
    (
        echo {
        echo   "pii_patterns": [],
        echo   "clean_steps": []
        echo }
    ) > preprocessing_rules.json
    echo    - preprocessing_rules.json 생성됨
)

:: config.json
if not exist "config.json" (
    (
        echo {
        echo   "mail_qdrant_path": "%USERPROFILE%\\Documents\\qdrant_mail",
        echo   "doc_qdrant_path": "%USERPROFILE%\\Documents\\qdrant_document",
        echo   "local_msg_path": ""
        echo }
    ) > config.json
    echo    - config.json 생성됨
)

:: 설치 완료 메시지
echo.
echo ======================================================
echo  설치가 완료되었습니다!
echo ======================================================
echo.
echo 다음 단계:
echo.
echo 1. src\bin 폴더에 필요한 파일 복사:
echo    - qdrant.exe (Qdrant 벡터 DB 실행 파일)
echo    - bge-m3-local\ (임베딩 모델 폴더)
echo    - kobart-local\ (한국어 요약 모델 폴더 - 선택사항)
echo.
echo 2. 프로그램 실행:
echo    - GUI 프로그램: venv\Scripts\activate && python src\HDLLM.py
echo    - 또는 RUN.bat 실행
echo.
echo 3. 웹 서버 실행:
echo    - 백엔드: run_backend.bat
echo    - 프론트엔드: run_frontend.bat
echo.
echo * 주의: 다음에 프로그램을 실행할 때는 먼저 가상환경을 활성화하세요:
echo   venv\Scripts\activate
echo.
pause