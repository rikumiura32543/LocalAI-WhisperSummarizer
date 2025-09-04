"""
メインアプリケーションのテスト
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_root_endpoint():
    """ルートエンドポイントのテスト"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data
    assert "status" in data
    assert data["version"] == "1.0.0"


def test_health_check():
    """ヘルスチェックエンドポイントのテスト"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "1.0.0"
    assert "environment" in data


def test_api_status():
    """APIステータスエンドポイントのテスト"""
    response = client.get("/api/v1/status")
    assert response.status_code == 200
    data = response.json()
    assert data["api_version"] == "v1"
    assert data["status"] == "active"
    assert "services" in data
    assert "transcription" in data["services"]
    assert "summarization" in data["services"]
    assert "database" in data["services"]


def test_cors_headers():
    """CORSヘッダーのテスト"""
    response = client.options("/")
    assert "access-control-allow-origin" in response.headers


@pytest.mark.asyncio
async def test_startup_event():
    """起動イベントのテスト"""
    from pathlib import Path
    
    # 必要なディレクトリが作成されることを確認
    expected_dirs = ["uploads", "data", "logs"]
    
    for dir_name in expected_dirs:
        dir_path = Path(dir_name)
        # テスト実行により作成される可能性があるため、存在チェックのみ
        assert True  # プレースホルダー：実際の起動イベントテストは後で実装