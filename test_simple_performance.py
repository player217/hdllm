#!/usr/bin/env python3
"""
Simple performance test to measure API response times
"""
import requests
import time
import json
from datetime import datetime

def test_api_performance():
    backend_url = "http://localhost:8080"
    
    print("\n" + "="*60)
    print(" Simple Performance Test")
    print("="*60)
    
    # Check backend status and warmup
    print("\n1. Checking backend status...")
    try:
        response = requests.get(f"{backend_url}/")
        if response.status_code == 200:
            data = response.json()
            print(f"   Backend Version: {data.get('version')}")
            perf = data.get('performance', {})
            print(f"   Model Warmed Up: {perf.get('model_warmed_up')}")
            print(f"   Keep Alive: {perf.get('keep_alive')}")
            print(f"   LLM Timeout: {perf.get('llm_timeout')}s")
        else:
            print(f"   Backend not responding: {response.status_code}")
            return
    except Exception as e:
        print(f"   Error: {e}")
        return
    
    # Test API response times
    print("\n2. Testing API response times (3 requests)...")
    
    for i in range(3):
        print(f"\n   Request {i+1}:")
        
        start_time = time.time()
        first_chunk_time = None
        
        try:
            # Simple test question
            payload = {
                "question": f"Test question {i+1}: What is 2+2?",
                "source": "mail",
                "model": "gemma3:4b"
            }
            
            print(f"      Sending: {payload['question']}")
            
            response = requests.post(
                f"{backend_url}/ask",
                json=payload,
                stream=True,
                timeout=35
            )
            
            if response.status_code == 200:
                # Measure time to first chunk
                for line in response.iter_lines():
                    if line and first_chunk_time is None:
                        first_chunk_time = time.time()
                        time_to_first_chunk = first_chunk_time - start_time
                        print(f"      First chunk: {time_to_first_chunk:.2f}s")
                        
                        # Check if this is actually fast
                        if time_to_first_chunk < 10:
                            print(f"      ✓ FAST response!")
                        elif time_to_first_chunk < 20:
                            print(f"      ~ Moderate response")
                        else:
                            print(f"      ✗ SLOW response")
                        break
                
                # Read rest of response
                for line in response.iter_lines():
                    pass
                
                total_time = time.time() - start_time
                print(f"      Total time: {total_time:.2f}s")
                
            else:
                print(f"      Error: HTTP {response.status_code}")
                
        except requests.Timeout:
            print(f"      ✗ TIMEOUT (>35s)")
        except Exception as e:
            print(f"      Error: {e}")
        
        # Short delay between requests
        if i < 2:
            time.sleep(1)
    
    print("\n" + "="*60)
    print(" Test Complete")
    print("="*60)

if __name__ == "__main__":
    test_api_performance()