"""
バックアップとディザスタリカバリサービス
Google Cloud E2環境での最適化されたバックアップシステム
"""

import asyncio
import json
import gzip
import shutil
import tarfile
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path
import structlog
from dataclasses import dataclass, asdict

from ..core.config import get_settings
# from .database_service import DatabaseService
# from .alert_service import get_alert_service

logger = structlog.get_logger(__name__)

@dataclass
class BackupInfo:
    """バックアップ情報"""
    backup_id: str
    timestamp: datetime
    type: str  # "full", "incremental", "database", "files"
    size_bytes: int
    file_path: str
    status: str  # "pending", "running", "completed", "failed"
    duration_seconds: float
    checksum: Optional[str] = None
    compression_ratio: float = 0.0

@dataclass
class RestorePoint:
    """リストアポイント"""
    restore_id: str
    timestamp: datetime
    backup_ids: List[str]
    description: str
    verified: bool = False

class BackupService:
    """バックアップサービス"""
    
    def __init__(self):
        self.settings = get_settings()
        # self.alert_service = get_alert_service()
        
        # バックアップ設定
        self.backup_dir = Path("backups")
        self.backup_dir.mkdir(exist_ok=True)
        
        # Google Cloud Storage設定（本番環境）
        self.gcs_bucket = getattr(self.settings, 'gcs_backup_bucket', None)
        
        # バックアップスケジュール
        self.backup_schedule = {
            "full": timedelta(days=7),      # 週次フルバックアップ
            "incremental": timedelta(hours=6), # 6時間毎増分バックアップ
            "database": timedelta(hours=2),    # 2時間毎DBバックアップ
        }
        
        # 保持期間
        self.retention_policy = {
            "daily": 30,    # 30日間
            "weekly": 12,   # 12週間
            "monthly": 12,  # 12ヶ月
        }
        
        # バックアップ履歴
        self.backup_history: List[BackupInfo] = []
        self.restore_points: List[RestorePoint] = []
        
        # 監視タスク
        self._backup_task = None
        self._running = False
        
        # 除外パターン
        self.exclude_patterns = [
            "*.tmp",
            "*.log",
            "__pycache__/*",
            ".git/*",
            "node_modules/*",
            "*.pyc",
        ]
        
    async def start_backup_scheduler(self):
        """バックアップスケジューラー開始"""
        if self._running:
            logger.warning("Backup scheduler already running")
            return
        
        self._running = True
        self._backup_task = asyncio.create_task(self._backup_scheduler_loop())
        logger.info("Backup scheduler started")
        
        await self.alert_service.send_alert(
            "backup_scheduler_started",
            "Backup scheduler started successfully",
            severity="info",
            details={"timestamp": datetime.utcnow().isoformat()}
        )
    
    async def stop_backup_scheduler(self):
        """バックアップスケジューラー停止"""
        self._running = False
        if self._backup_task:
            self._backup_task.cancel()
            try:
                await self._backup_task
            except asyncio.CancelledError:
                pass
        logger.info("Backup scheduler stopped")
    
    async def _backup_scheduler_loop(self):
        """バックアップスケジューラーループ"""
        while self._running:
            try:
                current_time = datetime.utcnow()
                
                # スケジュールチェック
                for backup_type, interval in self.backup_schedule.items():
                    last_backup = self._get_last_backup(backup_type)
                    
                    if not last_backup or (current_time - last_backup.timestamp) >= interval:
                        logger.info("Scheduled backup triggered", type=backup_type)
                        await self._create_backup(backup_type)
                
                # リストアポイント作成（日次）
                if self._should_create_restore_point():
                    await self._create_restore_point()
                
                # 古いバックアップの削除
                await self._cleanup_old_backups()
                
                # 1時間毎にチェック
                await asyncio.sleep(3600)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in backup scheduler", error=str(e))
                await asyncio.sleep(1800)  # エラー時は30分待機
    
    async def create_manual_backup(self, backup_type: str = "full", description: str = "") -> BackupInfo:
        """手動バックアップ作成"""
        logger.info("Manual backup requested", type=backup_type, description=description)
        
        backup_info = await self._create_backup(backup_type, description)
        
        await self.alert_service.send_alert(
            "manual_backup_created",
            f"Manual backup completed: {backup_type}",
            severity="info",
            details=asdict(backup_info)
        )
        
        return backup_info
    
    async def _create_backup(self, backup_type: str, description: str = "") -> BackupInfo:
        """バックアップ作成"""
        backup_id = f"{backup_type}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        start_time = datetime.utcnow()
        
        backup_info = BackupInfo(
            backup_id=backup_id,
            timestamp=start_time,
            type=backup_type,
            size_bytes=0,
            file_path="",
            status="pending",
            duration_seconds=0.0,
        )
        
        try:
            backup_info.status = "running"
            self.backup_history.append(backup_info)
            
            if backup_type == "database":
                await self._backup_database(backup_info)
            elif backup_type == "files":
                await self._backup_files(backup_info)
            elif backup_type == "full":
                await self._backup_full(backup_info)
            elif backup_type == "incremental":
                await self._backup_incremental(backup_info)
            else:
                raise ValueError(f"Unknown backup type: {backup_type}")
            
            # バックアップ完了
            backup_info.status = "completed"
            backup_info.duration_seconds = (datetime.utcnow() - start_time).total_seconds()
            
            # チェックサム計算
            if Path(backup_info.file_path).exists():
                backup_info.checksum = await self._calculate_checksum(backup_info.file_path)
                backup_info.size_bytes = Path(backup_info.file_path).stat().st_size
            
            # Google Cloud Storageにアップロード（本番環境）
            if self.settings.is_production() and self.gcs_bucket:
                await self._upload_to_gcs(backup_info)
            
            logger.info("Backup completed successfully", backup_id=backup_id, 
                       size_mb=backup_info.size_bytes / 1024 / 1024,
                       duration=backup_info.duration_seconds)
            
        except Exception as e:
            backup_info.status = "failed"
            backup_info.duration_seconds = (datetime.utcnow() - start_time).total_seconds()
            logger.error("Backup failed", backup_id=backup_id, error=str(e))
            
            await self.alert_service.send_alert(
                "backup_failed",
                f"Backup failed: {backup_id}",
                severity="error",
                details={"backup_id": backup_id, "error": str(e)}
            )
            
            raise
        
        return backup_info
    
    async def _backup_database(self, backup_info: BackupInfo):
        """データベースバックアップ"""
        # db_service = DatabaseService()
        
        # SQLiteファイルのコピー
        db_path = Path("data/m4a_transcribe.db")
        backup_path = self.backup_dir / f"{backup_info.backup_id}_database.sqlite"
        
        if db_path.exists():
            # SQLite VACUUMでデータベース最適化
            await db_service.execute_query("VACUUM")
            
            # ファイルコピー
            shutil.copy2(db_path, backup_path)
            
            # 圧縮
            compressed_path = backup_path.with_suffix('.sqlite.gz')
            with open(backup_path, 'rb') as f_in:
                with gzip.open(compressed_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            # 元ファイル削除
            backup_path.unlink()
            backup_info.file_path = str(compressed_path)
            
            # 圧縮率計算
            original_size = db_path.stat().st_size
            compressed_size = compressed_path.stat().st_size
            backup_info.compression_ratio = compressed_size / original_size if original_size > 0 else 0
        else:
            raise FileNotFoundError("Database file not found")
    
    async def _backup_files(self, backup_info: BackupInfo):
        """ファイルバックアップ（アップロードファイルなど）"""
        backup_path = self.backup_dir / f"{backup_info.backup_id}_files.tar.gz"
        
        # アーカイブ作成
        with tarfile.open(backup_path, 'w:gz') as tar:
            # アップロードファイル
            uploads_dir = Path("uploads")
            if uploads_dir.exists():
                tar.add(uploads_dir, arcname="uploads", exclude=self._exclude_filter)
            
            # 設定ファイル
            config_files = [".env", ".env.production"]
            for config_file in config_files:
                config_path = Path(config_file)
                if config_path.exists():
                    tar.add(config_path, arcname=config_file)
        
        backup_info.file_path = str(backup_path)
    
    async def _backup_full(self, backup_info: BackupInfo):
        """フルバックアップ"""
        backup_path = self.backup_dir / f"{backup_info.backup_id}_full.tar.gz"
        
        # 全データのアーカイブ作成
        with tarfile.open(backup_path, 'w:gz') as tar:
            # データディレクトリ
            data_dir = Path("data")
            if data_dir.exists():
                tar.add(data_dir, arcname="data", exclude=self._exclude_filter)
            
            # アップロードディレクトリ
            uploads_dir = Path("uploads")
            if uploads_dir.exists():
                tar.add(uploads_dir, arcname="uploads", exclude=self._exclude_filter)
            
            # ログディレクトリ（最新のもののみ）
            logs_dir = Path("logs")
            if logs_dir.exists():
                # 最新のログファイルのみバックアップ
                for log_file in logs_dir.glob("*.log"):
                    if (datetime.utcnow() - datetime.fromtimestamp(log_file.stat().st_mtime)).days < 1:
                        tar.add(log_file, arcname=f"logs/{log_file.name}")
            
            # 設定ファイル
            config_files = [".env", ".env.production", "docker-compose.yml"]
            for config_file in config_files:
                config_path = Path(config_file)
                if config_path.exists():
                    tar.add(config_path, arcname=config_file)
        
        backup_info.file_path = str(backup_path)
    
    async def _backup_incremental(self, backup_info: BackupInfo):
        """増分バックアップ"""
        # 最後のフルバックアップまたは増分バックアップからの変更ファイルのみ
        last_backup = self._get_last_backup("full") or self._get_last_backup("incremental")
        cutoff_time = last_backup.timestamp if last_backup else datetime.utcnow() - timedelta(days=1)
        
        backup_path = self.backup_dir / f"{backup_info.backup_id}_incremental.tar.gz"
        
        with tarfile.open(backup_path, 'w:gz') as tar:
            # 変更されたファイルのみ追加
            for directory in ["data", "uploads"]:
                dir_path = Path(directory)
                if dir_path.exists():
                    for file_path in dir_path.rglob("*"):
                        if file_path.is_file():
                            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                            if mtime > cutoff_time:
                                tar.add(file_path, arcname=str(file_path))
        
        backup_info.file_path = str(backup_path)
    
    def _exclude_filter(self, tarinfo):
        """tarファイル除外フィルター"""
        for pattern in self.exclude_patterns:
            if tarinfo.name.endswith(pattern.replace('*', '')):
                return None
        return tarinfo
    
    async def _calculate_checksum(self, file_path: str) -> str:
        """ファイルチェックサム計算"""
        import hashlib
        
        hash_sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    
    async def _upload_to_gcs(self, backup_info: BackupInfo):
        """Google Cloud Storageへのアップロード"""
        try:
            # Google Cloud Storage クライアント使用
            # 実装省略：google-cloud-storage ライブラリを使用
            logger.info("GCS upload would be implemented here", 
                       backup_id=backup_info.backup_id)
        except Exception as e:
            logger.error("GCS upload failed", backup_id=backup_info.backup_id, error=str(e))
    
    async def _create_restore_point(self):
        """リストアポイント作成"""
        restore_id = f"restore_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        # 最新のバックアップを含むリストアポイント
        recent_backups = [b for b in self.backup_history if b.status == "completed" 
                         and (datetime.utcnow() - b.timestamp).days < 7]
        
        restore_point = RestorePoint(
            restore_id=restore_id,
            timestamp=datetime.utcnow(),
            backup_ids=[b.backup_id for b in recent_backups],
            description=f"Automated restore point - {datetime.utcnow().strftime('%Y-%m-%d')}"
        )
        
        # 検証
        restore_point.verified = await self._verify_restore_point(restore_point)
        
        self.restore_points.append(restore_point)
        logger.info("Restore point created", restore_id=restore_id, 
                   verified=restore_point.verified)
    
    async def _verify_restore_point(self, restore_point: RestorePoint) -> bool:
        """リストアポイント検証"""
        try:
            # バックアップファイルの整合性チェック
            for backup_id in restore_point.backup_ids:
                backup = next((b for b in self.backup_history if b.backup_id == backup_id), None)
                if not backup or backup.status != "completed":
                    return False
                
                # ファイル存在チェック
                if not Path(backup.file_path).exists():
                    return False
                
                # チェックサム検証
                if backup.checksum:
                    current_checksum = await self._calculate_checksum(backup.file_path)
                    if current_checksum != backup.checksum:
                        return False
            
            return True
            
        except Exception as e:
            logger.error("Restore point verification failed", error=str(e))
            return False
    
    def _get_last_backup(self, backup_type: str) -> Optional[BackupInfo]:
        """最新バックアップ取得"""
        type_backups = [b for b in self.backup_history 
                       if b.type == backup_type and b.status == "completed"]
        return max(type_backups, key=lambda x: x.timestamp) if type_backups else None
    
    def _should_create_restore_point(self) -> bool:
        """リストアポイント作成判定"""
        if not self.restore_points:
            return True
        
        last_restore_point = max(self.restore_points, key=lambda x: x.timestamp)
        return (datetime.utcnow() - last_restore_point.timestamp).days >= 1
    
    async def _cleanup_old_backups(self):
        """古いバックアップ削除"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=self.retention_policy["daily"])
            
            old_backups = [b for b in self.backup_history 
                          if b.timestamp < cutoff_date]
            
            for backup in old_backups:
                backup_path = Path(backup.file_path)
                if backup_path.exists():
                    backup_path.unlink()
                    logger.info("Old backup deleted", backup_id=backup.backup_id)
            
            # 履歴からも削除
            self.backup_history = [b for b in self.backup_history 
                                  if b.timestamp >= cutoff_date]
                                  
        except Exception as e:
            logger.error("Backup cleanup failed", error=str(e))
    
    async def restore_from_backup(self, backup_id: str, target_path: Optional[str] = None) -> bool:
        """バックアップからリストア"""
        try:
            backup = next((b for b in self.backup_history if b.backup_id == backup_id), None)
            if not backup:
                raise ValueError(f"Backup not found: {backup_id}")
            
            if backup.status != "completed":
                raise ValueError(f"Backup not completed: {backup_id}")
            
            backup_path = Path(backup.file_path)
            if not backup_path.exists():
                raise FileNotFoundError(f"Backup file not found: {backup.file_path}")
            
            # チェックサム検証
            if backup.checksum:
                current_checksum = await self._calculate_checksum(backup.file_path)
                if current_checksum != backup.checksum:
                    raise ValueError("Backup file checksum mismatch")
            
            # リストア実行
            restore_path = Path(target_path) if target_path else Path("restore")
            restore_path.mkdir(exist_ok=True)
            
            if backup_path.suffix == '.gz':
                if backup.type == "database":
                    # データベースリストア
                    with gzip.open(backup_path, 'rb') as f_in:
                        with open(restore_path / "m4a_transcribe.db", 'wb') as f_out:
                            shutil.copyfileobj(f_in, f_out)
                else:
                    # ファイルリストア
                    with tarfile.open(backup_path, 'r:gz') as tar:
                        tar.extractall(restore_path)
            
            logger.info("Restore completed successfully", backup_id=backup_id)
            
            await self.alert_service.send_alert(
                "restore_completed",
                f"Restore completed from backup: {backup_id}",
                severity="info",
                details={"backup_id": backup_id, "restore_path": str(restore_path)}
            )
            
            return True
            
        except Exception as e:
            logger.error("Restore failed", backup_id=backup_id, error=str(e))
            
            await self.alert_service.send_alert(
                "restore_failed",
                f"Restore failed from backup: {backup_id}",
                severity="error",
                details={"backup_id": backup_id, "error": str(e)}
            )
            
            return False
    
    def get_backup_status(self) -> Dict[str, Any]:
        """バックアップ状況取得"""
        recent_backups = [b for b in self.backup_history 
                         if (datetime.utcnow() - b.timestamp).days < 7]
        
        return {
            "total_backups": len(self.backup_history),
            "recent_backups": len(recent_backups),
            "successful_backups": len([b for b in recent_backups if b.status == "completed"]),
            "failed_backups": len([b for b in recent_backups if b.status == "failed"]),
            "total_size_mb": sum(b.size_bytes for b in recent_backups) / 1024 / 1024,
            "restore_points": len(self.restore_points),
            "last_backup": self.backup_history[-1].timestamp.isoformat() if self.backup_history else None,
            "retention_policy": self.retention_policy,
            "schedule": {k: v.total_seconds() / 3600 for k, v in self.backup_schedule.items()},
        }
    
    def get_backup_history(self, days: int = 30) -> List[Dict[str, Any]]:
        """バックアップ履歴取得"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        recent_backups = [b for b in self.backup_history if b.timestamp >= cutoff_date]
        
        return [
            {
                "backup_id": b.backup_id,
                "timestamp": b.timestamp.isoformat(),
                "type": b.type,
                "status": b.status,
                "size_mb": b.size_bytes / 1024 / 1024,
                "duration_minutes": b.duration_seconds / 60,
                "compression_ratio": b.compression_ratio,
            }
            for b in sorted(recent_backups, key=lambda x: x.timestamp, reverse=True)
        ]

# グローバルインスタンス
_backup_service = None

def get_backup_service() -> BackupService:
    """バックアップサービスインスタンス取得"""
    global _backup_service
    if _backup_service is None:
        _backup_service = BackupService()
    return _backup_service