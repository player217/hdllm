import os
import re
import logging
import json
import uuid
import datetime
import urllib.parse
import signal
import asyncio
from collections import deque
from contextlib import asynccontextmanager
from textwrap import dedent
from pathlib import Path
import hashlib

import torch
import requests
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from qdrant_client import QdrantClient, models
from langchain_huggingface import HuggingFaceEmbeddings
from dotenv import load_dotenv
load_dotenv()

# --------------------------------------------------------------------------
# 1. 로깅 설정
# --------------------------------------------------------------------------
LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)
log_filename = os.path.join(LOGS_DIR, f"rag_log_{datetime.date.today()}.log")

logger = logging.getLogger()
logger.setLevel(logging.INFO)
if logger.hasHandlers():
    logger.handlers.clear()

c_handler = logging.StreamHandler()
c_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
c_handler.setFormatter(c_format)
logger.addHandler(c_handler)

f_handler = logging.FileHandler(log_filename, encoding='utf-8')
f_format = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
f_handler.setFormatter(f_format)
logger.addHandler(f_handler)


# --------------------------------------------------------------------------
# 2. 전역 변수 및 설정
# --------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
EMBEDDING_MODEL_DEFAULT_PATH = PROJECT_ROOT / "src" / "bin" / "bge-m3-local"

# 디버그 모드 설정
DEBUG_MODE = os.getenv("RAG_DEBUG", "false").lower() == "true"
VERBOSE_LOGGING = os.getenv("RAG_VERBOSE", "false").lower() == "true"

if DEBUG_MODE:
    logger.setLevel(logging.DEBUG)
    logger.info("🔍 DEBUG MODE ENABLED")
if VERBOSE_LOGGING:
    logger.info("📝 VERBOSE LOGGING ENABLED")

try:
    import pythoncom
    import win32com.client
    WIN_COM_AVAILABLE = True
except ImportError:
    WIN_COM_AVAILABLE = False

class AppConfig:
    """애플리케이션 설정을 관리합니다."""
    
    def __init__(self):
        """config.json 파일에서 설정을 로드합니다."""
        self.config = self._load_config()
        
        # 기본값 설정 (config.json에서 못 읽을 경우 fallback) - 속성이 아닌 것들만
        self.QDRANT_SCORE_THRESHOLD = 0.30
        self.QDRANT_SEARCH_LIMIT = 3
        self.QDRANT_SEARCH_PARAMS = {
            "hnsw_ef": 128,
            "exact": False
        }
        self.GREETINGS = ["안녕", "안녕하세요", "ㅎㅇ", "하이", "반가워", "반갑습니다"]
    
    def _load_config(self):
        """config.json 파일을 로드합니다."""
        try:
            config_path = PROJECT_ROOT / "config.json"
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                logger.warning(f"config.json not found at {config_path}")
                return {}
        except Exception as e:
            logger.error(f"Failed to load config.json: {e}")
            return {}
    
    def get_qdrant_config(self, source: str = "mail"):
        """소스별 Qdrant 설정을 반환합니다."""
        try:
            # config.json에서 설정 가져오기
            qdrant_mode = self.config.get('qdrant_mode', {})
            source_config = qdrant_mode.get(source, {})
            hosting = source_config.get('hosting', 'local')
            instance_config = source_config.get('instances', {}).get(hosting, {})
            
            return {
                'host': instance_config.get('host', 'localhost'),
                'port': instance_config.get('port', 6333),
                'grpc_port': instance_config.get('grpc_port', 6334),
                'timeout': instance_config.get('timeout', 30.0),
                'collection': source_config.get('collection', 'my_documents')
            }
        except Exception as e:
            logger.error(f"Error getting Qdrant config for {source}: {e}")
            # 기본값 반환
            return {
                'host': 'localhost',
                'port': 6333,
                'grpc_port': 6334,
                'timeout': 30.0,
                'collection': 'my_documents'
            }
    
    @property
    def MAIL_QDRANT_COLLECTIONS(self) -> list[str]:
        """메일용 컬렉션을 반환합니다."""
        config = self.get_qdrant_config('mail')
        return [config['collection']]
    
    @property
    def DOC_QDRANT_COLLECTIONS(self) -> list[str]:
        """문서용 컬렉션을 반환합니다."""
        config = self.get_qdrant_config('doc')
        return [config['collection']]
    
    # 🔥 NEW: Ollama Keep-Alive and Warmup Settings (properties로 변경)
    @property
    def OLLAMA_KEEP_ALIVE(self) -> str:
        return self.config.get('OLLAMA_KEEP_ALIVE', '10m')
    
    @property
    def OLLAMA_WARMUP_ENABLED(self) -> bool:
        return self.config.get('OLLAMA_WARMUP_ENABLED', True)
    
    @property
    def OLLAMA_WARMUP_PROMPT(self) -> str:
        return self.config.get('OLLAMA_WARMUP_PROMPT', 'Hello')
    
    @property
    def EMBEDDING_MODEL_PATH(self) -> str:
        return self.config.get('EMBEDDING_MODEL_PATH', 'src/bin/bge-m3-local')
    
    @property
    def DEFAULT_LLM_MODEL(self) -> str:
        # config.json의 ollama.default_model을 읽기
        ollama_config = self.config.get('ollama', {})
        return ollama_config.get('default_model', 'gemma3:4b')
    
    @property
    def OLLAMA_API_URL(self) -> str:
        ollama_config = self.config.get('ollama', {})
        # 현재 hosting mode 확인 (기본값: local)
        hosting = 'local'  # 추후 동적으로 변경 가능
        instance = ollama_config.get(hosting, {})
        host = instance.get('host', '127.0.0.1')
        port = instance.get('port', 11434)
        return f'http://{host}:{port}/api/chat'
    
    @property
    def LLM_TIMEOUT(self) -> int:
        return self.config.get('LLM_TIMEOUT', 180)
    
    @property
    def QDRANT_TIMEOUT(self) -> float:
        # 기본 타임아웃 (Qdrant 설정에서 가져올 수도 있음)
        return self.config.get('QDRANT_TIMEOUT', 30.0)
    
    # 동적 속성으로 변경
    @property
    def MAIL_QDRANT_HOST(self) -> str:
        """config.json에서 메일 Qdrant 호스트를 가져옵니다."""
        return self.get_qdrant_config('mail')['host']
    
    @property
    def MAIL_QDRANT_PORT(self) -> int:
        """config.json에서 메일 Qdrant 포트를 가져옵니다."""
        return self.get_qdrant_config('mail')['port']
    
    @property
    def DOC_QDRANT_HOST(self) -> str:
        """config.json에서 문서 Qdrant 호스트를 가져옵니다."""
        return self.get_qdrant_config('doc')['host']
    
    @property
    def DOC_QDRANT_PORT(self) -> int:
        """config.json에서 문서 Qdrant 포트를 가져옵니다."""
        return self.get_qdrant_config('doc')['port']

