"""
モックサービス実装
"""

import asyncio
import json
import time
import random
from typing import Optional, Dict, Any, List
from unittest.mock import Mock, AsyncMock
from pathlib import Path


class MockWhisperService:
    """WhisperServiceのモック実装"""
    
    def __init__(self, 
                 response_delay: float = 1.0, 
                 failure_rate: float = 0.0,
                 confidence_range: tuple = (0.8, 0.98)):
        self.response_delay = response_delay
        self.failure_rate = failure_rate
        self.confidence_range = confidence_range
        self.call_count = 0
    
    def transcribe_audio(self, file_path: str) -> Optional[Dict[str, Any]]:
        """音声転写のモック実装"""
        self.call_count += 1
        
        # ファイル存在確認
        if not Path(file_path).exists():
            return None
        
        # 遅延シミュレーション
        time.sleep(self.response_delay)
        
        # 失敗レートに基づく失敗シミュレーション
        if random.random() < self.failure_rate:
            return None
        
        # ファイル名に基づく応答変更
        file_name = Path(file_path).stem.lower()
        
        if "english" in file_name or "en" in file_name:
            return self._create_english_response()
        elif "meeting" in file_name:
            return self._create_meeting_response()
        elif "interview" in file_name:
            return self._create_interview_response()
        elif "lecture" in file_name:
            return self._create_lecture_response()
        else:
            return self._create_default_response()
    
    def _create_default_response(self) -> Dict[str, Any]:
        """デフォルト転写結果"""
        confidence = random.uniform(*self.confidence_range)
        
        return {
            "text": "こんにちは。これはM4A転写システムのテストです。音声認識機能が正常に動作していることを確認しています。システムは期待通りに動作しており、高精度でテキスト変換が行われています。",
            "language": "ja",
            "segments": [
                {
                    "id": 0,
                    "start": 0.0,
                    "end": 3.0,
                    "text": "こんにちは。これはM4A転写システムのテストです。",
                    "confidence": confidence + 0.02
                },
                {
                    "id": 1,
                    "start": 3.0,
                    "end": 8.0,
                    "text": "音声認識機能が正常に動作していることを確認しています。",
                    "confidence": confidence
                },
                {
                    "id": 2,
                    "start": 8.0,
                    "end": 12.0,
                    "text": "システムは期待通りに動作しており、高精度でテキスト変換が行われています。",
                    "confidence": confidence - 0.01
                }
            ]
        }
    
    def _create_english_response(self) -> Dict[str, Any]:
        """英語転写結果"""
        confidence = random.uniform(*self.confidence_range)
        
        return {
            "text": "Hello, this is a test of the M4A transcription system. We are verifying that the speech recognition functionality is working correctly. The system is performing as expected with high accuracy text conversion.",
            "language": "en",
            "segments": [
                {
                    "id": 0,
                    "start": 0.0,
                    "end": 3.5,
                    "text": "Hello, this is a test of the M4A transcription system.",
                    "confidence": confidence
                },
                {
                    "id": 1,
                    "start": 3.5,
                    "end": 8.0,
                    "text": "We are verifying that the speech recognition functionality is working correctly.",
                    "confidence": confidence - 0.02
                },
                {
                    "id": 2,
                    "start": 8.0,
                    "end": 12.5,
                    "text": "The system is performing as expected with high accuracy text conversion.",
                    "confidence": confidence + 0.01
                }
            ]
        }
    
    def _create_meeting_response(self) -> Dict[str, Any]:
        """会議用転写結果"""
        return {
            "text": "本日の会議を開始いたします。議題は新しいプロジェクトの進捗について確認することです。まず、開発チームからの報告をお聞きします。プロジェクトは順調に進んでおり、予定より早く完成する見込みです。次に、マーケティング戦略について議論しましょう。来月のリリースに向けて準備を進めています。最後に、今後のスケジュールを確認して本日の会議を終了します。",
            "language": "ja",
            "segments": [
                {"id": 0, "start": 0.0, "end": 5.0, "text": "本日の会議を開始いたします。議題は新しいプロジェクトの進捗について確認することです。", "confidence": 0.96},
                {"id": 1, "start": 5.0, "end": 10.0, "text": "まず、開発チームからの報告をお聞きします。プロジェクトは順調に進んでおり、予定より早く完成する見込みです。", "confidence": 0.94},
                {"id": 2, "start": 10.0, "end": 15.0, "text": "次に、マーケティング戦略について議論しましょう。来月のリリースに向けて準備を進めています。", "confidence": 0.93},
                {"id": 3, "start": 15.0, "end": 18.0, "text": "最後に、今後のスケジュールを確認して本日の会議を終了します。", "confidence": 0.95}
            ]
        }
    
    def _create_interview_response(self) -> Dict[str, Any]:
        """面接用転写結果"""
        return {
            "text": "本日はお忙しい中、面接にお越しいただきありがとうございます。まず自己紹介をお願いいたします。私は田中と申します。エンジニアとして5年の経験があります。主にWebアプリケーションの開発に携わってきました。最近ではPythonとJavaScriptを使用したフルスタック開発を得意としています。チームでの協働を大切にし、常に新しい技術を学ぶことを心がけています。",
            "language": "ja",
            "segments": [
                {"id": 0, "start": 0.0, "end": 4.0, "text": "本日はお忙しい中、面接にお越しいただきありがとうございます。まず自己紹介をお願いいたします。", "confidence": 0.97},
                {"id": 1, "start": 4.0, "end": 8.0, "text": "私は田中と申します。エンジニアとして5年の経験があります。", "confidence": 0.95},
                {"id": 2, "start": 8.0, "end": 12.0, "text": "主にWebアプリケーションの開発に携わってきました。最近ではPythonとJavaScriptを使用したフルスタック開発を得意としています。", "confidence": 0.92},
                {"id": 3, "start": 12.0, "end": 16.0, "text": "チームでの協働を大切にし、常に新しい技術を学ぶことを心がけています。", "confidence": 0.94}
            ]
        }
    
    def _create_lecture_response(self) -> Dict[str, Any]:
        """講義用転写結果"""
        return {
            "text": "今日の講義では機械学習の基礎について説明します。まず機械学習とは何かから始めましょう。機械学習は人工知能の一分野で、データからパターンを学習するアルゴリズムです。教師あり学習と教師なし学習の二つに大別されます。教師あり学習では正解データを使って学習を行います。一方、教師なし学習では正解データがない状態でパターンを発見します。次回は具体的なアルゴリズムについて詳しく説明します。",
            "language": "ja",
            "segments": [
                {"id": 0, "start": 0.0, "end": 5.0, "text": "今日の講義では機械学習の基礎について説明します。まず機械学習とは何かから始めましょう。", "confidence": 0.96},
                {"id": 1, "start": 5.0, "end": 10.0, "text": "機械学習は人工知能の一分野で、データからパターンを学習するアルゴリズムです。", "confidence": 0.94},
                {"id": 2, "start": 10.0, "end": 15.0, "text": "教師あり学習と教師なし学習の二つに大別されます。教師あり学習では正解データを使って学習を行います。", "confidence": 0.93},
                {"id": 3, "start": 15.0, "end": 20.0, "text": "一方、教師なし学習では正解データがない状態でパターンを発見します。次回は具体的なアルゴリズムについて詳しく説明します。", "confidence": 0.91}
            ]
        }


