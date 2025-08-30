#!/usr/bin/env python
"""P1-6 Performance Test Script"""
import asyncio
import aiohttp
import time
import statistics
import json

async def test_request(session, question):
    """Send a single request and measure response time"""
    start = time.time()
    try:
        async with session.post(
            'http://localhost:8080/ask',
            json={'question': question, 'source': 'mail'},
            timeout=aiohttp.ClientTimeout(total=30)
        ) as resp:
            await resp.text()
            return time.time() - start
    except Exception as e:
        print(f"Error: {e}")
        return None

async def load_test():
    """Run performance test with multiple queries"""
    questions = [
        "HD현대미포 선각기술부는 무엇인가요?",
        "품질 관리 절차는 어떻게 되나요?",
        "안전 규정에 대해 알려주세요",
        "프로젝트 일정은 어떻게 관리하나요?",
        "기술 문서는 어디에 있나요?",
        "회의록은 어떻게 작성하나요?",
        "업무 프로세스를 설명해주세요",
        "시스템 구조는 어떻게 되어있나요?"
    ] * 2  # 16 requests total
    
    print("Starting P1-6 Performance Test...")
    print(f"Testing with {len(questions)} requests\n")
    
    async with aiohttp.ClientSession() as session:
        # Warm-up request
        print("Warming up...")
        await test_request(session, "테스트 질문")
        
        # Run tests
        print("Running tests...")
        tasks = [test_request(session, q) for q in questions]
        times = await asyncio.gather(*tasks)
        
        # Filter out None values (errors)
        valid_times = [t for t in times if t is not None]
        
        if valid_times:
            print("\nPerformance Results:")
            print(f"  Successful: {len(valid_times)}/{len(questions)}")
            print(f"  Average: {statistics.mean(valid_times):.2f}s")
            print(f"  Median: {statistics.median(valid_times):.2f}s")
            if len(valid_times) > 1:
                print(f"  P95: {statistics.quantiles(valid_times, n=20)[18] if len(valid_times) >= 20 else max(valid_times):.2f}s")
            print(f"  Min: {min(valid_times):.2f}s")
            print(f"  Max: {max(valid_times):.2f}s")
        else:
            print("All requests failed")

async def check_metrics():
    """Check Prometheus metrics"""
    print("\nChecking metrics...")
    async with aiohttp.ClientSession() as session:
        async with session.get('http://localhost:8080/metrics') as resp:
            metrics = await resp.text()
            
            # Parse relevant metrics
            for line in metrics.split('\n'):
                if 'cache_hits_total{cache_type="embedding"}' in line and 'HELP' not in line and 'TYPE' not in line:
                    print(f"  Cache hits: {line.split()[-1]}")
                elif 'cache_misses_total{cache_type="embedding"}' in line and 'HELP' not in line and 'TYPE' not in line:
                    print(f"  Cache misses: {line.split()[-1]}")

if __name__ == "__main__":
    asyncio.run(load_test())
    asyncio.run(check_metrics())
    print("\nP1-6 Performance test complete!")