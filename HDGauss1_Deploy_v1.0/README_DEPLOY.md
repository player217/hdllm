# HD현대미포 Gauss-1 RAG System - 배포 가이드

> **버전**: 1.0.0  
> **대상**: Docker 불가 PC 환경  
> **타입**: 완전 독립 실행형 패키지  
> **업데이트**: 2025-09-01

## 📋 개요

HD현대미포 Gauss-1 RAG 시스템의 Docker 없이 실행 가능한 완전 독립형 배포 패키지입니다.
모든 필요한 바이너리, 모델, 의존성을 포함하여 인터넷 연결 없이도 동작합니다.

### ✨ 주요 특징
- **🚀 원클릭 실행**: `scripts\run.bat` 실행만으로 전체 시스템 시작
- **📦 완전 독립**: Docker, Python 사전 설치 불필요  
- **🔄 듀얼 라우팅**: Personal(로컬) + Department(원격) Qdrant 지원
- **💾 오프라인**: 모든 모델과 바이너리 포함 (선택사항)
- **🛠️ 관리 도구**: 진단, 디버그, 개별 테스트 스크립트 제공

---

## 🖥️ 시스템 요구사항

| 항목 | 최소 사양 | 권장 사양 |
|------|-----------|-----------|
| **OS** | Windows 10 64bit | Windows 11 64bit |
| **RAM** | 8 GB | 16 GB |
| **저장공간** | 20 GB 여유 | 30 GB 여유 |
| **CPU** | Intel i5 또는 동급 | Intel i7 또는 동급 |
| **네트워크** | 선택사항* | 100 Mbps+ |

*첫 실행 시 모델 다운로드를 위해 인터넷 연결 필요 (모델 미포함 시)

---

## 📁 패키지 구조

```
HDGauss1_Deploy_v1.0/
├── 📁 backend/                    # 백엔드 서버 (최소 구성)
│   ├── main.py                   # FastAPI 메인 서버
│   ├── resource_manager.py       # 리소스 관리자  
│   ├── security.py              # 보안 미들웨어
│   ├── security_config.py       # 보안 설정
│   └── requirements.lock.txt     # 고정 의존성
├── 📁 src/                       # GUI 애플리케이션
│   ├── HDLLM.py                 # 메인 GUI
│   ├── ui_user_tab.py           # 사용자 탭
│   └── parsers/                 # 문서 파서
├── 📁 frontend/                  # 웹 인터페이스  
│   ├── index.html               # 웹 UI
│   └── favicon.ico              # 아이콘
├── 📁 bin/                       # 실행 파일들
│   ├── python311/               # 임베디드 Python 3.11
│   │   └── python.exe
│   ├── qdrant/                  # 벡터 데이터베이스
│   │   ├── qdrant.exe
│   │   └── qdrant.yaml
│   └── ollama/                  # LLM 서버
│       └── ollama.exe
├── 📁 models/                    # AI 모델 캐시
│   ├── embeddings/              # 임베딩 모델
│   │   └── bge-m3/
│   └── ollama/                  # LLM 모델
│       └── gemma3-4b/
├── 📁 data/                      # 데이터 저장소
│   └── qdrant/                  # 벡터 DB 저장소
├── 📁 logs/                      # 로그 파일
├── 📁 scripts/                   # 관리 스크립트
│   ├── run.bat                  # 🚀 메인 실행
│   ├── run_gui_debug.bat        # 🐛 GUI 디버그  
│   ├── stop.bat                 # ⏹️ 전체 중지
│   ├── run_qdrant.bat           # ⚙️ Qdrant 테스트
│   ├── run_ollama.bat           # 🤖 Ollama 테스트
│   └── self_check.ps1           # 🔍 시스템 점검
├── .env                         # 환경 설정
├── manifest.json                # 패키지 정보
└── README_DEPLOY.md             # 이 파일
```

---

## 🚀 설치 및 실행

### 1단계: 압축 해제
```cmd
# 원하는 위치에 압축 파일 해제
# 예: C:\HDGauss1\ 또는 D:\Applications\HDGauss1\
```

### 2단계: 시스템 점검 (권장)
```powershell
# PowerShell 관리자 모드로 실행
cd HDGauss1_Deploy_v1.0
.\scripts\self_check.ps1 -Detailed -Fix
```

### 3단계: 메인 실행
```cmd  
# 메인 실행 스크립트
scripts\run.bat
```

### 4단계: 접속 확인
- **GUI**: 자동 실행됨
- **웹 인터페이스**: http://localhost:8001
- **API 문서**: http://localhost:8080/docs
- **시스템 상태**: http://localhost:8080/status

---

## 🔧 관리 도구

### 스크립트 모음

