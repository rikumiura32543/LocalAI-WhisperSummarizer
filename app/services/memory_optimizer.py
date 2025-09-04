"""
メモリ最適化サービス
"""

import gc
import psutil
import os
import threading
from typing import Dict, Any, Optional, Callable
from contextlib import contextmanager
from functools import wraps
import structlog

logger = structlog.get_logger(__name__)


class MemoryMonitor:
    """メモリ使用量監視"""
    
    def __init__(self):
        self.process = psutil.Process(os.getpid())
        self._monitoring = False
        self._monitor_thread = None
        self._callbacks = []
    
    def get_memory_info(self) -> Dict[str, Any]:
        """メモリ使用量情報取得"""
        try:
            memory_info = self.process.memory_info()
            memory_percent = self.process.memory_percent()
            
            return {
                "rss_mb": memory_info.rss / 1024 / 1024,  # Resident Set Size
                "vms_mb": memory_info.vms / 1024 / 1024,  # Virtual Memory Size  
                "percent": memory_percent,
                "available_mb": psutil.virtual_memory().available / 1024 / 1024,
                "total_mb": psutil.virtual_memory().total / 1024 / 1024,
            }
        except Exception as e:
            logger.error("Failed to get memory info", error=str(e))
            return {}
    
    def add_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """メモリ情報コールバック追加"""
        self._callbacks.append(callback)
    
    def start_monitoring(self, interval: float = 5.0):
        """メモリ監視開始"""
        if self._monitoring:
            return
        
        self._monitoring = True
        
        def monitor():
            while self._monitoring:
                memory_info = self.get_memory_info()
                if memory_info:
                    for callback in self._callbacks:
                        try:
                            callback(memory_info)
                        except Exception as e:
                            logger.error("Memory callback failed", error=str(e))
                
                threading.Event().wait(interval)
        
        self._monitor_thread = threading.Thread(target=monitor, daemon=True)
        self._monitor_thread.start()
        
        logger.info("Memory monitoring started", interval=interval)
    
    def stop_monitoring(self):
        """メモリ監視停止"""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1.0)
        logger.info("Memory monitoring stopped")


class MemoryOptimizer:
    """メモリ最適化サービス"""
    
    def __init__(self, memory_limit_mb: int = 6000):  # Google Cloud E2の80%
        self.memory_limit_mb = memory_limit_mb
        self.monitor = MemoryMonitor()
        self.monitor.add_callback(self._memory_callback)
        
    def _memory_callback(self, memory_info: Dict[str, Any]):
        """メモリ監視コールバック"""
        rss_mb = memory_info.get("rss_mb", 0)
        percent = memory_info.get("percent", 0)
        
        if rss_mb > self.memory_limit_mb:
            logger.warning(
                "Memory limit exceeded",
                rss_mb=rss_mb,
                limit_mb=self.memory_limit_mb,
                percent=percent
            )
            self.force_gc()
        
        if percent > 90:
            logger.error(
                "Critical memory usage",
                percent=percent,
                rss_mb=rss_mb
            )
    
    def force_gc(self):
        """強制ガベージコレクション"""
        logger.info("Performing forced garbage collection")
        
        # 3世代のガベージコレクションを実行
        collected = []
        for generation in range(3):
            count = gc.collect(generation)
            collected.append(count)
        
        logger.info("Garbage collection completed", collected_objects=collected)
        
        # メモリ情報をログ出力
        memory_info = self.monitor.get_memory_info()
        if memory_info:
            logger.info("Memory usage after GC", **memory_info)
    
    def start_monitoring(self):
        """監視開始"""
        self.monitor.start_monitoring()
    
    def stop_monitoring(self):
        """監視停止"""
        self.monitor.stop_monitoring()


# グローバルメモリ最適化サービス
memory_optimizer = MemoryOptimizer()


@contextmanager
def memory_limit_context(limit_mb: int):
    """メモリ制限コンテキスト"""
    monitor = MemoryMonitor()
    initial_memory = monitor.get_memory_info()
    
    logger.info("Entering memory limit context", 
               limit_mb=limit_mb,
               initial_rss_mb=initial_memory.get("rss_mb", 0))
    
    try:
        yield monitor
    finally:
        final_memory = monitor.get_memory_info()
        memory_used = final_memory.get("rss_mb", 0) - initial_memory.get("rss_mb", 0)
        
        logger.info("Exiting memory limit context",
                   memory_used_mb=memory_used,
                   final_rss_mb=final_memory.get("rss_mb", 0))
        
        if final_memory.get("rss_mb", 0) > limit_mb:
            logger.warning("Memory limit exceeded in context")
            gc.collect()


