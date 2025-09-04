"""
エラー追跡とデバッグ支援システム
"""

import traceback
import hashlib
import json
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Type
from collections import defaultdict, Counter
from dataclasses import dataclass, asdict
from enum import Enum
import structlog

from app.core.enhanced_logging import get_logger

logger = get_logger("error_tracking")


class ErrorSeverity(Enum):
    """エラー重要度"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ErrorOccurrence:
    """エラー発生情報"""
    id: str
    error_hash: str
    timestamp: datetime
    request_id: Optional[str]
    user_id: Optional[str]
    endpoint: Optional[str]
    method: Optional[str]
    client_ip: Optional[str]
    user_agent: Optional[str]
    context: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class ErrorPattern:
    """エラーパターン"""
    hash: str
    error_type: str
    error_message: str
    file_path: str
    line_number: int
    function_name: str
    stack_trace: str
    first_seen: datetime
    last_seen: datetime
    occurrence_count: int
    severity: ErrorSeverity
    status: str  # "new", "investigating", "resolved", "ignored"
    tags: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "severity": self.severity.value,
            "frequency_per_hour": self.occurrence_count / max(1, (self.last_seen - self.first_seen).total_seconds() / 3600)
        }


class ErrorTracker:
    """エラー追跡システム"""
    
    def __init__(self):
        self.error_patterns: Dict[str, ErrorPattern] = {}
        self.error_occurrences: List[ErrorOccurrence] = []
        self.error_context_stack: List[Dict[str, Any]] = []
        
    def track_error(self, 
                   exception: Exception,
                   request_id: Optional[str] = None,
                   user_id: Optional[str] = None,
                   endpoint: Optional[str] = None,
                   method: Optional[str] = None,
                   client_ip: Optional[str] = None,
                   user_agent: Optional[str] = None,
                   additional_context: Dict[str, Any] = None) -> str:
        """エラー追跡"""
        
        # スタックトレース取得
        tb = traceback.extract_tb(exception.__traceback__)
        stack_trace = ''.join(traceback.format_exception(type(exception), exception, exception.__traceback__))
        
        # エラーハッシュ生成（同じエラーパターンをグループ化）
        error_signature = f"{type(exception).__name__}:{str(exception)}"
        if tb:
            error_signature += f":{tb[-1].filename}:{tb[-1].lineno}"
        
        error_hash = hashlib.md5(error_signature.encode()).hexdigest()
        
        # エラーパターン更新または作成
        if error_hash in self.error_patterns:
            pattern = self.error_patterns[error_hash]
            pattern.occurrence_count += 1
            pattern.last_seen = datetime.now()
            
            # 頻度に基づく重要度自動調整
            if pattern.occurrence_count > 50:
                pattern.severity = ErrorSeverity.CRITICAL
            elif pattern.occurrence_count > 20:
                pattern.severity = ErrorSeverity.HIGH
            elif pattern.occurrence_count > 5:
                pattern.severity = ErrorSeverity.MEDIUM
        else:
            # 新しいエラーパターン
            pattern = ErrorPattern(
                hash=error_hash,
                error_type=type(exception).__name__,
                error_message=str(exception),
                file_path=tb[-1].filename if tb else "unknown",
                line_number=tb[-1].lineno if tb else 0,
                function_name=tb[-1].name if tb else "unknown",
                stack_trace=stack_trace,
                first_seen=datetime.now(),
                last_seen=datetime.now(),
                occurrence_count=1,
                severity=self._determine_initial_severity(exception),
                status="new",
                tags=self._generate_error_tags(exception)
            )
            
            self.error_patterns[error_hash] = pattern
            
            logger.error(
                "New error pattern detected",
                error_hash=error_hash,
                error_type=pattern.error_type,
                error_message=pattern.error_message
            )
        
        # エラー発生記録
        occurrence_id = f"{error_hash}_{int(datetime.now().timestamp())}"
        occurrence = ErrorOccurrence(
            id=occurrence_id,
            error_hash=error_hash,
            timestamp=datetime.now(),
            request_id=request_id,
            user_id=user_id,
            endpoint=endpoint,
            method=method,
            client_ip=client_ip,
            user_agent=user_agent,
            context={
                **(additional_context or {}),
                **{ctx for ctx in self.error_context_stack}
            }
        )
        
        self.error_occurrences.append(occurrence)
        
        # デバッグ情報ログ出力
        logger.error(
            "Error tracked",
            error_hash=error_hash,
            occurrence_id=occurrence_id,
            error_type=type(exception).__name__,
            error_message=str(exception),
            request_id=request_id,
            endpoint=endpoint
        )
        
        return error_hash
    
    def _determine_initial_severity(self, exception: Exception) -> ErrorSeverity:
        """初期重要度判定"""
        if isinstance(exception, (SystemExit, KeyboardInterrupt)):
            return ErrorSeverity.CRITICAL
        elif isinstance(exception, (MemoryError, OSError)):
            return ErrorSeverity.HIGH
        elif isinstance(exception, (ValueError, TypeError, AttributeError)):
            return ErrorSeverity.MEDIUM
        else:
            return ErrorSeverity.LOW
    
    def _generate_error_tags(self, exception: Exception) -> List[str]:
        """エラータグ生成"""
        tags = [type(exception).__name__.lower()]
        
        error_msg = str(exception).lower()
        
        if "database" in error_msg or "sql" in error_msg:
            tags.append("database")
        if "network" in error_msg or "connection" in error_msg:
            tags.append("network")
        if "file" in error_msg or "path" in error_msg:
            tags.append("filesystem")
        if "memory" in error_msg:
            tags.append("memory")
        if "permission" in error_msg or "forbidden" in error_msg:
            tags.append("permissions")
        
        return list(set(tags))
    
    def get_error_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """エラー統計取得"""
        since = datetime.now() - timedelta(hours=hours)
        
        recent_occurrences = [
            occ for occ in self.error_occurrences
            if occ.timestamp >= since
        ]
        
        # エラータイプ別統計
        error_types = Counter([
            self.error_patterns[occ.error_hash].error_type
            for occ in recent_occurrences
        ])
        
        # 重要度別統計
        severity_counts = Counter([
            self.error_patterns[occ.error_hash].severity.value
            for occ in recent_occurrences
        ])
        
        # 時間別分布
        hourly_distribution = defaultdict(int)
        for occ in recent_occurrences:
            hour_key = occ.timestamp.strftime("%Y-%m-%d %H:00")
            hourly_distribution[hour_key] += 1
        
        return {
            "total_errors": len(recent_occurrences),
            "unique_patterns": len(set(occ.error_hash for occ in recent_occurrences)),
            "error_types": dict(error_types),
            "severity_distribution": dict(severity_counts),
            "hourly_distribution": dict(hourly_distribution),
            "top_errors": self.get_top_errors(limit=10),
            "error_rate_per_hour": len(recent_occurrences) / max(1, hours)
        }
    
    def get_top_errors(self, limit: int = 10) -> List[Dict[str, Any]]:
        """頻発エラー取得"""
        sorted_patterns = sorted(
            self.error_patterns.values(),
            key=lambda x: x.occurrence_count,
            reverse=True
        )
        
        return [pattern.to_dict() for pattern in sorted_patterns[:limit]]
    
    def get_error_details(self, error_hash: str) -> Optional[Dict[str, Any]]:
        """エラー詳細取得"""
        if error_hash not in self.error_patterns:
            return None
        
        pattern = self.error_patterns[error_hash]
        occurrences = [
            occ.to_dict() for occ in self.error_occurrences
            if occ.error_hash == error_hash
        ]
        
        return {
            "pattern": pattern.to_dict(),
            "recent_occurrences": occurrences[-20:],  # 最新20件
            "total_occurrences": len(occurrences)
        }
    
    def update_error_status(self, error_hash: str, status: str, notes: str = None):
        """エラーステータス更新"""
        if error_hash in self.error_patterns:
            self.error_patterns[error_hash].status = status
            
            logger.audit(
                "Error status updated",
                error_hash=error_hash,
                new_status=status,
                notes=notes
            )


class DebugHelper:
    """デバッグ支援"""
    
    def __init__(self):
        self.debug_sessions = {}
    
    def create_debug_context(self, request_id: str) -> Dict[str, Any]:
        """デバッグコンテキスト作成"""
        debug_context = {
            "request_id": request_id,
            "created_at": datetime.now(),
            "variables": {},
            "checkpoints": [],
            "performance_markers": []
        }
        
        self.debug_sessions[request_id] = debug_context
        return debug_context
    
    def add_checkpoint(self, request_id: str, checkpoint_name: str, data: Dict[str, Any] = None):
        """デバッグチェックポイント追加"""
        if request_id in self.debug_sessions:
            checkpoint = {
                "name": checkpoint_name,
                "timestamp": datetime.now(),
                "data": data or {}
            }
            self.debug_sessions[request_id]["checkpoints"].append(checkpoint)
    
    def add_variable(self, request_id: str, var_name: str, var_value: Any):
        """デバッグ変数追加"""
        if request_id in self.debug_sessions:
            self.debug_sessions[request_id]["variables"][var_name] = {
                "value": str(var_value),
                "type": type(var_value).__name__,
                "timestamp": datetime.now().isoformat()
            }
    
    def get_debug_session(self, request_id: str) -> Optional[Dict[str, Any]]:
        """デバッグセッション取得"""
        return self.debug_sessions.get(request_id)
    
    def cleanup_old_sessions(self, hours: int = 24):
        """古いデバッグセッションのクリーンアップ"""
        cutoff = datetime.now() - timedelta(hours=hours)
        
        to_remove = []
        for request_id, session in self.debug_sessions.items():
            if session["created_at"] < cutoff:
                to_remove.append(request_id)
        
        for request_id in to_remove:
            del self.debug_sessions[request_id]
        
        if to_remove:
            logger.info("Cleaned up old debug sessions", count=len(to_remove))


# グローバルインスタンス
error_tracker = ErrorTracker()
debug_helper = DebugHelper()