#!/usr/bin/env python3
"""
Performance Optimization Test Script
Tests the implemented performance fixes for LMM_UI_APP
"""
import asyncio
import time
import requests
import json
from datetime import datetime

class PerformanceTest:
    def __init__(self):
        self.backend_url = "http://127.0.0.1:8080"
        self.test_question = "HD현대미포에서 진행 중인 주요 프로젝트는 무엇입니까?"
        
    async def test_model_warmup(self):
        """Test if Ollama model warmup is working"""
        print("🔥 Testing Model Warmup System...")
        
        # Get backend info
        try:
            response = requests.get(f"{self.backend_url}/")
            if response.status_code == 200:
                data = response.json()
                performance_info = data.get("performance", {})
                
                print(f"   Backend Version: {data.get('version')}")
                print(f"   Model Warmed Up: {performance_info.get('model_warmed_up')}")
                print(f"   Keep Alive: {performance_info.get('keep_alive')}")
                print(f"   LLM Timeout: {performance_info.get('llm_timeout')}s")
                
                if performance_info.get('model_warmed_up'):
                    print("   ✅ Model warmup system is active!")
                    return True
                else:
                    print("   ⚠️ Model warmup not confirmed")
                    return False
            else:
                print(f"   ❌ Backend not responding: {response.status_code}")
                return False
        except Exception as e:
            print(f"   ❌ Error testing warmup: {e}")
            return False
    
    def test_api_response_time(self, num_tests=3):
        """Test API response time improvement"""
        print(f"\n⚡ Testing API Response Times ({num_tests} tests)...")
        
        times = []
        for i in range(num_tests):
            print(f"   Test {i+1}/{num_tests}...")
            start_time = time.time()
            
            try:
                response = requests.post(
                    f"{self.backend_url}/ask",
                    json={
                        "question": self.test_question,
                        "source": "mail"
                    },
                    timeout=35,  # Slightly longer than new 30s timeout
                    stream=True
                )
                
                if response.status_code == 200:
                    # Read first chunk to measure actual response start
                    first_chunk_time = None
                    for chunk in response.iter_lines(chunk_size=1024):
                        if chunk and first_chunk_time is None:
                            first_chunk_time = time.time()
                            break
                    
                    if first_chunk_time:
                        response_time = first_chunk_time - start_time
                        times.append(response_time)
                        print(f"      Response time: {response_time:.2f}s")
                        
                        if response_time < 10:
                            print(f"      ✅ Fast response! (< 10s)")
                        elif response_time < 20:
                            print(f"      ⚡ Good response! (< 20s)")
                        else:
                            print(f"      ⚠️ Slow response (> 20s)")
                    else:
                        print(f"      ❌ No response content received")
                else:
                    print(f"      ❌ API error: {response.status_code}")
                    
            except requests.Timeout:
                print(f"      ❌ Request timed out (>35s)")
                times.append(35.0)
            except Exception as e:
                print(f"      ❌ Error: {e}")
                times.append(35.0)
        
        if times:
            avg_time = sum(times) / len(times)
            min_time = min(times)
            max_time = max(times)
            
            print(f"\n   📊 Response Time Summary:")
            print(f"      Average: {avg_time:.2f}s")
            print(f"      Fastest: {min_time:.2f}s") 
            print(f"      Slowest: {max_time:.2f}s")
            
            if avg_time < 5:
                print(f"      ✅ EXCELLENT performance! (avg < 5s)")
                return "excellent"
            elif avg_time < 10:
                print(f"      ✅ GOOD performance! (avg < 10s)")
                return "good"
            elif avg_time < 20:
                print(f"      ⚡ ACCEPTABLE performance (avg < 20s)")
                return "acceptable"
            else:
                print(f"      ❌ POOR performance (avg > 20s)")
                return "poor"
        else:
            print(f"      ❌ No valid response times measured")
            return "failed"
    
    def test_status_endpoint(self):
        """Test status endpoint performance"""
        print(f"\n📊 Testing Status Endpoint...")
        
        start_time = time.time()
        try:
            response = requests.get(f"{self.backend_url}/status", timeout=5)
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                print(f"   Response time: {response_time:.3f}s")
                print(f"   FastAPI: {data.get('fastapi')}")
                print(f"   Ollama: {data.get('ollama')}")
                print(f"   Qdrant Mail: {data.get('qdrant_mail')}")
                print(f"   Qdrant Doc: {data.get('qdrant_doc')}")
                
                if response_time < 2:
                    print(f"   ✅ Fast status check!")
                    return True
                else:
                    print(f"   ⚠️ Slow status check")
                    return False
            else:
                print(f"   ❌ Status endpoint error: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"   ❌ Status test failed: {e}")
            return False
    
    def run_all_tests(self):
        """Run all performance tests"""
        print("="*60)
        print("🚀 LMM_UI_APP Performance Optimization Test")
        print("="*60)
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        results = {}
        
        # Test 1: Model Warmup
        results['warmup'] = asyncio.run(self.test_model_warmup())
        
        # Test 2: Status Endpoint  
        results['status'] = self.test_status_endpoint()
        
        # Test 3: API Response Times
        results['api_performance'] = self.test_api_response_time()
        
        # Summary
        print("\n" + "="*60)
        print("📈 PERFORMANCE TEST SUMMARY")
        print("="*60)
        
        print(f"🔥 Model Warmup: {'✅ ACTIVE' if results['warmup'] else '❌ INACTIVE'}")
        print(f"📊 Status Check: {'✅ FAST' if results['status'] else '❌ SLOW'}")
        
        api_perf = results['api_performance']
        if api_perf == 'excellent':
            print(f"⚡ API Performance: ✅ EXCELLENT (< 5s avg)")
        elif api_perf == 'good':
            print(f"⚡ API Performance: ✅ GOOD (< 10s avg)")  
        elif api_perf == 'acceptable':
            print(f"⚡ API Performance: ⚡ ACCEPTABLE (< 20s avg)")
        else:
            print(f"⚡ API Performance: ❌ NEEDS IMPROVEMENT")
            
        # Overall assessment
        if results['warmup'] and results['status'] and api_perf in ['excellent', 'good']:
            print(f"\n🎉 OVERALL: ✅ PERFORMANCE OPTIMIZATIONS SUCCESSFUL!")
            print(f"   - Model warmup prevents cold starts")
            print(f"   - API responses are fast and consistent") 
            print(f"   - Status checks are responsive")
        else:
            print(f"\n⚠️ OVERALL: PERFORMANCE NEEDS ATTENTION")
            if not results['warmup']:
                print(f"   - Check Ollama model warmup system")
            if not results['status']:
                print(f"   - Status endpoint may be slow")
            if api_perf in ['poor', 'failed']:
                print(f"   - API response times need optimization")
                
        return results

if __name__ == "__main__":
    test = PerformanceTest()
    test.run_all_tests()