# LLM RAG System - 메일/문서 분리 아키텍처

## 개요
이 시스템은 메일과 문서를 분리하여 검색할 수 있는 RAG(Retrieval-Augmented Generation) 시스템입니다.

## 주요 개선사항

### 1. 백엔드 개선
- **메일/문서 분리 설정**: AppConfig에 메일과 문서용 Qdrant 호스트/포트 분리
- **Qdrant 클라이언트 2개 분리**: 메일용과 문서용 클라이언트 각각 초기화
- **의존성 주입**: search_qdrant 함수가 클라이언트를 파라미터로 받도록 변경
- **/ask 엔드포인트 개선**: source 파라미터('mail' 또는 'doc') 추가
- **/status 엔드포인트 신규**: 모든 서비스 상태를 한 번에 확인

### 2. 프론트엔드 개선
- **백엔드 URL 단일화**: BACKEND_BASE 상수로 모든 API 호출 통일
- **소스 토글 UI**: 메일/문서 선택 드롭다운 추가
- **상태표시 개선**: /status 엔드포인트만 사용하여 모든 서비스 상태 확인
- **조건부 UI**: 문서 모드에서는 "열기" 버튼 숨김

## 설치 및 실행

### 1. 필수 요구사항
- Python 3.11+
- Qdrant 서버
- Ollama 서버

### 2. 패키지 설치
```bash
pip install -r requirements.txt
```

### 3. 환경 변수 설정 (선택사항)
```bash
# 메일 Qdrant (개인 PC 로컬)
set RAG_MAIL_QDRANT_HOST=127.0.0.1
set RAG_MAIL_QDRANT_PORT=6333

# 문서 Qdrant (부서 대표 PC)
set RAG_DOC_QDRANT_HOST=<부서PC_IP>
set RAG_DOC_QDRANT_PORT=6333

# Ollama
set RAG_OLLAMA_URL=http://127.0.0.1:11434/api/chat
```

### 4. 서버 실행
```bash
# 백엔드 실행
run_backend.bat

# 프론트엔드 실행 (새 터미널에서)
run_frontend.bat
```

### 5. 접속
브라우저에서 http://localhost:8001 접속

## 아키텍처

### 메일 모드
- 개인 PC의 로컬 Qdrant 사용 (localhost:6333)
- Outlook 메일 열기 기능 지원

### 문서 모드
- 부서 대표 PC의 네트워크 Qdrant 사용
- 선각계열회의록 등 공유 문서 검색

### 컬렉션명
- 모든 모드에서 동일한 컬렉션명 사용: `my_documents`

## 주의사항
- 사내/사외 환경에 따라 환경변수만 변경하여 사용
- 컬렉션명과 DB 경로는 기존 시스템과 동일하게 유지
- 문서 모드에서는 메일 열기 기능이 비활성화됨