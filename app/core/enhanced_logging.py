"""
高度化ログ管理システム
"""

import os
import sys
import json
import time
import logging
import logging.handlers
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from contextlib import contextmanager
from enum import Enum
import structlog
import traceback
from dataclasses import dataclass, asdict
import threading

from app.core.config import settings


class LogLevel(Enum):
    """ログレベル定義"""
    TRACE = "TRACE"
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogCategory(Enum):
    """ログカテゴリ定義"""
    SYSTEM = "system"
    REQUEST = "request"
    SECURITY = "security"
    DATABASE = "database"
    BUSINESS = "business"
    PERFORMANCE = "performance"
    AUDIT = "audit"
    ERROR = "error"


@dataclass
class LogContext:
    """ログコンテキスト"""
    request_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    job_id: Optional[str] = None
    trace_id: Optional[str] = None
    component: Optional[str] = None
    operation: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


class StructuredFormatter(logging.Formatter):
    """構造化ログフォーマッター"""
    
    def __init__(self):
        super().__init__()
        self.hostname = os.uname().nodename
    
    def format(self, record: logging.LogRecord) -> str:
        # 基本ログ情報
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "hostname": self.hostname,
            "process_id": os.getpid(),
            "thread_id": threading.get_ident(),
        }
        
        # 追加コンテキスト
        if hasattr(record, 'context') and record.context:
            log_data.update(record.context)
        
        # スタックトレース
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info)
            }
        
        # 実行場所情報
        if hasattr(record, 'pathname'):
            log_data["source"] = {
                "file": record.pathname,
                "line": record.lineno,
                "function": record.funcName
            }
        
        return json.dumps(log_data, ensure_ascii=False, default=str)


class LogRotationHandler(logging.handlers.TimedRotatingFileHandler):
    """ログローテーションハンドラー"""
    
    def __init__(self, filename: str, max_bytes: int = 100*1024*1024, backup_count: int = 30):
        # 日次ローテーション
        super().__init__(
            filename=filename,
            when='midnight',
            interval=1,
            backupCount=backup_count,
            encoding='utf-8'
        )
        self.max_bytes = max_bytes
        
    def shouldRollover(self, record):
        """ローテーション判定（サイズまたは時間ベース）"""
        # サイズチェック
        if self.stream and self.stream.tell() + len(self.format(record)) > self.max_bytes:
            return True
        
        # 時間チェック
        return super().shouldRollover(record)


class SecurityLogHandler(logging.Handler):
    """セキュリティ専用ログハンドラー"""
    
    def __init__(self, filename: str):
        super().__init__()
        self.filename = filename
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        
        # セキュリティログは別ファイルに出力
        self.file_handler = logging.FileHandler(filename, encoding='utf-8')
        self.file_handler.setFormatter(StructuredFormatter())
    
    def emit(self, record):
        # セキュリティイベントのみ処理
        if hasattr(record, 'category') and record.category == LogCategory.SECURITY.value:
            self.file_handler.emit(record)


class AuditLogHandler(logging.Handler):
    """監査ログハンドラー"""
    
    def __init__(self, filename: str):
        super().__init__()
        self.filename = filename
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        
        # 監査ログは改ざん防止のため追記専用
        self.file_handler = logging.FileHandler(filename, mode='a', encoding='utf-8')
        self.file_handler.setFormatter(StructuredFormatter())
    
    def emit(self, record):
        if hasattr(record, 'category') and record.category == LogCategory.AUDIT.value:
            self.file_handler.emit(record)


