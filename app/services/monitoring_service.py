"""
モニタリングサービス
"""

import time
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict, deque
from dataclasses import dataclass, asdict
import structlog
import asyncio
from pathlib import Path

logger = structlog.get_logger(__name__)


@dataclass
class MetricData:
    """メトリクスデータ"""
    name: str
    value: float
    timestamp: float
    labels: Dict[str, str] = None
    
    def __post_init__(self):
        if self.labels is None:
            self.labels = {}


@dataclass
class SystemMetrics:
    """システムメトリクス"""
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    disk_usage_percent: float
    active_connections: int
    response_time_avg: float
    error_rate: float
    timestamp: float


class MetricsCollector:
    """メトリクス収集サービス"""
    
    def __init__(self, retention_hours: int = 24):
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=retention_hours * 60))  # 1分間隔
        self.retention_hours = retention_hours
        self.collection_interval = 60  # 秒
        self._running = False
        self._task = None
    
    def add_metric(self, metric: MetricData):
        """メトリクス追加"""
        key = f"{metric.name}_{':'.join(f'{k}={v}' for k, v in metric.labels.items())}"
        self.metrics[key].append(metric)
        
        logger.debug("Metric added", 
                    name=metric.name, 
                    value=metric.value, 
                    labels=metric.labels)
    
    def get_metrics(self, name: str, labels: Dict[str, str] = None, 
                   since: Optional[datetime] = None) -> List[MetricData]:
        """メトリクス取得"""
        key = f"{name}_{':'.join(f'{k}={v}' for k, v in (labels or {}).items())}"
        metrics = list(self.metrics.get(key, []))
        
        if since:
            since_timestamp = since.timestamp()
            metrics = [m for m in metrics if m.timestamp >= since_timestamp]
        
        return metrics
    
    def get_latest_metric(self, name: str, labels: Dict[str, str] = None) -> Optional[MetricData]:
        """最新メトリクス取得"""
        metrics = self.get_metrics(name, labels)
        return metrics[-1] if metrics else None
    
    def get_metric_summary(self, name: str, labels: Dict[str, str] = None,
                          since: Optional[datetime] = None) -> Dict[str, float]:
        """メトリクス統計情報"""
        metrics = self.get_metrics(name, labels, since)
        if not metrics:
            return {}
        
        values = [m.value for m in metrics]
        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "latest": values[-1] if values else 0
        }
    
    async def start_collection(self):
        """メトリクス収集開始"""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._collection_loop())
        logger.info("Metrics collection started", interval=self.collection_interval)
    
    async def stop_collection(self):
        """メトリクス収集停止"""
        self._running = False
        if self._task:
            await self._task
        logger.info("Metrics collection stopped")
    
    async def _collection_loop(self):
        """メトリクス収集ループ"""
        while self._running:
            try:
                await self._collect_system_metrics()
                await asyncio.sleep(self.collection_interval)
            except Exception as e:
                logger.error("Metrics collection failed", error=str(e))
                await asyncio.sleep(self.collection_interval)
    
    async def _collect_system_metrics(self):
        """システムメトリクス収集"""
        try:
            import psutil
            
            # CPU使用率
            cpu_percent = psutil.cpu_percent()
            self.add_metric(MetricData("system_cpu_percent", cpu_percent, time.time()))
            
            # メモリ使用率
            memory = psutil.virtual_memory()
            self.add_metric(MetricData("system_memory_percent", memory.percent, time.time()))
            self.add_metric(MetricData("system_memory_used_mb", memory.used / 1024 / 1024, time.time()))
            
            # ディスク使用率
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            self.add_metric(MetricData("system_disk_percent", disk_percent, time.time()))
            
            # プロセス情報
            process = psutil.Process()
            self.add_metric(MetricData("process_memory_percent", process.memory_percent(), time.time()))
            self.add_metric(MetricData("process_cpu_percent", process.cpu_percent(), time.time()))
            
            # ネットワーク接続数
            connections = len(psutil.net_connections())
            self.add_metric(MetricData("network_connections", connections, time.time()))
            
        except Exception as e:
            logger.error("Failed to collect system metrics", error=str(e))


