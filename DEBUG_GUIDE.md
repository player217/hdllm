# 백엔드 디버그 가이드

## 📋 개요
메일 검색이 작동하지 않는 문제를 진단하기 위한 상세 로깅 시스템이 구현되었습니다.

## 🚀 빠른 시작

### 1. 디버그 모드로 백엔드 실행

**Windows (CMD/PowerShell):**
```cmd
set RAG_DEBUG=true
set RAG_VERBOSE=true
python backend/main.py
```

**Windows (한 줄):**
```cmd
set RAG_DEBUG=true && set RAG_VERBOSE=true && python backend/main.py
```

**Linux/Mac:**
```bash
RAG_DEBUG=true RAG_VERBOSE=true python backend/main.py
```

### 2. 실시간 로그 모니터링

**모든 로그 보기:**
```cmd
python log_monitor.py
```

**특정 키워드 필터링:**
```cmd
python log_monitor.py 르꼬끄
```

**특정 레벨만 보기:**
```cmd
python log_monitor.py --debug
python log_monitor.py --error
```

### 3. 검색 테스트

**테스트 스크립트 실행:**
```cmd
python test_backend_logging.py
```

**수동 테스트 (curl):**
```bash
curl -X POST http://localhost:8080/ask \
  -H "Content-Type: application/json" \
  -d "{\"question\": \"르꼬끄 패딩 할인 몇퍼센트야?\", \"source\": \"mail\"}"
```

## 📊 로그 레벨 설명

### 환경 변수
- `RAG_DEBUG=true`: DEBUG 레벨 로그 활성화
- `RAG_VERBOSE=true`: 매우 상세한 로그 활성화

### 로그 레벨
- **DEBUG**: 상세한 디버깅 정보 (벡터 차원, 메타데이터 등)
- **INFO**: 주요 이벤트 (검색 시작, 결과 수)
- **WARNING**: 경고 (낮은 점수, 빈 결과)
- **ERROR**: 오류 (연결 실패, 예외)

## 🔍 추가된 로깅 포인트

### 1. 쿼리 처리
- 원본 쿼리와 정규화된 쿼리
- 특수 키워드 감지 ("르꼬끄" 등)
- 쿼리 벡터 차원

### 2. Qdrant 검색
- 각 컬렉션별 검색 시도
- 검색 파라미터 (limit, threshold)
- 각 hit의 점수와 메타데이터 키
- 중복 제거 전/후 결과 수

### 3. 메타데이터 처리
- 사용 가능한 필드 목록
- 누락된 필드 경고
- 필드 값 접근 로그

### 4. 컬렉션 상태
- 시작 시 컬렉션 정보
- 벡터 수와 인덱싱 상태

## 📝 로그 출력 예시

### 정상적인 검색
```
[uuid] 📨 Original Question: 르꼬끄 패딩 할인 몇퍼센트야?
[uuid] 📁 Source: mail
[uuid] 🔍 Special keyword '르꼬끄' detected in query
[uuid] 🔎 Searching collection: 'my_documents'
[uuid] ✅ Found 3 hits in 'my_documents'
[uuid] 📊 Total hits before deduplication: 3
[uuid] 📊 Final top hits selected: 3
[uuid] 🎯 Top 3 후보 문서:
[uuid]   1. Score: 0.8234 | Title: 르꼬끄 패딩 할인 안내
[uuid]      Date: 2024-01-15 | Sender: shop@lecoq.com
```

### 검색 실패
```
[uuid] 🔎 Searching collection: 'my_documents'
[uuid] ⚠️ No hits found in 'my_documents' (threshold: 0.55)
[uuid] ❌ No hits found across all collections
[uuid] ⚠️ No context found for question: 르꼬끄 패딩
```

## 🛠️ 문제 진단 체크리스트

### 1. Qdrant 연결 확인
```python
# 로그에서 확인할 내용
✅ Qdrant 클라이언트들 연결 성공
📊 MAIL Qdrant 컬렉션 상태:
  - Collection 'my_documents': vectors=3, indexed=3
```

### 2. 임베딩 확인
```python
# 로그에서 확인할 내용
Query vector created - dimension: 1024
```

### 3. 검색 결과 확인
```python
# 로그에서 확인할 내용
Found X hits in 'collection_name'
Score: 0.XXXX | Title: XXX
```

### 4. 메타데이터 필드 확인
```python
# 로그에서 확인할 내용
Metadata keys: ['text', 'mail_subject', 'sent_date', 'sender', ...]
```

## 🐛 일반적인 문제와 해결책

### 문제 1: "No hits found"
**원인**: 점수 임계값이 너무 높음
**해결**: `QDRANT_SCORE_THRESHOLD` 값을 낮춤 (예: 0.55 → 0.40)

### 문제 2: "Missing date field"
**원인**: 메타데이터 필드명 불일치
**해결**: 이미 수정됨 (sent_date/date 모두 지원)

### 문제 3: "Collection not found"
**원인**: 컬렉션이 생성되지 않음
**해결**: 메일 임베딩 먼저 실행

## 📂 파일 구조

```
LMM_UI_APP/
├── backend/
│   └── main.py          # 로깅 추가된 백엔드
├── logs/
│   └── rag_log_*.log    # 로그 파일
├── log_monitor.py        # 실시간 로그 모니터
├── test_backend_logging.py  # 테스트 스크립트
└── DEBUG_GUIDE.md        # 이 문서
```

## 💡 팁

1. **두 터미널 사용**: 하나는 백엔드, 하나는 로그 모니터
2. **키워드 필터링**: 특정 문제에 집중
3. **로그 레벨 조정**: 필요한 정보만 표시
4. **테스트 자동화**: test_backend_logging.py 활용

## 🔄 다음 단계

로그를 확인한 후:
1. 정확한 문제 지점 파악
2. 필요시 추가 로깅 포인트 추가
3. 문제 해결 후 로깅 레벨 조정