| 스크립트 | 용도 | 실행 방법 |
|----------|------|-----------|
| `run.bat` | 🚀 **전체 시스템 시작** | `scripts\run.bat` |
| `stop.bat` | ⏹️ **전체 시스템 중지** | `scripts\stop.bat` |
| `run_gui_debug.bat` | 🐛 **GUI 문제 진단** | `scripts\run_gui_debug.bat` |
| `run_qdrant.bat` | ⚙️ **Qdrant 단독 테스트** | `scripts\run_qdrant.bat` |
| `run_ollama.bat` | 🤖 **Ollama 단독 테스트** | `scripts\run_ollama.bat` |
| `self_check.ps1` | 🔍 **시스템 자가 진단** | `powershell .\scripts\self_check.ps1` |

### 시스템 진단 명령어

```powershell
# 기본 점검
.\scripts\self_check.ps1

# 상세 점검 + 자동 수정
.\scripts\self_check.ps1 -Detailed -Fix

# 포트 사용 현황 확인
netstat -ano | findstr "6333\|8080\|8001\|11434"

# 실행 중인 프로세스 확인  
tasklist | findstr "python\|qdrant\|ollama"
```

---

## 🔄 듀얼 Qdrant 라우팅

이 시스템은 두 개의 Qdrant 인스턴스를 지원합니다:

### 설정 (.env 파일)
```env
# Personal PC (로컬)
QDRANT_PERSONAL_HOST=127.0.0.1
QDRANT_PERSONAL_PORT=6333

# Department Server (원격) 
QDRANT_DEPT_HOST=10.150.104.37
QDRANT_DEPT_PORT=6333

# 기본값
DEFAULT_DB_SCOPE=personal
```

### 사용 방법
1. **GUI**: 상단 메뉴에서 "Personal" ↔ "Department" 전환
2. **웹**: 우상단 드롭다운에서 선택
3. **API**: `X-Qdrant-Scope: personal|dept` 헤더 사용

---

## 🛠️ 문제 해결

### 자주 발생하는 문제

#### 1. GUI가 실행되지 않음
```cmd
# 디버그 모드로 실행하여 로그 확인
scripts\run_gui_debug.bat

# 로그 파일 확인
type logs\gui_debug.log
```

**일반적인 원인**:
- Python 경로 문제
- PySide6 모듈 누락
- 권한 문제

#### 2. 포트 충돌 오류
```cmd
# 사용 중인 포트 확인
netstat -ano | findstr ":6333"
netstat -ano | findstr ":8080" 

# 모든 서비스 중지 후 재시작
scripts\stop.bat
scripts\run.bat
```

#### 3. 모델을 찾을 수 없음
```cmd
# 환경변수 확인
echo %OLLAMA_MODELS%
echo %HF_HOME%

# 모델 디렉토리 확인
dir models\ollama
dir models\embeddings
```

#### 4. Qdrant 시작 실패
```cmd  
# Qdrant 단독 테스트
scripts\run_qdrant.bat

# 저장소 권한 확인
mkdir data\qdrant
echo test > data\qdrant\test.txt
```

#### 5. 백엔드 API 오류
```cmd
# API 상태 확인
curl http://localhost:8080/status

# 백엔드 로그 확인 (실행 중이면)
# Window Title "Backend API"인 콘솔 창 확인
```

### 로그 위치

| 서비스 | 로그 파일 | 용도 |
|---------|-----------|------|
| GUI | `logs\gui_debug.log` | GUI 실행 오류 |
| Backend | 콘솔 창 | API 서버 로그 |
| Qdrant | 콘솔 창 | 벡터 DB 로그 |
| Ollama | 콘솔 창 | LLM 서버 로그 |

### 완전 재설정

```cmd
# 1. 모든 서비스 중지
scripts\stop.bat

# 2. 데이터 폴더 초기화 (주의: 데이터 손실)
rmdir /s data\qdrant
mkdir data\qdrant

# 3. 로그 정리
del /q logs\*

# 4. 재시작
scripts\run.bat
```

---

## ⚙️ 고급 설정

### 환경 변수 커스터마이징

**포트 변경** (`.env` 파일 수정):
```env
APP_PORT=8081        # 기본값: 8080
FRONTEND_PORT=8002   # 기본값: 8001
QDRANT_PERSONAL_PORT=6334  # 기본값: 6333
```

**성능 튜닝**:
```env
MAX_CONCURRENT_REQUESTS=20    # 기본값: 10
EMBEDDING_BATCH_SIZE=64       # 기본값: 32  
VECTOR_SEARCH_LIMIT=5         # 기본값: 3
```

