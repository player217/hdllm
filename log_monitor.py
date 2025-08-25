#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
실시간 로그 모니터링 도구
백엔드 RAG 시스템의 로그를 실시간으로 모니터링하고 특정 키워드를 필터링합니다.

사용법:
    python log_monitor.py                    # 모든 로그 표시
    python log_monitor.py 르꼬끄            # '르꼬끄' 포함 로그만 표시
    python log_monitor.py --debug           # DEBUG 레벨 로그만 표시
    python log_monitor.py --error           # ERROR 레벨 로그만 표시
    python log_monitor.py --follow          # tail -f 모드
"""

import os
import sys
import time
import datetime
import argparse
from pathlib import Path
import re
from colorama import init, Fore, Style

# colorama 초기화 (Windows 지원)
init(autoreset=True)

class LogMonitor:
    def __init__(self, log_dir="logs", follow=True):
        self.log_dir = Path(log_dir)
        self.follow = follow
        self.colors = {
            'DEBUG': Fore.CYAN,
            'INFO': Fore.GREEN,
            'WARNING': Fore.YELLOW,
            'ERROR': Fore.RED,
            'CRITICAL': Fore.MAGENTA,
        }
        
    def get_latest_log_file(self):
        """가장 최근 로그 파일 찾기"""
        today = datetime.date.today()
        log_pattern = f"rag_log_{today}.log"
        log_file = self.log_dir / log_pattern
        
        if not log_file.exists():
            # 오늘 날짜 파일이 없으면 가장 최근 파일 찾기
            log_files = list(self.log_dir.glob("rag_log_*.log"))
            if log_files:
                log_file = max(log_files, key=lambda x: x.stat().st_mtime)
            else:
                return None
                
        return log_file
    
    def colorize_line(self, line):
        """로그 레벨에 따라 색상 적용"""
        for level, color in self.colors.items():
            if f"| {level} |" in line or f"- {level} -" in line:
                return f"{color}{line}{Style.RESET_ALL}"
        
        # 특수 마커 강조
        if "🔍" in line or "Special keyword" in line:
            return f"{Fore.MAGENTA}{Style.BRIGHT}{line}{Style.RESET_ALL}"
        if "✅" in line or "Found" in line:
            return f"{Fore.GREEN}{Style.BRIGHT}{line}{Style.RESET_ALL}"
        if "⚠️" in line or "No hits" in line:
            return f"{Fore.YELLOW}{line}{Style.RESET_ALL}"
        if "❌" in line or "실패" in line:
            return f"{Fore.RED}{line}{Style.RESET_ALL}"
        if "📊" in line or "Total" in line:
            return f"{Fore.CYAN}{line}{Style.RESET_ALL}"
        if "🎯" in line or "Score:" in line:
            return f"{Fore.BLUE}{line}{Style.RESET_ALL}"
            
        return line
    
    def filter_line(self, line, keywords=None, level=None):
        """필터 조건에 맞는 라인인지 확인"""
        if level:
            if f"| {level.upper()} |" not in line and f"- {level.upper()} -" not in line:
                return False
                
        if keywords:
            # 키워드 중 하나라도 포함되면 True
            if not any(keyword.lower() in line.lower() for keyword in keywords):
                return False
                
        return True
    
    def tail_file(self, filepath, keywords=None, level=None):
        """로그 파일 실시간 모니터링"""
        print(f"📂 Monitoring: {filepath}")
        print(f"🔍 Keywords: {keywords if keywords else 'All'}")
        print(f"📊 Level: {level if level else 'All'}")
        print("=" * 80)
        
        with open(filepath, 'r', encoding='utf-8') as f:
            # 파일 끝으로 이동 (follow 모드일 때만)
            if self.follow:
                f.seek(0, 2)
            else:
                f.seek(0, 0)  # 처음부터 읽기
            
            while True:
                line = f.readline()
                
                if line:
                    line = line.rstrip()
                    if self.filter_line(line, keywords, level):
                        print(self.colorize_line(line))
                elif self.follow:
                    time.sleep(0.1)  # 새 로그 대기
                else:
                    break  # follow 모드가 아니면 종료
    
    def monitor(self, keywords=None, level=None):
        """로그 모니터링 시작"""
        log_file = self.get_latest_log_file()
        
        if not log_file:
            print(f"❌ No log files found in {self.log_dir}")
            return
            
        try:
            self.tail_file(log_file, keywords, level)
        except KeyboardInterrupt:
            print("\n\n🛑 Monitoring stopped")
        except Exception as e:
            print(f"❌ Error: {e}")

def parse_arguments():
    """명령줄 인자 파싱"""
    parser = argparse.ArgumentParser(
        description="RAG 백엔드 로그 실시간 모니터링 도구"
    )
    
    parser.add_argument(
        'keywords',
        nargs='*',
        help='필터링할 키워드 (여러 개 가능)'
    )
    
    parser.add_argument(
        '--debug',
        action='store_const',
        const='DEBUG',
        dest='level',
        help='DEBUG 레벨 로그만 표시'
    )
    
    parser.add_argument(
        '--info',
        action='store_const',
        const='INFO',
        dest='level',
        help='INFO 레벨 로그만 표시'
    )
    
    parser.add_argument(
        '--warning',
        action='store_const',
        const='WARNING',
        dest='level',
        help='WARNING 레벨 로그만 표시'
    )
    
    parser.add_argument(
        '--error',
        action='store_const',
        const='ERROR',
        dest='level',
        help='ERROR 레벨 로그만 표시'
    )
    
    parser.add_argument(
        '--no-follow',
        action='store_false',
        dest='follow',
        help='실시간 모드 비활성화 (파일 전체 읽기)'
    )
    
    parser.add_argument(
        '--log-dir',
        default='logs',
        help='로그 디렉토리 경로 (기본값: logs)'
    )
    
    return parser.parse_args()

def main():
    """메인 함수"""
    args = parse_arguments()
    
    # LogMonitor 인스턴스 생성
    monitor = LogMonitor(log_dir=args.log_dir, follow=args.follow)
    
    # 모니터링 시작
    monitor.monitor(keywords=args.keywords, level=args.level)

if __name__ == "__main__":
    main()