#!/usr/bin/env python3
"""
Collection Validation Script for HD현대미포 Gauss-1 RAG System
Author: Claude Code
Date: 2025-01-26
Description: 컬렉션 존재 및 벡터 차원 검증을 위한 독립 실행 스크립트
"""

import os
import sys
import asyncio
import logging
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional

# 프로젝트 루트를 Python 경로에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """메인 검증 실행 함수"""
    parser = argparse.ArgumentParser(description="Qdrant 컬렉션 검증 스크립트")
    parser.add_argument("--sources", nargs="+", default=["mail", "doc"], help="검증할 소스 타입")
    parser.add_argument("--base-name", default="my_documents", help="기본 컬렉션 이름")
    parser.add_argument("--verbose", "-v", action="store_true", help="상세 로그 출력")
    parser.add_argument("--auto-create", action="store_true", help="누락된 컬렉션 자동 생성")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger.info("🔍 HD현대미포 Gauss-1 컬렉션 검증 시작...")
    logger.info(f"📋 검증 대상: {args.sources}")
    logger.info(f"🏷️ 기본 컬렉션명: {args.base_name}")
    logger.info(f"🔧 자동 생성: {'활성화' if args.auto_create else '비활성화'}")
    
    try:
        # ResourceManager 임포트 및 초기화
        from backend.resource_manager import ResourceManager
        
        logger.info("🎛️ ResourceManager 초기화 중...")
        resource_manager = ResourceManager.from_env()
        
        # 스타트업 검증 실행
        logger.info("🚀 컬렉션 검증 실행...")
        result = await resource_manager.startup_vector_dim_check(
            sources=args.sources,
            base_name=args.base_name,
            auto_create=args.auto_create
        )
        
        # 결과 출력
        print("\n" + "=" * 60)
        print("📊 검증 결과 요약")
        print("=" * 60)
        
        overall_status = result["overall_status"]
        status_icon = "✅" if overall_status == "success" else ("⚠️" if overall_status == "warning" else "❌")
        print(f"{status_icon} 전체 상태: {overall_status.upper()}")
        
        if "embedding_dimension" in result:
            print(f"🔢 임베딩 차원: {result['embedding_dimension']}")
        
        print(f"📈 검증된 컬렉션 수: {result['validation_summary']['total_collections']}")
        print(f"✅ 성공: {result['validation_summary']['successful_collections']}")
        print(f"❌ 실패: {result['validation_summary']['failed_collections']}")
        
        print("\n📋 컬렉션별 상세 결과:")
        for source, info in result["collection_status"].items():
            collection_name = info.get("collection_name", "N/A")
            status = info["status"]
            dimension = info.get("dimension", "N/A")
            vector_count = info.get("vector_count", "N/A")
            
            status_icon = "✅" if status == "ok" else "❌"
            print(f"  {status_icon} {source}:")
            print(f"    - 컬렉션명: {collection_name}")
            print(f"    - 상태: {status}")
            print(f"    - 차원: {dimension}")
            print(f"    - 벡터 수: {vector_count}")
            
            if "message" in info and status != "ok":
                print(f"    - 메시지: {info['message']}")
        
        if result.get("issues"):
            print(f"\n🚨 발견된 문제점 ({len(result['issues'])}개):")
            for i, issue in enumerate(result["issues"], 1):
                print(f"  {i}. {issue}")
        
        if result.get("recommendations"):
            print(f"\n💡 권장사항 ({len(result['recommendations'])}개):")
            for i, rec in enumerate(result["recommendations"], 1):
                print(f"  {i}. {rec}")
        
        print("\n" + "=" * 60)
        
        # 종료 코드 결정
        if overall_status == "error":
            print("❌ 검증 실패 - 시스템 설정을 확인하세요")
            sys.exit(1)
        elif overall_status == "warning":
            print("⚠️ 일부 문제 발견 - 검토 필요")
            sys.exit(2)
        else:
            print("✅ 모든 검증 통과")
            sys.exit(0)
            
    except ImportError as e:
        logger.error(f"❌ 모듈 임포트 실패: {e}")
        logger.error("backend 디렉토리가 Python 경로에 있는지 확인하세요")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ 검증 중 오류 발생: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)
    finally:
        # ResourceManager 정리
        try:
            if 'resource_manager' in locals():
                await resource_manager.cleanup()
                logger.info("🧹 ResourceManager 정리 완료")
        except Exception as cleanup_error:
            logger.warning(f"⚠️ 정리 중 오류: {cleanup_error}")


if __name__ == "__main__":
    if sys.platform == "win32":
        # Windows에서 asyncio 이벤트 루프 정책 설정
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    asyncio.run(main())