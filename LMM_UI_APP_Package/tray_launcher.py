# tray_launcher.py (Final Patched Version)
# pip install pystray pillow psutil

import os
import sys
import time
import socket
import psutil
import shutil
import json
import threading
import subprocess
import multiprocessing
from pathlib import Path
import msvcrt

import pystray
from pystray import MenuItem as Item, Menu
from PIL import Image, ImageDraw

# 통합 관리 시스템 import
from process_manager import get_process_manager
from log_manager import setup_tray_logging, get_log_manager

# -------------------------
# 경로/환경 설정
# -------------------------
def get_project_root() -> Path:
    env_home = os.getenv("HDLLM_HOME", "").strip()
    if env_home:
        root = Path(env_home).expanduser().resolve()
        if root.exists():
            return root
    
    # PyInstaller로 컴파일된 경우
    if getattr(sys, 'frozen', False):
        # 실행 파일이 있는 디렉토리
        exe_dir = Path(sys.executable).parent
        
        # dist 폴더에서 실행되는 경우 상위 디렉토리가 프로젝트 루트
        if exe_dir.name == "dist":
            project_root = exe_dir.parent
        else:
            # 이미 프로젝트 루트에서 실행 중
            project_root = exe_dir
        
        # config.json으로 검증
        if (project_root / "config.json").exists():
            return project_root
        
        # config.json을 찾아서 프로젝트 루트 확인
        current = exe_dir
        for _ in range(3):  # 최대 3단계 상위까지 확인
            if (current / "config.json").exists():
                return current
            current = current.parent
        
        # 기본값: exe의 부모 디렉토리
        return exe_dir.parent
    
    return Path(__file__).parent.resolve()

PROJECT_ROOT = get_project_root()
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_PATH = PROJECT_ROOT / "config.json"
QDRANT_BIN = PROJECT_ROOT / "qdrant_bin" / "qdrant.exe"
VENV_PYTHON = PROJECT_ROOT / "venv" / "Scripts" / "python.exe"
HTTP_SERVER_BAT = PROJECT_ROOT / "http_server.bat"

# 포트 및 로그 경로
OLLAMA_PORT = 11434
BACKEND_PORT = 8080
FRONTEND_PORT = 8001
OLLAMA_LOG = LOG_DIR / "ollama.log"
BACKEND_LOG = LOG_DIR / "backend.log"
FRONTEND_LOG = LOG_DIR / "frontend.log"
QDRANT_LOG = LOG_DIR / "qdrant.log"
UPDATER_LOG = LOG_DIR / "updater.log"

# 전역 상태 변수
# CHILD_PROCESSES = []  # ProcessManager로 대체됨
STOP_EVENT = threading.Event()
EXIT_IN_PROGRESS = threading.Event()  # 종료 진행 상태 플래그
LOCK_FILE = PROJECT_ROOT / "tray_launcher.lock"
_LOCK_FH = None

# 통합 관리 시스템 초기화
process_manager = get_process_manager()
log_managers = setup_tray_logging()  # 로거들 딕셔너리 반환

# 개별 로거들 설정
updater_logger = log_managers['updater']
backend_logger = log_managers['backend']
frontend_logger = log_managers['frontend']
qdrant_logger = log_managers['qdrant']
ollama_logger = log_managers['ollama']

# 로그 정리 스케줄러 시작 (매일 오전 2시)
try:
    log_manager_instance = get_log_manager()
    log_manager_instance.start_cleanup_scheduler(cleanup_hour=2)
    updater_logger.info("✅ 로그 정리 스케줄러 시작됨 (매일 02:00)")
except Exception as e:
    updater_logger.warning(f"⚠️ 로그 정리 스케줄러 시작 실패: {e}")

# -------------------------
# 단일 인스턴스 보장 (파일 잠금)
# -------------------------
def acquire_single_instance_lock():
    global _LOCK_FH
    try:
        LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        _LOCK_FH = open(LOCK_FILE, "w")
        msvcrt.locking(_LOCK_FH.fileno(), msvcrt.LK_NBLCK, 1)
        return True
    except OSError:
        if _LOCK_FH: _LOCK_FH.close(); _LOCK_FH = None
        return False

