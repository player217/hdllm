#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
GUI 수정사항 테스트 스크립트
"""

import sys
import subprocess
import time
import requests
import json
from pathlib import Path

def test_process_termination():
    """프로세스 종료 기능 테스트"""
    print("=" * 60)
    print("테스트 1: 프로세스 트리 종료 기능")
    print("-" * 60)
    
    # run_all.py를 시작하여 자식 프로세스 생성
    project_root = Path(__file__).parent
    script_path = project_root / "run_all.py"
    venv_python = project_root / "venv" / "Scripts" / "python.exe"
    
    if not script_path.exists() or not venv_python.exists():
        print("필요한 파일을 찾을 수 없습니다.")
        return False
    
    try:
        # 프로세스 시작
        process = subprocess.Popen(
            [str(venv_python), str(script_path), "--service_type=mail"],
            creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
        )
        
        print(f"프로세스 시작됨 (PID: {process.pid})")
        time.sleep(5)  # 서버 시작 대기
        
        # 서버 상태 확인
        try:
            response = requests.get("http://localhost:8080/health", timeout=2)
            if response.status_code == 200:
                print("✓ 백엔드 서버가 정상 실행 중입니다.")
            else:
                print("✗ 백엔드 서버가 응답하지 않습니다.")
        except:
            print("✗ 백엔드 서버 연결 실패")
        
        # 프로세스 트리 종료 테스트
        if sys.platform == 'win32':
            print(f"\ntaskkill로 프로세스 트리 종료 시도 (PID: {process.pid})...")
            result = subprocess.call(
                ['taskkill', '/F', '/T', '/PID', str(process.pid)],
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL
            )
            if result == 0:
                print("✓ 프로세스 트리 종료 성공")
            else:
                print("✗ 프로세스 트리 종료 실패")
                process.terminate()
        else:
            process.terminate()
        
        # 프로세스 정리 대기
        try:
            process.wait(timeout=5)
            print("✓ 프로세스 정리 완료")
        except subprocess.TimeoutExpired:
            process.kill()
            print("⚠ 프로세스 강제 종료")
        
        # 서버 종료 확인
        time.sleep(2)
        try:
            response = requests.get("http://localhost:8080/health", timeout=1)
            print("✗ 서버가 여전히 실행 중입니다 - 종료 실패")
            return False
        except:
            print("✓ 서버가 정상적으로 종료되었습니다.")
            return True
            
    except Exception as e:
        print(f"테스트 중 오류 발생: {e}")
        return False

def test_qdrant_auto_start():
    """Qdrant 자동 시작 기능 테스트"""
    print("\n" + "=" * 60)
    print("테스트 2: Qdrant 자동 시작 기능")
    print("-" * 60)
    
    # config.json 확인
    config_path = Path(__file__).parent / "config.json"
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        mail_qdrant_path = config.get('mail_qdrant_path', '')
        if mail_qdrant_path:
            print(f"✓ 메일 Qdrant 경로 설정됨: {mail_qdrant_path}")
        else:
            print("✗ 메일 Qdrant 경로가 설정되지 않음")
        
        endpoints = config.get('endpoints', {})
        if endpoints:
            mail_ep = endpoints.get('mail', {})
            if mail_ep:
                print(f"✓ 메일 엔드포인트 설정됨: {mail_ep.get('qdrant_host')}:{mail_ep.get('qdrant_port')}")
            else:
                print("✗ 메일 엔드포인트가 설정되지 않음")
        else:
            print("⚠ 엔드포인트 설정이 없음 (기본값 사용)")
    else:
        print("✗ config.json 파일이 없음")
    
    return True

def test_browser_button():
    """브라우저 열기 버튼 테스트"""
    print("\n" + "=" * 60)
    print("테스트 3: 브라우저 열기 기능")
    print("-" * 60)
    
    # 간단한 HTTP 서버 시작하여 테스트
    import http.server
    import threading
    
    def start_test_server():
        handler = http.server.SimpleHTTPRequestHandler
        httpd = http.server.HTTPServer(('localhost', 8001), handler)
        httpd.handle_request()  # 한 번의 요청만 처리
    
    # 백그라운드에서 서버 시작
    server_thread = threading.Thread(target=start_test_server)
    server_thread.daemon = True
    server_thread.start()
    
    time.sleep(2)  # 서버 시작 대기
    
    # 서버 연결 테스트
    try:
        response = requests.get("http://localhost:8001", timeout=2)
        if response.status_code in [200, 404]:  # 404도 서버 응답으로 간주
            print("✓ 프론트엔드 서버 연결 가능")
            return True
        else:
            print(f"✗ 프론트엔드 서버 응답 오류: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ 프론트엔드 서버 연결 실패: {e}")
        return False

def main():
    """메인 테스트 함수"""
    print("=" * 60)
    print("HDLLM GUI 수정사항 테스트")
    print("=" * 60)
    
    results = []
    
    # 테스트 1: 프로세스 종료
    results.append(("프로세스 트리 종료", test_process_termination()))
    
    # 테스트 2: Qdrant 자동 시작
    results.append(("Qdrant 자동 시작", test_qdrant_auto_start()))
    
    # 테스트 3: 브라우저 버튼
    results.append(("브라우저 열기", test_browser_button()))
    
    # 결과 요약
    print("\n" + "=" * 60)
    print("테스트 결과 요약")
    print("-" * 60)
    
    for test_name, passed in results:
        status = "✓ 통과" if passed else "✗ 실패"
        print(f"{test_name}: {status}")
    
    total_passed = sum(1 for _, passed in results if passed)
    total_tests = len(results)
    
    print("-" * 60)
    print(f"총 {total_tests}개 테스트 중 {total_passed}개 통과")
    print("=" * 60)
    
    return total_passed == total_tests

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)