config = AppConfig()
app_state = {}
dialog_cache: deque[tuple[str, str]] = deque(maxlen=3)

# Embedding cache with LRU (Least Recently Used) eviction
# Cache up to 100 queries to balance memory and performance
embedding_cache = {}
MAX_CACHE_SIZE = 100

# 🔥 NEW: Model Warmup System
class OllamaModelManager:
    """Ollama 모델 워밍업 및 Keep-Alive 관리"""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.is_warmed_up = False
        self.warmup_in_progress = False
        self.last_warmup_time = None
        
    async def warmup_model(self) -> bool:
        """모델을 미리 워밍업하여 Cold Start 방지"""
        if self.is_warmed_up or self.warmup_in_progress:
            return self.is_warmed_up
            
        if not self.config.OLLAMA_WARMUP_ENABLED:
            logger.info("🔥 Model warmup disabled in config")
            return True
            
        self.warmup_in_progress = True
        logger.info("🔥 Starting Ollama model warmup...")
        
        try:
            warmup_data = {
                "model": self.config.DEFAULT_LLM_MODEL,
                "messages": [
                    {"role": "user", "content": self.config.OLLAMA_WARMUP_PROMPT}
                ],
                "stream": False,  # Don't stream for warmup
                "options": {
                    "temperature": 0.1,
                    "num_ctx": 1024,  # Small context for faster warmup
                    "num_predict": 10  # Just a few tokens for warmup
                },
                "keep_alive": self.config.OLLAMA_KEEP_ALIVE
            }
            
            # Use asyncio.timeout for better async control
            async with asyncio.timeout(15.0):  # 15s timeout for warmup
                # Run synchronous requests.post in thread pool to avoid blocking
                # requests.post timeout as tuple: (connect_timeout, read_timeout)
                timeout = (5.0, 15.0)
                
                # Use asyncio.to_thread for non-blocking execution (Python 3.9+)
                response = await asyncio.to_thread(
                    requests.post,
                    self.config.OLLAMA_API_URL,
                    json=warmup_data,
                    timeout=timeout
                )
                response.raise_for_status()
                
                result = response.json()
                # Check for either 'message' or 'response' field (Ollama response format)
                if "message" in result or "response" in result:
                    self.is_warmed_up = True
                    self.last_warmup_time = datetime.datetime.now()
                    logger.info("🔥 ✅ Model warmup completed successfully!")
                    logger.info(f"🔥 Model will stay loaded for {self.config.OLLAMA_KEEP_ALIVE}")
                    return True
                else:
                    logger.warning("🔥 ⚠️ Warmup response missing expected fields")
                    return False
                    
        except asyncio.TimeoutError:
            logger.error("🔥 ❌ Model warmup timed out after 15s")
            return False
        except requests.RequestException as e:
            logger.error(f"🔥 ❌ Model warmup failed: {e}")
            return False
        except Exception as e:
            logger.error(f"🔥 ❌ Unexpected warmup error: {e}")
            return False
        finally:
            self.warmup_in_progress = False
            
    def should_rewarm(self) -> bool:
        """Keep-alive 시간이 지났는지 확인하여 재워밍업 필요성 판단"""
        if not self.last_warmup_time:
            return True
            
        # Parse keep_alive time (e.g., "10m" -> 10 minutes)
        keep_alive_str = self.config.OLLAMA_KEEP_ALIVE.lower()
        if keep_alive_str.endswith('m'):
            keep_alive_minutes = int(keep_alive_str[:-1])
        elif keep_alive_str.endswith('s'):
            keep_alive_minutes = int(keep_alive_str[:-1]) / 60
        else:
            keep_alive_minutes = 10  # Default to 10 minutes
            
        elapsed = datetime.datetime.now() - self.last_warmup_time
        elapsed_minutes = elapsed.total_seconds() / 60
        
        # Rewarm if 80% of keep-alive time has passed
        return elapsed_minutes > (keep_alive_minutes * 0.8)

# Initialize model manager
model_manager = OllamaModelManager(config)


