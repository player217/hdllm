@echo off
echo Starting test...
cd /d "%~dp0"
set PROJECT_ROOT=%~dp0
echo PROJECT_ROOT is: [%PROJECT_ROOT%]
echo Full path to check: [%PROJECT_ROOT%src\bin]

if exist "src\bin" (
    echo SUCCESS: src\bin exists using relative path
) else (
    echo FAIL: src\bin NOT found using relative path
)

if exist "%PROJECT_ROOT%src\bin" (
    echo SUCCESS: %PROJECT_ROOT%src\bin exists using full path
) else (
    echo FAIL: %PROJECT_ROOT%src\bin NOT found using full path
)

echo End of test.
pause