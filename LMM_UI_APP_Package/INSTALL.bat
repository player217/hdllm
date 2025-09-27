@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

:: --- PYTHONPATH 환경 변수 초기화 ---
set PYTHONPATH=

title TT - 통합 설치 프로그램

cd /d "%~dp0"
set PROJECT_ROOT=%~dp0

echo ======================================================
echo  TT - 통합 설치 시스템
echo ======================================================
echo.
echo [INFO] 오프라인 설치 파일을 사용하여 필수 프로그램을 설치합니다.
echo.
echo [DEBUG] PROJECT_ROOT=[%PROJECT_ROOT%]
echo [DEBUG] Checking path: %PROJECT_ROOT%src\bin
echo.

:: --- 0. src/bin 폴더 확인 ---
echo [DEBUG] Step 0: Checking src/bin folder...
echo [DEBUG] Current directory: %CD%
echo [DEBUG] Testing dir command result...
dir src\bin >nul 2>&1 && (
    echo [DEBUG] Step 0: src/bin folder found successfully!
    goto :src_bin_found
) || (
    echo [DEBUG] dir command failed, trying alternative check...
    echo [ERROR] src/bin 폴더를 찾을 수 없습니다.
    echo        오프라인 설치 파일이 포함된 src/bin 폴더가 필요합니다.
    echo        다음 파일들이 src/bin 폴더에 있어야 합니다:
    echo        - python-3.11.9-amd64.exe
    echo        - OllamaSetup.exe
    echo        - jdk-21_windows-x64_bin.exe (또는 유사한 JDK 설치파일)
    goto :fatal_error
)
:src_bin_found

:: --- 1. Python 3.11 설치/확인 ---
echo [DEBUG] Step 1: Starting Python 3.11 check...
echo [1/7] Python 3.11 확인 중...
py -3.11 -V >nul 2>&1 && (
    echo [DEBUG] Step 1: Python 3.11 already installed!
    echo     Python 3.11이 이미 설치되어 있습니다.
    goto :python_check_done
) || (
    echo [DEBUG] Step 1: Python 3.11 not found, checking installer...
    echo     Python 3.11이 설치되지 않았습니다. 설치를 시작합니다...
    dir "src\bin\python-3.11.9-amd64.exe" >nul 2>&1 && (
        echo [DEBUG] Step 1: Python installer found, starting installation...
        echo     설치 파일 실행 중... (설치 화면의 지시를 따라주세요)
        echo     [중요] 'Add Python to PATH' 옵션을 반드시 체크하세요!
        start /wait "" "src\bin\python-3.11.9-amd64.exe"
        
        :: 설치 후 다시 확인
        echo [DEBUG] Step 1: Verifying Python installation...
        py -3.11 -V >nul 2>&1 && (
            echo [DEBUG] Step 1: Python installation verified successfully!
            echo     Python 3.11 설치 완료!
        ) || (
            echo [ERROR] Python 3.11 설치가 완료되지 않았습니다.
            echo         수동으로 설치 후 다시 실행해주세요.
            goto :fatal_error
        )
    ) || (
        echo [ERROR] Python 설치 파일을 찾을 수 없습니다:
        echo         src\bin\python-3.11.9-amd64.exe
        goto :fatal_error
    )
)
:python_check_done

:: --- 2. Java JDK 설치/확인 ---
echo [DEBUG] Step 2: Starting Java JDK check...
echo [2/7] Java JDK 확인 중...
java -version >nul 2>&1
echo [DEBUG] Step 2: java -version result: errorlevel=%errorlevel%
if %errorlevel% neq 0 (
    echo [DEBUG] Step 2: Java JDK not found, checking installer...
    echo     Java JDK가 설치되지 않았습니다. 설치를 시작합니다...
    
    :: JDK 설치 파일 찾기 (여러 버전 가능)
    set JDK_INSTALLER=
    for %%f in ("src\bin\jdk*.exe") do (
        set JDK_INSTALLER=%%f
    )
    
    if defined JDK_INSTALLER (
        echo [DEBUG] Step 2: JDK installer found: !JDK_INSTALLER!
        echo     JDK 설치 파일 실행 중...
        start /wait "" "!JDK_INSTALLER!"
        echo [DEBUG] Step 2: JDK installation completed!
        echo     Java JDK 설치 완료!
    ) else (
        echo [DEBUG] Step 2: No JDK installer found, continuing without Java
        echo [WARNING] Java JDK 설치 파일을 찾을 수 없습니다.
        echo           Tika 파서 기능이 제한될 수 있습니다.
        echo           계속 진행합니다...
    )
) else (
    echo [DEBUG] Step 2: Java JDK already installed!
    echo     Java JDK가 이미 설치되어 있습니다.
)

