#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
HD현대미포 안전 관련 샘플 메일 데이터 추가
"""

from qdrant_client import QdrantClient, models
from langchain_huggingface import HuggingFaceEmbeddings
import uuid
from datetime import datetime, timedelta

# Qdrant 클라이언트 연결
client = QdrantClient(host="localhost", port=6333)

# 임베딩 모델
embeddings = HuggingFaceEmbeddings(
    model_name="BAAI/bge-m3",
    model_kwargs={'device': 'cpu'},
    encode_kwargs={'normalize_embeddings': True}
)

# 샘플 메일 데이터
sample_mails = [
    {
        "subject": "[안전공지] HD현대미포 2024년 안전보건 관리 규정 개정 안내",
        "sender": "안전보건팀 <safety@hdmipo.com>",
        "body": """
        안녕하세요, HD현대미포 임직원 여러분.
        
        2024년 안전보건 관리 규정이 다음과 같이 개정되었음을 알려드립니다:
        
        1. 작업 전 안전점검 의무화
           - 모든 작업 시작 전 5분 안전점검 실시
           - TBM(Tool Box Meeting) 참여 의무화
        
        2. 개인보호구 착용 기준 강화
           - 안전모, 안전화는 현장 내 상시 착용
           - 용접작업 시 보안경 및 방진마스크 필수
        
        3. 중대재해 예방 조치
           - 고소작업 시 안전대 2중 체결
           - 밀폐공간 작업 시 가스측정 및 감시자 배치
        
        4. 비상대응 체계
           - 비상연락망 숙지 의무
           - 월 1회 비상대피 훈련 참여
        
        모든 임직원은 개정된 규정을 숙지하시고 준수해 주시기 바랍니다.
        
        안전보건팀 드림
        """,
        "date": datetime.now() - timedelta(days=7),
        "link": "file:///C:/safety/regulations_2024.pdf"
    },
    {
        "subject": "[긴급] 조선소 크레인 작업 안전 주의사항",
        "sender": "현장안전관리자 <site_safety@hdmipo.com>",
        "body": """
        긴급 안전 공지사항입니다.
        
        최근 타 조선소에서 크레인 작업 중 중대재해가 발생했습니다.
        HD현대미포 전 현장에 다음 사항을 즉시 적용합니다:
        
        ■ 크레인 작업 안전수칙
        1. 크레인 작업반경 내 출입 절대 금지
        2. 신호수 없는 크레인 작업 금지
        3. 풍속 10m/s 이상 시 작업 중지
        4. 와이어로프 일일점검 의무화
        
        ■ 위반 시 조치사항
        - 1차: 경고 및 안전교육
        - 2차: 작업 중지 명령
        - 3차: 퇴출 조치
        
        안전은 선택이 아닌 필수입니다.
        """,
        "date": datetime.now() - timedelta(days=3),
        "link": "file:///C:/safety/crane_safety_2024.pdf"
    },
    {
        "subject": "RE: 용접작업 안전관리 문의",
        "sender": "김안전 과장 <kim.safety@hdmipo.com>",
        "body": """
        문의하신 용접작업 안전관리 기준에 대해 답변드립니다.
        
        HD현대미포 용접작업 안전기준:
        
        1. 작업 전 준비사항
           - 작업허가서 발급 확인
           - 소화기 비치 (10m 이내)
           - 불꽃비산방지포 설치
        
        2. 작업 중 안전조치
           - 용접 보호구 완전 착용
           - 환기장치 가동
           - 화기감시자 배치
        
        3. 작업 후 조치
           - 잔화 확인 (최소 30분)
           - 작업장 정리정돈
           - 안전점검표 작성
        
        추가 문의사항은 안전보건팀(내선 1234)으로 연락주세요.
        """,
        "date": datetime.now() - timedelta(days=1),
        "link": "file:///C:/safety/welding_guide.pdf"
    }
]

# 컬렉션에 데이터 추가
collection_name = "my_documents"
for mail in sample_mails:
    # 텍스트 결합
    full_text = f"{mail['subject']} {mail['sender']} {mail['body']}"
    
    # 임베딩 생성
    vector = embeddings.embed_query(full_text)
    
    # 포인트 생성
    point_id = str(uuid.uuid4())
    
    # Qdrant에 추가
    client.upsert(
        collection_name=collection_name,
        points=[
            models.PointStruct(
                id=point_id,
                vector=vector,
                payload={
                    "subject": mail["subject"],
                    "sender": mail["sender"],
                    "body": mail["body"],
                    "text": mail["body"],  # Add text field for context extraction
                    "date": mail["date"].isoformat(),
                    "link": mail["link"],
                    "type": "mail",
                    "source_type": "email_body"  # Add source_type for proper formatting
                }
            )
        ]
    )
    print(f"Added: {mail['subject'][:50]}...")

print(f"\nTotal {len(sample_mails)} safety-related mails added.")