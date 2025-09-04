"""
エンドツーエンド（E2E）テスト - 完全なワークフロー
"""

import pytest
import tempfile
import time
import json
import asyncio
from pathlib import Path
from unittest.mock import patch, Mock, AsyncMock
from fastapi.testclient import TestClient

from app.main import create_application
from app.services.audio_processor import AudioProcessor
from app.services.transcription_service import TranscriptionService
from app.services.summary_service import SummaryService
from app.services.whisper_service import WhisperService
from app.services.ollama_service import OllamaService


@pytest.fixture
def real_audio_file():
    """実際の音声ファイル形式に近いテストファイル"""
    # 最小限のM4Aヘッダーを含む疑似ファイル
    m4a_header = (
        b'\\x00\\x00\\x00\\x20ftypM4A \\x00\\x00\\x00\\x00M4A mp42isom\\x00\\x00\\x00\\x00'
        b'\\x00\\x00\\x00\\x28moov\\x00\\x00\\x00\\x20mvhd\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00'
        b'\\x00\\x00\\x00\\x00\\x00\\x00\\x03\\xe8\\x00\\x00\\x00\\x00\\x00\\x01\\x00\\x00\\x01\\x00'
    )
    
    with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as f:
        f.write(m4a_header)
        f.write(b'\\x00' * 1024)  # ダミーデータ
        f.flush()
        return f.name


@pytest.fixture
def mock_services():
    """全サービスのモック設定"""
    with patch.multiple(
        'app.services.audio_processor',
        WhisperService=Mock(),
        OllamaService=Mock()
    ) as mocks:
        
        # Whisper サービスモック
        whisper_mock = mocks['WhisperService'].return_value
        whisper_mock.transcribe_audio.return_value = {
            "text": "こんにちは。今日は M4A 転写システムのテストを実行しています。このシステムは音声ファイルをテキストに変換し、AI を使って要約を生成します。テストが正常に動作することを確認しています。",
            "language": "ja",
            "segments": [
                {
                    "id": 0,
                    "start": 0.0,
                    "end": 5.0,
                    "text": "こんにちは。今日は M4A 転写システムのテストを実行しています。"
                },
                {
                    "id": 1,
                    "start": 5.0,
                    "end": 10.0,
                    "text": "このシステムは音声ファイルをテキストに変換し、AI を使って要約を生成します。"
                },
                {
                    "id": 2,
                    "start": 10.0,
                    "end": 13.0,
                    "text": "テストが正常に動作することを確認しています。"
                }
            ]
        }
        
        # Ollama サービスモック
        ollama_mock = mocks['OllamaService'].return_value
        ollama_mock.generate_meeting_summary = AsyncMock(return_value={
            "overview": "M4A転写システムのテスト実行に関する会議。システムの動作確認と品質保証について議論された。",
            "key_points": [
                "転写システムが正常に動作することを確認",
                "音声からテキストへの変換精度が高い",
                "AI要約機能が期待通りに動作している"
            ],
            "action_items": [
                "全ての機能テストを完了させる",
                "システムの本番環境への展開を準備する"
            ],
            "participants": ["テストエンジニア"]
        })
        
        ollama_mock.generate_interview_summary = AsyncMock(return_value={
            "candidate_assessment": {
                "strengths": ["システム理解が深い", "テスト設計能力が高い"],
                "areas_for_improvement": ["実装速度の向上"],
                "overall_impression": "優秀なエンジニア候補"
            },
            "questions_and_answers": [
                {
                    "question": "M4A転写システムについて説明してください",
                    "answer": "音声ファイルからテキストを抽出し、AI要約を生成するシステムです"
                }
            ],
            "recommendation": "採用を強く推奨"
        })
        
        ollama_mock.is_available = AsyncMock(return_value=True)
        
        yield mocks


