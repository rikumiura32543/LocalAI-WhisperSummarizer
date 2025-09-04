"""
データベース関連テスト
"""

import pytest
import tempfile
import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.models.master import UsageType, JobStatus, FileFormat, SystemSetting
from app.models.transcription import TranscriptionJob, AudioFile, TranscriptionResult
from app.services.transcription_service import TranscriptionService
from app.core.migration import MigrationManager


@pytest.fixture
def test_db():
    """テスト用データベース設定"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
        test_db_path = temp_file.name
    
    # テスト用エンジン作成
    engine = create_engine(f"sqlite:///{test_db_path}", echo=False)
    Base.metadata.create_all(engine)
    
    # セッションファクトリ作成
    TestSession = sessionmaker(bind=engine)
    
    yield TestSession
    
    # クリーンアップ
    if os.path.exists(test_db_path):
        os.unlink(test_db_path)


@pytest.fixture
def session(test_db):
    """テスト用セッション"""
    session = test_db()
    yield session
    session.close()


def test_master_data_creation(session):
    """マスターデータ作成テスト"""
    # 使用用途マスター
    meeting_type = UsageType(code="meeting", name="会議", description="会議録作成用")
    session.add(meeting_type)
    
    # 処理状況マスター
    uploading_status = JobStatus(code="uploading", name="アップロード中", description="処理中")
    session.add(uploading_status)
    
    # ファイル形式マスター
    txt_format = FileFormat(code="txt", name="テキスト", mime_type="text/plain", extension=".txt")
    session.add(txt_format)
    
    # システム設定
    setting = SystemSetting(
        key="test_setting", 
        value="test_value", 
        data_type="string", 
        description="テスト設定"
    )
    session.add(setting)
    
    session.commit()
    
    # 検証
    assert session.query(UsageType).filter_by(code="meeting").first() is not None
    assert session.query(JobStatus).filter_by(code="uploading").first() is not None
    assert session.query(FileFormat).filter_by(code="txt").first() is not None
    assert session.query(SystemSetting).filter_by(key="test_setting").first() is not None


def test_transcription_job_creation(session):
    """転写ジョブ作成テスト"""
    # 前提データ作成
    usage_type = UsageType(code="meeting", name="会議", description="会議録作成用")
    status = JobStatus(code="uploading", name="アップロード中", description="処理中")
    session.add(usage_type)
    session.add(status)
    session.commit()
    
    # 転写ジョブ作成
    import uuid
    job_id = str(uuid.uuid4())
    
    job = TranscriptionJob(
        id=job_id,
        filename="test.m4a",
        original_filename="テスト音声.m4a",
        file_size=1024000,
        file_hash="dummy_hash",
        mime_type="audio/m4a",
        usage_type_code="meeting",
        status_code="uploading",
        progress=0
    )
    
    session.add(job)
    session.commit()
    
    # 検証
    saved_job = session.query(TranscriptionJob).filter_by(id=job_id).first()
    assert saved_job is not None
    assert saved_job.filename == "test.m4a"
    assert saved_job.original_filename == "テスト音声.m4a"
    assert saved_job.file_size == 1024000
    assert saved_job.usage_type_code == "meeting"
    assert saved_job.progress == 0


def test_audio_file_info_creation(session):
    """音声ファイル情報作成テスト"""
    # 前提データ作成
    usage_type = UsageType(code="meeting", name="会議", description="会議録作成用")
    status = JobStatus(code="uploading", name="アップロード中", description="処理中")
    session.add(usage_type)
    session.add(status)
    
    import uuid
    job_id = str(uuid.uuid4())
    
    job = TranscriptionJob(
        id=job_id,
        filename="test.m4a",
        original_filename="テスト音声.m4a",
        file_size=1024000,
        file_hash="dummy_hash",
        mime_type="audio/m4a",
        usage_type_code="meeting",
        status_code="uploading"
    )
    session.add(job)
    session.commit()
    
    # 音声ファイル情報作成
    audio_file = AudioFile(
        job_id=job_id,
        duration_seconds=120.5,
        bitrate=128000,
        sample_rate=44100,
        channels=2,
        file_path="/tmp/test.m4a"
    )
    
    # フォーマット詳細設定
    audio_file.set_format_details({
        "codec": "aac",
        "container": "m4a",
        "quality": "high"
    })
    
    session.add(audio_file)
    session.commit()
    
    # 検証
    saved_audio = session.query(AudioFile).filter_by(job_id=job_id).first()
    assert saved_audio is not None
    assert saved_audio.duration_seconds == 120.5
    assert saved_audio.bitrate == 128000
    assert saved_audio.sample_rate == 44100
    assert saved_audio.channels == 2
    
    # フォーマット詳細検証
    format_details = saved_audio.get_format_details()
    assert format_details["codec"] == "aac"
    assert format_details["container"] == "m4a"
    assert format_details["quality"] == "high"


def test_transcription_result_creation(session):
    """転写結果作成テスト"""
    # 前提データ作成
    usage_type = UsageType(code="meeting", name="会議", description="会議録作成用")
    status = JobStatus(code="completed", name="完了", description="処理完了")
    session.add(usage_type)
    session.add(status)
    
    import uuid
    job_id = str(uuid.uuid4())
    
    job = TranscriptionJob(
        id=job_id,
        filename="test.m4a",
        original_filename="テスト音声.m4a",
        file_size=1024000,
        file_hash="dummy_hash",
        mime_type="audio/m4a",
        usage_type_code="meeting",
        status_code="completed"
    )
    session.add(job)
    session.commit()
    
    # 転写結果作成
    result = TranscriptionResult(
        job_id=job_id,
        text="これはテスト用の転写結果です。音声認識により生成されました。",
        confidence=0.95,
        language="ja",
        duration_seconds=120.5,
        model_used="whisper-base",
        processing_time_seconds=45.2,
        segments_count=5
    )
    
    session.add(result)
    session.commit()
    
    # 検証
    saved_result = session.query(TranscriptionResult).filter_by(job_id=job_id).first()
    assert saved_result is not None
    assert saved_result.confidence == 0.95
    assert saved_result.language == "ja"
    assert saved_result.model_used == "whisper-base"
    assert saved_result.text_length > 0
    assert saved_result.words_per_minute > 0


def test_system_setting_typed_values():
    """システム設定の型変換テスト"""
    # 文字列設定
    str_setting = SystemSetting(
        key="str_test", 
        value="hello", 
        data_type="string", 
        description="文字列テスト"
    )
    assert str_setting.get_typed_value() == "hello"
    
    # 整数設定
    int_setting = SystemSetting(
        key="int_test", 
        value="42", 
        data_type="integer", 
        description="整数テスト"
    )
    assert int_setting.get_typed_value() == 42
    
    # 浮動小数点設定
    float_setting = SystemSetting(
        key="float_test", 
        value="3.14", 
        data_type="float", 
        description="浮動小数点テスト"
    )
    assert float_setting.get_typed_value() == 3.14
    
    # ブール設定
    bool_setting_true = SystemSetting(
        key="bool_test", 
        value="true", 
        data_type="boolean", 
        description="ブールテスト"
    )
    assert bool_setting_true.get_typed_value() is True
    
    bool_setting_false = SystemSetting(
        key="bool_test2", 
        value="false", 
        data_type="boolean", 
        description="ブールテスト2"
    )
    assert bool_setting_false.get_typed_value() is False
    
    # JSON設定
    json_setting = SystemSetting(
        key="json_test", 
        value='["ja", "en"]', 
        data_type="json", 
        description="JSONテスト"
    )
    assert json_setting.get_typed_value() == ["ja", "en"]


def test_transcription_service_integration(session):
    """転写サービス統合テスト"""
    # マスターデータ作成
    usage_type = UsageType(code="meeting", name="会議", description="会議録作成用")
    uploading_status = JobStatus(code="uploading", name="アップロード中", description="処理中")
    completed_status = JobStatus(code="completed", name="完了", description="処理完了")
    
    session.add(usage_type)
    session.add(uploading_status)
    session.add(completed_status)
    session.commit()
    
    # 転写サービス使用
    service = TranscriptionService(session)
    
    # ジョブ作成
    test_content = b"dummy audio content"
    job = service.create_job(
        original_filename="テスト会議.m4a",
        file_content=test_content,
        usage_type_code="meeting"
    )
    
    assert job is not None
    assert job.original_filename == "テスト会議.m4a"
    assert job.file_size == len(test_content)
    assert job.usage_type_code == "meeting"
    assert job.status_code == "uploading"
    
    # ステータス更新
    success = service.update_job_status(
        job_id=job.id,
        status="transcribing",
        progress=50,
        message="転写処理中..."
    )
    
    assert success is True
    
    updated_job = service.get_job(job.id)
    assert updated_job.status_code == "transcribing"
    assert updated_job.progress == 50
    assert updated_job.message == "転写処理中..."
    
    # 音声情報保存
    audio_success = service.save_audio_info(
        job_id=job.id,
        file_path=f"/tmp/{job.filename}",
        duration_seconds=180.0,
        bitrate=128000,
        sample_rate=44100,
        channels=1
    )
    
    assert audio_success is True
    
    # 転写結果保存
    segments = [
        {"start": 0.0, "end": 5.0, "text": "こんにちは", "confidence": 0.9},
        {"start": 5.0, "end": 10.0, "text": "今日の会議を始めます", "confidence": 0.95}
    ]
    
    transcription_success = service.save_transcription_result(
        job_id=job.id,
        text="こんにちは。今日の会議を始めます。",
        confidence=0.92,
        language="ja",
        duration_seconds=180.0,
        model_used="whisper-base",
        processing_time_seconds=45.0,
        segments=segments
    )
    
    assert transcription_success is True
    
    # 結果取得確認
    result = service.get_transcription_result(job.id)
    assert result is not None
    assert result.confidence == 0.92
    assert result.language == "ja"
    
    segments_result = service.get_transcription_segments(job.id)
    assert len(segments_result) == 2
    assert segments_result[0].text == "こんにちは"
    assert segments_result[1].text == "今日の会議を始めます"
    
    # 統計情報取得
    stats = service.get_job_statistics()
    assert stats["total_jobs"] >= 1
    assert "uploading" in stats["status_distribution"] or "transcribing" in stats["status_distribution"]


@pytest.mark.skip(reason="実際のファイルシステムが必要")
def test_migration_system():
    """マイグレーションシステムテスト"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
        test_db_path = temp_file.name
    
    try:
        # テスト用エンジン作成
        os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"
        
        migration_manager = MigrationManager()
        
        # マイグレーション実行
        success = migration_manager.migrate_up()
        assert success is True
        
        # 適用済みマイグレーション確認
        applied = migration_manager.get_applied_migrations()
        assert len(applied) > 0
        
        # 未適用マイグレーション確認（すべて適用済みのはず）
        pending = migration_manager.get_pending_migrations()
        assert len(pending) == 0
        
        # スキーマ情報確認
        schema_info = migration_manager.get_schema_info()
        assert "transcription_jobs" in schema_info["tables"]
        assert len(schema_info["applied_migrations"]) > 0
        
    finally:
        if os.path.exists(test_db_path):
            os.unlink(test_db_path)