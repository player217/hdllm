@echo off
setlocal ENABLEDELAYEDEXPANSION
chcp 65001 >nul 2>&1

REM HD������� Gauss-1 RAG System - Enhanced Runner
REM Version: 2.1 - Smart Port Detection & Process Management
REM Date: 2025-01-30

title HD������� Gauss-1 RAG System

echo ============================================================
echo   HD������� Gauss-1 RAG System - ���� ���α׷� v2.1
echo ============================================================
echo.

REM ���� ���
set ROOT=%~dp0
cd /d "%ROOT%"

REM 1) ����ȯ�� Ȱ��ȭ
echo [1/5] ����ȯ�� Ȯ��...
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] ����ȯ���� �����ϴ�. ���� install.bat �� �����ϼ���.
    pause
    exit /b 1
)
call venv\Scripts\activate.bat
echo    -^> ����ȯ�� Ȱ��ȭ �Ϸ�
echo.

REM 2) ���� Qdrant ����(���ο�) - �̹� �������� �ǳʶ�
echo [2/5] Qdrant ���� DB ����...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":6333" ^| findstr "LISTENING"') do set QPID=%%p
if not defined QPID (
    if exist "bin\qdrant\qdrant.exe" (
        start "Qdrant Server" /B "bin\qdrant\qdrant.exe" --storage-dir "%ROOT%storage\qdrant"
        echo    -^> Qdrant ���� �� (���ͺ� ����)...
    ) else if exist "src\bin\qdrant.exe" (
        start "Qdrant Server" /B "src\bin\qdrant.exe"
        echo    -^> Qdrant ���� �� (���� ���)...
    ) else (
        echo    -^> Qdrant ���� ���� ����. ��ġ�� Ȯ���ϼ���.
    )
    timeout /t 3 /nobreak >nul
) else (
    echo    -^> Qdrant �̹� ���� �� (PID: !QPID!)
)
echo.

REM 3) Ollama ���� ����
echo [3/5] Ollama LLM ���� ����...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":11434" ^| findstr "LISTENING"') do set OPID=%%p
if not defined OPID (
    where ollama >nul 2>&1
    if !errorlevel! equ 0 (
        start "Ollama Server" /B ollama serve
        echo    -^> Ollama ���� ��...
    ) else if exist "bin\ollama\ollama.exe" (
        start "Ollama Server" /B "bin\ollama\ollama.exe" serve
        echo    -^> Ollama ���� �� (���ͺ� ����)...
    ) else (
        echo    -^> Ollama �̼�ġ. LLM ����� ���ѵ˴ϴ�.
    )
    timeout /t 3 /nobreak >nul
) else (
    echo    -^> Ollama �̹� ���� �� (PID: !OPID!)
)
echo.

REM 4) �鿣�� API ���� ����
echo [4/5] Backend API ���� ����...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8080" ^| findstr "LISTENING"') do set BPID=%%p
if not defined BPID (
    echo    -^> FastAPI ���� ���� �� (��Ʈ 8080)...
    
    REM .env ���� Ȯ��
    if exist ".env" (
        start "Backend API" cmd /k "cd backend && python -m uvicorn main:app --host 0.0.0.0 --port 8080 --reload --env-file ..\.env"
    ) else if exist ".env.test" (
        start "Backend API" cmd /k "cd backend && python -m uvicorn main:app --host 0.0.0.0 --port 8080 --reload --env-file ..\.env.test"
    ) else (
        start "Backend API" cmd /k "cd backend && python -m uvicorn main:app --host 0.0.0.0 --port 8080 --reload"
    )
    
    timeout /t 5 /nobreak >nul
) else (
    echo    -^> Backend API �̹� ���� �� (PID: !BPID!)
)
echo.

REM 5) ����Ʈ���� ���� ����
echo [5/5] Frontend �� ���� ����...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8001" ^| findstr "LISTENING"') do set FPID=%%p
if not defined FPID (
    echo    -^> �� ���� ���� �� (��Ʈ 8001)...
    start "Frontend Server" cmd /k "cd frontend && python -m http.server 8001"
    timeout /t 2 /nobreak >nul
) else (
    echo    -^> Frontend �̹� ���� �� (PID: !FPID!)
)
echo.

REM ����: GUI ���ø����̼� ����
echo GUI ���ø����̼��� �����Ͻðڽ��ϱ�? (Y/N)
set /p RUNGUI=����: 
if /i "!RUNGUI!"=="Y" (
    echo GUI ���ø����̼� ���� ��...
    start "GUI Application" "%ROOT%venv\Scripts\python.exe" "%ROOT%src\HDLLM.py"
)

echo.
echo ============================================================
echo   ? ��� ���񽺰� ���۵Ǿ����ϴ�!
echo ============================================================
echo.
echo ���� ����:
echo   ? �� �������̽�: http://localhost:8001
echo   ? API ����: http://localhost:8080
echo   ? API ����: http://localhost:8080/docs
echo   ? ���� Ȯ��: http://localhost:8080/status
echo.
echo ������ �ҽ�:
echo   ? ���� Qdrant: 127.0.0.1:6333
echo   ? �μ� Qdrant: 10.150.104.37:6333
echo.
echo ���� ���:
echo   ? �� â�� ������ GUI�� ����˴ϴ�
echo   ? ��� ���� ����: kill.bat ����
echo.

REM ������ ����
echo �������� ���ðڽ��ϱ�? (Y/N)
set /p OPENBROWSER=����: 
if /i "!OPENBROWSER!"=="Y" (
    start http://localhost:8001
)

echo.
echo [��� ��] �ƹ� Ű�� ������ �����մϴ�...
pause >nul
exit /b 0
