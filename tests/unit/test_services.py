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
from app.models.summary import AISummary, MeetingSummary
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
        
        job = service.create_job(
            original_filename="test.m4a",
            file_content=b"dummy content",
            usage_type_code="meeting"
        )
        
        assert job.id is not None
        assert job.original_filename == "test.m4a"
        assert job.file_size == 13
        assert job.usage_type_code == "meeting"
        assert job.status_code == "uploading"
    
    def test_get_job_by_id(self, test_db_session):
        """ID指定でジョブ取得テスト"""
        service = TranscriptionService(test_db_session)
        
        # ジョブ作成
        job = service.create_job(
            original_filename="test.m4a",
            file_content=b"dummy content",
            usage_type_code="meeting"
        )
        
        # 取得テスト
        retrieved_job = service.get_job(job.id)
        assert retrieved_job is not None
        assert retrieved_job.id == job.id
        assert retrieved_job.original_filename == "test.m4a"
        
        # 存在しないID
        non_existent = service.get_job("non-existent-id")
        assert non_existent is None
    
    def test_update_job_status(self, test_db_session):
        """ジョブステータス更新テスト"""
        service = TranscriptionService(test_db_session)
        
        job = service.create_job(
            original_filename="test.m4a",
            file_content=b"dummy content",
            usage_type_code="meeting"
        )
        
        # ステータス更新
        updated = service.update_job_status(
            job.id,
            status="processing",
            message="Processing started"
        )
        
        assert updated is True
        # Refetch to check
        updated_job = service.get_job(job.id)
        assert updated_job.status_code == "processing"
    
    def test_list_jobs_with_pagination(self, test_db_session):
        """ジョブ一覧取得（ページネーション付き）テスト"""
        service = TranscriptionService(test_db_session)
        
        # 複数ジョブ作成
        for i in range(15):
            service.create_job(
                original_filename=f"test_{i}.m4a",
                file_content=b"dummy",
                usage_type_code="meeting"
            )
        
        # 1ページ目取得（10件）
        page1_jobs = service.get_jobs(limit=10, offset=0)
        assert len(page1_jobs) == 10
        # assert total == 15 # get_jobs doesn't return total in new impl
        
        # 2ページ目取得（5件）
        page2_jobs = service.get_jobs(limit=10, offset=10)
        assert len(page2_jobs) == 5
        
    def test_delete_job(self, test_db_session):
        """ジョブ削除テスト"""
        service = TranscriptionService(test_db_session)
        
        job = service.create_job(
            original_filename="test.m4a",
            file_content=b"dummy",
            usage_type_code="meeting"
        )
        job_id = job.id
        
        # 削除実行
        result = service.delete_job(job_id)
        assert result is True
        
        # 削除確認
        deleted_job = service.get_job(job_id)
        assert deleted_job is None
        
        # 存在しないジョブの削除
        result = service.delete_job("non-existent-id")
        assert result is False


class TestSummaryService:
    """SummaryServiceのテスト"""
    
    def test_create_meeting_summary(self, test_db_session):
        """会議要約作成テスト"""
        # 先にジョブを作成
        transcription_service = TranscriptionService(test_db_session)
        job = transcription_service.create_job(
            original_filename="test.m4a",
            file_content=b"dummy",
            usage_type_code="meeting"
        )
        
        summary_service = SummaryService(test_db_session)
        
        # 基底サマリー作成
        summary_service.create_ai_summary(
            job_id=job.id,
            summary_type="meeting",
            model_used="llama3.2:3b",
            confidence=0.88,
            processing_time_seconds=15.5,
            raw_response={},
            formatted_text="# Summary"
        )

        # 詳細サマリー作成
        meeting_summary = summary_service.create_meeting_summary(
            job_id=job.id,
            decisions=["決定1"],
            action_plans=["アクション1"],
            summary="会議概要",
            topics_discussed=["議題1"]
        )
        
        assert meeting_summary.job_id == job.id
        assert meeting_summary.summary == "会議概要"
        assert len(meeting_summary.get_decisions()) == 1
        assert len(meeting_summary.get_action_plans()) == 1
    
    def test_get_complete_summary(self, test_db_session):
        """完全な要約取得テスト"""
        # ジョブと要約作成
        transcription_service = TranscriptionService(test_db_session)
        summary_service = SummaryService(test_db_session)
        
        job = transcription_service.create_job(
            original_filename="test.m4a",
            file_content=b"dummy",
            usage_type_code="meeting"
        )
        
        summary_service.create_ai_summary(
            job_id=job.id,
            summary_type="meeting",
            model_used="llama3.2:3b",
            confidence=0.9,
            processing_time_seconds=10.0,
            raw_response={},
            formatted_text="# Summary"
        )
        
        summary_service.create_meeting_summary(
            job_id=job.id,
            decisions=["Dec1"],
            action_plans=["Act1"],
            summary="Overview"
        )
        
        # 取得テスト
        result = summary_service.get_complete_summary(job.id)
        assert result is not None
        assert result["job_id"] == job.id
        assert result["type"] == "meeting"
        assert result["details"]["summary"] == "Overview"
        assert result["details"]["decisions"][0] == "Dec1"
        
        # 存在しないジョブID
        non_existent = summary_service.get_complete_summary("non-existent-id")
        assert non_existent is None