class AlertManager:
    """アラート管理サービス"""
    
    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics_collector = metrics_collector
        self.alert_rules = []
        self.active_alerts = {}
    
    def add_rule(self, name: str, metric_name: str, condition: str, 
                threshold: float, duration_minutes: int = 5):
        """アラートルール追加"""
        rule = {
            "name": name,
            "metric_name": metric_name,
            "condition": condition,  # "gt", "lt", "eq"
            "threshold": threshold,
            "duration_minutes": duration_minutes
        }
        self.alert_rules.append(rule)
        logger.info("Alert rule added", **rule)
    
    async def check_alerts(self):
        """アラートチェック"""
        for rule in self.alert_rules:
            await self._check_rule(rule)
    
    async def _check_rule(self, rule: Dict[str, Any]):
        """個別ルールチェック"""
        try:
            since = datetime.now() - timedelta(minutes=rule["duration_minutes"])
            metrics = self.metrics_collector.get_metrics(rule["metric_name"], since=since)
            
            if not metrics:
                return
            
            # 指定時間内のすべてのメトリクスが条件を満たすかチェック
            values = [m.value for m in metrics]
            condition_met = False
            
            if rule["condition"] == "gt":
                condition_met = all(v > rule["threshold"] for v in values)
            elif rule["condition"] == "lt":
                condition_met = all(v < rule["threshold"] for v in values)
            elif rule["condition"] == "eq":
                condition_met = all(v == rule["threshold"] for v in values)
            
            alert_key = rule["name"]
            
            if condition_met and alert_key not in self.active_alerts:
                # 新しいアラート発火
                self.active_alerts[alert_key] = {
                    "rule": rule,
                    "started_at": datetime.now(),
                    "latest_value": values[-1] if values else 0
                }
                
                logger.error("Alert fired",
                           alert=rule["name"],
                           metric=rule["metric_name"],
                           threshold=rule["threshold"],
                           latest_value=values[-1] if values else 0)
                
            elif not condition_met and alert_key in self.active_alerts:
                # アラート解除
                alert_info = self.active_alerts.pop(alert_key)
                duration = datetime.now() - alert_info["started_at"]
                
                logger.info("Alert resolved",
                          alert=rule["name"],
                          duration_minutes=duration.total_seconds() / 60)
        
        except Exception as e:
            logger.error("Alert check failed", rule=rule["name"], error=str(e))


class PerformanceTracker:
    """パフォーマンス追跡サービス"""
    
    def __init__(self):
        self.request_times = deque(maxlen=1000)
        self.error_counts = defaultdict(int)
        self.endpoint_stats = defaultdict(lambda: {"count": 0, "total_time": 0.0, "errors": 0})
    
    def record_request(self, endpoint: str, duration: float, status_code: int):
        """リクエスト記録"""
        self.request_times.append(duration)
        
        stats = self.endpoint_stats[endpoint]
        stats["count"] += 1
        stats["total_time"] += duration
        
        if status_code >= 400:
            stats["errors"] += 1
            self.error_counts[status_code] += 1
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """パフォーマンス統計"""
        if not self.request_times:
            return {}
        
        request_times_list = list(self.request_times)
        
        return {
            "total_requests": len(request_times_list),
            "avg_response_time": sum(request_times_list) / len(request_times_list),
            "min_response_time": min(request_times_list),
            "max_response_time": max(request_times_list),
            "error_count": sum(self.error_counts.values()),
            "error_rate": sum(self.error_counts.values()) / len(request_times_list) * 100,
            "endpoint_stats": dict(self.endpoint_stats)
        }


