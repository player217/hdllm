#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
백엔드 직접 실행 스크립트
가상환경에서 백엔드만 직접 실행합니다.
"""

import sys
import os
from pathlib import Path

# 프로젝트 루트 경로
project_root = Path(__file__).parent
backend_dir = project_root / "backend"

# Python 경로를 명시적으로 추가
sys.path.insert(0, str(backend_dir))
sys.path.insert(0, str(project_root))

# 환경변수 설정
os.environ['RAG_MAIL_QDRANT_HOST'] = '127.0.0.1'
os.environ['RAG_MAIL_QDRANT_PORT'] = '6333'
os.environ['RAG_DOC_QDRANT_HOST'] = '127.0.0.1'
os.environ['RAG_DOC_QDRANT_PORT'] = '6333'
os.environ['RAG_OLLAMA_URL'] = 'http://127.0.0.1:11434/api/chat'

# 작업 디렉토리 변경
os.chdir(str(backend_dir))

def main():
    print("=" * 60)
    print("백엔드 서버를 시작합니다...")
    print("=" * 60)
    
    try:
        # uvicorn을 직접 import하여 실행
        import uvicorn
        
        # FastAPI 앱 실행
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=8080,
            reload=False,  # Windows에서 reload 비활성화
            log_level="info"
        )
    except ImportError as e:
        print(f"필요한 패키지가 설치되지 않았습니다: {e}")
        print("INSTALL.bat을 실행하여 필요한 패키지를 설치하세요.")
        sys.exit(1)
    except Exception as e:
        print(f"백엔드 서버 실행 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    # Windows multiprocessing 지원
    from multiprocessing import freeze_support
    freeze_support()
    main()