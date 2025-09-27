#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UTF-8 안전 테스트 파일
Windows 콘솔 환경에서 인코딩 문제 없이 실행되는 테스트
"""

import sys
import os
import tempfile
from pathlib import Path

# Windows 콘솔 인코딩 문제 해결
if sys.platform.startswith('win'):
    import locale
    try:
        # stdout을 UTF-8로 재구성
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except (AttributeError, OSError):
        # Python < 3.7이거나 reconfigure가 실패한 경우
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 프로젝트 경로 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

try:
    from HDLLM import MailParser, extract_email_name, parse_eml_date, keep_name_only
    print("[OK] HDLLM 모듈 import 성공")
except ImportError as e:
    print(f"[ERROR] HDLLM 모듈 import 실패: {e}")
    sys.exit(1)

def test_utf8_safe_parsing():
    """UTF-8 안전 파싱 테스트"""
    print("\n=== UTF-8 안전 파싱 테스트 ===")
    
    # 안전한 ASCII 문자열로만 테스트 (수정된 로직 반영)
    test_cases = [
        ("Basic Email <basic@test.com>", "Basic Email"),
        ("user@example.com", "user"),  # @ 앞부분만 추출하도록 수정
        ("", ""),
        ("N/A", "")
    ]
    
    success_count = 0
    for input_val, expected in test_cases:
        result = extract_email_name(input_val)
        if result == expected:
            print(f"  [OK] '{input_val}' -> '{result}'")
            success_count += 1
        else:
            print(f"  [FAIL] '{input_val}' -> 예상: '{expected}', 실제: '{result}'")
    
    print(f"ASCII 테스트: {success_count}/{len(test_cases)} 성공")
    return success_count == len(test_cases)

def test_mailparser_ascii_only():
    """MailParser ASCII 전용 테스트"""
    print("\n=== MailParser ASCII 전용 테스트 ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        mail_parser = MailParser()
        
        # ASCII 전용 EML 파일 생성
        import email
        from email.mime.text import MIMEText
        
        msg = MIMEText("This is ASCII only test email.", 'plain', 'utf-8')
        msg['Subject'] = 'ASCII Test Email'
        msg['From'] = 'Sender <sender@test.com>'
        msg['To'] = 'Receiver <receiver@test.com>'
        msg['Date'] = email.utils.formatdate(localtime=True)
        
        eml_file = temp_path / "ascii_test.eml"
        with open(eml_file, 'wb') as f:
            f.write(msg.as_bytes())
        
        try:
            parsed_data = mail_parser.parse_mail_file(eml_file)
            
            if parsed_data:
                print(f"  Subject: {parsed_data['subject']}")
                print(f"  Sender: {parsed_data['sender']}")
                print(f"  [OK] ASCII EML 파싱 성공")
                return True
            else:
                print("  [ERROR] ASCII EML 파싱 실패")
                return False
                
        except Exception as e:
            print(f"  [ERROR] ASCII EML 테스트 실패: {e}")
            return False

def test_consistency_ascii():
    """MSG/EML 일관성 ASCII 테스트"""
    print("\n=== MSG/EML 일관성 ASCII 테스트 ===")
    
    # ASCII 안전 값들로 테스트
    test_values = ["", "N/A", "user@test.com"]
    
    all_consistent = True
    for val in test_values:
        msg_result = keep_name_only(val)
        eml_result = extract_email_name(val)
        
        if msg_result == eml_result:
            print(f"  [OK] 일관성: '{val}' -> MSG:'{msg_result}', EML:'{eml_result}'")
        else:
            print(f"  [FAIL] 불일치: '{val}' -> MSG:'{msg_result}', EML:'{eml_result}'")
            all_consistent = False
    
    return all_consistent

def main():
    """메인 테스트 함수"""
    print("[TEST] UTF-8 안전 메일 처리 테스트")
    print("=" * 50)
    
    test_results = []
    
    # 테스트 실행
    test_results.append(("UTF-8 안전 파싱", test_utf8_safe_parsing()))
    test_results.append(("MailParser ASCII", test_mailparser_ascii_only()))
    test_results.append(("일관성 ASCII", test_consistency_ascii()))
    
    # 결과 요약
    print("\n" + "=" * 50)
    print("[SUMMARY] UTF-8 안전 테스트 결과")
    
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n총 테스트: {total}, 통과: {passed}")
    
    if passed == total:
        print("\n[SUCCESS] 모든 UTF-8 안전 테스트 통과!")
        print("Core functionality verified with ASCII-safe testing")
        return True
    else:
        print("\n[FAILED] 일부 테스트 실패")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)