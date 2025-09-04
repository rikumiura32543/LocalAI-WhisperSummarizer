"""
高度アラートシステム
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from enum import Enum
from dataclasses import dataclass, asdict
import structlog

from app.core.enhanced_logging import get_logger
from app.services.monitoring_service import monitoring_service

logger = get_logger("alert_system")


class AlertSeverity(Enum):
    """アラート重要度"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertStatus(Enum):
    """アラート状態"""
    ACTIVE = "active"
    RESOLVED = "resolved"
    ACKNOWLEDGED = "acknowledged"
    SUPPRESSED = "suppressed"


@dataclass
class Alert:
    """アラート"""
    id: str
    name: str
    description: str
    severity: AlertSeverity
    status: AlertStatus
    created_at: datetime
    updated_at: datetime
    source: str
    tags: Dict[str, str]
    threshold: float
    current_value: float
    rule_id: str
    resolved_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    escalation_level: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "severity": self.severity.value,
            "status": self.status.value
        }


@dataclass 
class AlertRule:
    """アラートルール"""
    id: str
    name: str
    description: str
    metric_name: str
    condition: str  # "gt", "lt", "eq", "ne"
    threshold: float
    severity: AlertSeverity
    duration_minutes: int
    cooldown_minutes: int = 10
    enabled: bool = True
    tags: Dict[str, str] = None
    notification_channels: List[str] = None
    escalation_rules: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = {}
        if self.notification_channels is None:
            self.notification_channels = []
        if self.escalation_rules is None:
            self.escalation_rules = []


class NotificationChannel:
    """通知チャンネル基底クラス"""
    
    def __init__(self, channel_id: str, config: Dict[str, Any]):
        self.channel_id = channel_id
        self.config = config
        self.enabled = config.get("enabled", True)
    
    async def send_notification(self, alert: Alert, message: str) -> bool:
        """通知送信（サブクラスで実装）"""
        raise NotImplementedError


class LogNotificationChannel(NotificationChannel):
    """ログ通知チャンネル"""
    
    async def send_notification(self, alert: Alert, message: str) -> bool:
        try:
            if alert.severity in [AlertSeverity.ERROR, AlertSeverity.CRITICAL]:
                logger.error(message, alert_id=alert.id, **alert.tags)
            else:
                logger.warning(message, alert_id=alert.id, **alert.tags)
            return True
        except Exception as e:
            logger.error("Log notification failed", error=str(e), alert_id=alert.id)
            return False


class EmailNotificationChannel(NotificationChannel):
    """Email通知チャンネル（プレースホルダー実装）"""
    
    async def send_notification(self, alert: Alert, message: str) -> bool:
        try:
            # 実際のメール送信実装はここに
            recipients = self.config.get("recipients", [])
            
            logger.info(
                "Email notification sent",
                alert_id=alert.id,
                recipients=recipients,
                subject=f"[M4A転写システム] {alert.severity.value.upper()}: {alert.name}"
            )
            
            # プレースホルダー：常に成功とする
            return True
            
        except Exception as e:
            logger.error("Email notification failed", error=str(e), alert_id=alert.id)
            return False


class SlackNotificationChannel(NotificationChannel):
    """Slack通知チャンネル（プレースホルダー実装）"""
    
    async def send_notification(self, alert: Alert, message: str) -> bool:
        try:
            webhook_url = self.config.get("webhook_url")
            if not webhook_url:
                logger.error("Slack webhook URL not configured")
                return False
            
            # Slack通知の実装はここに
            logger.info(
                "Slack notification sent",
                alert_id=alert.id,
                channel=self.config.get("channel", "#alerts")
            )
            
            # プレースホルダー：常に成功とする
            return True
            
        except Exception as e:
            logger.error("Slack notification failed", error=str(e), alert_id=alert.id)
            return False


