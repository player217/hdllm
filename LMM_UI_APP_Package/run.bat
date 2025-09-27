@echo off
setlocal
chcp 65001 >nul

:: --- 공통/경로 초기화 ---
set PYTHONPATH=
set "APP_HOME=%~dp0"
rem %%~dp0는 경로 끝에 \를 포함하므로, Robocopy의 인자 파싱 오류 방지를 위해 제거합니다.
set "APP_HOME=%APP_HOME:~0,-1%"
cd /d "%APP_HOME%"
title TT - RUN

echo ======================================================
echo  Starting TT...
echo ======================================================
echo.

:: ==================================================================
:: [0] 서버 업데이트 폴더 스캔 후 로컬에 덮어쓰기 (네트워크 안전성 강화)
::     - 서버 폴더: \\203.228.239.6\선체생산\999) [실험실]\HDLLM\update
::     - 제외: venv, logs, chunk_outputs, storage, *.lock, *.tmp
::  ⚠️ 한글/괄호/공백 경로 안전하게 처리 위해 pushd 사용
:: ==================================================================
set "UPDATE_UNC=\\203.228.239.6\선체생산\999) [실험실]\HDLLM\update"
echo [INFO] Checking update folder: %UPDATE_UNC%

rem UNC 경로 접근 테스트 (네트워크 타임아웃 설정)
echo   -> Testing network access...
ping -n 1 -w 2000 203.228.239.6 >nul 2>&1
if errorlevel 1 (
    echo   -> Update server not reachable. Skipping update.
    goto post_update
)

rem UNC 경로를 임시 드라이브 문자로 매핑
pushd "%UPDATE_UNC%" >nul 2>&1
if errorlevel 1 (
    echo   -> Update folder not accessible. Skipping update.
    goto post_update
) else (
    rem 현재 디렉터리가 임시 드라이브로 매핑됨
    echo   -> Update path mapped successfully.

    rem 내용 유무 확인
    if exist ".\*" (
        echo   -> Update files detected. Applying to "%APP_HOME%"

        rem robocopy 실행 (단일 라인으로 정리)
        robocopy . "%APP_HOME%" /E /R:1 /W:1 /COPY:DAT /DCOPY:T /FFT /NFL /NDL /NP /XF *.lock *.tmp /XD venv logs chunk_outputs storage

        if %ERRORLEVEL% GEQ 8 (
            echo [WARN] Robocopy returned code %ERRORLEVEL%. Update may have failed or partially applied.
        ) else (
            echo   -> Update applied successfully.
        )
    ) else (
        echo   -> No files in update folder. Skip update.
    )

    rem 임시 드라이브 매핑 해제
    popd >nul 2>&1
)

:post_update
echo.

:: --- 1. 가상환경 확인 ---
echo [INFO] Checking for virtual environment...
if not exist ".\venv\Scripts\activate.bat" (
    echo [FATAL ERROR] Virtual environment not found. Please run INSTALL.bat first.
    pause
    exit /b
)
echo   -> Virtual environment check: PASSED
echo.

:: --- 2. 가상환경 활성화 ---
echo [INFO] Activating virtual environment...
call .\venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo [FATAL ERROR] Failed to activate virtual environment!
    pause
    exit /b
)
echo   -> Environment activated successfully.
echo.

:: --- 3. 파이썬 스크립트 실행 ---
echo [INFO] Running the Python GUI script...
echo   -> Command: python .\src\HDLLM.py
echo ------------------------------------------------------
echo.

python .\src\HDLLM.py

echo.
echo ------------------------------------------------------
echo [DEBUG] Python script has finished. Press any key to exit.
pause
endlocal