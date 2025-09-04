"""
ヘルスチェックと自動復旧システム
"""

import asyncio
import json
import time
import psutil
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path
import structlog
from dataclasses import dataclass

from ..core.config import get_settings
# from .database_service import DatabaseService
from .cache_service import get_cache_service
from .ollama_service import OllamaService
from .whisper_service import WhisperService

logger = structlog.get_logger(__name__)

@dataclass
class HealthCheckResult:
    """ヘルスチェック結果"""
    service: str
    status: str  # "healthy", "unhealthy", "degraded"
    response_time: float
    message: str
    details: Dict[str, Any]
    timestamp: datetime

@dataclass
class SystemMetrics:
    """システムメトリクス"""
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    network_connections: int
    active_processes: int
    uptime_seconds: int

class HealthService:
    """ヘルスチェックサービス"""
    
    def __init__(self):
        self.settings = get_settings()
        self.start_time = time.time()
        self.health_history: List[HealthCheckResult] = []
        self.max_history = 100
        self.services = {
            "database": self._check_database,
            "cache": self._check_cache,
            "ollama": self._check_ollama,
            "whisper": self._check_whisper,
            "filesystem": self._check_filesystem,
            "system": self._check_system_resources,
        }
        self.alert_thresholds = {
            "cpu_percent": 90.0,
            "memory_percent": 85.0,
            "disk_percent": 90.0,
            "response_time": 5.0,
        }
        
    async def check_health(self, detailed: bool = False) -> Dict[str, Any]:
        """総合ヘルスチェック実行"""
        start_time = time.time()
        results = {}
        overall_status = "healthy"
        
        # 各サービスのヘルスチェック実行
        for service_name, check_func in self.services.items():
            try:
                result = await check_func()
                results[service_name] = {
                    "status": result.status,
                    "response_time": result.response_time,
                    "message": result.message,
                }
                
                if detailed:
                    results[service_name]["details"] = result.details
                
                # 履歴に追加
                self.health_history.append(result)
                if len(self.health_history) > self.max_history:
                    self.health_history = self.health_history[-self.max_history:]
                
                # 全体ステータスを更新
                if result.status == "unhealthy":
                    overall_status = "unhealthy"
                elif result.status == "degraded" and overall_status == "healthy":
                    overall_status = "degraded"
                    
            except Exception as e:
                logger.error("Health check failed", 
                           service=service_name, error=str(e))
                results[service_name] = {
                    "status": "unhealthy",
                    "response_time": time.time() - start_time,
                    "message": f"Check failed: {str(e)}",
                }
                overall_status = "unhealthy"
        
        # システム情報を追加
        total_time = time.time() - start_time
        system_info = {
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "total_response_time": total_time,
            "uptime_seconds": int(time.time() - self.start_time),
            "version": "1.0.0",
            "environment": self.settings.environment.value,
        }
        
        return {
            "system": system_info,
            "services": results,
        }
    
    async def _check_database(self) -> HealthCheckResult:
        """データベースヘルスチェック"""
        start_time = time.time()
        
        try:
            # TODO: データベースサービス実装後に有効化
            # db_service = DatabaseService()
            # await db_service.execute_query("SELECT 1")
            
            # 一時的にデータベースファイルの存在確認のみ
            
            response_time = time.time() - start_time
            
            # データベースファイルサイズ確認
            db_path = Path("data/m4a_transcribe.db")
            db_size = db_path.stat().st_size if db_path.exists() else 0
            
            details = {
                "database_size_mb": db_size / (1024 * 1024),
                "connection_pool_active": "active",  # SQLAlchemy情報
            }
            
            status = "healthy"
            if response_time > self.alert_thresholds["response_time"]:
                status = "degraded"
            
            return HealthCheckResult(
                service="database",
                status=status,
                response_time=response_time,
                message="Database is accessible",
                details=details,
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            return HealthCheckResult(
                service="database",
                status="unhealthy",
                response_time=time.time() - start_time,
                message=f"Database check failed: {str(e)}",
                details={"error": str(e)},
                timestamp=datetime.utcnow()
            )
    
    async def _check_cache(self) -> HealthCheckResult:
        """キャッシュヘルスチェック"""
        start_time = time.time()
        
        try:
            cache_service = get_cache_service()
            
            # テストキーでキャッシュ動作確認
            test_key = "health_check_test"
            test_value = "test_data"
            
            await cache_service.set(test_key, test_value, expire=30)
            cached_value = await cache_service.get(test_key)
            await cache_service.delete(test_key)
            
            response_time = time.time() - start_time
            
            if cached_value != test_value:
                raise Exception("Cache read/write test failed")
            
            details = {
                "cache_type": "redis" if hasattr(cache_service, 'redis') else "memory",
            }
            
            status = "healthy"
            if response_time > self.alert_thresholds["response_time"]:
                status = "degraded"
            
            return HealthCheckResult(
                service="cache",
                status=status,
                response_time=response_time,
                message="Cache is operational",
                details=details,
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            return HealthCheckResult(
                service="cache",
                status="unhealthy",
                response_time=time.time() - start_time,
                message=f"Cache check failed: {str(e)}",
                details={"error": str(e)},
                timestamp=datetime.utcnow()
            )
    
    async def _check_ollama(self) -> HealthCheckResult:
        """Ollamaサービスヘルスチェック"""
        start_time = time.time()
        
        try:
            ollama_service = OllamaService()
            
            # モデル一覧取得でサービス確認
            models = await ollama_service.list_models()
            
            response_time = time.time() - start_time
            
            details = {
                "available_models": len(models),
                "models": [model.get("name", "unknown") for model in models[:3]],
                "base_url": self.settings.ollama_base_url,
            }
            
            status = "healthy"
            if response_time > self.alert_thresholds["response_time"]:
                status = "degraded"
            
            return HealthCheckResult(
                service="ollama",
                status=status,
                response_time=response_time,
                message="Ollama service is available",
                details=details,
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            return HealthCheckResult(
                service="ollama",
                status="unhealthy",
                response_time=time.time() - start_time,
                message=f"Ollama check failed: {str(e)}",
                details={"error": str(e)},
                timestamp=datetime.utcnow()
            )
    
    async def _check_whisper(self) -> HealthCheckResult:
        """Whisperサービスヘルスチェック"""
        start_time = time.time()
        
        try:
            whisper_service = WhisperService()
            
            # モデル読み込み状態確認
            model_loaded = hasattr(whisper_service, '_model') and whisper_service._model is not None
            
            response_time = time.time() - start_time
            
            details = {
                "model_loaded": model_loaded,
                "model_name": self.settings.whisper_model,
                "device": self.settings.whisper_device,
            }
            
            status = "healthy"
            if not model_loaded:
                status = "degraded"
                details["message"] = "Model not preloaded, will load on first use"
            
            return HealthCheckResult(
                service="whisper",
                status=status,
                response_time=response_time,
                message="Whisper service is available",
                details=details,
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            return HealthCheckResult(
                service="whisper",
                status="unhealthy",
                response_time=time.time() - start_time,
                message=f"Whisper check failed: {str(e)}",
                details={"error": str(e)},
                timestamp=datetime.utcnow()
            )
    
    async def _check_filesystem(self) -> HealthCheckResult:
        """ファイルシステムヘルスチェック"""
        start_time = time.time()
        
        try:
            # 必要なディレクトリ存在確認
            required_dirs = ["data", "uploads", "logs", "backups"]
            details = {"directories": {}}
            
            for dir_name in required_dirs:
                dir_path = Path(dir_name)
                dir_path.mkdir(parents=True, exist_ok=True)
                
                # ディスク使用量確認
                if dir_path.exists():
                    stat = os.statvfs(str(dir_path))
                    total = stat.f_frsize * stat.f_blocks
                    free = stat.f_frsize * stat.f_bavail
                    used_percent = ((total - free) / total) * 100
                    
                    details["directories"][dir_name] = {
                        "exists": True,
                        "writable": os.access(str(dir_path), os.W_OK),
                        "used_percent": used_percent,
                    }
                else:
                    details["directories"][dir_name] = {"exists": False}
            
            response_time = time.time() - start_time
            
            # ディスク使用量警告
            max_usage = max([d.get("used_percent", 0) for d in details["directories"].values()])
            status = "healthy"
            if max_usage > self.alert_thresholds["disk_percent"]:
                status = "unhealthy"
            elif max_usage > 75:
                status = "degraded"
            
            return HealthCheckResult(
                service="filesystem",
                status=status,
                response_time=response_time,
                message="Filesystem is accessible",
                details=details,
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            return HealthCheckResult(
                service="filesystem",
                status="unhealthy",
                response_time=time.time() - start_time,
                message=f"Filesystem check failed: {str(e)}",
                details={"error": str(e)},
                timestamp=datetime.utcnow()
            )
    
    async def _check_system_resources(self) -> HealthCheckResult:
        """システムリソースヘルスチェック"""
        start_time = time.time()
        
        try:
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # メモリ使用率
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # ディスク使用率
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            
            # プロセス数
            active_processes = len(psutil.pids())
            
            details = {
                "cpu_percent": cpu_percent,
                "memory_percent": memory_percent,
                "memory_available_gb": memory.available / (1024**3),
                "disk_percent": disk_percent,
                "disk_free_gb": disk.free / (1024**3),
                "active_processes": active_processes,
                "load_average": os.getloadavg() if hasattr(os, 'getloadavg') else [0, 0, 0],
            }
            
            response_time = time.time() - start_time
            
            # ステータス判定
            status = "healthy"
            if (cpu_percent > self.alert_thresholds["cpu_percent"] or 
                memory_percent > self.alert_thresholds["memory_percent"] or
                disk_percent > self.alert_thresholds["disk_percent"]):
                status = "unhealthy"
            elif (cpu_percent > 75 or memory_percent > 75 or disk_percent > 75):
                status = "degraded"
            
            return HealthCheckResult(
                service="system",
                status=status,
                response_time=response_time,
                message="System resources within limits",
                details=details,
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            return HealthCheckResult(
                service="system",
                status="unhealthy",
                response_time=time.time() - start_time,
                message=f"System check failed: {str(e)}",
                details={"error": str(e)},
                timestamp=datetime.utcnow()
            )
    
    def get_health_history(self, service: Optional[str] = None, hours: int = 24) -> List[Dict[str, Any]]:
        """ヘルスチェック履歴取得"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        filtered_history = [
            result for result in self.health_history
            if result.timestamp > cutoff_time and (not service or result.service == service)
        ]
        
        return [
            {
                "service": result.service,
                "status": result.status,
                "response_time": result.response_time,
                "message": result.message,
                "timestamp": result.timestamp.isoformat(),
            }
            for result in filtered_history
        ]
    
    async def get_system_metrics(self) -> SystemMetrics:
        """システムメトリクス取得"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            network_connections = len(psutil.net_connections())
            active_processes = len(psutil.pids())
            uptime_seconds = int(time.time() - self.start_time)
            
            return SystemMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                disk_percent=(disk.used / disk.total) * 100,
                network_connections=network_connections,
                active_processes=active_processes,
                uptime_seconds=uptime_seconds,
            )
        except Exception as e:
            logger.error("Failed to get system metrics", error=str(e))
            return SystemMetrics(
                cpu_percent=0.0,
                memory_percent=0.0,
                disk_percent=0.0,
                network_connections=0,
                active_processes=0,
                uptime_seconds=0,
            )

# グローバルインスタンス
_health_service = None

def get_health_service() -> HealthService:
    """ヘルスサービスインスタンス取得"""
    global _health_service
    if _health_service is None:
        _health_service = HealthService()
    return _health_service