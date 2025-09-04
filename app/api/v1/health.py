"""
ヘルスチェック関連API
"""

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db, get_database_stats
from app.core.config import settings
from app.services.audio_processor import AudioProcessor
from app.services.health_service import get_health_service
from app.services.auto_recovery_service import get_auto_recovery_service
from app.services.production_monitoring import get_production_monitoring
from app.services.backup_service import get_backup_service

router = APIRouter()


@router.get("")
async def health_check():
    """基本ヘルスチェック"""
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT
    }


@router.get("/detailed")
async def detailed_health_check(db: Session = Depends(get_db)):
    """詳細ヘルスチェック"""
    try:
        # データベースチェック
        db_stats = get_database_stats()
        db_healthy = db_stats.get("health_status", False)
        
        # AI サービスチェック
        audio_processor = AudioProcessor(db)
        ai_health = await audio_processor.health_check()
        
        # 各サービスの状態
        services = {
            "database": {
                "status": "healthy" if db_healthy else "unhealthy",
                "details": {
                    "connected": db_healthy,
                    "tables": len(db_stats.get("table_statistics", {}))
                }
            },
            "storage": {
                "status": "healthy",
                "details": {
                    "upload_dir": settings.UPLOAD_DIR
                }
            },
            "ai_services": {
                "status": ai_health["overall_status"],
                "details": ai_health["services"]
            }
        }
        
        # 全体の健康状態判定
        overall_healthy = all(
            service["status"] in ["healthy", "ready"] 
            for service in services.values()
        )
        
        response_data = {
            "status": "healthy" if overall_healthy else "unhealthy",
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "services": services,
            "configuration": {
                "debug": settings.DEBUG,
                "max_file_size_mb": settings.MAX_FILE_SIZE_MB,
                "allowed_extensions": settings.ALLOWED_EXTENSIONS
            }
        }
        
        status_code = status.HTTP_200_OK if overall_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
        
        return JSONResponse(
            status_code=status_code,
            content=response_data
        )
        
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "version": settings.APP_VERSION,
                "environment": settings.ENVIRONMENT,
                "error": str(e) if settings.is_development else "Service check failed"
            }
        )


@router.get("/readiness")
async def readiness_check(db: Session = Depends(get_db)):
    """レディネスチェック（Kubernetes用）"""
    try:
        # 最低限の機能確認
        db_stats = get_database_stats()
        ready = db_stats.get("health_status", False)
        
        if ready:
            return {"status": "ready"}
        else:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "not_ready", "reason": "database_not_connected"}
            )
    
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not_ready", 
                "reason": "service_error",
                "error": str(e) if settings.is_development else None
            }
        )


@router.get("/liveness")
async def liveness_check():
    """ライブネスチェック（Kubernetes用）"""
    return {"status": "alive", "version": settings.APP_VERSION}


@router.get("/comprehensive")
async def comprehensive_health_check():
    """包括的ヘルスチェック（本番環境対応）"""
    try:
        health_service = get_health_service()
        health_result = await health_service.check_health(detailed=True)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK if health_result["system"]["status"] == "healthy" else status.HTTP_503_SERVICE_UNAVAILABLE,
            content=health_result
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "error",
                "message": "Comprehensive health check failed",
                "error": str(e) if settings.is_development else None
            }
        )


@router.get("/system-metrics")
async def system_metrics():
    """システムメトリクス取得"""
    try:
        health_service = get_health_service()
        metrics = await health_service.get_system_metrics()
        
        return {
            "cpu_percent": metrics.cpu_percent,
            "memory_percent": metrics.memory_percent,
            "disk_percent": metrics.disk_percent,
            "network_connections": metrics.network_connections,
            "active_processes": metrics.active_processes,
            "uptime_seconds": metrics.uptime_seconds,
        }
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "Failed to get system metrics", "detail": str(e)}
        )


@router.get("/recovery-history")
async def recovery_history(service: str = None, hours: int = 24):
    """自動復旧履歴取得"""
    try:
        auto_recovery = get_auto_recovery_service()
        history = auto_recovery.get_recovery_history(service=service, hours=hours)
        
        return {
            "recovery_history": history,
            "total_attempts": len(history),
            "successful_attempts": len([h for h in history if h["success"]]),
            "failed_attempts": len([h for h in history if not h["success"]])
        }
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "Failed to get recovery history", "detail": str(e)}
        )


@router.get("/production-status")
async def production_status():
    """本番環境ステータス（本番環境専用）"""
    if not settings.is_production():
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "Production endpoints only available in production environment"}
        )
    
    try:
        production_monitoring = get_production_monitoring()
        dashboard_data = production_monitoring.get_production_dashboard_data()
        
        return dashboard_data
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "Failed to get production status", "detail": str(e)}
        )


@router.get("/backup-status")
async def backup_status():
    """バックアップステータス取得"""
    try:
        backup_service = get_backup_service()
        status_info = backup_service.get_backup_status()
        
        return status_info
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "Failed to get backup status", "detail": str(e)}
        )


@router.get("/backup-history")
async def backup_history(days: int = 7):
    """バックアップ履歴取得"""
    try:
        backup_service = get_backup_service()
        history = backup_service.get_backup_history(days=days)
        
        return {"backup_history": history}
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "Failed to get backup history", "detail": str(e)}
        )