class MockOllamaService:
    """OllamaServiceのモック実装"""
    
    def __init__(self, 
                 response_delay: float = 2.0, 
                 failure_rate: float = 0.0,
                 available: bool = True):
        self.response_delay = response_delay
        self.failure_rate = failure_rate
        self.available = available
        self.call_count = 0
    
    async def is_available(self) -> bool:
        """サービス利用可能性確認"""
        return self.available
    
    async def generate_meeting_summary(self, transcription_text: str) -> Optional[Dict[str, Any]]:
        """会議要約生成のモック実装"""
        self.call_count += 1
        
        # 遅延シミュレーション
        await asyncio.sleep(self.response_delay)
        
        # 失敗シミュレーション
        if random.random() < self.failure_rate:
            return None
        
        # テキスト長に基づく詳細度調整
        is_detailed = len(transcription_text) > 200
        
        return {
            "overview": "会議の主要な内容について議論され、プロジェクトの進捗確認と今後の方針について合意が得られました。" + 
                       (" 詳細な議論が行われ、多角的な観点から検討されました。" if is_detailed else ""),
            "key_points": [
                "プロジェクトの現在の進捗状況の確認",
                "次のマイルストーンに向けた課題の特定",
                "チーム間の連携強化の必要性",
                "リソース配分の最適化"
            ] + (["品質保証プロセスの改善", "ユーザーフィードバックの活用"] if is_detailed else []),
            "action_items": [
                "来週までに詳細なスケジュールを作成",
                "関係部署との調整会議を設定",
                "技術的な課題の解決策を検討"
            ] + (["外部ベンダーとの打ち合わせ実施"] if is_detailed else []),
            "participants": ["プロジェクトマネージャー", "開発リーダー", "デザイナー"] + 
                          (["品質保証担当", "マーケティング担当"] if is_detailed else []),
            "next_meeting": "来週火曜日 14:00",
            "duration_minutes": 45 if is_detailed else 30
        }
    
    async def generate_interview_summary(self, transcription_text: str) -> Optional[Dict[str, Any]]:
        """面接要約生成のモック実装"""
        self.call_count += 1
        
        await asyncio.sleep(self.response_delay)
        
        if random.random() < self.failure_rate:
            return None
        
        # 候補者評価のランダム性
        strengths_options = [
            ["コミュニケーション能力が優秀", "技術的理解力が高い", "問題解決能力に長けている"],
            ["学習意欲が旺盛", "チームワークを重視", "責任感が強い"],
            ["創造的思考ができる", "リーダーシップ素質がある", "顧客志向が強い"]
        ]
        
        improvements_options = [
            ["大規模プロジェクト経験が不足", "マネジメント経験を積む必要"],
            ["特定技術分野の深掘りが必要", "プレゼンテーション能力の向上"],
            ["業界知識の拡充", "国際的な経験を積む必要"]
        ]
        
        recommendations = ["強く採用推奨", "採用推奨", "条件付き採用推奨", "要再検討"]
        
        strengths = random.choice(strengths_options)
        improvements = random.choice(improvements_options)
        recommendation = random.choice(recommendations[:2])  # ポジティブな評価を多く
        
        return {
            "candidate_assessment": {
                "strengths": strengths,
                "areas_for_improvement": improvements,
                "technical_skills": {
                    "programming": ["Python", "JavaScript", "SQL"],
                    "frameworks": ["FastAPI", "React", "Vue.js"],
                    "tools": ["Git", "Docker", "AWS"],
                    "databases": ["PostgreSQL", "MongoDB"]
                },
                "overall_impression": "優秀な候補者" if recommendation.startswith("強く") else "良好な候補者"
            },
            "questions_and_answers": [
                {
                    "question": "これまでの経験について教えてください",
                    "answer": "Webアプリケーション開発を中心に経験を積んできました",
                    "evaluation": "具体的で説得力のある回答"
                },
                {
                    "question": "困難な課題をどう解決しますか",
                    "answer": "問題を分析し、段階的にアプローチします",
                    "evaluation": "論理的な思考プロセスを示している"
                }
            ],
            "recommendation": recommendation,
            "recommended_position": "ミドルレベル・エンジニア",
            "next_steps": [
                "技術テストの実施",
                "チーム面接の調整",
                "リファレンスチェック"
            ]
        }
    
    async def generate_lecture_summary(self, transcription_text: str) -> Optional[Dict[str, Any]]:
        """講義要約生成のモック実装"""
        self.call_count += 1
        
        await asyncio.sleep(self.response_delay)
        
        if random.random() < self.failure_rate:
            return None
        
        return {
            "lecture_info": {
                "title": "テスト講義",
                "instructor": "講師名",
                "duration_minutes": 90,
                "topic": "技術トピック"
            },
            "key_concepts": [
                "基本的な概念の理解",
                "実践的な応用方法",
                "理論と実装の関係",
                "最新動向と将来展望"
            ],
            "important_points": [
                "理論的背景の重要性",
                "実践での注意点",
                "業界での活用例",
                "継続学習の必要性"
            ],
            "examples_discussed": [
                "具体例1: 基本的なケース",
                "具体例2: 応用的なケース",
                "具体例3: 複合的なケース"
            ],
            "assignments": [
                "次回までに配布資料を復習",
                "演習問題1-5を解く",
                "関連文献を読む"
            ],
            "next_lecture": "来週: 応用編"
        }


