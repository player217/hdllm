#!/usr/bin/env python3
"""
실제 Tika 파싱 테스트 - GUI 없이 직접 파싱 엔진 테스트
Java/Tika 서버가 필요하지만 실제 파싱 결과를 확인
"""

import os
import sys
import tempfile
import logging
from pathlib import Path
from datetime import datetime

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def check_java_installation():
    """Java 설치 여부 확인"""
    try:
        import subprocess
        result = subprocess.run(['java', '-version'], capture_output=True, text=True)
        if result.returncode == 0:
            print("SUCCESS: Java is installed and available")
            print(f"Version info: {result.stderr.split()[2] if result.stderr else 'Unknown'}")
            return True
        else:
            print("FAILED: Java is not properly installed")
            return False
    except FileNotFoundError:
        print("FAILED: Java is not installed")
        return False

def create_test_documents():
    """실제 테스트 문서 파일 생성"""
    temp_dir = Path(tempfile.mkdtemp(prefix="real_tika_test_"))
    print(f"Creating test files in: {temp_dir}")
    
    # 1. 텍스트 파일
    txt_file = temp_dir / "sample.txt"
    txt_file.write_text("""
Tika 파서 실제 테스트 문서

이 문서는 한글 텍스트를 포함한 테스트 파일입니다.
여러 줄의 내용이 있으며, 특수문자도 포함됩니다: !@#$%^&*()

작성일: 2025년 9월 2일
작성자: 테스트 사용자
""", encoding='utf-8')
    
    # 2. HTML 파일 (Tika가 지원)
    html_file = temp_dir / "sample.html"
    html_file.write_text("""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>테스트 HTML 문서</title>
    <meta name="author" content="HTML 테스터">
    <meta name="description" content="Tika HTML 파싱 테스트">
</head>
<body>
    <h1>HTML 파싱 테스트</h1>
    <p>이것은 <strong>HTML</strong> 형식의 테스트 문서입니다.</p>
    <ul>
        <li>첫 번째 항목</li>
        <li>두 번째 항목</li>
    </ul>
    <p>한글과 영어가 모두 포함되어 있습니다.</p>
</body>
</html>""", encoding='utf-8')
    
    print(f"Created {len(list(temp_dir.glob('*')))} test files")
    return temp_dir

def test_direct_parsing():
    """직접 파싱 테스트 (개선된 파서 사용)"""
    print("\n" + "="*60)
    print("REAL TIKA PARSING TEST")
    print("="*60)
    
    # 1. Java 설치 확인
    if not check_java_installation():
        print("\n❌ Java가 설치되어 있지 않습니다.")
        print("Java를 설치한 후 다시 시도하세요:")
        print("- Windows: https://adoptium.net/ 에서 다운로드")
        print("- 또는 GUI에서 파싱 기능을 사용해보세요")
        return False
    
    try:
        # 2. 개선된 파서 import
        import importlib.util
        parser_path = project_root / "src" / "parsers" / "02_default_parser.py"
        spec = importlib.util.spec_from_file_location("default_parser", parser_path)
        default_parser_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(default_parser_module)
        load_documents = default_parser_module.load_documents
        print("✅ 개선된 Tika 파서 로드 성공")
        
        # 3. 테스트 파일 생성
        test_dir = create_test_documents()
        
        # 4. 실제 파싱 수행
        print("\n🔄 Starting real document parsing...")
        file_filters = ['.txt', '.html']
        docs = load_documents(test_dir, file_filters)
        
        if not docs:
            print("❌ 파싱된 문서가 없습니다.")
            return False
        
        print(f"✅ 파싱 성공! {len(docs)}개 문서 처리됨")
        
        # 5. 결과 분석
        print("\n📊 PARSING RESULTS ANALYSIS:")
        print("-" * 40)
        
        for i, doc in enumerate(docs, 1):
            metadata = doc.metadata
            content_preview = doc.page_content[:100] + "..." if len(doc.page_content) > 100 else doc.page_content
            
            print(f"\n📄 Document {i}:")
            print(f"   파일명: {metadata.get('file_name', 'N/A')}")
            print(f"   DATA_TYPE: {metadata.get('DATA_TYPE', 'N/A')}")
            print(f"   파일 크기: {metadata.get('file_size', 'N/A')} bytes")
            print(f"   수정 날짜: {metadata.get('modified_date', 'N/A')}")
            print(f"   확장자: {metadata.get('file_extension', 'N/A')}")
            print(f"   제목: {metadata.get('title', 'N/A')}")
            print(f"   작성자: {metadata.get('author', 'N/A')}")
            print(f"   Content-Type: {metadata.get('content_type', 'N/A')}")
            print(f"   내용 미리보기: {content_preview}")
        
        # 6. 메타데이터 구조 검증
        print(f"\n✅ 메타데이터 검증:")
        required_fields = ["DATA_TYPE", "file_name", "path", "file_size", "modified_date", "file_extension"]
        
        all_valid = True
        for doc in docs:
            missing = [f for f in required_fields if f not in doc.metadata]
            if missing:
                print(f"   ❌ {doc.metadata.get('file_name', 'Unknown')}: 누락된 필드 - {missing}")
                all_valid = False
            else:
                print(f"   ✅ {doc.metadata.get('file_name', 'Unknown')}: 모든 필수 필드 존재")
        
        if all_valid:
            print(f"\n🎉 성공! 모든 문서가 올바른 메타데이터 구조를 가지고 있습니다.")
            print(f"선각 파서와 동일한 형식으로 메타데이터가 생성되었습니다.")
        else:
            print(f"\n⚠️  일부 메타데이터 필드가 누락되었습니다.")
        
        # 7. 정리
        import shutil
        shutil.rmtree(test_dir)
        print(f"\n🧹 임시 파일 정리 완료")
        
        return all_valid
        
    except Exception as e:
        print(f"❌ 테스트 실행 중 오류: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """메인 함수"""
    success = test_direct_parsing()
    
    if success:
        print("\n✅ CONCLUSION: Tika 파서 메타데이터 개선이 성공적으로 완료되었습니다!")
        print("GUI에서 일반문서 파싱 기능을 사용해보세요.")
        return 0
    else:
        print("\n❌ CONCLUSION: 추가 작업이 필요합니다.")
        return 1

if __name__ == "__main__":
    sys.exit(main())