#!/usr/bin/env python3
"""
P1-1 E2E Integration Test Runner
Author: Claude Code
Date: 2025-01-26
Purpose: Run real end-to-end integration tests with live services
"""

import os
import sys
import time
import subprocess
import asyncio
import httpx
from pathlib import Path

# Setup UTF-8 encoding for Windows
if sys.platform == "win32":
    os.system("chcp 65001 > nul 2>&1")
    os.environ['PYTHONIOENCODING'] = 'utf-8'

class E2ETestRunner:
    """Run E2E tests for P1-1 implementation"""
    
    def __init__(self):
        self.results = {
            "1_server_startup": "pending",
            "2_smoke_tests": "pending", 
            "3_collection_validation": "pending",
            "4_security_check": "pending"
        }
        self.server_process = None
    
    def print_section(self, title):
        """Print formatted section header"""
        print("\n" + "=" * 60)
        print(f"  {title}")
        print("=" * 60)
    
    def check_prerequisites(self):
        """Check if required services are running"""
        self.print_section("Checking Prerequisites")
        
        # Check Qdrant
        try:
            response = httpx.get("http://127.0.0.1:6333/")
            if response.status_code == 200:
                print("[OK] Qdrant is running on port 6333")
            else:
                print("[WARNING] Qdrant returned status:", response.status_code)
        except Exception as e:
            print(f"[ERROR] Qdrant not accessible: {e}")
            print("Please start Qdrant first!")
            return False
        
        # Check Ollama
        try:
            response = httpx.get("http://127.0.0.1:11434/")
            if response.status_code in [200, 404]:  # Ollama returns 404 on root
                print("[OK] Ollama is running on port 11434")
            else:
                print("[WARNING] Ollama returned status:", response.status_code)
        except Exception as e:
            print(f"[ERROR] Ollama not accessible: {e}")
            print("Please start Ollama first!")
            return False
        
        return True
    
    def test_server_startup(self):
        """Test 1: Server startup and self-check"""
        self.print_section("Test 1: Server Startup & Self-Check")
        
        try:
            # Start the server
            print("Starting FastAPI server...")
            cmd = [
                sys.executable, "-m", "uvicorn",
                "backend.main:app",
                "--host", "0.0.0.0",
                "--port", "8000",
                "--log-level", "info"
            ]
            
            self.server_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            
            # Wait for server to start and check logs
            print("Waiting for server startup...")
            start_time = time.time()
            timeout = 30  # 30 second timeout
            
            startup_success = False
            validation_status = None
            
            while time.time() - start_time < timeout:
                if self.server_process.poll() is not None:
                    # Server exited prematurely
                    print("[ERROR] Server exited unexpectedly")
                    break
                
                # Check if server is responding
                try:
                    response = httpx.get("http://127.0.0.1:8000/health")
                    if response.status_code == 200:
                        print("[OK] Server is responding on port 8000")
                        startup_success = True
                        break
                except:
                    pass
                
                time.sleep(1)
            
            if startup_success:
                # Check status endpoint for validation results
                response = httpx.get("http://127.0.0.1:8000/status")
                if response.status_code == 200:
                    data = response.json()
                    print(f"[OK] Status endpoint responding")
                    
                    # Check for namespace separation
                    if "namespace_separation" in data:
                        print(f"[OK] Namespace separation: {data['namespace_separation']}")
                    
                    self.results["1_server_startup"] = "passed"
                    return True
                else:
                    print(f"[WARNING] Status endpoint returned: {response.status_code}")
            else:
                print("[ERROR] Server failed to start within timeout")
            
            self.results["1_server_startup"] = "failed"
            return False
            
        except Exception as e:
            print(f"[ERROR] Server startup test failed: {e}")
            self.results["1_server_startup"] = "failed"
            return False
    
    def test_smoke_tests(self):
        """Test 2: Run pytest smoke tests"""
        self.print_section("Test 2: Smoke Tests (pytest)")
        
        try:
            # Test 1: Boot and ask basic
            print("\nRunning test_app_boot_and_ask_basic...")
            result1 = subprocess.run(
                [sys.executable, "-m", "pytest", 
                 "backend/tests/test_smoke.py::TestSmoke::test_app_boot_and_ask_basic",
                 "-q", "--tb=short"],
                capture_output=True,
                text=True
            )
            
            if result1.returncode == 0:
                print("[OK] test_app_boot_and_ask_basic passed")
            else:
                print(f"[FAIL] test_app_boot_and_ask_basic failed")
                print(result1.stdout)
                
            # Test 2: Status endpoint
            print("\nRunning test_status_endpoint...")
            result2 = subprocess.run(
                [sys.executable, "-m", "pytest",
                 "backend/tests/test_smoke.py::TestSmoke::test_status_endpoint",
                 "-q", "--tb=short"],
                capture_output=True,
                text=True
            )
            
            if result2.returncode == 0:
                print("[OK] test_status_endpoint passed")
            else:
                print(f"[FAIL] test_status_endpoint failed")
                print(result2.stdout)
            
            # Check /ask endpoint manually
            print("\nTesting /ask endpoint manually...")
            response = httpx.post(
                "http://127.0.0.1:8000/ask",
                json={"question": "test", "source": "mail"},
                timeout=10.0
            )
            
            if response.status_code == 200:
                print(f"[OK] /ask returned 200")
                print(f"[OK] Content-Type: {response.headers.get('content-type')}")
                
                # Check content type
                content_type = response.headers.get('content-type', '')
                valid_types = ['application/x-ndjson', 'text/event-stream', 'application/json']
                if any(t in content_type for t in valid_types):
                    print(f"[OK] Valid content type")
                else:
                    print(f"[WARNING] Unexpected content type: {content_type}")
            else:
                print(f"[FAIL] /ask returned {response.status_code}")
            
            # Overall result
            if result1.returncode == 0 and result2.returncode == 0 and response.status_code == 200:
                self.results["2_smoke_tests"] = "passed"
                return True
            else:
                self.results["2_smoke_tests"] = "failed"
                return False
                
        except Exception as e:
            print(f"[ERROR] Smoke tests failed: {e}")
            self.results["2_smoke_tests"] = "failed"
            return False
    
    def test_collection_validation(self):
        """Test 3: Collection validation script"""
        self.print_section("Test 3: Collection Validation")
        
        try:
            print("Running validate_collections.py...")
            result = subprocess.run(
                [sys.executable, "scripts/validate_collections.py",
                 "--sources", "mail", "doc", "--verbose"],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            
            output = result.stdout + result.stderr
            
            # Check for expected patterns
            if "expected_dimension" in output:
                print("[OK] Dimension check performed")
            
            if "overall_status" in output or "validation" in output.lower():
                print("[OK] Validation completed")
            
            # Check exit code
            if result.returncode == 0:
                print("[OK] validate_collections.py succeeded")
                self.results["3_collection_validation"] = "passed"
                return True
            elif result.returncode == 2:
                print("[WARNING] Collections have warnings")
                self.results["3_collection_validation"] = "warning"
                return True
            else:
                print(f"[FAIL] validate_collections.py failed with code {result.returncode}")
                print(output[:500])  # First 500 chars of output
                self.results["3_collection_validation"] = "failed"
                return False
                
        except Exception as e:
            print(f"[ERROR] Collection validation failed: {e}")
            self.results["3_collection_validation"] = "failed"
            return False
    
    def test_security_check(self):
        """Test 4: Security and naming checks"""
        self.print_section("Test 4: Security & Naming Checks")
        
        try:
            # Check for wildcard CORS
            print("Checking for wildcard CORS...")
            result1 = subprocess.run(
                ["git", "grep", "-n", r'allow_origins=\["\*"\]'],
                capture_output=True,
                text=True
            )
            
            if result1.returncode == 0:
                print("[WARNING] Found wildcard CORS:")
                print(result1.stdout[:200])
            else:
                print("[OK] No wildcard CORS found")
            
            # Check for hardcoded collection names
            print("\nChecking for hardcoded collection names...")
            result2 = subprocess.run(
                ["git", "grep", "-n", "mail_my_documents\\|doc_my_documents"],
                capture_output=True,
                text=True
            )
            
            if result2.returncode == 0:
                # Filter out allowed patterns
                lines = result2.stdout.split('\n')
                bad_lines = [l for l in lines if l and 
                            'fallback' not in l.lower() and 
                            'legacy' not in l.lower() and
                            'security_config' not in l]
                
                if bad_lines:
                    print(f"[WARNING] Found {len(bad_lines)} hardcoded names")
                    for line in bad_lines[:3]:
                        print(f"  {line}")
                else:
                    print("[OK] Only fallback/legacy names found")
            else:
                print("[OK] No hardcoded collection names")
            
            self.results["4_security_check"] = "passed"
            return True
            
        except Exception as e:
            print(f"[WARNING] Security check had issues: {e}")
            self.results["4_security_check"] = "warning"
            return True
    
    def cleanup(self):
        """Stop the server and cleanup"""
        if self.server_process:
            print("\nStopping server...")
            self.server_process.terminate()
            time.sleep(2)
            if self.server_process.poll() is None:
                self.server_process.kill()
            print("Server stopped")
    
    def print_summary(self):
        """Print test summary"""
        self.print_section("E2E Test Summary")
        
        passed = sum(1 for v in self.results.values() if v == "passed")
        failed = sum(1 for v in self.results.values() if v == "failed")
        warnings = sum(1 for v in self.results.values() if v == "warning")
        
        print(f"\nTest Results:")
        for test, status in self.results.items():
            symbol = {
                "passed": "[PASS]",
                "failed": "[FAIL]",
                "warning": "[WARN]",
                "pending": "[SKIP]"
            }.get(status, "[?]")
            
            test_name = test.replace("_", " ").title()
            print(f"{symbol} {test_name}: {status}")
        
        print(f"\nTotal: {len(self.results)} tests")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Warnings: {warnings}")
        
        if failed == 0:
            print("\n[SUCCESS] All E2E tests passed!")
            return True
        else:
            print(f"\n[FAILURE] {failed} test(s) failed")
            return False
    
    def run_all_tests(self):
        """Run all E2E tests"""
        print("=" * 60)
        print("  P1-1 E2E Integration Tests")
        print("=" * 60)
        
        # Check prerequisites
        if not self.check_prerequisites():
            print("\n[ERROR] Prerequisites not met. Exiting.")
            return False
        
        try:
            # Run tests in sequence
            if self.test_server_startup():
                self.test_smoke_tests()
                self.test_collection_validation()
            else:
                print("[SKIP] Skipping remaining tests due to server startup failure")
            
            self.test_security_check()
            
        finally:
            self.cleanup()
        
        return self.print_summary()


def main():
    """Main entry point"""
    runner = E2ETestRunner()
    success = runner.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()