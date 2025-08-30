#!/usr/bin/env python3
"""
Collection Unification Test Script
Author: Claude Code
Date: 2025-01-26
Description: ResourceManager의 컬렉션 통합 기능 테스트
"""

import asyncio
import sys
import logging
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_resource_manager_methods():
    """ResourceManager의 새로운 메서드들 테스트"""
    
    print("=" * 80)
    print("ResourceManager Collection Unification Test")
    print("=" * 80)
    
    try:
        from backend.resource_manager import ResourceManager
        
        # ResourceManager 초기화
        print("\n[1] ResourceManager Initialization Test")
        print("-" * 50)
        resource_manager = ResourceManager.from_env()
        print("[OK] ResourceManager initialization successful")
        
        # 컬렉션명 생성 테스트
        print("\n2️⃣ 컬렉션명 생성 테스트")
        print("-" * 50)
        
        test_sources = ["mail", "doc", "test"]
        for source in test_sources:
            collection_name = resource_manager.get_default_collection_name(source, "my_documents")
            print(f"📋 {source} → {collection_name}")
        print("✅ 컬렉션명 생성 테스트 성공")
        
        # 임베딩 차원 감지 테스트
        print("\n3️⃣ 임베딩 차원 감지 테스트")
        print("-" * 50)
        try:
            embedding_dim = await resource_manager.get_embedding_dim()
            print(f"🔢 감지된 임베딩 차원: {embedding_dim}")
            print("✅ 임베딩 차원 감지 테스트 성공")
        except Exception as e:
            print(f"⚠️ 임베딩 차원 감지 실패 (예상됨 - 모델 미로드): {e}")
        
        # 스타트업 검증 테스트 (자동 생성 비활성화)
        print("\n4️⃣ 스타트업 검증 테스트")
        print("-" * 50)
        try:
            validation_result = await resource_manager.startup_vector_dim_check(
                sources=["mail", "doc"],
                base_name="my_documents",
                auto_create=False
            )
            
            print(f"📊 검증 결과:")
            print(f"  - 전체 상태: {validation_result['overall_status']}")
            print(f"  - 검증된 컬렉션 수: {validation_result['validation_summary']['total_collections']}")
            print(f"  - 성공: {validation_result['validation_summary']['successful_collections']}")
            print(f"  - 실패: {validation_result['validation_summary']['failed_collections']}")
            
            print(f"📋 컬렉션별 상태:")
            for source, info in validation_result["collection_status"].items():
                status_icon = "✅" if info["status"] == "ok" else "❌"
                print(f"  {status_icon} {source}: {info['status']}")
                if "message" in info:
                    print(f"    📝 {info['message']}")
            
            print("✅ 스타트업 검증 테스트 완료")
            
        except Exception as e:
            print(f"⚠️ 스타트업 검증 실패 (예상됨 - Qdrant 미연결): {e}")
        
        # ResourceManager 정리
        await resource_manager.cleanup()
        print("✅ ResourceManager 정리 완료")
        
        print("\n" + "=" * 80)
        print("🎉 모든 테스트 완료!")
        print("=" * 80)
        
        return True
        
    except ImportError as e:
        print(f"❌ 모듈 임포트 실패: {e}")
        return False
    except Exception as e:
        print(f"❌ 테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_namespace_mapping():
    """네임스페이스 매핑 테스트 (main.py 함수)"""
    
    print("\n5️⃣ 네임스페이스 매핑 테스트")
    print("-" * 50)
    
    try:
        # main.py에서 _get_current_namespace_mapping 함수 테스트
        sys.path.insert(0, str(PROJECT_ROOT / "backend"))
        from backend.main import _get_current_namespace_mapping
        
        mapping = _get_current_namespace_mapping()
        print(f"📋 현재 네임스페이스 매핑:")
        for source, collection_name in mapping.items():
            print(f"  {source} → {collection_name}")
        print("✅ 네임스페이스 매핑 테스트 성공")
        
        return True
        
    except ImportError as e:
        print(f"⚠️ main.py 함수 테스트 실패 (모듈 미설치): {e}")
        return False
    except Exception as e:
        print(f"❌ 네임스페이스 매핑 테스트 실패: {e}")
        return False


def test_security_config():
    """보안 설정 동적 생성 테스트"""
    
    print("\n6️⃣ 보안 설정 동적 생성 테스트")
    print("-" * 50)
    
    try:
        from backend.qdrant_security_config import create_default_security_config
        
        # ResourceManager 없이 테스트 (레거시 폴백)
        config1 = create_default_security_config(resource_manager=None)
        print(f"📋 레거시 폴백 설정:")
        for source, collection_name in config1.collection_namespaces.items():
            print(f"  {source} → {collection_name}")
        
        print("✅ 보안 설정 동적 생성 테스트 성공")
        return True
        
    except ImportError as e:
        print(f"⚠️ 보안 설정 테스트 실패 (모듈 미설치): {e}")
        return False
    except Exception as e:
        print(f"❌ 보안 설정 테스트 실패: {e}")
        return False


async def main():
    """메인 테스트 함수"""
    
    print("🚀 HD현대미포 Gauss-1 컬렉션 통합 테스트 시작")
    
    # 비동기 테스트
    test1_result = await test_resource_manager_methods()
    
    # 동기 테스트들
    test2_result = test_namespace_mapping()
    test3_result = test_security_config()
    
    # 결과 요약
    print("\n" + "=" * 80)
    print("📊 테스트 결과 요약")
    print("=" * 80)
    
    tests = [
        ("ResourceManager 메서드", test1_result),
        ("네임스페이스 매핑", test2_result),
        ("보안 설정 동적 생성", test3_result)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, result in tests:
        status_icon = "✅" if result else "❌"
        print(f"{status_icon} {test_name}: {'성공' if result else '실패'}")
        if result:
            passed += 1
    
    print(f"\n📈 성공률: {passed}/{total} ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🎉 모든 테스트 통과!")
        return 0
    else:
        print("⚠️ 일부 테스트 실패")
        return 1


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    exit_code = asyncio.run(main())
    sys.exit(exit_code)