#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
"""
백엔드 로깅 시스템 테스트 스크립트
디버그 모드로 백엔드를 실행하고 검색 요청을 보내 로그를 검증합니다.

사용법:
    1. 디버그 모드로 백엔드 실행:
       set RAG_DEBUG=true && set RAG_VERBOSE=true && python backend/main.py
       
    2. 다른 터미널에서 이 스크립트 실행:
       python test_backend_logging.py
"""

import requests
import json
import time
from datetime import datetime

# 테스트 설정
BACKEND_URL = "http://localhost:8081"
TEST_QUERIES = [
    {
        "question": "르꼬끄 패딩 할인 몇퍼센트야?",
        "source": "mail",
        "description": "르꼬끄 키워드 검색 테스트"
    },
    {
        "question": "패딩 할인",
        "source": "mail", 
        "description": "일반 키워드 검색 테스트"
    },
    {
        "question": "안녕하세요",
        "source": "mail",
        "description": "인사말 테스트"
    }
]

def check_backend_status():
    """백엔드 상태 확인"""
    print("=" * 60)
    print("백엔드 상태 확인")
    print("=" * 60)
    
    try:
        # Health check
        response = requests.get(f"{BACKEND_URL}/health")
        if response.status_code == 200:
            print("✅ 백엔드 Health Check: OK")
        else:
            print(f"❌ 백엔드 Health Check 실패: {response.status_code}")
            return False
            
        # Service status check
        response = requests.get(f"{BACKEND_URL}/status")
        if response.status_code == 200:
            status = response.json()
            print("\n서비스 상태:")
            print(f"  - FastAPI: {'✅' if status.get('fastapi') else '❌'}")
            print(f"  - Ollama: {'✅' if status.get('ollama') else '❌'}")
            print(f"  - Qdrant Mail: {'✅' if status.get('qdrant_mail') else '❌'}")
            print(f"  - Qdrant Doc: {'✅' if status.get('qdrant_doc') else '❌'}")
            
            if not status.get('qdrant_mail'):
                print("\n⚠️ Qdrant Mail 서비스가 실행되지 않았습니다.")
                print("   Qdrant를 먼저 시작해주세요.")
                return False
                
        return True
        
    except requests.exceptions.ConnectionError:
        print("❌ 백엔드에 연결할 수 없습니다.")
        print("   백엔드가 실행 중인지 확인해주세요.")
        return False
    except Exception as e:
        print(f"❌ 상태 확인 중 오류: {e}")
        return False

def send_test_query(query_info):
    """테스트 쿼리 전송 및 응답 분석"""
    print("\n" + "=" * 60)
    print(f"테스트: {query_info['description']}")
    print("=" * 60)
    print(f"질문: {query_info['question']}")
    print(f"소스: {query_info['source']}")
    print("-" * 60)
    
    payload = {
        "question": query_info["question"],
        "source": query_info["source"],
        "model": "gemma3:4b"
    }
    
    try:
        # 스트리밍 응답 처리
        response = requests.post(
            f"{BACKEND_URL}/ask",
            json=payload,
            stream=True,
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"❌ 요청 실패: {response.status_code}")
            print(f"   응답: {response.text}")
            return
            
        print("\n응답 스트림:")
        print("-" * 40)
        
        full_answer = ""
        references = []
        
        for line in response.iter_lines():
            if line:
                try:
                    data = json.loads(line.decode('utf-8'))
                    
                    # 답변 청크 처리
                    if "answer_chunk" in data:
                        chunk = data["answer_chunk"]
                        full_answer += chunk
                        print(chunk, end='', flush=True)
                    
                    # 참조 문서 처리
                    if "references" in data:
                        references = data["references"]
                        
                except json.JSONDecodeError:
                    print(f"\n⚠️ JSON 파싱 실패: {line}")
        
        print("\n" + "-" * 40)
        
        # 결과 분석
        print("\n📊 결과 분석:")
        print(f"  - 전체 답변 길이: {len(full_answer)} 문자")
        print(f"  - 참조 문서 수: {len(references)}")
        
        if references:
            print("\n📚 참조 문서:")
            for i, ref in enumerate(references, 1):
                print(f"  {i}. {ref.get('title', 'N/A')}")
                print(f"     - 날짜: {ref.get('date', 'N/A')}")
                print(f"     - 발신자: {ref.get('sender', 'N/A')}")
        else:
            print("\n⚠️ 참조 문서가 없습니다.")
            
        # 특정 메시지 확인
        if "관련 메일을 찾을 수 없습니다" in full_answer:
            print("\n❌ 메일 검색 실패: '관련 메일을 찾을 수 없습니다' 메시지 발견")
        elif "안녕하세요" in query_info["question"] and "무엇을 도와드릴까요" in full_answer:
            print("\n✅ 인사말 처리 정상")
        elif references:
            print("\n✅ 메일 검색 성공")
        
    except requests.exceptions.Timeout:
        print("❌ 요청 타임아웃 (30초)")
    except Exception as e:
        print(f"❌ 요청 중 오류: {e}")

