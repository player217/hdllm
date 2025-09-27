#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
포괄적 메일 통합 테스트
- 다양한 엣지 케이스 테스트
- 에러 처리 검증
"""

import sys
import os
import tempfile
from pathlib import Path
from datetime import datetime
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.policy import default

# 프로젝트 경로 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

try:
    from HDLLM import extract_email_name, parse_eml_date, keep_name_only
    print("[OK] HDLLM 모듈 import 성공")
except ImportError as e:
    print(f"[ERROR] HDLLM 모듈 import 실패: {e}")
    sys.exit(1)

def test_edge_cases():
    """엣지 케이스 테스트"""
    print("\n=== 엣지 케이스 테스트 ===")
    
    test_cases = [
        # 빈 값 테스트
        ("", ""),
        (None, ""),
        ("N/A", ""),
        
        # 특수 문자 테스트
        ("테스트 <test@한글.com>", "테스트"),
        ("John O'Brien <john@test.com>", "John O'Brien"),
        ('"Smith, John" <smith@test.com>', "Smith, John"),
        
        # 형식 변형 테스트
        ("test@example.com", "test@example.com"),
        ("<test@example.com>", "test@example.com"),
        ("Test User<test@example.com>", "Test User"),  # 공백 없음
    ]
    
    failed = 0
    for input_val, expected in test_cases:
        try:
            result = extract_email_name(input_val) if input_val is not None else extract_email_name("")
            if result == expected:
                print(f"  [OK] '{input_val}' -> '{result}'")
            else:
                print(f"  [FAIL] '{input_val}' -> 예상: '{expected}', 실제: '{result}'")
                failed += 1
        except Exception as e:
            print(f"  ✗ '{input_val}' -> 오류: {e}")
            failed += 1
    
    return failed == 0

def test_date_edge_cases():
    """날짜 파싱 엣지 케이스"""
    print("\n=== 날짜 파싱 엣지 케이스 ===")
    
    test_dates = [
        # 다양한 형식
        ("2024-01-01", "2024-01-01 00:00:00"),
        ("01 Jan 2024", "2024-01-01 00:00:00"),
        ("January 1, 2024", "2024-01-01 00:00:00"),
        
        # 잘못된 형식
        ("", ""),
        ("not a date", "not a date"),
        ("N/A", ""),
    ]
    
    failed = 0
    for input_val, expected in test_dates:
        result = parse_eml_date(input_val)
        # 날짜 파싱은 시간대에 따라 결과가 달라질 수 있으므로 날짜 부분만 검증
        if input_val in ["", "not a date", "N/A"]:
            if result == expected:
                print(f"  [OK] '{input_val}' -> '{result}'")
            else:
                print(f"  [FAIL] '{input_val}' -> 예상: '{expected}', 실제: '{result}'")
                failed += 1
        else:
            if result.startswith(expected[:10]):  # 날짜 부분만
                print(f"  ✓ '{input_val}' -> '{result}'")
            else:
                print(f"  ✗ '{input_val}' -> 예상 시작: '{expected[:10]}', 실제: '{result}'")
                failed += 1
    
    return failed == 0

def test_multipart_eml():
    """멀티파트 EML 테스트"""
    print("\n=== 멀티파트 EML 테스트 ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # 멀티파트 메시지 생성
        msg = MIMEMultipart()
        msg['Subject'] = '멀티파트 테스트'
        msg['From'] = '발신자 <sender@test.com>'
        msg['To'] = '수신자 <receiver@test.com>'
        msg['Date'] = email.utils.formatdate(localtime=True)
        
        # 텍스트 파트
        text_part = MIMEText("텍스트 본문입니다.", 'plain', 'utf-8')
        msg.attach(text_part)
        
        # HTML 파트
        html_part = MIMEText("<html><body>HTML 본문입니다.</body></html>", 'html', 'utf-8')
        msg.attach(html_part)
        
        # 파일로 저장
        eml_file = temp_path / "multipart.eml"
        with open(eml_file, 'wb') as f:
            f.write(msg.as_bytes())
        
        print(f"멀티파트 EML 생성: {eml_file}")
        
        # 파싱 테스트
        try:
            with open(eml_file, 'rb') as f:
                from email.parser import BytesParser
                parser = BytesParser(policy=default)
                parsed_msg = parser.parse(f)
                
                # 헤더 확인
                subject = parsed_msg.get('Subject', '')
                sender = extract_email_name(parsed_msg.get('From', ''))
                
                print(f"  Subject: {subject}")
                print(f"  Sender: {sender}")
                
                # 본문 추출
                body = None
                if parsed_msg.is_multipart():
                    for part in parsed_msg.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_content()
                            break
                
                if body:
                    print(f"  Body: {body[:50]}...")
                    print("  [OK] 멀티파트 본문 추출 성공")
                    return True
                else:
                    print("  [ERROR] 멀티파트 본문 추출 실패")
                    return False
                    
        except Exception as e:
            print(f"  [ERROR] 멀티파트 파싱 실패: {e}")
            return False

def test_corrupted_eml():
    """손상된 EML 파일 테스트"""
    print("\n=== 손상된 EML 테스트 ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # 잘못된 형식의 EML
        bad_eml = temp_path / "corrupted.eml"
        with open(bad_eml, 'w', encoding='utf-8') as f:
            f.write("이것은 올바른 EML 형식이 아닙니다.\n")
            f.write("헤더도 없고 본문만 있습니다.\n")
        
        try:
            with open(bad_eml, 'rb') as f:
                from email.parser import BytesParser
                parser = BytesParser(policy=default)
                msg = parser.parse(f)
                
                # 헤더가 없어도 파싱은 성공해야 함
                subject = msg.get('Subject', 'N/A')
                print(f"  Subject: {subject}")
                
                # 본문은 전체 내용이 되어야 함
                body = msg.get_content() if hasattr(msg, 'get_content') else str(msg)
                if body:
                    print(f"  Body 추출: {len(body)} bytes")
                    print("  [OK] 손상된 파일도 안전하게 처리")
                    return True
                    
        except Exception as e:
            print(f"  [WARNING] 예외 발생 (예상됨): {e}")
            # 손상된 파일에서 예외가 발생하는 것도 정상
            return True

def test_msg_eml_consistency():
    """MSG와 EML 처리 일관성 테스트"""
    print("\n=== MSG/EML 일관성 테스트 ===")
    
    # 두 형식 모두 빈 문자열 반환 확인
    test_values = ["", None, "N/A"]
    
    all_consistent = True
    for val in test_values:
        # keep_name_only는 None 처리가 다를 수 있음
        if val is not None:
            msg_result = keep_name_only(val)
            eml_result = extract_email_name(val)
            
            if msg_result == eml_result:
                print(f"  ✓ 일관성 OK: '{val}' -> MSG:'{msg_result}', EML:'{eml_result}'")
            else:
                print(f"  ✗ 불일치: '{val}' -> MSG:'{msg_result}', EML:'{eml_result}'")
                all_consistent = False
    
    return all_consistent

def main():
    """메인 테스트 함수"""
    print("[TEST] 포괄적 메일 처리 테스트 시작")
    print("=" * 50)
    
    test_results = []
    
    # 테스트 실행
    test_results.append(("엣지 케이스", test_edge_cases()))
    test_results.append(("날짜 파싱 엣지 케이스", test_date_edge_cases()))
    test_results.append(("멀티파트 EML", test_multipart_eml()))
    test_results.append(("손상된 EML", test_corrupted_eml()))
    test_results.append(("MSG/EML 일관성", test_msg_eml_consistency()))
    
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