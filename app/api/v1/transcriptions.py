"""
転写関連API
"""

import os
import uuid
from typing import List, Optional
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings, is_allowed_file, get_upload_path
from app.services.transcription_service import TranscriptionService
from app.services.summary_service import SummaryService
from app.services.audio_processor import process_audio_background
from app.services.file_validation_service import FileValidationService, FileQuarantineService
from app.api.models import (
    TranscriptionJobResponse, TranscriptionJobListResponse,
    UsageTypeEnum, JobStatusEnum, BaseResponse
)
import structlog

logger = structlog.get_logger(__name__)
router = APIRouter()


def validate_upload_file(file: UploadFile) -> None:
    """アップロードファイルバリデーション（基本チェック）"""
    
    # ファイル存在チェック
    if not file or not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ファイルが選択されていません"
        )
    
    # ファイル名検証
    if len(file.filename) > 255:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ファイル名が長すぎます"
        )
    
    # 危険な文字チェック
    dangerous_chars = ['..', '/', '\\', ':', '*', '?', '"', '<', '>', '|']
    if any(char in file.filename for char in dangerous_chars):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ファイル名に使用できない文字が含まれています"
        )
    
    # ファイル形式チェック
    if not is_allowed_file(file.filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"サポートされていないファイル形式です。許可される形式: {', '.join(settings.ALLOWED_EXTENSIONS)}"
        )
    
    # MIMEタイプチェック
    allowed_mime_types = ["audio/m4a", "audio/mp4", "audio/mpeg", "audio/wav", "audio/x-wav", "audio/wave"]
    if file.content_type and file.content_type not in allowed_mime_types:
        logger.warning("Potentially unsupported MIME type", 
                      filename=file.filename,
                      content_type=file.content_type)
        # 厳密なチェックは後続の詳細検証で行う


async def save_upload_file(file: UploadFile, filename: str, file_content: bytes = None) -> Path:
    """アップロードファイル保存と詳細検証"""
    file_path = get_upload_path(filename)
    quarantine_service = FileQuarantineService(Path(settings.UPLOAD_DIR) / "quarantine")
    
    try:
        # ファイル保存
        with open(file_path, "wb") as buffer:
            if file_content:
                # 既に読み込まれたコンテンツを使用
                content = file_content
            else:
                # ファイルから読み込み
                content = await file.read()
            buffer.write(content)
        
        logger.info("File saved for validation", 
                   filename=filename,
                   size_bytes=len(content),
                   path=str(file_path))
        
        # 詳細ファイル検証
        validation_service = FileValidationService(max_file_size=settings.max_file_size_bytes)
        validation_result = validation_service.validate_file(file_path)
        
        if not validation_result.is_valid:
            # ファイルを隔離
            error_details = "; ".join(validation_result.errors)
            quarantine_service.quarantine_file(file_path, f"Validation failed: {error_details}")
            
            logger.error("File validation failed",
                        filename=filename,
                        errors=validation_result.errors,
                        warnings=validation_result.warnings)
            
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"ファイル検証エラー: {error_details}"
            )
        
        # 警告がある場合はログに記録
        if validation_result.warnings:
            logger.warning("File validation warnings",
                          filename=filename,
                          warnings=validation_result.warnings)
        
        # 検証成功のログ
        logger.info("File validation successful",
                   filename=filename,
                   file_type=validation_result.file_type,
                   mime_type=validation_result.mime_type,
                   duration=validation_result.duration,
                   codec=validation_result.codec)
        
        return file_path
    
    except HTTPException:
        # HTTPExceptionはそのまま再発生
        raise
    except Exception as e:
        logger.error("Failed to save or validate file", 
                    filename=filename,
                    error=str(e))
        if file_path.exists():
            try:
                quarantine_service.quarantine_file(file_path, f"Processing error: {str(e)}")
            except Exception:
                file_path.unlink()  # 隔離に失敗した場合は削除
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ファイル処理エラー"
        )


def normalize_mime_type(mime_type: str) -> str:
    """MIMEタイプを正規化"""
    if not mime_type:
        return "audio/m4a"
    
    # MIMEタイプの正規化マッピング
    mime_mapping = {
        "audio/x-m4a": "audio/m4a",
        "audio/mp4": "audio/mp4", 
        "audio/m4a": "audio/m4a",
        "audio/wav": "audio/wav",
        "audio/wave": "audio/wav",
        "audio/x-wav": "audio/wav",
        "audio/mp3": "audio/mp3",
        "audio/mpeg": "audio/mp3"
    }
    
    return mime_mapping.get(mime_type.lower(), "audio/m4a")

