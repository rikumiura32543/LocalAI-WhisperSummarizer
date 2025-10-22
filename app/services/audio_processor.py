"""
音声処理統合サービス
"""

import asyncio
import time
from pathlib import Path
from typing import Dict, Any, Optional
import structlog

from sqlalchemy.orm import Session

from app.services.whisper_service import WhisperService, WhisperError
from app.services.ollama_service import OllamaService, OllamaError
from app.services.transcription_service import TranscriptionService
from app.services.summary_service import SummaryService
from app.core.config import settings


logger = structlog.get_logger(__name__)


class AudioProcessingError(Exception):
    """音声処理エラー"""
    pass


class AudioProcessor:
    """音声処理統合サービス"""
    
    def __init__(self, db: Session):
        self.db = db
        self.transcription_service = TranscriptionService(db)
        self.summary_service = SummaryService(db)
        
        logger.info("Audio processor initialized")
    
    async def process_audio_file(self, job_id: str) -> Dict[str, Any]:
        """音声ファイル完全処理パイプライン（文脈補正機能付き）"""
        
        logger.info("Starting audio processing pipeline", job_id=job_id)
        
        try:
            # ジョブ取得
            job = self.transcription_service.get_job(job_id)
            if not job:
                raise AudioProcessingError("ジョブが見つかりません")
            
            # ステータス更新: 処理開始（transcribingステータスを使用）
            self.transcription_service.update_job_status(
                job_id=job_id,
                status="transcribing",
                progress=10,
                message="音声転写を開始します..."
            )
            
            # 音声ファイルパス取得
            audio_file_info = None
            if hasattr(job, 'audio_file') and job.audio_file:
                audio_file_info = job.audio_file
                audio_path = Path(audio_file_info.file_path)
            else:
                # フォールバック: アップロードディレクトリから推測
                audio_path = Path(settings.UPLOAD_DIR) / f"{job_id}.m4a"
                if not audio_path.exists():
                    # 他の拡張子も試す
                    for ext in settings.ALLOWED_EXTENSIONS:
                        test_path = Path(settings.UPLOAD_DIR) / f"{job_id}.{ext}"
                        if test_path.exists():
                            audio_path = test_path
                            break
            
            if not audio_path.exists():
                raise AudioProcessingError(f"音声ファイルが見つかりません: {audio_path}")
            
            # 1. 音声転写処理
            transcription_result = await self._transcribe_audio(job_id, audio_path)
            original_transcription_text = transcription_result["text"]
            
            # 2. AI文脈補正（新機能）
            self.transcription_service.update_job_status(
                job_id=job_id,
                status="transcribing",
                progress=50,
                message="AI文脈補正を実行中..."
            )
            
            corrected_result = await self._correct_transcription(job_id, transcription_result)
            
            # 3. 書き起こし結果は元のテキストを保存、補正結果は別フィールドで保存
            transcription_result["text"] = original_transcription_text  # 元の書き起こしテキストを保持
            transcription_result["corrected_text"] = corrected_result["corrected_text"]  # 補正後テキストを追加
            transcription_result["corrections_made"] = corrected_result.get("corrections_made", False)
            
            # 4. 転写結果保存（元のテキストを保存）
            await self._save_transcription_result(job_id, transcription_result)
            
            # ステータス更新: 転写完了
            self.transcription_service.update_job_status(
                job_id=job_id,
                status="summarizing",
                progress=70,
                message="AI要約を生成しています..."
            )
            
            # 5. AI要約生成（補正後のテキストを使用）
            # 要約用に補正後テキストを使用
            corrected_transcription_for_summary = transcription_result.copy()
            corrected_transcription_for_summary["text"] = corrected_result["corrected_text"]
            summary_result = await self._generate_summary(job_id, corrected_transcription_for_summary)
            
            # 6. 要約結果保存
            await self._save_summary_result(job_id, summary_result)
            
            # ステータス更新: 完了
            self.transcription_service.update_job_status(
                job_id=job_id,
                status="completed",
                progress=100,
                message="処理が完了しました"
            )
            
            logger.info("Audio processing pipeline completed successfully", 
                       job_id=job_id,
                       corrections_made=corrected_result.get("corrections_made", False))
            
            return {
                "job_id": job_id,
                "status": "completed",
                "transcription": transcription_result,
                "summary": summary_result
            }
            
        except Exception as e:
            logger.error("Audio processing pipeline failed",
                        job_id=job_id,
                        error=str(e))
            
            # エラー状態に更新
            self.transcription_service.update_job_status(
                job_id=job_id,
                status="error",
                progress=0,
                message="処理エラー",
                error_message=str(e)
            )
            
            raise AudioProcessingError(f"音声処理パイプラインエラー: {e}")
    
    async def _transcribe_audio(self, job_id: str, audio_path: Path) -> Dict[str, Any]:
        """音声転写処理"""
        
        logger.info("Starting audio transcription", 
                   job_id=job_id,
                   audio_path=str(audio_path))
        
        try:
            # Whisperサービス初期化
            whisper_service = WhisperService()
            
            # 進行状況コールバック関数を定義
            def progress_callback(progress: int, message: str):
                """進行状況更新コールバック"""
                # 進行状況を10-50の範囲にマッピング（転写フェーズ）
                mapped_progress = 10 + int(progress * 0.4)  # 10% + (0-100% * 40%)
                
                # データベース更新（エラーが発生しても処理を継続）
                try:
                    self.transcription_service.update_job_status(
                        job_id=job_id,
                        status="transcribing",
                        progress=mapped_progress,
                        message=message
                    )
                except Exception as e:
                    logger.warning("Failed to update progress", 
                                 job_id=job_id, 
                                 progress=mapped_progress,
                                 error=str(e))
            
            # 転写実行（進行状況コールバック付き）
            result = await whisper_service.transcribe_audio(
                audio_path=audio_path,
                language="ja",  # 日本語指定
                task="transcribe",
                progress_callback=progress_callback
            )
            
            logger.info("Audio transcription completed",
                       job_id=job_id,
                       text_length=len(result["text"]),
                       segments_count=len(result["segments"]))
            
            return result
            
        except WhisperError as e:
            logger.error("Whisper transcription failed",
                        job_id=job_id,
                        error=str(e))
            raise AudioProcessingError(f"音声転写エラー: {e}")
        except Exception as e:
            logger.error("Unexpected error in transcription",
                        job_id=job_id,
                        error=str(e))
            raise AudioProcessingError(f"予期しない転写エラー: {e}")

    async def _correct_transcription(self, job_id: str, transcription_result: Dict[str, Any]) -> Dict[str, Any]:
        """AI文脈補正処理"""
        
        logger.info("Starting AI transcription correction", 
                   job_id=job_id,
                   text_length=len(transcription_result["text"]))
        
        try:
            # テキストが空の場合はスキップ
            if not transcription_result["text"] or len(transcription_result["text"].strip()) == 0:
                logger.warning("Empty transcription text, skipping correction", job_id=job_id)
                return {
                    "corrected_text": transcription_result["text"],
                    "original_text": transcription_result["text"],
                    "corrections_made": False
                }
            
            # Ollamaサービス初期化
            async with OllamaService() as ollama:
                # AI文脈補正実行
                correction_result = await ollama.correct_transcription(
                    text=transcription_result["text"]
                )
                
                logger.info("AI transcription correction completed",
                           job_id=job_id,
                           original_length=len(transcription_result["text"]),
                           corrected_length=len(correction_result["corrected_text"]),
                           corrections_made=correction_result.get("corrections_made", False))
                
                return correction_result
                
        except Exception as e:
            logger.error("AI transcription correction failed, using original text",
                        job_id=job_id,
                        error=str(e))
            # エラー時は元のテキストを返す
            return {
                "corrected_text": transcription_result["text"],
                "original_text": transcription_result["text"],
                "corrections_made": False,
                "error": str(e)
            }
    
    async def _save_transcription_result(self, job_id: str, result: Dict[str, Any]) -> None:
        """転写結果保存"""
        
        logger.info("Saving transcription result", job_id=job_id)
        
        try:
            # 転写結果保存
            self.transcription_service.save_transcription_result(
                job_id=job_id,
                text=result["text"],
                confidence=result["confidence"],
                language=result["language"],
                duration_seconds=result["duration_seconds"],
                model_used=result["model_used"],
                processing_time_seconds=result["processing_time_seconds"]
            )
            
            # セグメント保存
            segments = result.get("segments", [])
            if segments:
                for segment in segments:
                    self.transcription_service.save_transcription_segment(
                        job_id=job_id,
                        segment_index=segment["segment_index"],
                        start_time=segment["start_time"],
                        end_time=segment["end_time"],
                        text=segment["text"],
                        confidence=segment["confidence"],
                        speaker_id=segment["speaker_id"],
                        speaker_name=segment["speaker_name"]
                    )
            
            logger.info("Transcription result saved successfully",
                       job_id=job_id,
                       segments_count=len(segments))
            
        except Exception as e:
            logger.error("Failed to save transcription result",
                        job_id=job_id,
                        error=str(e))
            raise AudioProcessingError(f"転写結果保存エラー: {e}")
    
    async def _generate_summary(self, job_id: str, transcription_result: Dict[str, Any]) -> Dict[str, Any]:
        """AI要約生成"""
        
        logger.info("Starting AI summarization", job_id=job_id)
        
        try:
            # ジョブ情報取得
            job = self.transcription_service.get_job(job_id)
            usage_type = job.usage_type_code
            
            # Ollamaサービス初期化
            async with OllamaService() as ollama:
                # 要約生成
                summary_result = await ollama.generate_summary(
                    text=transcription_result["text"],
                    summary_type=usage_type,
                    max_tokens=1000
                )
                
                logger.info("AI summarization completed",
                           job_id=job_id,
                           summary_type=usage_type,
                           summary_length=len(summary_result["text"]))
                
                return summary_result
                
        except OllamaError as e:
            logger.error("Ollama summarization failed",
                        job_id=job_id,
                        error=str(e))
            raise AudioProcessingError(f"AI要約エラー: {e}")
        except Exception as e:
            logger.error("Unexpected error in summarization",
                        job_id=job_id,
                        error=str(e))
            raise AudioProcessingError(f"予期しない要約エラー: {e}")
    
    async def _save_summary_result(self, job_id: str, result: Dict[str, Any]) -> None:
        """要約結果保存"""
        
        logger.info("Saving summary result", job_id=job_id)
        
        try:
            # ジョブ情報取得
            job = self.transcription_service.get_job(job_id)
            usage_type = job.usage_type_code
            
            # AI要約基底レコード作成
            ai_summary = self.summary_service.create_ai_summary(
                job_id=job_id,
                summary_type=usage_type,
                model_used=result["model_used"],
                confidence=result["confidence"],
                processing_time_seconds=result.get("processing_time", 0.0),
                raw_response=result,
                formatted_text=result["formatted_text"]
            )
            
            # 詳細情報の保存（用途別）
            details = result.get("details", {})
            
            if usage_type == "meeting" and details:
                # 会議要約詳細作成
                self.summary_service.create_meeting_summary(
                    job_id=job_id,
                    decisions=details.get("decisions", []),
                    action_plans=details.get("action_plans", []),
                    summary=details.get("summary", result["text"]),
                    next_meeting=details.get("next_meeting"),
                    participants_count=details.get("participants_count"),
                    meeting_duration_minutes=details.get("meeting_duration_minutes"),
                    topics_discussed=details.get("topics_discussed", [])
                )
            elif usage_type == "interview" and details:
                # 面接要約詳細作成
                self.summary_service.create_interview_summary(
                    job_id=job_id,
                    evaluation=details.get("evaluation", {}),
                    experience=details.get("experience", ""),
                    career_axis=details.get("career_axis", ""),
                    work_experience=details.get("work_experience", ""),
                    character_analysis=details.get("character_analysis", ""),
                    next_steps=details.get("next_steps", ""),
                    interview_duration_minutes=details.get("interview_duration_minutes"),
                    position_applied=details.get("position_applied"),
                    interviewer_notes=details.get("interviewer_notes", {})
                )
            
            logger.info("Summary result saved successfully", job_id=job_id)
            
        except Exception as e:
            logger.error("Failed to save summary result",
                        job_id=job_id,
                        error=str(e))
            raise AudioProcessingError(f"要約結果保存エラー: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """音声処理サービス全体のヘルスチェック"""
        
        logger.info("Performing audio processor health check")
        
        health_status = {
            "overall_status": "healthy",
            "services": {}
        }
        
        try:
            # Whisperヘルスチェック
            whisper_service = WhisperService()
            whisper_health = await whisper_service.health_check()
            health_status["services"]["whisper"] = whisper_health
            
            # Ollamaヘルスチェック
            async with OllamaService() as ollama:
                ollama_health = await ollama.health_check()
                health_status["services"]["ollama"] = ollama_health
            
            # 全体ステータス判定
            service_statuses = [
                health_status["services"]["whisper"]["status"],
                health_status["services"]["ollama"]["status"]
            ]
            
            if "error" in service_statuses:
                health_status["overall_status"] = "error"
            elif "warning" in service_statuses:
                health_status["overall_status"] = "warning"
            
            logger.info("Audio processor health check completed",
                       overall_status=health_status["overall_status"])
            
            return health_status
            
        except Exception as e:
            logger.error("Audio processor health check failed", error=str(e))
            return {
                "overall_status": "error",
                "message": f"ヘルスチェックエラー: {e}",
                "services": health_status.get("services", {})
            }


# バックグラウンド処理用関数
async def process_audio_background(job_id: str, db: Session) -> None:
    """バックグラウンド音声処理"""
    
    logger.info("Starting background audio processing", job_id=job_id)
    
    try:
        processor = AudioProcessor(db)
        await processor.process_audio_file(job_id)
        
        logger.info("Background audio processing completed", job_id=job_id)
        
    except Exception as e:
        logger.error("Background audio processing failed",
                    job_id=job_id,
                    error=str(e))


# 便利関数
async def get_audio_processor(db: Session) -> AudioProcessor:
    """音声処理サービス取得（依存注入用）"""
    return AudioProcessor(db)