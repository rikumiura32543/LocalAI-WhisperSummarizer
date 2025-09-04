"""
pytest設定とフィクスチャ
"""

import pytest
import os
from pathlib import Path
from fastapi.testclient import TestClient

# テスト環境の設定
os.environ["ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///./test.db"


@pytest.fixture
def client():
    """FastAPIテストクライアント"""
    from app.main import app
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def test_db():
    """テスト用データベース"""
    test_db_path = Path("test.db")
    
    # テスト実行前の準備
    yield "test.db"
    
    # テスト実行後のクリーンアップ
    if test_db_path.exists():
        test_db_path.unlink()


@pytest.fixture
def sample_m4a_file():
    """テスト用M4Aファイルのモック"""
    return {
        "filename": "test_audio.m4a",
        "content_type": "audio/m4a",
        "size": 1024 * 1024,  # 1MB
    }


@pytest.fixture
def mock_transcription_result():
    """転写結果のモック"""
    return {
        "text": "これはテスト用の転写結果です。",
        "confidence": 0.95,
        "language": "ja",
        "duration": 60.0
    }


@pytest.fixture
def mock_summary_result():
    """要約結果のモック"""
    return {
        "summary": "テスト用の要約結果です。",
        "key_points": ["ポイント1", "ポイント2"],
        "action_items": ["アクション1", "アクション2"],
        "participants": ["参加者A", "参加者B"]
    }