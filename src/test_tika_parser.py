#!/usr/bin/env python3
"""
Tika 파서 메타데이터 통합 테스트
선각 파서와 동일한 형태의 메타데이터 구조 검증 및 테스트
"""

import os
import sys
import tempfile
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

try:
    # 모듈 import를 동적으로 수행 (숫자로 시작하는 파일명 때문)
    import importlib.util
    parser_path = project_root / "src" / "parsers" / "02_default_parser.py"
    spec = importlib.util.spec_from_file_location("default_parser", parser_path)
    default_parser_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(default_parser_module)
    load_documents = default_parser_module.load_documents
    
    from langchain.docstore.document import Document
    print("SUCCESS: Tika parser import successful")
except ImportError as e:
    print(f"FAILED: Import error: {e}")
    sys.exit(1)

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class TikaParserTester:
    def __init__(self):
        self.test_results = []
        self.temp_dir = None
        
    def create_test_files(self) -> Path:
        """테스트용 임시 파일들 생성"""
        self.temp_dir = Path(tempfile.mkdtemp(prefix="tika_test_"))
        print(f"TEST: Creating test files in {self.temp_dir}")
        
        # 간단한 텍스트 파일 생성
        txt_file = self.temp_dir / "test_document.txt"
        txt_file.write_text("이것은 Tika 파서 테스트를 위한 한글 텍스트 파일입니다.\n테스트 내용이 포함되어 있습니다.", encoding='utf-8')
        
        # HTML 파일 생성 (Tika가 지원)
        html_file = self.temp_dir / "test_document.html"
        html_file.write_text("""<!DOCTYPE html>
<html>
<head>
    <title>테스트 문서</title>
    <meta name="author" content="Tika 테스터">
    <meta name="subject" content="테스트 주제">
</head>
<body>
    <h1>Tika 파서 테스트</h1>
    <p>이것은 HTML 형태의 테스트 문서입니다.</p>
</body>
</html>""", encoding='utf-8')
        
        print(f"SUCCESS: Created {len(list(self.temp_dir.glob('*')))} test files")
        return self.temp_dir
    
    def test_metadata_structure(self, docs: List[Document]) -> bool:
        """메타데이터 구조 검증"""
        print("\nTEST: Validating metadata structure...")
        
        required_fields = [
            "DATA_TYPE", "file_name", "path", "source_type", "parser",
            "file_size", "created_date", "modified_date", "file_extension"
        ]
        
        all_passed = True
        
        for i, doc in enumerate(docs):
            print(f"  - Document {i+1}: {doc.metadata.get('file_name', 'Unknown')}")
            
            missing_fields = []
            for field in required_fields:
                if field not in doc.metadata:
                    missing_fields.append(field)
                    all_passed = False
            
            if missing_fields:
                print(f"    FAILED: Missing fields: {missing_fields}")
            else:
                print(f"    SUCCESS: All required fields present")
                
            # 메타데이터 상세 출력
            metadata = doc.metadata
            print(f"    Metadata details:")
            print(f"      - DATA_TYPE: {metadata.get('DATA_TYPE', 'N/A')}")
            print(f"      - file_name: {metadata.get('file_name', 'N/A')}")
            print(f"      - file_size: {metadata.get('file_size', 'N/A')} bytes")
            print(f"      - modified_date: {metadata.get('modified_date', 'N/A')}")
            print(f"      - file_extension: {metadata.get('file_extension', 'N/A')}")
            print(f"      - title: {metadata.get('title', 'N/A')}")
            print(f"      - author: {metadata.get('author', 'N/A')}")
            print(f"      - content_type: {metadata.get('content_type', 'N/A')}")
        
        return all_passed
    
    def test_date_format(self, docs: List[Document]) -> bool:
        """날짜 형식 검증 (YYYY-MM-DD HH:mm:ss)"""
        print("\nTEST: Validating date format...")
        
        date_fields = ["created_date", "modified_date"]
        all_passed = True
        
        for doc in docs:
            for field in date_fields:
                if field in doc.metadata:
                    date_str = doc.metadata[field]
                    try:
                        # 날짜 파싱 시도
                        parsed_date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                        print(f"    SUCCESS: {field} format valid: {date_str}")
                    except ValueError:
                        print(f"    FAILED: {field} format invalid: {date_str}")
                        all_passed = False
        
        return all_passed
    
    def test_seongak_compatibility(self, docs: List[Document]) -> bool:
        """선각 파서와의 호환성 검증"""
        print("\nTEST: Validating Seongak parser compatibility...")
        
        # 선각 파서의 필수 필드들
        seongak_common_fields = ["DATA_TYPE", "path"]
        
        all_passed = True
        for doc in docs:
            for field in seongak_common_fields:
                if field not in doc.metadata:
                    print(f"    FAILED: Missing Seongak-compatible field: {field}")
                    all_passed = False
                else:
                    print(f"    SUCCESS: Seongak-compatible field present: {field}")
        
        # DATA_TYPE 값 검증
        for doc in docs:
            data_type = doc.metadata.get('DATA_TYPE')
            if data_type == "일반문서":
                print(f"    SUCCESS: DATA_TYPE correct: {data_type}")
            else:
                print(f"    FAILED: DATA_TYPE incorrect: {data_type}")
                all_passed = False
        
        return all_passed
    
    def test_file_system_metadata(self, docs: List[Document]) -> bool:
        """파일 시스템 메타데이터 정확성 검증"""
        print("\nTEST: Validating file system metadata accuracy...")
        
        all_passed = True
        for doc in docs:
            file_path = Path(doc.metadata.get('path', ''))
            if not file_path.exists():
                print(f"    FAILED: File path doesn't exist: {file_path}")
                all_passed = False
                continue
                
            # 실제 파일 정보와 비교
            actual_stat = file_path.stat()
            
            # 파일 크기 검증
            reported_size = doc.metadata.get('file_size')
            if reported_size != actual_stat.st_size:
                print(f"    FAILED: File size mismatch - reported: {reported_size}, actual: {actual_stat.st_size}")
                all_passed = False
            else:
                print(f"    SUCCESS: File size correct: {reported_size} bytes")
            
            # 확장자 검증
            reported_ext = doc.metadata.get('file_extension')
            actual_ext = file_path.suffix.lower()
            if reported_ext != actual_ext:
                print(f"    FAILED: Extension mismatch - reported: {reported_ext}, actual: {actual_ext}")
                all_passed = False
            else:
                print(f"    SUCCESS: Extension correct: {reported_ext}")
        
        return all_passed
    
    def run_all_tests(self):
        """모든 테스트 실행"""
        print("="*60)
        print("TIKA PARSER METADATA INTEGRATION TEST")
        print("="*60)
        
        try:
            # 1. 테스트 파일 생성
            test_dir = self.create_test_files()
            
            # 2. Tika 파서로 문서 로드
            print("\nTEST: Loading documents with Tika parser...")
            file_filters = ['.txt', '.html']  # 테스트 파일 확장자
            docs = load_documents(test_dir, file_filters)
            
            if not docs:
                print("FAILED: No documents loaded")
                return False
            
            print(f"SUCCESS: Loaded {len(docs)} documents")
            
            # 3. 테스트 실행
            tests = [
                ("Metadata Structure", self.test_metadata_structure),
                ("Date Format", self.test_date_format),
                ("Seongak Compatibility", self.test_seongak_compatibility),
                ("File System Metadata", self.test_file_system_metadata),
            ]
            
            all_tests_passed = True
            for test_name, test_func in tests:
                print(f"\n{'='*40}")
                print(f"RUNNING: {test_name}")
                print(f"{'='*40}")
                
                try:
                    result = test_func(docs)
                    if result:
                        print(f"✅ PASSED: {test_name}")
                    else:
                        print(f"❌ FAILED: {test_name}")
                        all_tests_passed = False
                except Exception as e:
                    print(f"❌ ERROR: {test_name} - {e}")
                    all_tests_passed = False
            
            # 4. 최종 결과
            print("\n" + "="*60)
            if all_tests_passed:
                print("🎉 ALL TESTS PASSED! Tika parser metadata integration successful!")
            else:
                print("💥 SOME TESTS FAILED! Check the output above for details.")
            print("="*60)
            
            return all_tests_passed
            
        except Exception as e:
            print(f"CRITICAL ERROR: {e}")
            import traceback
            traceback.print_exc()
            return False
            
        finally:
            # 임시 파일 정리
            if self.temp_dir and self.temp_dir.exists():
                import shutil
                shutil.rmtree(self.temp_dir)
                print(f"\nCLEANUP: Removed temporary directory: {self.temp_dir}")

def main():
    """메인 테스트 함수"""
    tester = TikaParserTester()
    success = tester.run_all_tests()
    
    if success:
        print("\n🎯 RECOMMENDATION: Integration ready for production!")
        sys.exit(0)
    else:
        print("\n⚠️  RECOMMENDATION: Fix issues before production deployment!")
        sys.exit(1)

if __name__ == "__main__":
    main()