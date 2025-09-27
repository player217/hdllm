# 파일 경로: src/parsers/02_default_parser.py
from __future__ import annotations
from pathlib import Path
from typing import List
from datetime import datetime
from tqdm import tqdm
import logging
import os

try:
    from tika import parser as tika_parser
    from tika import tika
    from langchain.docstore.document import Document
except ImportError:
    raise ImportError("파싱 필요 라이브러리: tika, langchain")

# Tika 서버 설정 최적화
os.environ['TIKA_SERVER_JAR'] = 'https://repo1.maven.org/maven2/org/apache/tika/tika-server/2.9.0/tika-server-2.9.0.jar'
os.environ['TIKA_CLIENT_ONLY'] = 'False'
os.environ['TIKA_SERVER_ENDPOINT'] = 'http://localhost:9998'

# Tika 서버 설정 (첫 호출 시 자동으로 시작됨)


# 메인 GUI에서 호출할 진입점 함수
def load_documents(folder_path: Path, file_filter: List[str]) -> List[Document]:
    all_docs = []
    # file_filter를 사용하여 지정된 확장자만 검색
    files_to_process = []
    for ext in file_filter:
        files_to_process.extend(folder_path.rglob(f"*{ext}"))
    
    files = sorted(list(set(p for p in files_to_process if p.is_file() and not p.name.startswith("~$"))))
    
    # 파일이 있을 경우 첫 파싱에서 Tika 서버 시작
    if files:
        logging.info(f"Tika 파서 시작: {len(files)}개 파일 처리 예정")

    for file_path in tqdm(files, desc="Tika 문서 파싱", unit="파일"):
        try:
            # Tika 파서 실행 (타임아웃 설정으로 무한 대기 방지)
            parsed = tika_parser.from_file(
                str(file_path),
                serverEndpoint=os.environ.get('TIKA_SERVER_ENDPOINT', 'http://localhost:9998'),
                requestOptions={'timeout': 30}  # 30초 타임아웃
            )
            content = parsed.get("content", "")
            if content and content.strip():
                # 파일 시스템 메타데이터 수집
                stat = file_path.stat()
                
                # Tika 메타데이터 추출
                tika_metadata = parsed.get("metadata", {})
                
                # 일반 문서 메타데이터 생성
                meta = {
                    # 기본 정보 (선각 파서와 통일)
                    "DATA_TYPE": "일반문서",
                    "file_name": file_path.name,
                    "path": str(file_path.resolve()),
                    "source_type": "document",
                    "parser": "기본 Tika 파서",
                    
                    # 파일 시스템 메타데이터 (핵심 요구사항)
                    "file_size": stat.st_size,
                    "created_date": datetime.fromtimestamp(stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S'),
                    "modified_date": datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                    "file_extension": file_path.suffix.lower(),
                    
                    # Tika 문서 메타데이터
                    "title": tika_metadata.get("title", "") or tika_metadata.get("Title", ""),
                    "author": tika_metadata.get("author", "") or tika_metadata.get("Author", "") or tika_metadata.get("creator", ""),
                    "content_type": tika_metadata.get("Content-Type", ""),
                    "subject": tika_metadata.get("subject", "") or tika_metadata.get("Subject", ""),
                    "keywords": tika_metadata.get("Keywords", "") or tika_metadata.get("keywords", ""),
                    
                    # 추가 문서 정보
                    "page_count": tika_metadata.get("xmpTPg:NPages", "") or tika_metadata.get("Page-Count", ""),
                    "word_count": tika_metadata.get("Word-Count", ""),
                    "language": tika_metadata.get("language", "") or tika_metadata.get("Language", ""),
                }
                
                # 빈 값 제거
                meta = {k: v for k, v in meta.items() if v != ""}
                
                all_docs.append(Document(page_content=content, metadata=meta))
        except Exception as e:
            logging.error(f"Tika 파싱 오류 {file_path.name}: {e}")
            # 타임아웃이나 연결 오류 시 건너뛰기
            continue
    
    if files:
        logging.info(f"Tika 파싱 완료: {len(all_docs)}개 문서 처리됨")
    
    return all_docs