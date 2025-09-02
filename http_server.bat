@echo off
:: 이 스크립트는 프로젝트 최상위 폴더(LLM_UI_APP)에 있다고 가정합니다.

:: 1. 이 스크립트가 있는 위치를 기준으로 frontend 폴더로 이동합니다.
cd /d "%~dp0frontend"

:: 2. 프로젝트의 로컬 가상환경(venv)에 있는 파이썬을 사용해 웹 서버를 실행합니다.
"%~dp0venv\Scripts\python.exe" -m http.server 8001