"""
データベース接続と設定管理
"""

import os
from typing import Generator, Optional
from contextlib import asynccontextmanager, contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
import structlog

logger = structlog.get_logger(__name__)


class DatabaseConfig:
    """データベース設定クラス"""
    
    def __init__(self):
        self.database_url = os.getenv("DATABASE_URL", "sqlite:///./data/m4a_transcribe.db")
        self.echo = os.getenv("DATABASE_ECHO", "false").lower() == "true"
        self.pool_pre_ping = True
        self.pool_recycle = 3600  # 1時間
        
        # SQLite固有設定
        self.connect_args = {}
        self.poolclass = None
        
        if "sqlite" in self.database_url:
            self.connect_args = {
                "check_same_thread": False,
                "timeout": 30  # SQLite接続タイムアウト
            }
            self.poolclass = StaticPool
    
    def get_engine_kwargs(self):
        """エンジン作成用パラメータ取得"""
        kwargs = {
            "echo": self.echo,
            "pool_pre_ping": self.pool_pre_ping,
            "pool_recycle": self.pool_recycle,
            "connect_args": self.connect_args
        }
        
        if self.poolclass:
            kwargs["poolclass"] = self.poolclass
        
        return kwargs


class DatabaseManager:
    """データベース管理クラス"""
    
    def __init__(self):
        self.config = DatabaseConfig()
        self.engine = None
        self.session_factory = None
        self._initialize()
    
    def _initialize(self):
        """データベース初期化"""
        try:
            # エンジン作成
            self.engine = create_engine(
                self.config.database_url,
                **self.config.get_engine_kwargs()
            )
            
            # SQLite WALモード設定
            if "sqlite" in self.config.database_url:
                self._setup_sqlite_optimizations()
            
            # セッションファクトリ作成
            self.session_factory = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )
            
            logger.info("Database initialized", database_url=self.config.database_url)
            
        except Exception as e:
            logger.error("Database initialization failed", error=str(e))
            raise
    
    def _setup_sqlite_optimizations(self):
        """SQLite最適化設定"""
        @event.listens_for(self.engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            """SQLite接続時の最適化設定"""
            cursor = dbapi_connection.cursor()
            
            # WALモード（Write-Ahead Logging）
            cursor.execute("PRAGMA journal_mode=WAL")
            
            # 外部キー制約有効化
            cursor.execute("PRAGMA foreign_keys=ON")
            
            # 同期モード設定（パフォーマンス向上）
            cursor.execute("PRAGMA synchronous=NORMAL")
            
            # キャッシュサイズ設定（メモリ使用量調整）
            cursor.execute("PRAGMA cache_size=10000")
            
            # 一時ファイルをメモリに保存
            cursor.execute("PRAGMA temp_store=memory")
            
            cursor.close()
    
    def get_session(self) -> Session:
        """新しいセッション取得"""
        return self.session_factory()
    
    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """セッションスコープ管理（同期版）"""
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def health_check(self) -> bool:
        """データベースヘルスチェック"""
        from sqlalchemy import text
        try:
            with self.session_scope() as session:
                session.execute(text("SELECT 1"))
                return True
        except Exception as e:
            logger.error("Database health check failed", error=str(e))
            return False
    
    def get_connection_info(self) -> dict:
        """接続情報取得"""
        return {
            "database_url": self.config.database_url,
            "engine_echo": self.config.echo,
            "pool_size": getattr(self.engine.pool, 'size', None),
            "checked_out": getattr(self.engine.pool, 'checkedout', None),
            "overflow": getattr(self.engine.pool, 'overflow', None),
        }
    
    def close(self):
        """データベース接続クリーンアップ"""
        if self.engine:
            self.engine.dispose()
            logger.info("Database connections closed")


# グローバルインスタンス
_db_manager: Optional[DatabaseManager] = None


def get_database_manager() -> DatabaseManager:
    """データベースマネージャー取得"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


def get_db() -> Generator[Session, None, None]:
    """
    データベースセッション依存注入
    FastAPI依存注入で使用
    """
    db_manager = get_database_manager()
    with db_manager.session_scope() as session:
        yield session


def get_session() -> Session:
    """新しいセッション取得（手動管理用）"""
    db_manager = get_database_manager()
    return db_manager.get_session()


@contextmanager
def database_transaction() -> Generator[Session, None, None]:
    """トランザクション管理コンテキスト"""
    db_manager = get_database_manager()
    with db_manager.session_scope() as session:
        yield session


def initialize_database():
    """データベース初期化（アプリケーション起動時に実行）"""
    db_manager = get_database_manager()
    
    # マイグレーション実行
    from app.core.migration import MigrationManager
    migration_manager = MigrationManager()
    
    if migration_manager.migrate_up():
        logger.info("Database migrations completed successfully")
    else:
        logger.error("Database migrations failed")
        raise RuntimeError("Database migration failed")
    
    return db_manager


def cleanup_database():
    """データベースクリーンアップ（アプリケーション終了時に実行）"""
    global _db_manager
    if _db_manager:
        _db_manager.close()
        _db_manager = None


# 統計・監視用関数
def get_database_stats() -> dict:
    """データベース統計情報取得"""
    from sqlalchemy import text
    
    db_manager = get_database_manager()
    
    with db_manager.session_scope() as session:
        # テーブルサイズ情報
        table_stats = {}
        
        if "sqlite" in db_manager.config.database_url:
            # SQLiteの場合
            tables_result = session.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            )
            
            for (table_name,) in tables_result:
                count_result = session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                table_stats[table_name] = count_result.scalar()
        
        return {
            "connection_info": db_manager.get_connection_info(),
            "table_statistics": table_stats,
            "health_status": db_manager.health_check()
        }