"""
Whisper音声転写サービス
"""

import asyncio
import time
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
import structlog

try:
    import whisper
    import torch
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    whisper = None
    torch = None

try:
    import librosa
    import soundfile as sf
    AUDIO_PROCESSING_AVAILABLE = True
except ImportError:
    AUDIO_PROCESSING_AVAILABLE = False
    librosa = None
    sf = None

from app.core.config import settings


logger = structlog.get_logger(__name__)


class WhisperError(Exception):
    """Whisper関連エラー"""
    pass


class WhisperService:
    """Whisper音声転写サービス"""
    
    def __init__(self, model_name: str = None, device: str = None):
        if not WHISPER_AVAILABLE:
            raise WhisperError("Whisperライブラリがインストールされていません")
        
        self.model_name = model_name or settings.WHISPER_MODEL
        self.device = device or settings.WHISPER_DEVICE
        self.model = None
        
        logger.info("Whisper service initializing",
                   model=self.model_name,
                   device=self.device)
    
    def _load_model(self) -> None:
        """Whisperモデル読み込み"""
        if self.model is not None:
            return
        
        try:
            logger.info("Loading Whisper model", model=self.model_name)
            start_time = time.time()
            
            self.model = whisper.load_model(
                self.model_name,
                device=self.device
            )
            
            load_time = time.time() - start_time
            logger.info("Whisper model loaded successfully",
                       model=self.model_name,
                       load_time=f"{load_time:.2f}s")
            
        except Exception as e:
            logger.error("Failed to load Whisper model",
                        model=self.model_name,
                        error=str(e))
            raise WhisperError(f"Whisperモデルの読み込みに失敗しました: {e}")
    
    async def transcribe_audio(self, 
                              audio_path: Union[str, Path],
                              language: Optional[str] = None,
                              task: str = "transcribe",
                              progress_callback: Optional[callable] = None) -> Dict[str, Any]:
        """音声ファイル転写"""
        
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise WhisperError(f"音声ファイルが見つかりません: {audio_path}")
        
        # モデル読み込み
        self._load_model()
        
        try:
            logger.info("Starting transcription",
                       file=str(audio_path),
                       language=language,
                       task=task)
            
            start_time = time.time()
            
            # 進行状況コールバック実行（開始時）
            if progress_callback:
                progress_callback(0, "音声ファイル前処理中...")
            
            # 音声ファイル前処理
            preprocessed_path = await self._preprocess_audio(audio_path)
            
            # 進行状況コールバック実行（前処理完了）
            if progress_callback:
                progress_callback(5, "Whisper転写実行中...")
            
            # Whisper転写実行（CPU集約的処理のため別スレッドで実行）
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._transcribe_sync,
                str(preprocessed_path),
                language,
                task,
                progress_callback
            )
            
            # 前処理ファイル削除
            if preprocessed_path != audio_path and preprocessed_path.exists():
                preprocessed_path.unlink()
            
            processing_time = time.time() - start_time
            
            # 進行状況コールバック実行（後処理開始）
            if progress_callback:
                progress_callback(95, "転写結果を処理中...")
            
            # 結果構造化
            transcription_result = {
                "text": result["text"].strip(),
                "language": result.get("language", "ja"),
                "confidence": self._calculate_average_confidence(result),
                "duration_seconds": self._get_audio_duration(audio_path),
                "segments": self._process_segments(result.get("segments", [])),
                "processing_time_seconds": processing_time,
                "model_used": self.model_name,
                "task": task
            }
            
            # 進行状況コールバック実行（完了）
            if progress_callback:
                progress_callback(100, "転写完了")
            
            logger.info("Transcription completed successfully",
                       text_length=len(transcription_result["text"]),
                       segments_count=len(transcription_result["segments"]),
                       processing_time=f"{processing_time:.2f}s",
                       language=transcription_result["language"])
            
            return transcription_result
            
        except Exception as e:
            logger.error("Transcription failed",
                        file=str(audio_path),
                        error=str(e))
            raise WhisperError(f"転写処理に失敗しました: {e}")
    
    def _transcribe_sync(self, audio_path: str, language: Optional[str], task: str, progress_callback: Optional[callable] = None) -> Dict[str, Any]:
        """同期転写処理（スレッドプール用）"""
        options = {
            "task": task,
            "verbose": False
        }
        
        if language:
            options["language"] = language
        
        # 進行状況をモニターするために、Whisperの内部進行状況を監視
        # （注意：Whisperライブラリの内部実装に依存するため、完全な精度は保証されない）
        try:
            if progress_callback:
                # 転写開始時
                progress_callback(10, "Whisper転写実行中...")
            
            result = self.model.transcribe(audio_path, **options)
            
            if progress_callback:
                # 転写完了時
                progress_callback(90, "転写結果を処理中...")
                
            return result
            
        except Exception as e:
            if progress_callback:
                progress_callback(0, f"転写エラー: {str(e)}")
            raise
    
    async def _preprocess_audio(self, audio_path: Path) -> Path:
        """音声ファイル前処理"""
        
        if not AUDIO_PROCESSING_AVAILABLE:
            logger.info("Audio processing libraries not available, using original file")
            return audio_path
        
        try:
            # ファイル拡張子チェック
            if audio_path.suffix.lower() in ['.wav', '.mp3']:
                return audio_path
            
            logger.info("Converting audio format", 
                       original=audio_path.suffix,
                       target=".wav")
            
            # 一時ファイル作成
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                output_path = Path(tmp_file.name)
            
            # 音声読み込み・変換
            loop = asyncio.get_event_loop()
            audio_data, sample_rate = await loop.run_in_executor(
                None,
                librosa.load,
                str(audio_path),
                sr=16000  # Whisper推奨サンプリング率
            )
            
            # WAVファイル保存
            await loop.run_in_executor(
                None,
                sf.write,
                str(output_path),
                audio_data,
                sample_rate
            )
            
            logger.info("Audio conversion completed",
                       input_path=str(audio_path),
                       output_path=str(output_path))
            
            return output_path
            
        except Exception as e:
            logger.warning("Audio preprocessing failed, using original file",
                          error=str(e))
            return audio_path
    
    def _calculate_average_confidence(self, result: Dict[str, Any]) -> float:
        """平均信頼度計算"""
        segments = result.get("segments", [])
        if not segments:
            return 0.95  # デフォルト信頼度
        
        # セグメントごとの平均信頼度を計算
        total_confidence = 0.0
        total_duration = 0.0
        
        for segment in segments:
            if "avg_logprob" in segment:
                # log probabilityを信頼度に変換（概算）
                confidence = max(0.0, min(1.0, (segment["avg_logprob"] + 1.0) / 1.0))
            else:
                confidence = 0.9  # デフォルト
            
            duration = segment.get("end", 0) - segment.get("start", 0)
            total_confidence += confidence * duration
            total_duration += duration
        
        if total_duration > 0:
            return total_confidence / total_duration
        
        return 0.9
    
    def _get_audio_duration(self, audio_path: Path) -> float:
        """音声ファイル長取得"""
        try:
            if AUDIO_PROCESSING_AVAILABLE:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    duration = librosa.get_duration(path=str(audio_path))
                    return duration
                finally:
                    loop.close()
        except Exception as e:
            logger.warning("Failed to get audio duration", error=str(e))
        
        # フォールバック: ファイルサイズから概算
        file_size = audio_path.stat().st_size
        estimated_duration = file_size / (128 * 1024 / 8)  # 128kbps想定
        return max(1.0, estimated_duration)
    
    def _process_segments(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """セグメント情報処理"""
        processed_segments = []
        
        for i, segment in enumerate(segments):
            processed_segment = {
                "segment_index": i,
                "start_time": segment.get("start", 0.0),
                "end_time": segment.get("end", 0.0),
                "text": segment.get("text", "").strip(),
                "confidence": max(0.0, min(1.0, 
                                         (segment.get("avg_logprob", -1.0) + 1.0) / 1.0)),
                "speaker_id": None,  # Whisperは話者識別しないのでNone
                "speaker_name": None
            }
            processed_segments.append(processed_segment)
        
        return processed_segments
    
    def get_available_models(self) -> List[str]:
        """利用可能なWhisperモデル一覧"""
        if not WHISPER_AVAILABLE:
            return []
        
        return [
            "tiny", "tiny.en",
            "base", "base.en", 
            "small", "small.en",
            "medium", "medium.en",
            "large", "large-v1", "large-v2", "large-v3"
        ]
    
    def get_model_info(self) -> Dict[str, Any]:
        """モデル情報取得"""
        return {
            "model_name": self.model_name,
            "device": self.device,
            "available_models": self.get_available_models(),
            "whisper_available": WHISPER_AVAILABLE,
            "audio_processing_available": AUDIO_PROCESSING_AVAILABLE,
            "model_loaded": self.model is not None
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Whisperヘルスチェック"""
        try:
            if not WHISPER_AVAILABLE:
                return {
                    "status": "error",
                    "message": "Whisperライブラリが利用できません"
                }
            
            # モデル読み込みテスト
            try:
                self._load_model()
                model_status = "loaded"
                model_message = "正常に読み込まれています"
            except Exception as e:
                model_status = "error"
                model_message = f"読み込みエラー: {e}"
            
            return {
                "status": "healthy" if model_status == "loaded" else "error",
                "message": f"Whisperサービス状態: {model_message}",
                "model_name": self.model_name,
                "device": self.device,
                "model_status": model_status,
                "audio_processing_available": AUDIO_PROCESSING_AVAILABLE
            }
            
        except Exception as e:
            logger.error("Whisper health check failed", error=str(e))
            return {
                "status": "error",
                "message": f"ヘルスチェックエラー: {e}"
            }


# 便利関数
async def get_whisper_service() -> WhisperService:
    """Whisperサービス取得（依存注入用）"""
    return WhisperService()


def check_whisper_dependencies() -> Dict[str, bool]:
    """Whisper依存関係チェック"""
    return {
        "whisper": WHISPER_AVAILABLE,
        "torch": torch is not None if WHISPER_AVAILABLE else False,
        "librosa": AUDIO_PROCESSING_AVAILABLE,
        "soundfile": sf is not None if AUDIO_PROCESSING_AVAILABLE else False
    }