class HealthChecker:
    """ヘルスチェックサービス"""
    
    def __init__(self):
        self.checks = {}
    
    def add_check(self, name: str, check_func, timeout: int = 5):
        """ヘルスチェック追加"""
        self.checks[name] = {
            "func": check_func,
            "timeout": timeout
        }
    
    async def run_all_checks(self) -> Dict[str, Any]:
        """全ヘルスチェック実行"""
        results = {}
        overall_healthy = True
        
        for name, check_info in self.checks.items():
            try:
                result = await asyncio.wait_for(
                    check_info["func"](),
                    timeout=check_info["timeout"]
                )
                
                results[name] = {
                    "status": "healthy" if result else "unhealthy",
                    "details": result if isinstance(result, dict) else {}
                }
                
                if not result:
                    overall_healthy = False
                    
            except asyncio.TimeoutError:
                results[name] = {
                    "status": "timeout",
                    "details": {"error": "Health check timeout"}
                }
                overall_healthy = False
                
            except Exception as e:
                results[name] = {
                    "status": "error", 
                    "details": {"error": str(e)}
                }
                overall_healthy = False
        
        return {
            "overall_status": "healthy" if overall_healthy else "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "checks": results
        }


class MonitoringService:
    """統合モニタリングサービス"""
    
    def __init__(self):
        self.metrics_collector = MetricsCollector()
        self.alert_manager = AlertManager(self.metrics_collector)
        self.performance_tracker = PerformanceTracker()
        self.health_checker = HealthChecker()
        
        self._setup_default_alerts()
        self._setup_default_health_checks()
    
    def _setup_default_alerts(self):
        """デフォルトアラート設定"""
        # CPU使用率アラート
        self.alert_manager.add_rule(
            "high_cpu_usage",
            "system_cpu_percent",
            "gt",
            80.0,
            duration_minutes=5
        )
        
        # メモリ使用率アラート
        self.alert_manager.add_rule(
            "high_memory_usage",
            "system_memory_percent",
            "gt",
            90.0,
            duration_minutes=3
        )
        
        # エラー率アラート
        self.alert_manager.add_rule(
            "high_error_rate",
            "error_rate",
            "gt",
            10.0,
            duration_minutes=5
        )
    
    def _setup_default_health_checks(self):
        """デフォルトヘルスチェック設定"""
        async def check_database():
            """データベース接続チェック"""
            try:
                from app.core.database import get_db
                db = next(get_db())
                # 簡単なクエリ実行
                db.execute("SELECT 1")
                return True
            except Exception:
                return False
        
        async def check_disk_space():
            """ディスク容量チェック"""
            try:
                import psutil
                disk = psutil.disk_usage('/')
                usage_percent = (disk.used / disk.total) * 100
                return usage_percent < 95  # 95%未満なら健康
            except Exception:
                return False
        
        self.health_checker.add_check("database", check_database)
        self.health_checker.add_check("disk_space", check_disk_space)
    
    async def start(self):
        """モニタリング開始"""
        await self.metrics_collector.start_collection()
        logger.info("Monitoring service started")
    
    async def stop(self):
        """モニタリング停止"""
        await self.metrics_collector.stop_collection()
        logger.info("Monitoring service stopped")
    
    def get_system_status(self) -> Dict[str, Any]:
        """システム状態取得"""
        performance_summary = self.performance_tracker.get_performance_summary()
        
        # 最新のシステムメトリクス
        cpu_metric = self.metrics_collector.get_latest_metric("system_cpu_percent")
        memory_metric = self.metrics_collector.get_latest_metric("system_memory_percent")
        
        return {
            "timestamp": datetime.now().isoformat(),
            "cpu_percent": cpu_metric.value if cpu_metric else 0,
            "memory_percent": memory_metric.value if memory_metric else 0,
            "active_alerts": len(self.alert_manager.active_alerts),
            "performance": performance_summary,
            "uptime": time.time() - (self.metrics_collector.metrics["system_cpu_percent"][0].timestamp 
                                   if self.metrics_collector.metrics.get("system_cpu_percent") else time.time())
        }


# グローバルモニタリングサービス
monitoring_service = MonitoringService()


def get_monitoring_service() -> MonitoringService:
    """モニタリングサービス取得（依存注入用）"""
    return monitoring_service