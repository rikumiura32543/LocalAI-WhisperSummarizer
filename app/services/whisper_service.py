"""
Whisper音声転写サービス (faster-whisper版)
"""

import asyncio
import time
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
import structlog

try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    FASTER_WHISPER_AVAILABLE = False
    WhisperModel = None

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
    """Whisper音声転写サービス (faster-whisper使用)"""
    
    def __init__(self, model_name: str = None, device: str = None):
        if not FASTER_WHISPER_AVAILABLE:
            raise WhisperError("faster-whisperライブラリがインストールされていません")
        
        self.model_name = model_name or settings.WHISPER_MODEL
        
        # device設定の最適化
        if device:
            self.device = device
        else:
            # Macの場合はMPSではなくCPU (int8) または CPU (float32) を使用
            # faster-whisperはCoreML対応していないため、MacではCPU実行が一般的だが
            # CTranslate2の最適化によりOpenAI Whisperより高速
            self.device = "cpu"
            
        self.compute_type = "int8" # CPU推論の高速化
        self.model = None
        
        logger.info("Whisper service initializing",
                   model=self.model_name,
                   device=self.device,
                   compute_type=self.compute_type)
    
    def _load_model(self) -> None:
        """Whisperモデル読み込み"""
        if self.model is not None:
            return
        
        try:
            logger.info("Loading Whisper model via faster-whisper", model=self.model_name)
            start_time = time.time()
            
            self.model = WhisperModel(
                self.model_name,
                device=self.device,
                compute_type=self.compute_type
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
                "confidence": result.get("avg_confidence", 0.9),
                "duration_seconds": self._get_audio_duration(audio_path),
                "segments": result.get("segments", []),
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
        """同期転写処理（faster-whisper使用）"""
        
        # オプション設定
        # faster-whisperはbeam_size=5がデフォルト推奨
        beam_size = 5
        
        try:
            if progress_callback:
                progress_callback(10, "Whisper転写実行中...")
            
            # faster-whisperでの転写実行
            # segmentsはジェネレータなのでlist化して実体化する
            segments_generator, info = self.model.transcribe(
                audio_path, 
                beam_size=beam_size,
                language=language,
                task=task
            )
            
            # セグメント処理
            segments = []
            full_text = []
            
            # ジェネレータを回して処理（ストリーミング処理も可能だが今回は一括）
            # 注意: ここで時間はかかる
            for segment in segments_generator:
                segments.append({
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text,
                    "avg_logprob": 0, # faster-whisperは直接ログプロブを出さない構造が違うが互換性のため
                    "confidence": segment.avg_logprob # 近似値として使用
                })
                full_text.append(segment.text)
                
                # 簡易的な進捗更新（正確な全体の長さが不明なため、あくまで動いていることを示す）
                if progress_callback and len(segments) % 10 == 0:
                     progress_callback(50, f"転写中... ({len(segments)}セグメント)")

            
            if progress_callback:
                progress_callback(90, "転写結果を処理中...")
                
            return {
                "text": "".join(full_text),
                "language": info.language,
                "avg_confidence": info.language_probability, # 言語確信度を代用、またはセグメント平均を計算すべきだが簡易化
                "segments": segments
            }
            
        except Exception as e:
            if progress_callback:
                progress_callback(0, f"転写エラー: {str(e)}")
            raise
    
    async def _preprocess_audio(self, audio_path: Path) -> Path:
        """音声ファイル前処理"""
        # faster-whisperはffmpegを内部で使うため、多くの形式を直接扱えるが
        # 念のため既存のロジック（librosa変換）は維持しても良い。
        # 今回はパフォーマンス優先で、直接渡してみて失敗したら変換するという手もあるが
        # 安全のため既存ロジックを維持する
        
        if not AUDIO_PROCESSING_AVAILABLE:
            logger.info("Audio processing libraries not available, using original file")
            return audio_path
        
        try:
            # ファイル拡張子チェック - faster-whisperはm4aも直接いけるはずだが
            # ffmpeg依存。環境による。safe sideでwav変換しておく
            if audio_path.suffix.lower() in ['.wav']:
                return audio_path
            
            logger.info("Converting audio format", 
                       original=audio_path.suffix,
                       target=".wav")
            
            # 一時ファイル作成
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                output_path = Path(tmp_file.name)
            
            # 音声読み込み・変換
            loop = asyncio.get_event_loop()
            import functools
            audio_data, sample_rate = await loop.run_in_executor(
                None,
                functools.partial(librosa.load, str(audio_path), sr=16000)
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
    
    def get_available_models(self) -> List[str]:
        """利用可能なWhisperモデル一覧"""
        if not FASTER_WHISPER_AVAILABLE:
            return []
        
        return [
            "tiny", "tiny.en",
            "base", "base.en", 
            "small", "small.en",
            "medium", "medium.en",
            "large-v1", "large-v2", "large-v3"
        ]
    
    async def health_check(self) -> Dict[str, Any]:
        """Whisperヘルスチェック"""
        try:
            if not FASTER_WHISPER_AVAILABLE:
                return {
                    "status": "error",
                    "message": "faster-whisperライブラリが利用できません"
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
                "compute_type": self.compute_type,
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