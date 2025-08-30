#!/usr/bin/env python3
"""
Collection Creation Script for HD현대미포 Gauss-1 RAG System
Author: Claude Code
Date: 2025-01-26
Description: 컬렉션 생성 및 초기 설정을 위한 독립 실행 스크립트
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


async def create_collections_with_validation(
    resource_manager, 
    sources: List[str], 
    base_name: str,
    force: bool = False
):
    """컬렉션 생성 및 검증 통합 함수"""
    
    logger.info(f"🏗️ 컬렉션 생성 시작 (소스: {sources})")
    creation_results = {}
    
    # 1단계: 기존 컬렉션 상태 확인
    logger.info("📋 1단계: 기존 컬렉션 상태 확인...")
    existing_status = await resource_manager.startup_vector_dim_check(
        sources=sources,
        base_name=base_name,
        auto_create=False
    )
    
    # 2단계: 생성이 필요한 컬렉션 식별
    collections_to_create = []
    for source in sources:
        collection_info = existing_status["collection_status"].get(source, {})
        if collection_info.get("status") != "ok" or force:
            collections_to_create.append(source)
            if force:
                logger.info(f"🔄 {source} 컬렉션 강제 재생성 예정")
            else:
                logger.info(f"➕ {source} 컬렉션 신규 생성 예정")
        else:
            logger.info(f"✅ {source} 컬렉션 이미 존재")
    
    if not collections_to_create:
        logger.info("✅ 모든 컬렉션이 이미 존재합니다")
        return {"status": "success", "message": "모든 컬렉션이 이미 정상 상태입니다"}
    
    # 3단계: 임베딩 차원 감지
    logger.info("🔢 2단계: 임베딩 차원 감지...")
    embedding_dim = await resource_manager.get_embedding_dim()
    logger.info(f"✅ 감지된 임베딩 차원: {embedding_dim}")
    
    # 4단계: 컬렉션 생성
    logger.info(f"🚀 3단계: 컬렉션 생성 ({len(collections_to_create)}개)...")
    for source in collections_to_create:
        try:
            collection_name = resource_manager.get_default_collection_name(source, base_name)
            logger.info(f"🏗️ '{collection_name}' 생성 중...")
            
            # ResourceManager의 내부 메서드 호출
            await resource_manager._create_collection_with_defaults(
                collection_name=collection_name,
                vector_size=embedding_dim
            )
            
            creation_results[source] = {
                "status": "created",
                "collection_name": collection_name,
                "dimension": embedding_dim
            }
            logger.info(f"✅ '{collection_name}' 생성 완료")
            
        except Exception as e:
            logger.error(f"❌ {source} 컬렉션 생성 실패: {e}")
            creation_results[source] = {
                "status": "failed",
                "error": str(e)
            }
    
    # 5단계: 생성 후 검증
    logger.info("🔍 4단계: 생성 후 검증...")
    final_validation = await resource_manager.startup_vector_dim_check(
        sources=sources,
        base_name=base_name,
        auto_create=False
    )
    
    # 결과 집계
    success_count = sum(1 for r in creation_results.values() if r["status"] == "created")
    total_count = len(creation_results)
    
    overall_status = "success" if success_count == total_count else "partial"
    if success_count == 0:
        overall_status = "failed"
    
    return {
        "status": overall_status,
        "creation_results": creation_results,
        "final_validation": final_validation,
        "summary": {
            "created": success_count,
            "failed": total_count - success_count,
            "total": total_count
        }
    }


async def main():
    """메인 생성 실행 함수"""
    parser = argparse.ArgumentParser(description="Qdrant 컬렉션 생성 스크립트")
    parser.add_argument("--sources", nargs="+", default=["mail", "doc"], help="생성할 소스 타입")
    parser.add_argument("--base-name", default="my_documents", help="기본 컬렉션 이름")
    parser.add_argument("--force", action="store_true", help="기존 컬렉션 강제 재생성")
    parser.add_argument("--verbose", "-v", action="store_true", help="상세 로그 출력")
    parser.add_argument("--dry-run", action="store_true", help="실제 생성하지 않고 계획만 출력")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger.info("🏗️ HD현대미포 Gauss-1 컬렉션 생성 시작...")
    logger.info(f"📋 생성 대상: {args.sources}")
    logger.info(f"🏷️ 기본 컬렉션명: {args.base_name}")
    logger.info(f"🔄 강제 재생성: {'활성화' if args.force else '비활성화'}")
    logger.info(f"🧪 드라이런 모드: {'활성화' if args.dry_run else '비활성화'}")
    
    try:
        # ResourceManager 임포트 및 초기화
        from backend.resource_manager import ResourceManager
        
        logger.info("🎛️ ResourceManager 초기화 중...")
        resource_manager = ResourceManager.from_env()
        
        if args.dry_run:
            logger.info("🧪 드라이런 모드: 실제 생성하지 않습니다")
            
            # 현재 상태만 확인
            result = await resource_manager.startup_vector_dim_check(
                sources=args.sources,
                base_name=args.base_name,
                auto_create=False
            )
            
            print("\n" + "=" * 60)
            print("🧪 드라이런 결과 - 생성 계획")
            print("=" * 60)
            
            collections_to_create = []
            for source in args.sources:
                collection_info = result["collection_status"].get(source, {})
                if collection_info.get("status") != "ok" or args.force:
                    collection_name = resource_manager.get_default_collection_name(source, args.base_name)
                    collections_to_create.append((source, collection_name))
            
            if collections_to_create:
                print(f"📋 생성 예정 컬렉션 ({len(collections_to_create)}개):")
                for source, collection_name in collections_to_create:
                    action = "재생성" if args.force else "신규생성"
                    print(f"  🏗️ {source} → {collection_name} ({action})")
                    
                embedding_dim = await resource_manager.get_embedding_dim()
                print(f"🔢 사용할 임베딩 차원: {embedding_dim}")
            else:
                print("✅ 생성이 필요한 컬렉션이 없습니다")
            
            print("\n실제 생성하려면 --dry-run 옵션을 제거하고 다시 실행하세요")
            sys.exit(0)
        
        # 실제 컬렉션 생성 실행
        result = await create_collections_with_validation(
            resource_manager=resource_manager,
            sources=args.sources,
            base_name=args.base_name,
            force=args.force
        )
        
        # 결과 출력
        print("\n" + "=" * 60)
        print("🏗️ 컬렉션 생성 결과")
        print("=" * 60)
        
        status = result["status"]
        status_icon = "✅" if status == "success" else ("⚠️" if status == "partial" else "❌")
        print(f"{status_icon} 전체 상태: {status.upper()}")
        
        if "summary" in result:
            summary = result["summary"]
            print(f"📊 생성 요약:")
            print(f"  ✅ 성공: {summary['created']}")
            print(f"  ❌ 실패: {summary['failed']}")
            print(f"  📋 전체: {summary['total']}")
        
        if "creation_results" in result:
            print(f"\n📋 컬렉션별 생성 결과:")
            for source, info in result["creation_results"].items():
                creation_status = info["status"]
                status_icon = "✅" if creation_status == "created" else "❌"
                print(f"  {status_icon} {source}:")
                
                if creation_status == "created":
                    print(f"    - 컬렉션명: {info['collection_name']}")
                    print(f"    - 차원: {info['dimension']}")
                    print(f"    - 상태: 생성 완료")
                else:
                    print(f"    - 오류: {info.get('error', '알 수 없는 오류')}")
        
        # 최종 검증 결과
        if "final_validation" in result:
            final_val = result["final_validation"]
            print(f"\n🔍 최종 검증 결과:")
            for source, info in final_val["collection_status"].items():
                status = info["status"]
                status_icon = "✅" if status == "ok" else "❌"
                print(f"  {status_icon} {source}: {status}")
        
        print("\n" + "=" * 60)
        
        # 종료 코드 결정
        if status == "failed":
            print("❌ 컬렉션 생성 실패")
            sys.exit(1)
        elif status == "partial":
            print("⚠️ 일부 컬렉션 생성 실패")
            sys.exit(2)
        else:
            print("✅ 모든 컬렉션 생성 완료")
            sys.exit(0)
            
    except ImportError as e:
        logger.error(f"❌ 모듈 임포트 실패: {e}")
        logger.error("backend 디렉토리가 Python 경로에 있는지 확인하세요")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ 생성 중 오류 발생: {e}")
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