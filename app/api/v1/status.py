"""
ステータス関連API
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db, get_database_stats
from app.core.config import settings
from app.services.transcription_service import TranscriptionService
from app.services.summary_service import SummaryService

router = APIRouter()


@router.get("")
async def get_api_status(db: Session = Depends(get_db)):
    """APIステータス取得"""
    
    # データベース統計
    db_stats = get_database_stats()
    
    # サービス統計
    transcription_service = TranscriptionService(db)
    job_stats = transcription_service.get_job_statistics()
    
    summary_service = SummaryService(db)
    summary_stats = summary_service.get_summary_statistics()
    
    return {
        "api_version": "v1",
        "status": "active",
        "environment": settings.ENVIRONMENT,
        "app_version": settings.APP_VERSION,
        "services": {
            "transcription": "ready",
            "summarization": "ready",
            "database": "connected" if db_stats.get("health_status") else "error",
            "file_storage": "ready"
        },
        "statistics": {
            "total_jobs": job_stats.get("total_jobs", 0),
            "total_summaries": summary_stats.get("total_summaries", 0),
            "database_tables": len(db_stats.get("table_statistics", {}))
        },
        "configuration": {
            "max_file_size_mb": settings.MAX_FILE_SIZE_MB,
            "allowed_extensions": settings.ALLOWED_EXTENSIONS,
            "ollama_model": settings.OLLAMA_MODEL,
            "whisper_model": settings.WHISPER_MODEL
        }
    }


@router.get("/database")
async def get_database_status():
    """データベースステータス取得"""
    return get_database_stats()


@router.get("/jobs/stats")
async def get_job_statistics(db: Session = Depends(get_db)):
    """ジョブ統計情報取得"""
    service = TranscriptionService(db)
    return service.get_job_statistics()


@router.get("/summaries/stats")
async def get_summary_statistics(db: Session = Depends(get_db)):
    """要約統計情報取得"""
    service = SummaryService(db)
    return service.get_summary_statistics()