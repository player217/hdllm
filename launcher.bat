@echo off
chcp 65001 >nul
title TT Launcher

:: 실행 파일의 디렉토리를 프로젝트 루트로 설정
cd /d "%~dp0"

:: tray_launcher.exe 실행
echo Starting TT System Tray...
start "" "dist\tray_launcher.exe"

:: 창 자동 종료
exit