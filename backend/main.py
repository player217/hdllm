import os
import re
import logging
import json
import uuid
import datetime
import urllib.parse
from collections import deque
from contextlib import asynccontextmanager
from textwrap import dedent
from pathlib import Path
import hashlib

import torch
import requests
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import Response, StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from qdrant_client import QdrantClient, models
from langchain_huggingface import HuggingFaceEmbeddings

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
    EMBEDDING_MODEL_PATH: str = str(EMBEDDING_MODEL_DEFAULT_PATH)
    OLLAMA_API_URL: str = os.getenv("RAG_OLLAMA_URL", "http://127.0.0.1:11434/api/chat")
    
    # 기존 필드 유지
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTIONS: list[str] = ["my_documents"]
    QDRANT_SCORE_THRESHOLD: float = 0.30  # Lowered threshold to find more results
    QDRANT_SEARCH_LIMIT: int = 3  # Reduce to 3 for faster processing
    QDRANT_TIMEOUT: float = 30.0
    QDRANT_SEARCH_PARAMS: dict = {
        "hnsw_ef": 128,  # Increase for better accuracy (default: 128)
        "exact": False   # Use approximate search for speed
    }
    
    # 신규: 쿼리용 네트워크 엔드포인트(경로와 무관)
    MAIL_QDRANT_HOST: str = os.getenv("RAG_MAIL_QDRANT_HOST", "127.0.0.1")
    MAIL_QDRANT_PORT: int = int(os.getenv("RAG_MAIL_QDRANT_PORT", "6333"))
    
    DOC_QDRANT_HOST: str = os.getenv("RAG_DOC_QDRANT_HOST", "127.0.0.1")
    DOC_QDRANT_PORT: int = int(os.getenv("RAG_DOC_QDRANT_PORT", "6333"))
    
    DEFAULT_LLM_MODEL: str = "gemma3:4b"
    LLM_TIMEOUT: int = 60
    GREETINGS: list[str] = ["안녕", "안녕하세요", "ㅎㅇ", "하이", "반가워", "반갑습니다"]

config = AppConfig()
app_state = {}
dialog_cache: deque[tuple[str, str]] = deque(maxlen=3)

# Embedding cache with LRU (Least Recently Used) eviction
# Cache up to 100 queries to balance memory and performance
embedding_cache = {}
MAX_CACHE_SIZE = 100


# --------------------------------------------------------------------------
# 3. FastAPI 생명주기 및 앱 초기화
# --------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 시작 시 모델 및 클라이언트 로드, 종료 시 정리"""
    logger.info("🚀 애플리케이션 시작...")
    logger.info(f"📦 Backend Version: 1.0.3 - Updated")
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
        # Qdrant 클라이언트 2개 초기화
        app_state["qdrant_clients"] = {
            "mail": QdrantClient(host=config.MAIL_QDRANT_HOST, port=config.MAIL_QDRANT_PORT, timeout=config.QDRANT_TIMEOUT),
            "doc": QdrantClient(host=config.DOC_QDRANT_HOST, port=config.DOC_QDRANT_PORT, timeout=config.QDRANT_TIMEOUT),
        }
        logger.info("✅ Qdrant 클라이언트들 연결 성공.")
        
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

    yield
    
    logger.info("🌙 애플리케이션 종료...")
    app_state.clear()
    dialog_cache.clear()

# Initialize base FastAPI app
app = FastAPI(lifespan=lifespan)

# Import security configuration
try:
    from security_config import (
        CORS_CONFIG, 
        QuestionRequest, 
        EnhancedPIIMasker,
        get_current_user,
        SecurityMiddleware,
        sanitize_log_message
    )
    SECURITY_ENABLED = True
except ImportError:
    logger.warning("Security module not found, using legacy configuration")
    SECURITY_ENABLED = False
    CORS_CONFIG = {
        "allow_origins": ["*"],
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"]
    }

# Phase 3 Integration - Apply comprehensive enhancements
try:
    from integration import create_integrated_app
    
    # Transform app with Phase 3 integration
    app = create_integrated_app(
        existing_app=app,
        enable_security=SECURITY_ENABLED,
        development_mode=DEBUG_MODE
    )
    logger.info("✅ Phase 3 integration applied successfully")
    
    # Legacy middleware for compatibility (already handled in integration)
    PHASE3_INTEGRATED = True
    
except ImportError as e:
    logger.warning(f"Phase 3 integration not available: {e}")
    PHASE3_INTEGRATED = False
    
    # Fallback to legacy configuration
    app.add_middleware(CORSMiddleware, **CORS_CONFIG)
    
    # Add security middleware if available
    if SECURITY_ENABLED:
        app.add_middleware(SecurityMiddleware)
        
        # Include authentication routes
        try:
            from auth_routes import router as auth_router
            app.include_router(auth_router)
            logger.info("Authentication routes loaded successfully")
        except ImportError:
            logger.warning("Authentication routes not available")


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
    
    json_data = {
        "model": model,
        "messages": [
            {"role": "system", "content": "당신은 HD현대미포의 한국어 AI 어시스턴트입니다. 반드시 한국어로만 응답하세요. 영어나 다른 언어는 절대 사용하지 마세요. 모든 답변은 정중하고 명확한 한국어로 작성해주세요."},
            {"role": "user", "content": prompt}
        ],
        "stream": True,
        "options": {"temperature": 0.3}  # Slight temperature for more natural Korean
    }
    
    try:
        with requests.post(
            config.OLLAMA_API_URL, json=json_data, timeout=config.LLM_TIMEOUT, stream=True
        ) as res:
            res.raise_for_status()
            # Increase buffer size to 8KB for better streaming performance
            for chunk in res.iter_lines(chunk_size=8192):
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

