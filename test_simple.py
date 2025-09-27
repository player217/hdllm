#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
간단한 메일 기능 테스트
"""

import sys
from pathlib import Path

# 프로젝트 경로 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

try:
    from HDLLM import extract_email_name, parse_eml_date, keep_name_only
    print("[OK] HDLLM 모듈 import 성공")
except ImportError as e:
    print(f"[ERROR] HDLLM 모듈 import 실패: {e}")
    sys.exit(1)

def test_basic_functionality():
    """기본 기능 테스트"""
    print("\n=== 기본 기능 테스트 ===")
    
    # extract_email_name 테스트
    test_cases = [
        ("홍길동 <hong@test.com>", "홍길동"),
        ("test@example.com", "test@example.com"),
        ("", ""),
        ("N/A", ""),
    ]
    
    print("extract_email_name 테스트:")
    for input_val, expected in test_cases:
        result = extract_email_name(input_val)
        status = "OK" if result == expected else "FAIL"
        print(f"  [{status}] '{input_val}' -> '{result}' (예상: '{expected}')")
    
    # parse_eml_date 테스트
    date_cases = [
        ("Mon, 01 Jan 2024 09:00:00 +0900", "2024-01-01"),
        ("", ""),
        ("N/A", ""),
    ]
    
    print("\nparse_eml_date 테스트:")
    for input_val, expected_start in date_cases:
        result = parse_eml_date(input_val)
        if not expected_start or result.startswith(expected_start):
            status = "OK"
        else:
            status = "FAIL"
        print(f"  [{status}] '{input_val}' -> '{result}'")
    
    # 일관성 테스트
    print("\n기본값 일관성 테스트:")
    empty_values = ["", "N/A"]
    for val in empty_values:
        msg_result = keep_name_only(val)
        eml_result = extract_email_name(val)
        status = "OK" if msg_result == eml_result else "FAIL"
        print(f"  [{status}] '{val}' -> MSG:'{msg_result}', EML:'{eml_result}'")

def main():
    """메인 함수"""
    print("[TEST] 메일 기능 간단 테스트")
    print("=" * 40)
    
    test_basic_functionality()
    
    print("\n" + "=" * 40)
    print("[SUCCESS] 테스트 완료")

if __name__ == "__main__":
    main()