# --------------------------------------------------------------------------
# 3. FastAPI 생명주기 및 앱 초기화
# --------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 시작 시 모델 및 클라이언트 로드, 종료 시 정리"""
    logger.info("🚀 애플리케이션 시작...")
    logger.info(f"📦 Backend Version: 1.0.4 - Performance Optimized")
    logger.info(f"🕐 Start Time: {datetime.datetime.now().isoformat()}")
    device_type = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"✅ 실행 디바이스: {device_type.upper()}")

    try:
        app_state["embeddings"] = HuggingFaceEmbeddings(
            model_name=config.EMBEDDING_MODEL_PATH,
            model_kwargs={"device": device_type},
            encode_kwargs={"normalize_embeddings": True}
        )
        logger.info(f"✅ 임베딩 모델 로드 성공 ({device_type.upper()}).")
    except Exception as e:
        logger.error(f"❌ 임베딩 모델 로드 실패: {e}", exc_info=True)

    try:
        # config.json에서 Qdrant 설정 읽기
        mail_config = config.get_qdrant_config("mail")
        doc_config = config.get_qdrant_config("doc")
        
        # Qdrant 클라이언트 2개 초기화
        app_state["qdrant_clients"] = {
            "mail": QdrantClient(
                host=mail_config['host'], 
                port=mail_config['port'], 
                timeout=mail_config['timeout']
            ),
            "doc": QdrantClient(
                host=doc_config['host'], 
                port=doc_config['port'], 
                timeout=doc_config['timeout']
            ),
        }
        
        # 엔드포인트 문자열 저장 및 상세 로깅
        app_state["qdrant_endpoints"] = {
            "mail": f"http://{mail_config['host']}:{mail_config['port']}",
            "doc": f"http://{doc_config['host']}:{doc_config['port']}",
        }
        
        logger.info("✅ Qdrant 클라이언트들 연결 성공.")
        logger.info(f"   MAIL → {app_state['qdrant_endpoints']['mail']} | collection={mail_config['collection']}")
        logger.info(f"   DOC  → {app_state['qdrant_endpoints']['doc']}  | collection={doc_config['collection']}")
        
        # Qdrant 컬렉션 상태 확인 (디버그 모드)
        if DEBUG_MODE:
            for name, client in app_state["qdrant_clients"].items():
                try:
                    collections = client.get_collections()
                    logger.debug(f"📊 {name.upper()} Qdrant 컬렉션 상태:")
                    for col in collections.collections:
                        try:
                            info = client.get_collection(col.name)
                            logger.debug(f"  - Collection '{col.name}': vectors={info.vectors_count}, indexed={info.indexed_vectors_count}")
                        except:
                            logger.debug(f"  - Collection '{col.name}': info unavailable")
                except Exception as e:
                    logger.warning(f"  - {name} Qdrant 상태 확인 실패: {e}")
    except Exception as e:
        logger.error(f"❌ Qdrant 클라이언트 연결 실패: {e}", exc_info=True)

    # 🔥 NEW: Ollama Model Warmup on Startup
    try:
        logger.info("🔥 Initiating Ollama model warmup...")
        warmup_success = await model_manager.warmup_model()
        if warmup_success:
            logger.info("🔥 ✅ Startup warmup completed - model ready for fast inference!")
        else:
            logger.warning("🔥 ⚠️ Startup warmup failed - first request may be slow")
    except Exception as e:
        logger.error(f"🔥 ❌ Startup warmup error: {e}")

    yield
    
    logger.info("🌙 애플리케이션 종료 시작...")
    
    # Graceful shutdown implementation
    try:
        # Close Qdrant connections
        if "qdrant_clients" in app_state:
            for name, client in app_state["qdrant_clients"].items():
                try:
                    client.close()
                    logger.info(f"✅ {name.upper()} Qdrant 클라이언트 연결 종료")
                except Exception as e:
                    logger.warning(f"⚠️ {name.upper()} Qdrant 클라이언트 종료 중 오류: {e}")
        
        # Clear embeddings model and GPU memory
        if "embeddings" in app_state:
            try:
                # Embeddings 모델 정리 (메모리 및 GPU 메모리)
                del app_state["embeddings"]
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                logger.info("✅ 임베딩 모델 메모리 정리 완료")
            except Exception as e:
                logger.warning(f"⚠️ 임베딩 모델 정리 중 오류: {e}")
        
        # Clear caches
        try:
            global embedding_cache
            embedding_cache.clear()
            logger.info("✅ 임베딩 캐시 정리 완료")
        except Exception as e:
            logger.warning(f"⚠️ 캐시 정리 중 오류: {e}")
        
        # Clear application state and dialog cache
        app_state.clear()
        dialog_cache.clear()
        logger.info("✅ 애플리케이션 상태 정리 완료")
        
        # Small delay to ensure cleanup completion
        await asyncio.sleep(0.5)
        
    except Exception as e:
        logger.error(f"❌ Graceful shutdown 중 오류 발생: {e}", exc_info=True)
    finally:
        logger.info("🌙 애플리케이션 종료 완료")

app = FastAPI(lifespan=lifespan)

# CORS 설정 개선 - Frontend 전용 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8001",  # Frontend 기본 포트
        "http://127.0.0.1:8001",
        "http://localhost:3000",  # 추가 개발 포트
        "http://127.0.0.1:3000",
        "*"  # 개발 환경에서 모든 origin 허용
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------
# 4. 핵심 로직 함수
# --------------------------------------------------------------------------
def format_context(payload: dict) -> str:
    """검색된 컨텍스트를 LLM 프롬프트에 맞게 포맷합니다."""
    source_type = payload.get("source_type")
    raw_text = payload.get("text", "") or payload.get("body", "")
    raw_text = raw_text.strip()
    
    # Limit context length for faster processing
    MAX_CONTEXT_LENGTH = 500
    if len(raw_text) > MAX_CONTEXT_LENGTH:
        raw_text = raw_text[:MAX_CONTEXT_LENGTH] + "..."
    
    if VERBOSE_LOGGING:
        logger.debug(f"format_context - source_type: {source_type}")
        logger.debug(f"format_context - available fields: {list(payload.keys())}")

    if source_type in ["email_body", "email_attachment"]:
        is_attachment = source_type == 'email_attachment'
        attachment_info = f"- 첨부파일명: {payload.get('file_name', 'N/A')}\n" if is_attachment else ""
        
        # [수정] 제목과 날짜를 유연하게 가져오도록 변경
        title = payload.get("mail_subject") or payload.get("subject", "N/A")
        date = payload.get("sent_date") or payload.get("date", "N/A")
        
        if VERBOSE_LOGGING:
            logger.debug(f"format_context - title: {title[:50] if title != 'N/A' else 'N/A'}")
            logger.debug(f"format_context - date: {date}")
            if title == "N/A":
                logger.warning(f"format_context - Missing title field. Available: {list(payload.keys())}")
            if date == "N/A":
                logger.warning(f"format_context - Missing date field. Available: {list(payload.keys())}")

        return dedent(f"""\
            [참고자료: 이메일 {'첨부파일' if is_attachment else '본문'}]
            - 제목: {title}
            - 보낸 사람: {payload.get('sender', 'N/A')}
            - 날짜: {date}
            {attachment_info}- 내용:
            {raw_text}""").strip()
    
    return f"[참고자료: 기타]\n{raw_text}"

