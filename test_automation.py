#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
HD현대미포 Gauss-1 RAG 시스템 자동화 테스트
100회 반복 테스트를 수행합니다.
"""

import asyncio
import random
import json
import time
from datetime import datetime
from playwright.async_api import async_playwright
from typing import Dict, List, Any

# 테스트 케이스 정의
TEST_MESSAGES = [
    # 안전 관련 질문
    "크레인 작업 안전 수칙에 대해 알려주세요",
    "용접 작업 시 주의사항은?",
    "고소작업 안전 기준",
    "화재 예방 수칙",
    "안전 보호구 착용 기준",
    
    # 업무 관련 질문
    "최근 회의록 요약해줘",
    "이번 주 일정 확인",
    "프로젝트 진행 상황",
    "품질 관리 절차",
    "작업 지시서 확인",
    
    # 메일 관련 질문
    "오늘 받은 메일 목록",
    "중요 메일 필터링",
    "안전 관련 메일 찾기",
    "미팅 관련 메일",
    "결재 요청 메일",
    
    # 문서 검색 질문
    "HD현대미포 안전 규정",
    "작업 매뉴얼 검색",
    "기술 사양서",
    "품질 인증서",
    "교육 자료",
    
    # 일반 대화
    "안녕하세요",
    "오늘 날씨는?",
    "도움이 필요해요",
    "감사합니다",
    "테스트 메시지"
]

# UI 기능 테스트
UI_ACTIONS = [
    "new_conversation",  # 새 대화
    "toggle_source",      # 개인메일/부서서버 토글
    "search_conversation", # 대화 검색
    "delete_conversation", # 대화 삭제
    "toggle_sidebar",     # 사이드바 토글
    "dark_mode",          # 다크모드 전환
    "settings",           # 설정 열기
    "feedback_positive",  # 긍정 피드백
    "feedback_negative"   # 부정 피드백
]

class GaussTestAutomation:
    def __init__(self):
        self.test_results = {
            "total_tests": 0,
            "successful": 0,
            "failed": 0,
            "errors": [],
            "response_times": [],
            "ui_tests": {},
            "message_tests": {},
            "start_time": None,
            "end_time": None
        }
        
    async def run_tests(self, iterations: int = 100):
        """100회 반복 테스트 실행"""
        self.test_results["start_time"] = datetime.now().isoformat()
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()
            
            # 페이지 로드
            await page.goto("http://localhost:8001")
            await page.wait_for_load_state("networkidle")
            
            for i in range(iterations):
                print(f"\n=== 테스트 {i+1}/{iterations} ===")
                self.test_results["total_tests"] += 1
                
                try:
                    # 랜덤하게 테스트 유형 선택
                    test_type = random.choice(["message", "ui", "mixed"])
                    
                    if test_type == "message":
                        await self.test_message(page)
                    elif test_type == "ui":
                        await self.test_ui_function(page)
                    else:  # mixed
                        await self.test_message(page)
                        await self.test_ui_function(page)
                    
                    self.test_results["successful"] += 1
                    
                except Exception as e:
                    self.test_results["failed"] += 1
                    self.test_results["errors"].append({
                        "iteration": i + 1,
                        "error": str(e),
                        "timestamp": datetime.now().isoformat()
                    })
                    print(f"Error in test {i+1}: {e}")
                
                # 테스트 간 짧은 대기
                await asyncio.sleep(random.uniform(0.5, 2))
            
            await browser.close()
        
        self.test_results["end_time"] = datetime.now().isoformat()
        self.save_results()
        self.print_summary()
    
    async def test_message(self, page):
        """메시지 전송 테스트"""
        message = random.choice(TEST_MESSAGES)
        print(f"Testing message: {message}")
        
        start_time = time.time()
        
        # 메시지 입력
        await page.fill('input[placeholder="메시지를 입력하세요..."]', message)
        
        # 전송 버튼 클릭
        await page.click('button:has-text("→")')
        
        # 응답 대기 (최대 10초)
        try:
            await page.wait_for_selector('.message-group:last-child .assistant-message', 
                                        timeout=10000)
            response_time = time.time() - start_time
            self.test_results["response_times"].append(response_time)
            
            # 메시지별 성공 카운트
            if message not in self.test_results["message_tests"]:
                self.test_results["message_tests"][message] = {"success": 0, "fail": 0}
            self.test_results["message_tests"][message]["success"] += 1
            
            print(f"✓ Message sent successfully (Response time: {response_time:.2f}s)")
            
        except Exception as e:
            if message not in self.test_results["message_tests"]:
                self.test_results["message_tests"][message] = {"success": 0, "fail": 0}
            self.test_results["message_tests"][message]["fail"] += 1
            raise e
    
    async def test_ui_function(self, page):
        """UI 기능 테스트"""
        action = random.choice(UI_ACTIONS)
        print(f"Testing UI action: {action}")
        
        try:
            if action == "new_conversation":
                await page.click('button:has-text("+ 새 대화")')
                await page.wait_for_timeout(500)
                
            elif action == "toggle_source":
                # 개인메일/부서서버 토글
                if await page.is_visible('button:has-text("개인메일")'):
                    await page.click('button:has-text("개인메일")')
                elif await page.is_visible('button:has-text("부서서버")'):
                    await page.click('button:has-text("부서서버")')
                    
            elif action == "search_conversation":
                await page.fill('input[placeholder="대화 검색..."]', "테스트")
                await page.wait_for_timeout(500)
                await page.fill('input[placeholder="대화 검색..."]', "")
                
            elif action == "delete_conversation":
                # 대화 삭제 버튼이 있으면 클릭
                delete_buttons = await page.query_selector_all('.conversation-item button:has-text("🗑")')
                if delete_buttons:
                    await delete_buttons[0].click()
                    
            elif action == "toggle_sidebar":
                await page.click('button:has-text("☰")')
                await page.wait_for_timeout(500)
                
            elif action == "dark_mode":
                await page.click('button:has-text("🌙")')
                await page.wait_for_timeout(500)
                
            elif action == "settings":
                await page.click('button:has-text("⚙")')
                await page.wait_for_timeout(500)
                
            elif action == "feedback_positive":
                positive_buttons = await page.query_selector_all('button:has-text("👍")')
                if positive_buttons:
                    await positive_buttons[-1].click()
                    
            elif action == "feedback_negative":
                negative_buttons = await page.query_selector_all('button:has-text("👎")')
                if negative_buttons:
                    await negative_buttons[-1].click()
            
            # UI 액션별 성공 카운트
            if action not in self.test_results["ui_tests"]:
                self.test_results["ui_tests"][action] = {"success": 0, "fail": 0}
            self.test_results["ui_tests"][action]["success"] += 1
            
            print(f"✓ UI action completed: {action}")
            
        except Exception as e:
            if action not in self.test_results["ui_tests"]:
                self.test_results["ui_tests"][action] = {"success": 0, "fail": 0}
            self.test_results["ui_tests"][action]["fail"] += 1
            raise e
    
    def save_results(self):
        """테스트 결과 저장"""
        with open("test_results_100.json", "w", encoding="utf-8") as f:
            json.dump(self.test_results, f, ensure_ascii=False, indent=2)
    
    def print_summary(self):
        """테스트 요약 출력"""
        print("\n" + "="*60)
        print("테스트 완료 요약")
        print("="*60)
        print(f"총 테스트: {self.test_results['total_tests']}")
        print(f"성공: {self.test_results['successful']}")
        print(f"실패: {self.test_results['failed']}")
        print(f"성공률: {(self.test_results['successful']/self.test_results['total_tests']*100):.2f}%")
        
        if self.test_results["response_times"]:
            avg_response = sum(self.test_results["response_times"]) / len(self.test_results["response_times"])
            print(f"평균 응답 시간: {avg_response:.2f}초")
        
        print("\n메시지 테스트 결과:")
        for msg, stats in self.test_results["message_tests"].items():
            print(f"  {msg[:30]}... - 성공: {stats['success']}, 실패: {stats['fail']}")
        
        print("\nUI 테스트 결과:")
        for action, stats in self.test_results["ui_tests"].items():
            print(f"  {action} - 성공: {stats['success']}, 실패: {stats['fail']}")
        
        if self.test_results["errors"]:
            print(f"\n에러 발생: {len(self.test_results['errors'])}건")
            for error in self.test_results["errors"][:5]:  # 처음 5개만 표시
                print(f"  - 반복 {error['iteration']}: {error['error'][:50]}...")

if __name__ == "__main__":
    tester = GaussTestAutomation()
    asyncio.run(tester.run_tests(100))