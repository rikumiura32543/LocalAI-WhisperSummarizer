"""
テストデータとフィクスチャの定義
"""

import pytest
import tempfile
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any
import uuid


class TestDataGenerator:
    """テストデータ生成クラス"""
    
    @staticmethod
    def create_sample_m4a_content() -> bytes:
        """サンプルM4Aファイル内容生成"""
        # M4Aの最小ヘッダー
        ftyp_box = (
            b'\\x00\\x00\\x00\\x20'  # サイズ（32バイト）
            b'ftyp'                 # ボックスタイプ
            b'M4A '                 # メジャーブランド
            b'\\x00\\x00\\x00\\x00'    # マイナーバージョン
            b'M4A mp42isom'         # 互換ブランド
        )
        
        moov_box = (
            b'\\x00\\x00\\x00\\x28'    # サイズ（40バイト）
            b'moov'                 # ボックスタイプ
            b'\\x00\\x00\\x00\\x20'    # mvhdサイズ
            b'mvhd'                 # ムービーヘッダー
            b'\\x00\\x00\\x00\\x00'    # バージョン・フラグ
            b'\\x00\\x00\\x00\\x00'    # 作成日時
            b'\\x00\\x00\\x00\\x00'    # 更新日時
            b'\\x00\\x00\\x03\\xe8'    # タイムスケール（1000）
            b'\\x00\\x00\\x00\\x00'    # 継続時間
            b'\\x00\\x01\\x00\\x00'    # 再生レート
            b'\\x01\\x00'            # ボリューム
        )
        
        # ダミーオーディオデータ
        audio_data = b'\\x00' * 1024
        
        return ftyp_box + moov_box + audio_data
    
    @staticmethod
    def create_sample_transcription_result() -> Dict[str, Any]:
        """サンプル転写結果生成"""
        return {
            "text": "これはテスト用の転写結果です。音声認識システムが正常に動作していることを確認するためのサンプルテキストです。日本語の音声を適切に認識し、テキストに変換することができています。",
            "language": "ja",
            "confidence": 0.95,
            "processing_time": 12.5,
            "detected_language": "ja",
            "segments": [
                {
                    "id": 0,
                    "start": 0.0,
                    "end": 3.5,
                    "text": "これはテスト用の転写結果です。",
                    "confidence": 0.98
                },
                {
                    "id": 1,
                    "start": 3.5,
                    "end": 8.0,
                    "text": "音声認識システムが正常に動作していることを確認するためのサンプルテキストです。",
                    "confidence": 0.94
                },
                {
                    "id": 2,
                    "start": 8.0,
                    "end": 12.0,
                    "text": "日本語の音声を適切に認識し、テキストに変換することができています。",
                    "confidence": 0.96
                }
            ]
        }
    
    @staticmethod
    def create_sample_meeting_summary() -> Dict[str, Any]:
        """サンプル会議要約生成"""
        return {
            "overview": "M4A転写システムのテスト実施に関する会議。システムの品質保証と機能検証について議論し、今後の開発方針を決定した。",
            "key_points": [
                "転写機能の精度が期待値（95%以上）を満たしていることを確認",
                "AI要約機能が会議、面接、講義の各用途に適切に対応できている",
                "レスポンス時間が要求仕様（平均30秒以内）を満たしている",
                "エラーハンドリングが適切に実装されている"
            ],
            "action_items": [
                "パフォーマンステストの実施と結果分析",
                "ユーザビリティテストの計画立案",
                "本番環境へのデプロイメント準備",
                "運用ドキュメントの作成"
            ],
            "participants": [
                "プロジェクトマネージャー",
                "シニアエンジニア",
                "QAエンジニア",
                "デザイナー"
            ],
            "next_meeting": "来週金曜日 14:00",
            "duration_minutes": 45
        }
    
    @staticmethod
    def create_sample_interview_summary() -> Dict[str, Any]:
        """サンプル面接要約生成"""
        return {
            "candidate_assessment": {
                "strengths": [
                    "技術的な理解力が高い",
                    "コミュニケーション能力に優れている",
                    "問題解決能力が高い",
                    "学習意欲が旺盛"
                ],
                "areas_for_improvement": [
                    "大規模システムでの実務経験がやや不足",
                    "プロジェクト管理経験を積む必要がある"
                ],
                "technical_skills": {
                    "programming": ["Python", "JavaScript", "SQL"],
                    "frameworks": ["FastAPI", "React", "Django"],
                    "tools": ["Git", "Docker", "AWS"],
                    "databases": ["PostgreSQL", "MongoDB", "Redis"]
                },
                "overall_impression": "非常に優秀な候補者。技術力と人柄の両面で高い評価"
            },
            "questions_and_answers": [
                {
                    "question": "これまでの開発経験について教えてください",
                    "answer": "Webアプリケーションの開発を3年間経験しており、特にPythonとJavaScriptを使用したフルスタック開発が得意です",
                    "evaluation": "具体的で説得力のある回答"
                },
                {
                    "question": "困難な技術的課題をどのように解決しますか",
                    "answer": "まず問題を細分化し、調査と検証を繰り返しながら段階的にアプローチします",
                    "evaluation": "体系的な問題解決アプローチを示している"
                }
            ],
            "recommendation": "強く採用を推奨",
            "recommended_position": "ミドルレベル・フルスタックエンジニア",
            "salary_range": "600-800万円",
            "next_steps": [
                "チーム面接の実施",
                "技術課題の提示",
                "リファレンスチェック"
            ]
        }
    
    @staticmethod
    def create_sample_lecture_summary() -> Dict[str, Any]:
        """サンプル講義要約生成"""
        return {
            "lecture_info": {
                "title": "機械学習入門",
                "instructor": "田中教授",
                "duration_minutes": 90,
                "topic": "教師あり学習の基礎"
            },
            "key_concepts": [
                "機械学習の定義と分類",
                "教師あり学習vs教師なし学習",
                "特徴量エンジニアリングの重要性",
                "過学習の問題とその対策",
                "交差検証による性能評価"
            ],
            "important_points": [
                "データの質が機械学習の成功を大きく左右する",
                "アルゴリズムの選択よりもデータの前処理が重要",
                "モデルの解釈可能性も性能と同様に重要",
                "実際の問題では完璧な解よりも実用的な解が求められる"
            ],
            "examples_discussed": [
                "線形回帰による住宅価格予測",
                "決定木による顧客分類",
                "ランダムフォレストによる信用リスク評価"
            ],
            "assignments": [
                "次回までにscikit-learnをインストール",
                "配布資料の演習問題1-5を解く",
                "推奨図書の第3章を読む"
            ],
            "next_lecture": "来週：教師なし学習（クラスタリング）"
        }
    
    @staticmethod
    def create_sample_job_data(usage_type: str = "meeting") -> Dict[str, Any]:
        """サンプルジョブデータ生成"""
        job_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        
        return {
            "id": job_id,
            "filename": f"sample_{usage_type}.m4a",
            "file_size": 2048576,  # 2MB
            "usage_type": usage_type,
            "status": "pending",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "processing_step": None,
            "processing_duration": None,
            "audio_duration": 120.0,  # 2分
            "detected_language": "ja",
            "confidence": None,
            "error_message": None
        }
    
    @staticmethod
    def create_audio_file_metadata() -> Dict[str, Any]:
        """音声ファイルメタデータ生成"""
        return {
            "original_filename": "sample_audio.m4a",
            "file_path": "/tmp/uploaded/sample_audio_123.m4a",
            "file_size": 2048576,
            "mime_type": "audio/m4a",
            "duration": 120.0,
            "sample_rate": 44100,
            "channels": 2,
            "bit_rate": 128000,
            "codec": "AAC"
        }