@router.post("", response_model=TranscriptionJobResponse, status_code=status.HTTP_201_CREATED)
async def create_transcription_job(
    background_tasks: BackgroundTasks,
    usage_type: UsageTypeEnum = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """転写ジョブ作成"""
    
    # ファイルバリデーション
    validate_upload_file(file)
    
    # ファイル読み込み
    content = await file.read()
    
    # ファイルサイズチェック
    if len(content) > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"ファイルサイズが制限を超えています（最大: {settings.MAX_FILE_SIZE_MB}MB）"
        )
    
    # サービス初期化
    service = TranscriptionService(db)
    
    try:
        # MIMEタイプを正規化
        normalized_mime_type = normalize_mime_type(file.content_type or "audio/m4a")
        
        # ジョブ作成
        job = service.create_job(
            original_filename=file.filename,
            file_content=content,
            usage_type_code=usage_type.value,
            mime_type=normalized_mime_type
        )
        
        # ファイル保存（読み込んだコンテンツを渡す）
        file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'm4a'
        saved_filename = f"{job.id}.{file_extension}"
        file_path = await save_upload_file(file, saved_filename, content)
        
        # 音声ファイル情報保存
        service.save_audio_info(
            job_id=job.id,
            file_path=str(file_path),
            duration_seconds=0.0,  # 後で実際の値に更新
        )
        
        # バックグラウンド処理開始（音声転写・AI要約）
        background_tasks.add_task(process_audio_background, job.id, db)
        
        logger.info("Transcription job created successfully", 
                   job_id=job.id,
                   filename=job.original_filename,
                   usage_type=usage_type,
                   mime_type=normalized_mime_type)
        
        # レスポンス生成
        return TranscriptionJobResponse(
            id=job.id,
            filename=job.filename,
            original_filename=job.original_filename,
            file_size=job.file_size,
            mime_type=job.mime_type,
            usage_type_code=job.usage_type_code,
            status_code=JobStatusEnum(job.status_code),
            progress=job.progress,
            message=job.message,
            error_message=job.error_message,
            processing_started_at=job.processing_started_at,
            processing_completed_at=job.processing_completed_at,
            created_at=job.created_at,
            updated_at=job.updated_at
        )
        
    except Exception as e:
        logger.error("Failed to create transcription job", 
                    filename=file.filename,
                    usage_type=usage_type,
                    error=str(e))
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="転写ジョブの作成に失敗しました"
        )