class TestCompleteWorkflow:
    """完全ワークフローのE2Eテスト"""
    
    def test_meeting_transcription_complete_flow(self, mock_services, real_audio_file):
        """会議音声の完全な転写・要約フローテスト"""
        client = TestClient(create_application())
        
        # 1. システム状態確認
        status_response = client.get("/api/v1/status")
        assert status_response.status_code == 200
        status_data = status_response.json()
        assert status_data["status"] == "active"
        
        # 2. 音声ファイルアップロードとジョブ作成
        with open(real_audio_file, 'rb') as f:
            files = {"audio_file": ("meeting_audio.m4a", f, "audio/m4a")}
            data = {"usage_type": "meeting"}
            
            upload_response = client.post("/api/v1/transcriptions", files=files, data=data)
            assert upload_response.status_code == 200
            
            job_data = upload_response.json()
            job_id = job_data["job_id"]
            assert job_data["status"] == "processing"
        
        # 3. 処理状況の監視（実際のアプリでは時間がかかる）
        max_wait_time = 30  # 最大30秒待機
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            status_response = client.get(f"/api/v1/transcriptions/{job_id}")
            assert status_response.status_code == 200
            
            job_status = status_response.json()
            
            if job_status["status"] == "completed":
                break
            elif job_status["status"] == "failed":
                pytest.fail(f"Job failed: {job_status.get('error_message', 'Unknown error')}")
            
            time.sleep(1)
        else:
            pytest.fail("Job did not complete within the expected time")
        
        # 4. 完了したジョブの詳細確認
        final_status = client.get(f"/api/v1/transcriptions/{job_id}")
        final_job = final_status.json()
        
        assert final_job["status"] == "completed"
        assert "transcription_result" in final_job
        assert "summary_result" in final_job
        assert final_job["transcription_result"]["text"] is not None
        assert final_job["summary_result"]["summary"] is not None
        
        # 5. 転写結果ダウンロード
        transcription_txt = client.get(f"/api/v1/files/{job_id}/transcription.txt")
        assert transcription_txt.status_code == 200
        assert "M4A 転写システム" in transcription_txt.content.decode()
        
        transcription_json = client.get(f"/api/v1/files/{job_id}/transcription.json")
        assert transcription_json.status_code == 200
        transcription_data = transcription_json.json()
        assert "text" in transcription_data
        assert "segments" in transcription_data
        
        # 6. 要約結果ダウンロード
        summary_txt = client.get(f"/api/v1/files/{job_id}/summary.txt")
        assert summary_txt.status_code == 200
        summary_content = summary_txt.content.decode()
        assert "概要" in summary_content
        assert "重要" in summary_content or "ポイント" in summary_content
        
        summary_json = client.get(f"/api/v1/files/{job_id}/summary.json")
        assert summary_json.status_code == 200
        summary_data = summary_json.json()
        assert "summary" in summary_data
        assert "overview" in summary_data["summary"]
        assert "key_points" in summary_data["summary"]
        assert "action_items" in summary_data["summary"]
        
        # 7. 全データエクスポート
        export_response = client.get(f"/api/v1/files/{job_id}/export")
        # 実装によってはZIPファイルまたはJSON形式
        assert export_response.status_code in [200, 501]  # 501は未実装
        
        print(f"✅ 会議音声の完全ワークフローテスト成功 (Job ID: {job_id})")
    
    def test_interview_transcription_complete_flow(self, mock_services, real_audio_file):
        """面接音声の完全な転写・要約フローテスト"""
        client = TestClient(create_application())
        
        # 面接用の音声ファイルアップロード
        with open(real_audio_file, 'rb') as f:
            files = {"audio_file": ("interview_audio.m4a", f, "audio/m4a")}
            data = {"usage_type": "interview"}
            
            upload_response = client.post("/api/v1/transcriptions", files=files, data=data)
            assert upload_response.status_code == 200
            
            job_id = upload_response.json()["job_id"]
        
        # 処理完了まで待機
        max_attempts = 30
        for _ in range(max_attempts):
            status_response = client.get(f"/api/v1/transcriptions/{job_id}")
            job_status = status_response.json()
            
            if job_status["status"] == "completed":
                break
            elif job_status["status"] == "failed":
                pytest.fail("Interview job failed")
            
            time.sleep(1)
        else:
            pytest.fail("Interview job did not complete")
        
        # 面接特有の要約内容確認
        summary_response = client.get(f"/api/v1/files/{job_id}/summary.json")
        assert summary_response.status_code == 200
        
        summary_data = summary_response.json()
        interview_summary = summary_data["summary"]
        
        # 面接要約の構造確認
        assert "candidate_assessment" in interview_summary
        assert "recommendation" in interview_summary
        assert "strengths" in interview_summary["candidate_assessment"]
        assert "areas_for_improvement" in interview_summary["candidate_assessment"]
        
        print(f"✅ 面接音声の完全ワークフローテスト成功 (Job ID: {job_id})")
    
    def test_multiple_concurrent_jobs(self, mock_services, real_audio_file):
        """複数の同時処理ジョブテスト"""
        client = TestClient(create_application())
        
        job_ids = []
        
        # 3つのジョブを同時に開始
        with open(real_audio_file, 'rb') as f:
            audio_content = f.read()
        
        for i in range(3):
            files = {"audio_file": (f"concurrent_test_{i}.m4a", audio_content, "audio/m4a")}
            data = {"usage_type": "meeting"}
            
            response = client.post("/api/v1/transcriptions", files=files, data=data)
            assert response.status_code == 200
            
            job_ids.append(response.json()["job_id"])
        
        # すべてのジョブの完了を待機
        completed_jobs = 0
        max_wait_time = 60  # 1分
        start_time = time.time()
        
        while completed_jobs < 3 and time.time() - start_time < max_wait_time:
            completed_jobs = 0
            
            for job_id in job_ids:
                status_response = client.get(f"/api/v1/transcriptions/{job_id}")
                job_status = status_response.json()
                
                if job_status["status"] == "completed":
                    completed_jobs += 1
                elif job_status["status"] == "failed":
                    pytest.fail(f"Job {job_id} failed")
            
            if completed_jobs < 3:
                time.sleep(2)
        
        assert completed_jobs == 3, f"Only {completed_jobs}/3 jobs completed"
        
        # 全ジョブの結果確認
        for job_id in job_ids:
            transcription = client.get(f"/api/v1/files/{job_id}/transcription.txt")
            assert transcription.status_code == 200
            
            summary = client.get(f"/api/v1/files/{job_id}/summary.txt")
            assert summary.status_code == 200
        
        print(f"✅ 同時実行ジョブテスト成功 ({len(job_ids)} jobs)")
    
    def test_error_recovery_workflow(self, real_audio_file):
        """エラー回復ワークフローテスト"""
        client = TestClient(create_application())
        
        # 1. 正常なジョブから開始
        with open(real_audio_file, 'rb') as f:
            files = {"audio_file": ("test.m4a", f, "audio/m4a")}
            data = {"usage_type": "meeting"}
            
            response = client.post("/api/v1/transcriptions", files=files, data=data)
            assert response.status_code == 200
            job_id = response.json()["job_id"]
        
        # 2. ジョブをキャンセル
        cancel_response = client.delete(f"/api/v1/transcriptions/{job_id}")
        assert cancel_response.status_code == 200
        
        # 3. キャンセルされたジョブにアクセス
        status_response = client.get(f"/api/v1/transcriptions/{job_id}")
        assert status_response.status_code == 404
        
        # 4. 不正なファイル形式でリトライ
        invalid_files = {"audio_file": ("test.txt", b"not audio", "text/plain")}
        invalid_response = client.post("/api/v1/transcriptions", files=invalid_files, data=data)
        assert invalid_response.status_code == 400
        
        # 5. 正常なファイルで再実行
        with open(real_audio_file, 'rb') as f:
            files = {"audio_file": ("retry.m4a", f, "audio/m4a")}
            retry_response = client.post("/api/v1/transcriptions", files=files, data=data)
            assert retry_response.status_code == 200
        
        print("✅ エラー回復ワークフローテスト成功")


