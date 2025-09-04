"""
AI要約関連サービス層

要約結果のCRUD操作とビジネスロジック
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models import (
    AISummary, MeetingSummary, InterviewSummary, 
    TranscriptionJob
)
from app.core.database import get_session
import structlog

logger = structlog.get_logger(__name__)


class SummaryService:
    """要約サービスクラス"""
    
    def __init__(self, session: Optional[Session] = None):
        self.session = session or get_session()
    
    def create_ai_summary(
        self,
        job_id: str,
        summary_type: str,
        model_used: str,
        confidence: float,
        processing_time_seconds: float,
        raw_response: Dict[str, Any],
        formatted_text: str
    ) -> AISummary:
        """AI要約基底レコード作成"""
        try:
            summary = AISummary(
                job_id=job_id,
                type=summary_type,
                model_used=model_used,
                confidence=confidence,
                processing_time_seconds=processing_time_seconds,
                formatted_text=formatted_text
            )
            
            summary.set_raw_response(raw_response)
            
            self.session.add(summary)
            self.session.commit()
            
            logger.info("AI summary created", 
                       job_id=job_id, 
                       type=summary_type,
                       model=model_used)
            
            return summary
            
        except Exception as e:
            self.session.rollback()
            logger.error("Failed to create AI summary", 
                        job_id=job_id, 
                        error=str(e))
            raise
    
    def create_meeting_summary(
        self,
        job_id: str,
        decisions: List[str],
        action_plans: List[str],
        summary: str,
        next_meeting: Optional[str] = None,
        participants_count: Optional[int] = None,
        meeting_duration_minutes: Optional[int] = None,
        topics_discussed: Optional[List[str]] = None
    ) -> MeetingSummary:
        """会議要約詳細作成"""
        try:
            meeting_summary = MeetingSummary(
                job_id=job_id,
                summary=summary,
                next_meeting=next_meeting,
                participants_count=participants_count,
                meeting_duration_minutes=meeting_duration_minutes
            )
            
            # JSON データ設定
            meeting_summary.set_decisions(decisions)
            meeting_summary.set_action_plans(action_plans)
            
            if topics_discussed:
                meeting_summary.set_topics_discussed(topics_discussed)
            
            self.session.add(meeting_summary)
            self.session.commit()
            
            logger.info("Meeting summary created", 
                       job_id=job_id,
                       decisions_count=len(decisions),
                       action_plans_count=len(action_plans))
            
            return meeting_summary
            
        except Exception as e:
            self.session.rollback()
            logger.error("Failed to create meeting summary", 
                        job_id=job_id, 
                        error=str(e))
            raise
    
    def create_interview_summary(
        self,
        job_id: str,
        evaluation: Dict[str, Any],
        experience: str,
        career_axis: str,
        work_experience: str,
        character_analysis: str,
        next_steps: str,
        interview_duration_minutes: Optional[int] = None,
        position_applied: Optional[str] = None,
        interviewer_notes: Optional[Dict[str, Any]] = None
    ) -> InterviewSummary:
        """面接要約詳細作成"""
        try:
            interview_summary = InterviewSummary(
                job_id=job_id,
                experience=experience,
                career_axis=career_axis,
                work_experience=work_experience,
                character_analysis=character_analysis,
                next_steps=next_steps,
                interview_duration_minutes=interview_duration_minutes,
                position_applied=position_applied
            )
            
            # JSON データ設定
            interview_summary.set_evaluation(evaluation)
            
            if interviewer_notes:
                interview_summary.set_interviewer_notes(interviewer_notes)
            
            self.session.add(interview_summary)
            self.session.commit()
            
            logger.info("Interview summary created", 
                       job_id=job_id,
                       position=position_applied)
            
            return interview_summary
            
        except Exception as e:
            self.session.rollback()
            logger.error("Failed to create interview summary", 
                        job_id=job_id, 
                        error=str(e))
            raise
    
    def get_ai_summary(self, job_id: str) -> Optional[AISummary]:
        """AI要約取得"""
        return self.session.query(AISummary).filter_by(job_id=job_id).first()
    
    def get_meeting_summary(self, job_id: str) -> Optional[MeetingSummary]:
        """会議要約詳細取得"""
        return self.session.query(MeetingSummary).filter_by(job_id=job_id).first()
    
    def get_interview_summary(self, job_id: str) -> Optional[InterviewSummary]:
        """面接要約詳細取得"""
        return self.session.query(InterviewSummary).filter_by(job_id=job_id).first()
    
    def get_complete_summary(self, job_id: str) -> Optional[Dict[str, Any]]:
        """完全な要約データ取得（基底+詳細）"""
        ai_summary = self.get_ai_summary(job_id)
        if not ai_summary:
            return None
        
        result = {
            "job_id": job_id,
            "type": ai_summary.type,
            "model_used": ai_summary.model_used,
            "confidence": ai_summary.confidence,
            "processing_time_seconds": ai_summary.processing_time_seconds,
            "formatted_text": ai_summary.formatted_text,
            "raw_response": ai_summary.get_raw_response(),
            "created_at": ai_summary.created_at,
            "details": None
        }
        
        if ai_summary.type == "meeting":
            meeting_summary = self.get_meeting_summary(job_id)
            if meeting_summary:
                result["details"] = {
                    "summary": meeting_summary.summary,
                    "decisions": meeting_summary.get_decisions(),
                    "action_plans": meeting_summary.get_action_plans(),
                    "next_meeting": meeting_summary.next_meeting,
                    "participants_count": meeting_summary.participants_count,
                    "meeting_duration_minutes": meeting_summary.meeting_duration_minutes,
                    "topics_discussed": meeting_summary.get_topics_discussed()
                }
        
        elif ai_summary.type == "interview":
            interview_summary = self.get_interview_summary(job_id)
            if interview_summary:
                result["details"] = {
                    "evaluation": interview_summary.get_evaluation(),
                    "experience": interview_summary.experience,
                    "career_axis": interview_summary.career_axis,
                    "work_experience": interview_summary.work_experience,
                    "character_analysis": interview_summary.character_analysis,
                    "next_steps": interview_summary.next_steps,
                    "interview_duration_minutes": interview_summary.interview_duration_minutes,
                    "position_applied": interview_summary.position_applied,
                    "interviewer_notes": interview_summary.get_interviewer_notes()
                }
        
        return result
    
    def update_summary_confidence(self, job_id: str, confidence: float) -> bool:
        """要約信頼度更新"""
        try:
            summary = self.get_ai_summary(job_id)
            if not summary:
                return False
            
            old_confidence = summary.confidence
            summary.confidence = confidence
            
            self.session.commit()
            
            logger.info("Summary confidence updated", 
                       job_id=job_id,
                       old_confidence=old_confidence,
                       new_confidence=confidence)
            
            return True
            
        except Exception as e:
            self.session.rollback()
            logger.error("Failed to update summary confidence", 
                        job_id=job_id, 
                        error=str(e))
            return False
    
    def delete_summary(self, job_id: str) -> bool:
        """要約削除（カスケード削除）"""
        try:
            summary = self.get_ai_summary(job_id)
            if not summary:
                return False
            
            self.session.delete(summary)
            self.session.commit()
            
            logger.info("Summary deleted", job_id=job_id)
            return True
            
        except Exception as e:
            self.session.rollback()
            logger.error("Failed to delete summary", job_id=job_id, error=str(e))
            return False
    
    def get_summary_statistics(self) -> Dict[str, Any]:
        """要約統計情報取得"""
        from sqlalchemy import func
        
        # タイプ別集計
        type_stats = self.session.query(
            AISummary.type,
            func.count(AISummary.job_id).label('count'),
            func.avg(AISummary.confidence).label('avg_confidence'),
            func.avg(AISummary.processing_time_seconds).label('avg_processing_time')
        ).group_by(AISummary.type).all()
        
        # モデル別集計
        model_stats = self.session.query(
            AISummary.model_used,
            func.count(AISummary.job_id).label('count')
        ).group_by(AISummary.model_used).all()
        
        return {
            "type_distribution": {
                row.type: {
                    "count": row.count,
                    "average_confidence": float(row.avg_confidence or 0),
                    "average_processing_time": float(row.avg_processing_time or 0)
                }
                for row in type_stats
            },
            "model_distribution": {row.model_used: row.count for row in model_stats},
            "total_summaries": sum(row.count for row in type_stats)
        }
    
    def get_recent_summaries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """最近の要約一覧取得"""
        summaries = self.session.query(AISummary)\
                                .order_by(desc(AISummary.created_at))\
                                .limit(limit)\
                                .all()
        
        result = []
        for summary in summaries:
            # ジョブ情報も含める
            job = self.session.query(TranscriptionJob).filter_by(id=summary.job_id).first()
            
            result.append({
                "job_id": summary.job_id,
                "job_filename": job.original_filename if job else None,
                "job_created_at": job.created_at if job else None,
                "type": summary.type,
                "model_used": summary.model_used,
                "confidence": summary.confidence,
                "processing_time_seconds": summary.processing_time_seconds,
                "text_length": summary.formatted_text_length,
                "created_at": summary.created_at
            })
        
        return result
    
    def export_summary_data(self, job_id: str) -> Dict[str, Any]:
        """要約データエクスポート用形式取得"""
        complete_summary = self.get_complete_summary(job_id)
        if not complete_summary:
            return {}
        
        # ジョブ情報も含める
        job = self.session.query(TranscriptionJob).filter_by(id=job_id).first()
        
        export_data = {
            "metadata": {
                "job_id": job_id,
                "original_filename": job.original_filename if job else None,
                "usage_type": complete_summary["type"],
                "ai_model": complete_summary["model_used"],
                "confidence": complete_summary["confidence"],
                "created_at": complete_summary["created_at"].isoformat(),
                "processing_time_seconds": complete_summary["processing_time_seconds"]
            },
            "summary": complete_summary
        }
        
        return export_data
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.session.rollback()
        self.session.close()