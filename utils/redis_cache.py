# utils/redis_cache.py
import os
import json
import hashlib
from functools import wraps
from datetime import datetime
import warnings

# ====================== GRACEFUL REDIS (local + Render) ======================
REDIS_URL = os.getenv("REDIS_URL")

if REDIS_URL:
    try:
        from redis import Redis
        redis_client = Redis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_timeout=3,
            socket_connect_timeout=3,
            retry_on_timeout=True
        )
        redis_client.ping()
        REDIS_AVAILABLE = True
    except Exception as e:
        warnings.warn(f"Redis connection failed: {e}. Falling back to in-memory cache.")
        REDIS_AVAILABLE = False
        redis_client = None
else:
    warnings.warn("REDIS_URL not set → using in-memory cache for local dev.")
    REDIS_AVAILABLE = False
    redis_client = None

# ====================== IN-MEMORY FALLBACK ======================
_memory_cache = {}

def _get_cache(key: str):
    if REDIS_AVAILABLE and redis_client:
        return redis_client.get(key)
    return _memory_cache.get(key)

def _set_cache(key: str, value, ttl_seconds: int = 1800):
    if REDIS_AVAILABLE and redis_client:
        redis_client.setex(key, ttl_seconds, value)
    else:
        _memory_cache[key] = value

# ====================== RAG CACHE DECORATOR ======================
def cache_rag_result(ttl_seconds: int = 1800):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key_parts = [str(arg) for arg in args] + [f"{k}:{v}" for k, v in sorted(kwargs.items())]
            cache_key = f"rag:{hashlib.sha256(':'.join(key_parts).encode()).hexdigest()[:16]}"
            
            cached = _get_cache(cache_key)
            if cached is not None:
                _log_cache_event(cache_key, "HIT")
                return json.loads(cached) if isinstance(cached, str) else cached
            
            result = func(*args, **kwargs)
            
            # NEW: Graceful skip for non-JSON objects (like PGVector)
            try:
                json.dumps(result)
                _set_cache(cache_key, json.dumps(result), ttl_seconds)
                _log_cache_event(cache_key, "MISS")
            except TypeError:
                _log_cache_event(cache_key, "SKIP_NON_SERIALIZABLE")
                pass
            
            return result
        return wrapper
    return decorator
# ====================== SESSION HELPERS (FIXED: always return list) ======================
def save_session_to_redis(session_id: str, data: list, ttl_seconds: int = 86400):
    """data MUST be list of messages"""
    if REDIS_AVAILABLE and redis_client:
        redis_client.setex(f"session:{session_id}", ttl_seconds, json.dumps(data))
    else:
        _memory_cache[f"session:{session_id}"] = data

def load_session_from_redis(session_id: str) -> list:
    """Always returns list (never dict)"""
    if REDIS_AVAILABLE and redis_client:
        data = redis_client.get(f"session:{session_id}")
        if data:
            loaded = json.loads(data)
            return loaded if isinstance(loaded, list) else []
        return []
    else:
        return _memory_cache.get(f"session:{session_id}", [])

# ====================== AUDIT LOG ======================
def _log_cache_event(cache_key: str, event: str):
    try:
        import sqlite3
        conn = sqlite3.connect("data/audit.db")
        conn.execute("""INSERT INTO rag_usage_log 
                     (timestamp, event_type, cache_key, model)
                     VALUES (datetime('now'),?,?,?)""",
                     (event, cache_key, "gemini-1.5-pro"))
        conn.commit()
        conn.close()
    except Exception:
        pass