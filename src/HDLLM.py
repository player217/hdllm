from __future__ import annotations
import sys
import os
import re
import shutil
import subprocess
import datetime
import time
from pathlib import Path
import uuid
import json
import traceback
import logging
import importlib.util
import types
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any, Set, Tuple
import unicodedata
import textwrap
import webbrowser
import requests
import email
from email import policy
from email.parser import BytesParser

# PySide6 UI 관련 모듈
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QTabWidget,
    QGroupBox, QGridLayout, QLabel, QLineEdit, QPushButton, QFileDialog,
    QTextEdit, QProgressBar, QMessageBox, QTreeWidget, QTreeWidgetItem,
    QCheckBox, QHBoxLayout, QTreeWidgetItemIterator, QSpinBox, QComboBox,
    QSystemTrayIcon, QMenu
)
from PySide6.QtCore import QThread, Signal, Qt, QTimer
from PySide6.QtGui import QIcon, QAction

# 기능 구현을 위한 라이브러리
try:
    from tika import parser as tika_parser
except ImportError:
    sys.exit("Tika 라이브러리가 설치되지 않았습니다. 'pip install tika'를 실행해주세요.")
try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    sys.exit("Sentence-transformers 라이브러리가 설치되지 않았습니다. 'pip install sentence-transformers'를 실행해주세요.")
try:
    from qdrant_client import QdrantClient, models
except ImportError:
    sys.exit("Qdrant-client 라이브러리가 설치되지 않았습니다. 'pip install qdrant-client'를 실행해주세요.")
try:
    import win32com.client, pythoncom
except ImportError:
    sys.exit("pywin32 라이브러리가 설치되지 않았습니다. 'pip install pypiwin32'를 실행해주세요.")
try:
    import xlwings as xw
except ImportError:
    sys.exit("xlwings 라이브러리가 설치되지 않았습니다. 'pip install xlwings'를 실행해주세요.")
try:
    import extract_msg
except ImportError:
    sys.exit("'extract-msg' 라이브러리가 설치되지 않았습니다. 'pip install extract-msg'를 실행해주세요.")
try:
    from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
    import torch
except ImportError:
    sys.exit("Transformers/PyTorch가 설치되지 않았습니다. 'pip install transformers sentencepiece torch'를 실행해주세요.")
try:
    from langchain.docstore.document import Document
except ImportError:
    class Document:
        """langchain.docstore.document.Document의 가벼운 대체 클래스."""
        def __init__(self, page_content: str, metadata: dict | None = None):
            self.page_content = page_content
            self.metadata = metadata or {}
        def __repr__(self):
            meta_preview = json.dumps(self.metadata, ensure_ascii=False, indent=2)
            content_preview = (self.page_content[:120] + '…') if len(self.page_content) > 120 else self.page_content
            return f"Document(meta={meta_preview}, content=\"{content_preview}\")"
try:
    from tqdm import tqdm
except ImportError:
    print("경고: tqdm 라이브러리가 없습니다. 'pip install tqdm'")


# ──────────────────────────────────────────────────────────────────────────────
# │ 상수 및 로깅 설정
# ──────────────────────────────────────────────────────────────────────────────
QDRANT_BATCH_SIZE = 128
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# ──────────────────────────────────────────────────────────────────────────────
# │ 1. 유틸리티 클래스 및 함수
# ──────────────────────────────────────────────────────────────────────────────
class TextCleaner:
    def __init__(self, rules_filepath: str):
        self.rules = self._load_rules(rules_filepath)
        self.pii_patterns = [re.compile(p) for p in self.rules.get("pii_patterns", [])]
        self.clean_steps = self._compile_steps(self.rules.get("clean_steps", []))

    def _load_rules(self, filepath: str) -> dict:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _compile_steps(self, steps: list) -> list:
        compiled_steps = []
        for step in steps:
            flags = 0
            for flag_str in step.get("flags", []):
                if hasattr(re, flag_str):
                    flags |= getattr(re, flag_str)
            step['pattern'] = re.compile(step['pattern'], flags)
            compiled_steps.append(step)
        return compiled_steps

    def clean(self, text: str) -> str:
        if not text:
            return ""
        cleaned_text = text
        for step in self.clean_steps:
            if step['action'] == "sub":
                cleaned_text = step['pattern'].sub(step['replace'], cleaned_text)
            elif step['action'] == "strip_before":
                if m := step['pattern'].search(cleaned_text):
                    cleaned_text = cleaned_text[:m.start()]
        for pii_pattern in self.pii_patterns:
            cleaned_text = pii_pattern.sub("[MASKED]", cleaned_text)
        return unicodedata.normalize("NFKC", cleaned_text).strip()

def preprocess_mail_for_rag(*, body_text: str, meta: Dict[str, str], cleaner: TextCleaner, summarize_fn) -> Tuple[list[str], str]:
    if not body_text: return [], ""
    cleaned = cleaner.clean(body_text)
    if not cleaned: return [], ""
    summary = textwrap.shorten(cleaned, width=120, placeholder="…")
    if summarize_fn:
        try:
            summary_input = re.sub(r"\s+", " ", cleaned).strip()[:2000]
            if summary_input:
                summary = summarize_fn(summary_input)
        except Exception:
            summary = "(요약 생성 실패)"
    return [cleaned], summary

def load_summarizer(model_dir):
    try:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        tokenizer = AutoTokenizer.from_pretrained(model_dir)
        model = AutoModelForSeq2SeqLM.from_pretrained(model_dir).to(device)
        def summarize_kobart(text: str, max_len=150, min_len=40) -> str:
            inputs = tokenizer([text[:800]], max_length=1024, truncation=True, return_tensors="pt").to(device)
            with torch.no_grad():
                ids = model.generate(inputs["input_ids"], max_length=max_len, min_length=min_len, num_beams=4, length_penalty=2.0, early_stopping=True)
            return tokenizer.decode(ids[0], skip_special_tokens=True)
        return summarize_kobart
    except Exception:
        return None

def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', '_', name)

def keep_name_only(email_field):
    if not email_field or not isinstance(email_field, str):
        return ""
    names = []
    for p in email_field.split(';'):
        if p_strip := p.strip():
            match = re.match(r'(.+)<.+>', p_strip)
            names.append(match.group(1).strip().strip('"\'') if match else p_strip.split('@')[0].strip())
    return "; ".join(names)

def chunk_by(text, chunk_size, chunk_overlap):
    if not text or chunk_size <= chunk_overlap:
        return []
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size - chunk_overlap)]

def parse_eml_file(file_path):
    """Parse .eml file and extract email metadata and content"""
    try:
        with open(file_path, 'rb') as f:
            msg = BytesParser(policy=policy.default).parse(f)
        
        # Extract body text
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_content()
                    break
                elif part.get_content_type() == "text/html" and not body:
                    # Fallback to HTML if no plain text
                    body = part.get_content()
        else:
            body = msg.get_content()
        
        # Parse date to string format
        date_str = str(msg['date']) if msg['date'] else 'N/A'
        
        return {
            'subject': msg.get('subject', 'N/A'),
            'sender': msg.get('from', 'N/A'),
            'date': date_str,
            'to': msg.get('to', 'N/A'),
            'cc': msg.get('cc', ''),
            'body': body or ''
        }
    except Exception as e:
        logging.error(f"Error parsing .eml file {file_path}: {e}")
        return None

# ──────────────────────────────────────────────────────────────────────────────
# │ 2. 문서 파싱 엔진
# ──────────────────────────────────────────────────────────────────────────────
def default_tika_engine(folder_path: Path, file_filter: List[str], **kwargs) -> List[Document]:
    """Tika를 사용하는 기본 파서 엔진"""
    all_docs = []
    files_to_process = [p for ext in file_filter for p in folder_path.rglob(f"*{ext}")]
    files = sorted(list(set(p for p in files_to_process if p.is_file() and not p.name.startswith("~$"))))
    
    for file_path in tqdm(files, desc="기본 Tika 파서 실행 중", unit="file"):
        try:
            parsed = tika_parser.from_file(str(file_path))
            content = parsed.get("content", "")
            if content and content.strip():
                meta = {"file_name": file_path.name, "path": str(file_path.resolve()), "source_type": "document"}
                all_docs.append(Document(page_content=content, metadata=meta))
        except Exception as e:
            logging.error(f"Tika 파싱 오류 {file_path.name}: {e}")
    return all_docs

def sungak_meeting_engine(folder_path: Path, file_filter: List[str], **kwargs) -> List[Document]:
    """
    xlwings를 사용하여 폴더 내의 모든 선각 회의록을 처리하는 엔진.
    각 파일마다 xlwings 인스턴스를 생성/종료하여 안정성을 확보하고, 외부 파서 로직을 동적으로 실행합니다.
    """
    logic_path_str = kwargs.get("logic_path")
    if not logic_path_str:
        logging.error("선각계열회의록 파서 엔진에 'logic_path'가 전달되지 않았습니다.")
        return []

    base_dir = Path(__file__).parent
    logic_path = base_dir / logic_path_str

    if not logic_path.exists():
        logging.error(f"지정된 파서 로직 파일을 찾을 수 없습니다: {logic_path}")
        return []

    try:
        with open(logic_path, "r", encoding="utf-8") as f:
            parser_code = f.read()
    except Exception as e:
        logging.error(f"파서 로직 파일 '{logic_path.name}'을 읽는 중 오류 발생: {e}")
        return []

    files = sorted([p for ext in file_filter for p in folder_path.rglob(f"*{ext}") if p.is_file() and not p.name.startswith('~$')])
    
    all_docs: List[Document] = []

    def process_shape_collection(shapes, collected_boxes):
        """재귀 함수: 도형 컬렉션을 순회하며 텍스트 상자를 추출합니다."""
        for shape in shapes:
            try:
                if shape.type == 'group':
                    process_shape_collection(shape.group_items, collected_boxes)
                elif shape.text and shape.text.strip():
                    tl = shape.api.TopLeftCell
                    collected_boxes.append({
                        "text": shape.text.strip(),
                        "row": tl.Row,
                        "column": tl.Column
                    })
            except Exception as shape_e:
                logging.warning(f"개별 도형({shape.name}) 처리 중 오류: {shape_e}")

    for xl_file in tqdm(files, desc="선각계열회의록 파싱 중", unit="file"):
        app = None
        workbook = None
        try:
            app = xw.App(visible=False)
            app.display_alerts = False
            workbook = app.books.open(str(xl_file), read_only=True, update_links=False)
            
            shapes_by_sheet = {}
            for sht in workbook.sheets:
                boxes = []
                if sht.shapes:
                    process_shape_collection(sht.shapes, boxes)
                shapes_by_sheet[sht.name] = boxes
            
            workbook.close()
            app.quit()
            workbook, app = None, None

            original_sys_modules = sys.modules.copy()
            parser_module = types.ModuleType("dynamic_parser")
            
            mock_langchain = types.ModuleType('langchain')
            mock_docstore = types.ModuleType('langchain.docstore')
            mock_document_module = types.ModuleType('langchain.docstore.document')
            mock_document_module.Document = Document
            mock_langchain.docstore = mock_docstore
            mock_docstore.document = mock_document_module
            sys.modules.update({
                'langchain': mock_langchain, 
                'langchain.docstore': mock_docstore, 
                'langchain.docstore.document': mock_document_module
            })

            exec(parser_code, parser_module.__dict__)
            
            if hasattr(parser_module, '_parse_workbook'):
                parse_function = getattr(parser_module, '_parse_workbook')
                if documents := parse_function(xl_file, shapes_by_sheet=shapes_by_sheet):
                    all_docs.extend(documents)
            else:
                logging.warning(f"'{logic_path.name}'에 '_parse_workbook' 함수가 없어 '{xl_file.name}'을 건너뜁니다.")

        except Exception as e:
            logging.error(f"'{xl_file.name}' 처리 중 오류 발생: {e}\n{traceback.format_exc()}")
        finally:
            if workbook:
                workbook.close()
            if app:
                app.quit()
            sys.modules.clear()
            sys.modules.update(original_sys_modules)
            
    return all_docs