def memory_efficient(func):
    """メモリ効率デコレータ"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        monitor = MemoryMonitor()
        initial_memory = monitor.get_memory_info()
        
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            final_memory = monitor.get_memory_info()
            memory_used = final_memory.get("rss_mb", 0) - initial_memory.get("rss_mb", 0)
            
            if memory_used > 100:  # 100MB以上使用した場合
                logger.info("High memory usage detected",
                           function=func.__name__,
                           memory_used_mb=memory_used)
                gc.collect()
    
    return wrapper


class ChunkedFileProcessor:
    """チャンク単位ファイル処理"""
    
    def __init__(self, chunk_size: int = 1024 * 1024):  # 1MB chunks
        self.chunk_size = chunk_size
    
    def process_file_in_chunks(self, file_path: str, processor_func: Callable[[bytes], None]):
        """ファイルをチャンク単位で処理"""
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(self.chunk_size)
                if not chunk:
                    break
                
                processor_func(chunk)
                
                # 定期的にガベージコレクション
                if f.tell() % (self.chunk_size * 10) == 0:
                    gc.collect()


class MemoryEfficientAudioProcessor:
    """メモリ効率的な音声処理"""
    
    def __init__(self):
        self.chunk_processor = ChunkedFileProcessor()
    
    @memory_efficient
    def load_audio_efficiently(self, file_path: str) -> Optional[Any]:
        """メモリ効率的な音声読み込み"""
        try:
            import librosa
            import numpy as np
            
            # メモリ使用量を制限するため、長い音声は分割処理
            with memory_limit_context(2000):  # 2GB limit
                # まず音声の長さを取得
                duration = librosa.get_duration(filename=file_path)
                
                if duration > 1800:  # 30分以上の場合は分割処理
                    logger.info("Long audio detected, using chunked processing",
                               duration=duration,
                               file_path=file_path)
                    return self._process_long_audio_in_chunks(file_path, duration)
                else:
                    # 通常の読み込み
                    audio, sr = librosa.load(file_path, sr=16000, mono=True)
                    logger.info("Audio loaded efficiently",
                               duration=duration,
                               sample_rate=sr,
                               shape=audio.shape)
                    return audio, sr
        
        except Exception as e:
            logger.error("Failed to load audio efficiently", error=str(e))
            return None
    
    def _process_long_audio_in_chunks(self, file_path: str, duration: float) -> Optional[Any]:
        """長時間音声の分割処理"""
        import librosa
        import numpy as np
        
        chunk_duration = 300  # 5分ずつ処理
        num_chunks = int(np.ceil(duration / chunk_duration))
        
        processed_chunks = []
        
        for i in range(num_chunks):
            start_time = i * chunk_duration
            
            try:
                # チャンク読み込み
                audio_chunk, sr = librosa.load(
                    file_path,
                    sr=16000,
                    mono=True,
                    offset=start_time,
                    duration=chunk_duration
                )
                
                processed_chunks.append(audio_chunk)
                
                logger.info("Processed audio chunk",
                           chunk=i+1,
                           total_chunks=num_chunks,
                           start_time=start_time,
                           chunk_duration=len(audio_chunk)/sr)
                
                # メモリクリーンアップ
                if i % 3 == 0:  # 3チャンクごと
                    gc.collect()
                    
            except Exception as e:
                logger.error("Failed to process audio chunk", 
                           chunk=i,
                           error=str(e))
                continue
        
        if processed_chunks:
            # チャンクを結合
            full_audio = np.concatenate(processed_chunks)
            del processed_chunks  # メモリ解放
            gc.collect()
            
            return full_audio, 16000
        
        return None
    
    @memory_efficient
    def prepare_for_transcription(self, audio_data, sample_rate: int = 16000) -> Optional[Any]:
        """転写用音声データ準備"""
        try:
            import numpy as np
            
            # 音声データの正規化（メモリ効率を重視）
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32)
            
            # 振幅正規化
            max_val = np.max(np.abs(audio_data))
            if max_val > 0:
                audio_data = audio_data / max_val
            
            # 無音部分のトリミング（メモリ節約）
            from librosa import effects
            audio_trimmed, _ = effects.trim(audio_data, top_db=30)
            
            logger.info("Audio prepared for transcription",
                       original_length=len(audio_data),
                       trimmed_length=len(audio_trimmed),
                       memory_saved_mb=(len(audio_data) - len(audio_trimmed)) * 4 / 1024 / 1024)
            
            return audio_trimmed
            
        except Exception as e:
            logger.error("Failed to prepare audio for transcription", error=str(e))
            return audio_data  # 失敗時は元のデータを返す


# グローバルインスタンス
memory_efficient_audio_processor = MemoryEfficientAudioProcessor()