class TestWhisperService:
    """WhisperServiceのテスト"""
    
    @patch('app.services.whisper_service.WhisperModel')
    @pytest.mark.asyncio
    async def test_transcribe_audio_success(self, mock_whisper_model):
        """音声転写成功テスト"""
        # モックの設定
        mock_model_instance = Mock()
        mock_whisper_model.return_value = mock_model_instance
        
        # Segments generator mock - faster-whisper returns a generator and info
        Segment = Mock()
        Segment.start = 0.0
        Segment.end = 5.0
        Segment.text = "これはテスト用の転写結果です。"
        Segment.avg_logprob = -0.1
        
        Info = Mock()
        Info.language = "ja"
        Info.duration = 5.0
        Info.language_probability = 0.99
        
        # Generator function to simulate transcribe return
        def segment_generator(*args, **kwargs):
             yield Segment

        mock_model_instance.transcribe.return_value = (segment_generator(), Info)
        
        # WhisperService mocks internal sync method or we just let it run if it's mocked well enough.
        # But transcribe_audio uses run_in_executor. 
        # For unit test, we can trust run_in_executor works or mock it.
        # Let's mock _transcribe_sync to avoid complexity of thread pool in unit test?
        # Actually, if we mock WhisperModel properly, _transcribe_sync should work fine in thread too.
        # However, to avoid "Model not loaded" we need to ensure load_model works or is mocked.
        
        service = WhisperService()
        # Mock _load_model to avoid actually trying to load faster-whisper model
        service._load_model = Mock()
        service.model = mock_model_instance
        
        # Also need detailed mocks for _preprocess_audio if we want to skip it
        service._preprocess_audio = AsyncMock(return_value=Path("dummy.wav"))
        service._get_audio_duration = Mock(return_value=5.0)

        # Mock run_in_executor to run synchronously for test simplicity OR verify async behavior.
        # If we use real run_in_executor, we need real model or perfect mock.
        # Let's mock _transcribe_sync and avoid thread purely.
        # service._transcribe_sync = Mock(return_value={...}) 
        # But we really want to test the glue code in transcribe_audio.
        
        # Let's keep it simple: Mock _transcribe_sync allows testing transcribe_audio main flow.
        service._transcribe_sync = Mock(return_value={
            "text": "これはテスト用の転写結果です。",
            "language": "ja",
            "avg_confidence": 0.99,
            "segments": [{
                "start": 0.0, "end": 5.0, "text": "これはテスト用の転写結果です。", "confidence": -0.1
            }]
        })

        with tempfile.NamedTemporaryFile(suffix=".m4a") as temp_file:
            # Create dummy file
             Path(temp_file.name).touch()
             
             result = await service.transcribe_audio(temp_file.name)
        
        assert result["text"] == "これはテスト用の転写結果です。"
        assert result["language"] == "ja"
        assert len(result["segments"]) == 1

    # Skipping Whisper tests update for now to focus on Services import fix first.
    # I will just replace the top imports and SummaryService tests which are causing the collection error.
    # I'll keep the rest as is for now and let them fail if they must, but import error must be fixed.


