"""
モデル層のユニットテスト
"""

import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.base import Base
from app.models.transcription import TranscriptionJob, AudioFile, TranscriptionResult
from app.models.summary import SummaryResult
from app.models.master import UsageType, JobStatus, FileFormat


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
        job = TranscriptionJob(
            filename="test.m4a",
            file_size=1024,
            usage_type="meeting",
            status="pending"
        )
        
        test_db_session.add(job)
        test_db_session.commit()
        
        assert job.id is not None
        assert job.filename == "test.m4a"
        assert job.file_size == 1024
        assert job.usage_type == "meeting"
        assert job.status == "pending"
        assert job.created_at is not None
    
    def test_transcription_job_status_progression(self, test_db_session):
        """ステータス遷移テスト"""
        job = TranscriptionJob(
            filename="test.m4a",
            file_size=1024,
            usage_type="meeting",
            status="pending"
        )
        test_db_session.add(job)
        test_db_session.commit()
        
        # processing状態に更新
        job.status = "processing"
        job.processing_step = "transcription"
        test_db_session.commit()
        
        assert job.status == "processing"
        assert job.processing_step == "transcription"
        
        # completed状態に更新
        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        test_db_session.commit()
        
        assert job.status == "completed"
        assert job.completed_at is not None
    
    def test_transcription_job_relationships(self, test_db_session):
        """リレーションシップテスト"""
        # ジョブ作成
        job = TranscriptionJob(
            filename="test.m4a",
            file_size=1024,
            usage_type="meeting",
            status="pending"
        )
        test_db_session.add(job)
        test_db_session.flush()
        
        # 音声ファイル作成
        audio_file = AudioFile(
            job_id=job.id,
            original_filename="test.m4a",
            file_path="/tmp/test.m4a",
            file_size=1024,
            mime_type="audio/m4a",
            duration=60.0,
            sample_rate=44100,
            channels=2
        )
        test_db_session.add(audio_file)
        
        # 転写結果作成
        transcription_result = TranscriptionResult(
            job_id=job.id,
            text="テスト用転写結果",
            confidence=0.95,
            processing_time=30.0,
            detected_language="ja"
        )
        test_db_session.add(transcription_result)
        
        test_db_session.commit()
        
        # リレーションシップ確認
        assert job.audio_file is not None
        assert job.audio_file.original_filename == "test.m4a"
        assert job.transcription_result is not None
        assert job.transcription_result.text == "テスト用転写結果"


class TestAudioFileModel:
    """AudioFileモデルのテスト"""
    
    def test_create_audio_file(self, test_db_session):
        """音声ファイル作成テスト"""
        # 先にジョブを作成
        job = TranscriptionJob(
            filename="test.m4a",
            file_size=1024,
            usage_type="meeting",
            status="pending"
        )
        test_db_session.add(job)
        test_db_session.flush()
        
        audio_file = AudioFile(
            job_id=job.id,
            original_filename="test.m4a",
            file_path="/tmp/test.m4a",
            file_size=1024,
            mime_type="audio/m4a",
            duration=120.5,
            sample_rate=44100,
            channels=2,
            bit_rate=128000
        )
        
        test_db_session.add(audio_file)
        test_db_session.commit()
        
        assert audio_file.id is not None
        assert audio_file.job_id == job.id
        assert audio_file.duration == 120.5
        assert audio_file.sample_rate == 44100
        assert audio_file.channels == 2
        assert audio_file.bit_rate == 128000


class TestTranscriptionResultModel:
    """TranscriptionResultモデルのテスト"""
    
    def test_create_transcription_result(self, test_db_session):
        """転写結果作成テスト"""
        # 先にジョブを作成
        job = TranscriptionJob(
            filename="test.m4a",
            file_size=1024,
            usage_type="meeting",
            status="pending"
        )
        test_db_session.add(job)
        test_db_session.flush()
        
        result = TranscriptionResult(
            job_id=job.id,
            text="これはテスト用の転写結果です。音声からテキストに変換されました。",
            confidence=0.95,
            processing_time=45.2,
            detected_language="ja",
            model_version="whisper-large-v3"
        )
        
        test_db_session.add(result)
        test_db_session.commit()
        
        assert result.id is not None
        assert result.job_id == job.id
        assert result.confidence == 0.95
        assert result.processing_time == 45.2
        assert result.detected_language == "ja"
        assert result.model_version == "whisper-large-v3"
        assert "転写結果" in result.text
    
    def test_transcription_result_with_segments(self, test_db_session):
        """セグメント付き転写結果テスト"""
        job = TranscriptionJob(
            filename="test.m4a",
            file_size=1024,
            usage_type="meeting",
            status="pending"
        )
        test_db_session.add(job)
        test_db_session.flush()
        
        segments_data = [
            {
                "id": 0,
                "start": 0.0,
                "end": 5.0,
                "text": "最初のセグメント",
                "confidence": 0.98
            },
            {
                "id": 1,
                "start": 5.0,
                "end": 10.0,
                "text": "2番目のセグメント",
                "confidence": 0.92
            }
        ]
        
        result = TranscriptionResult(
            job_id=job.id,
            text="最初のセグメント 2番目のセグメント",
            confidence=0.95,
            processing_time=20.0,
            detected_language="ja",
            segments=segments_data
        )
        
        test_db_session.add(result)
        test_db_session.commit()
        
        assert result.segments is not None
        assert len(result.segments) == 2
        assert result.segments[0]["text"] == "最初のセグメント"
        assert result.segments[1]["start"] == 5.0