def search_qdrant(question: str, request_id: str, client: QdrantClient, config: AppConfig, source: str = "mail") -> tuple[str, list[dict]]:
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
    for collection_name in config.QDRANT_COLLECTIONS:
        try:
            logger.info(f"[{request_id}] 🔎 Searching collection: '{collection_name}'")
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
                        logger.debug(f"[{request_id}]   Hit {i}: score={hit.score:.4f}, id={hit.id}")
                        logger.debug(f"[{request_id}]   Metadata keys: {list(hit.payload.keys())}")
                        if VERBOSE_LOGGING:
                            # 메타데이터 일부 출력 (텍스트 제외)
                            meta_preview = {k: v for k, v in hit.payload.items() if k != 'text' and k != 'embedding'}
                            logger.debug(f"[{request_id}]   Metadata preview: {meta_preview}")
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
        logger.info(f"[{request_id}]   점수: {hit.score:.4f}")
        logger.info(f"[{request_id}]   제목: {title}")
        logger.info(f"[{request_id}]   발신자: {sender}")
        logger.info(f"[{request_id}]   날짜: {date}")
        logger.info(f"[{request_id}]   텍스트 미리보기:")
        logger.info(f"[{request_id}]   {text_preview}")
        logger.info(f"[{request_id}] " + "-" * 40)
        
        if DEBUG_MODE and hit.score < 0.6:
            logger.warning(f"[{request_id}]   ⚠️ Low score detected: {hit.score:.4f}")

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
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "GET /": "API information",
            "GET /health": "Health check",
            "GET /status": "Service status check",
            "POST /ask": "RAG question answering",
            "GET /open_mail": "Open mail in Outlook (Windows only)"
        },
        "description": "HD현대미포 선각기술부 RAG 시스템 백엔드"
    }

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/status")
async def status():
    """프런트가 더 이상 외부 IP를 직접 치지 않도록, 백엔드가 올라마/두 Qdrant를 확인해 결과를 돌려줍니다."""
    import asyncio
    import aiohttp
    
    async def ping_async(url, timeout=1.0):
        """비동기로 서비스 상태를 체크합니다."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                    return response.status == 200
        except Exception:
            return False
    
    # 병렬로 모든 서비스 체크
    ollama_url = config.OLLAMA_API_URL.replace("/api/chat", "/")
    qdrant_mail_url = f"http://{config.MAIL_QDRANT_HOST}:{config.MAIL_QDRANT_PORT}/"
    qdrant_doc_url = f"http://{config.DOC_QDRANT_HOST}:{config.DOC_QDRANT_PORT}/"
    
    results = await asyncio.gather(
        ping_async(ollama_url),
        ping_async(qdrant_mail_url),
        ping_async(qdrant_doc_url),
        return_exceptions=True
    )
    
    return {
        "fastapi": True,  # 살아있으니 True
        "ollama": results[0] if not isinstance(results[0], Exception) else False,
        "qdrant_mail": results[1] if not isinstance(results[1], Exception) else False,
        "qdrant_doc": results[2] if not isinstance(results[2], Exception) else False,
    }

@app.post("/open_file")
async def open_file(request: Request):
    """파일 경로를 받아서 파일을 엽니다 (부서 문서용)."""
    try:
        body = await request.json()
        file_path = body.get("file_path", "")
        
        logger.info(f"받은 파일 경로: {file_path}")
        
        if not file_path:
            raise HTTPException(status_code=400, detail="파일 경로가 비어있습니다.")
        
        # Handle various path formats
        # Remove quotes if present
        file_path = file_path.strip('"').strip("'")
        
        # Handle file:// URLs
        if file_path.startswith('file:///'):
            # Convert file:///C:/path to C:/path
            file_path = file_path[8:]  # Remove 'file:///'
        elif file_path.startswith('file://'):
            # Convert file://path to path
            file_path = file_path[7:]  # Remove 'file://'
        
        # Convert forward slashes to backslashes for Windows
        if os.name == 'nt':
            file_path = file_path.replace('/', '\\')
        
        logger.info(f"처리된 파일 경로: {file_path}")
        
        # Check if file exists
        if os.path.exists(file_path):
            if os.name == 'nt':
                # Windows에서 os.startfile 사용
                os.startfile(file_path)
                logger.info(f"파일 열기 성공: {file_path}")
                return {"status": "success", "message": "파일을 열었습니다."}
            else:
                # Non-Windows 시스템에서는 지원하지 않음
                raise HTTPException(status_code=501, detail="파일 열기는 Windows 환경에서만 지원됩니다.")
        else:
            logger.error(f"파일을 찾을 수 없습니다: {file_path}")
            raise HTTPException(status_code=404, detail=f"파일을 찾을 수 없습니다: {file_path}")
                
    except HTTPException:
        # HTTPException은 그대로 다시 발생
        raise
    except Exception as e:
        logger.error(f"파일 열기 실패: {e}")
        raise HTTPException(status_code=500, detail=f"파일 열기 중 오류 발생: {str(e)}")

@app.post("/open-mail")
async def open_mail(request: Request):
    """통합된 메일/파일 열기 엔드포인트 (POST 방식)"""
    import webbrowser
    
    body = await request.json()
    
    # 다양한 키 이름 지원
    entry_id = body.get("entry_id") or body.get("id") or body.get("link_key", "")
    display_url = body.get("display_url") or body.get("link") or body.get("url", "")
    
    # link_key가 있으면 디코딩
    if entry_id:
        entry_id = urllib.parse.unquote(entry_id)
    
    # 1. file:/// 스키마 처리
    if entry_id and entry_id.startswith("file:///"):
        try:
            path = urllib.parse.unquote(entry_id[8:])
            if os.path.exists(path):
                os.startfile(path)
                return {"ok": True, "via": "file", "path": path}
            else:
                raise FileNotFoundError(f"파일을 찾을 수 없습니다: {path}")
        except Exception as e:
            logger.error(f"파일 열기 실패: {e}")
            raise HTTPException(status_code=400, detail=str(e))
    
    # 2. HTTP(S) 웹 링크 처리
    if display_url and display_url.startswith(("http://", "https://")):
        try:
            webbrowser.open(display_url)
            return {"ok": True, "via": "web", "url": display_url}
        except Exception as e:
            logger.error(f"웹 링크 열기 실패: {e}")
    
    # 3. outlook:// 스키마 처리
    if entry_id and entry_id.startswith("outlook://"):
        if not WIN_COM_AVAILABLE:
            raise HTTPException(status_code=501, detail="Outlook 연동이 필요합니다(Windows/pywin32).")
        
        pythoncom.CoInitialize()
        try:
            mapi_id = entry_id[10:]  # outlook:// 제거
            outlook = win32com.client.Dispatch("Outlook.Application")
            mapi_ns = outlook.GetNamespace("MAPI")
            item = mapi_ns.GetItemFromID(mapi_id)
            item.Display(True)
            return {"ok": True, "via": "outlook", "entry_id": mapi_id}
        except Exception as e:
            logger.error(f"Outlook 메일 열기 실패: {e}")
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
async def ask(
    req: Request,
    current_user: str = Depends(get_current_user) if SECURITY_ENABLED else None
):
    """사용자 질문에 대한 RAG 답변을 스트리밍합니다."""
    request_id = str(uuid.uuid4())
    user_info = f" (User: {current_user})" if current_user else ""
    logger.info(f"--- RAG REQUEST START: {request_id}{user_info} ---")

    try:
        if not all(k in app_state for k in ["embeddings", "qdrant_clients"]):
            raise HTTPException(status_code=503, detail="서비스가 준비되지 않았습니다.")

        # Use validated model if security is enabled
        if SECURITY_ENABLED:
            body = await req.json()
            validated_request = QuestionRequest(**body)
            question = validated_request.question
            model = validated_request.model
            source = validated_request.source
        else:
            # Legacy validation
            body = await req.json()
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
        context_text, references = search_qdrant(question, request_id, client, config, source)
        
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
                - 600자 이내로 답변
                - 불릿 포인트 5개 이내
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
                - 600자 이내로 답변
                - 불릿 포인트 5개 이내
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

    except Exception as e:
        logger.error(f"[{request_id}] /ask 엔드포인트에서 오류 발생: {e}", exc_info=True)
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail="An internal server error occurred.")
    finally:
        logger.info(f"--- RAG REQUEST END: {request_id} ---")


# --------------------------------------------------------------------------
# 6. Qdrant 상태 체크 엔드포인트
# --------------------------------------------------------------------------
@app.get("/api/v2/system/qdrant/status")
async def check_qdrant_status():
    """Qdrant 서버 상태 확인"""
    try:
        from qdrant_client import QdrantClient
        client = QdrantClient(host="127.0.0.1", port=6333, timeout=5.0)
        
        # 컬렉션 목록 가져오기
        collections = client.get_collections()
        collection_count = len(collections.collections) if hasattr(collections, 'collections') else 0
        
        return {
            "connected": True,
            "collections": collection_count,
            "host": "127.0.0.1",
            "port": 6333,
            "status": "online"
        }
    except Exception as e:
        logger.warning(f"Qdrant 연결 실패: {e}")
        return {
            "connected": False,
            "error": str(e),
            "message": "Qdrant 서버에 연결할 수 없습니다. Qdrant가 실행 중인지 확인하세요.",
            "host": "127.0.0.1",
            "port": 6333,
            "status": "offline"
        }

# --------------------------------------------------------------------------
# 7. 서버 실행
# --------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("RAG_PORT", "8080"))  # 기본 포트를 8080으로
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")