@router.get("", response_model=TranscriptionJobListResponse)
async def list_transcription_jobs(
    usage_type: Optional[UsageTypeEnum] = None,
    status_filter: Optional[JobStatusEnum] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """転写ジョブ一覧取得"""
    
    # パラメータバリデーション
    if limit > 100:
        limit = 100
    if offset < 0:
        offset = 0
    
    service = TranscriptionService(db)
    
    try:
        # ジョブ取得
        jobs = service.get_jobs(
            usage_type=usage_type.value if usage_type else None,
            status=status_filter.value if status_filter else None,
            limit=limit,
            offset=offset
        )
        
        # レスポンス変換
        job_responses = []
        for job in jobs:
            job_response = TranscriptionJobResponse(
                id=job.id,
                filename=job.filename,
                original_filename=job.original_filename,
                file_size=job.file_size,
                mime_type=job.mime_type,
                usage_type_code=job.usage_type_code,
                status_code=JobStatusEnum(job.status_code),
                progress=job.progress,
                message=job.message,
                error_message=job.error_message,
                processing_started_at=job.processing_started_at,
                processing_completed_at=job.processing_completed_at,
                created_at=job.created_at,
                updated_at=job.updated_at
            )
            job_responses.append(job_response)
        
        return TranscriptionJobListResponse(
            jobs=job_responses,
            total=len(job_responses),
            message=f"{len(job_responses)}件のジョブを取得しました"
        )
        
    except Exception as e:
        logger.error("Failed to list transcription jobs", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ジョブ一覧の取得に失敗しました"
        )


@router.get("/{job_id}", response_model=TranscriptionJobResponse)
async def get_transcription_job(
    job_id: str,
    db: Session = Depends(get_db)
):
    """転写ジョブ詳細取得"""
    
    service = TranscriptionService(db)
    
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="指定されたジョブが見つかりません"
        )
    
    # 関連データ取得
    transcription_result = None
    audio_info = None
    
    if job.status_code in ["completed", "error"]:
        # 転写結果取得
        result = service.get_transcription_result(job_id)
        if result:
            segments = service.get_transcription_segments(job_id)
            transcription_result = {
                "text": result.text,
                "confidence": result.confidence,
                "language": result.language,
                "duration_seconds": result.duration_seconds,
                "model_used": result.model_used,
                "processing_time_seconds": result.processing_time_seconds,
                "segments_count": result.segments_count,
                "segments": [
                    {
                        "segment_index": seg.segment_index,
                        "start_time": seg.start_time,
                        "end_time": seg.end_time,
                        "text": seg.text,
                        "confidence": seg.confidence,
                        "speaker_id": seg.speaker_id,
                        "speaker_name": seg.speaker_name
                    }
                    for seg in segments
                ] if segments else None
            }
        
        # 音声ファイル情報取得
        if hasattr(job, 'audio_file') and job.audio_file:
            audio_info = {
                "duration_seconds": job.audio_file.duration_seconds,
                "bitrate": job.audio_file.bitrate,
                "sample_rate": job.audio_file.sample_rate,
                "channels": job.audio_file.channels,
                "format_details": job.audio_file.get_format_details()
            }
    
    return TranscriptionJobResponse(
        id=job.id,
        filename=job.filename,
        original_filename=job.original_filename,
        file_size=job.file_size,
        mime_type=job.mime_type,
        usage_type_code=job.usage_type_code,
        status_code=JobStatusEnum(job.status_code),
        progress=job.progress,
        message=job.message,
        error_message=job.error_message,
        processing_started_at=job.processing_started_at,
        processing_completed_at=job.processing_completed_at,
        created_at=job.created_at,
        updated_at=job.updated_at,
        audio_file=audio_info,
        transcription_result=transcription_result
    )


@router.delete("/{job_id}", response_model=BaseResponse)
async def delete_transcription_job(
    job_id: str,
    db: Session = Depends(get_db)
):
    """転写ジョブ削除"""
    
    service = TranscriptionService(db)
    
    # ジョブ存在確認
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="指定されたジョブが見つかりません"
        )
    
    # 関連ファイル削除
    try:
        if hasattr(job, 'audio_file') and job.audio_file:
            file_path = Path(job.audio_file.file_path)
            if file_path.exists():
                file_path.unlink()
                logger.info("Audio file deleted", file_path=str(file_path))
    except Exception as e:
        logger.warning("Failed to delete audio file", 
                      job_id=job_id,
                      error=str(e))
    
    # ジョブ削除
    success = service.delete_job(job_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ジョブの削除に失敗しました"
        )
    
    logger.info("Transcription job deleted", job_id=job_id)
    
    return BaseResponse(
        success=True,
        message="ジョブが正常に削除されました"
    )


@router.get("/{job_id}/summary")
async def get_transcription_summary(
    job_id: str,
    db: Session = Depends(get_db)
):
    """転写ジョブの要約取得"""
    
    # ジョブ存在確認
    transcription_service = TranscriptionService(db)
    job = transcription_service.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="指定されたジョブが見つかりません"
        )
    
    # 要約取得
    summary_service = SummaryService(db)
    summary = summary_service.get_complete_summary(job_id)
    
    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="要約が見つかりません"
        )
    
    return summary


@router.post("/{job_id}/reprocess", response_model=BaseResponse)
async def reprocess_transcription_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """転写ジョブ再処理"""
    
    service = TranscriptionService(db)
    
    # ジョブ存在確認
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="指定されたジョブが見つかりません"
        )
    
    # エラー状態のみ再処理可能
    if job.status_code != "error":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="再処理はエラー状態のジョブのみ可能です"
        )
    
    # ステータス更新
    success = service.update_job_status(
        job_id=job_id,
        status="uploading",
        progress=0,
        message="再処理準備中...",
        error_message=None
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="再処理の開始に失敗しました"
        )
    
    # バックグラウンド処理開始（音声転写・AI要約）
    background_tasks.add_task(process_audio_background, job_id, db)
    
    logger.info("Transcription job reprocessing started", job_id=job_id)
    
    return BaseResponse(
        success=True,
        message="再処理を開始しました"
    )