DOCUMENT_PARSERS: Dict[str, Dict[str, Any]] = {
    "01_선각계열회의록": {
        "engine": sungak_meeting_engine,
        "allowed_extensions": [".xlsx", ".xlsm"],
        "requires_chunking": False,
        "logic_path": "parsers/01_seongak_parser.py"
    },
    "02_일반문서 (Tika)": {
        "engine": default_tika_engine,
        "allowed_extensions": [".pdf", ".docx", ".txt", ".pptx"],
        "requires_chunking": True
    }
}


# ──────────────────────────────────────────────────────────────────────────────
# │ 3. Worker, Main App 클래스
# ──────────────────────────────────────────────────────────────────────────────
class Worker(QThread):
    progress = Signal(int, str)
    log = Signal(str)
    finished = Signal(object)
    error = Signal(str)

    def __init__(self):
        super().__init__()
        self._work_function = None
        self._args = ()
        self._kwargs = {}
        self._is_stop_requested = False

    def start_work(self, func, *args, **kwargs):
        self._work_function = func
        self._args = args
        self._kwargs = kwargs
        self.start()

    def run(self):
        self._is_stop_requested = False
        if not self._work_function:
            return
        pythoncom.CoInitialize()
        try:
            result = self._work_function(*self._args, **self._kwargs)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(f"{e}\n{traceback.format_exc()}")
        finally:
            pythoncom.CoUninitialize()

    def request_stop(self):
        self._is_stop_requested = True

    def is_stop_requested(self):
        return self._is_stop_requested

class LLMToolApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LLM 데이터 처리 GUI v1.8 (메타데이터 로그 수정)")
        self.setGeometry(100, 100, 900, 900)
        self.embedding_model = None
        self.summarize_fn = None

        self.src_dir = Path(__file__).resolve().parent
        self.project_root = self.src_dir.parent if self.src_dir.name == "src" else self.src_dir
        self.bin_dir = self.src_dir / "bin"
        self.qdrant_exe_path = self.bin_dir / "qdrant.exe"
        self.embedding_model_path = self.bin_dir / "bge-m3-local"
        self.summarizer_model_path = self.bin_dir / "kobart-local"
        self.run_all_script_path = self.project_root / "run_all.py"
        self.rules_path = self.project_root / "preprocessing_rules.json"

        self.qdrant_process = None
        self.qdrant_client = None
        self.active_qdrant_service_type = None
        self.hosting_process = None  # 호스팅 프로세스 추가
        self.backend_process = None  # 백엔드 프로세스 추가
        
        # System tray setup
        self.tray_icon = None

        # GUI를 먼저 초기화하여 사용자에게 빠르게 표시
        self.init_ui()
        
        # Setup system tray
        self.setup_system_tray()
        
        # GUI 표시 후 백그라운드에서 모델 로드
        QThread.currentThread().msleep(100)  # GUI 렌더링을 위한 짧은 대기
        self.load_models()
        
        # Qdrant 자동 시작 확인 및 실행
        self.auto_start_qdrant_if_configured()
        
        # 백엔드 자동 시작 확인 및 실행
        self.auto_start_backend_if_configured()
        
        # Check if should start minimized
        self.check_start_minimized()

    def init_ui(self):
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self.mail_app_tab = MailEmbeddingApp(self)
        self.doc_app_tab = DocumentEmbeddingApp(self)
        self.settings_tab = SettingsTab(self)
        self.tabs.addTab(self.mail_app_tab, "  메일 임베딩")
        self.tabs.addTab(self.doc_app_tab, "📄 문서 임베딩")
        self.tabs.addTab(self.settings_tab, "⚙️ 설정")

    def load_models(self):
        try:
            if self.embedding_model_path.exists():
                logging.info(f"임베딩 모델 로드 중: {self.embedding_model_path}")
                self.embedding_model = SentenceTransformer(str(self.embedding_model_path))
                logging.info("임베딩 모델 로드 완료")
        except Exception as e:
            logging.error(f"임베딩 모델 로드 실패: {e}")
            # GUI가 아직 초기화되지 않았을 수 있으므로 메시지박스 표시하지 않음
            
        # kobart 모델 로드 - 옵션사항
        if self.summarizer_model_path.exists():
            try:
                logging.info(f"요약 모델 로드 중: {self.summarizer_model_path}")
                self.summarize_fn = load_summarizer(str(self.summarizer_model_path))
                logging.info("요약 모델 로드 완료")
            except Exception as e:
                logging.warning(f"요약 모델 로드 실패 (선택사항): {e}")
                self.summarize_fn = None
        else:
            logging.info("요약 모델 디렉토리가 없습니다. 요약 기능은 비활성화됩니다.")
            self.summarize_fn = None

    def closeEvent(self, event):
        """창 닫기 이벤트 처리"""
        config = self.load_config()
        
        # Debug logging
        logging.info(f"closeEvent triggered. minimize_to_tray: {config.get('minimize_to_tray', True)}, tray_icon exists: {self.tray_icon is not None}")
        
        # If minimize to tray is enabled and tray is available
        if config.get('minimize_to_tray', True) and self.tray_icon:
            logging.info("Minimizing to tray...")
            event.ignore()
            self.hide_to_tray()
            return
        
        logging.info("Normal close (not minimizing to tray)")
        
        # Otherwise, perform normal cleanup
        # Qdrant 프로세스 정리
        if self.qdrant_process:
            self.stop_qdrant()
        
        # 호스팅 프로세스 정리
        if self.hosting_process and self.hosting_process.poll() is None:
            self.hosting_process.terminate()
            try:
                self.hosting_process.wait(timeout=5)
            except:
                self.hosting_process.kill()
        
        event.accept()

    def start_qdrant(self, service_type: str, path: str):
        if self.qdrant_process:
            QMessageBox.warning(self, "오류", f"다른 Qdrant 서비스가 이미 실행 중입니다 ('{self.active_qdrant_service_type}'용). 먼저 중지해주세요.")
            return
        try:
            data_dir = Path(path)
            data_dir.mkdir(parents=True, exist_ok=True)
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            self.qdrant_process = subprocess.Popen([str(self.qdrant_exe_path)], cwd=str(data_dir), startupinfo=startupinfo)
            self.active_qdrant_service_type = service_type
            
            for tab in [self.mail_app_tab, self.doc_app_tab]:
                if hasattr(tab, 'status_label'):
                    tab.status_label.setText("🟡 시작 중...")
            QApplication.processEvents()
            time.sleep(5)
            
            self.qdrant_client = QdrantClient(host="127.0.0.1", port=6333)
            self.qdrant_client.get_collections()
            self.mail_app_tab.update_ui_for_qdrant_state()
            self.doc_app_tab.update_ui_for_qdrant_state()
        except Exception as e:
            self.stop_qdrant()
            QMessageBox.critical(self, "Qdrant 실행 실패", str(e))

    def stop_qdrant(self):
        if self.qdrant_process:
            self.qdrant_process.terminate()
        self.qdrant_process = None
        self.qdrant_client = None
        self.active_qdrant_service_type = None
        self.mail_app_tab.update_ui_for_qdrant_state()
        self.doc_app_tab.update_ui_for_qdrant_state()

    def auto_start_qdrant_if_configured(self):
        """프로그램 시작 시 설정에 따라 Qdrant를 자동으로 시작"""
        try:
            config_path = self.project_root / "config.json"
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # auto_start_qdrant 설정 확인
                if config.get('auto_start_qdrant', False):
                    # 기본 서비스 타입 결정 (설정에서 지정하거나 기본값 'mail')
                    service_type = config.get('default_qdrant_service', 'mail')
                    
                    # 해당 서비스의 경로 가져오기
                    if service_type == 'mail':
                        qdrant_path = config.get('mail_qdrant_path', '')
                    elif service_type == 'doc':
                        qdrant_path = config.get('doc_qdrant_path', '')
                    else:
                        logging.warning(f"알 수 없는 서비스 타입: {service_type}")
                        return
                    
                    if qdrant_path and Path(qdrant_path).exists():
                        logging.info(f"Qdrant 자동 시작 중 ({service_type} 서비스)...")
                        # 약간의 지연을 두어 GUI가 완전히 로드되도록 함
                        QTimer.singleShot(1000, lambda: self.start_qdrant(service_type, qdrant_path))
                    else:
                        logging.info(f"Qdrant 자동 시작 경로가 유효하지 않음: {qdrant_path}")
                else:
                    logging.info("Qdrant 자동 시작이 비활성화되어 있습니다.")
            else:
                logging.info("config.json 파일이 없어서 Qdrant 자동 시작을 건너뜁니다.")
        except Exception as e:
            logging.error(f"Qdrant 자동 시작 중 오류 발생: {e}")
    
    def auto_start_backend_if_configured(self):
        """프로그램 시작 시 설정에 따라 백엔드를 자동으로 시작"""
        try:
            config_path = self.project_root / "config.json"
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # auto_start_backend 설정 확인
                if config.get('auto_start_backend', False):
                    # 기본 서비스 타입 결정 (설정에서 지정하거나 기본값 'mail')
                    service_type = config.get('default_backend_service', 'mail')
                    
                    logging.info(f"백엔드 자동 시작 예약 중 ({service_type} 서비스)...")
                    # Qdrant가 먼저 시작되도록 더 긴 지연 시간 설정 (3초)
                    QTimer.singleShot(3000, lambda: self._start_backend_service(service_type))
                else:
                    logging.info("백엔드 자동 시작이 비활성화되어 있습니다.")
            else:
                logging.info("config.json 파일이 없어서 백엔드 자동 시작을 건너뜁니다.")
        except Exception as e:
            logging.error(f"백엔드 자동 시작 중 오류 발생: {e}")
    
    def _start_backend_service(self, service_type):
        """백엔드 서비스 자동 시작 헬퍼 메서드"""
        try:
            logging.info(f"백엔드 서비스 시작 중 ({service_type})...")
            
            # 이미 호스팅 프로세스가 실행 중인지 확인
            if self.hosting_process and self.hosting_process.poll() is None:
                logging.info("백엔드가 이미 실행 중입니다.")
                return
            
            # 서비스 타입에 따라 해당 탭의 run_hosting_script 메서드 호출
            if service_type == 'mail':
                if hasattr(self.mail_app_tab, 'run_hosting_script'):
                    # GUI 스레드에서 실행되도록 보장
                    self.mail_app_tab.run_hosting_script()
                    logging.info("메일 백엔드 서비스 시작 명령 실행됨")
                else:
                    logging.error("메일 탭에서 run_hosting_script 메서드를 찾을 수 없습니다.")
            elif service_type == 'doc':
                if hasattr(self.doc_app_tab, 'run_hosting_script'):
                    # GUI 스레드에서 실행되도록 보장
                    self.doc_app_tab.run_hosting_script()
                    logging.info("문서 백엔드 서비스 시작 명령 실행됨")
                else:
                    logging.error("문서 탭에서 run_hosting_script 메서드를 찾을 수 없습니다.")
            else:
                logging.warning(f"알 수 없는 서비스 타입: {service_type}")
        except Exception as e:
            logging.error(f"백엔드 서비스 시작 중 오류: {e}")
    
    def setup_system_tray(self):
        """시스템 트레이 아이콘 설정"""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            logging.warning("시스템 트레이를 사용할 수 없습니다.")
            return
        
        # Create tray icon
        self.tray_icon = QSystemTrayIcon(self)
        
        # Try to use custom icon file first for better visibility
        import os
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'frontend', 'favicon.ico')
        
        if os.path.exists(icon_path):
            # Use custom icon file - this will be more visible in system tray
            tray_icon = QIcon(icon_path)
            logging.info(f"Using custom icon from: {icon_path}")
        else:
            # Fallback to system icons that are more visible
            try:
                # Try different system icons that are more likely to be visible
                # SP_MessageBoxInformation usually has better visibility
                tray_icon = self.style().standardIcon(self.style().StandardPixmap.SP_MessageBoxInformation)
                if tray_icon.isNull():
                    # Try warning icon as it's usually more visible (yellow triangle)
                    tray_icon = self.style().standardIcon(self.style().StandardPixmap.SP_MessageBoxWarning)
                if tray_icon.isNull():
                    # Try critical icon (red X) which is usually visible
                    tray_icon = self.style().standardIcon(self.style().StandardPixmap.SP_MessageBoxCritical)
                if tray_icon.isNull():
                    # Last resort - computer icon
                    tray_icon = self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon)
                logging.info("Using system default icon")
            except:
                # Final fallback - create a simple colored icon programmatically
                from PySide6.QtGui import QPixmap, QPainter, QBrush
                pixmap = QPixmap(16, 16)
                pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(pixmap)
                # Use a bright blue color that will be visible
                painter.setBrush(QBrush(Qt.GlobalColor.blue))
                painter.drawEllipse(0, 0, 16, 16)
                painter.end()
                tray_icon = QIcon(pixmap)
                logging.info("Using generated blue circle icon")
        
        self.tray_icon.setIcon(tray_icon)
        self.tray_icon.setToolTip("HD 현대미포 Gauss-1")
        
        # Create tray menu
        tray_menu = QMenu()
        
        show_action = QAction("열기", self)
        show_action.triggered.connect(self.show_normal_from_tray)
        tray_menu.addAction(show_action)
        
        hide_action = QAction("숨기기", self)
        hide_action.triggered.connect(self.hide_to_tray)
        tray_menu.addAction(hide_action)
        
        tray_menu.addSeparator()
        
        quit_action = QAction("종료", self)
        quit_action.triggered.connect(self.quit_application)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_icon_activated)
        
        # Show tray icon if configured
        config = self.load_config()
        if config.get('minimize_to_tray', True):
            self.tray_icon.show()
    
    def tray_icon_activated(self, reason):
        """트레이 아이콘 클릭 처리"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_from_tray()
    
    def show_from_tray(self):
        """트레이에서 창 표시"""
        self.show()
        self.raise_()
        self.activateWindow()
    
    def show_normal_from_tray(self):
        """트레이에서 창을 일반 상태로 표시"""
        self.showNormal()
        self.raise_()
        self.activateWindow()
    
    def hide_to_tray(self):
        """창을 트레이로 숨기기"""
        logging.info("Hiding main window to tray")
        self.hide()
        if self.tray_icon and self.tray_icon.isSystemTrayAvailable():
            self.tray_icon.showMessage(
                "HD 현대미포 GAUSS-1",
                "프로그램이 시스템 트레이에서 실행 중입니다.",
                QSystemTrayIcon.MessageIcon.Information,
                2000
            )
            logging.info("Tray notification shown")
        else:
            logging.warning("System tray not available or tray_icon is None")
    
    def check_start_minimized(self):
        """시작 시 최소화 확인"""
        config = self.load_config()
        if config.get('start_minimized', False):
            QTimer.singleShot(100, self.hide_to_tray)
    
    def load_config(self):
        """설정 파일 로드"""
        config_path = self.project_root / "config.json"
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def quit_application(self):
        """애플리케이션 완전 종료"""
        logging.info("Quitting application...")
        
        # Stop backend process if running
        if self.backend_process and self.backend_process.poll() is None:
            self.backend_process.terminate()
            try:
                self.backend_process.wait(timeout=5)
            except:
                self.backend_process.kill()
        
        # Stop hosting process
        if self.hosting_process and self.hosting_process.poll() is None:
            self.hosting_process.terminate()
            try:
                self.hosting_process.wait(timeout=5)
            except:
                self.hosting_process.kill()
        
        if self.qdrant_process:
            self.stop_qdrant()
        
        if self.tray_icon:
            self.tray_icon.hide()
        
        QApplication.quit()

# ──────────────────────────────────────────────────────────────────────────────
# │ 4. 탭 위젯 기본 클래스
# ──────────────────────────────────────────────────────────────────────────────
class BaseEmbeddingTab(QWidget):
    def __init__(self, parent: LLMToolApp, service_name: str, log_file_name: str):
        super().__init__(parent)
        self.main_app = parent
        self.service_name = service_name
        self.embedding_log_path = self.main_app.project_root / log_file_name
        self.config_path = self.main_app.project_root / "config.json"
        
        self.worker = Worker()
        self.worker.log.connect(self.add_log)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.on_embedding_finished)
        self.worker.error.connect(self.on_embedding_error)

    def add_log(self, msg):
        self.log_widget.append(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}")

    def update_progress(self, val, msg):
        self.progress_bar.setValue(val)
        self.progress_bar.setFormat(f"{msg} - {val}%")

    def load_config(self, key_map: Dict[str, QLineEdit]):
        try:
            config = json.load(open(self.config_path, 'r', encoding='utf-8')) if self.config_path.exists() else {}
        except (json.JSONDecodeError, OSError):
            config = {}
        for key, widget in key_map.items():
            default_value = str(Path.home() / "Documents" / f"qdrant_{self.service_name}") if 'qdrant_path' in key else ''
            widget.setText(config.get(key, default_value))
            if widget.text():
                self.save_config(key, widget.text())

    def save_config(self, key, value):
        try:
            config = json.load(open(self.config_path, 'r', encoding='utf-8')) if self.config_path.exists() else {}
            config[key] = value
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
        except (json.JSONDecodeError, OSError) as e:
            self.add_log(f"오류: 설정 저장 실패 - {e}")

    def run_qdrant(self):
        self.main_app.start_qdrant(self.service_name, self.hosting_path_input.text())

    def stop_qdrant(self):
        self.main_app.stop_qdrant()

    def clear_qdrant_data(self):
        path_to_clear = self.hosting_path_input.text()
        reply = QMessageBox.question(self, '초기화 확인', f"'{path_to_clear}'의 모든 Qdrant 데이터와 '{self.embedding_log_path.name}' 기록을 삭제하시겠습니까?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if self.main_app.active_qdrant_service_type == self.service_name:
                self.stop_qdrant()
                time.sleep(1)
            try:
                if Path(path_to_clear).exists():
                    shutil.rmtree(path_to_clear)
                if self.embedding_log_path.exists():
                    os.remove(self.embedding_log_path)
                QMessageBox.information(self, "성공", "데이터와 기록 로그가 삭제되었습니다.")
            except Exception as e:
                QMessageBox.critical(self, "삭제 실패", f"데이터 삭제 중 오류: {e}")

    def on_embedding_finished(self, result):
        if result.get("stopped"):
            self.add_log("🛑 작업이 사용자에 의해 중지되었습니다.")
        self.add_log(f"✅ 작업 완료! 신규 {result.get('p', 0)}개, 중복/건너뜀 {result.get('s', 0)}개, 총 {result.get('c', 0)}개 청크/문서 저장됨.")
        self.set_buttons_enabled(True)
        self.update_progress(100, "완료")

    def on_embedding_error(self, error_message):
        self.add_log(f"❌ 오류 발생: {error_message}")
        self.set_buttons_enabled(True)
        self.update_progress(0, "오류")

    def _load_processed_ids(self) -> Set[str]:
        if not self.embedding_log_path.exists():
            return set()
        try:
            with open(self.embedding_log_path, 'r', encoding='utf-8') as f:
                return {line.strip() for line in f if line.strip()}
        except Exception as e:
            self.worker.log.emit(f"기록 로드 실패: {e}")
            return set()

    def _log_processed_ids(self, ids: List[str]):
        try:
            with open(self.embedding_log_path, 'a', encoding='utf-8') as f:
                for item_id in ids:
                    f.write(f"{item_id}\n")
        except Exception as e:
            self.worker.log.emit(f"기록 저장 실패: {e}")

    def _upload_batch(self, collection, batch, id_batch):
        if not batch:
            return
        self.main_app.qdrant_client.upsert(collection_name=collection, points=batch, wait=True)
        self._log_processed_ids(id_batch)
        self.worker.log.emit(f"   - {len(id_batch)}개 항목({len(batch)} 청크) DB 업로드 및 로그 기록 완료.")

    def _ensure_collection_exists(self, name: str):
        try:
            self.main_app.qdrant_client.get_collection(collection_name=name)
        except Exception:
            self.worker.log.emit(f"ℹ️ 컬렉션 '{name}'이(가) 없어 새로 생성합니다.")
            try:
                model = self.main_app.embedding_model
                self.main_app.qdrant_client.create_collection(
                    collection_name=name,
                    vectors_config=models.VectorParams(size=model.get_sentence_embedding_dimension(), distance=models.Distance.COSINE)
                )
            except Exception as e:
                # Check if it's a "collection already exists" error (409 Conflict)
                error_msg = str(e).lower()
                if "already exists" in error_msg or "409" in str(e):
                    self.worker.log.emit(f"ℹ️ 컬렉션 '{name}'이(가) 이미 존재합니다. 계속 진행합니다.")
                else:
                    raise Exception(f"컬렉션 생성에 실패했습니다: {e}")

    def _handle_fresh_start(self, fresh_start: bool) -> bool:
        if not fresh_start:
            return True
        reply = QMessageBox.question(self, '새롭게 임베딩 확인', "기존 기록을 지우고 처음부터 다시 시작하시겠습니까?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No:
            return False
        try:
            if self.embedding_log_path.exists():
                os.remove(self.embedding_log_path)
            self.add_log("✅ 기존 임베딩 기록을 삭제했습니다.")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"기록 파일 삭제 중 오류: {e}")
            return False
        self.log_widget.clear()
        return True

    def _start_embedding_task(self, task_name, *args):
        self.add_log(f"'{task_name}' 작업을 시작합니다...")
        self.set_buttons_enabled(False)
        self.worker.start_work(getattr(self, task_name), *args)

    def request_stop_embedding(self):
        self.add_log("🛑 중지 요청됨. 현재 작업 완료 후 중지합니다...")
        self.worker.request_stop()
        self.stop_embedding_btn.setEnabled(False)

# ──────────────────────────────────────────────────────────────────────────────
# │ 5. 메일 임베딩 탭 (변경 없음)
# ──────────────────────────────────────────────────────────────────────────────
class MailEmbeddingApp(BaseEmbeddingTab):
    def __init__(self, parent: LLMToolApp):
        super().__init__(parent, 'mail', 'embedding_log_mail.txt')
        self.outlook_namespace = None
        
        self.connection_worker = Worker()
        self.connection_worker.finished.connect(self._on_outlook_connection_finished)
        self.connection_worker.error.connect(self._on_outlook_connection_error)
        
        self.summarizer = self.main_app.summarize_fn
        
        self.init_ui()
        self.load_config({'mail_qdrant_path': self.hosting_path_input, 'local_msg_path': self.msg_path_display})

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)
        
        main_layout.addWidget(self._create_qdrant_group())
        main_layout.addWidget(self._create_live_mail_group())
        main_layout.addWidget(self._create_local_mail_group())
        main_layout.addWidget(self._create_log_group())
        main_layout.addWidget(self._create_endpoint_settings_group())
        main_layout.addWidget(self._create_hosting_group())
        
        self.update_ui_for_qdrant_state()
        self.load_endpoint_settings()

    def _create_qdrant_group(self):
        group = QGroupBox("Qdrant 서버 (메일용)")
        layout = QGridLayout()
        layout.addWidget(QLabel("저장 경로:"), 0, 0)
        self.hosting_path_input = QLineEdit()
        self.hosting_path_input.editingFinished.connect(lambda: self.save_config('mail_qdrant_path', self.hosting_path_input.text()))
        layout.addWidget(self.hosting_path_input, 0, 1)
        self.browse_btn = QPushButton("...")
        self.browse_btn.setFixedWidth(40)
        self.browse_btn.clicked.connect(self.browse_hosting_path)
        layout.addWidget(self.browse_btn, 0, 2)
        
        self.status_label = QLabel("🔴 중지됨")
        layout.addWidget(self.status_label, 1, 0, 1, 3)
        
        btn_layout = QHBoxLayout()
        self.run_btn = QPushButton("실행")
        self.run_btn.clicked.connect(self.run_qdrant)
        self.stop_btn = QPushButton("중지")
        self.stop_btn.clicked.connect(self.stop_qdrant)
        self.clear_btn = QPushButton("데이터 초기화")
        self.clear_btn.clicked.connect(self.clear_qdrant_data)
        self.recover_log_btn = QPushButton("기록 복구")
        self.recover_log_btn.clicked.connect(self.recover_history_from_db)
        
        btn_layout.addWidget(self.run_btn)
        btn_layout.addWidget(self.stop_btn)
        btn_layout.addWidget(self.clear_btn)
        btn_layout.addWidget(self.recover_log_btn)
        
        layout.addLayout(btn_layout, 2, 0, 1, 3)
        group.setLayout(layout)
        return group

    def _create_live_mail_group(self):
        group = QGroupBox("라이브 Outlook 처리")
        layout = QVBoxLayout()
        
        conn_layout = QHBoxLayout()
        self.conn_status_label = QLabel("🔴 연결 안 됨")
        self.conn_btn = QPushButton("Outlook 연결")
        self.conn_btn.clicked.connect(self.connect_outlook)
        conn_layout.addWidget(self.conn_status_label)
        conn_layout.addWidget(self.conn_btn)
        conn_layout.addStretch()
        layout.addLayout(conn_layout)
        
        self.folder_tree = QTreeWidget()
        self.folder_tree.setHeaderLabel("처리할 폴더 선택")
        layout.addWidget(self.folder_tree)
        
        folder_select_layout = QHBoxLayout()
        self.select_all_btn = QPushButton("전체 선택/해제")
        self.select_all_btn.clicked.connect(self.toggle_all_folders)
        folder_select_layout.addWidget(self.select_all_btn)
        folder_select_layout.addStretch()
        layout.addLayout(folder_select_layout)
        
        options_layout = QHBoxLayout()
        self.include_body_check = QCheckBox("메일 본문 포함")
        self.include_body_check.setChecked(True)
        self.include_attachments_check = QCheckBox("첨부 파일 포함")
        self.include_attachments_check.setChecked(True)
        options_layout.addWidget(self.include_body_check)
        options_layout.addWidget(self.include_attachments_check)
        options_layout.addStretch()
        layout.addLayout(options_layout)
        
        embedding_layout = QHBoxLayout()
        self.continue_live_btn = QPushButton("➡️ 이어서 임베딩")
        self.continue_live_btn.clicked.connect(lambda: self.start_live_embedding(fresh_start=False))
        self.new_live_btn = QPushButton("🔄 새롭게 임베딩")
        self.new_live_btn.clicked.connect(lambda: self.start_live_embedding(fresh_start=True))
        embedding_layout.addWidget(self.continue_live_btn, 2)
        embedding_layout.addWidget(self.new_live_btn, 1)
        layout.addLayout(embedding_layout)
        
        group.setLayout(layout)
        return group

    def _create_local_mail_group(self):
        group = QGroupBox("로컬 이메일 파일(.msg) 처리")
        layout = QGridLayout()
        
        layout.addWidget(QLabel(".msg 폴더:"), 0, 0)
        self.msg_path_display = QLineEdit()
        self.msg_path_display.editingFinished.connect(lambda: self.save_config('local_msg_path', self.msg_path_display.text()))
        layout.addWidget(self.msg_path_display, 0, 1)
        
        self.msg_browse_btn = QPushButton("...")
        self.msg_browse_btn.setFixedWidth(40)
        self.msg_browse_btn.clicked.connect(self.select_msg_folder)
        layout.addWidget(self.msg_browse_btn, 0, 2)
        
        embedding_layout = QHBoxLayout()
        self.continue_local_btn = QPushButton("➡️ 이어서 임베딩")
        self.continue_local_btn.clicked.connect(lambda: self.start_local_msg_embedding(fresh_start=False))
        self.new_local_btn = QPushButton("🔄 새롭게 임베딩")
        self.new_local_btn.clicked.connect(lambda: self.start_local_msg_embedding(fresh_start=True))
        embedding_layout.addWidget(self.continue_local_btn, 2)
        embedding_layout.addWidget(self.new_local_btn, 1)
        
        layout.addLayout(embedding_layout, 1, 0, 1, 3)
        group.setLayout(layout)
        return group
    
    def _create_log_group(self):
        group = QGroupBox("처리 로그")
        layout = QVBoxLayout()
        
        self.progress_bar = QProgressBar()
        self.log_widget = QTextEdit()
        self.log_widget.setReadOnly(True)
        self.stop_embedding_btn = QPushButton("🛑 임베딩 중지")
        self.stop_embedding_btn.clicked.connect(self.request_stop_embedding)
        self.stop_embedding_btn.setEnabled(False)
        
        log_ctrl_layout = QHBoxLayout()
        log_ctrl_layout.addWidget(self.progress_bar)
        log_ctrl_layout.addWidget(self.stop_embedding_btn)
        
        layout.addLayout(log_ctrl_layout)
        layout.addWidget(self.log_widget)
        group.setLayout(layout)
        return group
    
    def _create_endpoint_settings_group(self):
        """엔드포인트 설정 그룹 생성"""
        group = QGroupBox("서버 엔드포인트 설정")
        layout = QGridLayout()
        
        # Qdrant 설정
        layout.addWidget(QLabel("Qdrant 서버:"), 0, 0)
        self.mail_qdrant_host = QLineEdit("127.0.0.1")
        self.mail_qdrant_port = QLineEdit("6333")
        layout.addWidget(self.mail_qdrant_host, 0, 1)
        layout.addWidget(QLabel(":"), 0, 2)
        layout.addWidget(self.mail_qdrant_port, 0, 3)
        
        # Ollama 설정
        layout.addWidget(QLabel("Ollama 서버:"), 1, 0)
        self.mail_ollama_host = QLineEdit("127.0.0.1")
        self.mail_ollama_port = QLineEdit("11434")
        layout.addWidget(self.mail_ollama_host, 1, 1)
        layout.addWidget(QLabel(":"), 1, 2)
        layout.addWidget(self.mail_ollama_port, 1, 3)
        
        # 저장 버튼
        save_btn = QPushButton("💾 설정 저장")
        save_btn.clicked.connect(self.save_endpoint_settings)
        layout.addWidget(save_btn, 2, 0, 1, 4)
        
        group.setLayout(layout)
        return group
    
    def save_endpoint_settings(self):
        """엔드포인트 설정 저장"""
        config = json.load(open(self.config_path, 'r', encoding='utf-8')) if self.config_path.exists() else {}
        
        if 'endpoints' not in config:
            config['endpoints'] = {}
        
        config['endpoints']['mail'] = {
            'qdrant_host': self.mail_qdrant_host.text(),
            'qdrant_port': self.mail_qdrant_port.text(),
            'ollama_host': self.mail_ollama_host.text(),
            'ollama_port': self.mail_ollama_port.text()
        }
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        QMessageBox.information(self, "저장", "설정이 저장되었습니다.")
    
    def load_endpoint_settings(self):
        """엔드포인트 설정 로드"""
        if self.config_path.exists():
            config = json.load(open(self.config_path, 'r', encoding='utf-8'))
            endpoints = config.get('endpoints', {}).get('mail', {})
            
            self.mail_qdrant_host.setText(endpoints.get('qdrant_host', '127.0.0.1'))
            self.mail_qdrant_port.setText(endpoints.get('qdrant_port', '6333'))
            self.mail_ollama_host.setText(endpoints.get('ollama_host', '127.0.0.1'))
            self.mail_ollama_port.setText(endpoints.get('ollama_port', '11434'))
    
    def _create_hosting_group(self):
        group = QGroupBox("Frontend & Backend 호스팅")
        layout = QVBoxLayout()
        label = QLabel("아래 버튼을 누르면 메일 데이터 기반 전체 RAG 웹 앱 서버를 실행합니다.")
        label.setWordWrap(True)
        
        # 버튼 레이아웃
        btn_layout = QHBoxLayout()
        self.run_all_btn = QPushButton("🚀 전체 앱 실행 (메일용)")
        self.run_all_btn.clicked.connect(self.run_hosting_script)
        self.browser_btn = QPushButton("🌐 브라우저 열기")
        self.browser_btn.clicked.connect(self.open_browser)
        
        btn_layout.addWidget(self.run_all_btn)
        btn_layout.addWidget(self.browser_btn)
        
        layout.addWidget(label)
        layout.addLayout(btn_layout)
        group.setLayout(layout)
        return group
    
    def open_browser(self):
        """브라우저에서 프론트엔드 열기"""
        try:
            # 프론트엔드 서버가 실행 중인지 확인
            response = requests.get("http://localhost:8001", timeout=1)
            if response.status_code == 200:
                webbrowser.open("http://localhost:8001")
                self.add_log("브라우저에서 프론트엔드를 열었습니다.")
            else:
                QMessageBox.warning(self, "서버 오류", "프론트엔드 서버가 응답하지 않습니다.")
        except:
            QMessageBox.warning(self, "서버 없음", "프론트엔드 서버가 실행되지 않았습니다.\n먼저 '전체 앱 실행'을 클릭하세요.")

    def browse_hosting_path(self):
        if folder := QFileDialog.getExistingDirectory(self, "Qdrant 저장 경로 선택"):
            self.hosting_path_input.setText(folder)
            self.save_config('mail_qdrant_path', folder)
            
    def select_msg_folder(self):
        if folder := QFileDialog.getExistingDirectory(self, ".msg 파일 폴더 선택"):
            self.msg_path_display.setText(folder)
            self.save_config('local_msg_path', folder)

    def update_ui_for_qdrant_state(self):
        is_running = self.main_app.qdrant_client is not None
        is_my_service = is_running and self.main_app.active_qdrant_service_type == self.service_name
        
        self.run_btn.setEnabled(not is_running)
        self.stop_btn.setEnabled(is_my_service)
        self.hosting_path_input.setEnabled(not is_running)
        self.browse_btn.setEnabled(not is_running)
        self.clear_btn.setEnabled(not is_running) # 서버 중지 상태에서만 초기화 가능
        
        self.set_buttons_enabled(True) # This will handle embedding buttons
        
        if is_running:
            self.status_label.setText(f"🟢 실행 중" if is_my_service else "⚪️ (문서용 서버 실행 중)")
        else:
            self.status_label.setText("🔴 중지됨")
    
    def set_buttons_enabled(self, enabled: bool):
        is_my_service = self.main_app.qdrant_client is not None and self.main_app.active_qdrant_service_type == self.service_name
        can_embed = enabled and is_my_service
        live_ready = can_embed and self.outlook_namespace is not None
        
        self.continue_live_btn.setEnabled(live_ready)
        self.new_live_btn.setEnabled(live_ready)
        self.continue_local_btn.setEnabled(can_embed)
        self.new_local_btn.setEnabled(can_embed)
        
        self.stop_embedding_btn.setEnabled(not enabled)
        self.recover_log_btn.setEnabled(enabled and is_my_service)
        self.conn_btn.setEnabled(enabled)

    def connect_outlook(self):
        self.conn_status_label.setText("🟡 연결 시도 중...")
        self.conn_btn.setEnabled(False)
        self.connection_worker.start_work(self._connect_outlook_task)

    def _connect_outlook_task(self):
        mapi = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
        stores_data = []
        def _traverse(folders, parent_list):
            for folder in folders:
                try:
                    folder_info = {
                        'name': folder.Name, 
                        'id': folder.EntryID, 
                        'item_count': folder.Items.Count if folder.Items else 0, 
                        'children': [], 
                        'path': folder.FolderPath
                    }
                    parent_list.append(folder_info)
                    if folder.Folders.Count > 0:
                        _traverse(folder.Folders, folder_info['children'])
                except Exception:
                    pass
        for store in mapi.Stores:
            try:
                root = store.GetRootFolder()
                store_info = {'name': root.Name, 'id': root.EntryID, 'children': []}
                _traverse(root.Folders, store_info['children'])
                stores_data.append(store_info)
            except Exception as e:
                print(f"스토어 처리 오류: {e}")
        return stores_data
    
    def _on_outlook_connection_finished(self, result):
        if not result:
            self._on_outlook_connection_error("편지함을 찾을 수 없습니다.")
            return
        if not self.outlook_namespace:
            self.outlook_namespace = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
        self.conn_status_label.setText("🟢 연결됨")
        self.conn_btn.setText("폴더 새로고침")
        self.conn_btn.setEnabled(True)
        self.populate_folders(result)
        self.update_ui_for_qdrant_state()

    def _on_outlook_connection_error(self, error_msg):
        self.conn_status_label.setText("🔴 연결 실패")
        self.conn_btn.setEnabled(True)
        self.outlook_namespace = None
        QMessageBox.critical(self, "Outlook 연결 실패", f"오류: {error_msg}")

    def populate_folders(self, stores_data):
        self.folder_tree.clear()
        def _add_items(parent_item, subfolders):
            for info in subfolders:
                child = QTreeWidgetItem(parent_item)
                child.setText(0, f"{info['name']} ({info.get('item_count', 0)})")
                child.setData(0, Qt.UserRole, info['id'])
                child.setToolTip(0, info.get('path', ''))
                child.setCheckState(0, Qt.Unchecked)
                if info.get('children'):
                    _add_items(child, info['children'])
        for store_data in stores_data:
            root = QTreeWidgetItem(self.folder_tree)
            root.setText(0, store_data['name'])
            root.setData(0, Qt.UserRole, store_data.get('id'))
            root.setExpanded(True)
            _add_items(root, store_data.get('children', []))
            
    def toggle_all_folders(self):
        is_any_unchecked = any(it.value().checkState(0) == Qt.Unchecked for it in QTreeWidgetItemIterator(self.folder_tree))
        new_state = Qt.Checked if is_any_unchecked else Qt.Unchecked
        it = QTreeWidgetItemIterator(self.folder_tree)
        while it.value():
            it.value().setCheckState(0, new_state)
            it += 1
            
    def _get_selected_folder_ids(self) -> List[str]:
        return [it.value().data(0, Qt.UserRole) for it in QTreeWidgetItemIterator(self.folder_tree, QTreeWidgetItemIterator.IteratorFlag.Checked) if it.value().data(0, Qt.UserRole)]

    def start_live_embedding(self, fresh_start: bool):
        if not (selected_ids := self._get_selected_folder_ids()):
            QMessageBox.warning(self, "경고", "처리할 폴더를 선택해주세요.")
            return
        if not self._handle_fresh_start(fresh_start):
            return
        self._start_embedding_task('_live_embedding_task', selected_ids, self.include_body_check.isChecked(), self.include_attachments_check.isChecked())

    def start_local_msg_embedding(self, fresh_start: bool):
        folder_path = self.msg_path_display.text()
        if not folder_path or not Path(folder_path).is_dir():
            QMessageBox.warning(self, "경고", "유효한 .msg 폴더를 선택해주세요.")
            return
        if not self._handle_fresh_start(fresh_start):
            return
        self._start_embedding_task('_local_msg_embedding_task', folder_path)
        
    def recover_history_from_db(self):
        if not self.main_app.qdrant_client:
            QMessageBox.warning(self, "오류", "Qdrant 서버가 실행 중이 아닙니다.")
            return
        reply = QMessageBox.question(self, "기록 복구 확인", "DB에서 메일 ID를 스캔하여 로컬 기록 파일을 덮어씁니다.\n계속하시겠습니까?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No:
            return
        self.add_log("DB 기반 기록 복구를 시작합니다...")
        self.set_buttons_enabled(False)
        self.worker.start_work(self._recover_history_task)

    def _recover_history_task(self):
        collection_name = "my_documents"
        try:
            self.main_app.qdrant_client.get_collection(collection_name=collection_name)
        except Exception:
            self.worker.error.emit(f"오류: '{collection_name}' 컬렉션이 존재하지 않습니다.")
            return {"p": 0, "s": 0, "c": 0}
            
        processed_ids = set()
        next_offset = None
        total_scanned = 0
        self.worker.progress.emit(0, "DB 스캔 중...")
        while True:
            if self.worker.is_stop_requested():
                return {"p": len(processed_ids), "s": total_scanned, "c": 0, "stopped": True}
            try:
                records, next_page_offset = self.main_app.qdrant_client.scroll(
                    collection_name=collection_name,
                    limit=2000,
                    offset=next_offset,
                    with_payload=["mail_id"],
                    with_vectors=False
                )
                for record in records:
                    if mail_id := record.payload.get("mail_id"):
                        processed_ids.add(mail_id)
                total_scanned += len(records)
                self.worker.log.emit(f"{total_scanned}개 스캔, 고유 ID {len(processed_ids)}개 발견...")
                if next_page_offset is None:
                    break
                next_offset = next_page_offset
            except Exception as e:
                self.worker.error.emit(f"DB 스캔 중 오류: {e}")
                return {"p": len(processed_ids), "s": total_scanned, "c": 0}

        try:
            with open(self.embedding_log_path, 'w', encoding='utf-8') as f:
                for item_id in sorted(list(processed_ids)):
                    f.write(f"{item_id}\n")
            self.worker.log.emit(f"총 {len(processed_ids)}개의 고유 ID를 복구하여 로그 파일에 저장했습니다.")
        except Exception as e:
            self.worker.error.emit(f"로그 파일 저장 중 오류: {e}")
            
        return {"p": len(processed_ids), "s": total_scanned, "c": 0}

    def _generate_points(self, model, meta, text) -> List[models.PointStruct]:
        return [models.PointStruct(id=str(uuid.uuid4()), vector=emb.tolist(), payload={**meta, "text": chunk})
                for chunk, emb in zip([text], model.encode([text], show_progress_bar=False))]

    def _live_embedding_task(self, folder_ids, include_body, include_attachments):
        collection_name = "my_documents"
        try:
            self._ensure_collection_exists(collection_name)
        except Exception as e:
            self.worker.error.emit(str(e))
            return {"p": 0, "s": 0, "c": 0}
        
        cleaner = TextCleaner(self.main_app.rules_path)
        mapi = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
        newly_proc, skipped_count, total_chunks = 0, 0, 0
        qdrant_batch, id_batch = [], []
        processed_ids = self._load_processed_ids()
        attachment_base_dir = self.main_app.project_root / "email_attachments"
        model = self.main_app.embedding_model
        summarizer = self.main_app.summarize_fn
        
        folders_to_process = [mapi.GetFolderFromID(fid) for fid in folder_ids]
        total_mail_count = sum(f.Items.Count for f in folders_to_process if hasattr(f, 'Items'))
        processed_mail_count = 0

        for folder in folders_to_process:
            if self.worker.is_stop_requested(): break
            try:
                items = folder.Items
                try: items.Sort("[ReceivedTime]", True)
                except Exception: self.worker.log.emit(f"폴더 '{folder.Name}' 정렬 불가.")
                
                self.worker.log.emit(f"폴더 처리 시작: {folder.Name} ({items.Count}개)")
                for mail in items:
                    processed_mail_count += 1
                    if self.worker.is_stop_requested(): break
                    self.worker.progress.emit(int((processed_mail_count / total_mail_count) * 100) if total_mail_count > 0 else 0, f"메일 처리 중 ({processed_mail_count}/{total_mail_count})")
                    try:
                        if not hasattr(mail, 'EntryID'): continue
                        if (item_id := mail.EntryID) in processed_ids:
                            skipped_count += 1
                            continue
                        
                        points_for_mail = []
                        subject = getattr(mail, 'Subject', 'N/A')
                        meta = {
                            "mail_subject": subject, "subject": subject, 
                            "sender": keep_name_only(getattr(mail, 'SenderName', 'N/A')), 
                            "sent_date": mail.SentOn.strftime('%Y-%m-%d %H:%M:%S') if hasattr(mail, 'SentOn') and mail.SentOn else 'N/A',  # Added sent_date for backend compatibility
                            "date": mail.SentOn.strftime('%Y-%m-%d %H:%M:%S') if hasattr(mail, 'SentOn') and mail.SentOn else 'N/A',  # Keep both for backward compatibility
                            "to": keep_name_only(getattr(mail, 'To', 'N/A')), 
                            "cc": keep_name_only(getattr(mail, 'CC', 'N/A')), 
                            "mail_id": item_id, "link": f"outlook://{item_id}"
                        }
                        
                        if include_body and mail.Body:
                            chunks, summary = preprocess_mail_for_rag(body_text=mail.Body, meta=meta, cleaner=cleaner, summarize_fn=summarizer)
                            if chunks:
                                points_for_mail.extend(self._generate_points(model, {**meta, "summary": summary, "source_type": "email_body"}, chunks[0]))

                        if include_attachments and mail.Attachments.Count > 0:
                            for att in mail.Attachments:
                                if att.Size == 0: continue
                                save_path = attachment_base_dir / sanitize_filename(f"{meta['subject']}_{att.FileName}")
                                try:
                                    save_path.parent.mkdir(parents=True, exist_ok=True)
                                    att.SaveAsFile(str(save_path))
                                    if text_content := unicodedata.normalize("NFKC", (tika_parser.from_file(str(save_path)) or {}).get("content", "") or ""):
                                        att_summary = textwrap.shorten(text_content, width=120, placeholder="…")
                                        for chunk in chunk_by(text_content, 800, 250):
                                            att_meta = {**meta, "summary": att_summary, "source_type": "email_attachment", "file_name": att.FileName}
                                            points_for_mail.extend(self._generate_points(model, att_meta, chunk))
                                finally:
                                    if save_path.exists():
                                        os.remove(save_path)
                        
                        if points_for_mail:
                            qdrant_batch.extend(points_for_mail)
                            id_batch.append(item_id)
                            newly_proc += 1

                        if len(id_batch) >= QDRANT_BATCH_SIZE:
                            self._upload_batch(collection_name, qdrant_batch, id_batch)
                            total_chunks += len(qdrant_batch)
                            qdrant_batch.clear()
                            id_batch.clear()
                    except Exception as e:
                        self.worker.log.emit(f"개별 메일 처리 오류: {getattr(mail, 'Subject', 'N/A')} - {e}")
                if self.worker.is_stop_requested(): break
            except Exception as e:
                self.worker.log.emit(f"폴더 처리 오류: {folder.Name} - {e}")
                
        if id_batch:
            self._upload_batch(collection_name, qdrant_batch, id_batch)
            total_chunks += len(qdrant_batch)
        return {"p": newly_proc, "s": skipped_count, "c": total_chunks, "stopped": self.worker.is_stop_requested()}

    def _local_msg_embedding_task(self, folder_path):
        collection_name = "my_documents"
        try:
            self._ensure_collection_exists(collection_name)
        except Exception as e:
            self.worker.error.emit(str(e))
            return {"p": 0, "s": 0, "c": 0}
            
        model = self.main_app.embedding_model
        cleaner = TextCleaner(self.main_app.rules_path)
        processed_ids = self._load_processed_ids()
        
        # Find both .msg and .eml files
        msg_files = sorted([p for p in Path(folder_path).rglob("*.msg")], key=os.path.getmtime, reverse=True)
        eml_files = sorted([p for p in Path(folder_path).rglob("*.eml")], key=os.path.getmtime, reverse=True)
        files = sorted(msg_files + eml_files, key=os.path.getmtime, reverse=True)
        
        newly_proc, skipped, total_chunks = 0, 0, 0
        qdrant_batch, id_batch = [], []

        for i, file_path in enumerate(files):
            if self.worker.is_stop_requested(): break
            
            # Update progress message based on file type
            file_ext = file_path.suffix.lower()
            self.worker.progress.emit(int(((i + 1) / len(files)) * 100) if files else 100, f"{file_ext} 파일 처리 중 ({i+1}/{len(files)})")
            
            item_id = str(file_path.resolve())
            if item_id in processed_ids:
                skipped += 1
                continue
            try:
                points_for_mail = []
                
                # Handle .msg files
                if file_ext == '.msg':
                    with extract_msg.Message(file_path) as msg:
                        subject = msg.subject
                        meta = {
                            "mail_subject": subject, "subject": subject,
                            "sender": keep_name_only(msg.sender), 
                            "sent_date": msg.date,  # Added sent_date for backend compatibility
                            "date": msg.date,  # Keep both for backward compatibility
                            "to": keep_name_only(msg.to), "cc": keep_name_only(msg.cc),
                            "mail_id": item_id, "link": "file:///" + str(Path(item_id).resolve()).replace("\\", "/")
                        }
                        if msg.body:
                            chunks, summary = preprocess_mail_for_rag(body_text=msg.body, meta=meta, cleaner=cleaner, summarize_fn=self.main_app.summarize_fn)
                            if chunks:
                                points_for_mail.extend(self._generate_points(model, {**meta, "summary": summary, "source_type": "email_body"}, chunks[0]))
                
                # Handle .eml files
                elif file_ext == '.eml':
                    eml_data = parse_eml_file(file_path)
                    if eml_data:
                        subject = eml_data['subject']
                        meta = {
                            "mail_subject": subject, "subject": subject,
                            "sender": keep_name_only(eml_data['sender']), 
                            "sent_date": eml_data['date'],  # Added sent_date for backend compatibility
                            "date": eml_data['date'],  # Keep both for backward compatibility
                            "to": keep_name_only(eml_data['to']), 
                            "cc": keep_name_only(eml_data.get('cc', '')),
                            "mail_id": item_id, 
                            "link": "file:///" + str(Path(item_id).resolve()).replace("\\", "/")
                        }
                        if eml_data['body']:
                            chunks, summary = preprocess_mail_for_rag(body_text=eml_data['body'], meta=meta, cleaner=cleaner, summarize_fn=self.main_app.summarize_fn)
                            if chunks:
                                points_for_mail.extend(self._generate_points(model, {**meta, "summary": summary, "source_type": "email_body"}, chunks[0]))
                
                if points_for_mail:
                    qdrant_batch.extend(points_for_mail)
                    id_batch.append(item_id)
                    newly_proc += 1

                if len(id_batch) >= QDRANT_BATCH_SIZE:
                    self._upload_batch(collection_name, qdrant_batch, id_batch)
                    total_chunks += len(qdrant_batch)
                    qdrant_batch.clear()
                    id_batch.clear()
            except Exception as e:
                self.worker.log.emit(f"파일 처리 오류: {file_path.name} - {e}")
                
        if id_batch:
            self._upload_batch(collection_name, qdrant_batch, id_batch)
            total_chunks += len(qdrant_batch)
        return {"p": newly_proc, "s": skipped, "c": total_chunks, "stopped": self.worker.is_stop_requested()}

    def run_hosting_script(self):
        script_path = self.main_app.run_all_script_path
        if not Path(script_path).exists():
            QMessageBox.critical(self, "스크립트 없음", f"실행할 스크립트를 찾을 수 없습니다:\n{script_path}")
            return
        
        # 이미 실행 중인지 확인
        if hasattr(self.main_app, 'hosting_process') and self.main_app.hosting_process:
            if self.main_app.hosting_process.poll() is None:
                QMessageBox.warning(self, "이미 실행 중", "서버가 이미 실행 중입니다.")
                return
        
        try:
            config = json.load(open(self.config_path, 'r', encoding='utf-8')) if self.config_path.exists() else {}
            qdrant_path_arg = config.get('mail_qdrant_path', str(self.main_app.project_root / "qdrant_mail"))
            
            # Qdrant가 실행 중이지 않다면 자동 시작
            if not self.main_app.qdrant_client:
                self.add_log("Qdrant 서버가 실행되지 않아 자동 시작합니다...")
                self.main_app.start_qdrant('mail', qdrant_path_arg)
                
                # Qdrant가 시작될 때까지 대기
                time.sleep(2)
                
                # Qdrant 시작 확인
                if not self.main_app.qdrant_client:
                    QMessageBox.warning(self, "Qdrant 시작 실패", "Qdrant 서버를 시작할 수 없습니다. 수동으로 시작해주세요.")
                    return
                else:
                    self.add_log("Qdrant 서버 자동 시작 완료")
            
            # 가상환경 Python 사용
            venv_python = self.main_app.project_root / "venv" / "Scripts" / "python.exe"
            if not venv_python.exists():
                QMessageBox.critical(self, "가상환경 오류", "가상환경을 찾을 수 없습니다. INSTALL.bat을 먼저 실행하세요.")
                return
            
            # 프로세스 시작
            self.main_app.hosting_process = subprocess.Popen(
                [str(venv_python), str(script_path), f"--qdrant_path={qdrant_path_arg}", f"--service_type=mail"],
                creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
            )
            
            # 프로세스가 실제로 시작되었는지 확인
            time.sleep(1)  # 프로세스 시작 대기
            if self.main_app.hosting_process.poll() is None:
                # 프로세스가 정상적으로 실행 중
                self.add_log("전체 앱 서버가 성공적으로 시작되었습니다.")
                
                # 버튼 텍스트 변경
                self.run_all_btn.setText("⏹ 전체 앱 중지 (메일용)")
                self.run_all_btn.clicked.disconnect()
                self.run_all_btn.clicked.connect(self.stop_hosting_script)
                
                QMessageBox.information(self, "실행", "서버가 시작되었습니다.\n브라우저에서 http://localhost:8001 을 열어주세요.")
            else:
                # 프로세스가 즉시 종료됨
                self.add_log("프로세스 시작 실패 - 프로세스가 즉시 종료되었습니다.")
                self.main_app.hosting_process = None
                QMessageBox.critical(self, "실행 실패", "서버를 시작할 수 없습니다. 로그를 확인해주세요.")
                
        except Exception as e:
            self.add_log(f"서버 시작 중 오류 발생: {e}")
            # 오류 발생 시 버튼 상태 복구
            self.main_app.hosting_process = None
            self.run_all_btn.setText("🚀 전체 앱 실행 (메일용)")
            QMessageBox.critical(self, "실행 실패", f"스크립트 실행 중 오류가 발생했습니다: {e}")
    
    def stop_hosting_script(self):
        """호스팅 스크립트 중지 - 모든 자식 프로세스 포함"""
        if hasattr(self.main_app, 'hosting_process') and self.main_app.hosting_process:
            if self.main_app.hosting_process.poll() is None:
                # Windows에서 프로세스 트리 전체 종료
                if sys.platform == 'win32':
                    try:
                        # taskkill 명령어로 프로세스 트리 전체 종료
                        subprocess.call(['taskkill', '/F', '/T', '/PID', str(self.main_app.hosting_process.pid)], 
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    except Exception as e:
                        self.add_log(f"프로세스 종료 중 오류: {e}")
                        # 대체 방법: terminate 사용
                        self.main_app.hosting_process.terminate()
                else:
                    self.main_app.hosting_process.terminate()
                
                # 프로세스 정리 대기
                try:
                    self.main_app.hosting_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.main_app.hosting_process.kill()
                
                self.main_app.hosting_process = None
                
                # 버튼 텍스트 원래대로
                self.run_all_btn.setText("🚀 전체 앱 실행 (메일용)")
                self.run_all_btn.clicked.disconnect()
                self.run_all_btn.clicked.connect(self.run_hosting_script)
                
                QMessageBox.information(self, "중지", "서버가 중지되었습니다.")


# ──────────────────────────────────────────────────────────────────────────────
# │ 6. 문서 임베딩 탭 (수정됨)
# ──────────────────────────────────────────────────────────────────────────────
class DocumentEmbeddingApp(BaseEmbeddingTab):
    def __init__(self, parent: LLMToolApp):
        super().__init__(parent, 'document', 'embedding_log_doc.txt')
        self.parsers_info = DOCUMENT_PARSERS
        
        self.init_ui()
        self.load_config({'doc_qdrant_path': self.hosting_path_input, 'local_doc_path': self.doc_path_input})
        self._populate_parsers()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)
        main_layout.addWidget(self._create_qdrant_group())
        main_layout.addWidget(self._create_doc_source_group())
        main_layout.addWidget(self._create_log_group())
        main_layout.addWidget(self._create_endpoint_settings_group())
        main_layout.addWidget(self._create_hosting_group())
        self.update_ui_for_qdrant_state()
        self.load_endpoint_settings()

    def _create_qdrant_group(self):
        group = QGroupBox("Qdrant 서버 (문서용)")
        layout = QGridLayout()
        layout.addWidget(QLabel("저장 경로:"), 0, 0)
        self.hosting_path_input = QLineEdit()
        self.hosting_path_input.editingFinished.connect(lambda: self.save_config('doc_qdrant_path', self.hosting_path_input.text()))
        layout.addWidget(self.hosting_path_input, 0, 1)
        self.browse_btn = QPushButton("...")
        self.browse_btn.setFixedWidth(40)
        self.browse_btn.clicked.connect(self.browse_hosting_path)
        layout.addWidget(self.browse_btn, 0, 2)
        self.status_label = QLabel("🔴 중지됨")
        layout.addWidget(self.status_label, 1, 0, 1, 3)
        btn_layout = QHBoxLayout()
        self.run_btn = QPushButton("실행"); self.run_btn.clicked.connect(self.run_qdrant)
        self.stop_btn = QPushButton("중지"); self.stop_btn.clicked.connect(self.stop_qdrant)
        self.clear_btn = QPushButton("데이터 초기화"); self.clear_btn.clicked.connect(self.clear_qdrant_data)
        btn_layout.addWidget(self.run_btn); btn_layout.addWidget(self.stop_btn); btn_layout.addWidget(self.clear_btn)
        layout.addLayout(btn_layout, 2, 0, 1, 3)
        group.setLayout(layout)
        return group
    
    def _create_doc_source_group(self):
        group = QGroupBox("로컬 문서 처리")
        layout = QGridLayout()
        layout.addWidget(QLabel("문서 폴더:"), 0, 0)
        self.doc_path_input = QLineEdit()
        self.doc_path_input.editingFinished.connect(lambda: self.save_config('local_doc_path', self.doc_path_input.text()))
        layout.addWidget(self.doc_path_input, 0, 1, 1, 2)
        self.browse_doc_btn = QPushButton("..."); self.browse_doc_btn.setFixedWidth(40); self.browse_doc_btn.clicked.connect(self.browse_doc_path)
        layout.addWidget(self.browse_doc_btn, 0, 3)
        layout.addWidget(QLabel("파서 선택:"), 1, 0)
        self.parser_combo = QComboBox(); self.parser_combo.currentTextChanged.connect(self.on_parser_changed)
        layout.addWidget(self.parser_combo, 1, 1, 1, 3)
        chunk_group = QGroupBox("청킹 옵션"); chunk_layout = QHBoxLayout()
        chunk_layout.addWidget(QLabel("청크 크기:")); self.chunk_size_spin = QSpinBox(); self.chunk_size_spin.setRange(100, 5000); self.chunk_size_spin.setValue(1000)
        chunk_layout.addWidget(self.chunk_size_spin)
        chunk_layout.addWidget(QLabel("청크 중첩:")); self.chunk_overlap_spin = QSpinBox(); self.chunk_overlap_spin.setRange(0, 1000); self.chunk_overlap_spin.setValue(200)
        chunk_layout.addWidget(self.chunk_overlap_spin)
        chunk_group.setLayout(chunk_layout); layout.addWidget(chunk_group, 2, 0, 1, 4)
        embedding_layout = QHBoxLayout()
        self.continue_doc_btn = QPushButton("➡️ 이어서 임베딩"); self.continue_doc_btn.clicked.connect(lambda: self.start_document_embedding(fresh_start=False))
        self.new_doc_btn = QPushButton("🔄 새롭게 임베딩"); self.new_doc_btn.clicked.connect(lambda: self.start_document_embedding(fresh_start=True))
        embedding_layout.addWidget(self.continue_doc_btn, 2); embedding_layout.addWidget(self.new_doc_btn, 1)
        layout.addLayout(embedding_layout, 3, 0, 1, 4)
        group.setLayout(layout)
        return group

    def _create_log_group(self):
        group = QGroupBox("처리 로그")
        layout = QVBoxLayout()
        self.progress_bar = QProgressBar()
        self.log_widget = QTextEdit(); self.log_widget.setReadOnly(True)
        self.stop_embedding_btn = QPushButton("🛑 임베딩 중지")
        self.stop_embedding_btn.clicked.connect(self.request_stop_embedding)
        self.stop_embedding_btn.setEnabled(False)
        log_ctrl_layout = QHBoxLayout()
        log_ctrl_layout.addWidget(self.progress_bar); log_ctrl_layout.addWidget(self.stop_embedding_btn)
        layout.addLayout(log_ctrl_layout); layout.addWidget(self.log_widget)
        group.setLayout(layout)
        return group

    def _populate_parsers(self):
        self.parser_combo.clear()
        self.parser_combo.addItems(self.parsers_info.keys())
        if self.parsers_info:
            self.on_parser_changed(self.parser_combo.currentText())

    def on_parser_changed(self, display_name: str):
        if not display_name: return
        info = self.parsers_info.get(display_name, {})
        requires_chunking = info.get("requires_chunking", False)
        self.chunk_size_spin.setEnabled(requires_chunking)
        self.chunk_overlap_spin.setEnabled(requires_chunking)

    def browse_hosting_path(self):
        if folder := QFileDialog.getExistingDirectory(self, "Qdrant 저장 경로 선택"):
            self.hosting_path_input.setText(folder)
            self.save_config('doc_qdrant_path', folder)

    def browse_doc_path(self):
        if folder := QFileDialog.getExistingDirectory(self, "문서 폴더 선택"):
            self.doc_path_input.setText(folder)
            self.save_config('local_doc_path', folder)

    def update_ui_for_qdrant_state(self):
        is_running = self.main_app.qdrant_client is not None
        is_my_service = is_running and self.main_app.active_qdrant_service_type == self.service_name
        self.run_btn.setEnabled(not is_running)
        self.stop_btn.setEnabled(is_my_service)
        self.hosting_path_input.setEnabled(not is_running)
        self.browse_btn.setEnabled(not is_running)
        self.clear_btn.setEnabled(not is_running)
        self.set_buttons_enabled(True)
        if is_running:
            self.status_label.setText(f"🟢 실행 중" if is_my_service else "⚪️ (메일용 서버 실행 중)")
        else:
            self.status_label.setText("🔴 중지됨")
    
    def set_buttons_enabled(self, enabled: bool):
        is_my_service = self.main_app.qdrant_client is not None and self.main_app.active_qdrant_service_type == self.service_name
        can_embed = enabled and is_my_service
        self.continue_doc_btn.setEnabled(can_embed)
        self.new_doc_btn.setEnabled(can_embed)
        self.stop_embedding_btn.setEnabled(not enabled)

    def start_document_embedding(self, fresh_start: bool):
        folder_path = self.doc_path_input.text()
        if not folder_path or not Path(folder_path).is_dir():
            QMessageBox.warning(self, "경고", "유효한 문서 폴더를 선택해주세요.")
            return
        
        parser_key = self.parser_combo.currentText()
        if not parser_key:
            QMessageBox.warning(self, "경고", "사용할 파서를 선택해주세요.")
            return

        if not self._handle_fresh_start(fresh_start):
            return
        
        parser_info = self.parsers_info[parser_key]
        
        task_kwargs = {
            'folder_path_str': folder_path,
            'parser_key': parser_key,
            'file_filter': parser_info["allowed_extensions"],
            'requires_chunking': parser_info["requires_chunking"],
            'chunk_size': self.chunk_size_spin.value(),
            'chunk_overlap': self.chunk_overlap_spin.value(),
            'logic_path': parser_info.get("logic_path")
        }
        self.worker.start_work(self._document_embedding_task, **task_kwargs)
        self.add_log(f"'{parser_key}' 작업을 시작합니다...")
        self.set_buttons_enabled(False)

    def _document_embedding_task(
        self,
        folder_path_str,
        parser_key,
        file_filter,
        requires_chunking,
        chunk_size,
        chunk_overlap,
        logic_path=None
    ):
        collection_name = "my_documents"
        try:
            self._ensure_collection_exists(collection_name)
        except Exception as e:
            self.worker.error.emit(str(e))
            return {"p": 0, "s": 0, "c": 0}

        output_dir = self.main_app.project_root / "chunk_outputs"
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = output_dir / f"_document_embedding_{timestamp}.txt"
        self.worker.log.emit(f"청크 내용은 다음 파일에 저장됩니다: {output_filename}")

        folder_path = Path(folder_path_str)
        parser_engine = self.parsers_info[parser_key]['engine']

        self.worker.log.emit(f"'{parser_key}' 파서로 문서 스캔 시작...")

        engine_kwargs = {}
        if logic_path:
            engine_kwargs['logic_path'] = logic_path
        all_docs = parser_engine(folder_path, file_filter, **engine_kwargs)

        self.worker.log.emit(f"총 {len(all_docs)}개 문서(시트) 발견. 임베딩 및 저장을 시작합니다.")

        processed_ids = self._load_processed_ids()
        newly_proc, skipped, total_chunks = 0, 0, 0
        qdrant_batch, id_batch = [], []
        model = self.main_app.embedding_model

        doc_map = {}
        for doc in all_docs:
            path = doc.metadata.get('path')
            sheet = doc.metadata.get('sheet', 'N/A')
            doc_id = f"{path}::{sheet}"
            doc_map.setdefault(path, []).append((doc_id, doc))

        total_files = len(doc_map)
        processed_files = 0

        for file_path_str, doc_tuples in doc_map.items():
            processed_files += 1
            if self.worker.is_stop_requested():
                break
            prog = int((processed_files / total_files) * 100) if total_files > 0 else 100
            self.worker.progress.emit(prog, f"파일 처리 중 ({processed_files}/{total_files})")

            if all(doc_id in processed_ids for doc_id, _ in doc_tuples):
                skipped += len(doc_tuples)
                continue

            points_for_file = []
            ids_for_file = []
            newly_proc_sheets = 0

            for doc_id, doc in doc_tuples:
                if doc_id in processed_ids:
                    skipped += 1
                    continue

                try:
                    text = unicodedata.normalize("NFKC", (doc.page_content or "").strip())
                    if not text:
                        continue

                    chunks = (
                        chunk_by(text, chunk_size, chunk_overlap)
                        if requires_chunking else [text]
                    )
                    if not chunks:
                        continue

                    for idx, chunk in enumerate(chunks):
                        meta = {
                            **doc.metadata,
                            "chunk_index": idx,
                            "total_chunks": len(chunks),
                        }
                        
                        # [수정] RAG 시스템이 인식할 수 있는 표준 메타데이터 Key 추가
                        if doc.metadata.get("DATA_TYPE") == "선각계열회의 안건":
                            meta['title'] = doc.metadata.get("안건명", "N/A")
                        elif doc.metadata.get("DATA_TYPE") == "선각계열회의 표지":
                            meta['title'] = f"{doc.metadata.get('회의 차수', '')} 표지"
                        elif doc.metadata.get("DATA_TYPE") == "선각계열회의 회의 요약":
                            meta['title'] = f"{doc.metadata.get('회의 차수', '')} 회의 요약"
                        else:
                            meta['title'] = doc.metadata.get("file_name", "N/A")
                        
                        meta['source'] = doc.metadata.get("path", "N/A")
                        
                        # 로그 파일에 전체 메타데이터를 JSON 형식으로 저장
                        try:
                            with open(output_filename, "a", encoding="utf-8") as f:
                                f.write(f"--- Document Chunk ---\n")
                                metadata_str = json.dumps(meta, indent=2, ensure_ascii=False)
                                f.write(f"📄 Metadata:\n{metadata_str}\n\n")
                                f.write(f"📝 Page Content (Chunk):\n{chunk}\n")
                                f.write(f"{'='*60}\n\n")
                        except Exception as e:
                            self.worker.log.emit(f"청크 파일 저장 실패: {e}")
                        
                        emb = model.encode([chunk], show_progress_bar=False)[0]
                        point = models.PointStruct(
                            id=str(uuid.uuid4()),
                            vector=emb.tolist(),
                            payload={**meta, "text": chunk},
                        )
                        points_for_file.append(point)

                    ids_for_file.append(doc_id)
                    newly_proc_sheets += 1

                except Exception as e:
                    self.worker.log.emit(
                        f"문서/시트 처리 오류: {doc.metadata.get('file_name','N/A')} - "
                        f"{doc.metadata.get('sheet','N/A')} - {e}"
                    )

            if points_for_file:
                qdrant_batch.extend(points_for_file)
                id_batch.extend(ids_for_file)
                newly_proc += newly_proc_sheets

            if len(qdrant_batch) >= QDRANT_BATCH_SIZE:
                self._upload_batch(collection_name, qdrant_batch, id_batch)
                total_chunks += len(qdrant_batch)
                qdrant_batch.clear()
                id_batch.clear()

        if qdrant_batch:
            self._upload_batch(collection_name, qdrant_batch, id_batch)
            total_chunks += len(qdrant_batch)

        return {
            "p": newly_proc,
            "s": skipped,
            "c": total_chunks,
            "stopped": self.worker.is_stop_requested()
        }
    
    def _create_endpoint_settings_group(self):
        """엔드포인트 설정 그룹 생성"""
        group = QGroupBox("서버 엔드포인트 설정")
        layout = QGridLayout()
        
        # Qdrant 설정
        layout.addWidget(QLabel("Qdrant 서버:"), 0, 0)
        self.doc_qdrant_host = QLineEdit("10.150.104.21")
        self.doc_qdrant_port = QLineEdit("6333")
        layout.addWidget(self.doc_qdrant_host, 0, 1)
        layout.addWidget(QLabel(":"), 0, 2)
        layout.addWidget(self.doc_qdrant_port, 0, 3)
        
        # Ollama 설정
        layout.addWidget(QLabel("Ollama 서버:"), 1, 0)
        self.doc_ollama_host = QLineEdit("127.0.0.1")
        self.doc_ollama_port = QLineEdit("11434")
        layout.addWidget(self.doc_ollama_host, 1, 1)
        layout.addWidget(QLabel(":"), 1, 2)
        layout.addWidget(self.doc_ollama_port, 1, 3)
        
        # 저장 버튼
        save_btn = QPushButton("💾 설정 저장")
        save_btn.clicked.connect(self.save_endpoint_settings)
        layout.addWidget(save_btn, 2, 0, 1, 4)
        
        group.setLayout(layout)
        return group
    
    def save_endpoint_settings(self):
        """엔드포인트 설정 저장"""
        config = json.load(open(self.config_path, 'r', encoding='utf-8')) if self.config_path.exists() else {}
        
        if 'endpoints' not in config:
            config['endpoints'] = {}
        
        config['endpoints']['doc'] = {
            'qdrant_host': self.doc_qdrant_host.text(),
            'qdrant_port': self.doc_qdrant_port.text(),
            'ollama_host': self.doc_ollama_host.text(),
            'ollama_port': self.doc_ollama_port.text()
        }
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        QMessageBox.information(self, "저장", "설정이 저장되었습니다.")
    
    def load_endpoint_settings(self):
        """엔드포인트 설정 로드"""
        if self.config_path.exists():
            config = json.load(open(self.config_path, 'r', encoding='utf-8'))
            endpoints = config.get('endpoints', {}).get('doc', {})
            
            self.doc_qdrant_host.setText(endpoints.get('qdrant_host', '10.150.104.21'))
            self.doc_qdrant_port.setText(endpoints.get('qdrant_port', '6333'))
            self.doc_ollama_host.setText(endpoints.get('ollama_host', '127.0.0.1'))
            self.doc_ollama_port.setText(endpoints.get('ollama_port', '11434'))
    
    def _create_hosting_group(self):
        group = QGroupBox("Frontend & Backend 호스팅")
        layout = QVBoxLayout()
        label = QLabel("아래 버튼을 누르면 문서 데이터 기반 전체 RAG 웹 앱 서버를 실행합니다.")
        label.setWordWrap(True)
        
        # 버튼 레이아웃
        btn_layout = QHBoxLayout()
        self.run_all_btn = QPushButton("🚀 전체 앱 실행 (문서용)")
        self.run_all_btn.clicked.connect(self.run_hosting_script)
        self.browser_btn = QPushButton("🌐 브라우저 열기")
        self.browser_btn.clicked.connect(self.open_browser)
        
        btn_layout.addWidget(self.run_all_btn)
        btn_layout.addWidget(self.browser_btn)
        
        layout.addWidget(label)
        layout.addLayout(btn_layout)
        group.setLayout(layout)
        return group
    
    def open_browser(self):
        """브라우저에서 프론트엔드 열기"""
        try:
            # 프론트엔드 서버가 실행 중인지 확인
            response = requests.get("http://localhost:8001", timeout=1)
            if response.status_code == 200:
                webbrowser.open("http://localhost:8001")
                self.add_log("브라우저에서 프론트엔드를 열었습니다.")
            else:
                QMessageBox.warning(self, "서버 오류", "프론트엔드 서버가 응답하지 않습니다.")
        except:
            QMessageBox.warning(self, "서버 없음", "프론트엔드 서버가 실행되지 않았습니다.\n먼저 '전체 앱 실행'을 클릭하세요.")
    
    def run_hosting_script(self):
        script_path = self.main_app.run_all_script_path
        if not Path(script_path).exists():
            QMessageBox.critical(self, "스크립트 없음", f"실행할 스크립트를 찾을 수 없습니다:\n{script_path}")
            return
        
        # 이미 실행 중인지 확인
        if hasattr(self.main_app, 'hosting_process') and self.main_app.hosting_process:
            if self.main_app.hosting_process.poll() is None:
                QMessageBox.warning(self, "이미 실행 중", "서버가 이미 실행 중입니다.")
                return
        
        try:
            config = json.load(open(self.config_path, 'r', encoding='utf-8')) if self.config_path.exists() else {}
            qdrant_path_arg = config.get('doc_qdrant_path', str(self.main_app.project_root / "qdrant_document"))
            
            # 가상환경 Python 사용
            venv_python = self.main_app.project_root / "venv" / "Scripts" / "python.exe"
            if not venv_python.exists():
                QMessageBox.critical(self, "가상환경 오류", "가상환경을 찾을 수 없습니다. INSTALL.bat을 먼저 실행하세요.")
                return
            
            # 프로세스 시작
            self.main_app.hosting_process = subprocess.Popen(
                [str(venv_python), str(script_path), f"--qdrant_path={qdrant_path_arg}", f"--service_type=doc"],
                creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
            )
            
            # 프로세스가 실제로 시작되었는지 확인
            time.sleep(1)  # 프로세스 시작 대기
            if self.main_app.hosting_process.poll() is None:
                # 프로세스가 정상적으로 실행 중
                self.add_log("전체 앱 서버가 성공적으로 시작되었습니다.")
                
                # 버튼 텍스트 변경
                self.run_all_btn.setText("⏹ 전체 앱 중지 (문서용)")
                self.run_all_btn.clicked.disconnect()
                self.run_all_btn.clicked.connect(self.stop_hosting_script)
                
                QMessageBox.information(self, "실행", "서버가 시작되었습니다.\n브라우저에서 http://localhost:8001 을 열어주세요.")
            else:
                # 프로세스가 즉시 종료됨
                self.add_log("프로세스 시작 실패 - 프로세스가 즉시 종료되었습니다.")
                self.main_app.hosting_process = None
                QMessageBox.critical(self, "실행 실패", "서버를 시작할 수 없습니다. 로그를 확인해주세요.")
                
        except Exception as e:
            self.add_log(f"서버 시작 중 오류 발생: {e}")
            # 오류 발생 시 버튼 상태 복구
            self.main_app.hosting_process = None
            self.run_all_btn.setText("🚀 전체 앱 실행 (문서용)")
            QMessageBox.critical(self, "실행 실패", f"스크립트 실행 중 오류가 발생했습니다: {e}")
    
    def stop_hosting_script(self):
        """호스팅 스크립트 중지 - 모든 자식 프로세스 포함"""
        if hasattr(self.main_app, 'hosting_process') and self.main_app.hosting_process:
            if self.main_app.hosting_process.poll() is None:
                # Windows에서 프로세스 트리 전체 종료
                if sys.platform == 'win32':
                    try:
                        # taskkill 명령어로 프로세스 트리 전체 종료
                        subprocess.call(['taskkill', '/F', '/T', '/PID', str(self.main_app.hosting_process.pid)], 
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    except Exception as e:
                        self.add_log(f"프로세스 종료 중 오류: {e}")
                        # 대체 방법: terminate 사용
                        self.main_app.hosting_process.terminate()
                else:
                    self.main_app.hosting_process.terminate()
                
                # 프로세스 정리 대기
                try:
                    self.main_app.hosting_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.main_app.hosting_process.kill()
                
                self.main_app.hosting_process = None
                
                # 버튼 텍스트 원래대로
                self.run_all_btn.setText("🚀 전체 앱 실행 (문서용)")
                self.run_all_btn.clicked.disconnect()
                self.run_all_btn.clicked.connect(self.run_hosting_script)
                
                QMessageBox.information(self, "중지", "서버가 중지되었습니다.")

# ──────────────────────────────────────────────────────────────────────────────
# │ 설정 탭
# ──────────────────────────────────────────────────────────────────────────────
class SettingsTab(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.main_app = parent
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Background settings group
        bg_group = QGroupBox("백그라운드 실행 설정")
        bg_layout = QVBoxLayout()
        
        self.minimize_to_tray_cb = QCheckBox("창 닫을 때 트레이로 최소화")
        self.minimize_to_tray_cb.stateChanged.connect(self.save_settings)
        bg_layout.addWidget(self.minimize_to_tray_cb)
        
        self.start_minimized_cb = QCheckBox("프로그램 시작 시 트레이로 최소화")
        self.start_minimized_cb.stateChanged.connect(self.save_settings)
        bg_layout.addWidget(self.start_minimized_cb)
        
        # 설명 레이블 추가
        info_label = QLabel("트레이 아이콘을 더블클릭하면 창이 열립니다.\n우클릭하면 메뉴가 표시됩니다.")
        info_label.setStyleSheet("color: gray; font-size: 10pt;")
        bg_layout.addWidget(info_label)
        
        bg_group.setLayout(bg_layout)
        layout.addWidget(bg_group)
        
        # Auto-start settings group
        auto_group = QGroupBox("자동 시작 설정")
        auto_layout = QVBoxLayout()
        
        self.auto_start_qdrant_cb = QCheckBox("프로그램 시작 시 Qdrant 자동 실행")
        self.auto_start_qdrant_cb.stateChanged.connect(self.save_settings)
        auto_layout.addWidget(self.auto_start_qdrant_cb)
        
        self.auto_start_backend_cb = QCheckBox("프로그램 시작 시 백엔드 자동 실행")
        self.auto_start_backend_cb.stateChanged.connect(self.save_settings)
        auto_layout.addWidget(self.auto_start_backend_cb)
        
        auto_group.setLayout(auto_layout)
        layout.addWidget(auto_group)
        
        # Load current settings
        self.load_settings()
        
        layout.addStretch()
        self.setLayout(layout)
    
    def load_settings(self):
        """현재 설정 로드"""
        config = self.main_app.load_config()
        self.minimize_to_tray_cb.setChecked(config.get('minimize_to_tray', True))
        self.start_minimized_cb.setChecked(config.get('start_minimized', False))
        self.auto_start_qdrant_cb.setChecked(config.get('auto_start_qdrant', False))
        self.auto_start_backend_cb.setChecked(config.get('auto_start_backend', False))
    
    def save_settings(self):
        """설정 저장"""
        config_path = self.main_app.project_root / "config.json"
        config = self.main_app.load_config()
        
        config['minimize_to_tray'] = self.minimize_to_tray_cb.isChecked()
        config['start_minimized'] = self.start_minimized_cb.isChecked()
        config['auto_start_qdrant'] = self.auto_start_qdrant_cb.isChecked()
        config['auto_start_backend'] = self.auto_start_backend_cb.isChecked()
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
        
        # 트레이 아이콘 업데이트
        if self.main_app.tray_icon:
            if config['minimize_to_tray']:
                self.main_app.tray_icon.show()
            else:
                self.main_app.tray_icon.hide()

# ──────────────────────────────────────────────────────────────────────────────
# │ 7. 메인 실행
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        # 로깅 설정 확인
        logging.info("=== LLMPY Vector Studio 시작 ===")
        logging.info(f"Python 버전: {sys.version}")
        logging.info(f"작업 디렉토리: {os.getcwd()}")
        
        app = QApplication(sys.argv)
        app.setStyle('Fusion')  # 더 나은 UI 스타일
        app.setQuitOnLastWindowClosed(False)  # 트레이로 최소화할 때 앱이 종료되지 않도록
        
        # 스플래시 스크린 또는 로딩 표시 (선택사항)
        logging.info("메인 윈도우 생성 중...")
        window = LLMToolApp()
        
        logging.info("GUI 표시...")
        window.show()
        
        logging.info("이벤트 루프 시작...")
        sys.exit(app.exec())
        
    except ImportError as e:
        logging.error(f"필수 모듈 임포트 실패: {e}")
        print(f"\n[오류] 필수 라이브러리가 설치되지 않았습니다: {e}")
        print("requirements.txt 파일을 확인하고 다음 명령을 실행하세요:")
        print("pip install -r requirements.txt")
        sys.exit(1)
        
    except Exception as e:
        logging.error(f"애플리케이션 실행 중 치명적인 오류 발생: {e}")
        traceback_str = traceback.format_exc()
        logging.error(f"전체 추적:\n{traceback_str}")
        
        # GUI가 없어도 오류 메시지 출력
        print(f"\n[치명적 오류] {e}")
        print(f"상세 정보:\n{traceback_str}")
        
        # 가능하면 GUI로도 표시
        try:
            temp_app = QApplication.instance() or QApplication(sys.argv)
            QMessageBox.critical(
                None,
                "치명적 오류",
                f"애플리케이션을 시작할 수 없습니다.\n\n오류: {e}\n\n상세 정보:\n{traceback_str}"
            )
        except:
            pass  # GUI 오류 표시 실패시 무시
        
        sys.exit(1)