class TestPerformanceAndScalability:
    """パフォーマンスとスケーラビリティテスト"""
    
    def test_large_file_processing(self, mock_services):
        """大きなファイルの処理テスト"""
        client = TestClient(create_application())
        
        # 大きなファイル（5MB）を模擬
        large_content = b'\\x00\\x00\\x00\\x20ftypM4A ' + b'\\x00' * (5 * 1024 * 1024)
        
        files = {"audio_file": ("large_file.m4a", large_content, "audio/m4a")}
        data = {"usage_type": "meeting"}
        
        start_time = time.time()
        response = client.post("/api/v1/transcriptions", files=files, data=data)
        upload_time = time.time() - start_time
        
        assert response.status_code == 200
        assert upload_time < 10.0  # 10秒以内のアップロード
        
        print(f"✅ 大ファイル処理テスト成功 (アップロード時間: {upload_time:.2f}秒)")
    
    def test_api_response_times(self, mock_services, real_audio_file):
        """API応答時間テスト"""
        client = TestClient(create_application())
        
        # 各エンドポイントの応答時間測定
        endpoints_and_expected_times = [
            ("/api/v1/status", 0.5),
            ("/health", 0.3),
            ("/", 0.5)
        ]
        
        for endpoint, max_time in endpoints_and_expected_times:
            start_time = time.time()
            response = client.get(endpoint)
            response_time = time.time() - start_time
            
            assert response.status_code == 200
            assert response_time < max_time, f"{endpoint} took {response_time:.3f}s (max: {max_time}s)"
        
        # ファイルアップロード時間
        with open(real_audio_file, 'rb') as f:
            files = {"audio_file": ("perf_test.m4a", f, "audio/m4a")}
            data = {"usage_type": "meeting"}
            
            start_time = time.time()
            response = client.post("/api/v1/transcriptions", files=files, data=data)
            upload_time = time.time() - start_time
            
            assert response.status_code == 200
            assert upload_time < 3.0  # 3秒以内
        
        print("✅ API応答時間テスト成功")
    
    def test_memory_usage_stability(self, mock_services, real_audio_file):
        """メモリ使用量安定性テスト"""
        import psutil
        import os
        
        client = TestClient(create_application())
        process = psutil.Process(os.getpid())
        
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # 10個のジョブを順次処理
        with open(real_audio_file, 'rb') as f:
            audio_content = f.read()
        
        for i in range(10):
            files = {"audio_file": (f"memory_test_{i}.m4a", audio_content, "audio/m4a")}
            data = {"usage_type": "meeting"}
            
            response = client.post("/api/v1/transcriptions", files=files, data=data)
            assert response.status_code == 200
            
            # メモリ使用量確認
            current_memory = process.memory_info().rss / 1024 / 1024
            memory_increase = current_memory - initial_memory
            
            # 異常なメモリ増加がないことを確認（100MB以内）
            assert memory_increase < 100, f"Memory increased by {memory_increase:.1f}MB"
        
        final_memory = process.memory_info().rss / 1024 / 1024
        print(f"✅ メモリ安定性テスト成功 (初期: {initial_memory:.1f}MB, 最終: {final_memory:.1f}MB)")