async def stream_llm_response(prompt: str, model: str, request_id: str):
    """Ollama API를 통해 LLM 응답을 스트리밍합니다."""
    logger.info(f"[{request_id}] 최종 답변 스트리밍 중 (모델: {model})...")
    
    # 🔥 Smart Rewarm: Check if model needs rewarming
    if model_manager.should_rewarm():
        logger.info(f"[{request_id}] 🔥 Model may need rewarming - initiating background warmup")
        # Don't await - let it run in background
        asyncio.create_task(model_manager.warmup_model())
    
    json_data = {
        "model": model,
        "messages": [
            {"role": "system", "content": "당신은 HD현대미포의 한국어 AI 어시스턴트입니다. 반드시 한국어로만 응답하세요. 영어나 다른 언어는 절대 사용하지 마세요. 모든 답변은 정중하고 명확한 한국어로 작성해주세요."},
            {"role": "user", "content": prompt}
        ],
        "stream": True,
        "options": {
            "temperature": 0.3,  # Slight temperature for more natural Korean
            "num_ctx": 2048,     # ⚡ Reduced context window for faster processing
            "num_predict": 512   # ⚡ Limit response length for faster completion
        },
        "keep_alive": config.OLLAMA_KEEP_ALIVE  # 🔥 Keep model loaded
    }
    
    try:
        with requests.post(
            config.OLLAMA_API_URL, json=json_data, timeout=config.LLM_TIMEOUT, stream=True
        ) as res:
            res.raise_for_status()
            # Increase buffer size to 16KB for better streaming performance
            for chunk in res.iter_lines(chunk_size=16384):
                if not chunk: continue
                try:
                    data = json.loads(chunk.decode('utf-8'))
                    content = data.get("message", {}).get("content", "")
                    yield content
                    if data.get("done"): break
                except json.JSONDecodeError:
                    logger.warning(f"[{request_id}] JSON 청크 디코딩 실패: {chunk}")
    except Exception as e:
        logger.error(f"[{request_id}] LLM 스트리밍 실패: {e}")
        yield "답변 생성 중 오류가 발생했습니다."

