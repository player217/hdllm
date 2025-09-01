# HD현대미포 Gauss-1 RAG System - 포터블 설치 가이드

> **버전**: 3.0 - Portable & Smart Deployment Ready  
> **작성일**: 2025-08-31  
> **대상**: HD현대미포 선각기술부 및 시스템 관리자

## 시스템 개요

### 🎯 주요 개선사항 (v3.0)
- **원클릭 설치**: PowerShell 스크립트로 완전 자동화
- **포터블 배포**: 어떤 PC·어떤 경로에서도 실행 가능
- **스마트 전환**: 원격/로컬 Qdrant 자동 전환
- **경로 독립**: 설치 경로에 관계없이 동작
- **안전 종료**: 데이터 무결성 보장

### 🏗️ 아키텍처
```
LMM_UI_APP/
├── scripts/          # 실행 스크립트
│   ├── install.ps1   # PowerShell 자동 설치
│   ├── run.bat       # 스마트 실행기
│   └── stop.bat      # 안전 종료기
├── bin/              # 포터블 바이너리 (자동 다운로드)
│   ├── python311/    # Python 임베디드
│   ├── qdrant/       # Qdrant 서버
│   └── ollama/       # Ollama (선택사항)
├── data/             # 데이터 저장소
│   └── qdrant/       # 벡터 데이터
├── venv/             # Python 가상환경
└── .env              # 환경 설정
```

---

