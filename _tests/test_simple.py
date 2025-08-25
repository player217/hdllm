#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
간단한 검색 테스트 (타임아웃 포함)
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import requests
import json

# 테스트 쿼리
test_query = {
    "question": "르꼬끄 패딩 할인 몇퍼센트야?",
    "source": "mail",
    "model": "gemma3:4b"
}

print("=" * 60)
print("검색 테스트 (타임아웃 10초)")
print("=" * 60)
print(f"질문: {test_query['question']}")
print(f"소스: {test_query['source']}")
print("-" * 60)

try:
    # POST 요청 (짧은 타임아웃)
    response = requests.post(
        "http://localhost:8081/ask",
        json=test_query,
        headers={"Content-Type": "application/json; charset=utf-8"},
        stream=True,
        timeout=10  # 10초 타임아웃
    )
    
    print(f"응답 상태: {response.status_code}")
    
    if response.status_code == 200:
        print("\n응답:")
        print("-" * 40)
        
        full_answer = ""
        references = []
        
        for line in response.iter_lines():
            if line:
                try:
                    data = json.loads(line.decode('utf-8'))
                    
                    if "answer_chunk" in data:
                        chunk = data["answer_chunk"]
                        full_answer += chunk
                        print(chunk, end='', flush=True)
                    
                    if "references" in data:
                        references = data["references"]
                        
                except json.JSONDecodeError as e:
                    print(f"\nJSON 파싱 오류: {e}")
        
        print("\n" + "-" * 40)
        
        if references:
            print(f"\n✅ 검색 성공! {len(references)}개의 참조 문서 발견:")
            for i, ref in enumerate(references, 1):
                print(f"  {i}. {ref.get('title', 'N/A')[:50]}...")  # 제목 첫 50자만
                print(f"     날짜: {ref.get('date', 'N/A')}")
        else:
            if "관련 메일을 찾을 수 없습니다" in full_answer:
                print("\n❌ 검색 실패: 관련 메일을 찾을 수 없습니다")
            else:
                print("\n⚠️ 참조 문서가 없습니다")
    else:
        print(f"❌ 요청 실패: {response.status_code}")
        print(f"응답: {response.text}")
        
except requests.exceptions.Timeout:
    print("\n⏱️ 타임아웃 발생 (10초 초과)")
    print("   LLM 응답이 느립니다. 백엔드 로그를 확인하세요.")
except Exception as e:
    print(f"❌ 오류 발생: {e}")

print("\n" + "=" * 60)