def search_qdrant(question: str, request_id: str, client: QdrantClient, config: AppConfig, source: str, collections: list[str]) -> tuple[str, list[dict]]:
    """Qdrant에서 관련 문서를 검색합니다."""
    embeddings = app_state.get("embeddings")
    if not client or not embeddings:
        logger.warning(f"[{request_id}] Qdrant client or embeddings not available")
        return "", []

    # 쿼리 정규화 및 벡터 생성
    normalized_query = question.lower().strip()
    logger.debug(f"[{request_id}] Query normalization: '{question}' -> '{normalized_query}'")
    
    # 특정 키워드 감지 (디버깅용)
    if "르꼬끄" in question:
        logger.info(f"[{request_id}] 🔍 Special keyword '르꼬끄' detected in query")
    
    # Check embedding cache first
    cache_key = hashlib.md5(normalized_query.encode()).hexdigest()
    if cache_key in embedding_cache:
        query_vector = embedding_cache[cache_key]
        logger.debug(f"[{request_id}] 🎯 Using cached embedding for query")
    else:
        query_vector = embeddings.embed_query(normalized_query)
        
        # Add to cache with size limit
        if len(embedding_cache) >= MAX_CACHE_SIZE:
            # Remove oldest item (simple FIFO for now)
            oldest_key = next(iter(embedding_cache))
            del embedding_cache[oldest_key]
        
        embedding_cache[cache_key] = query_vector
        logger.debug(f"[{request_id}] 💾 Cached new embedding (cache size: {len(embedding_cache)})")
    
    logger.debug(f"[{request_id}] Query vector created - dimension: {len(query_vector)}")

    all_hits = []
    for collection_name in collections:
        try:
            logger.info(f"[{request_id}] 🔎 Searching collection: '{collection_name}' on source: {source}")
            logger.debug(f"[{request_id}] Search params - limit: {config.QDRANT_SEARCH_LIMIT}, threshold: {config.QDRANT_SCORE_THRESHOLD}")
            
            hits = client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=config.QDRANT_SEARCH_LIMIT,
                score_threshold=config.QDRANT_SCORE_THRESHOLD,
                search_params=models.SearchParams(**config.QDRANT_SEARCH_PARAMS)
            )
            
            if hits:
                logger.info(f"[{request_id}] ✅ Found {len(hits)} hits in '{collection_name}'")
                if DEBUG_MODE:
                    for i, hit in enumerate(hits[:5], 1):  # 상위 5개만 상세 로깅
                        logger.debug(f"[{request_id}]  Hit {i}: score={hit.score:.4f}, id={hit.id}")
                        logger.debug(f"[{request_id}]  Metadata keys: {list(hit.payload.keys())}")
                        if VERBOSE_LOGGING:
                            # 메타데이터 일부 출력 (텍스트 제외)
                            meta_preview = {k: v for k, v in hit.payload.items() if k != 'text' and k != 'embedding'}
                            logger.debug(f"[{request_id}]  Metadata preview: {meta_preview}")
            else:
                logger.warning(f"[{request_id}] ⚠️ No hits found in '{collection_name}' (threshold: {config.QDRANT_SCORE_THRESHOLD})")
            
            all_hits.extend(hits)
        except Exception as e:
            logger.error(f"[{request_id}] ❌ 컬렉션 '{collection_name}' 검색 실패: {e}", exc_info=DEBUG_MODE)

    if not all_hits:
        logger.warning(f"[{request_id}] ❌ No hits found across all collections")
        return "", []

    # 중복 제거 및 정렬
    logger.info(f"[{request_id}] 📊 Total hits before deduplication: {len(all_hits)}")
    unique_hits = {hit.id: hit for hit in sorted(all_hits, key=lambda x: x.score, reverse=True)}.values()
    logger.info(f"[{request_id}] 📊 Total hits after deduplication: {len(unique_hits)}")
    
    top_hits = sorted(list(unique_hits), key=lambda x: x.score, reverse=True)[:config.QDRANT_SEARCH_LIMIT]
    logger.info(f"[{request_id}] 📊 Final top hits selected: {len(top_hits)}")
    
    # 상세한 검색 결과 출력
    logger.info(f"[{request_id}] " + "=" * 60)
    logger.info(f"[{request_id}] 🔍 QDRANT 검색 결과 상세")
    logger.info(f"[{request_id}] " + "=" * 60)
    
    for i, hit in enumerate(top_hits, 1):
        title = hit.payload.get("mail_subject") or hit.payload.get("subject", "N/A")
        date = hit.payload.get("sent_date") or hit.payload.get("date", "N/A")
        sender = hit.payload.get("sender", "N/A")
        text = hit.payload.get("text", "")
        text_preview = text[:300] + "..." if len(text) > 300 else text
        
        logger.info(f"[{request_id}] 📄 문서 {i}:")
        logger.info(f"[{request_id}]  점수: {hit.score:.4f}")
        logger.info(f"[{request_id}]  제목: {title}")
        logger.info(f"[{request_id}]  발신자: {sender}")
        logger.info(f"[{request_id}]  날짜: {date}")
        logger.info(f"[{request_id}]  텍스트 미리보기:")
        logger.info(f"[{request_id}]  {text_preview}")
        logger.info(f"[{request_id}] " + "-" * 40)
        
        if DEBUG_MODE and hit.score < 0.6:
            logger.warning(f"[{request_id}]  ⚠️ Low score detected: {hit.score:.4f}")

    contexts = [format_context(hit.payload) for hit in top_hits]
    
    # 포맷팅된 컨텍스트 로깅
    if VERBOSE_LOGGING and contexts:
        logger.info(f"[{request_id}] " + "=" * 60)
        logger.info(f"[{request_id}] 📝 포맷팅된 컨텍스트")
        logger.info(f"[{request_id}] " + "=" * 60)
        for i, ctx in enumerate(contexts, 1):
            logger.info(f"[{request_id}] 컨텍스트 {i}:")
            logger.info(f"[{request_id}] {ctx[:500]}..." if len(ctx) > 500 else f"[{request_id}] {ctx}")
            logger.info(f"[{request_id}] " + "-" * 40)
    
    references = []
    for hit in top_hits:
        if source == "mail":
            # 메일 모드: 메일 링크 처리
            link_value = hit.payload.get("link")
            if link_value:
                # Debug logging for link
                logger.info(f"[{request_id}] Found mail link: {link_value[:50]}...")
                
                ref_title = hit.payload.get("mail_subject") or hit.payload.get("subject", "N/A")
                ref_date = hit.payload.get("sent_date") or hit.payload.get("date", "N/A")
                references.append({
                    "title": ref_title,
                    "date": ref_date,
                    "sender": hit.payload.get("sender", "N/A"),
                    "link": link_value,
                    "entry_id": hit.payload.get("entry_id") or hit.payload.get("mail_id"),
                    "display_url": hit.payload.get("display_url"),
                    "type": "mail"
                })
            else:
                logger.warning(f"[{request_id}] No link found in mail payload. Available keys: {list(hit.payload.keys())}")
        else:  # source == "doc"
            # 문서 모드: 파일 경로 처리
            # 파일 경로는 다양한 필드명으로 저장될 수 있음
            file_path = (hit.payload.get("file_path") or 
                         hit.payload.get("document_path") or 
                         hit.payload.get("path") or 
                         hit.payload.get("link"))
            
            if file_path:
                # 문서 제목 추출
                doc_title = (hit.payload.get("title") or 
                           hit.payload.get("document_name") or 
                           hit.payload.get("filename") or 
                           hit.payload.get("name") or 
                           "문서")
                
                # 문서 날짜 추출
                doc_date = (hit.payload.get("created_date") or 
                          hit.payload.get("modified_date") or 
                          hit.payload.get("date") or 
                          "N/A")
                
                references.append({
                    "title": doc_title,
                    "date": doc_date,
                    "path": file_path,
                    "type": "document"
                })

    return "\n\n---\n\n".join(contexts), references


