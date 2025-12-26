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
        b'\x00\x00\x00\x20ftypM4A \x00\x00\x00\x00M4A mp42isom\x00\x00\x00\x00'
        b'\x00\x00\x00\x28moov\x00\x00\x00\x20mvhd\x00\x00\x00\x00\x00\x00\x00\x00'
        b'\x00\x00\x00\x00\x00\x00\x03\xe8\x00\x00\x00\x00\x00\x01\x00\x00\x01\x00'
    )
    
    with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as f:
        f.write(m4a_header)
        f.write(b'\x00' * 1024)  # ダミーデータ
        f.flush()
        return f.name


@pytest.fixture
def mock_services():
    """全サービスのモック設定"""
    # AudioProcessor内でインスタンス化されるWhisperServiceとOllamaServiceをモック
    with patch('app.services.audio_processor.WhisperService') as MockWhisperService, \
         patch('app.services.audio_processor.OllamaService') as MockOllamaService:
        
        # Whisper サービスモック
        whisper_instance = MockWhisperService.return_value
        whisper_instance.transcribe_audio = AsyncMock(return_value={
            "text": "こんにちは。今日は M4A 転写システムのテストを実行しています。このシステムは音声ファイルをテキストに変換し、AI を使って要約を生成します。テストが正常に動作することを確認しています。",
            "language": "ja",
            "confidence": 0.95,
            "duration_seconds": 13.0,
            "model_used": "large-v3",
            "processing_time_seconds": 2.5,
            "segments": [
                {
                    "id": 0,
                    "segment_index": 0,
                    "start": 0.0,
                    "end": 5.0,
                    "text": "こんにちは。今日は M4A 転写システムのテストを実行しています。",
                    "confidence": 0.98,
                    "start_time": 0.0,
                    "end_time": 5.0,
                    "speaker_id": None,
                    "speaker_name": None
                },
                {
                    "id": 1,
                    "segment_index": 1,
                    "start": 5.0,
                    "end": 10.0,
                    "text": "このシステムは音声ファイルをテキストに変換し、AI を使って要約を生成します。",
                    "confidence": 0.95,
                    "start_time": 5.0,
                    "end_time": 10.0,
                    "speaker_id": None,
                    "speaker_name": None
                },
                {
                    "id": 2,
                    "segment_index": 2,
                    "start": 10.0,
                    "end": 13.0,
                    "text": "テストが正常に動作することを確認しています。",
                    "confidence": 0.99,
                    "start_time": 10.0,
                    "end_time": 13.0,
                    "speaker_id": None,
                    "speaker_name": None
                }
            ]
        })
        whisper_instance.health_check = AsyncMock(return_value={"status": "healthy"})
        
        # Ollama サービスモック
        ollama_instance = MockOllamaService.return_value
        ollama_instance.__aenter__.return_value = ollama_instance
        ollama_instance.__aexit__.return_value = None
        
        # correct_transcription mock
        ollama_instance.correct_transcription = AsyncMock(return_value={
            "corrected_text": "こんにちは。今日は M4A 転写システムのテストを実行しています。このシステムは音声ファイルをテキストに変換し、AI を使って要約を生成します。テストが正常に動作することを確認しています。",
            "original_text": "...",
            "corrections_made": False
        })
        
        # generate_summary mock
        ollama_instance.generate_summary = AsyncMock(return_value={
            "text": "M4A転写システムのテスト実行に関する会議。システム動作確認...",
            "formatted_text": "# 会議要約\n\n## 概要\nM4A転写システムのテスト\n\n## ポイント\n- 正常動作確認\n",
            "confidence": 0.9,
            "model_used": "gemma",
            "details": {
                "summary": "M4A転写システムのテスト実行に関する会議",
                "agenda": ["システム動作確認", "品質保証"],
                "decisions": ["全機能テスト完了へ"],
                "todo": ["テスト完了", "デプロイ準備"],
                "action_plans": ["ToDo: テスト完了", "ToDo: デプロイ準備"],
                "next_actions": ["デプロイ"],
                "next_meeting": "明日",
                "participants_count": 1,
                "meeting_duration_minutes": 30
            }
        })

        # For interview flow
        def side_effect_generate_summary(text, summary_type, **kwargs):
            if summary_type == "interview":
                return {
                    "text": "優秀なエンジニア候補の面接。",
                    "formatted_text": "# 面接要約\n...",
                    "confidence": 0.9,
                    "model_used": "gemma",
                    "details": {
                        "evaluation": {"overall": "A"},
                        "experience": "システム理解が深い", 
                        "career_axis": "技術志向",
                        "work_experience": "豊富な経験",
                        "character_analysis": "優秀",
                        "next_steps": "採用推奨",
                        "candidate_assessment": { # Old structure compat if needed
                            "strengths": ["理解力"],
                            "areas_for_improvement": ["速度"]
                        }
                    }
                }
            return ollama_instance.generate_summary.return_value

        ollama_instance.generate_summary.side_effect = side_effect_generate_summary
        
        ollama_instance.health_check = AsyncMock(return_value={"status": "healthy"})
        
        yield {"WhisperService": MockWhisperService, "OllamaService": MockOllamaService}


class TestCompleteWorkflow:
    """完全ワークフローのE2Eテスト"""
    
    def test_meeting_transcription_complete_flow(self, mock_services, real_audio_file):
        """会議音声の完全な転写・要約フローテスト"""
        client = TestClient(create_application())
        
        # 1. システム状態確認
        status_response = client.get("/api/v1/status")
        assert status_response.status_code == 200
        
        # 2. 音声ファイルアップロード
        with open(real_audio_file, 'rb') as f:
            files = {"audio_file": ("meeting_audio.m4a", f, "audio/m4a")}
            data = {"usage_type": "meeting"}
            
            upload_response = client.post("/api/v1/transcriptions", files=files, data=data)
            assert upload_response.status_code == 200
            
            job_data = upload_response.json()
            job_id = job_data["job_id"]
        
        # 3. 処理完了待機
        # テスト環境では非同期処理が即時実行されるわけではないが、
        # TestClientとSync処理またはバックグラウンドタスクがどう動くかによる
        # 通常FastAPIのBackgroundTasksはレスポンス後に走る
        # テストでは同期的に待つか、モックが即時完了するように振る舞う必要がある
        
        # 注: BackgroundTasksはTestClientではレスポンス返却後に実行される
        # ここで少し待つ
        time.sleep(1) # バックグラウンドタスク開始待ち
        
        # ポーリング (最大10秒)
        for _ in range(20):
            response = client.get(f"/api/v1/transcriptions/{job_id}")
            status = response.json()["status"]
            if status in ["completed", "failed", "error"]:
                break
            time.sleep(0.5)
            
        final_job = client.get(f"/api/v1/transcriptions/{job_id}").json()
        if final_job["status"] != "completed":
            pytest.fail(f"Job failed with status: {final_job['status']}, error: {final_job.get('error_message')}")
            
        assert final_job["status"] == "completed"
        assert "transcription_result" in final_job
        if final_job["transcription_result"]:
            assert final_job["transcription_result"]["text"] is not None
        
        # 5. ダウンロード確認
        txt = client.get(f"/api/v1/files/{job_id}/transcription.txt")
        assert txt.status_code == 200
        
        # エクスポート
        export = client.get(f"/api/v1/files/{job_id}/export")
        assert export.status_code == 200


    def test_api_response_times(self, mock_services):
        """API応答時間テスト"""
        client = TestClient(create_application())
        start = time.time()
        client.get("/health")
        duration = time.time() - start
        assert duration < 1.0

    def test_dummy(self):
        """プレースホルダー"""
        assert True