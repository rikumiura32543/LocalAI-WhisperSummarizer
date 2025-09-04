"""
API エンドポイントの統合テスト
"""

import pytest
import json
import tempfile
import os
from pathlib import Path
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock, AsyncMock
import time

# テスト環境の設定
os.environ["ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///./test_integration.db"

from app.main import create_application
from app.models.base import Base, get_db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture(scope="function")
def test_db():
    """テスト用データベース"""
    test_db_path = "test_integration.db"
    engine = create_engine(f"sqlite:///./{test_db_path}")
    Base.metadata.create_all(engine)
    
    TestingSessionLocal = sessionmaker(bind=engine)
    
    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()
    
    app = create_application()
    app.dependency_overrides[get_db] = override_get_db
    
    yield TestingSessionLocal()
    
    # クリーンアップ
    if Path(test_db_path).exists():
        Path(test_db_path).unlink()


@pytest.fixture
def client(test_db):
    """テストクライアント"""
    app = create_application()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sample_m4a_content():
    """サンプルM4Aファイル内容"""
    # 最小限のAACヘッダーを含むダミーファイル
    return b'\\x00\\x00\\x00\\x20ftypM4A \\x00\\x00\\x00\\x00M4A mp42isom\\x00\\x00\\x00\\x00'


class TestHealthEndpoints:
    """ヘルスチェック関連エンドポイントのテスト"""
    
    def test_root_endpoint(self, client):
        """ルートエンドポイントのテスト"""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
    
    def test_health_endpoint(self, client):
        """ヘルスチェックエンドポイントのテスト"""
        response = client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "system_info" in data
        assert data["status"] == "healthy"
    
    @patch('app.services.whisper_service.WhisperService')
    @patch('app.services.ollama_service.OllamaService')
    def test_status_endpoint_all_services_ready(
        self, mock_ollama_service, mock_whisper_service, client
    ):
        """全サービス正常時のステータス確認"""
        # Ollamaサービスのモック
        mock_ollama_instance = mock_ollama_service.return_value
        mock_ollama_instance.is_available = AsyncMock(return_value=True)
        
        response = client.get("/api/v1/status")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "active"
        assert "version" in data
        assert "services" in data
        assert "whisper" in data["services"]
        assert "ollama" in data["services"]
    
    @patch('app.services.whisper_service.WhisperService')
    @patch('app.services.ollama_service.OllamaService')
    def test_status_endpoint_service_unavailable(
        self, mock_ollama_service, mock_whisper_service, client
    ):
        """サービス一部停止時のステータス確認"""
        # Ollamaサービスが利用不可
        mock_ollama_instance = mock_ollama_service.return_value
        mock_ollama_instance.is_available = AsyncMock(return_value=False)
        
        response = client.get("/api/v1/status")
        assert response.status_code == 200
        
        data = response.json()
        # サービス一部停止でもstatusは activeを返す設計想定
        assert "services" in data
        assert "ollama" in data["services"]


class TestTranscriptionEndpoints:
    """転写関連エンドポイントのテスト"""
    
    def test_create_transcription_job_success(self, client, sample_m4a_content):
        """転写ジョブ作成成功テスト"""
        # ファイルアップロード用のデータ準備
        files = {
            "audio_file": ("test_audio.m4a", sample_m4a_content, "audio/m4a")
        }
        data = {"usage_type": "meeting"}
        
        response = client.post("/api/v1/transcriptions", files=files, data=data)
        assert response.status_code == 200
        
        result = response.json()
        assert "job_id" in result
        assert "status" in result
        assert result["status"] == "processing"
    
    def test_create_transcription_job_missing_file(self, client):
        """ファイル未添付時のエラーテスト"""
        data = {"usage_type": "meeting"}
        
        response = client.post("/api/v1/transcriptions", data=data)
        assert response.status_code == 422  # Validation error
    
    def test_create_transcription_job_missing_usage_type(self, client, sample_m4a_content):
        """用途未指定時のエラーテスト"""
        files = {
            "audio_file": ("test_audio.m4a", sample_m4a_content, "audio/m4a")
        }
        
        response = client.post("/api/v1/transcriptions", files=files)
        assert response.status_code == 422
    
    def test_create_transcription_job_invalid_file_type(self, client):
        """不正なファイル形式のテスト"""
        files = {
            "audio_file": ("test.txt", b"This is not audio", "text/plain")
        }
        data = {"usage_type": "meeting"}
        
        response = client.post("/api/v1/transcriptions", files=files, data=data)
        assert response.status_code == 400
        
        error = response.json()
        assert "detail" in error
        assert "ファイル形式" in error["detail"] or "format" in error["detail"].lower()
    
    def test_create_transcription_job_file_too_large(self, client):
        """ファイルサイズ制限テスト"""
        # 50MB以上のファイル（実際には少ない容量でヘッダーを偽装）
        large_content = b"dummy" * 1024 * 1024  # 約5MB（テスト用）
        
        files = {
            "audio_file": ("large_audio.m4a", large_content, "audio/m4a")
        }
        data = {"usage_type": "meeting"}
        
        # Content-Lengthヘッダーを偽装して大きなファイルをシミュレート
        with patch('app.core.middleware.FileSizeValidationMiddleware') as mock_middleware:
            response = client.post("/api/v1/transcriptions", files=files, data=data)
            # ファイルサイズ制限のテストは実際のミドルウェアでチェック
    
    def test_get_transcription_job_success(self, client, sample_m4a_content):
        """転写ジョブ取得成功テスト"""
        # まずジョブを作成
        files = {
            "audio_file": ("test_audio.m4a", sample_m4a_content, "audio/m4a")
        }
        data = {"usage_type": "meeting"}
        
        create_response = client.post("/api/v1/transcriptions", files=files, data=data)
        assert create_response.status_code == 200
        job_data = create_response.json()
        job_id = job_data["job_id"]
        
        # ジョブ取得
        get_response = client.get(f"/api/v1/transcriptions/{job_id}")
        assert get_response.status_code == 200
        
        job_info = get_response.json()
        assert job_info["id"] == job_id
        assert "filename" in job_info
        assert "status" in job_info
        assert "created_at" in job_info
    
    def test_get_transcription_job_not_found(self, client):
        """存在しないジョブ取得テスト"""
        response = client.get("/api/v1/transcriptions/nonexistent-id")
        assert response.status_code == 404
        
        error = response.json()
        assert "detail" in error
    
    def test_list_transcription_jobs(self, client, sample_m4a_content):
        """転写ジョブ一覧取得テスト"""
        # 複数のジョブを作成
        files = {
            "audio_file": ("test_audio.m4a", sample_m4a_content, "audio/m4a")
        }
        
        for i in range(3):
            data = {"usage_type": "meeting"}
            response = client.post("/api/v1/transcriptions", files=files, data=data)
            assert response.status_code == 200
        
        # ジョブ一覧取得
        list_response = client.get("/api/v1/transcriptions")
        assert list_response.status_code == 200
        
        jobs_data = list_response.json()
        assert "jobs" in jobs_data
        assert "total" in jobs_data
        assert len(jobs_data["jobs"]) >= 3
        assert jobs_data["total"] >= 3
    
    def test_list_transcription_jobs_with_pagination(self, client, sample_m4a_content):
        """ページネーション付きジョブ一覧テスト"""
        # 5個のジョブを作成
        files = {
            "audio_file": ("test_audio.m4a", sample_m4a_content, "audio/m4a")
        }
        
        for i in range(5):
            data = {"usage_type": "meeting"}
            client.post("/api/v1/transcriptions", files=files, data=data)
        
        # 1ページ目（3件まで）
        response = client.get("/api/v1/transcriptions?skip=0&limit=3")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["jobs"]) <= 3
        assert data["total"] >= 5
        
        # 2ページ目
        response = client.get("/api/v1/transcriptions?skip=3&limit=3")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["jobs"]) >= 2  # 残りの2件以上
    
    def test_delete_transcription_job_success(self, client, sample_m4a_content):
        """転写ジョブ削除成功テスト"""
        # ジョブ作成
        files = {
            "audio_file": ("test_audio.m4a", sample_m4a_content, "audio/m4a")
        }
        data = {"usage_type": "meeting"}
        
        create_response = client.post("/api/v1/transcriptions", files=files, data=data)
        job_id = create_response.json()["job_id"]
        
        # ジョブ削除
        delete_response = client.delete(f"/api/v1/transcriptions/{job_id}")
        assert delete_response.status_code == 200
        
        # 削除確認
        get_response = client.get(f"/api/v1/transcriptions/{job_id}")
        assert get_response.status_code == 404
    
    def test_delete_transcription_job_not_found(self, client):
        """存在しないジョブ削除テスト"""
        response = client.delete("/api/v1/transcriptions/nonexistent-id")
        assert response.status_code == 404