# --------------------------------------------------------------------------
# 5. API 엔드포인트
# --------------------------------------------------------------------------
@app.get("/")
def root():
    """API 루트 엔드포인트 - API 정보 제공"""
    return {
        "name": "Gauss-1 Backend API",
        "version": "1.0.4",
        "status": "running",
        "performance": {
            "model_warmed_up": model_manager.is_warmed_up,
            "keep_alive": config.OLLAMA_KEEP_ALIVE,
            "llm_timeout": config.LLM_TIMEOUT
        },
        "endpoints": {
            "GET /": "API information",
            "GET /health": "Health check",
            "GET /status": "Service status check",
            "POST /ask": "RAG question answering",
            "POST /open-mail": "Open mail (Outlook / http / file)",
            "POST /open-file": "Open department file (UNC / file)"
        },
        "description": "HD현대미포 선각기술부 RAG 시스템 백엔드 - 성능 최적화"
    }

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/status")
async def status():
    """시스템 상태를 확인하여 프론트엔드에 반환합니다."""
    import asyncio
    import aiohttp
    import socket
    
    async def ping_async(url, timeout=2.0):
        """비동기로 서비스 상태를 체크합니다."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                    logger.info(f"✅ Status check {url}: {response.status}")
                    return response.status in [200, 204]
        except Exception as e:
            logger.warning(f"❌ Status check {url} failed: {e}")
            return False
    
    def check_port_open(host, port):
        """포트가 열려있는지 확인합니다."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(1.0)
                result = sock.connect_ex((host, port))
                is_open = result == 0
                logger.info(f"🔍 Port check {host}:{port}: {'OPEN' if is_open else 'CLOSED'}")
                return is_open
        except Exception as e:
            logger.warning(f"❌ Port check {host}:{port} failed: {e}")
            return False
    
    # 서비스 URL 구성
    ollama_url = config.OLLAMA_API_URL.replace("/api/chat", "/")
    qdrant_mail_url = f"http://{config.MAIL_QDRANT_HOST}:{config.MAIL_QDRANT_PORT}/"
    
    logger.info(f"🔄 Status check starting...")
    logger.info(f"  Ollama URL: {ollama_url}")
    logger.info(f"  Qdrant Mail URL: {qdrant_mail_url}")
    
    # 개인 Qdrant (실제 포트 체크 + HTTP 체크)
    qdrant_mail_port_status = check_port_open(config.MAIL_QDRANT_HOST, config.MAIL_QDRANT_PORT)
    
    # Ollama와 개인 Qdrant HTTP 체크
    results = await asyncio.gather(
        ping_async(ollama_url),
        ping_async(qdrant_mail_url),  # HTTP 체크 항상 수행
        return_exceptions=True
    )
    
    # Qdrant 상태: 포트가 열려있거나 HTTP 응답이 성공하면 True
    qdrant_mail_http_status = results[1] if not isinstance(results[1], Exception) else False
    qdrant_mail_status = qdrant_mail_port_status or qdrant_mail_http_status
    
    # 부서 서버는 항상 false (요구사항에 따라)
    qdrant_doc_status = False
    
    status_result = {
        "fastapi": True,  # 응답 가능하므로 True
        "ollama": results[0] if not isinstance(results[0], Exception) else False,
        "qdrant_mail": qdrant_mail_status,
        "qdrant_doc": qdrant_doc_status,  # 부서 서버는 무시
    }
    
    logger.info(f"📊 Status result: {status_result}")
    return status_result

@app.post("/open_file")
@app.post("/open-file")  # 프론트엔드 호환용 하이픈 버전 추가
async def open_file(request: Request):
    """
    문서 열기(부서 데이터).
    - 입력: file_path | path | display_url | link
    - 지원: file:/// URI, UNC(\server\share\...), 로컬(C:\...)
    """
    import os
    from fastapi import HTTPException
    import subprocess
    from urllib.parse import urlparse, unquote
    
    # --- UNC 강제 보정: IP 시작 경로의 경계/접두 \\ 회복 ---
    def _force_unc(p: str) -> str:
        s = p
        
        # 0) 이미 \\로 시작하면 그대로 두되, \\server 다음 구분자 검사
        if s.startswith("\\\\"):
            return s
        
        # 1) "203.228.239.6..." 처럼 IP로 시작하는지 판별
        i = 0
        while i < len(s) and (s[i].isdigit() or s[i] == "."):
            i += 1
        
        ip = s[:i]
        rest = s[i:]
        
        def _looks_like_ip(x: str) -> bool:
            parts = x.split(".")
            if len(parts) != 4:
                return False
            for part in parts:
                if not part.isdigit():
                    return False
                n = int(part)
                if n < 0 or n > 255:
                    return False
            return True
        
        if _looks_like_ip(ip):
            if not rest.startswith("\\"):
                rest = "\\" + rest.lstrip("\\")
            s = "\\\\" + ip + rest
        
        return s

    # 0) 요청 파싱
    body = await request.json()
    logger.info(f"받은 파일 경로(raw): {body.get('file_path') or body.get('path') or body.get('display_url') or body.get('link')}")
    raw = (
        body.get("file_path")
        or body.get("path")
        or body.get("display_url")
        or body.get("link")
        or ""
    )
    if not raw:
        raise HTTPException(status_code=400, detail="파일 경로가 비어있습니다.")

    # 1) 조각(#fragment) 제거 + 양끝 공백/따옴표 제거
    def strip_fragment(p: str) -> str:
        return str(p).split("#", 1)[0]
    path = strip_fragment(raw).strip().strip('"').strip("'")

    # 2) file:/// → Windows 경로로 변환 (정규식 사용하지 않음)
    if path.lower().startswith("file://"):
        u = urlparse(path)
        if u.netloc:
            path = "\\\\" + u.netloc + unquote(u.path.replace("/", "\\"))
        else:
            path = unquote(u.path.replace("/", "\\"))
    else:
        # 3) 줄바꿈을 백슬래시로 + 슬래시 통일
        path = path.replace("\r\n", "\\").replace("\r", "\\").replace("\n", "\\")
        path = path.replace("/", "\\")

        # 4) 백슬래시 주변 공백만 정돈(세그먼트 내용은 보전)
        path = re.sub(r"\s*\\\s*", r"\\", path)

        # 5) 세그먼트별 좌우 공백 제거
        is_unc = path.startswith("\\\\")
        parts = [seg.strip() for seg in path.split("\\") if seg]
        path = ("\\\\" if is_unc else "") + "\\".join(parts)
    
    # 새로운 UNC 보정 함수 적용
    path = _force_unc(path)
    logger.info(f"정규화된 파일 경로(안전): {path}")

    # 6) 열기
    if os.path.exists(path):
        if os.name == "nt":
            os.startfile(path)
            logger.info(f"파일 열기 성공: {path}")
            return {"status": "success", "path": path}
        else:
            raise HTTPException(status_code=501, detail="Windows에서만 지원됩니다.")
    else:
        logger.error(f"파일을 찾을 수 없습니다: {path}")
        parent = os.path.dirname(path)
        if parent and os.path.isdir(parent):
            try:
                subprocess.Popen(["explorer.exe", parent])
            except Exception:
                pass
        raise HTTPException(status_code=404, detail=f"파일을 찾을 수 없습니다: {path}")

