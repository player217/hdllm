# LLM RAG 시스템 설치 및 실행 가이드

## 시스템 개요

이 시스템은 메일과 문서를 분리하여 관리하는 RAG(Retrieval-Augmented Generation) 시스템입니다.

### 주요 특징
- **메일/문서 분리 아키텍처**: 메일은 개인 PC 로컬 Qdrant, 문서는 부서 대표 PC Qdrant 사용
- **GUI 프로그램**: 메일/문서 임베딩을 위한 데스크톱 애플리케이션
- **웹 인터페이스**: FastAPI 백엔드 + HTML 프론트엔드
- **유연한 파서 시스템**: 선각계열회의록 전용 파서 및 일반 문서 파서 지원

## 1. 사전 요구사항

### 필수 소프트웨어
- Python 3.11 이상
- Ollama (LLM 서버)
- Microsoft Office (Outlook 연동 시 필요)

### 다운로드 필요 파일
- `qdrant.exe`: Qdrant 벡터 데이터베이스 실행 파일
- `bge-m3-local`: 임베딩 모델 (HuggingFace에서 다운로드)
- `kobart-local`: 한국어 요약 모델 (선택사항)

## 2. 설치 방법

### 자동 설치 (권장)
```batch
INSTALL.bat
```

### 수동 설치
```bash
# 1. pip 업그레이드
python -m pip install --upgrade pip

# 2. 필수 패키지 설치
pip install -r requirements.txt

# 3. 폴더 구조 생성
mkdir src\bin
mkdir chunk_outputs
mkdir email_attachments
```

### 모델 파일 복사
```
src/bin/
├── qdrant.exe           # Qdrant 실행 파일
├── bge-m3-local/        # 임베딩 모델 폴더
│   ├── config.json
│   ├── model.safetensors
│   └── ...
└── kobart-local/        # 요약 모델 폴더 (선택사항)
    ├── config.json
    ├── pytorch_model.bin
    └── ...
```

## 3. 환경 설정

### 환경 변수 설정

#### 메일 전용 환경
```batch
set RAG_MAIL_QDRANT_HOST=127.0.0.1
set RAG_MAIL_QDRANT_PORT=6333
set RAG_DOC_QDRANT_HOST=192.168.1.100  # 부서 대표 PC IP
set RAG_DOC_QDRANT_PORT=6333
```

#### 문서 전용 환경 (부서 대표 PC)
```batch
set RAG_MAIL_QDRANT_HOST=127.0.0.1
set RAG_MAIL_QDRANT_PORT=6333
set RAG_DOC_QDRANT_HOST=127.0.0.1
set RAG_DOC_QDRANT_PORT=6333
```

### config.json 설정
```json
{
    "mail_qdrant_path": "C:\\Users\\사용자\\Documents\\qdrant_mail",
    "doc_qdrant_path": "C:\\Users\\사용자\\Documents\\qdrant_document"
}
```

## 4. 실행 방법

### GUI 프로그램 실행
```batch
RUN.bat
```
또는
```bash
python src\HDLLM.py
```

### 웹 서버 실행

#### 개별 실행
```batch
# 터미널 1: 백엔드
run_backend.bat

# 터미널 2: 프론트엔드
run_frontend.bat
```

#### 통합 실행
```bash
# 메일 모드
python run_all.py --service_type=mail

# 문서 모드
python run_all.py --service_type=doc
```

## 5. 사용 방법

### GUI 프로그램 사용

1. **Qdrant 서버 시작**
   - 저장 경로 설정
   - "실행" 버튼 클릭

2. **메일 임베딩**
   - Outlook 연결
   - 처리할 폴더 선택
   - "이어서 임베딩" 또는 "새롭게 임베딩" 클릭

3. **문서 임베딩**
   - 문서 폴더 선택
   - 파서 선택 (선각계열회의록 또는 일반문서)
   - 청킹 옵션 설정
   - "이어서 임베딩" 또는 "새롭게 임베딩" 클릭

### 웹 인터페이스 사용

1. 브라우저에서 http://localhost:8001 접속
2. 소스 선택 (메일/문서)
3. 질문 입력
4. 답변 및 관련 문서 확인

## 6. 테스트 및 검증

### 통합 테스트 실행
```bash
python test_integration.py
```

### 서비스 상태 확인
- FastAPI: http://localhost:8080/docs
- Ollama: http://localhost:11434
- Qdrant: http://localhost:6333/dashboard

## 7. 문제 해결

### 일반적인 문제

1. **"Python이 설치되어 있지 않습니다"**
   - Python 3.11 이상 설치
   - 환경 변수 PATH에 Python 추가

2. **"모듈을 찾을 수 없습니다"**
   - `INSTALL.bat` 실행
   - 또는 `pip install -r requirements.txt`

3. **Qdrant 실행 실패**
   - `src/bin/qdrant.exe` 파일 확인
   - 포트 6333이 사용 중인지 확인

4. **임베딩 모델 로드 실패**
   - `src/bin/bge-m3-local` 폴더 확인
   - 모델 파일 완전성 확인

### 로그 확인
- 임베딩 로그: `embedding_log_mail.txt`, `embedding_log_doc.txt`
- 청크 출력: `chunk_outputs/` 폴더

## 8. 고급 설정

### 파서 추가
1. `src/parsers/` 폴더에 새 파서 파일 생성
2. `_parse_workbook` 함수 구현
3. HDLLM.py의 `DOCUMENT_PARSERS` 딕셔너리에 추가

### 네트워크 설정
- 방화벽에서 포트 허용: 8080, 8001, 6333, 11434
- 부서 대표 PC의 Qdrant는 네트워크 접근 허용 필요

### 성능 최적화
- `QDRANT_BATCH_SIZE`: 배치 크기 조정 (기본값: 128)
- 청크 크기/중첩 조정으로 검색 품질 개선

## 9. 보안 주의사항

- 민감한 정보가 포함된 메일/문서는 로컬에만 저장
- 네트워크 Qdrant 사용 시 접근 제어 설정
- preprocessing_rules.json으로 PII 마스킹 규칙 설정 가능