**로깅 레벨**:
```env
LOG_LEVEL=DEBUG      # INFO, WARNING, ERROR
DEBUG_MODE=true      # 개발 모드
SHOW_CONSOLE=true    # 콘솔 표시
```

### Qdrant 설정 수정

`bin\qdrant\qdrant.yaml` 파일 수정:
```yaml
# 메모리 사용량 제한 (MB)
limits:
  max_memory_usage: 4096

# 인덱싱 성능 조정
indexing:
  hnsw:
    m: 32              # 연결 수 증가 (메모리↑, 성능↑)
    ef_construct: 200  # 정확도 향상
```

---

## 🔒 보안 고려사항

### API 키 설정 
```env  
# .env 파일에서 기본 API 키 변경
API_KEYS=your_secure_key:production,test_key:development
```

### CORS 설정
```env
# 허용된 오리진만 추가
CORS_ALLOW_ORIGINS=http://localhost:8001,http://company-intranet
```

### 방화벽 설정
- **인바운드**: 포트 6333, 8080, 8001 허용
- **아웃바운드**: 모델 다운로드용 HTTPS 허용 (첫 실행 시)

---

## 📊 성능 모니터링

### 시스템 리소스 확인
```powershell
# 메모리 사용량
Get-Process python,qdrant,ollama | Select-Object Name, WorkingSet

# CPU 사용률  
Get-Counter "\Processor(_Total)\% Processor Time"

# 디스크 사용량
Get-ChildItem data\qdrant -Recurse | Measure-Object Length -Sum
```

### API 성능 테스트
```powershell
# 상태 확인
Invoke-RestMethod http://localhost:8080/status

# 질의응답 테스트  
$body = @{question="테스트 질문"} | ConvertTo-Json
Invoke-RestMethod -Uri http://localhost:8080/ask -Method POST -Body $body -ContentType "application/json"
```

---

## 🔄 업데이트 및 백업

### 백업 생성
```cmd
# 데이터 백업
xcopy data\qdrant backup\qdrant_%date%\ /E /I

# 설정 백업  
copy .env backup\.env_%date%
copy bin\qdrant\qdrant.yaml backup\qdrant_%date%.yaml
```

### 업데이트 절차
1. **현재 데이터 백업**
2. **서비스 중지**: `scripts\stop.bat`
3. **새 패키지로 교체** (data 폴더 제외)
4. **설정 파일 병합**
5. **서비스 재시작**: `scripts\run.bat`

---

## 📞 지원 및 문의

### 기술 지원
- **부서**: HD현대미포 선각기술부
- **담당자**: [담당자명]
- **내선**: [내선번호]
- **이메일**: [이메일주소]

### 문제 신고 시 포함 정보
1. **시스템 정보**: `scripts\self_check.ps1` 실행 결과
2. **로그 파일**: `logs\` 폴더 전체
3. **오류 상황**: 재현 단계 및 스크린샷
4. **환경 정보**: Windows 버전, 하드웨어 사양

### 자주 묻는 질문 (FAQ)

**Q: 인터넷 없이 사용 가능한가요?**
A: 네. 모델이 포함된 패키지라면 완전히 오프라인 사용 가능합니다.

**Q: 다른 PC로 이동할 수 있나요?**  
A: 네. 전체 폴더를 복사하면 바로 사용 가능합니다.

**Q: Docker 없이 정말 동작하나요?**
A: 네. 모든 필요한 바이너리가 포함되어 있어 독립 실행됩니다.

**Q: 메모리 사용량이 많습니다.**
A: `.env`에서 `MAX_MEMORY_USAGE` 및 Qdrant 설정을 조정하세요.

**Q: 모델을 업데이트하려면?**
A: `models\` 폴더의 해당 모델 폴더를 교체하거나 삭제 후 재다운로드하세요.

---

## 📝 버전 정보

### v1.0.0 (2025-09-01)
- ✨ 초기 독립 실행형 배포판 릴리스
- 🔄 듀얼 Qdrant 라우팅 지원  
- 🐍 임베디드 Python 3.11 통합
- 💾 오프라인 모델 캐싱 지원
- 🛠️ 포괄적인 관리 스크립트 제공
- 🔍 자가 진단 시스템 구축

---

> **⚠️ 주의사항**:  
> - 관리자 권한으로 실행하면 더 안정적입니다
> - Windows Defender에서 차단될 수 있습니다 (예외 추가 필요)  
> - 첫 실행 시 방화벽 허용 요청이 나타날 수 있습니다
> 
> **💡 팁**:
> - 정기적으로 `scripts\self_check.ps1`를 실행하여 시스템 상태 확인
> - 로그 파일이 커지면 주기적으로 정리
> - 중요한 데이터는 정기적으로 백업