#!/usr/bin/env python3
"""
データベース初期化スクリプト

使用方法:
    python scripts/init_db.py            # データベース初期化
    python scripts/init_db.py --reset    # データベースリセット（危険）
    python scripts/init_db.py --seed     # テストデータ投入
"""

import sys
import os
import argparse
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.models import (
    Base, create_tables, drop_tables, get_engine,
    UsageType, JobStatus, FileFormat, SystemSetting, OllamaModel
)
from sqlalchemy.orm import sessionmaker


def init_database():
    """データベース初期化"""
    print("🗄️  データベースを初期化中...")
    
    # テーブル作成
    create_tables()
    print("✅ テーブルが作成されました")
    
    # マスターデータ投入
    insert_master_data()
    print("✅ マスターデータが投入されました")


def reset_database():
    """データベースリセット（全削除後再作成）"""
    print("⚠️  データベースをリセット中...")
    print("⚠️  すべてのデータが削除されます！")
    
    response = input("続行しますか？ (yes/no): ")
    if response.lower() != 'yes':
        print("❌ リセットをキャンセルしました")
        return
    
    # テーブル削除
    drop_tables()
    print("🗑️  既存テーブルが削除されました")
    
    # 再初期化
    init_database()


def insert_master_data():
    """マスターデータ投入"""
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    
    with Session() as session:
        try:
            # 使用用途マスター
            usage_types = [
                UsageType(code="meeting", name="会議", description="会議録作成用"),
                UsageType(code="interview", name="面接", description="面接記録作成用"),
            ]
            
            for usage_type in usage_types:
                existing = session.query(UsageType).filter_by(code=usage_type.code).first()
                if not existing:
                    session.add(usage_type)
            
            # 処理状況マスター
            job_statuses = [
                JobStatus(code="uploading", name="アップロード中", description="ファイルアップロード処理中"),
                JobStatus(code="transcribing", name="転写中", description="音声転写処理中"),
                JobStatus(code="summarizing", name="要約中", description="AI要約生成中"),
                JobStatus(code="completed", name="完了", description="処理完了"),
                JobStatus(code="error", name="エラー", description="処理エラー"),
            ]
            
            for job_status in job_statuses:
                existing = session.query(JobStatus).filter_by(code=job_status.code).first()
                if not existing:
                    session.add(job_status)
            
            # ファイル形式マスター
            file_formats = [
                FileFormat(code="txt", name="テキスト", mime_type="text/plain", extension=".txt"),
                FileFormat(code="json", name="JSON", mime_type="application/json", extension=".json"),
                FileFormat(code="csv", name="CSV", mime_type="text/csv", extension=".csv"),
            ]
            
            for file_format in file_formats:
                existing = session.query(FileFormat).filter_by(code=file_format.code).first()
                if not existing:
                    session.add(file_format)
            
            # システム設定初期値
            system_settings = [
                SystemSetting(key="max_file_size_mb", value="50", data_type="integer", 
                             description="最大ファイルサイズ（MB）"),
                SystemSetting(key="default_ollama_model", value="llama2:7b", data_type="string", 
                             description="デフォルトOllamaモデル"),
                SystemSetting(key="transcription_timeout_seconds", value="900", data_type="integer", 
                             description="転写処理タイムアウト（秒）"),
                SystemSetting(key="summary_timeout_seconds", value="300", data_type="integer", 
                             description="AI要約処理タイムアウト（秒）"),
                SystemSetting(key="file_retention_days", value="7", data_type="integer", 
                             description="ファイル保持期間（日）"),
                SystemSetting(key="enable_speaker_detection", value="false", data_type="boolean", 
                             description="話者識別機能有効フラグ"),
                SystemSetting(key="supported_languages", value='["ja", "en"]', data_type="json", 
                             description="サポート言語"),
                SystemSetting(key="ui_theme", value="light", data_type="string", description="UIテーマ"),
                SystemSetting(key="accessibility_mode", value="true", data_type="boolean", 
                             description="アクセシビリティモード"),
            ]
            
            for setting in system_settings:
                existing = session.query(SystemSetting).filter_by(key=setting.key).first()
                if not existing:
                    session.add(setting)
            
            # デフォルトOllamaモデル
            ollama_models = [
                OllamaModel(
                    name="llama2:7b",
                    size_bytes=3800000000,  # 約3.8GB
                    description="Llama 2 7Bモデル - 軽量で高速",
                    language_codes='["ja", "en"]',
                    is_active=True,
                    memory_usage_mb=4096
                ),
            ]
            
            for model in ollama_models:
                existing = session.query(OllamaModel).filter_by(name=model.name).first()
                if not existing:
                    session.add(model)
            
            session.commit()
            print("📊 マスターデータが正常に投入されました")
            
        except Exception as e:
            session.rollback()
            print(f"❌ マスターデータ投入エラー: {e}")
            raise


