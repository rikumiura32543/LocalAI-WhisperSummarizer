"""
パフォーマンス分析サービス
"""

import time
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict, deque
from dataclasses import dataclass, asdict
import structlog
import asyncio
from contextlib import asynccontextmanager

from app.core.enhanced_logging import get_logger

logger = get_logger("performance_analyzer")


@dataclass
class PerformanceMetric:
    """パフォーマンスメトリクス"""
    name: str
    value: float
    unit: str
    timestamp: datetime
    tags: Dict[str, str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = {}


@dataclass
class RequestMetrics:
    """リクエストメトリクス"""
    endpoint: str
    method: str
    status_code: int
    duration_ms: float
    response_size: Optional[int]
    user_agent: Optional[str]
    client_ip: str
    timestamp: datetime
    error_message: Optional[str] = None


class PerformanceProfiler:
    """パフォーマンスプロファイラー"""
    
    def __init__(self):
        self.request_metrics: deque = deque(maxlen=10000)
        self.endpoint_stats = defaultdict(lambda: {
            "total_requests": 0,
            "total_duration": 0.0,
            "min_duration": float('inf'),
            "max_duration": 0.0,
            "error_count": 0,
            "status_codes": defaultdict(int),
            "recent_durations": deque(maxlen=100)
        })
        
    def record_request(self, metrics: RequestMetrics):
        """リクエストメトリクス記録"""
        self.request_metrics.append(metrics)
        
        # エンドポイント統計更新
        endpoint_key = f"{metrics.method} {metrics.endpoint}"
        stats = self.endpoint_stats[endpoint_key]
        
        stats["total_requests"] += 1
        stats["total_duration"] += metrics.duration_ms
        stats["min_duration"] = min(stats["min_duration"], metrics.duration_ms)
        stats["max_duration"] = max(stats["max_duration"], metrics.duration_ms)
        stats["status_codes"][metrics.status_code] += 1
        stats["recent_durations"].append(metrics.duration_ms)
        
        if metrics.status_code >= 400:
            stats["error_count"] += 1
        
        # パフォーマンス問題の検出
        if metrics.duration_ms > 5000:  # 5秒以上
            logger.warning(
                "Slow request detected",
                endpoint=endpoint_key,
                duration_ms=metrics.duration_ms,
                status_code=metrics.status_code
            )
    
    def get_endpoint_performance(self, hours: int = 1) -> Dict[str, Any]:
        """エンドポイントパフォーマンス分析"""
        since = datetime.now() - timedelta(hours=hours)
        recent_metrics = [
            m for m in self.request_metrics
            if m.timestamp >= since
        ]
        
        analysis = {}
        
        for endpoint, stats in self.endpoint_stats.items():
            if stats["total_requests"] == 0:
                continue
            
            recent_durations = list(stats["recent_durations"])
            if recent_durations:
                analysis[endpoint] = {
                    "total_requests": stats["total_requests"],
                    "avg_duration_ms": stats["total_duration"] / stats["total_requests"],
                    "min_duration_ms": stats["min_duration"],
                    "max_duration_ms": stats["max_duration"],
                    "median_duration_ms": statistics.median(recent_durations),
                    "p95_duration_ms": statistics.quantiles(recent_durations, n=20)[18] if len(recent_durations) >= 20 else max(recent_durations),
                    "error_rate": (stats["error_count"] / stats["total_requests"]) * 100,
                    "requests_per_hour": len([m for m in recent_metrics if endpoint in f"{m.method} {m.endpoint}"]),
                    "status_distribution": dict(stats["status_codes"])
                }
        
        return analysis
    
    def get_slowest_requests(self, limit: int = 10) -> List[Dict[str, Any]]:
        """最遅リクエスト取得"""
        sorted_requests = sorted(
            self.request_metrics,
            key=lambda x: x.duration_ms,
            reverse=True
        )
        
        return [
            {
                "endpoint": f"{req.method} {req.endpoint}",
                "duration_ms": req.duration_ms,
                "status_code": req.status_code,
                "timestamp": req.timestamp.isoformat(),
                "client_ip": req.client_ip,
                "error_message": req.error_message
            }
            for req in sorted_requests[:limit]
        ]
    
    def detect_performance_anomalies(self) -> List[Dict[str, Any]]:
        """パフォーマンス異常検出"""
        anomalies = []
        
        for endpoint, stats in self.endpoint_stats.items():
            recent_durations = list(stats["recent_durations"])
            
            if len(recent_durations) < 10:
                continue
            
            avg_duration = sum(recent_durations) / len(recent_durations)
            recent_avg = sum(recent_durations[-10:]) / 10
            
            # 最近のレスポンス時間が平均の3倍以上
            if recent_avg > avg_duration * 3:
                anomalies.append({
                    "type": "performance_degradation",
                    "endpoint": endpoint,
                    "avg_duration_ms": avg_duration,
                    "recent_avg_ms": recent_avg,
                    "severity": "high" if recent_avg > avg_duration * 5 else "medium"
                })
            
            # エラー率の急激な増加
            recent_requests = stats["total_requests"]
            recent_errors = stats["error_count"]
            error_rate = (recent_errors / recent_requests) * 100 if recent_requests > 0 else 0
            
            if error_rate > 10 and recent_requests > 10:
                anomalies.append({
                    "type": "high_error_rate",
                    "endpoint": endpoint,
                    "error_rate": error_rate,
                    "total_requests": recent_requests,
                    "total_errors": recent_errors,
                    "severity": "critical" if error_rate > 25 else "high"
                })
        
        return anomalies


@asynccontextmanager
async def performance_timer(operation: str, tags: Dict[str, str] = None):
    """パフォーマンス計測コンテキスト"""
    start_time = time.time()
    
    try:
        yield
    finally:
        duration_ms = (time.time() - start_time) * 1000
        
        logger.performance(
            f"Operation completed: {operation}",
            duration_ms=duration_ms,
            **(tags or {})
        )


class ResourceAnalyzer:
    """リソース使用量分析"""
    
    def __init__(self):
        self.cpu_history = deque(maxlen=1440)  # 24時間分（1分間隔）
        self.memory_history = deque(maxlen=1440)
        self.disk_history = deque(maxlen=1440)
    
    def record_system_metrics(self, cpu_percent: float, memory_percent: float, disk_percent: float):
        """システムメトリクス記録"""
        timestamp = datetime.now()
        
        self.cpu_history.append((timestamp, cpu_percent))
        self.memory_history.append((timestamp, memory_percent))
        self.disk_history.append((timestamp, disk_percent))
    
    def analyze_resource_trends(self) -> Dict[str, Any]:
        """リソース使用傾向分析"""
        analysis = {}
        
        for resource_name, history in [
            ("cpu", self.cpu_history),
            ("memory", self.memory_history),
            ("disk", self.disk_history)
        ]:
            if len(history) < 10:
                continue
            
            values = [value for _, value in history]
            recent_values = values[-60:]  # 最近1時間
            
            analysis[resource_name] = {
                "current": values[-1] if values else 0,
                "avg_1h": sum(recent_values) / len(recent_values) if recent_values else 0,
                "avg_24h": sum(values) / len(values),
                "max_24h": max(values),
                "min_24h": min(values),
                "trend": self._calculate_trend(values[-30:] if len(values) >= 30 else values),
                "peaks": self._find_peaks(values),
                "anomalies": self._detect_resource_anomalies(values)
            }
        
        return analysis
    
    def _calculate_trend(self, values: List[float]) -> str:
        """トレンド計算"""
        if len(values) < 5:
            return "insufficient_data"
        
        first_half = values[:len(values)//2]
        second_half = values[len(values)//2:]
        
        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)
        
        diff_percent = ((second_avg - first_avg) / first_avg) * 100 if first_avg > 0 else 0
        
        if diff_percent > 10:
            return "increasing"
        elif diff_percent < -10:
            return "decreasing"
        else:
            return "stable"
    
    def _find_peaks(self, values: List[float], threshold: float = 80.0) -> List[Tuple[int, float]]:
        """ピーク検出"""
        peaks = []
        for i, value in enumerate(values):
            if value > threshold:
                peaks.append((i, value))
        return peaks[-10:]  # 最新10個のピーク
    
    def _detect_resource_anomalies(self, values: List[float]) -> List[str]:
        """リソース異常検出"""
        anomalies = []
        
        if len(values) < 30:
            return anomalies
        
        avg = sum(values) / len(values)
        recent_avg = sum(values[-10:]) / 10
        
        # 急激な増加
        if recent_avg > avg * 2:
            anomalies.append("sudden_increase")
        
        # 持続的な高使用率
        high_usage_count = len([v for v in values[-30:] if v > 90])
        if high_usage_count > 20:  # 30分中20分以上
            anomalies.append("sustained_high_usage")
        
        # 使用率のばらつきが大きい
        if len(values) >= 60:
            std_dev = statistics.stdev(values[-60:])
            if std_dev > 20:
                anomalies.append("high_variability")
        
        return anomalies


# グローバルパフォーマンスプロファイラー
performance_profiler = PerformanceProfiler()
resource_analyzer = ResourceAnalyzer()