@pytest.fixture
def sample_m4a_file():
    """サンプルM4Aファイルのフィクスチャ"""
    content = TestDataGenerator.create_sample_m4a_content()
    
    with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as f:
        f.write(content)
        f.flush()
        yield f.name
    
    # クリーンアップ
    try:
        Path(f.name).unlink()
    except FileNotFoundError:
        pass


@pytest.fixture
def large_m4a_file():
    """大きなM4Aファイルのフィクスチャ（テスト用）"""
    content = TestDataGenerator.create_sample_m4a_content()
    # 5MB相当のファイルを作成
    large_content = content + (b'\\x00' * (5 * 1024 * 1024))
    
    with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as f:
        f.write(large_content)
        f.flush()
        yield f.name
    
    try:
        Path(f.name).unlink()
    except FileNotFoundError:
        pass


@pytest.fixture
def sample_transcription_result():
    """サンプル転写結果のフィクスチャ"""
    return TestDataGenerator.create_sample_transcription_result()


@pytest.fixture
def sample_meeting_summary():
    """サンプル会議要約のフィクスチャ"""
    return TestDataGenerator.create_sample_meeting_summary()


@pytest.fixture
def sample_interview_summary():
    """サンプル面接要約のフィクスチャ"""
    return TestDataGenerator.create_sample_interview_summary()


