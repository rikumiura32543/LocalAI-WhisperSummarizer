"""
サービス層のユニットテスト
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, mock_open
import tempfile
import json
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.transcription import TranscriptionJob, AudioFile, TranscriptionResult
from app.models.summary import SummaryResult
from app.services.transcription_service import TranscriptionService
from app.services.summary_service import SummaryService
from app.services.whisper_service import WhisperService
from app.services.ollama_service import OllamaService
from app.services.audio_processor import AudioProcessor


@pytest.fixture(scope="function")
def test_db_session():
    """テスト用データベースセッション"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    
    TestingSessionLocal = sessionmaker(bind=engine)
    session = TestingSessionLocal()
    
    yield session
    
    session.close()


@pytest.fixture
def sample_audio_file():
    """サンプル音声ファイル"""
    with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as f:
        f.write(b"dummy audio content")
        return f.name


class TestTranscriptionService:
    """TranscriptionServiceのテスト"""
    
    def test_create_transcription_job(self, test_db_session):
        """転写ジョブ作成テスト"""
        service = TranscriptionService(test_db_session)
        
        job_data = {
            "filename": "test.m4a",
            "file_size": 1024,
            "usage_type": "meeting"
        }
        
        job = service.create_job(**job_data)
        
        assert job.id is not None
        assert job.filename == "test.m4a"
        assert job.file_size == 1024
        assert job.usage_type == "meeting"
        assert job.status == "pending"
    
    def test_get_job_by_id(self, test_db_session):
        """ID指定でジョブ取得テスト"""
        service = TranscriptionService(test_db_session)
        
        # ジョブ作成
        job = service.create_job(
            filename="test.m4a",
            file_size=1024,
            usage_type="meeting"
        )
        
        # 取得テスト
        retrieved_job = service.get_job(job.id)
        assert retrieved_job is not None
        assert retrieved_job.id == job.id
        assert retrieved_job.filename == "test.m4a"
        
        # 存在しないID
        non_existent = service.get_job(99999)
        assert non_existent is None
    
    def test_update_job_status(self, test_db_session):
        """ジョブステータス更新テスト"""
        service = TranscriptionService(test_db_session)
        
        job = service.create_job(
            filename="test.m4a",
            file_size=1024,
            usage_type="meeting"
        )
        
        # ステータス更新
        updated_job = service.update_job_status(
            job.id,
            status="processing",
            processing_step="transcription"
        )
        
        assert updated_job.status == "processing"
        assert updated_job.processing_step == "transcription"
    
    def test_list_jobs_with_pagination(self, test_db_session):
        """ジョブ一覧取得（ページネーション付き）テスト"""
        service = TranscriptionService(test_db_session)
        
        # 複数ジョブ作成
        for i in range(15):
            service.create_job(
                filename=f"test_{i}.m4a",
                file_size=1024 + i,
                usage_type="meeting"
            )
        
        # 1ページ目取得（10件）
        page1_jobs, total = service.list_jobs(skip=0, limit=10)
        assert len(page1_jobs) == 10
        assert total == 15
        
        # 2ページ目取得（5件）
        page2_jobs, total = service.list_jobs(skip=10, limit=10)
        assert len(page2_jobs) == 5
        assert total == 15
    
    def test_delete_job(self, test_db_session):
        """ジョブ削除テスト"""
        service = TranscriptionService(test_db_session)
        
        job = service.create_job(
            filename="test.m4a",
            file_size=1024,
            usage_type="meeting"
        )
        job_id = job.id
        
        # 削除実行
        result = service.delete_job(job_id)
        assert result is True
        
        # 削除確認
        deleted_job = service.get_job(job_id)
        assert deleted_job is None
        
        # 存在しないジョブの削除
        result = service.delete_job(99999)
        assert result is False


class TestSummaryService:
    """SummaryServiceのテスト"""
    
    def test_save_summary_result(self, test_db_session):
        """要約結果保存テスト"""
        # 先にジョブを作成
        transcription_service = TranscriptionService(test_db_session)
        job = transcription_service.create_job(
            filename="test.m4a",
            file_size=1024,
            usage_type="meeting"
        )
        
        summary_service = SummaryService(test_db_session)
        
        summary_data = {
            "overview": "会議の概要",
            "key_points": ["ポイント1", "ポイント2"],
            "action_items": ["アクション1"]
        }
        
        result = summary_service.save_summary_result(
            job_id=job.id,
            summary=summary_data,
            confidence=0.88,
            processing_time=15.5,
            model_name="llama3.2:3b"
        )
        
        assert result.id is not None
        assert result.job_id == job.id
        assert result.summary["overview"] == "会議の概要"
        assert len(result.summary["key_points"]) == 2
        assert result.confidence == 0.88
    
    def test_get_summary_by_job_id(self, test_db_session):
        """ジョブIDで要約取得テスト"""
        # ジョブと要約作成
        transcription_service = TranscriptionService(test_db_session)
        summary_service = SummaryService(test_db_session)
        
        job = transcription_service.create_job(
            filename="test.m4a",
            file_size=1024,
            usage_type="meeting"
        )
        
        summary_data = {"overview": "テスト要約"}
        summary_service.save_summary_result(
            job_id=job.id,
            summary=summary_data,
            confidence=0.9,
            processing_time=10.0,
            model_name="llama3.2:3b"
        )
        
        # 取得テスト
        retrieved_summary = summary_service.get_summary_by_job_id(job.id)
        assert retrieved_summary is not None
        assert retrieved_summary.job_id == job.id
        assert retrieved_summary.summary["overview"] == "テスト要約"
        
        # 存在しないジョブID
        non_existent = summary_service.get_summary_by_job_id(99999)
        assert non_existent is None


