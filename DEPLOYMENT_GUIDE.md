# HD현대미포 Gauss-1 RAG System - 배포 가이드

## 🚀 원클릭 설치 및 실행 가이드

### 📋 시스템 요구사항

#### 최소 사양
- **OS**: Windows 10/11 (64-bit)
- **RAM**: 8GB 이상
- **저장공간**: 20GB 이상 여유 공간
- **CPU**: 4코어 이상
- **네트워크**: 인터넷 연결 (초기 설치 시)

#### 권장 사양
- **RAM**: 16GB 이상
- **저장공간**: 50GB 이상 여유 공간
- **CPU**: 8코어 이상
- **GPU**: CUDA 지원 GPU (선택사항)

### 🎯 빠른 시작 (2-Click Installation)

#### Step 1: 설치 (처음 한 번만)
```batch
INSTALL_ENHANCED.bat
```
- Python 3.11 자동 설치
- Qdrant 벡터 DB 다운로드
- Ollama LLM 서버 설치
- BGE-M3 임베딩 모델 다운로드
- 모든 Python 패키지 설치
- 환경 설정 파일 생성

**예상 시간**: 15-30분 (인터넷 속도에 따라 다름)

#### Step 2: 실행
```batch
RUN_ENHANCED.bat
```
- 모든 서비스 자동 시작
- 브라우저 자동 열기
- http://localhost:8001 접속

### 📂 프로젝트 구조

```
LMM_UI_APP/
├── INSTALL_ENHANCED.bat    # 원클릭 설치 스크립트
├── RUN_ENHANCED.bat        # 원클릭 실행 스크립트
├── .env.template          # 환경 설정 템플릿
├── .env                   # 실제 환경 설정 (자동 생성)
├── backend/               # FastAPI 백엔드
├── frontend/              # 웹 UI
├── src/                   # GUI 및 코어 모듈
├── bin/                   # 다운로드된 실행 파일
│   ├── qdrant.exe        # Qdrant 벡터 DB
│   ├── bge-m3-local/     # BGE-M3 모델
│   └── OllamaSetup.exe   # Ollama 설치 파일
├── storage/               # 데이터 저장소
└── venv/                  # Python 가상환경
```

### 🔧 환경 설정

#### 1. 기본 설정 (자동 생성됨)
`.env` 파일이 자동으로 생성되며 기본값이 설정됩니다.

#### 2. 데이터 소스 설정
```env
# 개인 Qdrant (로컬 PC)
QDRANT_PERSONAL_HOST=127.0.0.1
QDRANT_PERSONAL_PORT=6333

# 부서 Qdrant (원격 서버)
QDRANT_DEPT_HOST=10.150.104.37
QDRANT_DEPT_PORT=6333

# 기본 선택 (personal 또는 dept)
DEFAULT_DB_SCOPE=personal
```

#### 3. 고급 설정
`.env.template` 파일을 참고하여 필요한 설정을 변경할 수 있습니다.

### 🖥️ 사용 방법

#### 웹 인터페이스
1. 브라우저에서 http://localhost:8001 접속
2. 우측 상단 토글로 데이터 소스 선택 (개인/부서)
3. 질문 입력 후 전송
4. 실시간 스트리밍 응답 확인

#### GUI 애플리케이션
1. 시스템 트레이에서 LLMPY Vector Studio 아이콘 확인
2. 우클릭하여 메뉴 접근
3. 문서 임베딩, 메일 임베딩 등 기능 사용

### 🔄 데이터 소스 전환

#### 웹 UI에서 전환
```javascript
// 우측 상단 토글 버튼으로 전환
// 개인 DB ↔ 부서 DB
```

#### API 직접 호출
```bash
# 헤더로 지정
curl -X POST http://localhost:8080/ask \
  -H "X-Qdrant-Scope: dept" \
  -H "Content-Type: application/json" \
  -d '{"question": "질문 내용"}'

# 쿼리 파라미터로 지정
curl -X POST "http://localhost:8080/ask?db_scope=personal" \
  -H "Content-Type: application/json" \
  -d '{"question": "질문 내용"}'
```

### 📊 서비스 상태 확인

#### 전체 상태 확인
```bash
curl http://localhost:8080/status
```

응답 예시:
```json
{
  "status": "healthy",
  "components": {
    "qdrant_personal": {
      "status": "up",
      "collections": ["personal_prod_mail_my_documents"],
      "vector_count": 1234
    },
    "qdrant_dept": {
      "status": "up",
      "collections": ["dept_prod_mail_my_documents"],
      "vector_count": 5678
    },
    "ollama": {
      "status": "up",
      "models": ["gemma:3b"]
    }
  }
}
```

### 🛠️ 문제 해결

#### 설치 실패 시
1. 관리자 권한으로 실행
2. Windows Defender 예외 추가
3. 수동 설치:
   - Python: https://www.python.org/downloads/
   - Ollama: https://ollama.com/download

