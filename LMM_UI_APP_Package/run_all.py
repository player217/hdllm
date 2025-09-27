import subprocess
import time
import socket
from pathlib import Path
import sys
import os
import argparse

# psutil 사용 시도 (없으면 기본 기능만 사용)
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("Note: psutil이 설치되지 않아 고급 프로세스 관리 기능이 제한됩니다.")

# 명령행 인수 처리 (GUI에서 전달되는 인수 처리를 위한 방어적 코드)
parser = argparse.ArgumentParser(description='TT 서버 시작 스크립트')
parser.add_argument('--qdrant_path', type=str, help='Qdrant 데이터베이스 경로 (현재 사용하지 않음)')
parser.add_argument('--service_type', type=str, help='서비스 타입 (현재 사용하지 않음)')
args = parser.parse_args()

# 스크립트의 위치를 기준으로 프로젝트의 기본 경로들을 설정합니다.
project_root = Path(__file__).parent.resolve()
backend_dir = project_root / "backend"
activate_script = project_root / "venv" / "Scripts" / "activate.bat"

print("======================================================")
print(" TT - 서버 시작")
print("======================================================")
print()

# 프로세스 관리 함수들
def is_port_in_use(port):
    """포트가 사용 중인지 확인"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        result = s.connect_ex(('localhost', port))
        return result == 0

def kill_processes_by_name_windows(process_names):
    """Windows에서 프로세스 이름으로 프로세스 종료 (taskkill 사용)"""
    killed = []
    for process_name in process_names:
        try:
            result = subprocess.run(
                ['taskkill', '/f', '/im', process_name],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                killed.append(f"{process_name} (taskkill)")
        except subprocess.TimeoutExpired:
            pass
        except Exception:
            pass
    return killed

def kill_processes_by_name_psutil(process_names):
    """psutil을 사용한 프로세스 종료"""
    killed = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info['name'] and any(name.lower() in proc.info['name'].lower() for name in process_names):
                proc.terminate()
                killed.append(f"{proc.info['name']} (PID: {proc.info['pid']})")
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return killed

def kill_processes_by_port_windows(ports):
    """Windows에서 포트를 사용하는 프로세스 종료 (netstat + taskkill)"""
    killed = []
    for port in ports:
        try:
            # netstat으로 포트를 사용하는 PID 찾기
            result = subprocess.run(
                ['netstat', '-ano'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            for line in result.stdout.split('\n'):
                if f':{port}' in line and 'LISTENING' in line:
                    parts = line.split()
                    if len(parts) >= 5:
                        pid = parts[-1]
                        try:
                            subprocess.run(
                                ['taskkill', '/f', '/pid', pid],
                                capture_output=True,
                                timeout=5
                            )
                            killed.append(f"Process on port {port} (PID: {pid})")
                        except:
                            pass
        except:
            pass
    return killed

def kill_processes_by_port_psutil(ports):
    """psutil을 사용한 포트 기반 프로세스 종료"""
    killed = []
    for port in ports:
        for proc in psutil.process_iter(['pid', 'name', 'connections']):
            try:
                connections = proc.info.get('connections')
                if connections:
                    for conn in connections:
                        if hasattr(conn, 'laddr') and conn.laddr.port == port:
                            proc.terminate()
                            killed.append(f"{proc.info['name']} on port {port} (PID: {proc.info['pid']})")
                            break
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
    return killed

def check_and_cleanup_existing_processes():
    """기존 프로세스들을 확인하고 정리"""
    print("[0/3] 기존 프로세스 확인 및 정리 중...")
    
    # 체크할 포트들
    backend_port = 8080
    frontend_port = 8001
    
    cleanup_needed = False
    
    # 포트 사용 상태 확인
    if is_port_in_use(backend_port):
        print(f"      포트 {backend_port} 사용 중 - 백엔드 프로세스 정리 필요")
        cleanup_needed = True
        
    if is_port_in_use(frontend_port):
        print(f"      포트 {frontend_port} 사용 중 - 프론트엔드 프로세스 정리 필요")
        cleanup_needed = True
    
    if cleanup_needed:
        print("      기존 프로세스들을 정리합니다...")
        
        # 프로세스 종료 방식 선택
        if PSUTIL_AVAILABLE:
            # psutil을 사용한 정교한 프로세스 관리
            killed_by_name = kill_processes_by_name_psutil(['python.exe', 'pythonw.exe'])
            killed_by_port = kill_processes_by_port_psutil([backend_port, frontend_port])
        else:
            # Windows 기본 명령어 사용
            killed_by_name = kill_processes_by_name_windows(['python.exe', 'pythonw.exe'])
            killed_by_port = kill_processes_by_port_windows([backend_port, frontend_port])
        
        for process_info in killed_by_name + killed_by_port:
            print(f"        종료됨: {process_info}")
        
        # 프로세스 종료 대기
        print("      프로세스 종료 대기 중...")
        time.sleep(3)
        
        # 정리 후 재확인
        still_in_use = []
        if is_port_in_use(backend_port):
            still_in_use.append(str(backend_port))
        if is_port_in_use(frontend_port):
            still_in_use.append(str(frontend_port))
            
        if still_in_use:
            print(f"      [WARNING] 여전히 사용 중인 포트: {', '.join(still_in_use)}")
            print("      수동으로 프로세스를 종료해야 할 수 있습니다.")
        else:
            print("      모든 포트가 정리되었습니다.")
    else:
        print("      정리할 프로세스가 없습니다.")
    
    print()

# 정리 함수 정의
def cleanup_temp_files():
    """임시 파일들을 정리합니다."""
    temp_files = [project_root / "temp_backend.bat"]
    for temp_file in temp_files:
        try:
            if temp_file.exists():
                temp_file.unlink()
                print(f"      임시 파일 정리됨: {temp_file.name}")
        except Exception as e:
            print(f"      임시 파일 정리 실패: {temp_file.name} - {e}")

# 프로그램 종료 시 정리 함수 등록
import atexit
atexit.register(cleanup_temp_files)

# 기존 프로세스 정리
check_and_cleanup_existing_processes()

# 1. Ollama 서버 실행
print("[1/3] Ollama 서버 시작 중...")
try:
    # Ollama 환경변수 설정
    ollama_env = os.environ.copy()
    ollama_env["OLLAMA_NUM_GPU_LAYERS"] = "100"
    ollama_env["OLLAMA_HOST"] = "0.0.0.0"
    ollama_env["OLLAMA_ORIGINS"] = "[\"*\"]"

    subprocess.Popen(
        ["cmd.exe", "/k", "ollama serve"],
        creationflags=subprocess.CREATE_NEW_CONSOLE,
        env=ollama_env
    )
    print("      Ollama 서버 시작됨 (GPU 레이어: 100)")
    
    # 서버 시작 대기
    time.sleep(4)
    
    # config.json에서 기본 모델 읽기 및 확인
    try:
        import json
        config_path = Path(__file__).parent / "config.json"
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                model = config.get('ollama', {}).get('default_model', 'gemma3:4b')
                auto_pull = config.get('ollama', {}).get('auto_pull', True)
                
                print(f"      모델 확인 중: {model}")
                
                # 모델 설치 확인
                result = subprocess.run(
                    ["ollama", "list"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0 and model not in result.stdout:
                    if auto_pull:
                        print(f"      {model} 모델 다운로드 중...")
                        pull_result = subprocess.run(
                            ["ollama", "pull", model],
                            capture_output=True,
                            text=True,
                            timeout=300  # 5분 타임아웃
                        )
                        if pull_result.returncode == 0:
                            print(f"      {model} 모델 다운로드 완료!")
                        else:
                            print(f"      [WARNING] {model} 모델 다운로드 실패")
                    else:
                        print(f"      [INFO] {model} 모델이 설치되지 않았습니다.")
                else:
                    print(f"      {model} 모델 준비 완료")
    except Exception as e:
        print(f"      [WARNING] 모델 확인 중 오류: {e}")
        
except Exception as e:
    print(f"      [ERROR] Ollama 서버 시작 실패: {e}")
    print("      계속 진행합니다...")

# 2. FastAPI 백엔드 실행
print("[2/3] FastAPI 백엔드 서버 시작 중...")
if not activate_script.exists() or not backend_dir.exists():
    print("[ERROR] 가상환경 또는 backend 폴더를 찾을 수 없습니다.")
    print(f"        먼저 install.bat를 실행해주세요.")
    sys.exit(1)

try:
    # 백엔드 포트 최종 확인
    if is_port_in_use(8080):
        print("      [WARNING] 포트 8080이 여전히 사용 중입니다. 백엔드 시작을 건너뜁니다.")
    else:
        # FastAPI 백엔드를 위한 배치 명령 생성
        fastapi_batch_cmd = f'''
@echo off
chcp 65001 >nul
title TT - Backend Server
call "{activate_script}"
cd /d "{project_root}"
uvicorn backend.main:app --host 0.0.0.0 --port 8080
'''

        # 임시 배치 파일 생성
        temp_batch = project_root / "temp_backend.bat"
        with open(temp_batch, 'w', encoding='utf-8') as f:
            f.write(fastapi_batch_cmd)

        subprocess.Popen(
            ["cmd.exe", "/k", str(temp_batch)],
            creationflags=subprocess.CREATE_NEW_CONSOLE,
            cwd=str(project_root)
        )
        print("      FastAPI 백엔드 서버 시작됨 (포트: 8080)")
except Exception as e:
    print(f"      [ERROR] FastAPI 백엔드 서버 시작 실패: {e}")
    print("      계속 진행합니다...")
time.sleep(6)

# 3. HTML 프론트엔드 서버 실행
print("[3/3] HTML 프론트엔드 서버 시작 중...")
try:
    frontend_dir = project_root / "frontend"
    python_exe = project_root / "venv" / "Scripts" / "python.exe"
    
    if not frontend_dir.exists():
        print(f"      [ERROR] Frontend 폴더를 찾을 수 없습니다: {frontend_dir}")
        print("      프론트엔드 서버 시작을 건너뜁니다.")
    elif not python_exe.exists():
        print(f"      [ERROR] Python 실행 파일을 찾을 수 없습니다: {python_exe}")
        print("      프론트엔드 서버 시작을 건너뜁니다.")
    elif is_port_in_use(8001):
        print("      [WARNING] 포트 8001이 여전히 사용 중입니다. 프론트엔드 시작을 건너뜁니다.")
    else:
        # 배치 파일 대신 Python HTTP 서버 직접 실행
        subprocess.Popen(
            [str(python_exe), "-m", "http.server", "8001"],
            creationflags=subprocess.CREATE_NEW_CONSOLE,
            cwd=str(frontend_dir)
        )
        print("      HTML 프론트엔드 서버 시작됨 (포트: 8001)")
except Exception as e:
    print(f"      [ERROR] 프론트엔드 서버 시작 실패: {e}")
    print("      계속 진행합니다...")

# 최종 서버 상태 확인
print()
print("======================================================")
print(" 서버 시작 완료 - 상태 확인")
print("======================================================")
time.sleep(2)

backend_status = "✅ 실행 중" if is_port_in_use(8080) else "❌ 실행되지 않음"
frontend_status = "✅ 실행 중" if is_port_in_use(8001) else "❌ 실행되지 않음"

print(f" - 백엔드 서버 (포트 8080): {backend_status}")
print(f" - 프론트엔드 서버 (포트 8001): {frontend_status}")
print()
print(" 접속 주소:")
print(" - 웹 인터페이스: http://localhost:8001")
print(" - API 문서: http://localhost:8080/docs")
print()
print(" 종료하려면 각 콘솔 창을 닫으세요.")
print("======================================================")