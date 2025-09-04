"""
ファイル検証サービス
"""

import magic
import hashlib
import tempfile
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import structlog
import subprocess
from dataclasses import dataclass

logger = structlog.get_logger(__name__)


@dataclass
class FileValidationResult:
    """ファイル検証結果"""
    is_valid: bool
    file_type: str
    mime_type: str
    file_size: int
    sha256_hash: str
    duration: Optional[float] = None
    codec: Optional[str] = None
    bitrate: Optional[int] = None
    sample_rate: Optional[int] = None
    channels: Optional[int] = None
    errors: List[str] = None
    warnings: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []


class FileValidationService:
    """ファイル検証サービス"""
    
    # サポートされるファイル形式とMIMEタイプ
    SUPPORTED_FORMATS = {
        "audio/m4a": [".m4a"],
        "audio/x-m4a": [".m4a"],  # Safari等が送信するM4A
        "audio/mp4": [".mp4", ".m4a"],
        "audio/mpeg": [".mp3"],
        "audio/mp3": [".mp3"],
        "audio/wav": [".wav"],
        "audio/x-wav": [".wav"],
        "audio/wave": [".wav"],
    }
    
    # 危険なファイルシグネチャ
    DANGEROUS_SIGNATURES = {
        b"\\x4D\\x5A": "executable",  # MZ (Windows PE)
        b"\\x7F\\x45\\x4C\\x46": "elf",  # ELF
        b"\\xCA\\xFE\\xBA\\xBE": "mach-o",  # Mach-O
        b"\\x50\\x4B\\x03\\x04": "zip",  # ZIP/JAR
        b"\\x52\\x61\\x72\\x21": "rar",  # RAR
        b"\\x1F\\x8B\\x08": "gzip",  # GZIP
    }
    
    def __init__(self, max_file_size: int = 50 * 1024 * 1024):  # 50MB
        self.max_file_size = max_file_size
        
        # libmagicの初期化
        try:
            self.magic_mime = magic.Magic(mime=True)
            self.magic_type = magic.Magic()
        except Exception as e:
            logger.error("Failed to initialize libmagic", error=str(e))
            raise
    
    def validate_file(self, file_path: Path) -> FileValidationResult:
        """ファイル総合検証"""
        try:
            # ファイル存在確認
            if not file_path.exists():
                return FileValidationResult(
                    is_valid=False,
                    file_type="unknown",
                    mime_type="unknown",
                    file_size=0,
                    sha256_hash="",
                    errors=["ファイルが存在しません"]
                )
            
            # ファイルサイズチェック
            file_size = file_path.stat().st_size
            if file_size > self.max_file_size:
                return FileValidationResult(
                    is_valid=False,
                    file_type="unknown",
                    mime_type="unknown",
                    file_size=file_size,
                    sha256_hash="",
                    errors=[f"ファイルサイズが制限を超えています ({file_size} > {self.max_file_size})"]
                )
            
            if file_size == 0:
                return FileValidationResult(
                    is_valid=False,
                    file_type="unknown",
                    mime_type="unknown",
                    file_size=0,
                    sha256_hash="",
                    errors=["空ファイルです"]
                )
            
            # ファイルハッシュ計算
            sha256_hash = self._calculate_sha256(file_path)
            
            # MIMEタイプとファイルタイプ検出
            mime_type, file_type = self._detect_file_type(file_path)
            
            # 結果初期化
            result = FileValidationResult(
                is_valid=True,
                file_type=file_type,
                mime_type=mime_type,
                file_size=file_size,
                sha256_hash=sha256_hash
            )
            
            # 危険なファイルシグネチャチェック
            if self._has_dangerous_signature(file_path):
                result.is_valid = False
                result.errors.append("危険なファイルシグネチャが検出されました")
                return result
            
            # ファイル拡張子とMIMEタイプの整合性チェック
            if not self._validate_extension_mime_consistency(file_path, mime_type):
                result.warnings.append("ファイル拡張子とMIMEタイプが一致しません")
            
            # サポート形式チェック
            if not self._is_supported_format(mime_type):
                result.is_valid = False
                result.errors.append(f"サポートされていないファイル形式: {mime_type}")
                return result
            
            # 音声メタデータ解析
            audio_info = self._analyze_audio_metadata(file_path)
            if audio_info:
                result.duration = audio_info.get("duration")
                result.codec = audio_info.get("codec")
                result.bitrate = audio_info.get("bitrate")
                result.sample_rate = audio_info.get("sample_rate")
                result.channels = audio_info.get("channels")
                
                # 音声品質チェック
                quality_warnings = self._check_audio_quality(audio_info)
                result.warnings.extend(quality_warnings)
            else:
                result.warnings.append("音声メタデータの解析に失敗しました")
            
            # ファイル破損チェック
            if not self._verify_file_integrity(file_path, mime_type):
                result.is_valid = False
                result.errors.append("ファイルが破損している可能性があります")
            
            logger.info(
                "File validation completed",
                file_path=str(file_path),
                is_valid=result.is_valid,
                mime_type=mime_type,
                file_size=file_size,
                errors_count=len(result.errors),
                warnings_count=len(result.warnings)
            )
            
            return result
            
        except Exception as e:
            logger.error("File validation failed", error=str(e), file_path=str(file_path))
            return FileValidationResult(
                is_valid=False,
                file_type="unknown",
                mime_type="unknown",
                file_size=0,
                sha256_hash="",
                errors=[f"検証エラー: {str(e)}"]
            )

    
    def _calculate_sha256(self, file_path: Path) -> str:
        """SHA256ハッシュ計算"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    
    def _detect_file_type(self, file_path: Path) -> Tuple[str, str]:
        """ファイルタイプとMIMEタイプ検出"""
        try:
            mime_type = self.magic_mime.from_file(str(file_path))
            file_type = self.magic_type.from_file(str(file_path))
            return mime_type, file_type
        except Exception as e:
            logger.warning("Failed to detect file type", error=str(e))
            return "application/octet-stream", "unknown"
    
    def _has_dangerous_signature(self, file_path: Path) -> bool:
        """危険なファイルシグネチャチェック"""
        try:
            with open(file_path, "rb") as f:
                header = f.read(16)  # 最初の16バイトをチェック
                
            for signature, file_type in self.DANGEROUS_SIGNATURES.items():
                if header.startswith(signature.encode() if isinstance(signature, str) else signature):
                    logger.warning(
                        "Dangerous file signature detected",
                        signature_type=file_type,
                        file_path=str(file_path)
                    )
                    return True
            
            return False
        except Exception:
            return True  # エラー時は安全側に倒す
    
    def _validate_extension_mime_consistency(self, file_path: Path, mime_type: str) -> bool:
        """ファイル拡張子とMIMEタイプの整合性チェック"""
        file_extension = file_path.suffix.lower()
        
        # サポート形式での拡張子チェック
        for supported_mime, supported_extensions in self.SUPPORTED_FORMATS.items():
            if mime_type == supported_mime:
                return file_extension in supported_extensions
        
        return False
    
    def _is_supported_format(self, mime_type: str) -> bool:
        """サポート形式チェック"""
        return mime_type in self.SUPPORTED_FORMATS
    
    def _analyze_audio_metadata(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """音声メタデータ解析（ffprobeを使用）"""
        try:
            # ffprobeコマンドでメタデータ取得
            cmd = [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                str(file_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                logger.warning("ffprobe failed", error=result.stderr)
                return None
            
            import json
            probe_data = json.loads(result.stdout)
            
            # 音声ストリームを検索
            audio_stream = None
            for stream in probe_data.get("streams", []):
                if stream.get("codec_type") == "audio":
                    audio_stream = stream
                    break
            
            if not audio_stream:
                return None
            
            # メタデータ抽出
            format_info = probe_data.get("format", {})
            
            return {
                "duration": float(format_info.get("duration", 0)),
                "codec": audio_stream.get("codec_name"),
                "bitrate": int(audio_stream.get("bit_rate", 0)) if audio_stream.get("bit_rate") else None,
                "sample_rate": int(audio_stream.get("sample_rate", 0)) if audio_stream.get("sample_rate") else None,
                "channels": int(audio_stream.get("channels", 0)) if audio_stream.get("channels") else None,
            }
            
        except subprocess.TimeoutExpired:
            logger.warning("ffprobe timeout", file_path=str(file_path))
            return None
        except Exception as e:
            logger.warning("Audio metadata analysis failed", error=str(e))
            return None
    
    def _check_audio_quality(self, audio_info: Dict[str, Any]) -> List[str]:
        """音声品質チェック"""
        warnings = []
        
        # 長さチェック
        duration = audio_info.get("duration", 0)
        if duration > 3600:  # 1時間以上
            warnings.append("ファイルが長すぎます（1時間以上）")
        elif duration < 1:  # 1秒未満
            warnings.append("ファイルが短すぎます（1秒未満）")
        
        # ビットレートチェック
        bitrate = audio_info.get("bitrate")
        if bitrate:
            if bitrate < 32000:  # 32kbps未満
                warnings.append("ビットレートが低すぎます（音質が悪い可能性があります）")
            elif bitrate > 320000:  # 320kbps以上
                warnings.append("ビットレートが高すぎます（ファイルサイズが大きくなります）")
        
        # サンプルレートチェック
        sample_rate = audio_info.get("sample_rate")
        if sample_rate:
            if sample_rate < 16000:  # 16kHz未満
                warnings.append("サンプルレートが低すぎます（音質が悪い可能性があります）")
        
        return warnings
    
    def _verify_file_integrity(self, file_path: Path, mime_type: str) -> bool:
        """ファイル整合性チェック"""
        try:
            # ffprobeでファイルの読み取り可能性をテスト
            cmd = [
                "ffprobe",
                "-v", "error",
                "-select_streams", "a:0",
                "-count_packets",
                "-show_entries", "stream=nb_read_packets",
                "-of", "csv=p=0",
                str(file_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0 and result.stdout.strip().isdigit():
                packet_count = int(result.stdout.strip())
                return packet_count > 0
            
            return False
            
        except Exception as e:
            logger.warning("File integrity check failed", error=str(e))
            return True  # チェックできない場合は通す


class FileQuarantineService:
    """ファイル隔離サービス"""
    
    def __init__(self, quarantine_dir: Path):
        self.quarantine_dir = quarantine_dir
        self.quarantine_dir.mkdir(exist_ok=True)
        logger.info("File quarantine service initialized", quarantine_dir=str(quarantine_dir))
    
    def quarantine_file(self, file_path: Path, reason: str) -> Path:
        """ファイルを隔離"""
        try:
            # 隔離先パス生成
            timestamp = int(time.time())
            quarantine_name = f"{timestamp}_{file_path.name}"
            quarantine_path = self.quarantine_dir / quarantine_name
            
            # ファイル移動
            import shutil
            shutil.move(str(file_path), str(quarantine_path))
            
            # メタデータファイル作成
            metadata_path = quarantine_path.with_suffix(quarantine_path.suffix + ".meta")
            with open(metadata_path, "w") as f:
                f.write(f"Original path: {file_path}\n")
                f.write(f"Quarantine reason: {reason}\n")
                f.write(f"Quarantine time: {timestamp}\n")
            
            logger.warning(
                "File quarantined",
                original_path=str(file_path),
                quarantine_path=str(quarantine_path),
                reason=reason
            )
            
            return quarantine_path
            
        except Exception as e:
            logger.error("File quarantine failed", error=str(e))
            raise
    
    def cleanup_old_quarantine_files(self, max_age_days: int = 30):
        """古い隔離ファイルのクリーンアップ"""
        import time
        
        current_time = time.time()
        max_age_seconds = max_age_days * 24 * 3600
        
        try:
            for file_path in self.quarantine_dir.iterdir():
                if file_path.is_file():
                    file_age = current_time - file_path.stat().st_mtime
                    if file_age > max_age_seconds:
                        file_path.unlink()
                        logger.info("Old quarantine file deleted", file_path=str(file_path))
        except Exception as e:
            logger.error("Quarantine cleanup failed", error=str(e))