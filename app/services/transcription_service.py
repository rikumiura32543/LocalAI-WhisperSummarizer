"""
転写関連サービス層

転写ジョブのCRUD操作とビジネスロジック
"""

import uuid
import hashlib
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_

from app.models import (
    TranscriptionJob, AudioFile, TranscriptionResult, 
    TranscriptionSegment, ProcessingLog
)
from app.core.database import get_session, database_transaction
import structlog

logger = structlog.get_logger(__name__)


class TranscriptionService:
    """転写サービスクラス"""
    
    def __init__(self, session: Optional[Session] = None):
        self.session = session or get_session()
    
    def create_job(
        self,
        original_filename: str,
        file_content: bytes,
        usage_type_code: str,
        mime_type: str = "audio/m4a"
    ) -> TranscriptionJob:
        """転写ジョブ作成"""
        try:
            # ファイルハッシュ計算
            file_hash = hashlib.sha256(file_content).hexdigest()
            
            # 一意ファイル名生成
            job_id = str(uuid.uuid4())
            file_extension = original_filename.split('.')[-1] if '.' in original_filename else 'm4a'
            filename = f"{job_id}.{file_extension}"
            
            # ジョブ作成
            job = TranscriptionJob(
                id=job_id,
                filename=filename,
                original_filename=original_filename,
                file_size=len(file_content),
                file_hash=file_hash,
                mime_type=mime_type,
                usage_type_code=usage_type_code,
                status_code="uploading",
                progress=0,
                message="ファイルアップロード完了"
            )
            
            self.session.add(job)
            self.session.commit()
            
            # ログ記録
            self._create_log(job.id, "INFO", f"転写ジョブ作成: {original_filename}")
            
            logger.info("Transcription job created", 
                       job_id=job.id, 
                       filename=original_filename,
                       file_size=len(file_content))
            
            return job
            
        except Exception as e:
            self.session.rollback()
            logger.error("Failed to create transcription job", 
                        filename=original_filename, 
                        error=str(e))
            raise
    
    def get_job(self, job_id: str) -> Optional[TranscriptionJob]:
        """ジョブ取得"""
        return self.session.query(TranscriptionJob).filter_by(id=job_id).first()
    
    def get_jobs(
        self, 
        usage_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[TranscriptionJob]:
        """ジョブ一覧取得"""
        query = self.session.query(TranscriptionJob)
        
        if usage_type:
            query = query.filter(TranscriptionJob.usage_type_code == usage_type)
        
        if status:
            query = query.filter(TranscriptionJob.status_code == status)
        
        return query.order_by(desc(TranscriptionJob.created_at))\
                   .offset(offset)\
                   .limit(limit)\
                   .all()
    
    def update_job_status(
        self, 
        job_id: str, 
        status: str, 
        progress: int = None,
        message: str = None,
        error_message: str = None
    ) -> bool:
        """ジョブステータス更新"""
        try:
            job = self.get_job(job_id)
            if not job:
                return False
            
            # ステータス更新
            old_status = job.status_code
            job.status_code = status
            
            if progress is not None:
                job.progress = progress
            
            if message:
                job.message = message
            
            if error_message:
                job.error_message = error_message
            
            # 処理開始時刻設定
            if status in ("transcribing", "summarizing") and not job.processing_started_at:
                job.processing_started_at = datetime.utcnow()
            
            # 処理完了時刻設定
            if status in ("completed", "error"):
                job.processing_completed_at = datetime.utcnow()
            
            self.session.commit()
            
            # ログ記録
            self._create_log(job_id, "INFO", f"ステータス更新: {old_status} -> {status}")
            
            logger.info("Job status updated", 
                       job_id=job_id, 
                       old_status=old_status, 
                       new_status=status,
                       progress=progress)
            
            return True
            
        except Exception as e:
            self.session.rollback()
            logger.error("Failed to update job status", 
                        job_id=job_id, 
                        status=status, 
                        error=str(e))
            return False
    
    def save_audio_info(
        self, 
        job_id: str, 
        file_path: str,
        duration_seconds: float,
        bitrate: int = None,
        sample_rate: int = None,
        channels: int = None,
        format_details: Dict[str, Any] = None
    ) -> bool:
        """音声ファイル情報保存"""
        try:
            audio_file = AudioFile(
                job_id=job_id,
                file_path=file_path,
                duration_seconds=duration_seconds,
                bitrate=bitrate,
                sample_rate=sample_rate,
                channels=channels
            )
            
            if format_details:
                audio_file.set_format_details(format_details)
            
            self.session.add(audio_file)
            self.session.commit()
            
            logger.info("Audio info saved", 
                       job_id=job_id, 
                       duration=duration_seconds)
            
            return True
            
        except Exception as e:
            self.session.rollback()
            logger.error("Failed to save audio info", 
                        job_id=job_id, 
                        error=str(e))
            return False
    
    def save_transcription_result(
        self,
        job_id: str,
        text: str,
        confidence: float,
        language: str,
        duration_seconds: float,
        model_used: str,
        processing_time_seconds: float,
        segments: List[Dict[str, Any]] = None
    ) -> bool:
        """転写結果保存"""
        try:
            # 転写結果保存
            result = TranscriptionResult(
                job_id=job_id,
                text=text,
                confidence=confidence,
                language=language,
                duration_seconds=duration_seconds,
                model_used=model_used,
                processing_time_seconds=processing_time_seconds,
                segments_count=len(segments) if segments else 0
            )
            
            self.session.add(result)
            
            # セグメント保存
            if segments:
                for i, segment in enumerate(segments):
                    segment_obj = TranscriptionSegment(
                        job_id=job_id,
                        segment_index=i,
                        start_time=segment.get('start', 0),
                        end_time=segment.get('end', 0),
                        text=segment.get('text', ''),
                        confidence=segment.get('confidence', 0.0),
                        speaker_id=segment.get('speaker_id'),
                        speaker_name=segment.get('speaker_name')
                    )
                    self.session.add(segment_obj)
            
            self.session.commit()
            
            self._create_log(job_id, "INFO", f"転写結果保存完了: {len(text)}文字")
            
            logger.info("Transcription result saved", 
                       job_id=job_id, 
                       text_length=len(text),
                       segments_count=len(segments) if segments else 0)
            
            return True
            
        except Exception as e:
            self.session.rollback()
            logger.error("Failed to save transcription result", 
                        job_id=job_id, 
                        error=str(e))
            return False

    def save_transcription_segment(
        self, 
        job_id: str,
        segment_index: int,
        start_time: float,
        end_time: float,
        text: str,
        confidence: float,
        speaker_id: str = None,
        speaker_name: str = None
    ) -> Optional[TranscriptionSegment]:
        """転写セグメントを保存"""
        try:
            segment = TranscriptionSegment(
                job_id=job_id,
                segment_index=segment_index,
                start_time=start_time,
                end_time=end_time,
                text=text,
                confidence=confidence,
                speaker_id=speaker_id,
                speaker_name=speaker_name
            )
            
            self.session.add(segment)
            self.session.commit()
            
            logger.info("Transcription segment saved",
                       job_id=job_id,
                       segment_index=segment_index,
                       start_time=start_time,
                       end_time=end_time)
            
            return segment
            
        except Exception as e:
            self.session.rollback()
            logger.error("Failed to save transcription segment",
                        job_id=job_id,
                        segment_index=segment_index,
                        error=str(e))
            raise
    
    def get_transcription_result(self, job_id: str) -> Optional[TranscriptionResult]:
        """転写結果取得"""
        return self.session.query(TranscriptionResult).filter_by(job_id=job_id).first()
    
    def get_transcription_segments(self, job_id: str) -> List[TranscriptionSegment]:
        """転写セグメント取得"""
        return self.session.query(TranscriptionSegment)\
                          .filter_by(job_id=job_id)\
                          .order_by(TranscriptionSegment.segment_index)\
                          .all()
    
    def delete_job(self, job_id: str) -> bool:
        """ジョブ削除（カスケード削除）"""
        try:
            job = self.get_job(job_id)
            if not job:
                return False
            
            self.session.delete(job)
            self.session.commit()
            
            logger.info("Transcription job deleted", job_id=job_id)
            return True
            
        except Exception as e:
            self.session.rollback()
            logger.error("Failed to delete job", job_id=job_id, error=str(e))
            return False
    
    def get_job_statistics(self) -> Dict[str, Any]:
        """ジョブ統計情報取得"""
        from sqlalchemy import func
        
        # ステータス別集計
        status_stats = self.session.query(
            TranscriptionJob.status_code,
            func.count(TranscriptionJob.id).label('count')
        ).group_by(TranscriptionJob.status_code).all()
        
        # 使用用途別集計
        usage_stats = self.session.query(
            TranscriptionJob.usage_type_code,
            func.count(TranscriptionJob.id).label('count')
        ).group_by(TranscriptionJob.usage_type_code).all()
        
        # 総ファイルサイズ
        total_size = self.session.query(
            func.sum(TranscriptionJob.file_size)
        ).scalar() or 0
        
        # 平均処理時間（完了ジョブのみ）
        avg_processing_time = self.session.query(
            func.avg(
                func.julianday(TranscriptionJob.processing_completed_at) - 
                func.julianday(TranscriptionJob.processing_started_at)
            ) * 24 * 60 * 60  # 秒に変換
        ).filter(
            and_(
                TranscriptionJob.status_code == 'completed',
                TranscriptionJob.processing_started_at.isnot(None),
                TranscriptionJob.processing_completed_at.isnot(None)
            )
        ).scalar()
        
        return {
            "status_distribution": {row.status_code: row.count for row in status_stats},
            "usage_distribution": {row.usage_type_code: row.count for row in usage_stats},
            "total_file_size_bytes": total_size,
            "average_processing_time_seconds": avg_processing_time,
            "total_jobs": sum(row.count for row in status_stats)
        }
    
    def cleanup_expired_jobs(self, days: int = 7) -> int:
        """期限切れジョブクリーンアップ"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            expired_jobs = self.session.query(TranscriptionJob)\
                                     .filter(TranscriptionJob.created_at < cutoff_date)\
                                     .filter(TranscriptionJob.status_code.in_(['completed', 'error']))\
                                     .all()
            
            count = len(expired_jobs)
            
            for job in expired_jobs:
                self.session.delete(job)
            
            self.session.commit()
            
            logger.info("Expired jobs cleaned up", count=count, cutoff_days=days)
            return count
            
        except Exception as e:
            self.session.rollback()
            logger.error("Failed to cleanup expired jobs", error=str(e))
            return 0
    
    def _create_log(self, job_id: str, level: str, message: str, details: Dict[str, Any] = None):
        """処理ログ作成"""
        try:
            log_entry = ProcessingLog.create_log(job_id, level, message, details)
            self.session.add(log_entry)
            self.session.commit()
        except Exception as e:
            logger.warning("Failed to create processing log", 
                          job_id=job_id, 
                          level=level, 
                          message=message,
                          error=str(e))
    
    def get_job_logs(self, job_id: str, limit: int = 100) -> List[ProcessingLog]:
        """ジョブログ取得"""
        return self.session.query(ProcessingLog)\
                          .filter_by(job_id=job_id)\
                          .order_by(desc(ProcessingLog.timestamp))\
                          .limit(limit)\
                          .all()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.session.rollback()
        self.session.close()