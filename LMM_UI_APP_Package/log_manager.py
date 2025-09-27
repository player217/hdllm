#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
로그 관리 시스템 클래스
자동 로그 로테이션, 정리, 압축 기능 제공
"""

import logging
import logging.handlers
import os
import glob
import time
import threading
import gzip
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict

class LogManager:
    """통합 로그 관리 시스템 - 로테이션, 정리, 압축"""
    
    def __init__(self, log_dir: Path, max_file_size_mb: int = 10, backup_count: int = 5, max_age_days: int = 30):
        """
        로그 매니저 초기화
        
        Args:
            log_dir: 로그 디렉토리 경로
            max_file_size_mb: 로그 파일 최대 크기 (MB)
            backup_count: 보관할 백업 파일 수
            max_age_days: 로그 파일 보관 기간 (일)
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True, parents=True)
        
        self.max_file_size = max_file_size_mb * 1024 * 1024  # MB to bytes
        self.backup_count = backup_count
        self.max_age_days = max_age_days
        self.compress_old_logs = True
        
        # 로거 레지스트리
        self._loggers: Dict[str, logging.Logger] = {}
        self._handlers: Dict[str, logging.Handler] = {}
        
        # 정리 스케줄러 설정
        self._cleanup_thread = None
        self._stop_cleanup = threading.Event()
        
        # 기본 로그 포맷
        self.default_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 상세 로그 포맷 (디버그용)
        self.detailed_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        print(f"LogManager initialized: {self.log_dir}, max_size={max_file_size_mb}MB, backups={backup_count}, max_age={max_age_days}days")
    
    def get_logger(
        self, 
        name: str, 
        level: int = logging.INFO, 
        rotation_type: str = "size",
        detailed: bool = False,
        console_output: bool = False
    ) -> logging.Logger:
        """
        로거 생성 또는 기존 로거 반환
        
        Args:
            name: 로거 이름 (파일명으로도 사용)
            level: 로그 레벨
            rotation_type: 로테이션 타입 ("size", "time")
            detailed: 상세 포맷 사용 여부
            console_output: 콘솔 출력 여부
            
        Returns:
            logging.Logger: 설정된 로거
        """
        if name in self._loggers:
            return self._loggers[name]
        
        logger = logging.getLogger(f"tt.{name}")
        logger.setLevel(level)
        
        # 기존 핸들러 제거 (중복 방지)
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # 파일 핸들러 생성
        log_file = self.log_dir / f"{name}.log"
        
        if rotation_type == "size":
            handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=self.max_file_size,
                backupCount=self.backup_count,
                encoding='utf-8'
            )
        else:  # time-based rotation
            handler = logging.handlers.TimedRotatingFileHandler(
                log_file,
                when='midnight',
                interval=1,
                backupCount=self.max_age_days,
                encoding='utf-8'
            )
        
        # 포맷터 설정
        formatter = self.detailed_format if detailed else self.default_format
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        # 콘솔 핸들러 추가 (옵션)
        if console_output:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            console_handler.setLevel(logging.WARNING)  # 콘솔에는 경고 이상만
            logger.addHandler(console_handler)
        
        # 로거 등록
        self._loggers[name] = logger
        self._handlers[name] = handler
        
        logger.info(f"Logger '{name}' initialized with {rotation_type} rotation")
        return logger
    
    def setup_uvicorn_logging(self, level: int = logging.WARNING):
        """Uvicorn 로깅 설정 - health check 로그 노이즈 제거"""
        # Uvicorn access 로그 필터링
        uvicorn_access = logging.getLogger("uvicorn.access")
        uvicorn_access.setLevel(level)
        
        # Health check 요청 필터
        class HealthCheckFilter(logging.Filter):
            def filter(self, record):
                # /health 엔드포인트 요청은 필터링
                if hasattr(record, 'getMessage'):
                    message = record.getMessage()
                    if '/health' in message and 'GET' in message:
                        return False
                return True
        
        # 필터 적용
        for handler in uvicorn_access.handlers:
            handler.addFilter(HealthCheckFilter())
        
        print(f"Uvicorn logging configured with level {logging.getLevelName(level)}")
    
    def compress_old_logs(self, pattern: str = "*.log.*"):
        """오래된 로그 파일 압축"""
        compressed_count = 0
        
        for log_file in self.log_dir.glob(pattern):
            # 이미 압축된 파일은 스킵
            if log_file.suffix == '.gz':
                continue
                
            # 숫자로 끝나는 백업 파일만 압축 (예: app.log.1, app.log.2)
            if log_file.suffix.isdigit() or log_file.name.count('.') >= 2:
                try:
                    gz_file = log_file.with_suffix(log_file.suffix + '.gz')
                    
                    with open(log_file, 'rb') as f_in:
                        with gzip.open(gz_file, 'wb') as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    
                    # 원본 파일 삭제
                    log_file.unlink()
                    compressed_count += 1
                    print(f"Compressed: {log_file.name} -> {gz_file.name}")
                    
                except Exception as e:
                    print(f"Failed to compress {log_file}: {e}")
        
        if compressed_count > 0:
            print(f"Compressed {compressed_count} log files")
        
        return compressed_count
    
    def cleanup_old_logs(self, force: bool = False) -> Dict[str, int]:
        """
        오래된 로그 파일 정리
        
        Args:
            force: 강제 정리 (나이 무관하게 백업 수 초과 시 삭제)
            
        Returns:
            Dict[str, int]: 정리 통계 {'deleted': count, 'compressed': count, 'total_size_mb': size}
        """
        stats = {'deleted': 0, 'compressed': 0, 'total_size_freed_mb': 0}
        cutoff_time = time.time() - (self.max_age_days * 24 * 3600)
        
        try:
            # 압축 먼저 실행
            stats['compressed'] = self.compress_old_logs()
            
            # 로그 파일 패턴 목록
            patterns = ["*.log.*", "*.log*.gz", "audit_*.log", "rag_log_*.log"]
            
            for pattern in patterns:
                for log_file in self.log_dir.glob(pattern):
                    should_delete = False
                    file_size_mb = log_file.stat().st_size / (1024 * 1024)
                    
                    if force:
                        # 강제 모드: 백업 수 초과 시 삭제
                        should_delete = True
                    else:
                        # 나이 기준 삭제
                        file_age = os.path.getmtime(log_file)
                        if file_age < cutoff_time:
                            should_delete = True
                    
                    if should_delete:
                        try:
                            log_file.unlink()
                            stats['deleted'] += 1
                            stats['total_size_freed_mb'] += file_size_mb
                            print(f"Deleted old log: {log_file.name} ({file_size_mb:.2f}MB)")
                            
                        except Exception as e:
                            print(f"Failed to delete {log_file}: {e}")
            
            # 결과 요약
            if stats['deleted'] > 0 or stats['compressed'] > 0:
                print(f"Log cleanup completed: deleted={stats['deleted']}, compressed={stats['compressed']}, freed={stats['total_size_freed_mb']:.2f}MB")
            
        except Exception as e:
            print(f"Error during log cleanup: {e}")
        
        return stats
    
    def get_log_stats(self) -> Dict[str, any]:
        """로그 디렉토리 통계"""
        stats = {
            'total_files': 0,
            'total_size_mb': 0,
            'by_extension': {},
            'largest_files': [],
            'oldest_file': None,
            'newest_file': None
        }
        
        try:
            files_info = []
            
            for log_file in self.log_dir.iterdir():
                if log_file.is_file():
                    file_stat = log_file.stat()
                    size_mb = file_stat.st_size / (1024 * 1024)
                    
                    stats['total_files'] += 1
                    stats['total_size_mb'] += size_mb
                    
                    # 확장자별 통계
                    ext = log_file.suffix or 'no_ext'
                    if ext not in stats['by_extension']:
                        stats['by_extension'][ext] = {'count': 0, 'size_mb': 0}
                    stats['by_extension'][ext]['count'] += 1
                    stats['by_extension'][ext]['size_mb'] += size_mb
                    
                    # 파일 정보 수집
                    files_info.append({
                        'name': log_file.name,
                        'size_mb': size_mb,
                        'modified': file_stat.st_mtime
                    })
            
            # 가장 큰 파일들 (상위 5개)
            stats['largest_files'] = sorted(files_info, key=lambda x: x['size_mb'], reverse=True)[:5]
            
            # 가장 오래된/새로운 파일
            if files_info:
                stats['oldest_file'] = min(files_info, key=lambda x: x['modified'])
                stats['newest_file'] = max(files_info, key=lambda x: x['modified'])
            
            # 소수점 둘째자리까지
            stats['total_size_mb'] = round(stats['total_size_mb'], 2)
            for ext_stats in stats['by_extension'].values():
                ext_stats['size_mb'] = round(ext_stats['size_mb'], 2)
                
        except Exception as e:
            print(f"Error collecting log stats: {e}")
        
        return stats
    
    def start_cleanup_scheduler(self, cleanup_hour: int = 2):
        """
        로그 정리 스케줄러 시작 (매일 지정된 시간에 실행)
        
        Args:
            cleanup_hour: 정리 실행 시간 (24시간 형식, 기본값: 2 = 오전 2시)
        """
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            print("Cleanup scheduler is already running")
            return
        
        def cleanup_worker():
            """정리 작업 스레드"""
            while not self._stop_cleanup.is_set():
                now = datetime.now()
                
                # 다음 정리 시간 계산
                next_cleanup = now.replace(hour=cleanup_hour, minute=0, second=0, microsecond=0)
                if now >= next_cleanup:
                    next_cleanup += timedelta(days=1)
                
                wait_seconds = (next_cleanup - now).total_seconds()
                print(f"Next log cleanup scheduled for: {next_cleanup.strftime('%Y-%m-%d %H:%M:%S')} (in {wait_seconds/3600:.1f} hours)")
                
                # 대기 (종료 신호 확인)
                if self._stop_cleanup.wait(timeout=wait_seconds):
                    break  # 종료 신호 받음
                
                # 정리 실행
                try:
                    print(f"Starting scheduled log cleanup at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    stats = self.cleanup_old_logs()
                    
                    # 통계 로깅
                    if stats['deleted'] > 0 or stats['compressed'] > 0:
                        logger = self.get_logger('log_manager')
                        logger.info(f"Scheduled cleanup completed: {stats}")
                    
                except Exception as e:
                    print(f"Error during scheduled cleanup: {e}")
        
        # 스케줄러 스레드 시작
        self._cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        self._cleanup_thread.start()
        print(f"Log cleanup scheduler started (daily at {cleanup_hour:02d}:00)")
    
    def stop_cleanup_scheduler(self):
        """로그 정리 스케줄러 중지"""
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._stop_cleanup.set()
            self._cleanup_thread.join(timeout=2)
            print("Log cleanup scheduler stopped")
    
    def force_rotate_all(self):
        """모든 등록된 로거의 로그 파일을 강제 로테이션"""
        rotated_count = 0
        
        for name, handler in self._handlers.items():
            try:
                if isinstance(handler, logging.handlers.RotatingFileHandler):
                    handler.doRollover()
                    rotated_count += 1
                    print(f"Force rotated log: {name}")
                    
            except Exception as e:
                print(f"Failed to rotate {name}: {e}")
        
        print(f"Force rotated {rotated_count} log files")
        return rotated_count
    
    def close_all_loggers(self):
        """모든 로거 핸들러 종료"""
        for logger in self._loggers.values():
            for handler in logger.handlers[:]:
                try:
                    handler.close()
                    logger.removeHandler(handler)
                except:
                    pass
        
        self._loggers.clear()
        self._handlers.clear()
        print("All loggers closed")
    
    def __del__(self):
        """소멸자 - 정리 작업"""
        try:
            self.stop_cleanup_scheduler()
            self.close_all_loggers()
        except:
            pass


# 전역 로그 매니저 인스턴스
_global_log_manager = None

def get_log_manager(log_dir: str = "logs") -> LogManager:
    """전역 로그 매니저 인스턴스 반환"""
    global _global_log_manager
    if _global_log_manager is None:
        _global_log_manager = LogManager(Path(log_dir))
    return _global_log_manager


# 편의 함수들
def get_logger(name: str, **kwargs) -> logging.Logger:
    """전역 매니저에서 로거 생성/반환"""
    return get_log_manager().get_logger(name, **kwargs)

def setup_backend_logging(level: int = logging.INFO):
    """백엔드 전용 로깅 설정"""
    manager = get_log_manager()
    
    # 백엔드 로거 설정
    backend_logger = manager.get_logger('backend', level=level, detailed=False)
    
    # Uvicorn 로깅 설정 (health check 노이즈 제거)
    manager.setup_uvicorn_logging(level=logging.WARNING)
    
    # 정리 스케줄러 시작 (오전 3시)
    manager.start_cleanup_scheduler(cleanup_hour=3)
    
    return backend_logger

def setup_tray_logging(level: int = logging.INFO):
    """트레이 런처 전용 로깅 설정"""
    manager = get_log_manager()
    
    loggers = {}
    for name in ['updater', 'backend', 'frontend', 'qdrant', 'ollama']:
        loggers[name] = manager.get_logger(name, level=level, rotation_type='size')
    
    # 정리 스케줄러 시작 (오전 2시)
    manager.start_cleanup_scheduler(cleanup_hour=2)
    
    return loggers

def cleanup_logs_now():
    """즉시 로그 정리 실행"""
    return get_log_manager().cleanup_old_logs()

def get_log_statistics():
    """로그 통계 조회"""
    return get_log_manager().get_log_stats()


if __name__ == "__main__":
    # 테스트 코드
    import tempfile
    import sys
    
    # 임시 디렉토리로 테스트
    with tempfile.TemporaryDirectory() as temp_dir:
        manager = LogManager(Path(temp_dir))
        
        # 테스트 로거 생성
        logger = manager.get_logger('test', console_output=True)
        
        # 테스트 로그 작성
        logger.info("Test log message")
        logger.warning("Test warning")
        logger.error("Test error")
        
        # 통계 출력
        print("Log statistics:", manager.get_log_stats())
        
        # 정리 테스트
        cleanup_stats = manager.cleanup_old_logs(force=True)
        print("Cleanup stats:", cleanup_stats)