@pytest.fixture
def sample_lecture_summary():
    """サンプル講義要約のフィクスチャ"""
    return TestDataGenerator.create_sample_lecture_summary()


@pytest.fixture(params=["meeting", "interview", "lecture", "other"])
def sample_job_data(request):
    """パラメータ化されたジョブデータのフィクスチャ"""
    return TestDataGenerator.create_sample_job_data(request.param)


@pytest.fixture
def audio_file_metadata():
    """音声ファイルメタデータのフィクスチャ"""
    return TestDataGenerator.create_audio_file_metadata()


@pytest.fixture
def mock_whisper_responses():
    """Whisperサービスのモックレスポンス集"""
    return {
        "successful_transcription": {
            "text": "音声認識が正常に動作しています。",
            "language": "ja",
            "segments": [
                {
                    "id": 0,
                    "start": 0.0,
                    "end": 3.0,
                    "text": "音声認識が正常に動作しています。"
                }
            ]
        },
        "english_transcription": {
            "text": "This is an English transcription test.",
            "language": "en",
            "segments": [
                {
                    "id": 0,
                    "start": 0.0,
                    "end": 2.5,
                    "text": "This is an English transcription test."
                }
            ]
        },
        "low_confidence": {
            "text": "不明確な音声です",
            "language": "ja",
            "segments": []
        }
    }


@pytest.fixture
def mock_ollama_responses():
    """Ollamaサービスのモックレスポンス集"""
    return {
        "meeting_summary": TestDataGenerator.create_sample_meeting_summary(),
        "interview_summary": TestDataGenerator.create_sample_interview_summary(),
        "lecture_summary": TestDataGenerator.create_sample_lecture_summary(),
        "error_response": None,
        "timeout_response": None
    }


@pytest.fixture
def test_file_uploads():
    """テスト用ファイルアップロードデータ"""
    m4a_content = TestDataGenerator.create_sample_m4a_content()
    
    return {
        "valid_m4a": {
            "filename": "test.m4a",
            "content": m4a_content,
            "content_type": "audio/m4a"
        },
        "valid_mp4": {
            "filename": "test.mp4",
            "content": m4a_content,  # 同じ内容でMP4として扱う
            "content_type": "audio/mp4"
        },
        "invalid_txt": {
            "filename": "test.txt",
            "content": b"This is not an audio file",
            "content_type": "text/plain"
        },
        "invalid_large": {
            "filename": "large.m4a",
            "content": b'\\x00' * (100 * 1024 * 1024),  # 100MB
            "content_type": "audio/m4a"
        }
    }