class EnhancedLogger:
    """拡張ログクラス"""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(name)
        self._context = LogContext()
    
    def with_context(self, **kwargs) -> 'EnhancedLogger':
        """コンテキスト付きロガー作成"""
        new_logger = EnhancedLogger(self.name)
        new_logger._context = LogContext(**{**self._context.to_dict(), **kwargs})
        return new_logger
    
    def _log(self, level: LogLevel, message: str, category: LogCategory = LogCategory.SYSTEM,
            **kwargs):
        """内部ログメソッド"""
        extra = {
            'context': {
                **self._context.to_dict(),
                'category': category.value,
                **kwargs
            }
        }
        
        # Python標準ログレベルにマッピング
        level_mapping = {
            LogLevel.TRACE: logging.DEBUG,
            LogLevel.DEBUG: logging.DEBUG,
            LogLevel.INFO: logging.INFO,
            LogLevel.WARNING: logging.WARNING,
            LogLevel.ERROR: logging.ERROR,
            LogLevel.CRITICAL: logging.CRITICAL,
        }
        
        self.logger.log(level_mapping[level], message, extra=extra)
    
    def trace(self, message: str, **kwargs):
        """トレースログ"""
        self._log(LogLevel.TRACE, message, **kwargs)
    
    def debug(self, message: str, **kwargs):
        """デバッグログ"""
        self._log(LogLevel.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """情報ログ"""
        self._log(LogLevel.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """警告ログ"""
        self._log(LogLevel.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """エラーログ"""
        self._log(LogLevel.ERROR, message, category=LogCategory.ERROR, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """重要ログ"""
        self._log(LogLevel.CRITICAL, message, category=LogCategory.ERROR, **kwargs)
    
    def security(self, message: str, **kwargs):
        """セキュリティログ"""
        self._log(LogLevel.WARNING, message, category=LogCategory.SECURITY, **kwargs)
    
    def audit(self, message: str, **kwargs):
        """監査ログ"""
        self._log(LogLevel.INFO, message, category=LogCategory.AUDIT, **kwargs)
    
    def performance(self, message: str, duration_ms: float, **kwargs):
        """パフォーマンスログ"""
        self._log(LogLevel.INFO, message, category=LogCategory.PERFORMANCE, 
                 duration_ms=duration_ms, **kwargs)
    
    def business(self, message: str, **kwargs):
        """ビジネスログ"""
        self._log(LogLevel.INFO, message, category=LogCategory.BUSINESS, **kwargs)


class LogManager:
    """統合ログ管理"""
    
    def __init__(self):
        self.loggers: Dict[str, EnhancedLogger] = {}
        self._setup_logging()
    
    def _setup_logging(self):
        """ログ設定初期化"""
        # ログディレクトリ作成
        if settings.LOG_FILE:
            log_dir = Path(settings.LOG_FILE).parent
            log_dir.mkdir(parents=True, exist_ok=True)
        else:
            log_dir = Path("./logs")
            log_dir.mkdir(exist_ok=True)
        
        # ルートロガー設定
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
        
        # 既存のハンドラーをクリア
        root_logger.handlers.clear()
        
        # コンソールハンドラー（開発環境）
        if settings.is_development:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.DEBUG)
            console_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            root_logger.addHandler(console_handler)
        
        # メインログファイルハンドラー
        main_log_file = log_dir / "application.log"
        main_handler = LogRotationHandler(
            str(main_log_file),
            max_bytes=100*1024*1024,  # 100MB
            backup_count=30
        )
        main_handler.setLevel(logging.INFO)
        main_handler.setFormatter(StructuredFormatter())
        root_logger.addHandler(main_handler)
        
        # エラーログファイルハンドラー
        error_log_file = log_dir / "error.log"
        error_handler = LogRotationHandler(
            str(error_log_file),
            max_bytes=50*1024*1024,  # 50MB
            backup_count=30
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(StructuredFormatter())
        root_logger.addHandler(error_handler)
        
        # セキュリティログハンドラー
        security_log_file = log_dir / "security.log"
        security_handler = SecurityLogHandler(str(security_log_file))
        root_logger.addHandler(security_handler)
        
        # 監査ログハンドラー
        audit_log_file = log_dir / "audit.log"
        audit_handler = AuditLogHandler(str(audit_log_file))
        root_logger.addHandler(audit_handler)
        
        # SQLAlchemyログ設定
        if settings.DATABASE_ECHO:
            sqlalchemy_logger = logging.getLogger('sqlalchemy.engine')
            sqlalchemy_logger.setLevel(logging.INFO)
    
    def get_logger(self, name: str) -> EnhancedLogger:
        """拡張ロガー取得"""
        if name not in self.loggers:
            self.loggers[name] = EnhancedLogger(name)
        return self.loggers[name]
    
    def cleanup_old_logs(self, days: int = 30):
        """古いログファイルのクリーンアップ"""
        log_dir = Path(settings.LOG_FOLDER)
        cutoff_time = time.time() - (days * 24 * 3600)
        
        cleaned_count = 0
        for log_file in log_dir.glob("*.log.*"):
            if log_file.stat().st_mtime < cutoff_time:
                try:
                    log_file.unlink()
                    cleaned_count += 1
                except Exception as e:
                    print(f"Failed to delete log file {log_file}: {e}")
        
        if cleaned_count > 0:
            logger = self.get_logger("log_manager")
            logger.info(f"Cleaned up {cleaned_count} old log files")


# グローバルログマネージャー
log_manager = LogManager()


def get_logger(name: str) -> EnhancedLogger:
    """拡張ロガー取得（グローバル関数）"""
    return log_manager.get_logger(name)


@contextmanager
def log_context(**kwargs):
    """ログコンテキスト管理"""
    # スレッドローカルストレージを使用
    import threading
    
    if not hasattr(threading.current_thread(), 'log_context'):
        threading.current_thread().log_context = {}
    
    old_context = threading.current_thread().log_context.copy()
    threading.current_thread().log_context.update(kwargs)
    
    try:
        yield
    finally:
        threading.current_thread().log_context = old_context


class RequestLogger:
    """リクエスト専用ログ"""
    
    def __init__(self):
        self.logger = get_logger("request")
    
    def log_request_start(self, request_id: str, method: str, url: str, 
                         client_ip: str, user_agent: str = None):
        """リクエスト開始ログ"""
        self.logger.with_context(
            request_id=request_id,
            client_ip=client_ip
        ).info(
            "Request started",
            method=method,
            url=url,
            user_agent=user_agent,
            category=LogCategory.REQUEST
        )
    
    def log_request_end(self, request_id: str, status_code: int, 
                       duration_ms: float, response_size: int = None):
        """リクエスト終了ログ"""
        self.logger.with_context(
            request_id=request_id
        ).performance(
            "Request completed",
            duration_ms=duration_ms,
            status_code=status_code,
            response_size=response_size,
            category=LogCategory.REQUEST
        )


class SecurityLogger:
    """セキュリティ専用ログ"""
    
    def __init__(self):
        self.logger = get_logger("security")
    
    def log_auth_attempt(self, user_id: str, success: bool, client_ip: str, 
                        method: str = "password"):
        """認証試行ログ"""
        self.logger.security(
            f"Authentication {'succeeded' if success else 'failed'}",
            user_id=user_id,
            client_ip=client_ip,
            auth_method=method,
            success=success
        )
    
    def log_rate_limit_exceeded(self, client_ip: str, endpoint: str, 
                               limit: int, current_count: int):
        """レート制限超過ログ"""
        self.logger.security(
            "Rate limit exceeded",
            client_ip=client_ip,
            endpoint=endpoint,
            limit=limit,
            current_count=current_count
        )
    
    def log_suspicious_activity(self, client_ip: str, activity_type: str, 
                              details: Dict[str, Any]):
        """不審な活動ログ"""
        self.logger.security(
            f"Suspicious activity detected: {activity_type}",
            client_ip=client_ip,
            activity_type=activity_type,
            **details
        )
    
    def log_file_validation_failure(self, filename: str, client_ip: str, 
                                   reason: str):
        """ファイル検証失敗ログ"""
        self.logger.security(
            "File validation failed",
            filename=filename,
            client_ip=client_ip,
            failure_reason=reason
        )


class BusinessLogger:
    """ビジネスログ専用"""
    
    def __init__(self):
        self.logger = get_logger("business")
    
    def log_job_created(self, job_id: str, user_id: str, filename: str, 
                       usage_type: str):
        """ジョブ作成ログ"""
        self.logger.business(
            "Transcription job created",
            job_id=job_id,
            user_id=user_id,
            filename=filename,
            usage_type=usage_type
        )
    
    def log_job_completed(self, job_id: str, processing_time_ms: float, 
                         transcription_length: int, summary_generated: bool):
        """ジョブ完了ログ"""
        self.logger.business(
            "Transcription job completed",
            job_id=job_id,
            processing_time_ms=processing_time_ms,
            transcription_length=transcription_length,
            summary_generated=summary_generated
        )
    
    def log_file_downloaded(self, job_id: str, file_type: str, user_id: str):
        """ファイルダウンロードログ"""
        self.logger.audit(
            "File downloaded",
            job_id=job_id,
            file_type=file_type,
            user_id=user_id
        )


# グローバルロガーインスタンス
request_logger = RequestLogger()
security_logger = SecurityLogger()
business_logger = BusinessLogger()