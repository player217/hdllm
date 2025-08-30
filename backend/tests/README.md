# GPU 가속 시스템 테스트 스크립트

이 디렉토리에는 GPU 가속 RAG 시스템의 Phase 1-4 구현사항을 검증하기 위한 테스트 스크립트들이 포함되어 있습니다.

## 📁 파일 구조

```
backend/tests/
├── README.md                   # 이 파일
├── test_gpu_acceleration.py    # 핵심 GPU 가속 시스템 테스트
├── test_api_integration.py     # API 엔드포인트 통합 테스트  
└── demo_queue_usage.py         # TaskQueue 사용법 데모
```

## 🚀 빠른 시작

### 1. 모든 테스트 실행

```bash
# 프로젝트 루트에서 실행
python run_tests.py
```

### 2. 개별 테스트 실행

```bash
# GPU 가속 시스템 테스트
python backend/tests/test_gpu_acceleration.py

# 큐 시스템 사용법 데모
python backend/tests/demo_queue_usage.py

# API 통합 테스트 (백엔드 서버가 실행 중일 때)
python backend/tests/test_api_integration.py --url http://127.0.0.1:8080
```

## 📝 테스트 설명

### `test_gpu_acceleration.py`
**Phase 1-4 구현사항 종합 검증**

- ✅ **Phase 1**: Import 경로 수정 확인
- ✅ **Phase 2**: Ollama 클라이언트 통일 테스트
- ✅ **Phase 3**: 네임스페이스 확장 검증
- ✅ **Phase 4**: TaskQueue 기반 진정한 큐 시스템 테스트
- 🚀 **성능 테스트**: GPU 가속 임베딩 벤치마크
- ⚠️ **에러 처리**: DLQ 및 예외 처리 검증

**실행 예제:**
```bash
python backend/tests/test_gpu_acceleration.py
```

**예상 출력:**
```
🚀 Starting GPU Acceleration System Tests
✅ Phase 1: All imports successful
✅ Phase 2: Ollama client unified (st)
✅ Phase 3: Collections - Mail: hdmipo_sungak_dev_mail_documents
✅ Phase 4: Queue system working correctly
📈 SUMMARY: 6/6 tests passed (100.0%)
```

### `demo_queue_usage.py`
**새로운 TaskQueue 시스템 사용법 시연**

- 📤 **기본 큐잉**: 작업을 큐에 추가하고 처리 과정 모니터링
- ⚡ **우선순위 큐잉**: 우선순위별 작업 처리 순서 확인
- 📦 **배치 작업**: 여러 작업을 한번에 큐에 추가
- 👀 **작업 모니터링**: 개별 작업 상태 추적
- ⚠️ **에러 시나리오**: 잘못된 작업 처리 방식 확인

**실행 예제:**
```bash
python backend/tests/demo_queue_usage.py
```

### `test_api_integration.py` 
**API 엔드포인트와 큐 시스템 통합 검증**

- 🏥 **헬스체크**: `/health` 엔드포인트
- 📊 **상태 확인**: `/status` 엔드포인트  
- 💬 **스트리밍 질의응답**: `/ask` 엔드포인트
- 🔄 **큐 통합**: 동시 요청 처리 확인
- ❌ **에러 처리**: API 레벨 예외 처리

**실행 전 준비:**
```bash
# 백엔드 서버 먼저 실행 (별도 터미널)
cd backend
python main.py
```

**실행 예제:**
```bash
python backend/tests/test_api_integration.py
```

## ⚙️ 환경 요구사항

### 필수 의존성
```bash
pip install torch sentence-transformers qdrant-client aiohttp asyncio
```

### 선택적 의존성
```bash
# GPU 가속을 위한 CUDA (권장)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### 환경 변수
```bash
# .env 파일에 설정
EMBED_BACKEND=st                    # st|ollama
EMBED_MODEL=BAAI/bge-m3            # 임베딩 모델
EMBED_DEVICE=auto                  # auto|cpu|cuda:0
QDRANT_NAMESPACE=hdmipo_sungak     # 네임스페이스
QDRANT_ENV=dev                     # dev|staging|prod
```

## 🔧 테스트 구성

### GPU 가속 테스트 설정
```python
# ResourceManager 설정
resource_manager = ResourceManager()
await resource_manager.initialize()

# AsyncPipeline 설정  
pipeline = AsyncPipeline(
    resource_manager=resource_manager,
    max_concurrent=3,        # 워커 수
    max_queue_size=50        # 큐 크기
)
```

### API 테스트 설정
```python
# API 클라이언트 설정
tester = APIIntegrationTester(base_url="http://127.0.0.1:8080")

# 타임아웃 설정
timeout = aiohttp.ClientTimeout(total=30)
```

## 📊 테스트 결과 해석

### 성공 케이스
```
✅ PASS Phase1_ImportFixes        0.023s
✅ PASS Phase2_OllamaClient       2.456s
     └─ Backend: st
✅ PASS Phase3_NamespaceExpansion 0.012s  
     └─ Mail: hdmipo_sungak_dev_mail_documents
✅ PASS Phase4_QueueSystem        8.234s
     └─ Completed: 5
```

### 실패 케이스 디버깅
```
❌ FAIL Phase2_OllamaClient       1.234s
     └─ CUDA not available: No GPU found

❌ FAIL API_Integration          0.567s
     └─ Connection refused: Server not running
```

## 🐛 문제 해결

### GPU 가속 문제
```bash
# CUDA 사용 가능 여부 확인
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"

# CPU로 폴백 실행
export EMBED_DEVICE=cpu
python backend/tests/test_gpu_acceleration.py
```

### 서버 연결 문제
```bash
# 백엔드 서버 실행 확인
curl -X GET "http://127.0.0.1:8080/health"

# 포트 변경
python backend/tests/test_api_integration.py --url http://127.0.0.1:8081
```

### 의존성 문제
```bash
# 누락된 패키지 설치
pip install -r requirements.txt

# 개발 의존성 설치
pip install pytest pytest-asyncio aiohttp
```

## 📈 성능 벤치마크

### 임베딩 성능 기준값

| Device | Batch Size | Texts/Second | Memory Usage |
|--------|-----------|--------------|--------------|
| CPU    | 32        | ~20-30       | ~2GB         |
| GPU    | 64        | ~100-200     | ~4GB         |

### 큐 처리 성능

| Queue Size | Workers | Tasks/Second | Latency |
|-----------|---------|--------------|---------|
| 50        | 2       | ~5-10        | <2s     |
| 100       | 5       | ~15-25       | <1s     |

## 🔄 지속적 통합 (CI)

### GitHub Actions 설정 예제
```yaml
name: GPU Acceleration Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    - run: pip install -r requirements.txt
    - run: python run_tests.py
```

## 📚 추가 자료

- [GPU 가속 구현 가이드](../docs/gpu_acceleration_guide.md)
- [TaskQueue API 문서](../pipeline/task_queue.py)
- [ResourceManager 설정](../resource_manager.py)
- [환경 설정 가이드](../../.env.example)

---

**작성자**: Claude Code  
**최종 수정**: 2025-01-27  
**버전**: 1.0