class TestOllamaService:
    """OllamaServiceのテスト"""
    
    @patch('httpx.AsyncClient')
    @pytest.mark.asyncio
    async def test_generate_meeting_summary_success(self, mock_client):
        """会議要約生成成功テスト"""
        # モックレスポンス設定
        # Mock response needs to be a standard Mock, not AsyncMock, because we access .json() synchronously
        # and .status_code attribute.
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": json.dumps({
                "summary": "会議の概要について議論されました。",
                "details": {
                    "summary": "会議の概要について議論されました。",
                    "agenda": ["議題1"],
                    "decisions": ["決定1"],
                    "todo": ["ToDo1"],
                    "next_actions": ["Next1"],
                    "next_meeting": "次回"
                }
            }, ensure_ascii=False)
        }
        
        mock_client_instance = Mock()
        # post is async, so it returns a coroutine that resolves to mock_response
        # We use AsyncMock for post, and its return_value is the mock_response object
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        
        # Async context manager mock
        # When 'async with self.client' is used currently, but OllamaService uses self.client directly.
        # OllamaService initializes self.client in __init__.
        # The test patches httpx.AsyncClient class.
        # So httpx.AsyncClient() returns mock_client.return_value.
        # We want mock_client.return_value to be mock_client_instance (or behave like it).
        # Actually in the code: self.client = httpx.AsyncClient(...)
        # So mock_client.return_value IS the client instance.
        
        mock_client.return_value = mock_client_instance
        # If the code uses 'async with self.client', we need __aenter__.
        # OllamaService implements __aenter__ calling self.client.__aenter__?
        # No, OllamaService implements __aenter__ returning self.
        
        # We need to handle 'async with OllamaService() as ollama'.
        # This calls OllamaService.__aenter__, which returns self.
        # Then inside usage, we call ollama.generate_summary.
        # generate_summary uses self.client.post.
        # So simply mocking self.client (via httpx.AsyncClient return value) is enough.
        
        # Remove context manager mock for client unless OllamaService uses it internally?
        # OllamaService does NOT use client as context manager in generate_summary.
        # It uses it as instance attribute.
        
        # So this setup is sufficient:
        # mock_client.return_value = mock_client_instance
        # mock_client_instance.post = AsyncMock(return_value=mock_response)
        
        service = OllamaService()
        
        transcription_text = "今日の会議では重要な議題について話し合いました。"
        result = await service.generate_summary(transcription_text, "meeting")
        
        assert result is not None
        assert result["text"] == "会議の概要について議論されました。"
        assert "details" in result


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
        mock_whisper_instance.transcribe_audio = AsyncMock(return_value={
            "text": "会議の内容について話し合いました。",
            "language": "ja",
            "segments": [],
            "duration_seconds": 10.0,
            "confidence": 0.9,
            "model_used": "base",
            "processing_time_seconds": 1.0
        })
        
        # Ollamaサービスのモック
        mock_ollama_instance = mock_ollama_service.return_value
        # correct_transcription mock
        mock_ollama_instance.correct_transcription = AsyncMock(return_value={
            "corrected_text": "会議の内容について話し合いました。",
            "corrections_made": False
        })
        # generate_summary mock
        mock_ollama_instance.generate_summary = AsyncMock(return_value={
            "text": "会議概要",
            "formatted_text": "# Summary",
            "confidence": 0.9,
            "model_used": "llama3.2:3b",
            "details": {
                "summary": "会議概要",
                "agenda": ["議題"],
                "decisions": ["決定"],
                "todo": ["ToDo"],
                "next_actions": ["Next"],
                "next_meeting": "次回"
            }
        })
        
        # Setup context manager for async with OllamaService()
        # mock_ollama_instance is what OllamaService() returns.
        # We need to make sure __aenter__ returns mock_ollama_instance (or something with generate_summary)
        mock_ollama_instance.__aenter__.return_value = mock_ollama_instance
        mock_ollama_instance.__aexit__.return_value = None
        
        processor = AudioProcessor(Mock())
        # Mock services inside processor to avoid DB calls
        processor.transcription_service = Mock()
        processor.transcription_service.get_job = Mock(return_value=Mock(id="job123", usage_type_code="meeting", audio_file=None))
        processor.transcription_service.update_job_status = Mock(return_value=True)
        processor.transcription_service.save_transcription_result = Mock(return_value=True)
        processor.summary_service = Mock()
        processor.summary_service.create_ai_summary = Mock(return_value=Mock(id="ai_summ_1"))
        processor.summary_service.create_meeting_summary = Mock(return_value=Mock(id="meeting_summ_1"))
        
        # Mock _transcribe_audio and _generate_summary to use the service mocks? 
        # But process_audio_file instantiates services internally inside _transcribe_audio if not mocked.
        # process_audio_file calls _transcribe_audio. _transcribe_audio instantiates WhisperService.
        # So mocking WhisperService with patch is correct.
        
        with tempfile.NamedTemporaryFile(suffix=".m4a") as temp_file:
            temp_file.write(b"dummy audio content")
            temp_file.flush()
            
            # Create a dummy M4A file in UPLOAD_DIR or mock the file path logic
            # The test uses settings.UPLOAD_DIR. We should mock that or ensure file exists.
            # But process_audio_file has fallback logic.
            
            # Simpler: Mock internal methods to avoid file system dependency if possible, but we want to test flow.
            # Let's rely on patches.
            
            # Need to mock Path.exists? Or just put file where it expects.
            # job.audio_file is None in my mock above.
            # So it looks in UPLOAD_DIR/job_id.m4a.
            
            with patch('app.services.audio_processor.Path.exists', return_value=True):
                 result = await processor.process_audio_file(job_id="job123")
        
        assert result is not None
        assert result["status"] == "completed"
        assert "transcription" in result
        assert "summary" in result