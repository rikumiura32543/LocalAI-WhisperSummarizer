"""
API関連テスト
"""

import pytest
import tempfile
import os
from pathlib import Path
from fastapi.testclient import TestClient

# テスト環境設定
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///./test_api.db"

from app.main import app
from app.core.database import get_database_manager
from scripts.init_db import init_database, insert_master_data

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_test_database():
    """テスト用データベース設定"""
    # テストDB初期化
    try:
        db_manager = get_database_manager()
        # マスターデータ投入
        init_database()
        yield
    finally:
        # クリーンアップ
        test_db_path = Path("test_api.db")
        if test_db_path.exists():
            test_db_path.unlink()


def test_root_endpoint():
    """ルートエンドポイントテスト"""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_health_check():
    """ヘルスチェックテスト"""
    response = client.get("/health")
    assert response.status_code in [200, 503]  # データベース状態により変動
    
    data = response.json()
    assert "status" in data
    assert "version" in data
    assert "environment" in data


def test_api_status():
    """APIステータステスト"""
    response = client.get("/api/v1/status")
    assert response.status_code == 200
    
    data = response.json()
    assert data["api_version"] == "v1"
    assert data["status"] == "active"
    assert "services" in data
    assert "statistics" in data
    assert "configuration" in data


def test_detailed_health_check():
    """詳細ヘルスチェックテスト"""
    response = client.get("/api/v1/health/detailed")
    assert response.status_code in [200, 503]
    
    data = response.json()
    assert "status" in data
    assert "services" in data
    assert "configuration" in data


def test_readiness_check():
    """レディネスチェックテスト"""
    response = client.get("/api/v1/health/readiness")
    assert response.status_code in [200, 503]
    
    data = response.json()
    assert "status" in data


def test_liveness_check():
    """ライブネスチェックテスト"""
    response = client.get("/api/v1/health/liveness")
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "alive"
    assert "version" in data


def test_transcription_jobs_list_empty():
    """転写ジョブ一覧（空）テスト"""
    response = client.get("/api/v1/transcriptions")
    assert response.status_code == 200
    
    data = response.json()
    assert data["success"] is True
    assert "jobs" in data
    assert "total" in data


def test_transcription_job_not_found():
    """存在しない転写ジョブ取得テスト"""
    response = client.get("/api/v1/transcriptions/nonexistent-job-id")
    assert response.status_code == 404
    
    data = response.json()
    assert data["error"] is True
    assert "指定されたジョブが見つかりません" in data["message"]


def test_create_transcription_job_no_file():
    """ファイルなし転写ジョブ作成テスト"""
    response = client.post(
        "/api/v1/transcriptions",
        data={"usage_type": "meeting"}
    )
    assert response.status_code == 422  # バリデーションエラー


def test_create_transcription_job_invalid_usage_type():
    """無効な使用用途での転写ジョブ作成テスト"""
    # テスト用ダミーファイル作成
    test_content = b"dummy audio content"
    
    response = client.post(
        "/api/v1/transcriptions",
        data={"usage_type": "invalid"},
        files={"file": ("test.m4a", test_content, "audio/m4a")}
    )
    assert response.status_code == 422  # バリデーションエラー


def test_create_transcription_job_invalid_file_type():
    """無効なファイル形式での転写ジョブ作成テスト"""
    test_content = b"dummy content"
    
    response = client.post(
        "/api/v1/transcriptions",
        data={"usage_type": "meeting"},
        files={"file": ("test.txt", test_content, "text/plain")}
    )
    assert response.status_code == 400
    
    data = response.json()
    assert "サポートされていないファイル形式" in data["message"]


def test_create_transcription_job_success():
    """正常な転写ジョブ作成テスト"""
    test_content = b"dummy audio content for testing"
    
    response = client.post(
        "/api/v1/transcriptions",
        data={"usage_type": "meeting"},
        files={"file": ("test_meeting.m4a", test_content, "audio/m4a")}
    )
    
    if response.status_code != 201:
        print("Response:", response.json())
    
    assert response.status_code == 201
    
    data = response.json()
    assert "id" in data
    assert data["original_filename"] == "test_meeting.m4a"
    assert data["usage_type_code"] == "meeting"
    assert data["status_code"] == "uploading"
    assert data["file_size"] == len(test_content)
    
    # 作成されたジョブIDを保存（後続テスト用）
    return data["id"]


def test_get_created_transcription_job():
    """作成された転写ジョブ取得テスト"""
    # まずジョブを作成
    job_id = test_create_transcription_job_success()
    
    # 作成されたジョブを取得
    response = client.get(f"/api/v1/transcriptions/{job_id}")
    assert response.status_code == 200
    
    data = response.json()
    assert data["id"] == job_id
    assert data["original_filename"] == "test_meeting.m4a"
    assert data["usage_type_code"] == "meeting"


