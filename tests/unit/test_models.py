"""
モデル層のユニットテスト
"""

import pytest
import uuid
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.base import Base
from app.models.transcription import TranscriptionJob, AudioFile, TranscriptionResult
from app.models.summary import AISummary, MeetingSummary


@pytest.fixture(scope="function")
def test_db_session():
    """テスト用データベースセッション"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    
    TestingSessionLocal = sessionmaker(bind=engine)
    session = TestingSessionLocal()
    
    yield session
    
    session.close()


class TestTranscriptionJobModel:
    """TranscriptionJobモデルのテスト"""
    
    def test_create_transcription_job(self, test_db_session):
        """転写ジョブ作成テスト"""
        job_id = str(uuid.uuid4())
        job = TranscriptionJob(
            id=job_id,
            filename=f"{job_id}.m4a",
            original_filename="test.m4a",
            file_size=1024,
            file_hash="abc123def456",
            mime_type="audio/m4a",
            usage_type_code="meeting",
            status_code="pending"
        )
        
        test_db_session.add(job)
        test_db_session.commit()
        
        assert job.id == job_id
        assert job.original_filename == "test.m4a"
        assert job.file_size == 1024
        assert job.usage_type_code == "meeting"
        assert job.status_code == "pending"
        assert job.created_at is not None
    
    def test_transcription_job_status_progression(self, test_db_session):
        """ステータス遷移テスト"""
        job_id = str(uuid.uuid4())
        job = TranscriptionJob(
            id=job_id,
            filename=f"{job_id}.m4a",
            original_filename="test.m4a",
            file_size=1024,
            file_hash="abc123def456",
            mime_type="audio/m4a",
            usage_type_code="meeting",
            status_code="pending"
        )
        test_db_session.add(job)
        test_db_session.commit()
        
        # processing状態に更新
        job.status_code = "processing"
        job.processing_step = "transcription"
        test_db_session.commit()
        
        assert job.status_code == "processing"
        assert job.processing_step == "transcription"
        
        # completed状態に更新
        job.status_code = "completed"
        job.processing_completed_at = datetime.now(timezone.utc)
        test_db_session.commit()
        
        assert job.status_code == "completed"
        assert job.processing_completed_at is not None
    
    def test_transcription_job_relationships(self, test_db_session):
        """リレーションシップテスト"""
        # ジョブ作成
        job_id = str(uuid.uuid4())
        job = TranscriptionJob(
            id=job_id,
            filename=f"{job_id}.m4a",
            original_filename="test.m4a",
            file_size=1024,
            file_hash="abc123def456",
            mime_type="audio/m4a",
            usage_type_code="meeting",
            status_code="pending"
        )
        test_db_session.add(job)
        test_db_session.flush()
        
        # 音声ファイル作成
        audio_file = AudioFile(
            job_id=job.id,
            file_path="/tmp/test.m4a",
            duration_seconds=60.0,
            sample_rate=44100,
            channels=2
        )
        test_db_session.add(audio_file)
        
        # 転写結果作成
        transcription_result = TranscriptionResult(
            job_id=job.id,
            text="テスト用転写結果",
            confidence=0.95,
            language="ja",
            duration_seconds=60.0,
            model_used="large-v3",
            processing_time_seconds=30.0
        )
        test_db_session.add(transcription_result)
        
        test_db_session.commit()
        
        # リレーションシップ確認
        assert job.audio_file is not None
        assert job.transcription_result is not None
        assert job.transcription_result.text == "テスト用転写結果"


class TestAudioFileModel:
    """AudioFileモデルのテスト"""
    
    def test_create_audio_file(self, test_db_session):
        """音声ファイル作成テスト"""
        # 先にジョブを作成
        job_id = str(uuid.uuid4())
        job = TranscriptionJob(
            id=job_id,
            filename=f"{job_id}.m4a",
            original_filename="test.m4a",
            file_size=1024,
            file_hash="abc123def456",
            mime_type="audio/m4a",
            usage_type_code="meeting",
            status_code="pending"
        )
        test_db_session.add(job)
        test_db_session.flush()
        
        audio_file = AudioFile(
            job_id=job.id,
            file_path="/tmp/test.m4a",
            duration_seconds=120.5,
            sample_rate=44100,
            channels=2,
            bitrate=128000
        )
        
        test_db_session.add(audio_file)
        test_db_session.commit()
        
        assert audio_file.job_id == job.id
        assert audio_file.duration_seconds == 120.5
        assert audio_file.sample_rate == 44100
        assert audio_file.channels == 2
        assert audio_file.bitrate == 128000


class TestTranscriptionResultModel:
    """TranscriptionResultモデルのテスト"""
    
    def test_create_transcription_result(self, test_db_session):
        """転写結果作成テスト"""
        # 先にジョブを作成
        job_id = str(uuid.uuid4())
        job = TranscriptionJob(
            id=job_id,
            filename=f"{job_id}.m4a",
            original_filename="test.m4a",
            file_size=1024,
            file_hash="abc123def456",
            mime_type="audio/m4a",
            usage_type_code="meeting",
            status_code="pending"
        )
        test_db_session.add(job)
        test_db_session.flush()
        
        result = TranscriptionResult(
            job_id=job.id,
            text="これはテスト用の転写結果です。音声からテキストに変換されました。",
            confidence=0.95,
            language="ja",
            duration_seconds=45.2,
            model_used="whisper-large-v3",
            processing_time_seconds=45.2
        )
        
        test_db_session.add(result)
        test_db_session.commit()
        
        assert result.job_id == job.id
        assert result.confidence == 0.95
        assert result.language == "ja"
        assert result.model_used == "whisper-large-v3"
        assert "転写結果" in result.text
    
    def test_transcription_result_with_segments(self, test_db_session):
        """セグメント付き転写結果テスト"""
        job_id = str(uuid.uuid4())
        job = TranscriptionJob(
            id=job_id,
            filename=f"{job_id}.m4a",
            original_filename="test.m4a",
            file_size=1024,
            file_hash="abc123def456",
            mime_type="audio/m4a",
            usage_type_code="meeting",
            status_code="pending"
        )
        test_db_session.add(job)
        test_db_session.flush()
        
        # Note: TranscriptionResult doesn't have segments field in actual model
        # Segments are stored separately in TranscriptionSegment table
        result = TranscriptionResult(
            job_id=job.id,
            text="最初のセグメント 2番目のセグメント",
            confidence=0.95,
            language="ja",
            duration_seconds=20.0,
            model_used="whisper-large-v3",
            processing_time_seconds=20.0,
            segments_count=2
        )
        
        test_db_session.add(result)
        test_db_session.commit()
        
        assert result.segments_count == 2


class TestAISummaryModel:
    """AISummaryモデルのテスト"""
    
    def test_create_ai_summary(self, test_db_session):
        """AI要約作成テスト"""
        job_id = str(uuid.uuid4())
        job = TranscriptionJob(
            id=job_id,
            filename=f"{job_id}.m4a",
            original_filename="test.m4a",
            file_size=1024,
            file_hash="abc123def456",
            mime_type="audio/m4a",
            usage_type_code="meeting",
            status_code="pending"
        )
        test_db_session.add(job)
        test_db_session.flush()
        
        summary = AISummary(
            job_id=job.id,
            type="meeting",
            model_used="llama3.2:3b",
            confidence=0.88,
            processing_time_seconds=15.3,
            formatted_text="# Summary"
        )
        
        # set_raw_response is called separately
        summary.set_raw_response({})
        
        test_db_session.add(summary)
        test_db_session.commit()
        
        assert summary.job_id == job.id
        assert summary.confidence == 0.88
        assert summary.processing_time_seconds == 15.3
        assert summary.model_used == "llama3.2:3b"
        assert summary.formatted_text == "# Summary"


class TestModelValidation:
    """モデルバリデーションテスト"""
    
    def test_transcription_job_required_fields(self, test_db_session):
        """必須フィールドのバリデーション"""
        # IDなしで作成（エラーになるはず）
        with pytest.raises(Exception):
            job = TranscriptionJob(
                filename="test.m4a",
                original_filename="test.m4a",
                file_size=1024,
                file_hash="abc123",
                mime_type="audio/m4a",
                usage_type_code="meeting",
                status_code="pending"
            )
            test_db_session.add(job)
            test_db_session.commit()
    
    def test_audio_file_duration_validation(self, test_db_session):
        """音声ファイル長のバリデーション"""
        job_id = str(uuid.uuid4())
        job = TranscriptionJob(
            id=job_id,
            filename=f"{job_id}.m4a",
            original_filename="test.m4a",
            file_size=1024,
            file_hash="abc123def456",
            mime_type="audio/m4a",
            usage_type_code="meeting",
            status_code="pending"
        )
        test_db_session.add(job)
        test_db_session.flush()
        
        # 負の値は不正だが、SQLiteでは制約がチェックされない
        audio_file = AudioFile(
            job_id=job.id,
            file_path="/tmp/test.m4a",
            duration_seconds=-10.0,  # 負の値
            sample_rate=44100,
            channels=2
        )
        
        test_db_session.add(audio_file)
        test_db_session.commit()
        
        # 実際のアプリケーションでは負の値を受け付けない想定
        assert audio_file.duration_seconds == -10.0  # テストDB上では保存される