class TestWhisperService:
    """WhisperServiceのテスト"""
    
    @patch('app.services.whisper_service.whisper.load_model')
    @patch('app.services.whisper_service.whisper.transcribe')
    def test_transcribe_audio_success(self, mock_transcribe, mock_load_model):
        """音声転写成功テスト"""
        # モックの設定
        mock_model = Mock()
        mock_load_model.return_value = mock_model
        
        mock_result = {
            "text": "これはテスト用の転写結果です。",
            "language": "ja",
            "segments": [
                {
                    "id": 0,
                    "start": 0.0,
                    "end": 5.0,
                    "text": "これはテスト用の転写結果です。"
                }
            ]
        }
        mock_transcribe.return_value = mock_result
        
        service = WhisperService()
        
        with tempfile.NamedTemporaryFile(suffix=".m4a") as temp_file:
            result = service.transcribe_audio(temp_file.name)
        
        assert result is not None
        assert result["text"] == "これはテスト用の転写結果です。"
        assert result["language"] == "ja"
        assert len(result["segments"]) == 1
        
        mock_load_model.assert_called_once()
        mock_transcribe.assert_called_once()
    
    @patch('app.services.whisper_service.whisper.load_model')
    def test_transcribe_audio_file_not_found(self, mock_load_model):
        """存在しないファイルの転写テスト"""
        service = WhisperService()
        
        result = service.transcribe_audio("/nonexistent/file.m4a")
        assert result is None
    
    @patch('app.services.whisper_service.whisper.load_model')
    @patch('app.services.whisper_service.whisper.transcribe')
    def test_transcribe_audio_exception_handling(self, mock_transcribe, mock_load_model):
        """転写中の例外処理テスト"""
        mock_load_model.return_value = Mock()
        mock_transcribe.side_effect = Exception("転写エラー")
        
        service = WhisperService()
        
        with tempfile.NamedTemporaryFile(suffix=".m4a") as temp_file:
            result = service.transcribe_audio(temp_file.name)
        
        assert result is None


