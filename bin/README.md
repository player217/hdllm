# Bin 폴더 - 오프라인 설치 파일

이 폴더에는 LLMPY Vector Studio 통합 설치에 필요한 오프라인 설치 파일들이 포함되어야 합니다.

## 필수 파일 목록

### 1. Python 3.11.9
- **파일명**: `python-3.11.9-amd64.exe`
- **다운로드**: https://www.python.org/downloads/release/python-3119/
- **용량**: 약 25MB
- **설명**: Python 3.11.9 Windows 64비트 설치 파일

### 2. Ollama
- **파일명**: `OllamaSetup.exe`
- **다운로드**: https://ollama.com/download/windows
- **용량**: 약 50MB
- **설명**: Ollama Windows 설치 파일

### 3. Java JDK (선택사항)
- **파일명**: `jdk-21_windows-x64_bin.exe` (또는 다른 버전)
- **다운로드**: https://www.oracle.com/java/technologies/downloads/
- **용량**: 약 150MB
- **설명**: Apache Tika 파서 지원을 위한 Java JDK

### 4. BGE-M3 모델
- **폴더명**: `bge-m3/`
- **내용**: BGE-M3 임베딩 모델 파일들
- **설명**: 이미 준비된 BGE-M3 모델 파일들

## 폴더 구조
```
bin/
├── python-3.11.9-amd64.exe      # Python 설치 파일
├── OllamaSetup.exe               # Ollama 설치 파일
├── jdk-21_windows-x64_bin.exe   # Java JDK 설치 파일 (선택)
├── bge-m3/                       # BGE-M3 모델 폴더
│   ├── config.json
│   ├── model.safetensors
│   └── ...
└── README.md                     # 이 파일
```

## 설치 과정

`install.bat`를 실행하면 다음 순서로 자동 설치됩니다:

1. **Python 3.11.9 확인/설치**
   - 이미 설치되어 있으면 건너뜀
   - 없으면 bin 폴더의 설치 파일 실행

2. **Java JDK 확인/설치**
   - Tika 파서 지원용
   - 없어도 기본 기능은 작동

3. **Ollama 확인/설치**
   - LLM 서버용
   - 설치 후 gemma2:2b 모델 자동 다운로드

4. **Python 가상환경 및 패키지**
   - venv 생성
   - requirements.txt 패키지 설치

5. **BGE-M3 모델 복사**
   - bin/bge-m3 → models/bge-m3로 복사

## 주의사항

- 모든 설치 파일은 오프라인 설치를 위해 미리 준비되어야 합니다
- gemma2:2b 모델만 인터넷 연결이 필요합니다 (Ollama pull)
- 설치 파일이 없으면 install.bat에서 에러가 발생합니다

## 배포 시 체크리스트

- [ ] python-3.11.9-amd64.exe 포함
- [ ] OllamaSetup.exe 포함
- [ ] jdk 설치 파일 포함 (선택)
- [ ] bge-m3 폴더 포함
- [ ] 총 용량: 약 300-500MB (Java 포함 시)