#### 포트 충돌
```batch
# 사용 중인 포트 확인
netstat -an | findstr :6333
netstat -an | findstr :8080
netstat -an | findstr :11434

# 프로세스 종료
taskkill /F /PID [프로세스ID]
```

#### Qdrant 연결 실패
1. 방화벽 설정 확인
2. `.env` 파일의 호스트/포트 확인
3. Qdrant 서비스 재시작

#### Ollama 모델 오류
```batch
# 모델 수동 다운로드
ollama pull gemma:3b

# 모델 목록 확인
ollama list
```

### 🔒 보안 고려사항

#### 네트워크 보안
- 기본적으로 localhost만 허용
- 외부 접근 필요 시 방화벽 규칙 추가
- HTTPS 설정 권장 (프로덕션)

#### 데이터 보안
- PII 정보 자동 마스킹
- 로컬 저장소 암호화 권장
- 정기적인 백업 수행

#### 접근 제어
- API 키 설정 가능
- JWT 토큰 지원 (선택사항)
- Rate limiting 활성화

### 📈 성능 최적화

#### GPU 가속 활용
```env
# .env 파일에서 설정
EMBED_DEVICE=cuda  # GPU 사용
EMBED_BATCH=64     # 배치 크기 증가
```

#### 메모리 최적화
```env
# 캐시 크기 조정
EMBED_CACHE_MAX=1024  # 캐시 확대
QDRANT_HNSW_EF=256   # 검색 정확도 향상
```

#### 동시 처리 증가
```env
OLLAMA_MAX_CONCURRENCY=16  # 동시 요청 처리
```

### 🔄 업데이트 방법

#### 코드 업데이트
```batch
git pull origin main
pip install -r requirements.txt --upgrade
```

#### 모델 업데이트
```batch
# Ollama 모델 업데이트
ollama pull gemma:3b

# 임베딩 모델 재다운로드
python -c "from sentence_transformers import SentenceTransformer; model = SentenceTransformer('BAAI/bge-m3'); model.save('bin/bge-m3-local')"
```

### 📞 지원 및 문의

#### 내부 지원
- 담당부서: HD현대미포 선각기술부
- 내선: [내부 연락처]
- 이메일: [내부 이메일]

#### 기술 문서
- API 문서: http://localhost:8080/docs
- 시스템 로그: `logs/` 디렉토리
- 설정 파일: `.env`, `config.json`

### 🎓 사용자 교육

#### 기본 사용법 (30분)
1. 시스템 접속 방법
2. 질문 입력 요령
3. 데이터 소스 선택
4. 결과 해석 방법

#### 고급 기능 (1시간)
1. 문서 임베딩 방법
2. 메일 데이터 처리
3. API 직접 사용
4. 성능 튜닝

### 📝 체크리스트

#### 설치 전
- [ ] Windows 10/11 64-bit 확인
- [ ] 8GB 이상 RAM 확인
- [ ] 20GB 이상 저장공간 확인
- [ ] 인터넷 연결 확인

#### 설치 후
- [ ] Python 3.11 설치 확인
- [ ] Qdrant 실행 확인
- [ ] Ollama 실행 확인
- [ ] 웹 UI 접속 확인

#### 운영 중
- [ ] 일일 상태 점검
- [ ] 주간 로그 검토
- [ ] 월간 성능 분석
- [ ] 분기별 업데이트

---

## 부록: 명령어 참조

### 서비스 시작/중지
```batch
# 개별 서비스 시작
start "Qdrant" cmd /k "bin\qdrant.exe"
start "Ollama" cmd /k "ollama serve"
start "Backend" cmd /k "venv\Scripts\python.exe -m uvicorn backend.main:app --port 8080"
start "Frontend" cmd /k "cd frontend && ..\venv\Scripts\python.exe -m http.server 8001"

# 서비스 중지
taskkill /F /FI "WINDOWTITLE eq Qdrant*"
taskkill /F /FI "WINDOWTITLE eq Ollama*"
taskkill /F /FI "WINDOWTITLE eq Backend*"
taskkill /F /FI "WINDOWTITLE eq Frontend*"
```

### 로그 확인
```batch
# 백엔드 로그
type backend\logs\app.log

# 실시간 로그 모니터링
powershell Get-Content backend\logs\app.log -Wait
```

### 데이터 관리
```batch
# Qdrant 데이터 백업
xcopy /E /I storage\qdrant storage\backup\qdrant_%date%

# 캐시 정리
del /Q logs\*.log
del /Q chunk_outputs\*
```

## 🔄 네임스페이스 호환 모드 (Compatibility Mode)

### 개요

네임스페이스 호환 모드는 기존 벡터 컬렉션과의 호환성을 보장하기 위해 설계된 기능입니다. 새로운 네임스페이스 패턴으로 업그레이드된 시스템이 기존의 레거시 컬렉션 이름을 자동으로 감지하고 사용할 수 있도록 지원합니다.

