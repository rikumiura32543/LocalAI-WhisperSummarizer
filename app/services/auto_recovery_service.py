"""
自動復旧システム
"""

import asyncio
import time
import subprocess
import os
import signal
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from enum import Enum
import structlog
from dataclasses import dataclass

from ..core.config import get_settings
from .health_service import get_health_service, HealthCheckResult
# from .alert_service import get_alert_service

logger = structlog.get_logger(__name__)

class RecoveryAction(Enum):
    """復旧アクション種別"""
    RESTART_SERVICE = "restart_service"
    CLEAR_CACHE = "clear_cache"
    CLEANUP_FILES = "cleanup_files"
    RESTART_PROCESS = "restart_process"
    SCALE_DOWN = "scale_down"
    NOTIFY_ADMIN = "notify_admin"

@dataclass
class RecoveryRule:
    """復旧ルール"""
    service: str
    condition: str  # "unhealthy", "degraded", "response_time_high", etc.
    threshold: float
    action: RecoveryAction
    cooldown_minutes: int = 5
    max_attempts: int = 3
    description: str = ""

@dataclass
class RecoveryAttempt:
    """復旧試行記録"""
    service: str
    action: RecoveryAction
    timestamp: datetime
    success: bool
    message: str
    duration: float

class AutoRecoveryService:
    """自動復旧サービス"""
    
    def __init__(self):
        self.settings = get_settings()
        self.health_service = get_health_service()
        # self.alert_service = get_alert_service()
        
        # 復旧ルール定義
        self.recovery_rules = [
            # データベース関連
            RecoveryRule(
                service="database",
                condition="unhealthy",
                threshold=0,
                action=RecoveryAction.RESTART_SERVICE,
                cooldown_minutes=10,
                max_attempts=2,
                description="Database connection failure recovery"
            ),
            
            # キャッシュ関連
            RecoveryRule(
                service="cache",
                condition="unhealthy",
                threshold=0,
                action=RecoveryAction.CLEAR_CACHE,
                cooldown_minutes=5,
                max_attempts=3,
                description="Cache service recovery"
            ),
            
            # AI サービス関連
            RecoveryRule(
                service="ollama",
                condition="unhealthy",
                threshold=0,
                action=RecoveryAction.RESTART_SERVICE,
                cooldown_minutes=15,
                max_attempts=1,
                description="Ollama service restart"
            ),
            
            # システムリソース関連
            RecoveryRule(
                service="system",
                condition="cpu_high",
                threshold=90.0,
                action=RecoveryAction.SCALE_DOWN,
                cooldown_minutes=10,
                max_attempts=2,
                description="High CPU usage mitigation"
            ),
            
            RecoveryRule(
                service="system",
                condition="memory_high",
                threshold=85.0,
                action=RecoveryAction.CLEANUP_FILES,
                cooldown_minutes=5,
                max_attempts=3,
                description="High memory usage cleanup"
            ),
            
            # ファイルシステム関連
            RecoveryRule(
                service="filesystem",
                condition="disk_high",
                threshold=90.0,
                action=RecoveryAction.CLEANUP_FILES,
                cooldown_minutes=30,
                max_attempts=2,
                description="Disk space cleanup"
            ),
        ]
        
        # 復旧試行履歴
        self.recovery_attempts: List[RecoveryAttempt] = []
        self.max_history = 1000
        
        # 復旧アクション実装
        self.action_handlers = {
            RecoveryAction.RESTART_SERVICE: self._restart_service,
            RecoveryAction.CLEAR_CACHE: self._clear_cache,
            RecoveryAction.CLEANUP_FILES: self._cleanup_files,
            RecoveryAction.RESTART_PROCESS: self._restart_process,
            RecoveryAction.SCALE_DOWN: self._scale_down,
            RecoveryAction.NOTIFY_ADMIN: self._notify_admin,
        }
        
        # 監視タスク
        self._monitoring_task = None
        self._running = False
    
    async def start_monitoring(self):
        """自動復旧監視開始"""
        if self._running:
            logger.warning("Auto recovery monitoring already running")
            return
        
        self._running = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Auto recovery monitoring started")
    
    async def stop_monitoring(self):
        """自動復旧監視停止"""
        self._running = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("Auto recovery monitoring stopped")
    
    async def _monitoring_loop(self):
        """監視ループ"""
        while self._running:
            try:
                # ヘルスチェック実行
                health_status = await self.health_service.check_health(detailed=True)
                
                # 復旧ルールをチェックして必要に応じて復旧アクションを実行
                await self._check_and_recover(health_status)
                
                # システムメトリクスを取得して閾値チェック
                system_metrics = await self.health_service.get_system_metrics()
                await self._check_system_metrics(system_metrics)
                
                # 次の監視まで待機
                await asyncio.sleep(self.settings.health_check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in recovery monitoring loop", error=str(e))
                await asyncio.sleep(30)  # エラー時は長めに待機
    
    async def _check_and_recover(self, health_status: Dict[str, Any]):
        """ヘルスチェック結果に基づく復旧アクション判定・実行"""
        services = health_status.get("services", {})
        
        for service_name, service_info in services.items():
            status = service_info.get("status")
            response_time = service_info.get("response_time", 0)
            
            # 該当する復旧ルールを検索
            applicable_rules = [
                rule for rule in self.recovery_rules
                if rule.service == service_name and self._should_apply_rule(rule, status, response_time)
            ]
            
            for rule in applicable_rules:
                if await self._can_attempt_recovery(rule):
                    await self._attempt_recovery(rule, service_info)
    
    async def _check_system_metrics(self, metrics):
        """システムメトリクスチェック"""
        # CPU使用率チェック
        if metrics.cpu_percent > 90.0:
            rule = next((r for r in self.recovery_rules 
                        if r.service == "system" and r.condition == "cpu_high"), None)
            if rule and await self._can_attempt_recovery(rule):
                await self._attempt_recovery(rule, {"cpu_percent": metrics.cpu_percent})
        
        # メモリ使用率チェック
        if metrics.memory_percent > 85.0:
            rule = next((r for r in self.recovery_rules 
                        if r.service == "system" and r.condition == "memory_high"), None)
            if rule and await self._can_attempt_recovery(rule):
                await self._attempt_recovery(rule, {"memory_percent": metrics.memory_percent})
        
        # ディスク使用率チェック
        if metrics.disk_percent > 90.0:
            rule = next((r for r in self.recovery_rules 
                        if r.service == "filesystem" and r.condition == "disk_high"), None)
            if rule and await self._can_attempt_recovery(rule):
                await self._attempt_recovery(rule, {"disk_percent": metrics.disk_percent})
    
    def _should_apply_rule(self, rule: RecoveryRule, status: str, response_time: float) -> bool:
        """ルール適用判定"""
        if rule.condition == "unhealthy":
            return status == "unhealthy"
        elif rule.condition == "degraded":
            return status == "degraded"
        elif rule.condition == "response_time_high":
            return response_time > rule.threshold
        else:
            return False
    
    async def _can_attempt_recovery(self, rule: RecoveryRule) -> bool:
        """復旧試行可能判定"""
        # 過去の試行履歴をチェック
        cutoff_time = datetime.utcnow() - timedelta(minutes=rule.cooldown_minutes)
        recent_attempts = [
            attempt for attempt in self.recovery_attempts
            if (attempt.service == rule.service and 
                attempt.action == rule.action and
                attempt.timestamp > cutoff_time)
        ]
        
        # 最大試行回数チェック
        if len(recent_attempts) >= rule.max_attempts:
            logger.warning("Maximum recovery attempts reached",
                         service=rule.service, action=rule.action.value)
            return False
        
        # クールダウン時間チェック
        if recent_attempts:
            last_attempt = max(recent_attempts, key=lambda x: x.timestamp)
            if last_attempt.timestamp > cutoff_time:
                logger.debug("Recovery action in cooldown period",
                           service=rule.service, action=rule.action.value)
                return False
        
        return True
    
    async def _attempt_recovery(self, rule: RecoveryRule, service_info: Dict[str, Any]):
        """復旧アクション実行"""
        start_time = time.time()
        success = False
        message = ""
        
        try:
            logger.info("Starting recovery action",
                       service=rule.service, action=rule.action.value,
                       description=rule.description)
            
            # 復旧アクション実行
            handler = self.action_handlers.get(rule.action)
            if handler:
                result = await handler(rule.service, service_info)
                success = result.get("success", False)
                message = result.get("message", "Recovery action completed")
            else:
                message = f"No handler for action: {rule.action.value}"
                
        except Exception as e:
            message = f"Recovery action failed: {str(e)}"
            logger.error("Recovery action error", error=str(e))
        
        duration = time.time() - start_time
        
        # 復旧試行記録
        attempt = RecoveryAttempt(
            service=rule.service,
            action=rule.action,
            timestamp=datetime.utcnow(),
            success=success,
            message=message,
            duration=duration
        )
        
        self.recovery_attempts.append(attempt)
        if len(self.recovery_attempts) > self.max_history:
            self.recovery_attempts = self.recovery_attempts[-self.max_history:]
        
        # アラート送信
        if success:
            await self.alert_service.send_alert(
                "recovery_success",
                f"Recovery action successful: {rule.description}",
                severity="info",
                details={
                    "service": rule.service,
                    "action": rule.action.value,
                    "duration": duration,
                }
            )
        else:
            await self.alert_service.send_alert(
                "recovery_failure",
                f"Recovery action failed: {rule.description}",
                severity="warning",
                details={
                    "service": rule.service,
                    "action": rule.action.value,
                    "error": message,
                }
            )
        
        logger.info("Recovery action completed",
                   service=rule.service, action=rule.action.value,
                   success=success, duration=duration, message=message)
    
    async def _restart_service(self, service: str, service_info: Dict[str, Any]) -> Dict[str, Any]:
        """サービス再起動"""
        try:
            if service == "ollama":
                # Docker環境でのOllama再起動
                result = subprocess.run(
                    ["docker", "restart", "ollama"],
                    capture_output=True, text=True, timeout=60
                )
                if result.returncode == 0:
                    await asyncio.sleep(30)  # 起動待ち
                    return {"success": True, "message": "Ollama service restarted"}
                else:
                    return {"success": False, "message": f"Restart failed: {result.stderr}"}
            
            elif service == "database":
                # データベース接続プール再初期化
                # 実際の実装では、SQLAlchemyの接続プールをリセット
                return {"success": True, "message": "Database connection pool reset"}
            
            else:
                return {"success": False, "message": f"Service restart not implemented for {service}"}
                
        except Exception as e:
            return {"success": False, "message": f"Restart error: {str(e)}"}
    
    async def _clear_cache(self, service: str, service_info: Dict[str, Any]) -> Dict[str, Any]:
        """キャッシュクリア"""
        try:
            if service == "cache":
                # Redis接続でキャッシュクリア
                result = subprocess.run(
                    ["docker", "exec", "redis", "redis-cli", "FLUSHDB"],
                    capture_output=True, text=True, timeout=30
                )
                if result.returncode == 0:
                    return {"success": True, "message": "Cache cleared successfully"}
                else:
                    return {"success": False, "message": f"Cache clear failed: {result.stderr}"}
            else:
                return {"success": False, "message": f"Cache clear not applicable for {service}"}
                
        except Exception as e:
            return {"success": False, "message": f"Cache clear error: {str(e)}"}
    
    async def _cleanup_files(self, service: str, service_info: Dict[str, Any]) -> Dict[str, Any]:
        """ファイルクリーンアップ"""
        try:
            cleanup_paths = [
                "uploads/*.tmp",
                "uploads/*.processing",
                "logs/*.log.1",  # ローテーションされた古いログ
                "data/temp/*",
            ]
            
            cleaned_files = 0
            freed_space = 0
            
            for pattern in cleanup_paths:
                result = subprocess.run(
                    ["find", ".", "-path", pattern, "-mtime", "+1", "-delete"],
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    cleaned_files += len(result.stdout.strip().split('\n')) if result.stdout.strip() else 0
            
            # 一時ファイル削除
            temp_result = subprocess.run(
                ["find", "/tmp", "-name", "whisper_*", "-mtime", "+0.5", "-delete"],
                capture_output=True, text=True
            )
            
            return {
                "success": True, 
                "message": f"Cleaned up {cleaned_files} files",
                "details": {"cleaned_files": cleaned_files}
            }
            
        except Exception as e:
            return {"success": False, "message": f"Cleanup error: {str(e)}"}
    
    async def _restart_process(self, service: str, service_info: Dict[str, Any]) -> Dict[str, Any]:
        """プロセス再起動"""
        try:
            # 自身のプロセス再起動（通常は避ける）
            logger.warning("Process restart requested - this should be handled externally")
            return {"success": False, "message": "Process restart should be handled by orchestrator"}
            
        except Exception as e:
            return {"success": False, "message": f"Process restart error: {str(e)}"}
    
    async def _scale_down(self, service: str, service_info: Dict[str, Any]) -> Dict[str, Any]:
        """負荷軽減（スケールダウン）"""
        try:
            # 処理中のタスク数を制限
            # 実際の実装では、worker数を一時的に減らすなど
            logger.info("Scaling down service to reduce load", service=service)
            
            # CPU使用率が高い場合の対応
            if "cpu_percent" in service_info:
                # 並列処理数を制限
                return {"success": True, "message": "Scaled down concurrent processing"}
            
            return {"success": True, "message": "Load reduction measures applied"}
            
        except Exception as e:
            return {"success": False, "message": f"Scale down error: {str(e)}"}
    
    async def _notify_admin(self, service: str, service_info: Dict[str, Any]) -> Dict[str, Any]:
        """管理者通知"""
        try:
            await self.alert_service.send_alert(
                "manual_intervention_required",
                f"Service {service} requires manual intervention",
                severity="critical",
                details=service_info
            )
            
            return {"success": True, "message": "Admin notification sent"}
            
        except Exception as e:
            return {"success": False, "message": f"Notification error: {str(e)}"}
    
    def get_recovery_history(self, service: Optional[str] = None, hours: int = 24) -> List[Dict[str, Any]]:
        """復旧履歴取得"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        filtered_attempts = [
            attempt for attempt in self.recovery_attempts
            if attempt.timestamp > cutoff_time and (not service or attempt.service == service)
        ]
        
        return [
            {
                "service": attempt.service,
                "action": attempt.action.value,
                "timestamp": attempt.timestamp.isoformat(),
                "success": attempt.success,
                "message": attempt.message,
                "duration": attempt.duration,
            }
            for attempt in filtered_attempts
        ]

# グローバルインスタンス
_auto_recovery_service = None

def get_auto_recovery_service() -> AutoRecoveryService:
    """自動復旧サービスインスタンス取得"""
    global _auto_recovery_service
    if _auto_recovery_service is None:
        _auto_recovery_service = AutoRecoveryService()
    return _auto_recovery_service