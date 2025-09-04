"""
音声処理統合テスト
"""

import pytest
import asyncio
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

# テスト環境設定
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///./test_audio_processing.db"

from app.services.whisper_service import WhisperService, WhisperError, check_whisper_dependencies
from app.services.ollama_service import OllamaService, OllamaError
from app.services.audio_processor import AudioProcessor, AudioProcessingError
from app.core.database import get_database_manager


class TestWhisperService:
    """Whisperサービステスト"""
    
    def test_whisper_dependencies(self):
        """Whisper依存関係チェック"""
        deps = check_whisper_dependencies()
        
        # 依存関係情報が取得できることを確認
        assert "whisper" in deps
        assert "torch" in deps
        assert "librosa" in deps
        assert "soundfile" in deps
        
        # 各依存関係はbool値であることを確認
        for key, value in deps.items():
            assert isinstance(value, bool)
    
    def test_whisper_service_initialization(self):
        """Whisperサービス初期化テスト"""
        try:
            service = WhisperService(model_name="base", device="cpu")
            
            assert service.model_name == "base"
            assert service.device == "cpu"
            assert service.model is None  # モデルは遅延読み込み
            
        except WhisperError:
            # Whisperがインストールされていない場合はスキップ
            pytest.skip("Whisper not available")
    
    def test_get_available_models(self):
        """利用可能モデル一覧テスト"""
        try:
            service = WhisperService()
            models = service.get_available_models()
            
            # 標準的なモデルが含まれていることを確認
            assert "base" in models
            assert "small" in models
            assert "large" in models
            
        except WhisperError:
            pytest.skip("Whisper not available")
    
    def test_get_model_info(self):
        """モデル情報取得テスト"""
        try:
            service = WhisperService(model_name="base")
            info = service.get_model_info()
            
            assert info["model_name"] == "base"
            assert "device" in info
            assert "available_models" in info
            assert "whisper_available" in info
            
        except WhisperError:
            pytest.skip("Whisper not available")
    
    @pytest.mark.asyncio
    async def test_health_check(self):
        """Whisperヘルスチェックテスト"""
        try:
            service = WhisperService()
            health = await service.health_check()
            
            assert "status" in health
            assert "message" in health
            assert health["status"] in ["healthy", "error"]
            
        except WhisperError:
            pytest.skip("Whisper not available")


