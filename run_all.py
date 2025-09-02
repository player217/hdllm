import subprocess
import time
from pathlib import Path
import sys

# 1. 스크립트의 위치를 기준으로 프로젝트의 기본 경로들을 설정합니다.
project_root = Path(__file__).parent.resolve()
backend_dir = project_root / "backend"
activate_script = project_root / "venv" / "Scripts" / "activate.bat"

# 2. Ollama 서버 실행
ollama_command = (
    "set OLLAMA_NUM_GPU_LAYERS=100 && "
    "set OLLAMA_HOST=0.0.0.0 && "
    "set OLLAMA_ORIGINS=[\"*\"] && "
    "ollama serve"
)
subprocess.Popen(
    ["cmd.exe", "/k", ollama_command],
    creationflags=subprocess.CREATE_NEW_CONSOLE
)
print("[OK] Ollama 서버 시작됨")
time.sleep(4)

# 3. FastAPI 백엔드 실행
if not activate_script.exists() or not backend_dir.exists():
    print("[ERROR] 오류: 'venv' 또는 'backend' 폴더를 찾을 수 없습니다.")
    print(f"    - venv 경로: {activate_script}")
    print(f"    - backend 경로: {project_root}")
    sys.exit(1)

# [수정] f-string 내부의 경로 변수 주변 큰따옴표 제거
fastapi_command = (
    f'call {activate_script} && '
    f'cd /d {project_root} && '
    "uvicorn backend.main:app --host 0.0.0.0 --port 8080"
)
subprocess.Popen(
    ["cmd.exe", "/k", fastapi_command],
    creationflags=subprocess.CREATE_NEW_CONSOLE
)
print("[OK] FastAPI 백엔드 서버 시작됨")
time.sleep(6)

# 4. HTML 서버 실행
subprocess.Popen(["start", "", "http_server.bat"], shell=True)
print("[OK] HTML 프론트엔드 서버 시작됨")

print("\n[SUCCESS] 모든 서버가 시작되었습니다.")