### 작동 원리

1. **주 네임스페이스 확인**: 먼저 새로운 패턴의 네임스페이스를 확인합니다
   - 예: `personal_dev_mail_my_documents`, `dept_prod_doc_my_documents`

2. **레거시 컬렉션 폴백**: 주 네임스페이스가 존재하지 않거나 비어있을 경우, 자동으로 레거시 컬렉션을 검색합니다
   - `mail_my_documents`
   - `doc_my_documents` 
   - `my_documents`

3. **투명한 전환**: 사용자에게는 투명하게 작동하며, 필요시 토스트 알림으로 상태를 안내합니다

### 설정 옵션

#### .env 파일 설정
```env
# 호환성 모드 활성화
NAMESPACE_COMPAT_ENABLED=true

# 폴백 컬렉션 이름 목록 (우선순위 순)
NAMESPACE_COMPAT_FALLBACK=mail_my_documents,doc_my_documents,my_documents

# 자동 마이그레이션 (선택사항)
AUTO_MIGRATE_COLLECTIONS=false
MIGRATION_BATCH_SIZE=100
```

#### 설정 상세 설명

**NAMESPACE_COMPAT_ENABLED**
- `true`: 호환 모드 활성화 (기본값)
- `false`: 새로운 네임스페이스 패턴만 사용

**NAMESPACE_COMPAT_FALLBACK** 
- 쉼표로 구분된 레거시 컬렉션 이름 목록
- 왼쪽부터 우선순위 순으로 확인
- 기본값: `mail_my_documents,doc_my_documents,my_documents`

**AUTO_MIGRATE_COLLECTIONS**
- `true`: 레거시 컬렉션을 새 네임스페이스로 자동 마이그레이션
- `false`: 마이그레이션하지 않고 기존 컬렉션 사용 (기본값)

### UI 상태 표시

시스템 헤더의 Qdrant 상태 배지가 실시간으로 각 데이터베이스의 상태를 표시합니다:

- **개인**: 개인 Qdrant (127.0.0.1:6333) 상태
- **부서**: 부서 Qdrant (10.150.104.37:6333) 상태

#### 상태 표시 색상
- **초록색 (OK)**: 정상 연결됨
- **노란색 (WARN)**: 경고 상태
- **빨간색 (FAIL)**: 연결 실패
- **회색 (UNKNOWN)**: 상태 불명

### 폴백 알림

부서 데이터베이스 연결이 실패하여 개인 데이터베이스로 폴백할 경우, 자동으로 토스트 알림이 표시됩니다:

> ⚠️ "부서 DB 연결 실패로 개인 DB를 사용했습니다."

### 마이그레이션 가이드

#### 수동 마이그레이션
기존 컬렉션을 새로운 네임스페이스로 마이그레이션하려면:

1. **백업 생성**
```bash
# Qdrant 데이터 백업
xcopy /E /I storage\qdrant storage\backup\qdrant_%date%
```

2. **마이그레이션 스크립트 실행**
```python
# 예시: 마이그레이션 스크립트 (추후 제공 예정)
python scripts/migrate_collections.py
```

#### 자동 마이그레이션
`.env` 파일에서 `AUTO_MIGRATE_COLLECTIONS=true`로 설정하면 시스템 시작 시 자동으로 마이그레이션이 실행됩니다.

### 문제 해결

#### 컬렉션을 찾을 수 없음
```
❌ No collections found: my_documents, mail_my_documents, doc_my_documents
```

**해결방법:**
1. Qdrant 서비스가 실행 중인지 확인
2. 문서 임베딩이 완료되었는지 확인
3. 네트워크 연결 상태 점검

#### 권한 문제
```
❌ Permission denied: Cannot access department Qdrant
```

**해결방법:**
1. 부서 서버 접근 권한 확인
2. 방화벽 설정 점검 (포트 6333, 6334)
3. VPN 연결 상태 확인

### 모니터링

호환 모드 동작은 다음 방법으로 모니터링할 수 있습니다:

#### 로그 확인
```bash
# 백엔드 로그에서 네임스페이스 관련 항목 검색
findstr /i "namespace\|fallback\|compat" backend\logs\app.log
```

#### 상태 API
```bash
# 컬렉션 상태 확인
curl http://localhost:8080/status
```

응답 예시:
```json
{
  "qdrant": {
    "personal": {
      "status": "ok",
      "collections": ["personal_dev_mail_my_documents"],
      "fallback_used": false
    },
    "dept": {
      "status": "fail", 
      "collections": [],
      "fallback_used": true,
      "fallback_collection": "mail_my_documents"
    }
  }
}
```

---

**문서 버전**: 1.0  
**작성일**: 2025-01-30  
**작성자**: HD현대미포 선각기술부