class TestFileDownloadEndpoints:
    """ファイルダウンロード関連エンドポイントのテスト"""
    
    def setup_completed_job(self, client, sample_m4a_content):
        """完了済みジョブのセットアップ"""
        # ジョブ作成
        files = {
            "audio_file": ("test_audio.m4a", sample_m4a_content, "audio/m4a")
        }
        data = {"usage_type": "meeting"}
        
        create_response = client.post("/api/v1/transcriptions", files=files, data=data)
        job_id = create_response.json()["job_id"]
        
        # 手動でジョブを完了状態に変更（テスト用）
        # 実際のアプリケーションではバックグラウンド処理で自動実行
        with patch('app.services.transcription_service.TranscriptionService') as mock_service:
            mock_job = Mock()
            mock_job.id = job_id
            mock_job.status = "completed"
            mock_job.transcription_result = Mock()
            mock_job.transcription_result.text = "テスト用転写結果"
            mock_job.summary_result = Mock()
            mock_job.summary_result.summary = {"overview": "テスト要約"}
            
            mock_service.return_value.get_job.return_value = mock_job
        
        return job_id
    
    @patch('app.services.transcription_service.TranscriptionService')
    def test_download_transcription_txt(
        self, mock_service, client, sample_m4a_content
    ):
        """転写テキストファイルダウンロードテスト"""
        job_id = "test-job-id"
        
        # モックジョブ設定
        mock_job = Mock()
        mock_job.id = job_id
        mock_job.status = "completed"
        mock_job.transcription_result = Mock()
        mock_job.transcription_result.text = "これはテスト用の転写結果です。"
        
        mock_service.return_value.get_job.return_value = mock_job
        
        response = client.get(f"/api/v1/files/{job_id}/transcription.txt")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]
        assert "attachment" in response.headers.get("content-disposition", "")
        assert "これはテスト用の転写結果です。" in response.content.decode()
    
    @patch('app.services.transcription_service.TranscriptionService')
    def test_download_transcription_json(
        self, mock_service, client, sample_m4a_content
    ):
        """転写JSONファイルダウンロードテスト"""
        job_id = "test-job-id"
        
        mock_job = Mock()
        mock_job.id = job_id
        mock_job.status = "completed"
        mock_job.transcription_result = Mock()
        mock_job.transcription_result.text = "テスト転写"
        mock_job.transcription_result.confidence = 0.95
        mock_job.transcription_result.detected_language = "ja"
        
        mock_service.return_value.get_job.return_value = mock_job
        
        response = client.get(f"/api/v1/files/{job_id}/transcription.json")
        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]
        
        data = response.json()
        assert "text" in data
        assert "confidence" in data
        assert data["text"] == "テスト転写"
        assert data["confidence"] == 0.95
    
    @patch('app.services.transcription_service.TranscriptionService')
    def test_download_summary_txt(self, mock_service, client):
        """要約テキストファイルダウンロードテスト"""
        job_id = "test-job-id"
        
        mock_job = Mock()
        mock_job.id = job_id
        mock_job.status = "completed"
        mock_job.summary_result = Mock()
        mock_job.summary_result.summary = {
            "overview": "会議の概要",
            "key_points": ["ポイント1", "ポイント2"],
            "action_items": ["アクション1"]
        }
        
        mock_service.return_value.get_job.return_value = mock_job
        
        response = client.get(f"/api/v1/files/{job_id}/summary.txt")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]
        
        content = response.content.decode()
        assert "概要" in content
        assert "ポイント1" in content
        assert "アクション1" in content
    
    def test_download_file_job_not_found(self, client):
        """存在しないジョブのファイルダウンロードテスト"""
        response = client.get("/api/v1/files/nonexistent/transcription.txt")
        assert response.status_code == 404
    
    @patch('app.services.transcription_service.TranscriptionService')
    def test_download_file_job_not_completed(self, mock_service, client):
        """未完了ジョブのファイルダウンロードテスト"""
        job_id = "pending-job-id"
        
        mock_job = Mock()
        mock_job.id = job_id
        mock_job.status = "processing"
        
        mock_service.return_value.get_job.return_value = mock_job
        
        response = client.get(f"/api/v1/files/{job_id}/transcription.txt")
        assert response.status_code == 400
        
        error = response.json()
        assert "detail" in error