def analyze_log_file():
    """로그 파일 분석"""
    print("\n" + "=" * 60)
    print("로그 파일 분석")
    print("=" * 60)
    
    from pathlib import Path
    log_dir = Path("logs")
    
    if not log_dir.exists():
        print("❌ logs 디렉토리가 없습니다.")
        return
        
    # 오늘 날짜 로그 파일 찾기
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = log_dir / f"rag_log_{today}.log"
    
    if not log_file.exists():
        print(f"❌ 오늘 날짜 로그 파일이 없습니다: {log_file}")
        # 가장 최근 로그 파일 찾기
        log_files = list(log_dir.glob("rag_log_*.log"))
        if log_files:
            log_file = max(log_files, key=lambda x: x.stat().st_mtime)
            print(f"📁 대신 최근 로그 파일 사용: {log_file.name}")
        else:
            print("❌ 로그 파일을 찾을 수 없습니다.")
            return
    
    print(f"📁 로그 파일: {log_file}")
    
    # 로그 파일 읽기 및 분석
    with open(log_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 주요 로그 패턴 검색
    patterns = {
        "DEBUG 모드": "DEBUG MODE ENABLED",
        "VERBOSE 모드": "VERBOSE LOGGING ENABLED",
        "르꼬끄 감지": "Special keyword '르꼬끄'",
        "컬렉션 검색": "Searching collection:",
        "검색 결과": "Found .* hits in",
        "검색 실패": "No hits found",
        "메타데이터 필드": "Metadata keys:",
        "낮은 점수 경고": "Low score detected",
        "컨텍스트 없음": "No context found"
    }
    
    print("\n📊 로그 패턴 분석:")
    for pattern_name, pattern in patterns.items():
        import re
        count = sum(1 for line in lines if re.search(pattern, line))
        if count > 0:
            print(f"  ✅ {pattern_name}: {count}회 발견")
        else:
            print(f"  ❌ {pattern_name}: 발견되지 않음")
    
    # 최근 에러 확인
    error_lines = [line for line in lines if "ERROR" in line or "❌" in line]
    if error_lines:
        print(f"\n⚠️ 에러 로그 {len(error_lines)}개 발견:")
        for error in error_lines[-5:]:  # 최근 5개만
            print(f"  - {error.strip()}")

def main():
    """메인 테스트 함수"""
    print("🚀 백엔드 로깅 시스템 테스트 시작")
    print("=" * 60)
    
    # 1. 백엔드 상태 확인
    if not check_backend_status():
        print("\n❌ 백엔드가 준비되지 않았습니다.")
        print("\n다음 명령으로 디버그 모드로 백엔드를 실행하세요:")
        print("  Windows: set RAG_DEBUG=true && set RAG_VERBOSE=true && python backend/main.py")
        print("  Linux/Mac: RAG_DEBUG=true RAG_VERBOSE=true python backend/main.py")
        sys.exit(1)
    
    # 2. 테스트 쿼리 전송
    print("\n" + "=" * 60)
    print("테스트 쿼리 전송 시작")
    print("=" * 60)
    
    for query_info in TEST_QUERIES:
        send_test_query(query_info)
        time.sleep(2)  # 요청 간 대기
    
    # 3. 로그 파일 분석
    time.sleep(1)  # 로그 기록 대기
    analyze_log_file()
    
    print("\n" + "=" * 60)
    print("✅ 테스트 완료")
    print("=" * 60)
    print("\n💡 팁:")
    print("  - 실시간 로그 모니터링: python log_monitor.py")
    print("  - 르꼬끄 키워드만 필터링: python log_monitor.py 르꼬끄")
    print("  - DEBUG 레벨만 보기: python log_monitor.py --debug")

if __name__ == "__main__":
    main()