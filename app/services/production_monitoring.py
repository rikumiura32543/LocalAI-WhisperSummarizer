"""
本番環境専用監視システム
Google Cloud E2環境での最適化された監視機能
"""

import asyncio
import json
import time
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path
import structlog
from dataclasses import dataclass, asdict

from ..core.config import get_settings
from .health_service import get_health_service
from .monitoring_service import get_monitoring_service
# from .alert_service import get_alert_service

logger = structlog.get_logger(__name__)

@dataclass
class ProductionMetrics:
    """本番環境メトリクス"""
    timestamp: datetime
    requests_per_minute: int
    active_transcriptions: int
    queue_length: int
    avg_processing_time: float
    error_rate: float
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    response_time_p95: float

@dataclass
class PerformanceBaseline:
    """パフォーマンスベースライン"""
    avg_response_time: float
    avg_cpu_usage: float
    avg_memory_usage: float
    avg_processing_time: float
    error_rate: float
    requests_per_minute: int

class ProductionMonitoringService:
    """本番環境監視サービス"""
    
    def __init__(self):
        self.settings = get_settings()
        self.health_service = get_health_service()
        self.monitoring_service = get_monitoring_service()
        # self.alert_service = get_alert_service()
        
        # 本番環境固有の監視設定
        self.monitoring_interval = 30  # 30秒間隔
        self.metrics_retention_days = 30
        self.alert_thresholds = {
            "cpu_usage": 80.0,      # Google Cloud E2制約
            "memory_usage": 75.0,   # 8GB RAMの制約  
            "disk_usage": 85.0,
            "error_rate": 5.0,
            "response_time_p95": 10.0,
            "queue_length": 10,
        }
        
        # メトリクス履歴
        self.metrics_history: List[ProductionMetrics] = []
        self.max_metrics_history = 2880  # 24時間分（30秒間隔）
        
        # パフォーマンスベースライン
        self.baseline: Optional[PerformanceBaseline] = None
        self.baseline_samples = []
        self.baseline_sample_size = 288  # 2.4時間分
        
        # 監視タスク
        self._monitoring_task = None
        self._running = False
        
    async def start_production_monitoring(self):
        """本番監視開始"""
        if self._running:
            logger.warning("Production monitoring already running")
            return
        
        self._running = True
        
        # 並行してタスクを開始
        tasks = [
            self._metrics_collection_loop(),
            self._performance_analysis_loop(),
            self._health_monitoring_loop(),
            self._log_analysis_loop(),
        ]
        
        self._monitoring_task = asyncio.gather(*tasks, return_exceptions=True)
        logger.info("Production monitoring started")
        
        # アラート送信
        await self.alert_service.send_alert(
            "monitoring_started",
            "Production monitoring system started",
            severity="info",
            details={"timestamp": datetime.utcnow().isoformat()}
        )
    
    async def stop_production_monitoring(self):
        """本番監視停止"""
        self._running = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("Production monitoring stopped")
    
    async def _metrics_collection_loop(self):
        """メトリクス収集ループ"""
        while self._running:
            try:
                # システムメトリクス取得
                system_metrics = await self.health_service.get_system_metrics()
                
                # アプリケーションメトリクス取得
                app_metrics = await self.monitoring_service.get_current_metrics()
                
                # 本番環境メトリクス構築
                production_metrics = ProductionMetrics(
                    timestamp=datetime.utcnow(),
                    requests_per_minute=app_metrics.get("requests_per_minute", 0),
                    active_transcriptions=app_metrics.get("active_transcriptions", 0),
                    queue_length=app_metrics.get("queue_length", 0),
                    avg_processing_time=app_metrics.get("avg_processing_time", 0.0),
                    error_rate=app_metrics.get("error_rate", 0.0),
                    cpu_usage=system_metrics.cpu_percent,
                    memory_usage=system_metrics.memory_percent,
                    disk_usage=system_metrics.disk_percent,
                    response_time_p95=app_metrics.get("response_time_p95", 0.0),
                )
                
                # メトリクス履歴に追加
                self.metrics_history.append(production_metrics)
                if len(self.metrics_history) > self.max_metrics_history:
                    self.metrics_history = self.metrics_history[-self.max_metrics_history:]
                
                # ベースライン計算用サンプル追加
                if len(self.baseline_samples) < self.baseline_sample_size:
                    self.baseline_samples.append(production_metrics)
                else:
                    # ベースライン更新（FIFO）
                    self.baseline_samples.pop(0)
                    self.baseline_samples.append(production_metrics)
                
                # 閾値チェック
                await self._check_thresholds(production_metrics)
                
                await asyncio.sleep(self.monitoring_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in metrics collection", error=str(e))
                await asyncio.sleep(60)
    
    async def _performance_analysis_loop(self):
        """パフォーマンス分析ループ"""
        while self._running:
            try:
                # 5分間隔で分析実行
                await asyncio.sleep(300)
                
                if len(self.metrics_history) < 10:
                    continue
                
                # ベースライン更新
                await self._update_baseline()
                
                # 異常検知
                await self._detect_anomalies()
                
                # トレンド分析
                await self._analyze_trends()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in performance analysis", error=str(e))
                await asyncio.sleep(300)
    
    async def _health_monitoring_loop(self):
        """ヘルス監視ループ"""
        consecutive_failures = 0
        max_failures = 3
        
        while self._running:
            try:
                # 詳細ヘルスチェック実行
                health_status = await self.health_service.check_health(detailed=True)
                overall_status = health_status.get("system", {}).get("status", "unknown")
                
                if overall_status == "unhealthy":
                    consecutive_failures += 1
                    if consecutive_failures >= max_failures:
                        await self.alert_service.send_alert(
                            "system_critical",
                            f"System unhealthy for {consecutive_failures} consecutive checks",
                            severity="critical",
                            details=health_status
                        )
                else:
                    consecutive_failures = 0
                
                # サービス別詳細チェック
                services = health_status.get("services", {})
                for service_name, service_info in services.items():
                    if service_info.get("status") == "unhealthy":
                        await self.alert_service.send_alert(
                            f"service_unhealthy_{service_name}",
                            f"Service {service_name} is unhealthy",
                            severity="warning",
                            details=service_info
                        )
                
                await asyncio.sleep(60)  # 1分間隔
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in health monitoring", error=str(e))
                await asyncio.sleep(60)
    
    async def _log_analysis_loop(self):
        """ログ分析ループ"""
        while self._running:
            try:
                # 10分間隔でログ分析
                await asyncio.sleep(600)
                
                # エラーログ分析
                await self._analyze_error_logs()
                
                # パフォーマンスログ分析
                await self._analyze_performance_logs()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in log analysis", error=str(e))
                await asyncio.sleep(600)
    
    async def _check_thresholds(self, metrics: ProductionMetrics):
        """閾値チェック"""
        alerts = []
        
        # CPU使用率チェック
        if metrics.cpu_usage > self.alert_thresholds["cpu_usage"]:
            alerts.append({
                "type": "cpu_high",
                "message": f"CPU usage high: {metrics.cpu_usage:.1f}%",
                "severity": "warning" if metrics.cpu_usage < 90 else "critical",
                "value": metrics.cpu_usage,
                "threshold": self.alert_thresholds["cpu_usage"],
            })
        
        # メモリ使用率チェック
        if metrics.memory_usage > self.alert_thresholds["memory_usage"]:
            alerts.append({
                "type": "memory_high",
                "message": f"Memory usage high: {metrics.memory_usage:.1f}%",
                "severity": "warning" if metrics.memory_usage < 85 else "critical",
                "value": metrics.memory_usage,
                "threshold": self.alert_thresholds["memory_usage"],
            })
        
        # ディスク使用率チェック
        if metrics.disk_usage > self.alert_thresholds["disk_usage"]:
            alerts.append({
                "type": "disk_high",
                "message": f"Disk usage high: {metrics.disk_usage:.1f}%",
                "severity": "warning" if metrics.disk_usage < 90 else "critical",
                "value": metrics.disk_usage,
                "threshold": self.alert_thresholds["disk_usage"],
            })
        
        # エラー率チェック
        if metrics.error_rate > self.alert_thresholds["error_rate"]:
            alerts.append({
                "type": "error_rate_high",
                "message": f"Error rate high: {metrics.error_rate:.1f}%",
                "severity": "warning" if metrics.error_rate < 10 else "critical",
                "value": metrics.error_rate,
                "threshold": self.alert_thresholds["error_rate"],
            })
        
        # レスポンス時間チェック
        if metrics.response_time_p95 > self.alert_thresholds["response_time_p95"]:
            alerts.append({
                "type": "response_time_high",
                "message": f"Response time P95 high: {metrics.response_time_p95:.2f}s",
                "severity": "warning" if metrics.response_time_p95 < 15 else "critical",
                "value": metrics.response_time_p95,
                "threshold": self.alert_thresholds["response_time_p95"],
            })
        
        # キュー長チェック
        if metrics.queue_length > self.alert_thresholds["queue_length"]:
            alerts.append({
                "type": "queue_length_high",
                "message": f"Processing queue length high: {metrics.queue_length}",
                "severity": "warning" if metrics.queue_length < 20 else "critical",
                "value": metrics.queue_length,
                "threshold": self.alert_thresholds["queue_length"],
            })
        
        # アラート送信
        for alert in alerts:
            await self.alert_service.send_alert(
                alert["type"],
                alert["message"],
                severity=alert["severity"],
                details={
                    "value": alert["value"],
                    "threshold": alert["threshold"],
                    "timestamp": metrics.timestamp.isoformat(),
                }
            )
    
    async def _update_baseline(self):
        """パフォーマンスベースライン更新"""
        if len(self.baseline_samples) < 100:  # 最低サンプル数
            return
        
        try:
            # 統計計算
            avg_response_time = sum(m.response_time_p95 for m in self.baseline_samples) / len(self.baseline_samples)
            avg_cpu_usage = sum(m.cpu_usage for m in self.baseline_samples) / len(self.baseline_samples)
            avg_memory_usage = sum(m.memory_usage for m in self.baseline_samples) / len(self.baseline_samples)
            avg_processing_time = sum(m.avg_processing_time for m in self.baseline_samples) / len(self.baseline_samples)
            avg_error_rate = sum(m.error_rate for m in self.baseline_samples) / len(self.baseline_samples)
            avg_requests_per_minute = sum(m.requests_per_minute for m in self.baseline_samples) / len(self.baseline_samples)
            
            # ベースライン更新
            self.baseline = PerformanceBaseline(
                avg_response_time=avg_response_time,
                avg_cpu_usage=avg_cpu_usage,
                avg_memory_usage=avg_memory_usage,
                avg_processing_time=avg_processing_time,
                error_rate=avg_error_rate,
                requests_per_minute=int(avg_requests_per_minute),
            )
            
            logger.debug("Performance baseline updated", baseline=asdict(self.baseline))
            
        except Exception as e:
            logger.error("Failed to update baseline", error=str(e))
    
    async def _detect_anomalies(self):
        """異常検知"""
        if not self.baseline or len(self.metrics_history) < 10:
            return
        
        try:
            # 直近10分のメトリクス取得
            recent_metrics = self.metrics_history[-20:]  # 10分分（30秒間隔）
            
            for metric in recent_metrics:
                anomalies = []
                
                # CPU使用率異常
                if metric.cpu_usage > self.baseline.avg_cpu_usage * 1.5:
                    anomalies.append({
                        "type": "cpu_anomaly",
                        "current": metric.cpu_usage,
                        "baseline": self.baseline.avg_cpu_usage,
                    })
                
                # メモリ使用率異常
                if metric.memory_usage > self.baseline.avg_memory_usage * 1.3:
                    anomalies.append({
                        "type": "memory_anomaly",
                        "current": metric.memory_usage,
                        "baseline": self.baseline.avg_memory_usage,
                    })
                
                # レスポンス時間異常
                if metric.response_time_p95 > self.baseline.avg_response_time * 2.0:
                    anomalies.append({
                        "type": "response_time_anomaly",
                        "current": metric.response_time_p95,
                        "baseline": self.baseline.avg_response_time,
                    })
                
                # 異常があればアラート送信
                for anomaly in anomalies:
                    await self.alert_service.send_alert(
                        anomaly["type"],
                        f"Performance anomaly detected: {anomaly['type']}",
                        severity="warning",
                        details=anomaly
                    )
                    
        except Exception as e:
            logger.error("Anomaly detection failed", error=str(e))
    
    async def _analyze_trends(self):
        """トレンド分析"""
        if len(self.metrics_history) < 60:  # 30分分
            return
        
        try:
            # 直近30分のメトリクス
            recent_metrics = self.metrics_history[-60:]
            
            # CPU使用率トレンド
            cpu_values = [m.cpu_usage for m in recent_metrics]
            cpu_trend = self._calculate_trend(cpu_values)
            
            # メモリ使用率トレンド
            memory_values = [m.memory_usage for m in recent_metrics]
            memory_trend = self._calculate_trend(memory_values)
            
            # 上昇トレンドの警告
            if cpu_trend > 0.5:  # 30分で0.5%以上の上昇
                await self.alert_service.send_alert(
                    "cpu_trend_increasing",
                    f"CPU usage trend increasing: {cpu_trend:.2f}% per 30min",
                    severity="info",
                    details={"trend": cpu_trend, "current": cpu_values[-1]}
                )
            
            if memory_trend > 0.5:
                await self.alert_service.send_alert(
                    "memory_trend_increasing",
                    f"Memory usage trend increasing: {memory_trend:.2f}% per 30min",
                    severity="info",
                    details={"trend": memory_trend, "current": memory_values[-1]}
                )
                
        except Exception as e:
            logger.error("Trend analysis failed", error=str(e))
    
    def _calculate_trend(self, values: List[float]) -> float:
        """線形トレンド計算"""
        if len(values) < 2:
            return 0.0
        
        n = len(values)
        x_mean = (n - 1) / 2
        y_mean = sum(values) / n
        
        numerator = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        
        return numerator / denominator if denominator != 0 else 0.0
    
    async def _analyze_error_logs(self):
        """エラーログ分析"""
        try:
            # ログファイルからエラーパターン抽出
            error_patterns = await self._extract_error_patterns()
            
            # 頻出エラーの検出
            for pattern, count in error_patterns.items():
                if count > 10:  # 10分間で10回以上
                    await self.alert_service.send_alert(
                        "frequent_error_pattern",
                        f"Frequent error pattern detected: {pattern}",
                        severity="warning",
                        details={"pattern": pattern, "count": count}
                    )
                    
        except Exception as e:
            logger.error("Error log analysis failed", error=str(e))
    
    async def _extract_error_patterns(self) -> Dict[str, int]:
        """エラーパターン抽出"""
        # 実装省略：ログファイルからエラーパターンを抽出
        return {}
    
    async def _analyze_performance_logs(self):
        """パフォーマンスログ分析"""
        try:
            # パフォーマンスメトリクスの抽出と分析
            pass
        except Exception as e:
            logger.error("Performance log analysis failed", error=str(e))
    
    def get_production_dashboard_data(self) -> Dict[str, Any]:
        """本番環境ダッシュボード用データ取得"""
        if not self.metrics_history:
            return {"status": "no_data"}
        
        latest_metrics = self.metrics_history[-1]
        
        # 直近1時間の統計
        hour_metrics = self.metrics_history[-120:] if len(self.metrics_history) >= 120 else self.metrics_history
        
        return {
            "status": "operational",
            "timestamp": latest_metrics.timestamp.isoformat(),
            "current": asdict(latest_metrics),
            "baseline": asdict(self.baseline) if self.baseline else None,
            "stats_1h": {
                "avg_cpu": sum(m.cpu_usage for m in hour_metrics) / len(hour_metrics),
                "avg_memory": sum(m.memory_usage for m in hour_metrics) / len(hour_metrics),
                "avg_response_time": sum(m.response_time_p95 for m in hour_metrics) / len(hour_metrics),
                "total_requests": sum(m.requests_per_minute for m in hour_metrics),
                "avg_error_rate": sum(m.error_rate for m in hour_metrics) / len(hour_metrics),
            },
            "thresholds": self.alert_thresholds,
        }

# グローバルインスタンス
_production_monitoring = None

def get_production_monitoring() -> ProductionMonitoringService:
    """本番監視サービスインスタンス取得"""
    global _production_monitoring
    if _production_monitoring is None:
        _production_monitoring = ProductionMonitoringService()
    return _production_monitoring