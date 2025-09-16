#!/usr/bin/env python3
"""
프론트엔드 E2E 테스트 스크립트
질문-답변 기능이 정상적으로 작동하는지 확인
"""

import requests
import json
import time
from datetime import datetime

class FrontendE2ETest:
    def __init__(self):
        self.frontend_url = "http://localhost:8001"
        self.backend_url = "http://localhost:8080"
        self.test_results = []
        
    def log(self, level, message):
        """테스트 로그 출력"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        symbol = {"PASS": "[PASS]", "FAIL": "[FAIL]", "INFO": "[INFO]", "WARN": "[WARN]"}.get(level, "")
        print(f"[{timestamp}] {symbol} {message}")
        self.test_results.append({"time": timestamp, "level": level, "message": message})
    
    def test_frontend_loading(self):
        """프론트엔드 로딩 테스트"""
        self.log("INFO", "TEST 1: 프론트엔드 로딩 확인")
        try:
            response = requests.get(self.frontend_url, timeout=5)
            if response.status_code == 200:
                # HTML에서 중요 요소 확인
                html = response.text
                checks = {
                    "sendMessage 함수": "sendMessage" in html,
                    "adjustTextareaHeight 함수": "adjustTextareaHeight" in html,
                    "window.sendMessage 노출": "window.sendMessage" in html,
                    "IIFE 래핑": "(function()" in html,
                    "채팅 입력창": "user-input" in html,
                    "전송 버튼": "send-btn" in html
                }
                
                all_passed = True
                for check, result in checks.items():
                    if result:
                        self.log("PASS", f"  {check}: 존재함")
                    else:
                        self.log("FAIL", f"  {check}: 없음")
                        all_passed = False
                
                return all_passed
            else:
                self.log("FAIL", f"  프론트엔드 응답 실패: HTTP {response.status_code}")
                return False
        except Exception as e:
            self.log("FAIL", f"  프론트엔드 연결 실패: {str(e)}")
            return False
    
    def test_backend_status(self):
        """백엔드 상태 확인"""
        self.log("INFO", "TEST 2: 백엔드 상태 확인")
        try:
            response = requests.get(f"{self.backend_url}/status", timeout=5)
            if response.status_code == 200:
                status = response.json()
                self.log("PASS", f"  백엔드 상태: {status}")
                
                # 각 서비스 상태 확인
                services = {
                    "FastAPI": status.get("fastapi", False),
                    "Ollama": status.get("ollama", False),
                    "Qdrant Mail": status.get("qdrant_mail", False),
                    "Qdrant Doc": status.get("qdrant_doc", False)
                }
                
                for service, is_active in services.items():
                    if is_active:
                        self.log("PASS", f"  {service}: 활성")
                    else:
                        self.log("WARN", f"  {service}: 비활성")
                
                return True
            else:
                self.log("FAIL", f"  백엔드 응답 실패: HTTP {response.status_code}")
                return False
        except Exception as e:
            self.log("FAIL", f"  백엔드 연결 실패: {str(e)}")
            return False
    
    def test_message_sending(self):
        """메시지 전송 기능 테스트"""
        self.log("INFO", "TEST 3: 메시지 전송 기능 테스트")
        
        test_questions = [
            {"question": "Hello, is the system working?", "source": "mail"},
            {"question": "시스템 상태를 알려주세요", "source": "mail"},
            {"question": "What emails do you have?", "source": "mail"}
        ]
        
        all_passed = True
        for i, test_case in enumerate(test_questions, 1):
            self.log("INFO", f"  테스트 {i}: '{test_case['question']}'")
            
            try:
                # API 요청 준비
                payload = {
                    "question": test_case["question"],
                    "model": "gemma3:4b",
                    "source": test_case["source"]
                }
                
                # 요청 전송
                response = requests.post(
                    f"{self.backend_url}/ask",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=30,
                    stream=True
                )
                
                if response.status_code == 200:
                    # 스트리밍 응답 처리
                    answer_chunks = []
                    references = None
                    
                    for line in response.iter_lines():
                        if line:
                            try:
                                data = json.loads(line)
                                if "answer_chunk" in data:
                                    answer_chunks.append(data["answer_chunk"])
                                elif "references" in data:
                                    references = data["references"]
                            except json.JSONDecodeError:
                                continue
                    
                    answer = "".join(answer_chunks)
                    
                    if answer:
                        self.log("PASS", f"    답변 수신: {answer[:100]}...")
                    else:
                        self.log("WARN", "    답변이 비어있음")
                        all_passed = False
                    
                    if references:
                        self.log("PASS", f"    참조 문서: {len(references)}개")
                    else:
                        self.log("INFO", "    참조 문서 없음")
                        
                else:
                    self.log("FAIL", f"    응답 실패: HTTP {response.status_code}")
                    try:
                        error = response.json()
                        self.log("FAIL", f"    에러: {error}")
                    except:
                        self.log("FAIL", f"    에러 내용: {response.text}")
                    all_passed = False
                    
            except requests.Timeout:
                self.log("FAIL", "    요청 시간 초과")
                all_passed = False
            except Exception as e:
                self.log("FAIL", f"    테스트 실패: {str(e)}")
                all_passed = False
            
            time.sleep(1)  # 서버 부하 방지
        
        return all_passed
    
    def test_javascript_functions(self):
        """JavaScript 함수 정의 확인"""
        self.log("INFO", "TEST 4: JavaScript 함수 정의 확인")
        try:
            response = requests.get(self.frontend_url, timeout=5)
            html = response.text
            
            # IIFE 구조 확인
            if "(function()" in html and "})();" in html:
                self.log("PASS", "  IIFE 구조 정상")
            else:
                self.log("FAIL", "  IIFE 구조 문제")
                return False
            
            # 전역 함수 노출 확인
            global_functions = [
                "window.sendMessage = sendMessage",
                "window.adjustTextareaHeight = adjustTextareaHeight",
                "window.toggleSidebar = toggleSidebar",
                "window.toggleDarkMode = toggleDarkMode",
                "window.chatManager = chatManager"
            ]
            
            all_exposed = True
            for func in global_functions:
                if func in html:
                    self.log("PASS", f"  {func.split(' = ')[0]}: 노출됨")
                else:
                    self.log("FAIL", f"  {func.split(' = ')[0]}: 노출 안됨")
                    all_exposed = False
            
            # 초기화 가드 확인
            if "window.__TT_BOOTED__" in html:
                self.log("PASS", "  초기화 가드 존재")
                
                # return이 IIFE 내부에 있는지 확인
                if html.find("window.__TT_BOOTED__") < html.find("return") < html.find("})();"):
                    self.log("PASS", "  return이 IIFE 내부에 위치 (안전)")
                else:
                    self.log("WARN", "  return 위치 확인 필요")
            else:
                self.log("WARN", "  초기화 가드 없음")
            
            return all_exposed
        except Exception as e:
            self.log("FAIL", f"  테스트 실패: {str(e)}")
            return False
    
    def run_all_tests(self):
        """모든 테스트 실행"""
        print("\n" + "="*60)
        print(" LMM_UI_APP Frontend E2E Test")
        print("="*60)
        
        test_results = {
            "프론트엔드 로딩": self.test_frontend_loading(),
            "백엔드 상태": self.test_backend_status(),
            "JavaScript 함수": self.test_javascript_functions(),
            "메시지 전송": self.test_message_sending()
        }
        
        print("\n" + "="*60)
        print(" Test Results Summary")
        print("="*60)
        
        passed = 0
        failed = 0
        
        for test_name, result in test_results.items():
            if result:
                print(f"  [PASS] {test_name}: PASS")
                passed += 1
            else:
                print(f"  [FAIL] {test_name}: FAIL")
                failed += 1
        
        print(f"\n  총 {passed + failed}개 중 {passed}개 성공, {failed}개 실패")
        
        if failed == 0:
            print("\n  [SUCCESS] All tests passed! System is working correctly.")
        else:
            print("\n  [WARNING] Some tests failed. Check the detailed logs.")
        
        print("="*60)
        
        return failed == 0

if __name__ == "__main__":
    tester = FrontendE2ETest()
    success = tester.run_all_tests()
    exit(0 if success else 1)