"""
ログ管理とローテーションシステム
"""

import os
import gzip
import shutil
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Any
import json
import asyncio
from dataclasses import dataclass, asdict
import structlog

from app.core.config import settings
from app.core.enhanced_logging import get_logger

logger = get_logger("log_management")


@dataclass
class LogFile:
    """ログファイル情報"""
    path: Path
    size_bytes: int
    created_at: datetime
    modified_at: datetime
    log_type: str
    compressed: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "path": str(self.path),
            "created_at": self.created_at.isoformat(),
            "modified_at": self.modified_at.isoformat()
        }


@dataclass
class LogRetentionPolicy:
    """ログ保持ポリシー"""
    log_type: str
    max_age_days: int
    max_size_mb: int
    compress_after_days: int
    archive_after_days: int
    max_files: int = 100
    
    def __post_init__(self):
        # 論理的な順序チェック
        if self.compress_after_days > self.max_age_days:
            self.compress_after_days = self.max_age_days
        if self.archive_after_days > self.max_age_days:
            self.archive_after_days = self.max_age_days


class LogRotationManager:
    """ログローテーション管理"""
    
    def __init__(self, log_directory: Union[str, Path]):
        self.log_dir = Path(log_directory)
        self.log_dir.mkdir(exist_ok=True)
        
        # アーカイブディレクトリ
        self.archive_dir = self.log_dir / "archive"
        self.archive_dir.mkdir(exist_ok=True)
        
        # 一時作業ディレクトリ
        self.temp_dir = self.log_dir / "tmp"
        self.temp_dir.mkdir(exist_ok=True)
        
        # デフォルト保持ポリシー
        self.retention_policies = self._setup_default_policies()
        
        logger.info("Log rotation manager initialized", 
                   log_dir=str(self.log_dir),
                   archive_dir=str(self.archive_dir))
    
    def _setup_default_policies(self) -> Dict[str, LogRetentionPolicy]:
        """デフォルト保持ポリシー設定"""
        return {
            "application": LogRetentionPolicy(
                log_type="application",
                max_age_days=30,
                max_size_mb=100,
                compress_after_days=7,
                archive_after_days=14,
                max_files=50
            ),
            "error": LogRetentionPolicy(
                log_type="error", 
                max_age_days=90,  # エラーログは長期保存
                max_size_mb=50,
                compress_after_days=3,
                archive_after_days=7,
                max_files=100
            ),
            "security": LogRetentionPolicy(
                log_type="security",
                max_age_days=365,  # セキュリティログは1年保存
                max_size_mb=200,
                compress_after_days=1,
                archive_after_days=30,
                max_files=365
            ),
            "audit": LogRetentionPolicy(
                log_type="audit",
                max_age_days=2555,  # 監査ログは7年保存（法的要件）
                max_size_mb=500,
                compress_after_days=1,
                archive_after_days=30,
                max_files=2555
            ),
            "performance": LogRetentionPolicy(
                log_type="performance",
                max_age_days=14,
                max_size_mb=200,
                compress_after_days=3,
                archive_after_days=7,
                max_files=30
            )
        }
    
    def add_retention_policy(self, policy: LogRetentionPolicy):
        """保持ポリシー追加"""
        self.retention_policies[policy.log_type] = policy
        logger.info("Log retention policy added", 
                   log_type=policy.log_type,
                   max_age_days=policy.max_age_days)
    
    def discover_log_files(self) -> List[LogFile]:
        """ログファイル発見"""
        log_files = []
        
        for file_path in self.log_dir.glob("**/*.log*"):
            if file_path.is_file():
                try:
                    stat = file_path.stat()
                    log_type = self._determine_log_type(file_path)
                    
                    log_file = LogFile(
                        path=file_path,
                        size_bytes=stat.st_size,
                        created_at=datetime.fromtimestamp(stat.st_ctime),
                        modified_at=datetime.fromtimestamp(stat.st_mtime),
                        log_type=log_type,
                        compressed=file_path.suffix == ".gz"
                    )
                    
                    log_files.append(log_file)
                    
                except Exception as e:
                    logger.error("Failed to analyze log file", 
                               file_path=str(file_path), 
                               error=str(e))
        
        return log_files
    
    def _determine_log_type(self, file_path: Path) -> str:
        """ログタイプ判定"""
        filename = file_path.name.lower()
        
        if "error" in filename:
            return "error"
        elif "security" in filename:
            return "security"
        elif "audit" in filename:
            return "audit"
        elif "performance" in filename:
            return "performance"
        else:
            return "application"
    
    def rotate_logs(self) -> Dict[str, Any]:
        """ログローテーション実行"""
        logger.info("Starting log rotation")
        
        log_files = self.discover_log_files()
        rotation_stats = {
            "total_files": len(log_files),
            "compressed": 0,
            "archived": 0,
            "deleted": 0,
            "size_freed_mb": 0,
            "errors": []
        }
        
        for log_file in log_files:
            try:
                policy = self.retention_policies.get(log_file.log_type)
                if not policy:
                    continue
                
                file_age = datetime.now() - log_file.modified_at
                
                # 削除チェック
                if file_age.days > policy.max_age_days:
                    self._delete_log_file(log_file)
                    rotation_stats["deleted"] += 1
                    rotation_stats["size_freed_mb"] += log_file.size_bytes / (1024 * 1024)
                    continue
                
                # アーカイブチェック
                elif file_age.days > policy.archive_after_days:
                    if self._archive_log_file(log_file):
                        rotation_stats["archived"] += 1
                
                # 圧縮チェック
                elif (file_age.days > policy.compress_after_days and 
                      not log_file.compressed and
                      log_file.size_bytes > 1024 * 1024):  # 1MB以上
                    if self._compress_log_file(log_file):
                        rotation_stats["compressed"] += 1
                        rotation_stats["size_freed_mb"] += log_file.size_bytes * 0.7 / (1024 * 1024)  # 圧縮効率70%想定
                
            except Exception as e:
                error_msg = f"Failed to rotate {log_file.path}: {str(e)}"
                rotation_stats["errors"].append(error_msg)
                logger.error("Log rotation error", 
                           file_path=str(log_file.path),
                           error=str(e))
        
        # ファイル数制限の強制
        self._enforce_file_limits()
        
        logger.info("Log rotation completed", **rotation_stats)
        return rotation_stats
    
    def _compress_log_file(self, log_file: LogFile) -> bool:
        """ログファイル圧縮"""
        try:
            compressed_path = log_file.path.with_suffix(log_file.path.suffix + ".gz")
            
            with open(log_file.path, 'rb') as f_in:
                with gzip.open(compressed_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            # 元ファイル削除
            log_file.path.unlink()
            
            logger.info("Log file compressed", 
                       original=str(log_file.path),
                       compressed=str(compressed_path))
            return True
            
        except Exception as e:
            logger.error("Log compression failed", 
                        file_path=str(log_file.path),
                        error=str(e))
            return False
    
    def _archive_log_file(self, log_file: LogFile) -> bool:
        """ログファイルアーカイブ"""
        try:
            # アーカイブディレクトリに年月でサブディレクトリ作成
            archive_subdir = self.archive_dir / log_file.modified_at.strftime("%Y/%m")
            archive_subdir.mkdir(parents=True, exist_ok=True)
            
            archived_path = archive_subdir / log_file.path.name
            
            # ファイル移動
            shutil.move(str(log_file.path), str(archived_path))
            
            logger.info("Log file archived", 
                       original=str(log_file.path),
                       archived=str(archived_path))
            return True
            
        except Exception as e:
            logger.error("Log archiving failed", 
                        file_path=str(log_file.path),
                        error=str(e))
            return False
    
    def _delete_log_file(self, log_file: LogFile):
        """ログファイル削除"""
        try:
            log_file.path.unlink()
            logger.info("Old log file deleted", file_path=str(log_file.path))
            
        except Exception as e:
            logger.error("Log file deletion failed", 
                        file_path=str(log_file.path),
                        error=str(e))
    
    def _enforce_file_limits(self):
        """ファイル数制限強制"""
        for log_type, policy in self.retention_policies.items():
            log_files = [f for f in self.discover_log_files() if f.log_type == log_type]
            
            if len(log_files) > policy.max_files:
                # 古いファイルから削除
                log_files.sort(key=lambda x: x.modified_at)
                files_to_delete = log_files[:len(log_files) - policy.max_files]
                
                for log_file in files_to_delete:
                    self._delete_log_file(log_file)
                
                logger.info("Enforced file limit", 
                          log_type=log_type,
                          deleted_count=len(files_to_delete),
                          limit=policy.max_files)
    
    def get_log_statistics(self) -> Dict[str, Any]:
        """ログ統計取得"""
        log_files = self.discover_log_files()
        
        stats = {
            "total_files": len(log_files),
            "total_size_mb": sum(f.size_bytes for f in log_files) / (1024 * 1024),
            "by_type": {},
            "oldest_file": None,
            "newest_file": None,
            "compressed_files": len([f for f in log_files if f.compressed]),
            "archive_size_mb": 0
        }
        
        # タイプ別統計
        for log_type in self.retention_policies.keys():
            type_files = [f for f in log_files if f.log_type == log_type]
            if type_files:
                stats["by_type"][log_type] = {
                    "count": len(type_files),
                    "size_mb": sum(f.size_bytes for f in type_files) / (1024 * 1024),
                    "compressed_count": len([f for f in type_files if f.compressed])
                }
        
        # 最古・最新ファイル
        if log_files:
            oldest = min(log_files, key=lambda x: x.created_at)
            newest = max(log_files, key=lambda x: x.created_at)
            stats["oldest_file"] = {
                "path": str(oldest.path),
                "created_at": oldest.created_at.isoformat(),
                "age_days": (datetime.now() - oldest.created_at).days
            }
            stats["newest_file"] = {
                "path": str(newest.path),
                "created_at": newest.created_at.isoformat()
            }
        
        # アーカイブサイズ
        try:
            archive_size = sum(
                f.stat().st_size for f in self.archive_dir.rglob("*") 
                if f.is_file()
            )
            stats["archive_size_mb"] = archive_size / (1024 * 1024)
        except Exception as e:
            logger.error("Failed to calculate archive size", error=str(e))
        
        return stats


class LogSearchEngine:
    """ログ検索エンジン"""
    
    def __init__(self, log_directory: Union[str, Path]):
        self.log_dir = Path(log_directory)
        self.logger = get_logger("log_search")
    
    async def search_logs(self, 
                         query: str,
                         log_types: List[str] = None,
                         start_time: datetime = None,
                         end_time: datetime = None,
                         limit: int = 100) -> List[Dict[str, Any]]:
        """ログ検索"""
        results = []
        
        log_files = []
        for file_path in self.log_dir.glob("**/*.log*"):
            if file_path.is_file():
                log_type = self._determine_log_type(file_path)
                if log_types and log_type not in log_types:
                    continue
                
                # 時間フィルタ（ファイル更新時間ベース）
                if start_time or end_time:
                    file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if start_time and file_mtime < start_time:
                        continue
                    if end_time and file_mtime > end_time:
                        continue
                
                log_files.append(file_path)
        
        # 並行検索
        search_tasks = [
            self._search_in_file(file_path, query, start_time, end_time)
            for file_path in log_files
        ]
        
        file_results = await asyncio.gather(*search_tasks, return_exceptions=True)
        
        # 結果統合
        for file_result in file_results:
            if isinstance(file_result, Exception):
                continue
            results.extend(file_result)
        
        # タイムスタンプでソート
        results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        return results[:limit]
    
    async def _search_in_file(self, 
                             file_path: Path, 
                             query: str,
                             start_time: datetime = None,
                             end_time: datetime = None) -> List[Dict[str, Any]]:
        """ファイル内検索"""
        results = []
        
        try:
            # 圧縮ファイル対応
            if file_path.suffix == ".gz":
                import gzip
                open_func = gzip.open
                mode = "rt"
            else:
                open_func = open
                mode = "r"
            
            with open_func(file_path, mode, encoding="utf-8", errors="ignore") as f:
                line_number = 0
                
                for line in f:
                    line_number += 1
                    
                    if query.lower() in line.lower():
                        # JSON構造化ログの解析を試行
                        log_entry = self._parse_log_line(line, file_path, line_number)
                        
                        # 時間フィルタ
                        if start_time or end_time:
                            entry_time = log_entry.get("parsed_timestamp")
                            if entry_time:
                                if start_time and entry_time < start_time:
                                    continue
                                if end_time and entry_time > end_time:
                                    continue
                        
                        results.append(log_entry)
                        
                        # メモリ使用量制限
                        if len(results) > 1000:
                            break
        
        except Exception as e:
            self.logger.error("File search failed", 
                            file_path=str(file_path), 
                            error=str(e))
        
        return results
    
    def _parse_log_line(self, line: str, file_path: Path, line_number: int) -> Dict[str, Any]:
        """ログ行解析"""
        log_entry = {
            "file": str(file_path),
            "line_number": line_number,
            "raw_line": line.strip(),
            "timestamp": None,
            "parsed_timestamp": None,
            "level": None,
            "message": None,
            "log_type": self._determine_log_type(file_path)
        }
        
        try:
            # JSON構造化ログの解析
            if line.strip().startswith("{"):
                parsed = json.loads(line.strip())
                log_entry.update({
                    "timestamp": parsed.get("timestamp"),
                    "level": parsed.get("level"),
                    "message": parsed.get("message"),
                    "logger": parsed.get("logger"),
                    "context": parsed.get("context", {})
                })
                
                # タイムスタンプ解析
                if parsed.get("timestamp"):
                    try:
                        log_entry["parsed_timestamp"] = datetime.fromisoformat(
                            parsed["timestamp"].replace("Z", "+00:00")
                        )
                    except Exception:
                        pass
            
            # 通常のログ形式の解析（簡易実装）
            else:
                parts = line.split(" - ", 3)
                if len(parts) >= 4:
                    log_entry.update({
                        "timestamp": parts[0],
                        "logger": parts[1],
                        "level": parts[2],
                        "message": parts[3].strip()
                    })
        
        except Exception as e:
            # 解析失敗時は生ログのまま
            self.logger.debug("Log line parsing failed", error=str(e))
        
        return log_entry
    
    def _determine_log_type(self, file_path: Path) -> str:
        """ログタイプ判定"""
        filename = file_path.name.lower()
        
        if "error" in filename:
            return "error"
        elif "security" in filename:
            return "security"
        elif "audit" in filename:
            return "audit"
        elif "performance" in filename:
            return "performance"
        else:
            return "application"


class LogManager:
    """統合ログ管理"""
    
    def __init__(self, log_directory: Union[str, Path] = None):
        if log_directory:
            self.log_dir = Path(log_directory)
        elif settings.LOG_FILE:
            self.log_dir = Path(settings.LOG_FILE).parent
        else:
            self.log_dir = Path("./logs")
        self.rotation_manager = LogRotationManager(self.log_dir)
        self.search_engine = LogSearchEngine(self.log_dir)
        self._rotation_task = None
        
        logger.info("Log manager initialized", log_dir=str(self.log_dir))
    
    async def start_rotation_scheduler(self):
        """ローテーションスケジューラー開始"""
        if self._rotation_task:
            return
        
        self._rotation_task = asyncio.create_task(self._rotation_loop())
        logger.info("Log rotation scheduler started")
    
    async def stop_rotation_scheduler(self):
        """ローテーションスケジューラー停止"""
        if self._rotation_task:
            self._rotation_task.cancel()
            try:
                await self._rotation_task
            except asyncio.CancelledError:
                pass
            self._rotation_task = None
        
        logger.info("Log rotation scheduler stopped")
    
    async def _rotation_loop(self):
        """ローテーションループ"""
        while True:
            try:
                # 4時間ごとにローテーション実行
                await asyncio.sleep(4 * 3600)
                self.rotation_manager.rotate_logs()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Log rotation loop error", error=str(e))
                await asyncio.sleep(3600)  # エラー時は1時間後に再試行
    
    def manual_rotation(self) -> Dict[str, Any]:
        """手動ローテーション実行"""
        return self.rotation_manager.rotate_logs()
    
    async def search_logs(self, **kwargs) -> List[Dict[str, Any]]:
        """ログ検索"""
        return await self.search_engine.search_logs(**kwargs)
    
    def get_log_statistics(self) -> Dict[str, Any]:
        """ログ統計取得"""
        return self.rotation_manager.get_log_statistics()
    
    def add_retention_policy(self, policy: LogRetentionPolicy):
        """保持ポリシー追加"""
        self.rotation_manager.add_retention_policy(policy)


# グローバルログマネージャー
log_manager = LogManager()