class AdvancedAlertManager:
    """高度アラート管理システム"""
    
    def __init__(self):
        self.rules: Dict[str, AlertRule] = {}
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self.notification_channels: Dict[str, NotificationChannel] = {}
        self.rule_states: Dict[str, Dict[str, Any]] = {}
        self._setup_default_channels()
        self._setup_default_rules()
        self._running = False
        self._task = None
    
    def _setup_default_channels(self):
        """デフォルト通知チャンネル設定"""
        # ログ通知チャンネル
        self.notification_channels["log"] = LogNotificationChannel(
            "log", {"enabled": True}
        )
        
        # Email通知チャンネル（設定があれば）
        # self.notification_channels["email"] = EmailNotificationChannel(
        #     "email", {
        #         "enabled": True,
        #         "recipients": ["admin@example.com"]
        #     }
        # )
    
    def _setup_default_rules(self):
        """デフォルトアラートルール設定"""
        # 高CPU使用率アラート
        self.add_rule(AlertRule(
            id="high_cpu_usage",
            name="高CPU使用率",
            description="CPU使用率が80%を5分間以上継続",
            metric_name="system_cpu_percent",
            condition="gt",
            threshold=80.0,
            severity=AlertSeverity.WARNING,
            duration_minutes=5,
            notification_channels=["log"],
            tags={"category": "system", "resource": "cpu"}
        ))
        
        # 高メモリ使用率アラート
        self.add_rule(AlertRule(
            id="high_memory_usage", 
            name="高メモリ使用率",
            description="メモリ使用率が90%を3分間以上継続",
            metric_name="system_memory_percent",
            condition="gt",
            threshold=90.0,
            severity=AlertSeverity.ERROR,
            duration_minutes=3,
            notification_channels=["log"],
            tags={"category": "system", "resource": "memory"}
        ))
        
        # 高エラー率アラート
        self.add_rule(AlertRule(
            id="high_error_rate",
            name="高エラー率",
            description="エラー率が10%を5分間以上継続",
            metric_name="error_rate",
            condition="gt", 
            threshold=10.0,
            severity=AlertSeverity.ERROR,
            duration_minutes=5,
            notification_channels=["log"],
            tags={"category": "application", "metric": "error_rate"}
        ))
        
        # ディスク容量アラート
        self.add_rule(AlertRule(
            id="low_disk_space",
            name="ディスク容量不足",
            description="ディスク使用率が95%を超過",
            metric_name="system_disk_percent",
            condition="gt",
            threshold=95.0,
            severity=AlertSeverity.CRITICAL,
            duration_minutes=1,
            notification_channels=["log"],
            tags={"category": "system", "resource": "disk"}
        ))
    
    def add_rule(self, rule: AlertRule):
        """アラートルール追加"""
        self.rules[rule.id] = rule
        self.rule_states[rule.id] = {
            "triggered_at": None,
            "last_check": None,
            "consecutive_violations": 0,
            "cooldown_until": None
        }
        logger.info("Alert rule added", rule_id=rule.id, rule_name=rule.name)
    
    def remove_rule(self, rule_id: str):
        """アラートルール削除"""
        if rule_id in self.rules:
            del self.rules[rule_id]
            del self.rule_states[rule_id]
            logger.info("Alert rule removed", rule_id=rule_id)
    
    def add_notification_channel(self, channel: NotificationChannel):
        """通知チャンネル追加"""
        self.notification_channels[channel.channel_id] = channel
        logger.info("Notification channel added", channel_id=channel.channel_id)
    
    async def start_monitoring(self):
        """アラート監視開始"""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._monitoring_loop())
        logger.info("Alert monitoring started")
    
    async def stop_monitoring(self):
        """アラート監視停止"""
        self._running = False
        if self._task:
            await self._task
        logger.info("Alert monitoring stopped")
    
    async def _monitoring_loop(self):
        """アラート監視ループ"""
        while self._running:
            try:
                await self._check_all_rules()
                await asyncio.sleep(60)  # 1分間隔でチェック
            except Exception as e:
                logger.error("Alert monitoring loop error", error=str(e))
                await asyncio.sleep(60)
    
    async def _check_all_rules(self):
        """全ルールチェック"""
        for rule_id, rule in self.rules.items():
            if not rule.enabled:
                continue
            
            try:
                await self._check_rule(rule)
            except Exception as e:
                logger.error("Rule check failed", rule_id=rule_id, error=str(e))
    
    async def _check_rule(self, rule: AlertRule):
        """個別ルールチェック"""
        now = datetime.now()
        state = self.rule_states[rule.id]
        
        # クールダウン中チェック
        if state["cooldown_until"] and now < state["cooldown_until"]:
            return
        
        # メトリクス取得
        since = now - timedelta(minutes=rule.duration_minutes)
        metrics = monitoring_service.metrics_collector.get_metrics(rule.metric_name, since=since)
        
        if not metrics:
            return
        
        # 条件評価
        current_value = metrics[-1].value if metrics else 0
        condition_met = self._evaluate_condition(current_value, rule.condition, rule.threshold)
        
        # 期間内の全メトリクスが条件を満たすかチェック
        all_violating = len(metrics) > 0 and all(
            self._evaluate_condition(m.value, rule.condition, rule.threshold) 
            for m in metrics
        )
        
        if condition_met and all_violating:
            # 違反継続中
            if not state["triggered_at"]:
                state["triggered_at"] = now
            
            state["consecutive_violations"] += 1
            
            # アラート発火
            if rule.id not in self.active_alerts:
                alert = await self._create_alert(rule, current_value)
                self.active_alerts[rule.id] = alert
                await self._send_notifications(alert, f"アラート発火: {rule.description}")
        
        else:
            # 条件解除
            if rule.id in self.active_alerts:
                alert = self.active_alerts[rule.id]
                await self._resolve_alert(alert)
            
            # 状態リセット
            state["triggered_at"] = None
            state["consecutive_violations"] = 0
        
        state["last_check"] = now
    
    def _evaluate_condition(self, value: float, condition: str, threshold: float) -> bool:
        """条件評価"""
        if condition == "gt":
            return value > threshold
        elif condition == "lt":
            return value < threshold
        elif condition == "eq":
            return value == threshold
        elif condition == "ne":
            return value != threshold
        return False
    
    async def _create_alert(self, rule: AlertRule, current_value: float) -> Alert:
        """アラート作成"""
        alert = Alert(
            id=f"{rule.id}_{int(datetime.now().timestamp())}",
            name=rule.name,
            description=rule.description,
            severity=rule.severity,
            status=AlertStatus.ACTIVE,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            source="alert_system",
            tags=rule.tags,
            threshold=rule.threshold,
            current_value=current_value,
            rule_id=rule.id
        )
        
        self.alert_history.append(alert)
        logger.error("Alert created", alert_id=alert.id, **alert.tags)
        return alert
    
    async def _resolve_alert(self, alert: Alert):
        """アラート解決"""
        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = datetime.now()
        alert.updated_at = datetime.now()
        
        if alert.rule_id in self.active_alerts:
            del self.active_alerts[alert.rule_id]
        
        # クールダウン設定
        rule = self.rules[alert.rule_id]
        self.rule_states[alert.rule_id]["cooldown_until"] = (
            datetime.now() + timedelta(minutes=rule.cooldown_minutes)
        )
        
        await self._send_notifications(alert, f"アラート解決: {alert.description}")
        logger.info("Alert resolved", alert_id=alert.id, **alert.tags)
    
    async def _send_notifications(self, alert: Alert, message: str):
        """通知送信"""
        rule = self.rules[alert.rule_id]
        
        for channel_id in rule.notification_channels:
            if channel_id in self.notification_channels:
                channel = self.notification_channels[channel_id]
                if channel.enabled:
                    try:
                        success = await channel.send_notification(alert, message)
                        if not success:
                            logger.error("Notification failed", 
                                       channel_id=channel_id, 
                                       alert_id=alert.id)
                    except Exception as e:
                        logger.error("Notification error", 
                                   channel_id=channel_id,
                                   alert_id=alert.id,
                                   error=str(e))
    
    def acknowledge_alert(self, alert_id: str, acknowledged_by: str = "system"):
        """アラート確認"""
        for rule_id, alert in self.active_alerts.items():
            if alert.id == alert_id:
                alert.status = AlertStatus.ACKNOWLEDGED
                alert.acknowledged_at = datetime.now()
                alert.acknowledged_by = acknowledged_by
                alert.updated_at = datetime.now()
                
                logger.info("Alert acknowledged", 
                          alert_id=alert_id, 
                          acknowledged_by=acknowledged_by)
                return True
        
        return False
    
    def get_alert_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """アラート履歴取得"""
        since = datetime.now() - timedelta(hours=hours)
        
        filtered_alerts = [
            alert for alert in self.alert_history
            if alert.created_at >= since
        ]
        
        return [alert.to_dict() for alert in filtered_alerts]
    
    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """アクティブアラート取得"""
        return [alert.to_dict() for alert in self.active_alerts.values()]
    
    def get_alert_statistics(self) -> Dict[str, Any]:
        """アラート統計"""
        now = datetime.now()
        day_ago = now - timedelta(days=1)
        week_ago = now - timedelta(days=7)
        
        day_alerts = [a for a in self.alert_history if a.created_at >= day_ago]
        week_alerts = [a for a in self.alert_history if a.created_at >= week_ago]
        
        severity_counts = {}
        for alert in day_alerts:
            severity = alert.severity.value
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        return {
            "active_count": len(self.active_alerts),
            "total_rules": len(self.rules),
            "enabled_rules": len([r for r in self.rules.values() if r.enabled]),
            "alerts_24h": len(day_alerts),
            "alerts_7d": len(week_alerts),
            "severity_distribution_24h": severity_counts,
            "channels_configured": len(self.notification_channels)
        }


# グローバルアラートマネージャー
advanced_alert_manager = AdvancedAlertManager()