:: --- 3. Ollama 설치/확인 ---
echo [3/7] Ollama 확인 중...
ollama -v >nul 2>&1
if %errorlevel% neq 0 (
    echo     Ollama가 설치되지 않았습니다. 설치를 시작합니다...
    if exist "src\bin\OllamaSetup.exe" (
        echo     Ollama 설치 파일 실행 중...
        start /wait "" "src\bin\OllamaSetup.exe"
        
        :: 설치 후 확인
        ollama -v >nul 2>&1
        if !errorlevel! neq 0 (
            echo [WARNING] Ollama 설치가 완료되지 않았거나 PATH에 추가되지 않았습니다.
            echo           시스템 재시작이 필요할 수 있습니다.
        ) else (
            echo     Ollama 설치 완료!
        )
    ) else (
        echo [ERROR] Ollama 설치 파일을 찾을 수 없습니다:
        echo         src\bin\OllamaSetup.exe
        goto :fatal_error
    )
) else (
    echo     Ollama가 이미 설치되어 있습니다.
)

:: --- 4. 가상환경 생성 ---
echo [DEBUG] Step 4: Starting virtual environment creation...
echo [4/7] Python 가상환경 생성 중...
if exist venv (
    echo [DEBUG] Step 4: Existing venv found, deleting...
    echo     기존 가상환경을 삭제하고 새로 생성합니다...
    :: 강제 삭제 - 파일 속성 재설정 후 삭제
    attrib -r -s -h venv\*.* /s /d >nul 2>&1
    rmdir /s /q venv >nul 2>&1
    if exist venv (
        echo [DEBUG] Step 4: Standard deletion failed, trying PowerShell...
        powershell -Command "if (Test-Path 'venv') { Remove-Item -Path 'venv' -Recurse -Force -ErrorAction SilentlyContinue }" >nul 2>&1
    )
    if exist venv (
        echo [WARNING] 기존 가상환경 삭제에 실패했습니다. 새 이름으로 생성합니다...
        set VENV_DIR=venv
    ) else (
        set VENV_DIR=venv
    )
) else (
    set VENV_DIR=venv
)

:: Python 3.11.9로 가상환경 생성 (명확한 버전 지정)
echo [DEBUG] Step 4: Creating virtual environment with py -3.11 -m venv %VENV_DIR%
py -3.11 -m venv %VENV_DIR% >nul
echo [DEBUG] Step 4: py -3.11 -m venv %VENV_DIR% result: errorlevel=%errorlevel%
if %errorlevel% neq 0 (
    echo [ERROR] 가상환경 생성 실패!
    echo [DEBUG] Step 4: Virtual environment creation FAILED - going to fatal_error
    goto :fatal_error
)
echo [DEBUG] Step 4: Virtual environment created successfully in %VENV_DIR%!
echo     가상환경 생성 완료!

:: --- 5. Python 패키지 설치 ---
echo [5/7] Python 패키지 설치 중...
call .\%VENV_DIR%\Scripts\activate.bat
python -m pip install --upgrade pip >nul 2>&1
echo     pip 업그레이드 완료

echo     requirements.txt 패키지 설치 중 (시간이 걸릴 수 있습니다)...
python -m pip install -r requirements.txt --no-cache-dir
if %errorlevel% neq 0 (
    echo [ERROR] 패키지 설치 실패!
    goto :fatal_error
)
echo     모든 Python 패키지 설치 완료!

:: --- 6. Ollama 모델 다운로드 ---
echo [6/7] Ollama 모델 확인 중...

:: config.json에서 모델명 읽기
set MODEL_NAME=gemma3:4b
if exist config.json (
    for /f "delims=" %%i in ('powershell -NoProfile -Command "try { (Get-Content config.json -Raw -ErrorAction Stop | ConvertFrom-Json).ollama.default_model } catch { 'gemma3:4b' }" 2^>nul') do set MODEL_NAME=%%i
    echo     config.json에서 모델 설정 읽음: !MODEL_NAME!
) else (
    echo     [WARNING] config.json을 찾을 수 없습니다. 기본 모델 사용: !MODEL_NAME!
)

:: Ollama 서비스가 실행 중인지 확인
ollama list >nul 2>&1
if %errorlevel% neq 0 (
    echo     Ollama 서비스 시작 중...
    start /b ollama serve >nul 2>&1
    timeout /t 5 /nobreak >nul
)

