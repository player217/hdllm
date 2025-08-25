#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
LLM RAG 통합 실행 스크립트

백엔드와 프론트엔드를 동시에 실행하는 스크립트입니다.
"""

import subprocess
import sys
import os
import argparse
import signal
import time
from pathlib import Path

# UTF-8 인코딩 설정 (Windows cp949 오류 방지)
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

# 프로세스 목록 (전역 변수로 관리)
processes = []

def cleanup(signum=None, frame=None):
    """종료 시 모든 프로세스 정리"""
    print("\n서버를 종료합니다...")
    for process in processes:
        try:
            process.terminate()
            process.wait(timeout=5)
        except:
            try:
                process.kill()
            except:
                pass
    sys.exit(0)

# 시그널 핸들러 등록
signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)

def main():
    parser = argparse.ArgumentParser(description='LLM RAG 시스템 실행 스크립트')
    parser.add_argument('--qdrant_path', type=str, help='Qdrant 데이터 경로')
    parser.add_argument('--service_type', type=str, choices=['mail', 'doc'], default='mail', help='서비스 타입')
    args = parser.parse_args()

    # 프로젝트 루트 경로
    project_root = Path(__file__).parent
    backend_dir = project_root / "backend"
    frontend_dir = project_root / "frontend"

    # 환경 변수 설정
    env = os.environ.copy()
    
    # config.json에서 엔드포인트 설정 읽기
    config_file = project_root / "config.json"
    if config_file.exists():
        try:
            import json
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            endpoints = config.get('endpoints', {})
            
            if args.service_type == 'mail':
                # 메일 모드: config.json에서 메일 엔드포인트 사용
                mail_ep = endpoints.get('mail', {})
                env['RAG_MAIL_QDRANT_HOST'] = mail_ep.get('qdrant_host', '127.0.0.1')
                env['RAG_MAIL_QDRANT_PORT'] = mail_ep.get('qdrant_port', '6333')
                
                # Ollama URL 설정
                ollama_host = mail_ep.get('ollama_host', '127.0.0.1')
                ollama_port = mail_ep.get('ollama_port', '11434')
                env['RAG_OLLAMA_URL'] = f'http://{ollama_host}:{ollama_port}/api/chat'
                
                # 문서는 기본값 또는 설정값
                doc_ep = endpoints.get('doc', {})
                env['RAG_DOC_QDRANT_HOST'] = doc_ep.get('qdrant_host', '10.150.104.21')
                env['RAG_DOC_QDRANT_PORT'] = doc_ep.get('qdrant_port', '6333')
            else:  # doc
                # 문서 모드: config.json에서 문서 엔드포인트 사용
                doc_ep = endpoints.get('doc', {})
                env['RAG_DOC_QDRANT_HOST'] = doc_ep.get('qdrant_host', '10.150.104.21')
                env['RAG_DOC_QDRANT_PORT'] = doc_ep.get('qdrant_port', '6333')
                
                # Ollama URL 설정
                ollama_host = doc_ep.get('ollama_host', '127.0.0.1')
                ollama_port = doc_ep.get('ollama_port', '11434')
                env['RAG_OLLAMA_URL'] = f'http://{ollama_host}:{ollama_port}/api/chat'
                
                # 메일은 기본값
                mail_ep = endpoints.get('mail', {})
                env['RAG_MAIL_QDRANT_HOST'] = mail_ep.get('qdrant_host', '127.0.0.1')
                env['RAG_MAIL_QDRANT_PORT'] = mail_ep.get('qdrant_port', '6333')
        except Exception as e:
            print(f"config.json 읽기 실패, 기본값 사용: {e}")
            # 기본값 사용
            if args.service_type == 'mail':
                env['RAG_MAIL_QDRANT_HOST'] = '127.0.0.1'
                env['RAG_MAIL_QDRANT_PORT'] = '6333'
                env['RAG_DOC_QDRANT_HOST'] = '10.150.104.21'
                env['RAG_DOC_QDRANT_PORT'] = '6333'
            else:
                env['RAG_MAIL_QDRANT_HOST'] = '127.0.0.1'
                env['RAG_MAIL_QDRANT_PORT'] = '6333'
                env['RAG_DOC_QDRANT_HOST'] = '10.150.104.21'
                env['RAG_DOC_QDRANT_PORT'] = '6333'
            env['RAG_OLLAMA_URL'] = 'http://127.0.0.1:11434/api/chat'
    else:
        # config.json이 없으면 기본값 사용
        if args.service_type == 'mail':
            env['RAG_MAIL_QDRANT_HOST'] = '127.0.0.1'
            env['RAG_MAIL_QDRANT_PORT'] = '6333'
            env['RAG_DOC_QDRANT_HOST'] = '10.150.104.21'
            env['RAG_DOC_QDRANT_PORT'] = '6333'
        else:
            env['RAG_MAIL_QDRANT_HOST'] = '127.0.0.1'
            env['RAG_MAIL_QDRANT_PORT'] = '6333'
            env['RAG_DOC_QDRANT_HOST'] = '10.150.104.21'
            env['RAG_DOC_QDRANT_PORT'] = '6333'
        env['RAG_OLLAMA_URL'] = 'http://127.0.0.1:11434/api/chat'

    print("=" * 60)
    print(f"LLM RAG 시스템 실행 - {args.service_type.upper()} 모드")
    print("=" * 60)
    print(f"\n설정된 엔드포인트:")
    print(f"  메일 Qdrant: {env['RAG_MAIL_QDRANT_HOST']}:{env['RAG_MAIL_QDRANT_PORT']}")
    print(f"  문서 Qdrant: {env['RAG_DOC_QDRANT_HOST']}:{env['RAG_DOC_QDRANT_PORT']}")
    print(f"  Ollama: {env['RAG_OLLAMA_URL']}")
    print()
    
    # 가상환경 확인
    venv_python = project_root / "venv" / "Scripts" / "python.exe"
    if not venv_python.exists():
        print("[오류] 가상환경을 찾을 수 없습니다. INSTALL.bat을 먼저 실행하세요.")
        return
    
    # 백엔드 서버 실행
    print("\n1. 백엔드 서버를 시작합니다...")
    
    # 가상환경의 uvicorn 강제 사용
    uvicorn_exe = project_root / "venv" / "Scripts" / "uvicorn.exe"
    
    # 가상환경 uvicorn이 없으면 직접 main.py 실행
    if uvicorn_exe.exists():
        print(f"Using venv uvicorn: {uvicorn_exe}")
        backend_cmd = [
            str(uvicorn_exe),
            "main:app", 
            "--host", "0.0.0.0", 
            "--port", "8080",
            "--reload"
        ]
    else:
        # main.py를 직접 실행
        print(f"Using direct main.py execution with venv Python")
        backend_cmd = [
            str(venv_python), 
            str(backend_dir / "main.py")
        ]
    
    try:
        # 백엔드 프로세스 시작 (출력 표시)
        backend_process = subprocess.Popen(
            backend_cmd,
            cwd=backend_dir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        processes.append(backend_process)
        
        # 백엔드 시작 확인 (최대 10초 대기)
        import requests
        backend_started = False
        for i in range(10):
            time.sleep(1)
            try:
                response = requests.get("http://localhost:8080/health", timeout=1)
                if response.status_code == 200:
                    backend_started = True
                    break
            except:
                pass
            
            # 프로세스가 종료되었는지 확인
            if backend_process.poll() is not None:
                print(f"[ERROR] 백엔드 프로세스가 예기치 않게 종료되었습니다.")
                # 에러 출력 읽기
                output = backend_process.stdout.read()
                if output:
                    print(f"백엔드 오류 메시지:\n{output}")
                cleanup()
                return
        
        if backend_started:
            print("[OK] 백엔드 서버가 http://localhost:8080 에서 실행 중입니다.")
        else:
            print("[WARN] 백엔드 서버가 시작되었지만 응답하지 않습니다.")
            
    except Exception as e:
        print(f"[ERROR] 백엔드 서버 실행 실패: {e}")
        import traceback
        traceback.print_exc()
        cleanup()
        return

    # 백엔드가 시작될 시간을 줌
    time.sleep(3)

    # 프론트엔드 서버 실행
    print("\n2. 프론트엔드 서버를 시작합니다...")
    frontend_cmd = [
        str(venv_python), "-m", "http.server", "8001"
    ]
    
    try:
        frontend_process = subprocess.Popen(
            frontend_cmd,
            cwd=frontend_dir
        )
        processes.append(frontend_process)
        print("[OK] 프론트엔드 서버가 http://localhost:8001 에서 실행 중입니다.")
    except Exception as e:
        print(f"[ERROR] 프론트엔드 서버 실행 실패: {e}")
        cleanup()
        return

    print("\n" + "=" * 60)
    print("모든 서버가 실행 중입니다!")
    print("웹 브라우저에서 http://localhost:8001 을 열어주세요.")
    print("종료하려면 Ctrl+C를 누르세요.")
    print("=" * 60 + "\n")

    # 프로세스가 종료될 때까지 대기
    try:
        while True:
            # 프로세스가 여전히 실행 중인지 확인
            for process in processes:
                if process.poll() is not None:
                    print(f"\n프로세스가 예기치 않게 종료되었습니다.")
                    cleanup()
                    return
            time.sleep(1)
    except KeyboardInterrupt:
        cleanup()

if __name__ == "__main__":
    main()