class TestOllamaService:
    """OllamaServiceのテスト"""
    
    @patch('httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_generate_meeting_summary_success(self, mock_client):
        """会議要約生成成功テスト"""
        # モックレスポンス設定
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": json.dumps({
                "overview": "会議の概要について議論されました。",
                "key_points": ["重要なポイント1", "重要なポイント2"],
                "action_items": ["来週までにタスク完了"]
            }, ensure_ascii=False)
        }
        
        mock_client_instance = Mock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        
        service = OllamaService()
        
        transcription_text = "今日の会議では重要な議題について話し合いました。"
        result = await service.generate_meeting_summary(transcription_text)
        
        assert result is not None
        assert "overview" in result
        assert "key_points" in result
        assert "action_items" in result
        assert result["overview"] == "会議の概要について議論されました。"
        assert len(result["key_points"]) == 2
    
    @patch('httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_generate_interview_summary_success(self, mock_client):
        """面接要約生成成功テスト"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": json.dumps({
                "candidate_assessment": {
                    "strengths": ["コミュニケーション能力", "技術スキル"],
                    "areas_for_improvement": ["経験不足"],
                    "overall_impression": "良好"
                },
                "recommendation": "採用推奨"
            }, ensure_ascii=False)
        }
        
        mock_client_instance = Mock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        
        service = OllamaService()
        
        transcription_text = "自己紹介をお願いします。私は..."
        result = await service.generate_interview_summary(transcription_text)
        
        assert result is not None
        assert "candidate_assessment" in result
        assert "recommendation" in result
        assert result["recommendation"] == "採用推奨"
    
    @patch('httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_generate_summary_api_error(self, mock_client):
        """API呼び出しエラーテスト"""
        mock_response = Mock()
        mock_response.status_code = 500
        
        mock_client_instance = Mock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        
        service = OllamaService()
        
        result = await service.generate_meeting_summary("テスト")
        assert result is None
    
    @patch('httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_is_available_true(self, mock_client):
        """サービス利用可能性テスト（True）"""
        mock_response = Mock()
        mock_response.status_code = 200
        
        mock_client_instance = Mock()
        mock_client_instance.get = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        
        service = OllamaService()
        result = await service.is_available()
        
        assert result is True
    
    @patch('httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_is_available_false(self, mock_client):
        """サービス利用可能性テスト（False）"""
        mock_client_instance = Mock()
        mock_client_instance.get = AsyncMock(side_effect=Exception("接続エラー"))
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        
        service = OllamaService()
        result = await service.is_available()
        
        assert result is False


class TestAudioProcessor:
    """AudioProcessorのテスト"""
    
    @patch('app.services.audio_processor.WhisperService')
    @patch('app.services.audio_processor.OllamaService')
    @pytest.mark.asyncio
    async def test_process_audio_file_complete_flow(
        self, mock_ollama_service, mock_whisper_service
    ):
        """音声ファイル処理の完全フローテスト"""
        # Whisperサービスのモック
        mock_whisper_instance = mock_whisper_service.return_value
        mock_whisper_instance.transcribe_audio.return_value = {
            "text": "会議の内容について話し合いました。",
            "language": "ja",
            "segments": []
        }
        
        # Ollamaサービスのモック
        mock_ollama_instance = mock_ollama_service.return_value
        mock_ollama_instance.generate_meeting_summary = AsyncMock(return_value={
            "overview": "会議概要",
            "key_points": ["重要ポイント"],
            "action_items": ["アクション"]
        })
        
        processor = AudioProcessor()
        
        with tempfile.NamedTemporaryFile(suffix=".m4a") as temp_file:
            temp_file.write(b"dummy audio content")
            temp_file.flush()
            
            result = await processor.process_audio_file(
                file_path=temp_file.name,
                usage_type="meeting"
            )
        
        assert result is not None
        assert "transcription" in result
        assert "summary" in result
        assert result["transcription"]["text"] == "会議の内容について話し合いました。"
        assert result["summary"]["overview"] == "会議概要"
        
        mock_whisper_instance.transcribe_audio.assert_called_once()
        mock_ollama_instance.generate_meeting_summary.assert_called_once()
    
    @patch('app.services.audio_processor.WhisperService')
    @pytest.mark.asyncio
    async def test_process_audio_file_transcription_failure(self, mock_whisper_service):
        """転写失敗時のテスト"""
        mock_whisper_instance = mock_whisper_service.return_value
        mock_whisper_instance.transcribe_audio.return_value = None
        
        processor = AudioProcessor()
        
        with tempfile.NamedTemporaryFile(suffix=".m4a") as temp_file:
            result = await processor.process_audio_file(
                file_path=temp_file.name,
                usage_type="meeting"
            )
        
        assert result is None
    
    @patch('app.services.audio_processor.WhisperService')
    @patch('app.services.audio_processor.OllamaService')
    @pytest.mark.asyncio
    async def test_process_audio_file_summary_failure(
        self, mock_ollama_service, mock_whisper_service
    ):
        """要約生成失敗時のテスト"""
        # 転写は成功
        mock_whisper_instance = mock_whisper_service.return_value
        mock_whisper_instance.transcribe_audio.return_value = {
            "text": "テストテキスト",
            "language": "ja",
            "segments": []
        }
        
        # 要約生成が失敗
        mock_ollama_instance = mock_ollama_service.return_value
        mock_ollama_instance.generate_meeting_summary = AsyncMock(return_value=None)
        
        processor = AudioProcessor()
        
        with tempfile.NamedTemporaryFile(suffix=".m4a") as temp_file:
            result = await processor.process_audio_file(
                file_path=temp_file.name,
                usage_type="meeting"
            )
        
        # 転写結果のみ返される
        assert result is not None
        assert "transcription" in result
        assert "summary" not in result or result["summary"] is None


class TestServiceIntegration:
    """サービス層統合テスト"""
    
    def test_transcription_and_summary_integration(self, test_db_session):
        """転写サービスと要約サービスの統合テスト"""
        transcription_service = TranscriptionService(test_db_session)
        summary_service = SummaryService(test_db_session)
        
        # ジョブ作成
        job = transcription_service.create_job(
            filename="integration_test.m4a",
            file_size=2048,
            usage_type="meeting"
        )
        
        # 転写結果を模擬的に保存
        transcription_result = TranscriptionResult(
            job_id=job.id,
            text="統合テスト用の転写結果です。",
            confidence=0.95,
            processing_time=30.0,
            detected_language="ja"
        )
        test_db_session.add(transcription_result)
        test_db_session.commit()
        
        # 要約結果を保存
        summary_data = {
            "overview": "統合テストの概要",
            "key_points": ["統合テストの実行"],
            "action_items": ["テスト結果の確認"]
        }
        
        summary_result = summary_service.save_summary_result(
            job_id=job.id,
            summary=summary_data,
            confidence=0.9,
            processing_time=15.0,
            model_name="llama3.2:3b"
        )
        
        # 最終的なジョブ状態を確認
        final_job = transcription_service.get_job(job.id)
        assert final_job is not None
        assert final_job.transcription_result is not None
        assert final_job.summary_result is not None
        
        # リレーションシップの確認
        assert final_job.transcription_result.text == "統合テスト用の転写結果です。"
        assert final_job.summary_result.summary["overview"] == "統合テストの概要"