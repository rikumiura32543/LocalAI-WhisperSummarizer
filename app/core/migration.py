"""
データベースマイグレーション機能

簡易マイグレーションシステム（Alembicの代替）
"""

import os
import json
from typing import List, Dict, Any
from datetime import datetime
from pathlib import Path
from sqlalchemy import text, inspect
from sqlalchemy.orm import sessionmaker

from app.models.base import get_engine


class Migration:
    """マイグレーション定義クラス"""
    
    def __init__(self, version: str, description: str):
        self.version = version
        self.description = description
        self.timestamp = datetime.utcnow()
    
    def up(self, session) -> None:
        """マイグレーション適用"""
        raise NotImplementedError("up method must be implemented")
    
    def down(self, session) -> None:
        """マイグレーション取り消し"""
        raise NotImplementedError("down method must be implemented")


class MigrationManager:
    """マイグレーション管理クラス"""
    
    def __init__(self):
        self.engine = get_engine()
        self.Session = sessionmaker(bind=self.engine)
        self.migrations_dir = Path(__file__).parent.parent.parent / "migrations"
        self.migrations_dir.mkdir(exist_ok=True)
        
        # マイグレーション履歴テーブル作成
        self._create_migration_table()
    
    def _create_migration_table(self):
        """マイグレーション履歴テーブル作成"""
        with self.engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS migration_history (
                    version TEXT PRIMARY KEY,
                    description TEXT NOT NULL,
                    applied_at DATETIME NOT NULL,
                    execution_time_seconds REAL
                )
            """))
            conn.commit()
    
    def get_applied_migrations(self) -> List[str]:
        """適用済みマイグレーション一覧取得"""
        with self.Session() as session:
            result = session.execute(text("SELECT version FROM migration_history ORDER BY version"))
            return [row[0] for row in result]
    
    def get_pending_migrations(self) -> List[Migration]:
        """未適用マイグレーション一覧取得"""
        applied = set(self.get_applied_migrations())
        all_migrations = self._discover_migrations()
        return [m for m in all_migrations if m.version not in applied]
    
    def _discover_migrations(self) -> List[Migration]:
        """マイグレーションファイル発見"""
        migrations = []
        
        # 組み込みマイグレーション
        migrations.extend(self._get_builtin_migrations())
        
        # カスタムマイグレーションファイル読み込み
        # TODO: 必要に応じてカスタムマイグレーション機能を実装
        
        return sorted(migrations, key=lambda x: x.version)
    
    def _get_builtin_migrations(self) -> List[Migration]:
        """組み込みマイグレーション定義"""
        return [
            InitialSchemaMigration(),
            AddIndexesMigration(),
            AddTriggersMigration(),
        ]
    
    def apply_migration(self, migration: Migration) -> bool:
        """マイグレーション適用"""
        start_time = datetime.utcnow()
        
        try:
            with self.Session() as session:
                # マイグレーション実行
                migration.up(session)
                
                # 履歴記録
                execution_time = (datetime.utcnow() - start_time).total_seconds()
                session.execute(text("""
                    INSERT INTO migration_history (version, description, applied_at, execution_time_seconds)
                    VALUES (:version, :description, :applied_at, :execution_time)
                """), {
                    "version": migration.version,
                    "description": migration.description,
                    "applied_at": datetime.utcnow(),
                    "execution_time": execution_time
                })
                
                session.commit()
                
            print(f"✅ Migration {migration.version} applied: {migration.description}")
            return True
            
        except Exception as e:
            print(f"❌ Migration {migration.version} failed: {e}")
            return False
    
    def rollback_migration(self, migration: Migration) -> bool:
        """マイグレーション取り消し"""
        try:
            with self.Session() as session:
                # マイグレーション取り消し実行
                migration.down(session)
                
                # 履歴削除
                session.execute(text("""
                    DELETE FROM migration_history WHERE version = :version
                """), {"version": migration.version})
                
                session.commit()
                
            print(f"↩️  Migration {migration.version} rolled back: {migration.description}")
            return True
            
        except Exception as e:
            print(f"❌ Migration {migration.version} rollback failed: {e}")
            return False
    
    def migrate_up(self) -> bool:
        """未適用マイグレーションをすべて適用"""
        pending = self.get_pending_migrations()
        
        if not pending:
            print("✅ All migrations are up to date")
            return True
        
        print(f"📦 Applying {len(pending)} migrations...")
        
        success_count = 0
        for migration in pending:
            if self.apply_migration(migration):
                success_count += 1
            else:
                print(f"💥 Failed to apply migration {migration.version}")
                break
        
        print(f"🎉 Applied {success_count}/{len(pending)} migrations")
        return success_count == len(pending)
    
    def get_schema_info(self) -> Dict[str, Any]:
        """データベーススキーマ情報取得"""
        inspector = inspect(self.engine)
        
        return {
            "tables": inspector.get_table_names(),
            "views": inspector.get_view_names(),
            "applied_migrations": self.get_applied_migrations(),
            "pending_migrations": [m.version for m in self.get_pending_migrations()]
        }


class InitialSchemaMigration(Migration):
    """初期スキーママイグレーション"""
    
    def __init__(self):
        super().__init__("001_initial_schema", "Initial database schema")
    
    def up(self, session):
        """初期テーブル作成"""
        from app.models import create_tables
        create_tables()
    
    def down(self, session):
        """全テーブル削除"""
        from app.models import drop_tables
        drop_tables()


class AddIndexesMigration(Migration):
    """インデックス追加マイグレーション"""
    
    def __init__(self):
        super().__init__("002_add_indexes", "Add database indexes for performance")
    
    def up(self, session):
        """インデックス作成"""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_transcription_jobs_status ON transcription_jobs(status_code)",
            "CREATE INDEX IF NOT EXISTS idx_transcription_jobs_created_at ON transcription_jobs(created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_transcription_jobs_usage_type ON transcription_jobs(usage_type_code)",
            "CREATE INDEX IF NOT EXISTS idx_transcription_segments_job_id ON transcription_segments(job_id)",
            "CREATE INDEX IF NOT EXISTS idx_transcription_segments_time ON transcription_segments(start_time, end_time)",
            "CREATE INDEX IF NOT EXISTS idx_generated_files_job_id ON generated_files(job_id)",
            "CREATE INDEX IF NOT EXISTS idx_processing_logs_timestamp ON processing_logs(timestamp DESC)",
        ]
        
        for index_sql in indexes:
            session.execute(text(index_sql))
    
    def down(self, session):
        """インデックス削除"""
        indexes = [
            "DROP INDEX IF EXISTS idx_transcription_jobs_status",
            "DROP INDEX IF EXISTS idx_transcription_jobs_created_at",
            "DROP INDEX IF EXISTS idx_transcription_jobs_usage_type",
            "DROP INDEX IF EXISTS idx_transcription_segments_job_id",
            "DROP INDEX IF EXISTS idx_transcription_segments_time",
            "DROP INDEX IF EXISTS idx_generated_files_job_id",
            "DROP INDEX IF EXISTS idx_processing_logs_timestamp",
        ]
        
        for drop_sql in indexes:
            session.execute(text(drop_sql))


class AddTriggersMigration(Migration):
    """トリガー追加マイグレーション"""
    
    def __init__(self):
        super().__init__("003_add_triggers", "Add database triggers")
    
    def up(self, session):
        """トリガー作成"""
        triggers = [
            """
            CREATE TRIGGER IF NOT EXISTS trigger_transcription_jobs_updated_at
                AFTER UPDATE ON transcription_jobs
            BEGIN
                UPDATE transcription_jobs 
                SET updated_at = CURRENT_TIMESTAMP 
                WHERE id = NEW.id;
            END
            """,
            """
            CREATE TRIGGER IF NOT EXISTS trigger_check_file_expiration
                AFTER INSERT ON generated_files
            BEGIN
                UPDATE generated_files 
                SET expires_at = datetime(CURRENT_TIMESTAMP, '+7 days')
                WHERE id = NEW.id AND expires_at IS NULL;
            END
            """
        ]
        
        for trigger_sql in triggers:
            session.execute(text(trigger_sql))
    
    def down(self, session):
        """トリガー削除"""
        triggers = [
            "DROP TRIGGER IF EXISTS trigger_transcription_jobs_updated_at",
            "DROP TRIGGER IF EXISTS trigger_check_file_expiration",
        ]
        
        for drop_sql in triggers:
            session.execute(text(drop_sql))