"""
Ollama 관리 유틸리티 모듈
공통 Ollama 관리 기능을 제공합니다.
"""

import json
import subprocess
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class OllamaManager:
    """Ollama 서비스 및 모델 관리 클래스"""
    
    def __init__(self, config_path: str = "config.json"):
        """
        Args:
            config_path: config.json 파일 경로
        """
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.default_model = self.get_default_model()
        
    def _load_config(self) -> Dict[str, Any]:
        """config.json 파일 로드"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                logger.warning(f"Config file not found: {self.config_path}")
                return {}
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return {}
    
    def get_default_model(self) -> str:
        """기본 모델명 가져오기"""
        ollama_config = self.config.get('ollama', {})
        return ollama_config.get('default_model', 'gemma3:4b')
    
    def is_ollama_running(self) -> bool:
        """Ollama 서비스 실행 여부 확인"""
        try:
            result = subprocess.run(
                ['ollama', 'list'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def start_ollama_service(self) -> bool:
        """Ollama 서비스 시작"""
        if self.is_ollama_running():
            logger.info("Ollama service is already running")
            return True
            
        try:
            # Windows에서 백그라운드로 실행
            subprocess.Popen(
                ['ollama', 'serve'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            
            # 서비스 시작 대기
            for _ in range(10):
                time.sleep(1)
                if self.is_ollama_running():
                    logger.info("Ollama service started successfully")
                    return True
                    
            logger.error("Ollama service failed to start within timeout")
            return False
            
        except FileNotFoundError:
            logger.error("Ollama command not found. Please install Ollama first.")
            return False
        except Exception as e:
            logger.error(f"Failed to start Ollama service: {e}")
            return False
    
    def is_model_installed(self, model_name: Optional[str] = None) -> bool:
        """모델 설치 여부 확인"""
        model = model_name or self.default_model
        
        try:
            result = subprocess.run(
                ['ollama', 'list'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                return model in result.stdout
            return False
            
        except Exception as e:
            logger.error(f"Failed to check model: {e}")
            return False
    
    def pull_model(self, model_name: Optional[str] = None) -> bool:
        """모델 다운로드"""
        model = model_name or self.default_model
        
        if self.is_model_installed(model):
            logger.info(f"Model {model} is already installed")
            return True
        
        logger.info(f"Pulling model {model}...")
        
        try:
            # 타임아웃 설정 (기본 5분)
            timeout = self.config.get('ollama', {}).get('pull_timeout', 300)
            
            result = subprocess.run(
                ['ollama', 'pull', model],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            if result.returncode == 0:
                logger.info(f"Model {model} pulled successfully")
                return True
            else:
                logger.error(f"Failed to pull model {model}: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"Model pull timed out after {timeout} seconds")
            return False
        except Exception as e:
            logger.error(f"Failed to pull model: {e}")
            return False
    
    def ensure_model_ready(self, model_name: Optional[str] = None) -> bool:
        """모델이 사용 가능한 상태인지 확인하고 준비"""
        model = model_name or self.default_model
        
        # Ollama 서비스 시작
        if not self.start_ollama_service():
            return False
        
        # 자동 다운로드 설정 확인
        auto_pull = self.config.get('ollama', {}).get('auto_pull', True)
        
        # 모델 확인 및 다운로드
        if not self.is_model_installed(model):
            if auto_pull:
                logger.info(f"Model {model} not found, attempting to pull...")
                return self.pull_model(model)
            else:
                logger.warning(f"Model {model} not installed and auto_pull is disabled")
                return False
        
        return True
    
    def list_models(self) -> list:
        """설치된 모델 목록 가져오기"""
        try:
            result = subprocess.run(
                ['ollama', 'list'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                # 첫 번째 줄은 헤더이므로 제외
                if len(lines) > 1:
                    models = []
                    for line in lines[1:]:
                        if line.strip():
                            # 모델명은 첫 번째 컬럼
                            model_name = line.split()[0]
                            models.append(model_name)
                    return models
            return []
            
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return []


# 싱글톤 인스턴스
_manager = None


def get_ollama_manager(config_path: str = "config.json") -> OllamaManager:
    """OllamaManager 싱글톤 인스턴스 가져오기"""
    global _manager
    if _manager is None:
        _manager = OllamaManager(config_path)
    return _manager


# 편의 함수들
def get_default_model() -> str:
    """기본 모델명 가져오기"""
    return get_ollama_manager().get_default_model()


def ensure_model_ready(model_name: Optional[str] = None) -> bool:
    """모델이 사용 가능한 상태인지 확인하고 준비"""
    return get_ollama_manager().ensure_model_ready(model_name)


def start_ollama_with_model() -> bool:
    """Ollama 서비스 시작 및 기본 모델 준비"""
    manager = get_ollama_manager()
    return manager.ensure_model_ready()