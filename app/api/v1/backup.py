"""
バックアップ管理API
"""

from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List
import structlog

from app.core.config import settings
from app.services.backup_service import get_backup_service

logger = structlog.get_logger(__name__)
router = APIRouter()

class BackupRequest(BaseModel):
    """バックアップ作成リクエスト"""
    backup_type: str = "full"  # "full", "incremental", "database", "files"
    description: Optional[str] = ""

class RestoreRequest(BaseModel):
    """リストア実行リクエスト"""
    backup_id: str
    target_path: Optional[str] = None

@router.post("/create")
async def create_backup(request: BackupRequest, background_tasks: BackgroundTasks):
    """手動バックアップ作成"""
    try:
        backup_service = get_backup_service()
        
        # バリデーション
        valid_types = ["full", "incremental", "database", "files"]
        if request.backup_type not in valid_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid backup type. Must be one of: {valid_types}"
            )
        
        logger.info("Manual backup requested", 
                   backup_type=request.backup_type, 
                   description=request.description)
        
        # バックアップ作成（非同期実行）
        backup_info = await backup_service.create_manual_backup(
            backup_type=request.backup_type,
            description=request.description
        )
        
        return {
            "message": "Backup created successfully",
            "backup_id": backup_info.backup_id,
            "backup_type": backup_info.type,
            "status": backup_info.status,
            "timestamp": backup_info.timestamp.isoformat(),
            "size_mb": backup_info.size_bytes / 1024 / 1024 if backup_info.size_bytes > 0 else 0,
            "duration_seconds": backup_info.duration_seconds,
        }
        
    except Exception as e:
        logger.error("Manual backup failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Backup creation failed: {str(e)}"
        )

@router.get("/list")
async def list_backups(days: int = 30):
    """バックアップ一覧取得"""
    try:
        backup_service = get_backup_service()
        history = backup_service.get_backup_history(days=days)
        
        return {
            "backups": history,
            "total_count": len(history),
        }
        
    except Exception as e:
        logger.error("Failed to list backups", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve backup list"
        )

@router.get("/status")
async def get_backup_status():
    """バックアップ全体ステータス"""
    try:
        backup_service = get_backup_service()
        status_info = backup_service.get_backup_status()
        
        return status_info
        
    except Exception as e:
        logger.error("Failed to get backup status", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get backup status"
        )

@router.post("/restore")
async def restore_backup(request: RestoreRequest):
    """バックアップからリストア"""
    if not settings.is_development():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Restore operations only allowed in development environment"
        )
    
    try:
        backup_service = get_backup_service()
        
        logger.info("Restore requested", backup_id=request.backup_id, target_path=request.target_path)
        
        success = await backup_service.restore_from_backup(
            backup_id=request.backup_id,
            target_path=request.target_path
        )
        
        if success:
            return {
                "message": "Restore completed successfully",
                "backup_id": request.backup_id,
                "target_path": request.target_path or "restore"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Restore operation failed"
            )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Restore failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Restore failed: {str(e)}"
        )

@router.delete("/delete/{backup_id}")
async def delete_backup(backup_id: str):
    """バックアップ削除"""
    if not settings.is_development():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Backup deletion only allowed in development environment"
        )
    
    try:
        backup_service = get_backup_service()
        
        # 実装省略：バックアップ削除機能
        # backup_service.delete_backup(backup_id)
        
        return {
            "message": "Backup deletion feature not implemented yet",
            "backup_id": backup_id
        }
        
    except Exception as e:
        logger.error("Failed to delete backup", backup_id=backup_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete backup"
        )

@router.get("/validate/{backup_id}")
async def validate_backup(backup_id: str):
    """バックアップ整合性検証"""
    try:
        backup_service = get_backup_service()
        
        # バックアップ検索
        backup = None
        for b in backup_service.backup_history:
            if b.backup_id == backup_id:
                backup = b
                break
        
        if not backup:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Backup not found"
            )
        
        # 整合性チェック
        from pathlib import Path
        backup_path = Path(backup.file_path)
        
        if not backup_path.exists():
            return {
                "backup_id": backup_id,
                "valid": False,
                "reason": "Backup file not found",
                "file_path": backup.file_path
            }
        
        # チェックサム検証
        valid = True
        reason = "Backup file exists"
        
        if backup.checksum:
            current_checksum = await backup_service._calculate_checksum(backup.file_path)
            if current_checksum != backup.checksum:
                valid = False
                reason = "Checksum mismatch"
        
        return {
            "backup_id": backup_id,
            "valid": valid,
            "reason": reason,
            "checksum_verified": backup.checksum is not None,
            "file_size_mb": backup_path.stat().st_size / 1024 / 1024,
            "file_path": backup.file_path
        }
        
    except Exception as e:
        logger.error("Backup validation failed", backup_id=backup_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Backup validation failed"
        )