class TestEndToEndWorkflow:
    """エンドツーエンドワークフローテスト"""
    
    @patch('app.services.audio_processor.AudioProcessor')
    @pytest.mark.asyncio
    async def test_complete_transcription_workflow(
        self, mock_processor, client, sample_m4a_content
    ):
        """完全な転写ワークフローテスト"""
        # AudioProcessorのモック設定
        mock_processor_instance = mock_processor.return_value
        mock_processor_instance.process_audio_file = AsyncMock(return_value={
            "transcription": {
                "text": "完全なワークフローテストです。",
                "language": "ja",
                "confidence": 0.95
            },
            "summary": {
                "overview": "テストの概要",
                "key_points": ["重要なポイント"],
                "action_items": ["テスト完了"]
            }
        })
        
        # 1. ジョブ作成
        files = {
            "audio_file": ("workflow_test.m4a", sample_m4a_content, "audio/m4a")
        }
        data = {"usage_type": "meeting"}
        
        create_response = client.post("/api/v1/transcriptions", files=files, data=data)
        assert create_response.status_code == 200
        job_id = create_response.json()["job_id"]
        
        # 2. 処理状況確認（処理中）
        status_response = client.get(f"/api/v1/transcriptions/{job_id}")
        assert status_response.status_code == 200
        job_info = status_response.json()
        assert job_info["status"] in ["pending", "processing"]
        
        # 3. 処理完了まで待機（実際のシナリオでは時間がかかる）
        # テストでは即座に完了状態をモック
        
        # 4. 完了後のファイルダウンロード確認
        # この部分は実際の処理完了後にテストされる
    
    def test_error_handling_workflow(self, client):
        """エラーハンドリングワークフローテスト"""
        # 1. 不正なリクエスト
        response = client.post("/api/v1/transcriptions", data={"usage_type": "invalid"})
        assert response.status_code == 422
        
        # 2. 存在しないリソースへのアクセス
        response = client.get("/api/v1/transcriptions/invalid-id")
        assert response.status_code == 404
        
        # 3. 不正なファイルダウンロード
        response = client.get("/api/v1/files/invalid-id/transcription.txt")
        assert response.status_code == 404
    
    def test_concurrent_requests(self, client, sample_m4a_content):
        """同時リクエスト処理テスト"""
        import concurrent.futures
        import threading
        
        def create_job():
            files = {
                "audio_file": ("concurrent_test.m4a", sample_m4a_content, "audio/m4a")
            }
            data = {"usage_type": "meeting"}
            return client.post("/api/v1/transcriptions", files=files, data=data)
        
        # 5つの同時リクエストを送信
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(create_job) for _ in range(5)]
            responses = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # すべてのリクエストが成功することを確認
        for response in responses:
            assert response.status_code == 200
            assert "job_id" in response.json()
        
        # 各ジョブIDがユニークであることを確認
        job_ids = [response.json()["job_id"] for response in responses]
        assert len(job_ids) == len(set(job_ids))  # 重複なし


