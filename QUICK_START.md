# HD현대미포 Gauss-1 RAG System - 빠른 시작 가이드

## 🚀 2분 안에 시작하기

### 1️⃣ 설치 (처음 한 번만)
```batch
INSTALL_ENHANCED.bat
```
**⏱️ 예상 시간**: 15-30분

### 2️⃣ 실행
```batch
RUN_ENHANCED.bat
```
**⏱️ 예상 시간**: 30초

### 3️⃣ 사용
브라우저가 자동으로 열립니다 → http://localhost:8001

---

## 📱 기본 사용법

### 데이터 소스 선택
![Toggle](https://via.placeholder.com/150x50)
- **개인 DB**: 내 PC의 데이터 (기본값)
- **부서 DB**: 부서 서버의 데이터

### 질문하기
1. 텍스트 입력창에 질문 입력
2. Enter 또는 전송 버튼 클릭
3. 실시간 응답 확인

### 예시 질문
- "선각기술부는 무엇을 하는 부서인가요?"
- "최근 회의록 내용을 요약해주세요"
- "프로젝트 일정은 어떻게 되나요?"

---

## 🔧 문제 해결

### ❌ 설치 실패
→ 관리자 권한으로 실행하세요

### ❌ 포트 사용 중
→ 다른 프로그램이 포트를 사용 중입니다
```batch
# 확인
netstat -an | findstr :8080
# 해결
taskkill /F /PID [프로세스ID]
```

### ❌ 모델 다운로드 실패
→ 인터넷 연결을 확인하세요

---

## 📞 도움이 필요하신가요?

- **기술 지원**: HD현대미포 선각기술부
- **API 문서**: http://localhost:8080/docs
- **상태 확인**: http://localhost:8080/status

---

## ⚡ 고급 팁

### GPU 가속 사용
`.env` 파일에서:
```env
EMBED_DEVICE=cuda
```

### 메모리 부족 시
`.env` 파일에서:
```env
EMBED_BATCH=16  # 줄이기
EMBED_CACHE_MAX=256  # 줄이기
```

### 부서 DB 연결 실패 시
`.env` 파일에서:
```env
DEFAULT_DB_SCOPE=personal  # 개인 DB만 사용
```

### 📋 레거시 컬렉션 호환성
기존 `mail_my_documents`, `doc_my_documents`, `my_documents` 컬렉션과 자동 호환됩니다. 자세한 설정은 [배포 가이드의 네임스페이스 호환 모드](DEPLOYMENT_GUIDE.md#🔄-네임스페이스-호환-모드-compatibility-mode) 섹션을 참조하세요.

---

**버전**: 1.0 | **작성일**: 2025-01-30