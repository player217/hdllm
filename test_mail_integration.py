#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
메일 탭 .msg/.eml 통합 처리 테스트
"""

import sys
import os
import tempfile
import shutil
import email
from pathlib import Path
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.policy import default

# 프로젝트 경로 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

try:
    from HDLLM import extract_email_name, parse_eml_date, keep_name_only, MailParser
    print("[OK] HDLLM 모듈에서 헬퍼 함수와 MailParser import 성공")
except ImportError as e:
    print(f"[ERROR] HDLLM 모듈 import 실패: {e}")
    sys.exit(1)

def create_test_eml_file(test_dir: Path, filename: str):
    """테스트용 .eml 파일 생성"""
    
    # 테스트 이메일 메시지 생성
    msg = MIMEText("안녕하세요,\n\n이것은 테스트 이메일입니다.\n\n감사합니다.", 'plain', 'utf-8')
    msg['Subject'] = '테스트 이메일 제목'
    msg['From'] = '홍길동 <hong@test.com>'
    msg['To'] = '김철수 <kim@test.com>'
    msg['Cc'] = '박영희 <park@test.com>'
    msg['Date'] = email.utils.formatdate(localtime=True)
    
    eml_file = test_dir / filename
    with open(eml_file, 'wb') as f:
        f.write(msg.as_bytes())
    
    return eml_file

def test_eml_parsing():
    """EML 파싱 테스트 (MailParser 사용)"""
    print("\n=== EML 파싱 테스트 (MailParser) ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # 테스트 EML 파일 생성
        eml_file = create_test_eml_file(temp_path, "test_email.eml")
        print(f"테스트 EML 파일 생성: {eml_file}")
        
        try:
            # MailParser 사용하여 파싱
            mail_parser = MailParser()
            parsed_data = mail_parser.parse_eml_file(eml_file)
            
            if parsed_data:
                print(f"Subject: {parsed_data['subject']}")
                print(f"From: {parsed_data['sender']}")
                print(f"To: {parsed_data['to']}")
                print(f"Cc: {parsed_data['cc']}")
                print(f"Date: {parsed_data['date']}")
                
                if parsed_data['body']:
                    print(f"Body (일부): {parsed_data['body'][:100]}...")
                else:
                    print("Body: 추출 실패")
                
                print("[OK] EML 파싱 성공!")
                return True
            else:
                print("[ERROR] EML 파싱 실패: parsed_data가 None")
                return False
                
        except Exception as e:
            print(f"[ERROR] EML 파싱 실패: {e}")
            return False

def test_helper_functions():
    """헬퍼 함수 테스트"""
    print("\n=== 헬퍼 함수 테스트 ===")
    
    try:
        # extract_email_name 테스트
        test_emails = [
            "홍길동 <hong@test.com>",
            "<user@example.com>",
            "user@example.com",
            "N/A"
        ]
        
        print("extract_email_name 테스트:")
        for email_str in test_emails:
            result = extract_email_name(email_str)
            print(f"  '{email_str}' -> '{result}'")
        
        # parse_eml_date 테스트
        test_dates = [
            "Mon, 01 Jan 2024 09:00:00 +0900",
            "2024-01-01T09:00:00",
            "N/A",
            "invalid date"
        ]
        
        print("\nparse_eml_date 테스트:")
        for date_str in test_dates:
            result = parse_eml_date(date_str)
            print(f"  '{date_str}' -> '{result}'")
        
        # keep_name_only 테스트 (기존 함수)
        test_msg_emails = [
            "홍길동 <hong@test.com>",
            "김철수 <kim@test.com>; 박영희 <park@test.com>",
            "user@example.com"
        ]
        
        print("\nkeep_name_only 테스트:")
        for email_str in test_msg_emails:
            result = keep_name_only(email_str)
            print(f"  '{email_str}' -> '{result}'")
        
        print("[OK] 헬퍼 함수 테스트 성공!")
        return True
        
    except Exception as e:
        print(f"[ERROR] 헬퍼 함수 테스트 실패: {e}")
        return False

def test_file_scanning():
    """파일 스캔 테스트"""
    print("\n=== 파일 스캔 테스트 ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # 테스트 파일들 생성
        create_test_eml_file(temp_path, "test1.eml")
        create_test_eml_file(temp_path, "test2.eml")
        
        # 서브디렉토리 생성 및 파일 추가
        sub_dir = temp_path / "subdir"
        sub_dir.mkdir()
        create_test_eml_file(sub_dir, "test3.eml")
        
        print(f"테스트 디렉토리: {temp_path}")
        
        # 파일 스캔 (실제 로직과 동일)
        eml_files = list(temp_path.rglob("*.eml"))
        msg_files = list(temp_path.rglob("*.msg"))  # 빈 리스트일 것임
        files = sorted(eml_files + msg_files, key=os.path.getmtime, reverse=True)
        
        print(f"발견된 파일 수: {len(files)}")
        for file_path in files:
            print(f"  - {file_path.relative_to(temp_path)} ({file_path.suffix})")
        
        if len(files) == 3:
            print("[OK] 파일 스캔 성공!")
            return True
        else:
            print("[ERROR] 파일 스캔 실패: 예상과 다른 파일 수")
            return False

def main():
    """메인 테스트 함수"""
    print("[TEST] 메일 탭 .msg/.eml 통합 처리 테스트 시작")
    print("=" * 50)
    
    test_results = []
    
    # 테스트 실행
    test_results.append(("헬퍼 함수 테스트", test_helper_functions()))
    test_results.append(("EML 파싱 테스트", test_eml_parsing()))
    test_results.append(("파일 스캔 테스트", test_file_scanning()))
    
    # 결과 요약
    print("\n" + "=" * 50)
    print("[SUMMARY] 테스트 결과 요약")
    
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n총 테스트: {total}, 통과: {passed}, 실패: {total - passed}")
    
    if passed == total:
        print("[SUCCESS] 모든 테스트 통과!")
        return True
    else:
        print("[FAILED] 일부 테스트 실패")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)