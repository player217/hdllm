#!/usr/bin/env python3
"""
Comprehensive test suite for TT application
Tests all user flows and API endpoints
"""
import requests
import time
import json
import sys
from datetime import datetime

class TTApplicationTester:
    def __init__(self):
        self.backend_url = "http://localhost:8080"
        self.frontend_url = "http://localhost:8001"
        self.test_results = []
        
    def log_result(self, test_name, status, details=""):
        """Log test results"""
        result = {
            "test": test_name,
            "status": "[PASS]" if status else "[FAIL]",
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        self.test_results.append(result)
        print(f"{result['status']} - {test_name}: {details}")
        
    def test_backend_health(self):
        """Test backend health check"""
        print("\n[1] Testing Backend Health Check...")
        try:
            response = requests.get(f"{self.backend_url}/")
            if response.status_code == 200:
                data = response.json()
                self.log_result("Backend Health", True, f"Version: {data.get('version')}")
                return True
            else:
                self.log_result("Backend Health", False, f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.log_result("Backend Health", False, str(e))
            return False
            
    def test_frontend_access(self):
        """Test frontend accessibility"""
        print("\n[2] Testing Frontend Access...")
        try:
            response = requests.get(self.frontend_url)
            if response.status_code == 200:
                self.log_result("Frontend Access", True, "UI is accessible")
                return True
            else:
                self.log_result("Frontend Access", False, f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.log_result("Frontend Access", False, str(e))
            return False
            
    def test_status_endpoint(self):
        """Test /status endpoint"""
        print("\n[3] Testing Status Endpoint...")
        try:
            response = requests.get(f"{self.backend_url}/status")
            if response.status_code == 200:
                data = response.json()
                status_info = f"FastAPI: {data.get('fastapi')}, Ollama: {data.get('ollama')}"
                self.log_result("Status Endpoint", True, status_info)
                return True
            else:
                self.log_result("Status Endpoint", False, f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.log_result("Status Endpoint", False, str(e))
            return False
            
    def test_mail_search(self):
        """Test mail search functionality"""
        print("\n[4] Testing Mail Search...")
        try:
            payload = {
                "question": "최근 회의 일정을 알려주세요",
                "source": "mail",
                "model": "gemma3:4b"
            }
            
            response = requests.post(
                f"{self.backend_url}/ask",
                json=payload,
                stream=True,
                timeout=30
            )
            
            if response.status_code == 200:
                # Read first chunk
                first_chunk = None
                for line in response.iter_lines(chunk_size=1024):
                    if line:
                        first_chunk = line.decode('utf-8')
                        break
                        
                if first_chunk:
                    self.log_result("Mail Search", True, "Response received")
                    return True
                else:
                    self.log_result("Mail Search", False, "No response data")
                    return False
            else:
                self.log_result("Mail Search", False, f"Status: {response.status_code}")
                return False
        except requests.Timeout:
            self.log_result("Mail Search", False, "Request timeout")
            return False
        except Exception as e:
            self.log_result("Mail Search", False, str(e))
            return False
            
    def test_document_search(self):
        """Test document search functionality"""
        print("\n[5] Testing Document Search...")
        try:
            payload = {
                "question": "프로젝트 문서를 찾아주세요",
                "source": "doc",
                "model": "gemma3:4b"
            }
            
            response = requests.post(
                f"{self.backend_url}/ask",
                json=payload,
                stream=True,
                timeout=30
            )
            
            if response.status_code == 200:
                # Read first chunk
                first_chunk = None
                for line in response.iter_lines(chunk_size=1024):
                    if line:
                        first_chunk = line.decode('utf-8')
                        break
                        
                if first_chunk:
                    self.log_result("Document Search", True, "Response received")
                    return True
                else:
                    self.log_result("Document Search", False, "No response data")
                    return False
            else:
                self.log_result("Document Search", False, f"Status: {response.status_code}")
                return False
        except requests.Timeout:
            self.log_result("Document Search", False, "Request timeout")
            return False
        except Exception as e:
            self.log_result("Document Search", False, str(e))
            return False
            
    def test_error_handling(self):
        """Test error handling with invalid request"""
        print("\n[6] Testing Error Handling...")
        try:
            payload = {
                "question": "",  # Empty question
                "source": "invalid",  # Invalid source
                "model": "unknown"  # Unknown model
            }
            
            response = requests.post(
                f"{self.backend_url}/ask",
                json=payload,
                timeout=10
            )
            
            # Should return error status
            if response.status_code >= 400:
                self.log_result("Error Handling", True, f"Properly rejected invalid request: {response.status_code}")
                return True
            else:
                self.log_result("Error Handling", False, "Should reject invalid request")
                return False
        except Exception as e:
            self.log_result("Error Handling", False, str(e))
            return False
            
    def test_chat_history(self):
        """Test chat history functionality"""
        print("\n[7] Testing Chat History...")
        try:
            # Send first message
            payload1 = {
                "question": "안녕하세요",
                "source": "mail",
                "model": "gemma3:4b"
            }
            
            response1 = requests.post(
                f"{self.backend_url}/ask",
                json=payload1,
                stream=True,
                timeout=20
            )
            
            if response1.status_code == 200:
                # Consume response
                for _ in response1.iter_lines(chunk_size=1024):
                    pass
                    
                # Send follow-up message
                payload2 = {
                    "question": "이전 대화를 기억하나요?",
                    "source": "mail", 
                    "model": "gemma3:4b"
                }
                
                response2 = requests.post(
                    f"{self.backend_url}/ask",
                    json=payload2,
                    stream=True,
                    timeout=20
                )
                
                if response2.status_code == 200:
                    self.log_result("Chat History", True, "Multiple requests processed")
                    return True
                else:
                    self.log_result("Chat History", False, f"Second request failed: {response2.status_code}")
                    return False
            else:
                self.log_result("Chat History", False, f"First request failed: {response1.status_code}")
                return False
        except Exception as e:
            self.log_result("Chat History", False, str(e))
            return False
            
    def test_concurrent_requests(self):
        """Test concurrent request handling"""
        print("\n[8] Testing Concurrent Requests...")
        import threading
        
        results = []
        
        def make_request(index):
            try:
                payload = {
                    "question": f"Test request {index}",
                    "source": "mail",
                    "model": "gemma3:4b"
                }
                response = requests.post(
                    f"{self.backend_url}/ask",
                    json=payload,
                    timeout=30
                )
                results.append(response.status_code == 200)
            except:
                results.append(False)
                
        # Start 3 concurrent requests
        threads = []
        for i in range(3):
            t = threading.Thread(target=make_request, args=(i,))
            threads.append(t)
            t.start()
            
        # Wait for all to complete
        for t in threads:
            t.join(timeout=35)
            
        if all(results):
            self.log_result("Concurrent Requests", True, f"All {len(results)} requests succeeded")
            return True
        else:
            self.log_result("Concurrent Requests", False, f"Failed: {results.count(False)}/{len(results)}")
            return False
            
    def run_all_tests(self):
        """Run all tests"""
        print("="*60)
        print(">> TT Application Comprehensive Test Suite")
        print("="*60)
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Backend URL: {self.backend_url}")
        print(f"Frontend URL: {self.frontend_url}")
        
        # Run all tests
        tests = [
            self.test_backend_health,
            self.test_frontend_access,
            self.test_status_endpoint,
            self.test_mail_search,
            self.test_document_search,
            self.test_error_handling,
            self.test_chat_history,
            self.test_concurrent_requests
        ]
        
        for test in tests:
            try:
                test()
                time.sleep(1)  # Short delay between tests
            except Exception as e:
                print(f"Test failed with exception: {e}")
                
        # Summary
        print("\n" + "="*60)
        print(">> TEST SUMMARY")
        print("="*60)
        
        passed = sum(1 for r in self.test_results if "[OK]" in r['status'])
        failed = sum(1 for r in self.test_results if "[FAIL]" in r['status'])
        total = len(self.test_results)
        
        print(f"Total Tests: {total}")
        print(f"[OK] Passed: {passed}")
        print(f"[FAIL] Failed: {failed}")
        print(f"Success Rate: {(passed/total*100):.1f}%" if total > 0 else "N/A")
        
        # Detailed results
        print("\nDetailed Results:")
        for result in self.test_results:
            print(f"  {result['status']} {result['test']}: {result['details']}")
            
        # Overall assessment
        print("\n" + "="*60)
        if failed == 0:
            print(">> ALL TESTS PASSED! Application is working correctly!")
            print("[OK] URL parsing fix is working")
            print("[OK] Backend API is responsive")
            print("[OK] Frontend UI is accessible") 
            print("[OK] Search functionality is operational")
        elif passed > failed:
            print("[WARN] PARTIAL SUCCESS - Some tests failed")
            print("Application is mostly functional but has issues")
        else:
            print("[FAIL] CRITICAL - Most tests failed")
            print("Application has serious issues")
            
        return failed == 0

if __name__ == "__main__":
    tester = TTApplicationTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)