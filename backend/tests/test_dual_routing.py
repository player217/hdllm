"""
Dual Qdrant Routing Test Script
Author: Claude Code
Date: 2025-01-29
Description: Comprehensive test script for dual Qdrant routing functionality
"""

import asyncio
import json
import time
import requests
from typing import Dict, Any, Optional
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Test configuration
BASE_URL = "http://127.0.0.1:8080"
TEST_QUESTION = "HD현대미포 선각기술부의 주요 업무는 무엇인가요?"

class DualRoutingTester:
    """Test suite for dual Qdrant routing functionality"""
    
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.results = []
        
    def print_header(self, title: str):
        """Print formatted test header"""
        print("\n" + "="*60)
        print(f"[TEST] {title}")
        print("="*60)
    
    def print_result(self, test_name: str, passed: bool, details: str = ""):
        """Print test result"""
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status} | {test_name}")
        if details:
            print(f"     └─ {details}")
        self.results.append({"test": test_name, "passed": passed, "details": details})
    
    def test_health_check(self) -> bool:
        """Test basic health check"""
        self.print_header("Health Check Test")
        
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            passed = response.status_code == 200
            self.print_result(
                "Health Check", 
                passed,
                f"Status: {response.status_code}"
            )
            return passed
        except Exception as e:
            self.print_result("Health Check", False, str(e))
            return False
    
    def test_status_endpoint(self) -> Dict[str, Any]:
        """Test /status endpoint for dual routing information"""
        self.print_header("Status Endpoint Test")
        
        try:
            response = requests.get(f"{self.base_url}/status", timeout=10)
            
            if response.status_code == 200:
                status_data = response.json()
                
                # Check for dual routing information
                has_qdrant = "qdrant" in status_data
                self.print_result(
                    "Status contains qdrant info",
                    has_qdrant,
                    f"Keys: {list(status_data.keys())}"
                )
                
                if has_qdrant:
                    qdrant_status = status_data["qdrant"]
                    
                    # Check personal Qdrant
                    has_personal = "personal" in qdrant_status
                    self.print_result(
                        "Personal Qdrant status",
                        has_personal,
                        f"Status: {qdrant_status.get('personal', {}).get('status', 'missing')}"
                    )
                    
                    # Check department Qdrant
                    has_dept = "dept" in qdrant_status
                    self.print_result(
                        "Department Qdrant status",
                        has_dept,
                        f"Status: {qdrant_status.get('dept', {}).get('status', 'missing')}"
                    )
                    
                    # Check routing enabled
                    routing_enabled = status_data.get("routing_enabled", False)
                    self.print_result(
                        "Routing enabled",
                        routing_enabled,
                        f"Value: {routing_enabled}"
                    )
                    
                return status_data
            else:
                self.print_result("Status endpoint", False, f"Status: {response.status_code}")
                return {}
                
        except Exception as e:
            self.print_result("Status endpoint", False, str(e))
            return {}
    
    def test_scope_via_header(self, scope: str) -> bool:
        """Test routing via X-Qdrant-Scope header"""
        self.print_header(f"Header Routing Test: {scope}")
        
        headers = {
            "Content-Type": "application/json",
            "X-Qdrant-Scope": scope
        }
        
        payload = {
            "question": TEST_QUESTION,
            "source": "mail"
        }
        
        try:
            # Send request with scope header
            response = requests.post(
                f"{self.base_url}/ask",
                headers=headers,
                json=payload,
                stream=True,
                timeout=30
            )
            
            if response.status_code == 200:
                # Read streaming response
                content = ""
                references = []
                
                for line in response.iter_lines():
                    if line:
                        line_str = line.decode('utf-8')
                        if line_str.startswith("data: "):
                            try:
                                data = json.loads(line_str[6:])
                                if "content" in data:
                                    content += data["content"]
                                if "references" in data:
                                    references = data["references"]
                            except json.JSONDecodeError:
                                pass
                
                self.print_result(
                    f"Header routing ({scope})",
                    True,
                    f"Response length: {len(content)} chars, References: {len(references)}"
                )
                return True
            else:
                self.print_result(
                    f"Header routing ({scope})",
                    False,
                    f"Status: {response.status_code}"
                )
                return False
                
        except Exception as e:
            self.print_result(f"Header routing ({scope})", False, str(e))
            return False
    
    def test_scope_via_query(self, scope: str) -> bool:
        """Test routing via query parameter"""
        self.print_header(f"Query Parameter Routing Test: {scope}")
        
        headers = {"Content-Type": "application/json"}
        
        payload = {
            "question": TEST_QUESTION,
            "source": "mail"
        }
        
        try:
            # Send request with scope in query parameter
            response = requests.post(
                f"{self.base_url}/ask?db_scope={scope}",
                headers=headers,
                json=payload,
                stream=True,
                timeout=30
            )
            
            if response.status_code == 200:
                # Read streaming response
                content = ""
                
                for line in response.iter_lines():
                    if line:
                        line_str = line.decode('utf-8')
                        if line_str.startswith("data: "):
                            try:
                                data = json.loads(line_str[6:])
                                if "content" in data:
                                    content += data["content"]
                            except json.JSONDecodeError:
                                pass
                
                self.print_result(
                    f"Query routing ({scope})",
                    True,
                    f"Response length: {len(content)} chars"
                )
                return True
            else:
                self.print_result(
                    f"Query routing ({scope})",
                    False,
                    f"Status: {response.status_code}"
                )
                return False
                
        except Exception as e:
            self.print_result(f"Query routing ({scope})", False, str(e))
            return False
    
    def test_default_routing(self) -> bool:
        """Test default routing without explicit scope"""
        self.print_header("Default Routing Test")
        
        headers = {"Content-Type": "application/json"}
        
        payload = {
            "question": TEST_QUESTION,
            "source": "mail"
        }
        
        try:
            # Send request without scope
            response = requests.post(
                f"{self.base_url}/ask",
                headers=headers,
                json=payload,
                stream=True,
                timeout=30
            )
            
            if response.status_code == 200:
                self.print_result(
                    "Default routing",
                    True,
                    "Using DEFAULT_DB_SCOPE from environment"
                )
                return True
            else:
                self.print_result(
                    "Default routing",
                    False,
                    f"Status: {response.status_code}"
                )
                return False
                
        except Exception as e:
            self.print_result("Default routing", False, str(e))
            return False
    
    def test_invalid_scope(self) -> bool:
        """Test handling of invalid scope"""
        self.print_header("Invalid Scope Test")
        
        headers = {
            "Content-Type": "application/json",
            "X-Qdrant-Scope": "invalid_scope"
        }
        
        payload = {
            "question": TEST_QUESTION,
            "source": "mail"
        }
        
        try:
            # Send request with invalid scope
            response = requests.post(
                f"{self.base_url}/ask",
                headers=headers,
                json=payload,
                stream=True,
                timeout=30
            )
            
            # Should fallback to default
            if response.status_code == 200:
                self.print_result(
                    "Invalid scope handling",
                    True,
                    "Fallback to default scope"
                )
                return True
            else:
                self.print_result(
                    "Invalid scope handling",
                    False,
                    f"Status: {response.status_code}"
                )
                return False
                
        except Exception as e:
            self.print_result("Invalid scope handling", False, str(e))
            return False
    
    def test_concurrent_requests(self) -> bool:
        """Test concurrent requests with different scopes"""
        self.print_header("Concurrent Requests Test")
        
        async def send_request(scope: str) -> Dict[str, Any]:
            """Send async request with scope"""
            headers = {
                "Content-Type": "application/json",
                "X-Qdrant-Scope": scope
            }
            
            payload = {
                "question": TEST_QUESTION,
                "source": "mail"
            }
            
            try:
                response = requests.post(
                    f"{self.base_url}/ask",
                    headers=headers,
                    json=payload,
                    stream=True,
                    timeout=30
                )
                return {"scope": scope, "status": response.status_code}
            except Exception as e:
                return {"scope": scope, "error": str(e)}
        
        async def run_concurrent():
            """Run concurrent requests"""
            tasks = [
                send_request("personal"),
                send_request("dept"),
                send_request("personal"),
                send_request("dept")
            ]
            
            # Use asyncio.to_thread for synchronous requests
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                futures = [
                    executor.submit(requests.post,
                        f"{self.base_url}/ask",
                        headers={"Content-Type": "application/json", "X-Qdrant-Scope": scope},
                        json={"question": TEST_QUESTION, "source": "mail"},
                        stream=True,
                        timeout=30
                    )
                    for scope in ["personal", "dept", "personal", "dept"]
                ]
                
                results = []
                for i, future in enumerate(concurrent.futures.as_completed(futures)):
                    try:
                        response = future.result()
                        results.append({
                            "scope": ["personal", "dept", "personal", "dept"][i],
                            "status": response.status_code
                        })
                    except Exception as e:
                        results.append({
                            "scope": ["personal", "dept", "personal", "dept"][i],
                            "error": str(e)
                        })
                
                return results
        
        try:
            # Run concurrent test
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            results = loop.run_until_complete(run_concurrent())
            
            success = all(r.get("status") == 200 for r in results if "status" in r)
            self.print_result(
                "Concurrent requests",
                success,
                f"Processed {len(results)} requests"
            )
            
            for r in results:
                if "error" in r:
                    print(f"     └─ {r['scope']}: ERROR - {r['error']}")
                else:
                    print(f"     └─ {r['scope']}: Status {r.get('status')}")
            
            return success
            
        except Exception as e:
            self.print_result("Concurrent requests", False, str(e))
            return False
    
    def run_all_tests(self):
        """Run all tests"""
        print("\n" + "="*60)
        print("DUAL QDRANT ROUTING TEST SUITE")
        print("="*60)
        
        # Run tests
        self.test_health_check()
        status_data = self.test_status_endpoint()
        
        # Test routing mechanisms
        self.test_scope_via_header("personal")
        self.test_scope_via_header("dept")
        self.test_scope_via_query("personal")
        self.test_scope_via_query("dept")
        self.test_default_routing()
        self.test_invalid_scope()
        self.test_concurrent_requests()
        
        # Summary
        self.print_header("Test Summary")
        passed = sum(1 for r in self.results if r["passed"])
        total = len(self.results)
        
        print(f"\n[RESULTS] {passed}/{total} tests passed")
        
        if passed == total:
            print("[SUCCESS] All tests passed!")
        else:
            print(f"[WARNING] {total - passed} test(s) failed")
            print("\nFailed tests:")
            for r in self.results:
                if not r["passed"]:
                    print(f"  - {r['test']}: {r['details']}")
        
        return passed == total


def main():
    """Main test execution"""
    tester = DualRoutingTester()
    
    # Wait for services to be ready
    print("Waiting for services to be ready...")
    time.sleep(3)
    
    # Run tests
    success = tester.run_all_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()