@app.post("/open-mail")
@app.post("/open_mail")  # 구버전/프런트 혼용 대비 호환 라우트 추가
async def open_mail(request: Request):
    """통합된 메일/파일 열기 엔드포인트 (POST 방식)"""
    import webbrowser
    
    try:
        body = await request.json()
    except Exception:
        body = {}
    
    # entry_id는 outlook://... 또는 MAPI EntryID가 들어올 수 있음
    entry_id = (body.get("entry_id")
                or body.get("id")
                or body.get("link_key")
                or body.get("link")
                or "")
    display_url = (body.get("display_url")
                   or body.get("url")
                   or "")
    
    logger.info(f"[open_mail] keys={list(body.keys())} "
                f"entry_id(head)={str(entry_id)[:40]} "
                f"display_url(head)={str(display_url)[:40]}")
    
    # link_key가 있으면 디코딩
    if entry_id:
        entry_id = urllib.parse.unquote(entry_id)
    
    # 1. file:/// 스키마 처리
    if entry_id and entry_id.startswith("file:///"):
        try:
            # file:/// 이후 경로 추출
            path = urllib.parse.unquote(entry_id[8:])
            # Windows 경로 정규화 (슬래시를 백슬래시로 변환)
            path = os.path.normpath(path)
            logger.info(f"[open_mail] 정규화된 경로: {path}")
            
            if os.path.exists(path):
                os.startfile(path)
                return {"ok": True, "via": "file", "path": path}
            else:
                raise FileNotFoundError(f"파일을 찾을 수 없습니다: {path}")
        except Exception as e:
            logger.error(f"[open_mail] file:/// 열기 실패: {e}")
            raise HTTPException(status_code=400, detail=str(e))
    
    # 2. HTTP(S) 웹 링크 처리
    if display_url and display_url.startswith(("http://", "https://")):
        try:
            webbrowser.open(display_url)
            return {"ok": True, "via": "web", "url": display_url}
        except Exception as e:
            logger.error(f"웹 링크 열기 실패: {e}")
    
    # 3. outlook:// 스키마 처리 (및 일반 EntryID 포함)
    if entry_id:
        if not WIN_COM_AVAILABLE:
            raise HTTPException(status_code=501, detail="Outlook 연동이 필요합니다(Windows/pywin32).")

        pythoncom.CoInitialize()
        try:
            # outlook:// 접두어 제거
            mapi_id = entry_id
            if mapi_id.lower().startswith("outlook://"):
                mapi_id = mapi_id[10:]
            mapi_id = mapi_id.strip().strip('"').strip("'")

            outlook = win32com.client.Dispatch("Outlook.Application")
            session = outlook.Session  # GetNamespace("MAPI")와 동일

            # 1) 기본 스토어 시도
            try:
                item = session.GetItemFromID(mapi_id)
                item.Display(True)
                return {"ok": True, "via": "outlook", "entry_id": mapi_id, "store": "default"}
            except Exception:
                logger.info("[open_mail] Default store 조회 실패, Stores 순회 시도")

            # 2) 모든 Store 전수 탐색
            for store in session.Stores:
                try:
                    item = session.GetItemFromID(mapi_id, store.StoreID)
                    item.Display(True)
                    return {"ok": True, "via": "outlook", "entry_id": mapi_id, "store": store.DisplayName}
                except Exception:
                    logger.debug(f"[open_mail] Store '{store.DisplayName}' 미적중")
                    continue

            # 3) 못 찾으면 명확히 에러
            raise HTTPException(
                status_code=404,
                detail="Outlook에서 해당 메시지를 찾지 못했습니다(EntryID/Store 불일치/만료)."
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Outlook 메일 열기 실패: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Outlook 메일 열기 실패: {e}")
        finally:
            pythoncom.CoUninitialize()
    # 4. 일반 EntryID 처리 (outlook:// 없이)
    if entry_id and not entry_id.startswith(("file://", "http://", "https://")):
        if not WIN_COM_AVAILABLE:
            raise HTTPException(status_code=501, detail="Outlook 연동이 필요합니다(Windows/pywin32).")
        
        pythoncom.CoInitialize()
        try:
            outlook = win32com.client.Dispatch("Outlook.Application")
            mapi_ns = outlook.GetNamespace("MAPI")
            item = mapi_ns.GetItemFromID(entry_id)
            item.Display(True)
            return {"ok": True, "via": "mapi", "entry_id": entry_id}
        except Exception as e:
            logger.error(f"MAPI 메일 열기 실패: {e}")
            raise HTTPException(status_code=500, detail=f"MAPI 메일 열기 실패: {e}")
        finally:
            pythoncom.CoUninitialize()
    
    # 아무것도 제공되지 않은 경우
    raise HTTPException(status_code=400, detail="entry_id 또는 display_url이 필요합니다.")

@app.post("/ask")
async def ask(req: Request):
    """사용자 질문에 대한 RAG 답변을 스트리밍합니다."""
    request_id = str(uuid.uuid4())
    logger.info(f"--- RAG REQUEST START: {request_id} ---")

    try:
        if not all(k in app_state for k in ["embeddings", "qdrant_clients"]):
            raise HTTPException(status_code=503, detail="서비스가 준비되지 않았습니다.")

        # JSON 요청 파싱 with encoding handling
        try:
            body = await req.json()
        except UnicodeDecodeError as e:
            logger.error(f"[{request_id}] JSON 디코딩 오류: {e}")
            raise HTTPException(status_code=400, detail="요청 데이터 인코딩에 문제가 있습니다.")
        except Exception as e:
            logger.error(f"[{request_id}] JSON 파싱 오류: {e}")
            raise HTTPException(status_code=400, detail="잘못된 JSON 형식입니다.")
        question = body.get("question", "").strip()
        model = body.get("model", config.DEFAULT_LLM_MODEL)
        source = body.get("source", "mail")  # 기본 mail

        if source not in ("mail", "doc"):
            raise HTTPException(status_code=400, detail="source must be 'mail' or 'doc'")

        if not question:
            raise HTTPException(status_code=400, detail="질문이 비어있습니다.")
        
        if any(greet in question for greet in config.GREETINGS):
            async def greeting_stream():
                yield json.dumps({"answer_chunk": "안녕하세요! 무엇을 도와드릴까요?", "references": []})
            return StreamingResponse(greeting_stream(), media_type="application/x-ndjson")

        logger.info(f"[{request_id}] 📨 Original Question: {question}")
        logger.info(f"[{request_id}] 📁 Source: {source}")
        logger.info(f"[{request_id}] 🤖 Model: {model}")
        
        client = app_state["qdrant_clients"][source]
        endpoint = app_state["qdrant_endpoints"][source]
        collections = config.MAIL_QDRANT_COLLECTIONS if source == "mail" else config.DOC_QDRANT_COLLECTIONS
        
        logger.info(f"[{request_id}] 🌐 Qdrant endpoint: {endpoint}")
        logger.info(f"[{request_id}] 🗂️ Collections: {collections}")
        
        # 방어적 검증: 소스-엔드포인트 충돌 시 즉시 경고
        if source == "doc" and endpoint == app_state["qdrant_endpoints"]["mail"]:
            logger.error(f"[{request_id}] ❌ DOC 요청인데 MAIL 엔드포인트가 선택됨! 환경변수/초기화 확인 필요")
        if source == "mail" and endpoint == app_state["qdrant_endpoints"]["doc"]:
            logger.error(f"[{request_id}] ❌ MAIL 요청인데 DOC 엔드포인트가 선택됨! 환경변수/초기화 확인 필요")
        
        context_text, references = search_qdrant(question, request_id, client, config, source, collections)
        
        if not context_text:
            logger.warning(f"[{request_id}] ⚠️ No context found for question: {question}")
        else:
            logger.info(f"[{request_id}] ✅ Context prepared with {len(references)} references")
        
        # source에 따른 메타프롬프트 분리
        if source == "mail":
            final_prompt = dedent(f"""\
                당신은 HD현대미포 선각기술부의 메일 검색 비서입니다.
                반드시 한국어로 간결하게 답변하세요.
                
                질문: {question}

                참고 메일:
                {context_text or "참고 자료 없음"}
                
                답변 규칙:
                - 한국어로만 답변
                - 400자 이내로 답변
                - 불릿 포인트 3개 이내
                - 핵심만 간결하게
                - 참고 메일이 제공된 경우 반드시 해당 내용을 바탕으로 답변
                - 참고 메일이 "참고 자료 없음"인 경우에만 "관련 메일을 찾을 수 없습니다" 응답
                - 중요: 답변에는 링크, URL, 이메일 주소를 절대 포함하지 마세요
                - 중요: "링크", "URL", "http", "mailto" 등의 단어를 답변에 사용하지 마세요""")
        else:  # source == "doc"
            final_prompt = dedent(f"""\
                당신은 HD현대미포 선각기술부의 문서 검색 비서입니다.
                반드시 한국어로 간결하게 답변하세요.
                
                질문: {question}

                참고 문서:
                {context_text or "참고 자료 없음"}
                
                답변 규칙:
                - 한국어로만 답변
                - 400자 이내로 답변
                - 불릿 포인트 3개 이내
                - 핵심만 간결하게
                - 참고 문서가 제공된 경우 반드시 해당 내용을 바탕으로 답변
                - 참고 문서가 "참고 자료 없음"인 경우에만 "관련 문서를 찾을 수 없습니다" 응답
                - 중요: 답변에는 링크, URL, 파일 경로를 절대 포함하지 마세요
                - 중요: "링크", "URL", "http", "file://" 등의 단어를 답변에 사용하지 마세요""")

        # Ollama로 전송되는 최종 프롬프트 로깅
        if DEBUG_MODE:
            logger.info(f"[{request_id}] " + "=" * 60)
            logger.info(f"[{request_id}] 📮 OLLAMA 프롬프트")
            logger.info(f"[{request_id}] " + "=" * 60)
            # 프롬프트를 줄 단위로 출력 (너무 길어서)
            prompt_lines = final_prompt.split('\n')
            for line in prompt_lines[:50]:  # 처음 50줄만
                if line.strip():
                    logger.info(f"[{request_id}] {line}")
            if len(prompt_lines) > 50:
                logger.info(f"[{request_id}] ... (총 {len(prompt_lines)}줄, 나머지 생략)")
            logger.info(f"[{request_id}] " + "=" * 60)

        async def response_generator():
            full_answer = ""
            async for chunk in stream_llm_response(final_prompt, model, request_id):
                full_answer += chunk
                yield json.dumps({"answer_chunk": chunk}) + "\n"
            
            yield json.dumps({"references": references}) + "\n"
            
            dialog_cache.append((question, full_answer))
            
            # LLM 최종 답변 로깅
            if DEBUG_MODE:
                logger.info(f"[{request_id}] " + "=" * 60)
                logger.info(f"[{request_id}] 💬 LLM 최종 답변")
                logger.info(f"[{request_id}] " + "=" * 60)
                logger.info(f"[{request_id}] {full_answer}")
                logger.info(f"[{request_id}] " + "=" * 60)

        return StreamingResponse(response_generator(), media_type="application/x-ndjson")

    except HTTPException as he:
        logger.error(f"[{request_id}] HTTP Exception: {he.detail} (status: {he.status_code})")
        raise he
    except Exception as e:
        logger.error(f"[{request_id}] /ask 엔드포인트에서 예상치 못한 오류 발생: {e}", exc_info=True)
        
        # 더 구체적인 에러 메시지 제공
        error_detail = "서버에서 내부 오류가 발생했습니다."
        if "connection" in str(e).lower():
            error_detail = "데이터베이스 연결에 실패했습니다."
        elif "timeout" in str(e).lower():
            error_detail = "요청 처리 중 시간이 초과되었습니다."
        elif "model" in str(e).lower():
            error_detail = "AI 모델 처리 중 오류가 발생했습니다."
        
        raise HTTPException(status_code=500, detail=error_detail)
    finally:
        logger.info(f"--- RAG REQUEST END: {request_id} ---")


# --------------------------------------------------------------------------
# 6. 서버 실행
# --------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("RAG_PORT", "8080"))  # 기본 포트를 8080으로
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")