class TestUserExperienceFlows:
    """ユーザーエクスペリエンステスト"""
    
    def test_typical_user_journey(self, mock_services, real_audio_file):
        """典型的なユーザージャーニーテスト"""
        client = TestClient(create_application())
        
        # 1. ユーザーがサイトにアクセス
        home_response = client.get("/")
        assert home_response.status_code == 200
        assert "M4A転写システム" in home_response.content.decode()
        
        # 2. システム状態を確認
        status_response = client.get("/api/v1/status")
        assert status_response.status_code == 200
        
        # 3. 音声ファイルをアップロード
        with open(real_audio_file, 'rb') as f:
            files = {"audio_file": ("user_meeting.m4a", f, "audio/m4a")}
            data = {"usage_type": "meeting"}
            
            upload_response = client.post("/api/v1/transcriptions", files=files, data=data)
            assert upload_response.status_code == 200
            job_id = upload_response.json()["job_id"]
        
        # 4. 処理状況を定期的に確認
        checks = 0
        while checks < 20:
            status_response = client.get(f"/api/v1/transcriptions/{job_id}")
            job_status = status_response.json()
            
            if job_status["status"] == "completed":
                break
            
            checks += 1
            time.sleep(1)
        
        # 5. 結果をダウンロード
        transcription = client.get(f"/api/v1/files/{job_id}/transcription.txt")
        assert transcription.status_code == 200
        
        summary = client.get(f"/api/v1/files/{job_id}/summary.txt")
        assert summary.status_code == 200
        
        # 6. ジョブ一覧で履歴確認
        jobs_list = client.get("/api/v1/transcriptions")
        assert jobs_list.status_code == 200
        jobs_data = jobs_list.json()
        assert any(job["id"] == job_id for job in jobs_data["jobs"])
        
        print(f"✅ ユーザージャーニーテスト成功 (Job ID: {job_id})")
    
    def test_error_user_experience(self, mock_services):
        """エラー時のユーザーエクスペリエンステスト"""
        client = TestClient(create_application())
        
        # 1. 不正なファイル形式
        invalid_files = {"audio_file": ("document.pdf", b"PDF content", "application/pdf")}
        data = {"usage_type": "meeting"}
        
        response = client.post("/api/v1/transcriptions", files=invalid_files, data=data)
        assert response.status_code == 400
        error_data = response.json()
        assert "detail" in error_data
        assert "ファイル形式" in error_data["detail"] or "format" in error_data["detail"]
        
        # 2. 用途未選択
        files = {"audio_file": ("test.m4a", b"dummy", "audio/m4a")}
        response = client.post("/api/v1/transcriptions", files=files)
        assert response.status_code == 422
        
        # 3. 存在しないジョブアクセス
        response = client.get("/api/v1/transcriptions/nonexistent-job")
        assert response.status_code == 404
        error_data = response.json()
        assert "detail" in error_data
        
        print("✅ エラーUXテスト成功")