class MockAudioProcessor:
    """AudioProcessorのモック実装"""
    
    def __init__(self, whisper_service: MockWhisperService, ollama_service: MockOllamaService):
        self.whisper_service = whisper_service
        self.ollama_service = ollama_service
        self.processing_count = 0
    
    async def process_audio_file(self, file_path: str, usage_type: str) -> Optional[Dict[str, Any]]:
        """音声ファイル処理のモック実装"""
        self.processing_count += 1
        
        # 転写処理
        transcription_result = self.whisper_service.transcribe_audio(file_path)
        if not transcription_result:
            return None
        
        # 要約生成
        summary_result = None
        if usage_type == "meeting":
            summary_result = await self.ollama_service.generate_meeting_summary(transcription_result["text"])
        elif usage_type == "interview":
            summary_result = await self.ollama_service.generate_interview_summary(transcription_result["text"])
        elif usage_type == "lecture":
            summary_result = await self.ollama_service.generate_lecture_summary(transcription_result["text"])
        
        result = {
            "transcription": transcription_result
        }
        
        if summary_result:
            result["summary"] = summary_result
        
        return result


class MockServiceFactory:
    """モックサービスファクトリー"""
    
    @staticmethod
    def create_fast_services():
        """高速レスポンス用サービス（テスト用）"""
        whisper = MockWhisperService(response_delay=0.1, failure_rate=0.0)
        ollama = MockOllamaService(response_delay=0.2, failure_rate=0.0)
        processor = MockAudioProcessor(whisper, ollama)
        
        return whisper, ollama, processor
    
    @staticmethod
    def create_realistic_services():
        """実際のサービスに近い応答時間"""
        whisper = MockWhisperService(response_delay=2.0, failure_rate=0.05)
        ollama = MockOllamaService(response_delay=5.0, failure_rate=0.03)
        processor = MockAudioProcessor(whisper, ollama)
        
        return whisper, ollama, processor
    
    @staticmethod
    def create_unreliable_services():
        """不安定なサービス（エラーテスト用）"""
        whisper = MockWhisperService(response_delay=1.0, failure_rate=0.3)
        ollama = MockOllamaService(response_delay=3.0, failure_rate=0.4, available=False)
        processor = MockAudioProcessor(whisper, ollama)
        
        return whisper, ollama, processor
    
    @staticmethod
    def create_slow_services():
        """低速サービス（パフォーマンステスト用）"""
        whisper = MockWhisperService(response_delay=10.0, failure_rate=0.0)
        ollama = MockOllamaService(response_delay=15.0, failure_rate=0.0)
        processor = MockAudioProcessor(whisper, ollama)
        
        return whisper, ollama, processor


