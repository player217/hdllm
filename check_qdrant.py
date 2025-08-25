#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Qdrant 데이터베이스 확인 유틸리티
컬렉션 정보, 데이터 상태, 검색 테스트를 통합 제공
"""
import sys
import io
import argparse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from qdrant_client import QdrantClient
from langchain_huggingface import HuggingFaceEmbeddings
import json

def check_collections(client):
    """컬렉션 목록 확인"""
    print("\n📦 컬렉션 목록:")
    collections = client.get_collections()
    for col in collections.collections:
        print(f"  - {col.name}")
    return [col.name for col in collections.collections]

def check_collection_info(client, collection_name):
    """컬렉션 상세 정보 확인"""
    try:
        info = client.get_collection(collection_name)
        print(f"\n📊 '{collection_name}' 컬렉션 정보:")
        print(f"  - 벡터 수: {info.vectors_count}")
        print(f"  - 인덱싱된 벡터: {info.indexed_vectors_count}")
        print(f"  - 상태: {info.status}")
        return info.vectors_count
    except Exception as e:
        print(f"  ❌ 오류: {e}")
        return 0

def show_sample_data(client, collection_name, limit=5):
    """샘플 데이터 표시"""
    try:
        result = client.scroll(
            collection_name=collection_name,
            limit=limit,
            with_payload=True,
            with_vectors=False
        )
        
        points = result[0]
        print(f"\n📄 샘플 데이터 (최대 {limit}개):")
        
        for i, point in enumerate(points, 1):
            print(f"\n  [{i}] ID: {point.id}")
            if point.payload:
                # 주요 필드만 표시
                for key in ['subject', 'sender', 'date', 'type']:
                    if key in point.payload:
                        value = point.payload[key]
                        if isinstance(value, str) and len(value) > 50:
                            value = value[:50] + "..."
                        print(f"      {key}: {value}")
    except Exception as e:
        print(f"  ❌ 데이터 조회 오류: {e}")

def test_search(client, collection_name, query="테스트"):
    """검색 테스트"""
    try:
        embeddings = HuggingFaceEmbeddings(
            model_name="BAAI/bge-m3",
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )
        
        query_vector = embeddings.embed_query(query)
        
        results = client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=3
        )
        
        print(f"\n🔍 검색 테스트 (쿼리: '{query}'):")
        if results:
            for i, result in enumerate(results, 1):
                print(f"  [{i}] Score: {result.score:.4f}")
                if result.payload and 'subject' in result.payload:
                    print(f"      제목: {result.payload['subject'][:50]}...")
        else:
            print("  검색 결과 없음")
    except Exception as e:
        print(f"  ❌ 검색 오류: {e}")

def main():
    parser = argparse.ArgumentParser(description='Qdrant 데이터베이스 확인')
    parser.add_argument('--host', default='localhost', help='Qdrant 호스트')
    parser.add_argument('--port', type=int, default=6333, help='Qdrant 포트')
    parser.add_argument('--collection', default='my_documents', help='컬렉션 이름')
    parser.add_argument('--limit', type=int, default=5, help='표시할 샘플 수')
    parser.add_argument('--search', help='검색 테스트 쿼리')
    parser.add_argument('--simple', action='store_true', help='간단한 정보만 표시')
    
    args = parser.parse_args()
    
    # Qdrant 클라이언트 연결
    client = QdrantClient(host=args.host, port=args.port)
    
    print("=" * 60)
    print("Qdrant 데이터베이스 확인 유틸리티")
    print("=" * 60)
    
    # 컬렉션 목록
    collections = check_collections(client)
    
    # 컬렉션 정보
    if args.collection in collections:
        count = check_collection_info(client, args.collection)
        
        if not args.simple and count > 0:
            # 샘플 데이터
            show_sample_data(client, args.collection, args.limit)
            
            # 검색 테스트
            if args.search:
                test_search(client, args.collection, args.search)
    else:
        print(f"\n⚠️ '{args.collection}' 컬렉션이 없습니다.")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()