class TestDataIntegrity:
    """データ整合性テスト"""
    
    def test_job_data_consistency(self, mock_services, real_audio_file):
        """ジョブデータの整合性テスト"""
        client = TestClient(create_application())
        
        # ジョブ作成
        with open(real_audio_file, 'rb') as f:
            files = {"audio_file": ("integrity_test.m4a", f, "audio/m4a")}
            data = {"usage_type": "interview"}
            
            response = client.post("/api/v1/transcriptions", files=files, data=data)
            job_id = response.json()["job_id"]
        
        # 処理完了まで待機
        for _ in range(30):
            status_response = client.get(f"/api/v1/transcriptions/{job_id}")
            job_data = status_response.json()
            
            if job_data["status"] == "completed":
                break
            time.sleep(1)
        
        # データの整合性確認
        final_job = client.get(f"/api/v1/transcriptions/{job_id}").json()
        transcription_json = client.get(f"/api/v1/files/{job_id}/transcription.json").json()
        summary_json = client.get(f"/api/v1/files/{job_id}/summary.json").json()
        
        # 関連データの整合性
        assert final_job["id"] == job_id
        assert final_job["usage_type"] == "interview"
        assert final_job["status"] == "completed"
        
        # 転写結果の整合性
        assert final_job["transcription_result"]["text"] == transcription_json["text"]
        
        # 要約結果の整合性（面接用構造）
        assert "candidate_assessment" in summary_json["summary"]
        assert "recommendation" in summary_json["summary"]
        
        print("✅ データ整合性テスト成功")


@pytest.fixture(autouse=True)
def cleanup_test_files():
    """テスト後のファイルクリーンアップ"""
    yield
    
    # テスト用に作成された一時ファイルの削除
    test_files = Path.cwd().glob("test_*.db")
    for test_file in test_files:
        try:
            test_file.unlink()
        except (FileNotFoundError, PermissionError):
            pass


if __name__ == "__main__":
    # E2Eテストの実行
    pytest.main([__file__, "-v", "-s"])