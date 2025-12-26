"""
pytest設定とフィクスチャ
"""

import pytest
import os
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# テスト環境の設定
os.environ["ENVIRONMENT"] = "test"
os.environ["ENV"] = "test"
os.environ["DEBUG"] = "False"
os.environ["ENABLE_SWAGGER_UI"] = "False"


@pytest.fixture(scope="function")
def test_db_engine():
    """テスト用インメモリデータベースエンジン（各テストで独立）"""
    # In-memory SQLite with StaticPool to avoid connection issues
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False
    )
    
    # テーブル作成
    from app.models.base import Base
    Base.metadata.create_all(bind=engine)
    
    yield engine
    
    # クリーンアップ
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def test_db_session(test_db_engine):
    """テスト用データベースセッション（各テストで独立）"""
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_db_engine
    )
    
    session = TestingSessionLocal()
    
    yield session
    
    session.close()


@pytest.fixture(scope="function")
def client(test_db_engine):
    """FastAPIテストクライアント（データベース依存注入付き）"""
    from app.main import create_application
    from app.core.database import get_session
    from sqlalchemy.orm import Session
    
    # Override database session dependency
    def override_get_session():
        TestingSessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=test_db_engine
        )
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()
    
    app = create_application()
    app.dependency_overrides[get_session] = override_get_session
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def test_db():
    """テスト用データベース（後方互換性のため残す）"""
    # Use temporary file for session-scoped tests
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        test_db_path = f.name
    
    yield test_db_path
    
    # クリーンアップ
    try:
        Path(test_db_path).unlink()
    except FileNotFoundError:
        pass


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


@pytest.fixture(autouse=True)
def cleanup_test_files():
    """テスト後のファイルクリーンアップ（自動実行）"""
    yield
    
    # テスト用に作成された一時ファイルの削除
    test_patterns = ["test*.db", "test*.db-journal", "test*.db-wal"]
    for pattern in test_patterns:
        for test_file in Path.cwd().glob(pattern):
            try:
                test_file.unlink()
            except (FileNotFoundError, PermissionError):
                pass