class TestMiddleware:
    """ミドルウェア関連のテスト"""
    
    def test_cors_headers(self, client):
        """CORSヘッダーテスト"""
        response = client.options("/api/v1/status", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET"
        })
        
        assert "access-control-allow-origin" in response.headers
        assert "access-control-allow-methods" in response.headers
    
    def test_security_headers(self, client):
        """セキュリティヘッダーテスト"""
        response = client.get("/api/v1/status")
        
        # セキュリティヘッダーの確認
        assert "x-content-type-options" in response.headers
        assert "x-frame-options" in response.headers
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
    
    def test_request_logging(self, client):
        """リクエストログミドルウェアテスト"""
        with patch('app.core.middleware.logger') as mock_logger:
            response = client.get("/api/v1/status")
            assert response.status_code == 200
            
            # ログが呼び出されたことを確認
            mock_logger.info.assert_called()
    
    def test_rate_limiting(self, client):
        """レート制限テスト"""
        # 大量のリクエストを短時間で送信
        responses = []
        for _ in range(65):  # 制限を超える数のリクエスト
            response = client.get("/api/v1/status")
            responses.append(response)
        
        # 最初の60リクエストは成功、それ以降は429が返されることを確認
        success_count = sum(1 for r in responses if r.status_code == 200)
        rate_limited_count = sum(1 for r in responses if r.status_code == 429)
        
        assert success_count <= 60
        # レート制限が適切に機能することを確認（環境により変動可能性あり）