class MockDatabase:
    """モックデータベース実装"""
    
    def __init__(self):
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.transcription_results: Dict[str, Dict[str, Any]] = {}
        self.summary_results: Dict[str, Dict[str, Any]] = {}
        self.next_id = 1
    
    def create_job(self, filename: str, file_size: int, usage_type: str) -> str:
        """ジョブ作成"""
        job_id = f"mock-job-{self.next_id}"
        self.next_id += 1
        
        self.jobs[job_id] = {
            "id": job_id,
            "filename": filename,
            "file_size": file_size,
            "usage_type": usage_type,
            "status": "pending",
            "created_at": time.time(),
            "updated_at": time.time()
        }
        
        return job_id
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """ジョブ取得"""
        return self.jobs.get(job_id)
    
    def update_job_status(self, job_id: str, status: str, **kwargs):
        """ジョブステータス更新"""
        if job_id in self.jobs:
            self.jobs[job_id]["status"] = status
            self.jobs[job_id]["updated_at"] = time.time()
            self.jobs[job_id].update(kwargs)
    
    def delete_job(self, job_id: str) -> bool:
        """ジョブ削除"""
        if job_id in self.jobs:
            del self.jobs[job_id]
            if job_id in self.transcription_results:
                del self.transcription_results[job_id]
            if job_id in self.summary_results:
                del self.summary_results[job_id]
            return True
        return False
    
    def save_transcription_result(self, job_id: str, result: Dict[str, Any]):
        """転写結果保存"""
        self.transcription_results[job_id] = result
    
    def save_summary_result(self, job_id: str, result: Dict[str, Any]):
        """要約結果保存"""
        self.summary_results[job_id] = result
    
    def list_jobs(self, skip: int = 0, limit: int = 10) -> tuple:
        """ジョブ一覧取得"""
        all_jobs = list(self.jobs.values())
        total = len(all_jobs)
        jobs = all_jobs[skip:skip + limit]
        return jobs, total


# テスト用のグローバルモックインスタンス
_mock_db = MockDatabase()
_fast_whisper, _fast_ollama, _fast_processor = MockServiceFactory.create_fast_services()


def get_mock_services():
    """モックサービス取得"""
    return {
        "whisper": _fast_whisper,
        "ollama": _fast_ollama,
        "processor": _fast_processor,
        "database": _mock_db
    }


def reset_mock_services():
    """モックサービスリセット"""
    global _mock_db, _fast_whisper, _fast_ollama, _fast_processor
    
    _mock_db = MockDatabase()
    _fast_whisper, _fast_ollama, _fast_processor = MockServiceFactory.create_fast_services()


# プリセット設定
MOCK_PRESETS = {
    "fast": MockServiceFactory.create_fast_services,
    "realistic": MockServiceFactory.create_realistic_services,
    "unreliable": MockServiceFactory.create_unreliable_services,
    "slow": MockServiceFactory.create_slow_services
}