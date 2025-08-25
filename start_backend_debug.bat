@echo off
echo Starting backend in DEBUG mode...
set RAG_DEBUG=true
set RAG_VERBOSE=true
venv\Scripts\python.exe backend\main.py
pause