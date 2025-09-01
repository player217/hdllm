# 파일 경로: src/parsers/02_default_parser.py
from __future__ import annotations
from pathlib import Path
from typing import List
from tqdm import tqdm
import logging
try:
    from tika import parser as tika_parser
    from langchain.docstore.document import Document
except ImportError:
    raise ImportError("파싱 필요 라이브러리: tika, langchain")

# 메인 GUI에서 호출할 진입점 함수
def load_documents(folder_path: Path, file_filter: List[str]) -> List[Document]:
    all_docs = []
    # file_filter를 사용하여 지정된 확장자만 검색
    files_to_process = []
    for ext in file_filter:
        files_to_process.extend(folder_path.rglob(f"*{ext}"))
    
    files = sorted(list(set(p for p in files_to_process if p.is_file() and not p.name.startswith("~$"))))

    for file_path in tqdm(files, desc="기본 Tika 파서 실행 중", unit="file"):
        try:
            parsed = tika_parser.from_file(str(file_path))
            content = parsed.get("content", "")
            if content and content.strip():
                meta = {
                    "file_name": file_path.name,
                    "path": str(file_path.resolve()),
                    "source_type": "document",
                    "parser": "기본 Tika 파서"
                }
                all_docs.append(Document(page_content=content, metadata=meta))
        except Exception as e:
            logging.error(f"Tika 파싱 오류 {file_path.name}: {e}")
    return all_docs