class TestOllamaService:
    """Ollamaサービステスト"""
    
    @pytest.mark.asyncio
    async def test_ollama_service_initialization(self):
        """Ollamaサービス初期化テスト"""
        async with OllamaService(base_url="http://localhost:11434") as service:
            assert service.base_url == "http://localhost:11434"
            assert service.timeout > 0
            assert service.model is not None
    
    @pytest.mark.asyncio
    async def test_connection_check(self):
        """Ollama接続確認テスト"""
        async with OllamaService() as service:
            # 接続確認（Ollamaが動いていなくても例外は発生しない）
            is_connected = await service.check_connection()
            assert isinstance(is_connected, bool)
    
    @pytest.mark.asyncio 
    async def test_health_check(self):
        """Ollamaヘルスチェックテスト"""
        async with OllamaService() as service:
            health = await service.health_check()
            
            assert "status" in health
            assert "message" in health
            assert health["status"] in ["healthy", "error", "warning"]
    
    @pytest.mark.asyncio
    async def test_list_models_failure(self):
        """モデル一覧取得失敗テスト"""
        # 存在しないURLで初期化
        async with OllamaService(base_url="http://invalid-url:9999") as service:
            with pytest.raises(OllamaError):
                await service.list_models()
    
    @pytest.mark.asyncio
    async def test_generate_summary_with_mock(self):
        """要約生成テスト（モック使用）"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "これは会議の要約です。主要な決定事項として以下があります。"
        }
        mock_response.raise_for_status.return_value = None
        
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            
            async with OllamaService() as service:
                result = await service.generate_summary(
                    text="テスト会議の内容です。",
                    summary_type="meeting"
                )
                
                assert "text" in result
                assert "formatted_text" in result
                assert "confidence" in result
                assert "model_used" in result
                assert result["type"] == "meeting"
    
    def test_build_summary_prompt(self):
        """要約プロンプト構築テスト"""
        service = OllamaService()
        
        # 会議タイプ
        meeting_prompt = service._build_summary_prompt("会議内容", "meeting")
        assert "会議の転写テキスト" in meeting_prompt
        assert "JSON形式" in meeting_prompt
        assert "decisions" in meeting_prompt
        
        # 面接タイプ
        interview_prompt = service._build_summary_prompt("面接内容", "interview")
        assert "面接の転写テキスト" in interview_prompt
        assert "position_applied" in interview_prompt
        
        # 汎用タイプ
        general_prompt = service._build_summary_prompt("一般的な内容", "general")
        assert "要点を3-5行" in general_prompt


class TestAudioProcessor:
    """音声処理統合テスト"""
    
    @pytest.fixture
    def mock_db(self):
        """モックデータベース"""
        return Mock()
    
    @pytest.fixture
    def audio_processor(self, mock_db):
        """音声処理サービス"""
        return AudioProcessor(mock_db)
    
    @pytest.mark.asyncio
    async def test_health_check(self, audio_processor):
        """統合ヘルスチェックテスト"""
        health = await audio_processor.health_check()
        
        assert "overall_status" in health
        assert "services" in health
        assert health["overall_status"] in ["healthy", "error", "warning"]
        
        # 各サービスの状態確認
        services = health["services"]
        if "whisper" in services:
            assert "status" in services["whisper"]
        if "ollama" in services:
            assert "status" in services["ollama"]
    
    def test_create_temp_audio_file(self):
        """テスト用音声ファイル作成"""
        # WAVファイルのダミーヘッダー作成
        wav_header = b'RIFF\x24\x08\x00\x00WAVE'
        wav_header += b'fmt \x10\x00\x00\x00\x01\x00\x01\x00'
        wav_header += b'\x44\xAC\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00'
        wav_header += b'data\x00\x08\x00\x00'
        wav_header += b'\x00' * 2048  # ダミー音声データ
        
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            tmp_file.write(wav_header)
            return Path(tmp_file.name)
    
    @pytest.mark.asyncio
    async def test_process_audio_file_mock(self, audio_processor, mock_db):
        """音声ファイル処理テスト（モック使用）"""
        
        # モック設定
        mock_job = Mock()
        mock_job.id = "test-job-123"
        mock_job.usage_type_code = "meeting"
        mock_job.audio_file = None
        
        # TranscriptionServiceのモック
        audio_processor.transcription_service.get_job = Mock(return_value=mock_job)
        audio_processor.transcription_service.update_job_status = Mock(return_value=True)
        
        # 音声ファイル作成
        audio_path = self.test_create_temp_audio_file()
        
        try:
            # 実際の処理をモック
            with patch.object(audio_processor, '_transcribe_audio') as mock_transcribe:
                with patch.object(audio_processor, '_save_transcription_result') as mock_save_trans:
                    with patch.object(audio_processor, '_generate_summary') as mock_generate:
                        with patch.object(audio_processor, '_save_summary_result') as mock_save_summ:
                            
                            # モックの戻り値設定
                            mock_transcribe.return_value = {
                                "text": "テスト転写結果",
                                "confidence": 0.95,
                                "language": "ja",
                                "duration_seconds": 10.0,
                                "segments": []
                            }
                            
                            mock_generate.return_value = {
                                "text": "テスト要約結果",
                                "formatted_text": "■テスト要約\n内容です。",
                                "confidence": 0.90
                            }
                            
                            # 処理実行
                            result = await audio_processor.process_audio_file("test-job-123")
                            
                            # 結果確認
                            assert result["job_id"] == "test-job-123"
                            assert result["status"] == "completed"
                            assert "transcription" in result
                            assert "summary" in result
                            
                            # モック呼び出し確認
                            mock_transcribe.assert_called_once()
                            mock_save_trans.assert_called_once()
                            mock_generate.assert_called_once()
                            mock_save_summ.assert_called_once()
        
        finally:
            # 一時ファイル削除
            if audio_path.exists():
                audio_path.unlink()


class TestIntegrationErrors:
    """統合エラーハンドリングテスト"""
    
    @pytest.mark.asyncio
    async def test_whisper_error_handling(self):
        """Whisperエラーハンドリングテスト"""
        try:
            service = WhisperService()
            
            # 存在しないファイルで転写実行
            with pytest.raises(WhisperError):
                await service.transcribe_audio("nonexistent.wav")
                
        except WhisperError:
            pytest.skip("Whisper not available")
    
    @pytest.mark.asyncio
    async def test_ollama_error_handling(self):
        """Ollamaエラーハンドリングテスト"""
        # 無効なURLでサービス初期化
        service = OllamaService(base_url="http://invalid:9999")
        
        with pytest.raises(OllamaError):
            await service.generate_summary("テキスト", "meeting")


@pytest.fixture(scope="module", autouse=True)
def cleanup_test_files():
    """テストファイルクリーンアップ"""
    yield
    
    # テストデータベース削除
    test_db_files = [
        "test_audio_processing.db",
        "test_audio_processing.db-shm",
        "test_audio_processing.db-wal"
    ]
    
    for db_file in test_db_files:
        db_path = Path(db_file)
        if db_path.exists():
            try:
                db_path.unlink()
            except:
                pass  # ファイルロック等で削除できない場合は無視


if __name__ == "__main__":
    pytest.main([__file__, "-v"])