def release_single_instance_lock():
    global _LOCK_FH
    try:
        if _LOCK_FH:
            msvcrt.locking(_LOCK_FH.fileno(), msvcrt.LK_UNLCK, 1)
            _LOCK_FH.close()
            _LOCK_FH = None
    except Exception: pass

# -------------------------
# 유틸리티 함수
# -------------------------
def append_log(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", errors="ignore") as f:
        f.write(time.strftime("[%Y-%m-%d %H:%M:%S] ") + text + "\n")

def http_alive(url: str, timeout: float = 2.0, must_ok: bool = False) -> bool:
    try:
        import urllib.request
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return (resp.status == 200) if must_ok else (200 <= resp.status < 500)
    except Exception:
        return False

def is_port_open(port: int, host="127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex((host, port)) == 0

def popen_detached(cmd, log_path: Path = None, env=None, cwd: Path = None):
    """Create detached subprocess.Popen process"""
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    f = open(log_path, "a", encoding="utf-8", errors="ignore") if log_path else subprocess.DEVNULL
    return subprocess.Popen(
        cmd, stdout=f, stderr=f, env=env or os.environ.copy(),
        creationflags=creationflags, cwd=str(cwd or PROJECT_ROOT), shell=False
    )

def load_config() -> dict:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f: return json.load(f)
    except Exception as e:
        append_log(UPDATER_LOG, f"[ERROR] Failed to load config.json: {e}")
        return {}

def stop_by_port(port: int):
    for conn in psutil.net_connections(kind="inet"):
        if conn.laddr and conn.laddr.port == port and conn.status == psutil.CONN_LISTEN:
            try: psutil.Process(conn.pid).terminate()
            except psutil.Error: pass

# -------------------------
# 서비스 제어
# -------------------------
# ✅ [수정] 컬렉션 손상 시 자동 격리 및 재시도 기능이 추가된 Qdrant 실행 함수
def start_qdrant_mail(force: bool = False):
    """
    config.json 의 mail_qdrant_path 를 작업 디렉터리(CWD)로 지정해
    qdrant_bin/qdrant.exe 를 인자 없이 실행.
    실행 실패(컬렉션 JSON 에러 등) 시 my_documents 컬렉션을 백업 격리 후 재시도.
    """
    cfg = load_config()
    auto = bool(cfg.get("auto_start_qdrant", False))
    host = str(cfg.get("endpoints", {}).get("mail", {}).get("qdrant_host", "127.0.0.1"))
    try:
        port = int(cfg.get("endpoints", {}).get("mail", {}).get("qdrant_port", 6333))
    except (ValueError, TypeError):
        port = 6333

    mail_path = cfg.get("mail_qdrant_path")
    append_log(QDRANT_LOG, f"auto_start_qdrant={auto}, force={force}, host={host}, port={port}, should_start={force or auto}")

    # 이미 살아 있으면 패스
    if http_alive(f"http://{host}:{port}/readyz", must_ok=True) or is_port_open(port, host):
        append_log(QDRANT_LOG, f"Qdrant(mail) already alive at http://{host}:{port}")
        return True

    if not (force or auto):
        append_log(QDRANT_LOG, "auto_start_qdrant=False → skip starting Qdrant(mail).")
        return True  # 스킵(실패 아님)

    if not mail_path:
        append_log(QDRANT_LOG, "[ERROR] mail_qdrant_path is empty in config.json")
        return False
    if not QDRANT_BIN.exists():
        append_log(QDRANT_LOG, f"[FATAL] qdrant.exe not found: {QDRANT_BIN}")
        return False

    try:
        Path(mail_path).mkdir(parents=True, exist_ok=True)
    except Exception as e:
        append_log(QDRANT_LOG, f"[ERROR] Cannot create storage dir: {mail_path} ({e})")
        return False

    def _launch() -> subprocess.Popen:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        cmd = [str(QDRANT_BIN)]
        append_log(QDRANT_LOG, f"Launching: {QDRANT_BIN}  (cwd={mail_path})")
        return subprocess.Popen(
            cmd,
            cwd=str(Path(mail_path)),
            stdout=open(QDRANT_LOG, "a", encoding="utf-8", errors="ignore"),
            stderr=subprocess.STDOUT,
            startupinfo=si,
            creationflags=subprocess.CREATE_NO_WINDOW,
            shell=False
        )

    # 1차 실행
    proc = _launch()
    process_manager.register_process("qdrant_mail", proc, ports=[port])
    append_log(QDRANT_LOG, f"Qdrant process registered with PID {proc.pid}")

    # 최대 30초 기다리며 성공/실패 판단
    for _ in range(60):
        # 정상 기동?
        if http_alive(f"http://{host}:{port}/readyz", must_ok=True) or is_port_open(port, host):
            append_log(QDRANT_LOG, f"Qdrant(mail) is up at http://{host}:{port}")
            return True
        # 비정상 종료?
        if proc.poll() is not None:
            append_log(QDRANT_LOG, f"[ERROR] Qdrant exited early with code {proc.returncode}")
            break
        time.sleep(0.5)

    # 실패 → 로그 살펴보고 손상 패턴이면 격리 후 재시도
    try:
        last_log = ""
        with open(QDRANT_LOG, "r", encoding="utf-8", errors="ignore") as f:
            last_log = f.read()[-4096:]  # 마지막 4KB만
    except Exception:
        pass

    corrupt_markers = (
        "Can't read collection config",
        "Json error: invalid type: null, expected usize",
    )
    if any(m in last_log for m in corrupt_markers):
        # my_documents 컬렉션 격리
        storage_dir = Path(mail_path) / "storage" / "collections" / "my_documents"
        if storage_dir.exists():
            ts = time.strftime("%Y%m%d_%H%M%S")
            quarantine = storage_dir.parent / f"my_documents_corrupt_{ts}"
            try:
                storage_dir.rename(quarantine)
                append_log(QDRANT_LOG, f"[WARN] Corrupt collection moved to: {quarantine}")
            except Exception as e:
                append_log(QDRANT_LOG, f"[ERROR] Failed to quarantine collection: {e}")
                return False
        else:
            append_log(QDRANT_LOG, "[WARN] Corrupt collection marker found but path missing; skip quarantine.")

        # 재실행
        proc = _launch()
        process_manager.register_process("qdrant_mail", proc, ports=[port])
        append_log(QDRANT_LOG, f"Qdrant process re-registered with PID {proc.pid}")
        for _ in range(60):
            if http_alive(f"http://{host}:{port}/readyz", must_ok=True) or is_port_open(port, host):
                append_log(QDRANT_LOG, f"Qdrant(mail) is up after quarantine at http://{host}:{port}")
                return True
            if proc.poll() is not None:
                append_log(QDRANT_LOG, f"[ERROR] Qdrant exited again with code {proc.returncode}")
                break
            time.sleep(0.5)

    append_log(QDRANT_LOG, "[ERROR] Qdrant(mail) startup failed.")
    return False

def run_backend_process():
    append_log(BACKEND_LOG, "Backend process started (in-process fallback).")
    try:
        if str(PROJECT_ROOT) not in sys.path: sys.path.insert(0, str(PROJECT_ROOT))
        import uvicorn
        uvicorn.run("backend.main:app", host="0.0.0.0", port=BACKEND_PORT)
    except Exception as e:
        append_log(BACKEND_LOG, f"[FATAL] Exception in backend process: {e}")

def start_backend():
    if http_alive(f"http://127.0.0.1:{BACKEND_PORT}/health", must_ok=True): return True
    backend_logger.info("Attempting to start backend process...")

    if VENV_PYTHON.exists():
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONPATH"] = str(PROJECT_ROOT)
        cmd = [str(VENV_PYTHON), "-X", "utf8", "-m", "uvicorn", "backend.main:app", 
               "--host", "0.0.0.0", "--port", str(BACKEND_PORT),
               "--timeout-keep-alive", "30", "--timeout-graceful-shutdown", "10"]
        
        # ProcessManager를 사용하여 프로세스 등록
        process = popen_detached(cmd, log_path=BACKEND_LOG, env=env, cwd=PROJECT_ROOT / "backend")
        if process:
            process_manager.register_process("backend", process, ports=[BACKEND_PORT])
            backend_logger.info(f"Backend process registered with PID {process.pid}")
        
        for _ in range(40):
            if http_alive(f"http://127.0.0.1:{BACKEND_PORT}/health", must_ok=True):
                backend_logger.info("Backend is up via subprocess."); return True
            time.sleep(0.5)
        backend_logger.warning("Backend did not come up within 20 seconds.")
        return False
    backend_logger.error("venv/Scripts/python.exe not found.")
    return False

def start_frontend():
    """
    Start Frontend HTTP server using subprocess.Popen with proper cwd handling.
    Fixed to use same pattern as Backend and Qdrant services for PyInstaller compatibility.
    """
    if http_alive(f"http://127.0.0.1:{FRONTEND_PORT}/", must_ok=True): 
        frontend_logger.info("Frontend already running")
        return True
    
    frontend_logger.info("Attempting to start frontend process...")
    
    # frontend 디렉토리 확인 및 생성
    frontend_dir = PROJECT_ROOT / "frontend"
    if not frontend_dir.exists():
        frontend_dir.mkdir(parents=True, exist_ok=True)
        frontend_logger.info(f"Created frontend directory: {frontend_dir}")
        
        # 기본 index.html 생성
        index_file = frontend_dir / "index.html"
        if not index_file.exists():
            index_file.write_text("""<!DOCTYPE html>
<html>
<head>
    <title>TT System</title>
    <meta charset="utf-8">
</head>
<body>
    <h1>TT System Frontend</h1>
    <p>Frontend server is running on port 8001</p>
</body>
</html>""", encoding="utf-8")
            frontend_logger.info(f"Created default index.html: {index_file}")

    # Use subprocess.Popen with cwd parameter instead of multiprocessing.Process + os.chdir()
    if VENV_PYTHON.exists():
        # Option 1: Use venv Python with http.server module
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        cmd = [str(VENV_PYTHON), "-X", "utf8", "-m", "http.server", str(FRONTEND_PORT)]
        
        frontend_logger.info(f"Starting frontend with command: {' '.join(cmd)}")
        frontend_logger.info(f"Working directory: {frontend_dir}")
        
        try:
            process = popen_detached(cmd, log_path=FRONTEND_LOG, env=env, cwd=frontend_dir)
            if process:
                process_manager.register_process("frontend", process, ports=[FRONTEND_PORT])
                frontend_logger.info(f"Frontend process registered with PID {process.pid}")
                
                # Wait for server to start
                for i in range(20):
                    if http_alive(f"http://127.0.0.1:{FRONTEND_PORT}/", must_ok=True):
                        frontend_logger.info("Frontend is up via subprocess")
                        return True
                    time.sleep(0.5)
                
                frontend_logger.warning("Frontend did not come up within 10 seconds")
        except Exception as e:
            frontend_logger.error(f"Failed to start frontend with venv Python: {e}")
    else:
        frontend_logger.warning("venv/Scripts/python.exe not found, trying system Python")
    
    # Option 2: Use system Python as fallback
    try:
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        cmd = ["python", "-m", "http.server", str(FRONTEND_PORT)]
        
        frontend_logger.info(f"Fallback: Starting frontend with system Python: {' '.join(cmd)}")
        
        process = popen_detached(cmd, log_path=FRONTEND_LOG, env=env, cwd=frontend_dir)
        if process:
            process_manager.register_process("frontend_system", process, ports=[FRONTEND_PORT])
            frontend_logger.info(f"Frontend system Python process registered with PID {process.pid}")
            
            # Wait for server to start
            for i in range(20):
                if http_alive(f"http://127.0.0.1:{FRONTEND_PORT}/", must_ok=True):
                    frontend_logger.info("Frontend is up via system Python")
                    return True
                time.sleep(0.5)
        
        frontend_logger.warning("Frontend did not come up with system Python within 10 seconds")
    except Exception as e:
        frontend_logger.error(f"Failed to start frontend with system Python: {e}")
    
    # Option 3: Batch file fallback (legacy)
    if HTTP_SERVER_BAT.exists():
        frontend_logger.info(f"Final fallback: trying batch file: {HTTP_SERVER_BAT}")
        try:
            process = popen_detached(["cmd.exe", "/c", str(HTTP_SERVER_BAT)], log_path=FRONTEND_LOG)
            if process:
                process_manager.register_process("frontend_bat", process, ports=[FRONTEND_PORT])
                frontend_logger.info(f"Frontend batch process registered with PID {process.pid}")
                
                # Wait for server to start
                for i in range(20):
                    if http_alive(f"http://127.0.0.1:{FRONTEND_PORT}/", must_ok=True):
                        frontend_logger.info("Frontend is up via batch file")
                        return True
                    time.sleep(0.5)
        except Exception as e:
            frontend_logger.error(f"Failed to start frontend with batch file: {e}")
    
    frontend_logger.error("All frontend startup methods failed")
    return False

def start_ollama():
    if http_alive(f"http://127.0.0.1:{OLLAMA_PORT}/", must_ok=False): 
        append_log(OLLAMA_LOG, "Ollama server already running")
        ensure_model_loaded()  # 모델 확인
        return True
        
    if not shutil.which("ollama"):
        append_log(OLLAMA_LOG, "[WARN] 'ollama' command not found.")
        return False
        
    env = os.environ.copy()
    env.setdefault("OLLAMA_HOST", "0.0.0.0")
    process = popen_detached(["ollama", "serve"], log_path=OLLAMA_LOG, env=env)
    process_manager.register_process("ollama", process, ports=[OLLAMA_PORT])
    append_log(OLLAMA_LOG, f"Ollama process registered with PID {process.pid}")
    
    # 서버 시작 대기
    for _ in range(40):
        if http_alive(f"http://127.0.0.1:{OLLAMA_PORT}/", must_ok=False): 
            append_log(OLLAMA_LOG, "Ollama server started successfully")
            ensure_model_loaded()  # 모델 확인 및 로드
            return True
        time.sleep(0.5)
    return False

def ensure_model_loaded():
    """config.json에서 모델을 읽고 필요시 다운로드"""
    try:
        config_path = get_project_root() / "config.json"
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                model = config.get('ollama', {}).get('default_model', 'gemma3:4b')
                auto_pull = config.get('ollama', {}).get('auto_pull', True)
                
                append_log(OLLAMA_LOG, f"Checking model: {model}")
                
                # 모델 확인
                result = subprocess.run(
                    ["ollama", "list"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0 and model not in result.stdout:
                    if auto_pull:
                        append_log(OLLAMA_LOG, f"Pulling model {model}...")
                        pull_result = subprocess.run(
                            ["ollama", "pull", model],
                            capture_output=True,
                            text=True,
                            timeout=300
                        )
                        if pull_result.returncode == 0:
                            append_log(OLLAMA_LOG, f"Model {model} pulled successfully")
                        else:
                            append_log(OLLAMA_LOG, f"[WARN] Failed to pull model {model}")
                    else:
                        append_log(OLLAMA_LOG, f"[INFO] Model {model} not installed, auto_pull disabled")
                else:
                    append_log(OLLAMA_LOG, f"Model {model} is ready")
    except Exception as e:
        append_log(OLLAMA_LOG, f"[WARN] Error checking model: {e}")

def start_all(force: bool = False):
    start_qdrant_mail(force=force)
    time.sleep(0.3)
    start_ollama()
    time.sleep(0.3)
    start_backend()
    time.sleep(0.3)
    start_frontend()

def stop_all():
    """Stop all managed processes and services with timeout"""
    append_log(UPDATER_LOG, "Stopping all services via ProcessManager...")
    
    # Stop log cleanup scheduler first
    try:
        log_manager_instance = get_log_manager()
        log_manager_instance.stop_cleanup_scheduler()
        updater_logger.info("✅ 로그 정리 스케줄러 중지됨")
    except Exception as e:
        updater_logger.warning(f"⚠️ 로그 정리 스케줄러 중지 실패: {e}")
    
    # Use ProcessManager for coordinated shutdown with 30 second total timeout
    start_time = time.time()
    timeout_seconds = 30.0
    
    try:
        results = process_manager.terminate_all(parallel=True)
        
        # Log results
        success_count = sum(1 for success in results.values() if success)
        total_count = len(results)
        elapsed = time.time() - start_time
        append_log(UPDATER_LOG, f"ProcessManager shutdown: {success_count}/{total_count} processes terminated in {elapsed:.1f}s")
        
    except Exception as e:
        elapsed = time.time() - start_time
        append_log(UPDATER_LOG, f"ProcessManager shutdown failed after {elapsed:.1f}s: {e}")
    
    # Check if we exceeded timeout
    elapsed = time.time() - start_time
    if elapsed > timeout_seconds:
        append_log(UPDATER_LOG, f"⚠️ ProcessManager shutdown exceeded {timeout_seconds}s timeout")
        return False
    
    # Fallback port-based cleanup (already handled by ProcessManager._cleanup_by_ports)
    try:
        qport = int(load_config().get("endpoints", {}).get("mail", {}).get("qdrant_port", 6333))
    except (ValueError, TypeError):
        qport = 6333
    
    for port in [FRONTEND_PORT, BACKEND_PORT, OLLAMA_PORT, qport]:
        stop_by_port(port)
    
    append_log(UPDATER_LOG, f"Stop all completed in {time.time() - start_time:.1f}s")
    return True

def force_exit_after_timeout(timeout_seconds: float = 5.0):
    """강제 종료 타이머 - 타임아웃 후 sys.exit(0) 호출"""
    def timeout_exit():
        time.sleep(timeout_seconds)
        if not EXIT_IN_PROGRESS.is_set():
            return  # 정상 종료 완료됨
            
        append_log(UPDATER_LOG, f"⚠️ 강제 종료: {timeout_seconds}초 타임아웃 초과")
        updater_logger.warning(f"강제 종료 실행 - {timeout_seconds}초 타임아웃 초과")
        
        # 최후의 수단으로 모든 프로세스 강제 종료
        try:
            current_pid = os.getpid()
            current_process = psutil.Process(current_pid)
            children = current_process.children(recursive=True)
            
            for child in children:
                try:
                    child.kill()
                except psutil.NoSuchProcess:
                    pass
        except Exception:
            pass
        
        # 현재 프로세스도 강제 종료
        try:
            os._exit(0)
        except:
            sys.exit(0)
    
    timer_thread = threading.Thread(target=timeout_exit, daemon=True)
    timer_thread.start()

# -------------------------
# 트레이 아이콘 UI 및 메뉴
# -------------------------
def get_current_status():
    cfg = load_config()
    try:
        qport = int(cfg.get("endpoints", {}).get("mail", {}).get("qdrant_port", 6333))
    except (ValueError, TypeError):
        qport = 6333

    def qdrant_ok(base):
        urls = [f"{base}/readyz", f"{base}/livez", f"{base}/collections", base + "/"]
        port = int(base.rsplit(':',1)[-1])
        return any(http_alive(u, timeout=1.0, must_ok=False) for u in urls) or is_port_open(port, "127.0.0.1")

    return {
        "백엔드": http_alive(f"http://127.0.0.1:{BACKEND_PORT}/health", timeout=1.2, must_ok=True),
        "개인":   qdrant_ok(f"http://127.0.0.1:{qport}"),
        "부서":   http_alive("http://10.150.104.37:6333/readyz", timeout=1.2, must_ok=False) or http_alive("http://10.150.104.37:6333/collections", timeout=1.2, must_ok=False),
        "Ollama": http_alive(f"http://127.0.0.1:{OLLAMA_PORT}/", timeout=1.2, must_ok=False),
    }

def make_icon_image():
    """상태에 따른 동적 시스템 트레이 아이콘 생성"""
    statuses = get_current_status()
    on_count = sum(statuses.values())
    
    # 기본 트레이 아이콘 파일 경로
    base_icon_path = PROJECT_ROOT / "assets" / "tray_icon.ico"
    
    try:
        # ICO 파일이 있으면 사용, 없으면 동적 생성
        if base_icon_path.exists():
            # ICO 파일을 기반으로 상태 표시 추가
            img = Image.open(base_icon_path).convert("RGBA")
            # 32x32 크기로 리사이즈 (시스템 트레이 적합)
            img = img.resize((32, 32), Image.Resampling.LANCZOS)
            
            # 상태에 따른 색상 오버레이
            overlay = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            
            # 상태 표시용 작은 원 그리기
            if on_count == len(statuses):
                # 모든 서비스 정상: 녹색 점
                draw.ellipse((22, 22, 30, 30), fill=(0, 200, 0, 200))
            elif on_count > 0:
                # 일부 서비스 실행 중: 주황색 점
                draw.ellipse((22, 22, 30, 30), fill=(255, 165, 0, 200))
            else:
                # 모든 서비스 중단: 빨간색 점
                draw.ellipse((22, 22, 30, 30), fill=(200, 0, 0, 200))
            
            # 오버레이 합성
            img = Image.alpha_composite(img, overlay)
        else:
            # ICO 파일이 없으면 기존 방식으로 동적 생성
            color = (200, 0, 0)
            if on_count == len(statuses): color = (0, 180, 0)
            elif on_count > 0: color = (220, 160, 0)
            img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
            
            # 메인 원
            ImageDraw.Draw(img).ellipse((4, 4, 28, 28), fill=(70, 130, 180, 255))
            # 상태 표시 원
            ImageDraw.Draw(img).ellipse((20, 20, 30, 30), fill=color)
            # 'T' 텍스트
            try:
                from PIL import ImageFont
                font = ImageFont.load_default()
                bbox = ImageDraw.Draw(img).textbbox((0, 0), "T", font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                x = (32 - text_width) // 2
                y = (32 - text_height) // 2
                ImageDraw.Draw(img).text((x, y), "T", font=font, fill=(255, 255, 255, 255))
            except:
                # 폰트 로드 실패시 단순 원형 아이콘
                pass
            
        return img
        
    except Exception as e:
        # 오류 발생시 기본 아이콘으로 폴백
        updater_logger.warning(f"아이콘 생성 오류: {e}, 기본 아이콘 사용")
        color = (200, 0, 0)
        if on_count == len(statuses): color = (0, 180, 0)
        elif on_count > 0: color = (220, 160, 0)
        img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        ImageDraw.Draw(img).ellipse((4, 4, 28, 28), fill=color)
        return img

def status_text() -> str:
    statuses = get_current_status()
    parts = [f"{name}[{'O' if status else 'X'}]" for name, status in statuses.items()]
    return " ".join(parts)

def update_status_periodically(icon):
    while not STOP_EVENT.is_set():
        try:
            icon.icon = make_icon_image()
            icon.title = status_text()
        except Exception: break
        STOP_EVENT.wait(5)

def update_ui_immediately(icon):
    if icon:
        icon.icon = make_icon_image()
        icon.title = status_text()

# ✅ [추가] "개인 Qdrant 시작/재시작" 메뉴 액션 함수
def on_start_qdrant(icon, item):
    ok = start_qdrant_mail(force=True)
    update_ui_immediately(icon)
    if not ok:
        try:
            icon.notify("Qdrant(mail) 기동 실패. logs/qdrant.log 확인", "HDLLM Tray")
        except Exception:
            pass

def on_start(icon, item):
    start_all(force=True)
    update_ui_immediately(icon)

def on_stop(icon, item):
    stop_all()
    update_ui_immediately(icon)

def on_restart(icon, item):
    stop_all()
    time.sleep(1.0)
    start_all(force=True)
    update_ui_immediately(icon)

def safe_shutdown_process(icon):
    """안전한 종료 프로세스를 별도 스레드에서 실행"""
    start_time = time.time()
    append_log(UPDATER_LOG, "=== 안전한 종료 프로세스 시작 ===")
    updater_logger.info("트레이 종료 프로세스 시작")
    
    try:
        # 1. 백그라운드 스레드 중지 신호
        STOP_EVENT.set()
        append_log(UPDATER_LOG, "✓ 백그라운드 스레드 중지 신호 전송")
        
        # 2. 모든 서비스 정리 (30초 타임아웃)
        shutdown_success = stop_all()
        elapsed_shutdown = time.time() - start_time
        
        if shutdown_success:
            append_log(UPDATER_LOG, f"✓ 서비스 정리 완료 ({elapsed_shutdown:.1f}초)")
        else:
            append_log(UPDATER_LOG, f"⚠️ 서비스 정리 타임아웃 ({elapsed_shutdown:.1f}초)")
        
        # 3. pystray 아이콘 중지
        try:
            icon.stop()
            append_log(UPDATER_LOG, "✓ 시스템 트레이 아이콘 중지")
        except Exception as e:
            append_log(UPDATER_LOG, f"⚠️ 시스템 트레이 아이콘 중지 실패: {e}")
        
        # 4. 종료 완료 표시
        total_elapsed = time.time() - start_time
        append_log(UPDATER_LOG, f"=== 안전한 종료 완료 ({total_elapsed:.1f}초) ===")
        updater_logger.info(f"트레이 종료 완료 - 총 소요시간: {total_elapsed:.1f}초")
        
        # 종료 완료 플래그 설정
        EXIT_IN_PROGRESS.clear()
        
    except Exception as e:
        elapsed = time.time() - start_time
        append_log(UPDATER_LOG, f"[ERROR] 안전한 종료 중 오류 발생 ({elapsed:.1f}초): {e}")
        updater_logger.error(f"안전한 종료 중 오류: {e}")
        # 오류가 발생해도 종료 진행
        try:
            icon.stop()
        except:
            pass

def on_exit(icon, item):
    """✅ [수정] 개선된 종료 핸들러 - 5초 타임아웃과 강제 종료 포함"""
    # 중복 호출 방지
    if EXIT_IN_PROGRESS.is_set():
        return
    
    EXIT_IN_PROGRESS.set()
    append_log(UPDATER_LOG, ">>> 트레이 종료 요청 받음 <<<")
    updater_logger.info("사용자가 트레이 종료를 요청했습니다")
    
    try:
        # 사용자에게 종료 알림
        icon.notify("시스템을 종료하는 중...", "TT System")
    except Exception:
        pass
    
    # 강제 종료 타이머 시작 (5초)
    force_exit_after_timeout(5.0)
    
    # 별도 스레드에서 안전한 종료 실행
    shutdown_thread = threading.Thread(
        target=safe_shutdown_process,
        args=(icon,),
        daemon=True
    )
    shutdown_thread.start()

def open_logs_folder(icon, item): os.startfile(str(LOG_DIR))
def show_status(icon, item): icon.notify(status_text(), "TT")

# ✅ [수정] "개인 Qdrant 시작/재시작" 메뉴 아이템 추가
def build_menu():
    return Menu(
        Item(lambda item: status_text(), None, enabled=False),
        Item("상태 알림 띄우기", show_status),
        Item("로그 폴더 열기", open_logs_folder),
        Item("개인 Qdrant 시작/재시작", on_start_qdrant),
        Menu.SEPARATOR,
        Item("모두 실행", on_start),
        Item("모두 재실행", on_restart),
        Item("모두 종료", on_stop),
        Menu.SEPARATOR,
        Item("종료", on_exit)
    )

# -------------------------
# 프로그램 진입점
# -------------------------
if __name__ == "__main__":
    multiprocessing.freeze_support()
    if not acquire_single_instance_lock():
        sys.exit(0)
    try:
        append_log(UPDATER_LOG, f"[BOOT] CONFIG_PATH = {CONFIG_PATH.resolve()}")
        start_all(force=False)
        icon = pystray.Icon(
            "TT",
            make_icon_image(),
            title=status_text(),
            menu=build_menu()
        )
        update_thread = threading.Thread(target=update_status_periodically, args=(icon,), daemon=True)
        update_thread.start()
        icon.run()
    except Exception as e:
        append_log(UPDATER_LOG, f"[FATAL] Launcher crashed: {e!r}")
    finally:
        append_log(UPDATER_LOG, "Launcher is shutting down...")
        stop_all()
        release_single_instance_lock()