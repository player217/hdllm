"""
GPU 가속 시스템 테스트 실행기
Author: Claude Code
Date: 2025-01-27
Description: 모든 테스트를 실행하는 메인 스크립트
"""

import asyncio
import subprocess
import sys
import os
import time
import logging
from pathlib import Path

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

def run_python_script(script_path: str, description: str) -> bool:
    """파이썬 스크립트 실행"""
    logger.info(f"🚀 {description}")
    logger.info(f"   Running: {script_path}")
    
    try:
        # 현재 Python 인터프리터로 스크립트 실행
        result = subprocess.run(
            [sys.executable, script_path],
            cwd=Path(__file__).parent,
            capture_output=True,
            text=True,
            timeout=300  # 5분 타임아웃
        )
        
        if result.returncode == 0:
            logger.info(f"✅ {description} - SUCCESS")
            # 성공 시 마지막 몇 라인만 출력
            if result.stdout:
                lines = result.stdout.strip().split('\n')[-5:]
                for line in lines:
                    logger.info(f"   {line}")
            return True
        else:
            logger.error(f"❌ {description} - FAILED (exit code: {result.returncode})")
            if result.stderr:
                logger.error(f"   Error: {result.stderr}")
            if result.stdout:
                logger.info(f"   Output: {result.stdout}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error(f"❌ {description} - TIMEOUT (5 minutes)")
        return False
    except Exception as e:
        logger.error(f"❌ {description} - ERROR: {e}")
        return False

def check_environment():
    """환경 확인"""
    logger.info("🔍 Checking environment...")
    
    # Python 버전 확인
    logger.info(f"   Python: {sys.version}")
    
    # 필요한 디렉토리 존재 확인
    required_dirs = [
        "backend",
        "backend/pipeline", 
        "backend/tests"
    ]
    
    for dir_path in required_dirs:
        if not Path(dir_path).exists():
            logger.error(f"❌ Required directory missing: {dir_path}")
            return False
        logger.info(f"   ✅ {dir_path}")
    
    # 핵심 파일 존재 확인
    required_files = [
        "backend/resource_manager.py",
        "backend/pipeline/async_pipeline.py",
        "backend/pipeline/task_queue.py",
        "backend/tests/test_gpu_acceleration.py"
    ]
    
    for file_path in required_files:
        if not Path(file_path).exists():
            logger.error(f"❌ Required file missing: {file_path}")
            return False
        logger.info(f"   ✅ {file_path}")
    
    return True

def main():
    """메인 테스트 실행 함수"""
    logger.info("="*60)
    logger.info("🧪 GPU ACCELERATION SYSTEM TEST SUITE")
    logger.info("="*60)
    
    start_time = time.time()
    
    # 환경 확인
    if not check_environment():
        logger.error("❌ Environment check failed")
        return 1
    
    # 테스트 스크립트 목록
    test_scripts = [
        {
            "path": "backend/tests/demo_queue_usage.py",
            "description": "Queue System Usage Demo",
            "required": False  # 데모는 선택사항
        },
        {
            "path": "backend/tests/test_gpu_acceleration.py", 
            "description": "GPU Acceleration System Tests",
            "required": True
        },
        {
            "path": "backend/tests/test_api_integration.py",
            "description": "API Integration Tests", 
            "required": False  # API 서버가 실행 중이어야 함
        }
    ]
    
    results = []
    
    for test_script in test_scripts:
        script_path = test_script["path"]
        description = test_script["description"]
        required = test_script["required"]
        
        logger.info("\n" + "-"*50)
        
        if Path(script_path).exists():
            success = run_python_script(script_path, description)
            results.append({
                "script": description,
                "success": success,
                "required": required
            })
        else:
            logger.warning(f"⚠️ Test script not found: {script_path}")
            results.append({
                "script": description,
                "success": False,
                "required": required
            })
        
        # 테스트 간 간격
        time.sleep(2)
    
    # 결과 요약
    total_time = time.time() - start_time
    
    logger.info("\n" + "="*60)
    logger.info("📊 TEST SUITE RESULTS")
    logger.info("="*60)
    
    total_tests = len(results)
    required_tests = [r for r in results if r["required"]]
    optional_tests = [r for r in results if not r["required"]]
    
    required_passed = sum(1 for r in required_tests if r["success"])
    optional_passed = sum(1 for r in optional_tests if r["success"])
    
    for result in results:
        status = "✅ PASS" if result["success"] else "❌ FAIL"
        req_flag = "[REQUIRED]" if result["required"] else "[OPTIONAL]"
        logger.info(f"{status} {result['script']:<35} {req_flag}")
    
    logger.info("-"*60)
    logger.info(f"📈 REQUIRED TESTS: {required_passed}/{len(required_tests)} passed")
    logger.info(f"📈 OPTIONAL TESTS: {optional_passed}/{len(optional_tests)} passed")
    logger.info(f"⏱️  TOTAL TIME: {total_time:.1f} seconds")
    logger.info("="*60)
    
    # 반환값 결정 (필수 테스트가 모두 통과해야 성공)
    all_required_passed = required_passed == len(required_tests)
    
    if all_required_passed:
        logger.info("🎉 All required tests passed!")
        
        if len(optional_tests) > 0:
            if optional_passed == len(optional_tests):
                logger.info("✨ All optional tests also passed!")
            else:
                logger.info(f"ℹ️  {optional_passed}/{len(optional_tests)} optional tests passed")
        
        return 0
    else:
        logger.error("💥 Some required tests failed!")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)