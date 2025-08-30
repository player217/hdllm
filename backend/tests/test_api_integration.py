"""
API 통합 테스트 스크립트
Author: Claude Code
Date: 2025-01-27  
Description: main.py API 엔드포인트와 큐 시스템 통합 테스트
"""

import asyncio
import aiohttp
import json
import time
import logging
import sys
import os
from pathlib import Path

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)

class APIIntegrationTester:
    """API 통합 테스트 클래스"""
    
    def __init__(self, base_url: str = "http://127.0.0.1:8080"):
        self.base_url = base_url
        self.session = None
        self.test_results = []
    
    async def setup(self):
        """테스트 세션 설정"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30)
        )
        
        # 서버 헬스체크
        try:
            async with self.session.get(f"{self.base_url}/health") as response:
                if response.status == 200:
                    logger.info("✅ Server is healthy")
                    return True
                else:
                    logger.error(f"❌ Server health check failed: {response.status}")
                    return False
        except Exception as e:
            logger.error(f"❌ Cannot connect to server: {e}")
            return False
    
    async def teardown(self):
        """테스트 세션 정리"""
        if self.session:
            await self.session.close()
    
    def record_result(self, test_name: str, success: bool, duration: float, details: str = ""):
        """테스트 결과 기록"""
        self.test_results.append({
            "test": test_name,
            "success": success,
            "duration": duration,
            "details": details
        })
    
    async def test_health_endpoint(self):
        """헬스체크 엔드포인트 테스트"""
        logger.info("🔍 Testing /health endpoint...")
        start_time = time.time()
        
        try:
            async with self.session.get(f"{self.base_url}/health") as response:
                assert response.status == 200, f"Expected 200, got {response.status}"
                
                data = await response.json()
                assert "status" in data, "Response should contain 'status'"
                
                logger.info(f"✅ Health endpoint: {data}")
                self.record_result("Health_Endpoint", True, time.time() - start_time, f"Status: {data.get('status')}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Health endpoint test failed: {e}")
            self.record_result("Health_Endpoint", False, time.time() - start_time, str(e))
            return False
    
    async def test_status_endpoint(self):
        """상태 엔드포인트 테스트"""
        logger.info("🔍 Testing /status endpoint...")
        start_time = time.time()
        
        try:
            async with self.session.get(f"{self.base_url}/status") as response:
                assert response.status == 200, f"Expected 200, got {response.status}"
                
                data = await response.json()
                required_fields = ["status", "components"]
                for field in required_fields:
                    assert field in data, f"Response should contain '{field}'"
                
                components = data.get("components", {})
                logger.info(f"✅ Status endpoint: {len(components)} components")
                self.record_result("Status_Endpoint", True, time.time() - start_time, 
                                 f"Components: {list(components.keys())}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Status endpoint test failed: {e}")
            self.record_result("Status_Endpoint", False, time.time() - start_time, str(e))
            return False
    
    async def test_ask_endpoint_streaming(self):
        """스트리밍 질의응답 엔드포인트 테스트"""
        logger.info("🔍 Testing /ask endpoint (streaming)...")
        start_time = time.time()
        
        try:
            payload = {
                "question": "GPU 가속이란 무엇인가요?",
                "source": "mail",
                "model": "gemma3:4b"
            }
            
            headers = {"Content-Type": "application/json"}
            
            async with self.session.post(
                f"{self.base_url}/ask",
                json=payload,
                headers=headers
            ) as response:
                
                assert response.status == 200, f"Expected 200, got {response.status}"
                assert response.content_type == "text/event-stream", "Should be SSE stream"
                
                chunks_received = 0
                total_content = ""
                
                async for line in response.content:
                    line_str = line.decode('utf-8').strip()
                    
                    if line_str.startswith('data: '):
                        chunks_received += 1
                        data_str = line_str[6:]  # Remove 'data: ' prefix
                        
                        try:
                            chunk_data = json.loads(data_str)
                            content = chunk_data.get("content", "")
                            total_content += content
                            
                            if chunk_data.get("done", False):
                                logger.info(f"📄 Stream completed: {chunks_received} chunks")
                                break
                                
                        except json.JSONDecodeError:
                            # 마지막 빈 라인일 수 있음
                            continue
                
                assert chunks_received > 0, "Should receive at least one chunk"
                assert len(total_content) > 0, "Should receive some content"
                
                logger.info(f"✅ Ask endpoint streaming: {chunks_received} chunks, {len(total_content)} chars")
                self.record_result("Ask_Endpoint_Streaming", True, time.time() - start_time,
                                 f"Chunks: {chunks_received}, Content length: {len(total_content)}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Ask endpoint streaming test failed: {e}")
            self.record_result("Ask_Endpoint_Streaming", False, time.time() - start_time, str(e))
            return False
    
    async def test_ask_endpoint_queue_integration(self):
        """큐 시스템과 Ask 엔드포인트 통합 테스트"""
        logger.info("🔍 Testing /ask endpoint queue integration...")
        start_time = time.time()
        
        try:
            # 여러 동시 요청으로 큐 시스템 테스트
            questions = [
                "첫 번째 질문입니다.",
                "두 번째 질문입니다.",  
                "세 번째 질문입니다."
            ]
            
            tasks = []
            for i, question in enumerate(questions):
                payload = {
                    "question": question,
                    "source": "mail",
                    "model": "gemma3:4b"
                }
                
                task = self.session.post(
                    f"{self.base_url}/ask",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                tasks.append(task)
            
            # 모든 요청 동시 실행
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            
            successful_responses = 0
            for i, response in enumerate(responses):
                if isinstance(response, Exception):
                    logger.warning(f"⚠️ Request {i+1} failed: {response}")
                else:
                    if response.status == 200:
                        successful_responses += 1
                        response.close()
            
            assert successful_responses > 0, "At least one request should succeed"
            
            logger.info(f"✅ Queue integration: {successful_responses}/{len(questions)} requests successful")
            self.record_result("Ask_Queue_Integration", True, time.time() - start_time,
                             f"Success rate: {successful_responses}/{len(questions)}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ask queue integration test failed: {e}")
            self.record_result("Ask_Queue_Integration", False, time.time() - start_time, str(e))
            return False
    
    async def test_api_error_handling(self):
        """API 에러 처리 테스트"""
        logger.info("🔍 Testing API error handling...")
        start_time = time.time()
        
        try:
            # 1. 빈 질문 테스트
            payload = {"question": "", "source": "mail"}
            async with self.session.post(f"{self.base_url}/ask", json=payload) as response:
                # 400 또는 422 에러 예상
                assert response.status in [400, 422], f"Empty question should return 4xx, got {response.status}"
            
            # 2. 잘못된 source 테스트
            payload = {"question": "테스트", "source": "invalid_source"}
            async with self.session.post(f"{self.base_url}/ask", json=payload) as response:
                # 400 또는 422 에러 예상
                assert response.status in [400, 422], f"Invalid source should return 4xx, got {response.status}"
            
            # 3. 존재하지 않는 엔드포인트 테스트
            async with self.session.get(f"{self.base_url}/nonexistent") as response:
                assert response.status == 404, f"Nonexistent endpoint should return 404, got {response.status}"
            
            logger.info("✅ API error handling working correctly")
            self.record_result("API_Error_Handling", True, time.time() - start_time)
            return True
            
        except Exception as e:
            logger.error(f"❌ API error handling test failed: {e}")
            self.record_result("API_Error_Handling", False, time.time() - start_time, str(e))
            return False
    
    def print_results(self):
        """테스트 결과 출력"""
        logger.info("\n" + "="*60)
        logger.info("📊 API INTEGRATION TEST RESULTS")
        logger.info("="*60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r["success"])
        total_time = sum(r["duration"] for r in self.test_results)
        
        for result in self.test_results:
            status = "✅ PASS" if result["success"] else "❌ FAIL"
            logger.info(f"{status} {result['test']:<25} {result['duration']:.3f}s")
            if result["details"]:
                logger.info(f"     └─ {result['details']}")
        
        logger.info("-"*60)
        logger.info(f"📈 SUMMARY: {passed_tests}/{total_tests} tests passed ({passed_tests/total_tests*100:.1f}%)")
        logger.info(f"⏱️  TOTAL TIME: {total_time:.3f} seconds")
        logger.info("="*60)
        
        return passed_tests == total_tests
    
    async def run_all_tests(self):
        """모든 테스트 실행"""
        logger.info("🚀 Starting API Integration Tests")
        
        # 환경 설정
        if not await self.setup():
            logger.error("❌ Setup failed, aborting tests")
            return False
        
        try:
            # 테스트 실행
            tests = [
                self.test_health_endpoint,
                self.test_status_endpoint,
                self.test_ask_endpoint_streaming,
                self.test_ask_endpoint_queue_integration,
                self.test_api_error_handling
            ]
            
            for test in tests:
                try:
                    await test()
                except Exception as e:
                    logger.error(f"❌ Test {test.__name__} crashed: {e}")
                    self.record_result(test.__name__, False, 0, f"Crashed: {e}")
                
                # 테스트 간 간격
                await asyncio.sleep(1)
        
        finally:
            # 환경 정리
            await self.teardown()
        
        # 결과 출력
        return self.print_results()


async def main():
    """메인 테스트 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description="API Integration Tests")
    parser.add_argument("--url", default="http://127.0.0.1:8080", 
                       help="Base URL of the API server")
    args = parser.parse_args()
    
    tester = APIIntegrationTester(base_url=args.url)
    success = await tester.run_all_tests()
    
    if success:
        logger.info("🎉 All API tests passed!")
        return 0
    else:
        logger.error("💥 Some API tests failed!")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)