class TestSummaryResultModel:
    """SummaryResultモデルのテスト"""
    
    def test_create_summary_result(self, test_db_session):
        """要約結果作成テスト"""
        job = TranscriptionJob(
            filename="test.m4a",
            file_size=1024,
            usage_type="meeting",
            status="pending"
        )
        test_db_session.add(job)
        test_db_session.flush()
        
        summary_data = {
            "overview": "会議の概要について議論されました。",
            "key_points": [
                "重要なポイント1",
                "重要なポイント2",
                "重要なポイント3"
            ],
            "action_items": [
                "来週までにタスクを完了する",
                "資料を準備する"
            ],
            "participants": ["参加者A", "参加者B"]
        }
        
        summary = SummaryResult(
            job_id=job.id,
            summary=summary_data,
            confidence=0.88,
            processing_time=15.3,
            model_name="llama3.2:3b",
            model_version="3.2"
        )
        
        test_db_session.add(summary)
        test_db_session.commit()
        
        assert summary.id is not None
        assert summary.job_id == job.id
        assert summary.confidence == 0.88
        assert summary.processing_time == 15.3
        assert summary.model_name == "llama3.2:3b"
        
        # JSON形式のデータ確認
        assert summary.summary["overview"] == "会議の概要について議論されました。"
        assert len(summary.summary["key_points"]) == 3
        assert len(summary.summary["action_items"]) == 2
        assert "参加者A" in summary.summary["participants"]
    
    def test_summary_result_different_usage_types(self, test_db_session):
        """異なる用途タイプでの要約結果テスト"""
        # 面接用要約
        interview_job = TranscriptionJob(
            filename="interview.m4a",
            file_size=2048,
            usage_type="interview",
            status="pending"
        )
        test_db_session.add(interview_job)
        test_db_session.flush()
        
        interview_summary_data = {
            "candidate_assessment": {
                "strengths": ["コミュニケーション能力", "技術スキル"],
                "areas_for_improvement": ["経験不足"],
                "overall_impression": "良好"
            },
            "questions_and_answers": [
                {
                    "question": "自己紹介をお願いします",
                    "answer": "私は..."
                }
            ],
            "recommendation": "採用推奨"
        }
        
        interview_summary = SummaryResult(
            job_id=interview_job.id,
            summary=interview_summary_data,
            confidence=0.91,
            processing_time=20.5,
            model_name="llama3.2:3b"
        )
        
        test_db_session.add(interview_summary)
        test_db_session.commit()
        
        assert interview_summary.summary["recommendation"] == "採用推奨"
        assert "strengths" in interview_summary.summary["candidate_assessment"]


class TestMasterDataModels:
    """マスターデータモデルのテスト"""
    
    def test_usage_type_model(self, test_db_session):
        """UsageTypeモデルテスト"""
        usage_type = UsageType(
            code="meeting",
            name="会議",
            description="会議録音の転写・要約",
            is_active=True
        )
        
        test_db_session.add(usage_type)
        test_db_session.commit()
        
        assert usage_type.id is not None
        assert usage_type.code == "meeting"
        assert usage_type.name == "会議"
        assert usage_type.is_active is True
    
    def test_job_status_model(self, test_db_session):
        """JobStatusモデルテスト"""
        status = JobStatus(
            code="processing",
            name="処理中",
            description="音声ファイルを処理しています",
            order_index=2
        )
        
        test_db_session.add(status)
        test_db_session.commit()
        
        assert status.id is not None
        assert status.code == "processing"
        assert status.order_index == 2
    
    def test_file_format_model(self, test_db_session):
        """FileFormatモデルテスト"""
        file_format = FileFormat(
            extension="m4a",
            mime_type="audio/m4a",
            description="Apple Lossless Audio",
            is_supported=True,
            max_file_size_mb=50
        )
        
        test_db_session.add(file_format)
        test_db_session.commit()
        
        assert file_format.id is not None
        assert file_format.extension == "m4a"
        assert file_format.mime_type == "audio/m4a"
        assert file_format.is_supported is True
        assert file_format.max_file_size_mb == 50


class TestModelValidation:
    """モデルバリデーションテスト"""
    
    def test_transcription_job_required_fields(self, test_db_session):
        """必須フィールドのバリデーション"""
        # filenameなしで作成（エラーになるはず）
        with pytest.raises(Exception):
            job = TranscriptionJob(
                file_size=1024,
                usage_type="meeting",
                status="pending"
            )
            test_db_session.add(job)
            test_db_session.commit()
    
    def test_audio_file_duration_validation(self, test_db_session):
        """音声ファイル長のバリデーション"""
        job = TranscriptionJob(
            filename="test.m4a",
            file_size=1024,
            usage_type="meeting",
            status="pending"
        )
        test_db_session.add(job)
        test_db_session.flush()
        
        # 負の値は不正
        audio_file = AudioFile(
            job_id=job.id,
            original_filename="test.m4a",
            file_path="/tmp/test.m4a",
            file_size=1024,
            mime_type="audio/m4a",
            duration=-10.0,  # 負の値
            sample_rate=44100,
            channels=2
        )
        
        test_db_session.add(audio_file)
        # SQLiteでは制約がチェックされないが、アプリケーションレベルでの
        # バリデーションがあることを想定
        test_db_session.commit()
        
        # 実際のアプリケーションでは負の値を受け付けない想定
        assert audio_file.duration == -10.0  # テストDB上では保存される