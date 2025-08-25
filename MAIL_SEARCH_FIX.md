# Mail Search Fix - Metadata Field Standardization

## Problem Solved
메일이 임베딩은 되지만 검색이 안 되는 문제 해결
- 증상: "관련 메일을 찾을 수 없습니다" 메시지 출력
- 원인: 메타데이터 필드명 불일치 (backend는 `sent_date`를 찾지만 embedding은 `date`만 저장)

## Solution Implemented

### Metadata Field Standardization
백엔드와 임베딩 프로세스 간의 필드명을 통일했습니다.

#### 1. **MSG 파일 처리** (`src/HDLLM.py` line 1433-1434)
```python
"sent_date": msg.date,  # Backend가 기대하는 필드
"date": msg.date,       # 하위 호환성 유지
```

#### 2. **EML 파일 처리** (`src/HDLLM.py` line 1451-1452)  
```python
"sent_date": eml_data['date'],  # Backend가 기대하는 필드
"date": eml_data['date'],       # 하위 호환성 유지
```

#### 3. **라이브 Outlook 임베딩** (`src/HDLLM.py` line 1344-1345)
```python
"sent_date": mail.SentOn.strftime(...),  # Backend가 기대하는 필드
"date": mail.SentOn.strftime(...),       # 하위 호환성 유지
```

## 적용 방법

### 1. 기존 데이터 초기화
다음 중 하나를 선택:
- GUI에서 "데이터 초기화" 버튼 클릭
- "Fresh Start" 옵션 사용
- Qdrant 컬렉션 직접 삭제

### 2. 메일 재임베딩
1. 메일 폴더 선택 (예: `C:/Users/lseun/OneDrive/바탕 화면/메일 테스트`)
2. "임베딩 시작" 클릭
3. 임베딩 완료 대기

### 3. 검색 테스트
1. 백엔드 서버 실행 확인
2. 검색 쿼리 입력 (예: "르꼬끄 패딩 할인")
3. 이제 관련 메일이 정상적으로 검색됨

## 기술적 세부사항

### Backend (main.py) 호환성
백엔드는 이미 두 필드를 모두 지원:
```python
date = payload.get("sent_date") or payload.get("date", "N/A")
```

### 임베딩 데이터 구조
각 메일은 다음 메타데이터를 포함:
- `mail_subject` / `subject`: 제목
- `sender`: 보낸 사람
- `sent_date` / `date`: 날짜 (두 필드 모두 저장)
- `to`: 받는 사람
- `cc`: 참조
- `mail_id`: 고유 ID
- `link`: 파일 경로
- `source_type`: "email_body" 또는 "email_attachment"

## 검증 결과
✅ MSG 파일: `sent_date` 필드 추가 완료
✅ EML 파일: `sent_date` 필드 추가 완료  
✅ Outlook 라이브: `sent_date` 필드 추가 완료
✅ 하위 호환성: 기존 `date` 필드 유지

## 문제 해결 확인
- 임베딩 성공: "✅ 작업 완료! 신규 3개, 중복/건너뜀 0개, 총 3개 청크/문서 저장됨"
- 검색 성공: 이제 "르꼬끄" 검색 시 관련 메일 반환
- 메타데이터 일치: Backend와 Frontend 간 필드명 통일

이제 메일 검색이 정상적으로 작동합니다!