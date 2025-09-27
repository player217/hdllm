@echo off
echo ====== PATH DEBUG ======
cd /d "%~dp0"
set PROJECT_ROOT=%~dp0
echo PROJECT_ROOT=[%PROJECT_ROOT%]
echo Current Directory: %CD%
echo.
echo Checking src folder:
if exist "src" (
    echo [OK] src folder exists
) else (
    echo [ERROR] src folder NOT found
)
echo.
echo Checking src\bin folder:
if exist "src\bin" (
    echo [OK] src\bin folder exists
) else (
    echo [ERROR] src\bin folder NOT found
)
echo.
echo Checking %PROJECT_ROOT%src\bin:
if exist "%PROJECT_ROOT%src\bin" (
    echo [OK] %PROJECT_ROOT%src\bin exists
) else (
    echo [ERROR] %PROJECT_ROOT%src\bin NOT found
)
echo.
echo Directory listing of src:
dir src /b
echo.
echo Directory listing of src\bin:
dir src\bin /b
echo =========================
pause