def seed_test_data():
    """テストデータ投入"""
    print("🌱 テストデータを投入中...")
    
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    
    with Session() as session:
        try:
            from app.models import TranscriptionJob, AudioFile, TranscriptionResult
            import uuid
            from datetime import datetime, timedelta
            
            # テスト用転写ジョブ
            test_jobs = [
                {
                    "id": str(uuid.uuid4()),
                    "filename": "test_meeting_001.m4a",
                    "original_filename": "週次ミーティング_2024-01-15.m4a",
                    "file_size": 5242880,  # 5MB
                    "file_hash": "dummy_hash_001",
                    "mime_type": "audio/m4a",
                    "usage_type_code": "meeting",
                    "status_code": "completed",
                    "progress": 100,
                    "message": "処理完了",
                    "processing_started_at": datetime.utcnow() - timedelta(minutes=10),
                    "processing_completed_at": datetime.utcnow() - timedelta(minutes=5),
                },
                {
                    "id": str(uuid.uuid4()),
                    "filename": "test_interview_001.m4a",
                    "original_filename": "面接記録_田中太郎.m4a",
                    "file_size": 8388608,  # 8MB
                    "file_hash": "dummy_hash_002",
                    "mime_type": "audio/m4a",
                    "usage_type_code": "interview",
                    "status_code": "transcribing",
                    "progress": 65,
                    "message": "転写処理中...",
                    "processing_started_at": datetime.utcnow() - timedelta(minutes=5),
                },
            ]
            
            for job_data in test_jobs:
                # 既存チェック
                existing_job = session.query(TranscriptionJob).filter_by(id=job_data["id"]).first()
                if existing_job:
                    continue
                    
                # ジョブ作成
                job = TranscriptionJob(**job_data)
                session.add(job)
                session.flush()  # IDを取得するため
                
                # 音声ファイル情報を追加（完了済みジョブのみ）
                if job.status_code == "completed":
                    audio_file = AudioFile(
                        job_id=job.id,
                        duration_seconds=180.5,
                        bitrate=128000,
                        sample_rate=44100,
                        channels=1,
                        format_details='{"codec": "aac", "container": "m4a"}',
                        file_path=f"/app/uploads/{job.filename}"
                    )
                    session.add(audio_file)
                    
                    # 転写結果を追加
                    transcription_result = TranscriptionResult(
                        job_id=job.id,
                        text="これはテスト用の転写結果です。実際のシステムでは、ここに音声から転写されたテキストが表示されます。",
                        confidence=0.92,
                        language="ja",
                        duration_seconds=180.5,
                        model_used="whisper-base",
                        processing_time_seconds=45.2,
                        segments_count=15
                    )
                    session.add(transcription_result)
            
            session.commit()
            print("✅ テストデータが正常に投入されました")
            
        except Exception as e:
            session.rollback()
            print(f"❌ テストデータ投入エラー: {e}")
            raise


def main():
    """メイン処理"""
    parser = argparse.ArgumentParser(description="M4A転写システム データベース初期化")
    parser.add_argument("--reset", action="store_true", help="データベースをリセット（危険）")
    parser.add_argument("--seed", action="store_true", help="テストデータを投入")
    
    args = parser.parse_args()
    
    try:
        if args.reset:
            reset_database()
        else:
            init_database()
        
        if args.seed:
            seed_test_data()
        
        print("🎉 データベース初期化が完了しました！")
        
    except Exception as e:
        print(f"💥 エラーが発生しました: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()