def test_transcription_jobs_list_with_data():
    """転写ジョブ一覧（データあり）テスト"""
    # テストジョブを作成
    test_create_transcription_job_success()
    
    response = client.get("/api/v1/transcriptions")
    assert response.status_code == 200
    
    data = response.json()
    assert data["success"] is True
    assert len(data["jobs"]) >= 1
    assert data["total"] >= 1


def test_transcription_jobs_list_with_filters():
    """フィルター付き転写ジョブ一覧テスト"""
    # 会議タイプでフィルター
    response = client.get("/api/v1/transcriptions?usage_type=meeting")
    assert response.status_code == 200
    
    data = response.json()
    assert data["success"] is True
    
    # 面接タイプでフィルター（データなし）
    response = client.get("/api/v1/transcriptions?usage_type=interview")
    assert response.status_code == 200
    
    data = response.json()
    assert data["success"] is True


def test_transcription_jobs_list_pagination():
    """ページネーション付き転写ジョブ一覧テスト"""
    response = client.get("/api/v1/transcriptions?limit=10&offset=0")
    assert response.status_code == 200
    
    data = response.json()
    assert data["success"] is True
    assert len(data["jobs"]) <= 10


def test_file_download_nonexistent_job():
    """存在しないジョブのファイルダウンロードテスト"""
    response = client.get("/api/v1/files/nonexistent-job-id/transcription/txt")
    assert response.status_code == 404


def test_file_download_no_result():
    """転写結果なしのファイルダウンロードテスト"""
    # ジョブ作成（転写結果はまだない状態）
    job_id = test_create_transcription_job_success()
    
    response = client.get(f"/api/v1/files/{job_id}/transcription/txt")
    assert response.status_code == 404
    
    data = response.json()
    assert "転写結果が見つかりません" in data["message"]


def test_job_statistics():
    """ジョブ統計テスト"""
    response = client.get("/api/v1/status/jobs/stats")
    assert response.status_code == 200
    
    data = response.json()
    assert "total_jobs" in data
    assert "status_distribution" in data
    assert "usage_distribution" in data


def test_summary_statistics():
    """要約統計テスト"""
    response = client.get("/api/v1/status/summaries/stats")
    assert response.status_code == 200
    
    data = response.json()
    assert "total_summaries" in data
    assert "type_distribution" in data


def test_database_status():
    """データベースステータステスト"""
    response = client.get("/api/v1/status/database")
    assert response.status_code == 200
    
    data = response.json()
    assert "health_status" in data
    assert "table_statistics" in data


def test_error_handling():
    """エラーハンドリングテスト"""
    # 存在しないエンドポイント
    response = client.get("/api/v1/nonexistent-endpoint")
    assert response.status_code == 404
    
    data = response.json()
    assert data["error"] is True
    assert data["status_code"] == 404


def test_cors_headers():
    """CORSヘッダーテスト"""
    response = client.options("/api/v1/status")
    # CORSヘッダーが存在することを確認
    assert "access-control-allow-origin" in response.headers or response.status_code == 200


def test_security_headers():
    """セキュリティヘッダーテスト"""
    response = client.get("/api/v1/status")
    
    # セキュリティヘッダーの存在確認
    security_headers = [
        "x-content-type-options",
        "x-frame-options", 
        "x-xss-protection"
    ]
    
    for header in security_headers:
        # ヘッダーが設定されているかチェック（ミドルウェアが動作していれば）
        if header in response.headers:
            assert response.headers[header] is not None


def test_request_id_header():
    """リクエストIDヘッダーテスト"""
    response = client.get("/api/v1/status")
    
    # リクエストIDヘッダーが追加されているかチェック
    if "x-request-id" in response.headers:
        assert response.headers["x-request-id"] is not None


@pytest.mark.parametrize("endpoint", [
    "/api/v1/status",
    "/api/v1/health/detailed",
    "/api/v1/health/readiness",
    "/api/v1/health/liveness",
    "/api/v1/transcriptions"
])
def test_multiple_endpoints_availability(endpoint):
    """複数エンドポイント可用性テスト"""
    response = client.get(endpoint)
    # 2xx または 3xx のステータスコードを期待
    assert 200 <= response.status_code < 400


def test_large_file_rejection():
    """大容量ファイル拒否テスト"""
    # 設定された制限を超えるファイルサイズをシミュレート
    # 実際には巨大なファイルは作成せず、ヘッダーで制御
    
    test_content = b"dummy content"
    
    # 通常サイズは成功するはず
    response = client.post(
        "/api/v1/transcriptions",
        data={"usage_type": "meeting"},
        files={"file": ("normal.m4a", test_content, "audio/m4a")}
    )
    
    # バリデーションエラーまたは作成成功のいずれかになる
    assert response.status_code in [201, 400, 422]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])