:: 모델 확인 및 설치
ollama list 2>nul | findstr "!MODEL_NAME!" >nul
if %errorlevel% neq 0 (
    echo     !MODEL_NAME! 모델 다운로드 중 (인터넷 연결 필요)...
    ollama pull !MODEL_NAME!
    if %errorlevel% neq 0 (
        echo [ERROR] !MODEL_NAME! 모델 다운로드 실패!
        echo        가능한 원인:
        echo        1. 인터넷 연결을 확인하세요
        echo        2. Ollama 서비스가 실행 중인지 확인하세요
        echo        3. 모델명이 올바른지 확인하세요: !MODEL_NAME!
        echo.
        echo        수동으로 설치하려면: ollama pull !MODEL_NAME!
        pause
        goto :fatal_error
    ) else (
        echo     !MODEL_NAME! 모델 다운로드 완료!
    )
) else (
    echo     !MODEL_NAME! 모델이 이미 설치되어 있습니다.
)

:: --- 7. BGE-M3 모델 확인 ---
echo [7/7] BGE-M3 모델 확인 중...
if exist "src\bin\bge-m3-local" (
    echo     BGE-M3 모델 확인 완료!
    echo     경로: src\bin\bge-m3-local
) else (
    echo [WARNING] BGE-M3 모델 폴더를 찾을 수 없습니다.
    echo           src/bin/bge-m3-local 폴더가 필요합니다.
    echo           임베딩 기능이 제한될 수 있습니다.
)

:: --- 8. 시작 프로그램 등록 ---
echo [8/8] 시작 프로그램 등록 중...

:: tray_launcher.exe 존재 확인
if exist "%PROJECT_ROOT%dist\tray_launcher.exe" (
    echo     tray_launcher.exe 파일 확인 완료
    
    :: 시작 프로그램 폴더 경로 설정
    set "STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
    
    :: VBScript를 이용한 바로가기 생성
    echo     시작 프로그램에 바로가기 생성 중...
    
    :: VBScript 파일 생성
    echo Set WshShell = CreateObject^("WScript.Shell"^) > "%TEMP%\create_shortcut.vbs"
    echo Set Shortcut = WshShell.CreateShortcut^("!STARTUP_FOLDER!\TT Launcher.lnk"^) >> "%TEMP%\create_shortcut.vbs"
    echo Shortcut.TargetPath = "!PROJECT_ROOT!dist\tray_launcher.exe" >> "%TEMP%\create_shortcut.vbs"
    echo Shortcut.WorkingDirectory = "!PROJECT_ROOT!" >> "%TEMP%\create_shortcut.vbs"
    echo Shortcut.IconLocation = "!PROJECT_ROOT!dist\tray_launcher.exe" >> "%TEMP%\create_shortcut.vbs"
    echo Shortcut.Description = "TT Application Launcher" >> "%TEMP%\create_shortcut.vbs"
    echo Shortcut.Save >> "%TEMP%\create_shortcut.vbs"
    
    :: VBScript 실행
    cscript //nologo "%TEMP%\create_shortcut.vbs" 2>nul
    set CREATE_RESULT=!errorlevel!
    
    :: 임시 파일 삭제
    del "%TEMP%\create_shortcut.vbs" >nul 2>&1
    
    :: 결과 확인
    if exist "!STARTUP_FOLDER!\TT Launcher.lnk" (
        echo     시작 프로그램 등록 완료!
        echo     다음 부팅 시 자동으로 TT가 시스템 트레이에서 실행됩니다.
    ) else (
        echo [WARNING] 시작 프로그램 등록 실패 (에러 코드: !CREATE_RESULT!)
        echo           수동으로 등록하려면:
        echo           1. Win+R → shell:startup 실행
        echo           2. dist\tray_launcher.exe 바로가기 생성
    )
) else (
    echo [INFO] tray_launcher.exe를 찾을 수 없습니다.
    echo        시스템 트레이 기능을 사용하려면:
    echo        1. 먼저 애플리케이션을 빌드하세요
    echo        2. INSTALL.bat을 다시 실행하세요
)

echo.
echo ======================================================
echo  통합 설치 완료!
echo ======================================================
echo.
echo  설치된 구성요소:
echo  - Python 3.11 및 가상환경
echo  - Java JDK (Tika 파서용)
echo  - Ollama 및 LLM 모델
echo  - 모든 Python 패키지
echo  - BGE-M3 임베딩 모델
echo  - 시작 프로그램 등록 (tray_launcher.exe)
echo.
echo  다음 단계:
echo  1. RUN.bat 실행 - GUI 프로그램 시작
echo  2. run_all.py 실행 - 웹 인터페이스 시작
echo.
echo ======================================================

goto :end

:fatal_error
echo.
echo ======================================================
echo  설치 실패! 위의 오류 메시지를 확인하세요.
echo ======================================================
echo.
echo  문제 해결 방법:
echo  1. bin 폴더에 필요한 설치 파일이 있는지 확인
echo  2. 관리자 권한으로 실행 필요할 수 있음
echo  3. 바이러스 백신이 설치를 차단하지 않는지 확인
echo.

:end
endlocal
pause