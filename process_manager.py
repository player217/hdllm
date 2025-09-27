#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
통합 프로세스 관리 클래스
subprocess.Popen과 multiprocessing.Process를 일원화하여 관리
"""

import psutil
import subprocess
import multiprocessing
import signal
import time
import threading
from typing import Dict, Optional, Union, List, Tuple
from pathlib import Path
import logging

# 로깅 설정
logger = logging.getLogger(__name__)

class ProcessManager:
    """통합 프로세스 관리자 - subprocess.Popen과 multiprocessing.Process 통합 관리"""
    
    def __init__(self, cleanup_timeout: float = 5.0):
        self.processes: Dict[str, dict] = {}
        self.cleanup_timeout = cleanup_timeout
        self._lock = threading.RLock()
        
        # 정리해야 할 포트 목록 (기본값)
        self.managed_ports = [8080, 8001, 11434, 6333]
        
        logger.info("ProcessManager initialized")
    
    def register_process(
        self, 
        name: str, 
        process: Union[subprocess.Popen, multiprocessing.Process], 
        pid_file: Optional[str] = None,
        ports: Optional[List[int]] = None
    ) -> bool:
        """
        프로세스 등록 및 추적
        
        Args:
            name: 프로세스 식별 이름
            process: 등록할 프로세스 객체
            pid_file: PID 파일 경로 (선택사항)
            ports: 프로세스가 사용하는 포트 목록
            
        Returns:
            bool: 등록 성공 여부
        """
        with self._lock:
            try:
                proc_type = 'subprocess' if isinstance(process, subprocess.Popen) else 'multiprocessing'
                
                self.processes[name] = {
                    'process': process,
                    'pid_file': pid_file,
                    'type': proc_type,
                    'ports': ports or [],
                    'start_time': time.time()
                }
                
                # PID 가져오기
                try:
                    if proc_type == 'subprocess':
                        pid = process.pid if process.poll() is None else None
                    else:
                        pid = process.pid if process.is_alive() else None
                    self.processes[name]['pid'] = pid
                except:
                    self.processes[name]['pid'] = None
                
                logger.info(f"Registered {proc_type} process '{name}' with PID {pid}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to register process '{name}': {e}")
                return False
    
    def unregister_process(self, name: str) -> bool:
        """프로세스 등록 해제 (종료 없이)"""
        with self._lock:
            if name in self.processes:
                del self.processes[name]
                logger.info(f"Unregistered process '{name}'")
                return True
            return False
    
    def is_process_alive(self, name: str) -> bool:
        """프로세스 생존 상태 확인"""
        with self._lock:
            if name not in self.processes:
                return False
                
            proc_info = self.processes[name]
            process = proc_info['process']
            proc_type = proc_info['type']
            
            try:
                if proc_type == 'subprocess':
                    return process.poll() is None
                else:  # multiprocessing
                    return process.is_alive()
            except:
                return False
    
    def get_process_info(self, name: str) -> Optional[dict]:
        """프로세스 정보 조회"""
        with self._lock:
            if name not in self.processes:
                return None
            return self.processes[name].copy()
    
    def list_processes(self) -> Dict[str, dict]:
        """등록된 모든 프로세스 정보 반환"""
        with self._lock:
            result = {}
            for name, info in self.processes.items():
                result[name] = {
                    'type': info['type'],
                    'pid': info.get('pid'),
                    'alive': self.is_process_alive(name),
                    'start_time': info.get('start_time'),
                    'ports': info.get('ports', [])
                }
            return result
    
    def terminate_process(self, name: str, force_timeout: float = 3.0) -> bool:
        """
        개별 프로세스 정리 (단계적 종료)
        
        Args:
            name: 종료할 프로세스 이름
            force_timeout: 강제 종료 전 대기 시간
            
        Returns:
            bool: 종료 성공 여부
        """
        with self._lock:
            if name not in self.processes:
                logger.warning(f"Process '{name}' not found for termination")
                return True
                
            proc_info = self.processes[name]
            process = proc_info['process']
            proc_type = proc_info['type']
            
            try:
                logger.info(f"Terminating {proc_type} process '{name}'")
                
                if proc_type == 'subprocess':
                    # subprocess.Popen 처리
                    if process.poll() is None:  # 아직 실행 중
                        # 1단계: SIGTERM (정상 종료 요청)
                        process.terminate()
                        logger.debug(f"Sent SIGTERM to '{name}'")
                        
                        try:
                            # 정상 종료 대기
                            process.wait(timeout=force_timeout)
                            logger.info(f"Process '{name}' terminated gracefully")
                        except subprocess.TimeoutExpired:
                            # 2단계: SIGKILL (강제 종료)
                            logger.warning(f"Process '{name}' did not terminate gracefully, forcing kill")
                            process.kill()
                            process.wait(timeout=2)
                            logger.info(f"Process '{name}' force killed")
                            
                else:  # multiprocessing.Process
                    if process.is_alive():
                        # 1단계: terminate()
                        process.terminate()
                        logger.debug(f"Sent terminate signal to '{name}'")
                        
                        # 정상 종료 대기
                        process.join(timeout=force_timeout)
                        
                        if process.is_alive():
                            # 2단계: psutil을 사용한 강제 종료
                            logger.warning(f"Process '{name}' still alive after terminate, force killing")
                            try:
                                psutil_proc = psutil.Process(process.pid)
                                psutil_proc.kill()
                                process.join(timeout=2)
                            except psutil.NoSuchProcess:
                                pass  # 이미 종료됨
                            except Exception as e:
                                logger.error(f"Failed to force kill '{name}': {e}")
                        
                        if not process.is_alive():
                            logger.info(f"Process '{name}' terminated successfully")
                
                # PID 파일 정리
                if proc_info.get('pid_file'):
                    try:
                        Path(proc_info['pid_file']).unlink(missing_ok=True)
                        logger.debug(f"Removed PID file for '{name}'")
                    except Exception as e:
                        logger.warning(f"Failed to remove PID file for '{name}': {e}")
                
                # 프로세스 등록 해제
                del self.processes[name]
                logger.info(f"Successfully terminated and unregistered '{name}'")
                return True
                
            except Exception as e:
                logger.error(f"Failed to terminate process '{name}': {e}")
                # 실패해도 등록에서 제거
                if name in self.processes:
                    del self.processes[name]
                return False
    
    def terminate_all(self, parallel: bool = True, total_timeout: float = 30.0) -> Dict[str, bool]:
        """
        모든 등록된 프로세스 정리 (개선된 타임아웃 처리)
        
        Args:
            parallel: 병렬 종료 여부
            total_timeout: 전체 프로세스 종료 타임아웃 (초)
            
        Returns:
            Dict[str, bool]: 프로세스별 종료 결과
        """
        start_time = time.time()
        
        with self._lock:
            process_names = list(self.processes.keys())
        
        if not process_names:
            logger.info("No processes to terminate")
            return {}
        
        logger.info(f"Terminating {len(process_names)} processes ({'parallel' if parallel else 'sequential'}) with {total_timeout}s timeout")
        
        results = {}
        
        if parallel:
            # 병렬 종료 (개선된 타임아웃 처리)
            import concurrent.futures
            
            def terminate_single(name):
                try:
                    return name, self.terminate_process(name, force_timeout=3.0)
                except Exception as e:
                    logger.error(f"Exception terminating '{name}': {e}")
                    return name, False
            
            # 각 프로세스별 최대 대기 시간 계산
            per_process_timeout = min(total_timeout / len(process_names), 10.0)
            
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                    future_to_name = {
                        executor.submit(terminate_single, name): name 
                        for name in process_names
                    }
                    
                    # 전체 타임아웃으로 제한
                    remaining_timeout = total_timeout - (time.time() - start_time)
                    
                    for future in concurrent.futures.as_completed(future_to_name, timeout=max(remaining_timeout, 1.0)):
                        try:
                            name, success = future.result(timeout=1.0)
                            results[name] = success
                            logger.debug(f"Process '{name}' termination: {'success' if success else 'failed'}")
                        except concurrent.futures.TimeoutError:
                            name = future_to_name[future]
                            logger.warning(f"Timeout during termination of '{name}'")
                            results[name] = False
                        except Exception as e:
                            name = future_to_name[future]
                            logger.error(f"Exception during termination of '{name}': {e}")
                            results[name] = False
                        
                        # 전체 타임아웃 체크
                        if time.time() - start_time > total_timeout:
                            logger.warning(f"Total timeout {total_timeout}s exceeded, aborting remaining terminations")
                            break
                    
                    # 미완료 future들 처리
                    for future in future_to_name:
                        if not future.done():
                            name = future_to_name[future]
                            future.cancel()
                            results[name] = False
                            logger.warning(f"Cancelled termination of '{name}' due to timeout")
                            
            except concurrent.futures.TimeoutError:
                logger.warning(f"Parallel termination timed out after {total_timeout}s")
                # 미처리된 프로세스들을 실패로 표시
                for name in process_names:
                    if name not in results:
                        results[name] = False
                        
        else:
            # 순차 종료 (타임아웃 체크 포함)
            per_process_timeout = min(total_timeout / len(process_names), 5.0)
            
            for name in process_names:
                if time.time() - start_time > total_timeout:
                    logger.warning(f"Total timeout {total_timeout}s exceeded, skipping '{name}'")
                    results[name] = False
                    continue
                    
                results[name] = self.terminate_process(name, force_timeout=per_process_timeout)
        
        # 추가 안전망: 포트 기반 정리 (남은 시간이 있을 때만)
        elapsed = time.time() - start_time
        if elapsed < total_timeout:
            try:
                cleaned_count = self._cleanup_by_ports()
                if cleaned_count > 0:
                    logger.info(f"Port-based cleanup removed {cleaned_count} additional processes")
            except Exception as e:
                logger.error(f"Port-based cleanup failed: {e}")
        
        success_count = sum(1 for success in results.values() if success)
        total_elapsed = time.time() - start_time
        logger.info(f"Termination complete: {success_count}/{len(results)} processes terminated in {total_elapsed:.1f}s")
        
        return results
    
    def _cleanup_by_ports(self) -> int:
        """
        포트 기반 잔존 프로세스 정리 (안전망)
        
        Returns:
            int: 정리된 프로세스 수
        """
        cleaned_count = 0
        
        try:
            for port in self.managed_ports:
                for conn in psutil.net_connections(kind="inet"):
                    if (conn.laddr and conn.laddr.port == port and 
                        conn.status == psutil.CONN_LISTEN):
                        try:
                            process = psutil.Process(conn.pid)
                            logger.info(f"Cleaning up residual process on port {port}: PID {conn.pid}")
                            
                            # 정상 종료 시도
                            process.terminate()
                            time.sleep(0.5)
                            
                            # 강제 종료 확인
                            if process.is_running():
                                process.kill()
                                time.sleep(0.2)
                            
                            cleaned_count += 1
                            
                        except psutil.NoSuchProcess:
                            pass  # 이미 종료됨
                        except psutil.AccessDenied:
                            logger.warning(f"Access denied when cleaning PID {conn.pid} on port {port}")
                        except Exception as e:
                            logger.error(f"Error cleaning process on port {port}: {e}")
                            
        except Exception as e:
            logger.error(f"Error during port-based cleanup: {e}")
        
        if cleaned_count > 0:
            logger.info(f"Port-based cleanup: removed {cleaned_count} residual processes")
        
        return cleaned_count
    
    def add_managed_port(self, port: int):
        """관리할 포트 추가"""
        if port not in self.managed_ports:
            self.managed_ports.append(port)
            logger.debug(f"Added port {port} to managed ports")
    
    def remove_managed_port(self, port: int):
        """관리할 포트 제거"""
        if port in self.managed_ports:
            self.managed_ports.remove(port)
            logger.debug(f"Removed port {port} from managed ports")
    
    def health_check(self) -> Dict[str, any]:
        """프로세스 매니저 상태 확인"""
        with self._lock:
            total_processes = len(self.processes)
            alive_processes = sum(1 for name in self.processes if self.is_process_alive(name))
            
            return {
                'total_registered': total_processes,
                'alive_count': alive_processes,
                'dead_count': total_processes - alive_processes,
                'managed_ports': self.managed_ports.copy(),
                'processes': self.list_processes()
            }
    
    def __del__(self):
        """소멸자 - 모든 프로세스 정리"""
        try:
            if hasattr(self, 'processes') and self.processes:
                logger.warning("ProcessManager is being destroyed with active processes - cleaning up")
                self.terminate_all(parallel=False, total_timeout=10.0)
        except:
            pass  # 소멸자에서는 예외 무시


# 전역 프로세스 매니저 인스턴스
_global_process_manager = None

def get_process_manager() -> ProcessManager:
    """전역 프로세스 매니저 인스턴스 반환"""
    global _global_process_manager
    if _global_process_manager is None:
        _global_process_manager = ProcessManager()
    return _global_process_manager


# 편의 함수들
def register_process(name: str, process: Union[subprocess.Popen, multiprocessing.Process], **kwargs) -> bool:
    """전역 매니저에 프로세스 등록"""
    return get_process_manager().register_process(name, process, **kwargs)

def terminate_process(name: str) -> bool:
    """전역 매니저에서 프로세스 종료"""
    return get_process_manager().terminate_process(name)

def terminate_all_processes(parallel: bool = True) -> Dict[str, bool]:
    """전역 매니저의 모든 프로세스 종료"""
    return get_process_manager().terminate_all(parallel)

def is_process_alive(name: str) -> bool:
    """전역 매니저에서 프로세스 상태 확인"""
    return get_process_manager().is_process_alive(name)

def list_all_processes() -> Dict[str, dict]:
    """전역 매니저의 모든 프로세스 목록"""
    return get_process_manager().list_processes()


if __name__ == "__main__":
    # 테스트 코드
    import sys
    import tempfile
    
    logging.basicConfig(level=logging.DEBUG)
    
    manager = ProcessManager()
    
    # 테스트용 subprocess 시작
    test_proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    manager.register_process("test_subprocess", test_proc)
    
    print("Registered processes:", manager.list_processes())
    print("Health check:", manager.health_check())
    
    # 정리
    results = manager.terminate_all()
    print("Termination results:", results)