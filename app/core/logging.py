"""
ログ設定管理
"""

import sys
import structlog
from pathlib import Path
from typing import Any, Dict

from app.core.config import settings


def setup_logging():
    """ログ設定初期化"""
    
    # 基本設定
    log_level = settings.LOG_LEVEL.upper()
    
    # 開発環境用の設定
    if settings.is_development:
        # コンソール出力（開発用）
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="ISO"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.dev.ConsoleRenderer(colors=True)
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
    else:
        # 本番環境用の設定（JSON出力）
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="ISO"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )


def get_logger(name: str = None) -> Any:
    """ロガー取得"""
    return structlog.get_logger(name)


def log_request(method: str, url: str, status_code: int, duration_ms: float):
    """リクエストログ出力"""
    logger = get_logger("request")
    logger.info(
        "HTTP request",
        method=method,
        url=url,
        status_code=status_code,
        duration_ms=duration_ms
    )


def log_database_query(query: str, duration_ms: float, row_count: int = None):
    """データベースクエリログ出力"""
    if settings.DATABASE_ECHO:
        logger = get_logger("database")
        logger.debug(
            "Database query",
            query=query[:200] + "..." if len(query) > 200 else query,
            duration_ms=duration_ms,
            row_count=row_count
        )


def log_job_event(job_id: str, event: str, details: Dict[str, Any] = None):
    """ジョブイベントログ出力"""
    logger = get_logger("job")
    logger.info(
        "Job event",
        job_id=job_id,
        event=event,
        **details or {}
    )


def log_error(error: Exception, context: Dict[str, Any] = None):
    """エラーログ出力"""
    logger = get_logger("error")
    logger.error(
        "Application error",
        error=str(error),
        error_type=type(error).__name__,
        **context or {}
    )