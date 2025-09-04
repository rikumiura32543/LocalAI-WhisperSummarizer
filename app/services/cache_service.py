"""
キャッシュサービス（Redisベース）
"""

import json
import pickle
import redis
import time
from typing import Any, Optional, Dict, List, Union
from datetime import timedelta
import structlog
from functools import wraps
import hashlib

from app.core.config import settings

logger = structlog.get_logger(__name__)


class CacheService:
    """Redisベースキャッシュサービス"""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.enabled = False
        self._initialize_redis()
    
    def _initialize_redis(self):
        """Redis接続初期化"""
        try:
            # Redis設定（環境に応じて調整）
            redis_url = getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0')
            
            self.redis_client = redis.from_url(
                redis_url,
                decode_responses=False,  # バイナリデータも扱うためFalse
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True,
                max_connections=10
            )
            
            # 接続テスト
            self.redis_client.ping()
            self.enabled = True
            
            logger.info("Redis cache initialized successfully", redis_url=redis_url)
            
        except Exception as e:
            logger.warning("Failed to initialize Redis cache", error=str(e))
            self.redis_client = None
            self.enabled = False
    
    def _generate_key(self, namespace: str, key: str) -> str:
        """キャッシュキー生成"""
        return f"{settings.APP_NAME}:{namespace}:{key}"
    
    def _serialize_value(self, value: Any) -> bytes:
        """値のシリアライズ"""
        if isinstance(value, (str, int, float, bool)):
            return json.dumps(value).encode('utf-8')
        else:
            return pickle.dumps(value)
    
    def _deserialize_value(self, data: bytes) -> Any:
        """値のデシリアライズ"""
        try:
            # まずJSONとして試行
            return json.loads(data.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            # pickleとしてデシリアライズ
            return pickle.loads(data)
    
    def set(self, namespace: str, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """キャッシュ設定"""
        if not self.enabled:
            return False
        
        try:
            cache_key = self._generate_key(namespace, key)
            serialized_value = self._serialize_value(value)
            
            if ttl:
                result = self.redis_client.setex(cache_key, ttl, serialized_value)
            else:
                result = self.redis_client.set(cache_key, serialized_value)
            
            logger.debug("Cache set", namespace=namespace, key=key, ttl=ttl)
            return bool(result)
            
        except Exception as e:
            logger.error("Cache set failed", error=str(e), namespace=namespace, key=key)
            return False
    
    def get(self, namespace: str, key: str) -> Any:
        """キャッシュ取得"""
        if not self.enabled:
            return None
        
        try:
            cache_key = self._generate_key(namespace, key)
            data = self.redis_client.get(cache_key)
            
            if data is None:
                logger.debug("Cache miss", namespace=namespace, key=key)
                return None
            
            value = self._deserialize_value(data)
            logger.debug("Cache hit", namespace=namespace, key=key)
            return value
            
        except Exception as e:
            logger.error("Cache get failed", error=str(e), namespace=namespace, key=key)
            return None
    
    def delete(self, namespace: str, key: str) -> bool:
        """キャッシュ削除"""
        if not self.enabled:
            return False
        
        try:
            cache_key = self._generate_key(namespace, key)
            result = self.redis_client.delete(cache_key)
            
            logger.debug("Cache deleted", namespace=namespace, key=key)
            return bool(result)
            
        except Exception as e:
            logger.error("Cache delete failed", error=str(e), namespace=namespace, key=key)
            return False
    
    def exists(self, namespace: str, key: str) -> bool:
        """キャッシュ存在確認"""
        if not self.enabled:
            return False
        
        try:
            cache_key = self._generate_key(namespace, key)
            return bool(self.redis_client.exists(cache_key))
            
        except Exception as e:
            logger.error("Cache exists check failed", error=str(e))
            return False
    
    def clear_namespace(self, namespace: str) -> bool:
        """名前空間のキャッシュクリア"""
        if not self.enabled:
            return False
        
        try:
            pattern = self._generate_key(namespace, "*")
            keys = self.redis_client.keys(pattern)
            
            if keys:
                result = self.redis_client.delete(*keys)
                logger.info("Cache namespace cleared", namespace=namespace, keys_deleted=result)
                return True
            
            return True
            
        except Exception as e:
            logger.error("Cache namespace clear failed", error=str(e), namespace=namespace)
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """キャッシュ統計情報"""
        if not self.enabled:
            return {"enabled": False}
        
        try:
            info = self.redis_client.info()
            
            return {
                "enabled": True,
                "used_memory": info.get("used_memory", 0),
                "used_memory_human": info.get("used_memory_human", "0B"),
                "total_commands_processed": info.get("total_commands_processed", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "connected_clients": info.get("connected_clients", 0),
            }
            
        except Exception as e:
            logger.error("Failed to get cache stats", error=str(e))
            return {"enabled": True, "error": str(e)}


# グローバルキャッシュサービスインスタンス
cache_service = CacheService()


def cache_result(namespace: str, key_func=None, ttl: int = 300):
    """キャッシュ結果デコレータ"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not cache_service.enabled:
                return func(*args, **kwargs)
            
            # キー生成
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # 関数名と引数からキー生成
                arg_str = "_".join(str(arg) for arg in args)
                kwarg_str = "_".join(f"{k}_{v}" for k, v in sorted(kwargs.items()))
                combined = f"{func.__name__}_{arg_str}_{kwarg_str}"
                cache_key = hashlib.md5(combined.encode()).hexdigest()
            
            # キャッシュから取得
            cached_result = cache_service.get(namespace, cache_key)
            if cached_result is not None:
                return cached_result
            
            # キャッシュミス - 実際の関数を実行
            result = func(*args, **kwargs)
            
            # 結果をキャッシュに保存
            cache_service.set(namespace, cache_key, result, ttl)
            
            return result
        
        return wrapper
    return decorator


class JobCache:
    """ジョブ専用キャッシュ"""
    
    NAMESPACE = "jobs"
    DEFAULT_TTL = 300  # 5分
    
    @staticmethod
    def get_job(job_id: str) -> Optional[Dict[str, Any]]:
        """ジョブ情報取得"""
        return cache_service.get(JobCache.NAMESPACE, job_id)
    
    @staticmethod
    def set_job(job_id: str, job_data: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """ジョブ情報設定"""
        ttl = ttl or JobCache.DEFAULT_TTL
        return cache_service.set(JobCache.NAMESPACE, job_id, job_data, ttl)
    
    @staticmethod
    def delete_job(job_id: str) -> bool:
        """ジョブ情報削除"""
        return cache_service.delete(JobCache.NAMESPACE, job_id)
    
    @staticmethod
    def set_job_status(job_id: str, status: str, progress: int = 0) -> bool:
        """ジョブステータス更新"""
        job_data = cache_service.get(JobCache.NAMESPACE, job_id) or {}
        job_data.update({
            "status": status,
            "progress": progress,
            "updated_at": int(time.time())
        })
        return cache_service.set(JobCache.NAMESPACE, job_id, job_data, JobCache.DEFAULT_TTL)


class ResultCache:
    """結果専用キャッシュ"""
    
    NAMESPACE = "results"
    DEFAULT_TTL = 1800  # 30分
    
    @staticmethod
    def get_transcription(job_id: str) -> Optional[str]:
        """転写結果取得"""
        return cache_service.get(ResultCache.NAMESPACE, f"transcription_{job_id}")
    
    @staticmethod
    def set_transcription(job_id: str, text: str, ttl: Optional[int] = None) -> bool:
        """転写結果設定"""
        ttl = ttl or ResultCache.DEFAULT_TTL
        return cache_service.set(ResultCache.NAMESPACE, f"transcription_{job_id}", text, ttl)
    
    @staticmethod
    def get_summary(job_id: str) -> Optional[Dict[str, Any]]:
        """要約結果取得"""
        return cache_service.get(ResultCache.NAMESPACE, f"summary_{job_id}")
    
    @staticmethod
    def set_summary(job_id: str, summary_data: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """要約結果設定"""
        ttl = ttl or ResultCache.DEFAULT_TTL
        return cache_service.set(ResultCache.NAMESPACE, f"summary_{job_id}", summary_data, ttl)


class StatisticsCache:
    """統計専用キャッシュ"""
    
    NAMESPACE = "stats"
    DEFAULT_TTL = 60  # 1分
    
    @staticmethod
    def get_system_stats() -> Optional[Dict[str, Any]]:
        """システム統計取得"""
        return cache_service.get(StatisticsCache.NAMESPACE, "system")
    
    @staticmethod
    def set_system_stats(stats: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """システム統計設定"""
        ttl = ttl or StatisticsCache.DEFAULT_TTL
        return cache_service.set(StatisticsCache.NAMESPACE, "system", stats, ttl)
    
    @staticmethod
    def get_job_counts() -> Optional[Dict[str, int]]:
        """ジョブ数統計取得"""
        return cache_service.get(StatisticsCache.NAMESPACE, "job_counts")
    
    @staticmethod
    def set_job_counts(counts: Dict[str, int], ttl: Optional[int] = None) -> bool:
        """ジョブ数統計設定"""
        ttl = ttl or StatisticsCache.DEFAULT_TTL
        return cache_service.set(StatisticsCache.NAMESPACE, "job_counts", counts, ttl)


def get_cache_service() -> CacheService:
    """キャッシュサービス取得（依存注入用）"""
    return cache_service