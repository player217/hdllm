# HD현대미포 Gauss-1 컬렉션 관리 스크립트

이 디렉토리에는 Qdrant 컬렉션 검증 및 생성을 위한 유틸리티 스크립트들이 포함되어 있습니다.

## 📋 스크립트 목록

### 1. 컬렉션 검증 (`validate_collections.py`)
기존 컬렉션의 상태와 벡터 차원을 검증합니다.

**사용법:**
```bash
# 기본 검증 (mail, doc 소스)
python scripts/validate_collections.py

# 특정 소스만 검증
python scripts/validate_collections.py --sources mail

# 상세 로그와 함께 검증
python scripts/validate_collections.py --verbose

# Windows 배치 스크립트 사용
scripts\validate_collections.bat
```

**옵션:**
- `--sources`: 검증할 소스 타입 (기본값: mail, doc)
- `--base-name`: 기본 컬렉션 이름 (기본값: my_documents)
- `--verbose, -v`: 상세 로그 출력
- `--auto-create`: 누락된 컬렉션 자동 생성

**종료 코드:**
- `0`: 모든 검증 통과
- `1`: 검증 실패 (시스템 오류)
- `2`: 일부 문제 발견 (경고)

### 2. 컬렉션 생성 (`create_collections.py`)
새로운 컬렉션을 생성하거나 기존 컬렉션을 재생성합니다.

**사용법:**
```bash
# 기본 생성 (누락된 컬렉션만)
python scripts/create_collections.py

# 모든 컬렉션 강제 재생성
python scripts/create_collections.py --force

# 드라이런 모드 (실제 생성하지 않고 계획만 출력)
python scripts/create_collections.py --dry-run

# Windows 배치 스크립트 사용
scripts\create_collections.bat --dry-run
```

**옵션:**
- `--sources`: 생성할 소스 타입 (기본값: mail, doc)
- `--base-name`: 기본 컬렉션 이름 (기본값: my_documents)
- `--force`: 기존 컬렉션 강제 재생성
- `--verbose, -v`: 상세 로그 출력
- `--dry-run`: 실제 생성하지 않고 계획만 출력

**종료 코드:**
- `0`: 모든 컬렉션 생성 성공
- `1`: 생성 실패 (시스템 오류)
- `2`: 일부 컬렉션 생성 실패

## 🔧 컬렉션 명명 규칙

스크립트들은 ResourceManager의 동적 명명 규칙을 사용합니다:

```
{namespace}_{env}_{source_type}_{base_name}
```

**예시:**
- 환경변수 설정: `QDRANT_NAMESPACE=hdmipo`, `QDRANT_ENV=prod`
- Mail 컬렉션: `hdmipo_prod_mail_my_documents`
- Doc 컬렉션: `hdmipo_prod_doc_my_documents`

## 🚀 일반적인 사용 시나리오

### 1. 시스템 초기 설정
```bash
# 1. 드라이런으로 계획 확인
python scripts/create_collections.py --dry-run

# 2. 컬렉션 생성
python scripts/create_collections.py

# 3. 검증
python scripts/validate_collections.py
```

### 2. 시스템 상태 점검
```bash
# 현재 상태 확인
python scripts/validate_collections.py --verbose
```

### 3. 컬렉션 재생성 (문제 발생 시)
```bash
# 강제 재생성
python scripts/create_collections.py --force

# 검증
python scripts/validate_collections.py
```

### 4. 특정 소스만 관리
```bash
# Mail 컬렉션만 검증
python scripts/validate_collections.py --sources mail

# Doc 컬렉션만 재생성
python scripts/create_collections.py --sources doc --force
```

## 📝 로그 및 디버깅

### 상세 로그 활성화
```bash
python scripts/validate_collections.py --verbose
```

### 드라이런 모드로 안전 테스트
```bash
python scripts/create_collections.py --dry-run --verbose
```

## ⚠️ 주의사항

1. **운영 환경에서의 주의**: `--force` 옵션은 기존 데이터를 삭제할 수 있습니다
2. **권한 확인**: Qdrant 서버에 대한 읽기/쓰기 권한이 필요합니다
3. **백업 권장**: 중요한 데이터가 있는 경우 백업 후 실행하세요
4. **네트워크 연결**: Qdrant 서버가 실행 중이어야 합니다

## 🔍 문제 해결

### 일반적인 오류들

**1. "모듈 임포트 실패"**
- 가상환경이 활성화되어 있는지 확인
- `pip install -r requirements.txt` 실행

**2. "Qdrant 연결 실패"**
- Qdrant 서버가 실행 중인지 확인
- 네트워크 연결 및 포트 설정 확인

**3. "권한 오류"**
- Qdrant API 키 설정 확인
- 컬렉션 생성/수정 권한 확인

### 디버깅 명령어
```bash
# 상세 로그와 함께 실행
python scripts/validate_collections.py --verbose

# 드라이런으로 계획 확인
python scripts/create_collections.py --dry-run --verbose
```

## 📞 지원

문제가 발생하면 다음 정보와 함께 문의하세요:
1. 실행한 명령어
2. 오류 메시지 (--verbose 로그 포함)
3. 환경 정보 (OS, Python 버전, Qdrant 버전)
4. 환경 변수 설정 (민감한 정보 제외)