## 📋 목차
1. [시스템 개요](#시스템-개요)
2. [설치 전 준비사항](#설치-전-준비사항)
3. [자동 설치 (권장)](#자동-설치-권장)
4. [수동 설치](#수동-설치)
5. [실행 및 사용법](#실행-및-사용법)
6. [설정 가이드](#설정-가이드)
7. [문제 해결](#문제-해결)
8. [고급 설정](#고급-설정)

---

## 설치 전 준비사항

### ⚡ 최소 시스템 요구사항
- **OS**: Windows 10/11 (64-bit)
- **RAM**: 8GB 이상 (권장: 16GB)
- **저장공간**: 10GB 이상 여유공간
- **네트워크**: 인터넷 연결 (초기 설치 시)

### 🔧 선택사항
- **GPU**: CUDA 지원 그래픽카드 (성능 향상)
- **Ollama**: 로컬 LLM 서비스 (별도 설치)

---

## 자동 설치 (권장)

### 🚀 원클릭 설치

#### 1단계: PowerShell 실행
```powershell
# 관리자 권한으로 PowerShell 실행
# Windows + X → "Windows PowerShell(관리자)"
```

#### 2단계: 실행 정책 설정 (최초 1회)
```powershell
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser -Force
```

#### 3단계: 자동 설치 실행
```powershell
# 프로젝트 폴더로 이동
cd "C:\Users\lseun\Documents\LMM_UI_APP"

# 자동 설치 실행
.\scripts\install.ps1
```

### 📦 설치 과정
1. **환경 검사**: 시스템 요구사항 확인
2. **Python 설치**: Python 3.11 임베디드 버전 다운로드
3. **가상환경 구성**: venv 생성 및 패키지 설치
4. **Qdrant 설치**: 포터블 Qdrant 바이너리 다운로드
5. **설정 구성**: .env 파일 생성 및 최적화
6. **서비스 테스트**: 모든 컴포넌트 동작 확인

### ✅ 설치 완료 확인
```
✅ Python 3.11 임베디드 설치 완료
✅ 가상환경 생성 및 패키지 설치 완료
✅ Qdrant 서버 설치 완료
✅ 환경 설정 구성 완료
✅ 모든 컴포넌트 테스트 통과

🎉 설치가 완료되었습니다!
실행: scripts\run.bat
```

---

## 수동 설치

### 🔧 고급 사용자용

#### 1. Python 환경 구성
```bash
# Python 가상환경 생성
python -m venv venv

# 가상환경 활성화
venv\Scripts\activate.bat

# 패키지 설치
pip install -r requirements.txt
```

#### 2. Qdrant 설치
```bash
# Qdrant 다운로드 (수동)
# https://github.com/qdrant/qdrant/releases
# bin\qdrant\qdrant.exe에 압축해제
```

#### 3. 환경 설정
```bash
# .env.example을 .env로 복사
copy .env.example .env

# 필요한 설정 수정
notepad .env
```

---

## 실행 및 사용법

### 🎮 시스템 실행

#### 기본 실행
```bash
# 메인 디렉토리에서
scripts\run.bat
```

#### 실행 과정
1. **환경 변수 로드**: .env 파일 읽기
2. **가상환경 활성화**: Python venv 활성화
3. **Qdrant 연결**: 스마트 모드 선택
   - 원격 서버 연결 시도
   - 실패 시 로컬 서버 시작
4. **Ollama 확인**: LLM 서비스 상태 점검
5. **백엔드 시작**: FastAPI 서버 (포트 8080)
6. **프론트엔드 시작**: 웹 서버 (포트 8001)
7. **GUI 실행**: 선택적 데스크톱 애플리케이션

### 🌐 웹 인터페이스 접속
- **메인 페이지**: http://localhost:8001
- **API 문서**: http://localhost:8080/docs
- **시스템 상태**: http://localhost:8080/status

### 🛑 시스템 종료
```bash
scripts\stop.bat
```

---

## 설정 가이드

### 🎛️ 주요 설정 (.env)

#### Qdrant 모드 설정
```bash
# 자동 모드 (권장) - 원격 우선, 실패 시 로컬
QDRANT_MODE=auto

# 강제 로컬 모드 - 항상 로컬 서버 사용
QDRANT_MODE=local

# 강제 원격 모드 - 항상 원격 서버 사용
QDRANT_MODE=remote
```

#### 원격 서버 설정
```bash
# 부서 공용 서버
REMOTE_QDRANT_HOST=10.150.104.37
REMOTE_QDRANT_PORT=6333

# 연결 테스트 설정
CONNECTION_TIMEOUT=5
RETRY_ATTEMPTS=3
```

#### 포트 설정
```bash
# 웹 서버 포트
APP_PORT=8080
FRONTEND_PORT=8001

# 로컬 Qdrant 포트
LOCAL_QDRANT_PORT=6333
```

#### LLM 모델 설정
```bash
# Ollama 모델 (자동 다운로드)
OLLAMA_MODEL=gemma3:4b
OLLAMA_AUTO_PULL=true

# 대안 모델들
# OLLAMA_MODEL=llama3.2:3b
# OLLAMA_MODEL=mistral:7b
# OLLAMA_MODEL=qwen2.5:7b
```

---

## 문제 해결

### ❓ 자주 발생하는 문제

#### 1. PowerShell 실행 정책 오류
```
오류: 이 시스템에서 스크립트를 실행할 수 없습니다.
해결: Set-ExecutionPolicy RemoteSigned -Scope CurrentUser -Force
```

#### 2. 포트 충돌
```
오류: 포트 8080이 이미 사용 중입니다.
해결: 
1. netstat -ano | findstr :8080
2. taskkill /PID [PID번호] /F
3. 또는 .env에서 포트 변경
```

#### 3. Qdrant 연결 실패
```
오류: 원격 Qdrant 서버에 연결할 수 없습니다.
해결:
1. 네트워크 연결 확인
2. 방화벽 설정 확인
3. QDRANT_MODE=local로 변경
```

#### 4. Python 가상환경 오류
```
오류: 가상환경을 찾을 수 없습니다.
해결:
1. scripts\install.ps1 재실행
2. 또는 수동 가상환경 생성
```

### 🔍 로그 확인

#### 로그 위치
- **애플리케이션**: `logs/app.log`
- **에러 로그**: `logs/error.log`
- **백엔드 로그**: `backend/logs/`

#### 로그 레벨 조정
```bash
# .env 파일
LOG_LEVEL=DEBUG  # CRITICAL, ERROR, WARNING, INFO, DEBUG
```

---

## 고급 설정

### 🔐 보안 설정

#### API 보안
```bash
# API 키 활성화
API_KEY_ENABLED=true
API_KEY=your-secure-api-key-here

# CORS 제한
ALLOWED_ORIGINS=http://localhost:8001,http://127.0.0.1:8001
```

#### PII 보호
```bash
# 개인정보 마스킹
PII_MASKING_ENABLED=true
PII_PATTERNS_FILE=./config/pii_patterns.json
```

### ⚡ 성능 튜닝

#### GPU 가속 (CUDA)
```bash
# 디바이스 설정
EMBED_DEVICE=cuda  # cpu | cuda | cuda:0

# 배치 크기 증가
EMBED_BATCH_SIZE=64  # GPU 사용 시 증가 권장
```

#### Qdrant 최적화
```bash
# HNSW 파라미터
QDRANT_HNSW_EF=128
QDRANT_EXACT=false
QDRANT_SEARCH_LIMIT=10
QDRANT_SCORE_THRESHOLD=0.3
```

---

## 📞 지원 및 문의

### 🏢 HD현대미포 선각기술부
- **담당 부서**: 선각기술부
- **시스템 관리자**: 내부 문의
- **기술 문서**: 프로젝트 CLAUDE.md 참조

### 📚 추가 자료
- **API 문서**: http://localhost:8080/docs
- **프로젝트 README**: README.md
- **설정 템플릿**: .env.example

### 🔧 업데이트
- **현재 버전**: 3.0
- **다음 업데이트**: 기능 개선 시 자동 안내
- **업데이트 방법**: scripts\install.ps1 재실행

---

> **설치 완료 후 첫 실행 시**  
> 1. `scripts\run.bat` 실행  
> 2. 브라우저에서 http://localhost:8001 접속  
> 3. "선각기술부는 무엇인가요?" 질문으로 테스트  
>   
> **문제 발생 시**  
> 1. `logs/` 폴더의 로그 파일 확인  
> 2. `scripts\stop.bat`로 전체 종료 후 재시작  
> 3. 해결되지 않으면 `scripts\install.ps1` 재실행

**🎉 HD현대미포 Gauss-1 RAG System에 오신 것을 환영합니다!**