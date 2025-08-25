#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Qdrant 컬렉션 생성 스크립트
"""

from qdrant_client import QdrantClient, models

# Qdrant 클라이언트 연결
client = QdrantClient(host="localhost", port=6333)

collection_name = "my_documents"

# 기존 컬렉션이 있는지 확인
collections = client.get_collections()
existing_collections = [col.name for col in collections.collections]

if collection_name in existing_collections:
    print(f"Collection '{collection_name}' already exists.")
else:
    print(f"Creating collection '{collection_name}'...")
    
    # 컬렉션 생성 (BGE-M3 모델의 임베딩 차원은 1024)
    client.create_collection(
        collection_name=collection_name,
        vectors_config=models.VectorParams(
            size=1024,  # BGE-M3 embedding dimension
            distance=models.Distance.COSINE
        )
    )
    print(f"Collection '{collection_name}' created successfully!")

# 컬렉션 정보 확인
info = client.get_collection(collection_name)
print(f"Collection info:")
print(f"  - Vectors count: {info.vectors_count}")
print(f"  - Status: {info.status}")