@pytest.fixture
def database_test_data():
    """データベーステスト用のデータセット"""
    return {
        "usage_types": [
            {"code": "meeting", "name": "会議", "description": "会議の録音", "is_active": True},
            {"code": "interview", "name": "面接", "description": "面接の録音", "is_active": True},
            {"code": "lecture", "name": "講義", "description": "講義の録音", "is_active": True},
            {"code": "other", "name": "その他", "description": "その他の用途", "is_active": True}
        ],
        "job_statuses": [
            {"code": "pending", "name": "待機中", "description": "処理待ち", "order_index": 1},
            {"code": "processing", "name": "処理中", "description": "音声処理実行中", "order_index": 2},
            {"code": "completed", "name": "完了", "description": "処理完了", "order_index": 3},
            {"code": "failed", "name": "失敗", "description": "処理失敗", "order_index": 4}
        ],
        "file_formats": [
            {"extension": "m4a", "mime_type": "audio/m4a", "description": "M4A Audio", "is_supported": True, "max_file_size_mb": 50},
            {"extension": "mp4", "mime_type": "audio/mp4", "description": "MP4 Audio", "is_supported": True, "max_file_size_mb": 50},
            {"extension": "wav", "mime_type": "audio/wav", "description": "WAV Audio", "is_supported": True, "max_file_size_mb": 100},
            {"extension": "mp3", "mime_type": "audio/mpeg", "description": "MP3 Audio", "is_supported": True, "max_file_size_mb": 50}
        ]
    }


@pytest.fixture
def performance_test_data():
    """パフォーマンステスト用データ"""
    return {
        "small_file": TestDataGenerator.create_sample_m4a_content(),
        "medium_file": TestDataGenerator.create_sample_m4a_content() + (b'\\x00' * (5 * 1024 * 1024)),  # 5MB
        "large_file": TestDataGenerator.create_sample_m4a_content() + (b'\\x00' * (20 * 1024 * 1024)),  # 20MB
        "concurrent_jobs_count": 5,
        "stress_test_count": 20
    }


class TestDataSetup:
    """テストデータセットアップクラス"""
    
    @staticmethod
    def setup_master_data(db_session):
        """マスターデータのセットアップ"""
        from app.models.master import UsageType, JobStatus, FileFormat
        
        # 使用用途
        usage_types = [
            UsageType(code="meeting", name="会議", description="会議録音の転写・要約", is_active=True),
            UsageType(code="interview", name="面接", description="面接録音の転写・要約", is_active=True),
            UsageType(code="lecture", name="講義", description="講義録音の転写・要約", is_active=True),
            UsageType(code="other", name="その他", description="その他用途", is_active=True)
        ]
        
        # ジョブステータス
        job_statuses = [
            JobStatus(code="pending", name="待機中", description="処理待ち", order_index=1),
            JobStatus(code="processing", name="処理中", description="音声処理中", order_index=2),
            JobStatus(code="completed", name="完了", description="処理完了", order_index=3),
            JobStatus(code="failed", name="失敗", description="処理失敗", order_index=4),
            JobStatus(code="cancelled", name="キャンセル", description="ユーザーキャンセル", order_index=5)
        ]
        
        # ファイル形式
        file_formats = [
            FileFormat(extension="m4a", mime_type="audio/m4a", description="Apple Lossless", is_supported=True, max_file_size_mb=50),
            FileFormat(extension="mp4", mime_type="audio/mp4", description="MP4 Audio", is_supported=True, max_file_size_mb=50),
            FileFormat(extension="wav", mime_type="audio/wav", description="WAV Audio", is_supported=True, max_file_size_mb=100),
            FileFormat(extension="mp3", mime_type="audio/mpeg", description="MP3 Audio", is_supported=True, max_file_size_mb=50)
        ]
        
        for items in [usage_types, job_statuses, file_formats]:
            for item in items:
                db_session.add(item)
        
        db_session.commit()
    
    @staticmethod
    def create_test_jobs(db_session, count: int = 5):
        """テスト用ジョブの作成"""
        from app.models.transcription import TranscriptionJob
        
        jobs = []
        usage_types = ["meeting", "interview", "lecture", "other"]
        
        for i in range(count):
            job = TranscriptionJob(
                filename=f"test_audio_{i}.m4a",
                file_size=1024 * (i + 1),
                usage_type=usage_types[i % len(usage_types)],
                status="pending" if i % 2 == 0 else "completed"
            )
            db_session.add(job)
            jobs.append(job)
        
        db_session.commit()
        return jobs


@pytest.fixture
def setup_test_database(test_db_session):
    """テストデータベースのセットアップ"""
    TestDataSetup.setup_master_data(test_db_session)
    jobs = TestDataSetup.create_test_jobs(test_db_session)
    
    return {
        "session": test_db_session,
        "jobs": jobs
    }