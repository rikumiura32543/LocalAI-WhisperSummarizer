"""
Ollamaサービス
"""

import asyncio
import json
import httpx
import structlog
from typing import Dict, Any, Optional, List, Union
from pathlib import Path

from app.core.config import settings


logger = structlog.get_logger(__name__)


class OllamaError(Exception):
    """Ollama関連エラー"""
    pass


class OllamaService:
    """Ollamaサービスクラス"""
    
    def __init__(self, base_url: str = None, timeout: int = None):
        self.base_url = base_url or settings.OLLAMA_BASE_URL
        self.timeout = timeout or settings.OLLAMA_TIMEOUT
        self.model = settings.OLLAMA_MODEL
        
        # HTTPクライアント設定
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout)
        )
        
        logger.info("Ollama service initialized",
                   base_url=self.base_url,
                   model=self.model,
                   timeout=self.timeout)
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def check_connection(self) -> bool:
        """Ollama接続確認"""
        try:
            response = await self.client.get("/api/tags")
            return response.status_code == 200
        except Exception as e:
            logger.error("Ollama connection check failed", error=str(e))
            return False
    
    async def list_models(self) -> List[Dict[str, Any]]:
        """利用可能モデル一覧取得"""
        try:
            response = await self.client.get("/api/tags")
            response.raise_for_status()
            data = response.json()
            
            models = data.get("models", [])
            logger.info("Models retrieved", count=len(models))
            return models
            
        except httpx.HTTPError as e:
            logger.error("Failed to list models", error=str(e))
            raise OllamaError(f"モデル一覧の取得に失敗しました: {e}")
        except Exception as e:
            logger.error("Unexpected error in list_models", error=str(e))
            raise OllamaError(f"予期しないエラー: {e}")
    
    async def pull_model(self, model_name: str) -> bool:
        """モデルダウンロード"""
        try:
            logger.info("Pulling model", model=model_name)
            
            response = await self.client.post(
                "/api/pull",
                json={"name": model_name},
                timeout=httpx.Timeout(connect=30, read=None, write=30, pool=30)
            )
            
            if response.status_code != 200:
                raise OllamaError(f"モデルの取得に失敗しました: {response.status_code}")
            
            # ストリームレスポンス処理
            async for line in response.aiter_lines():
                if line.strip():
                    try:
                        data = json.loads(line)
                        if "status" in data:
                            logger.info("Pull progress", 
                                      model=model_name,
                                      status=data["status"],
                                      progress=data.get("completed", 0))
                        
                        # 完了チェック
                        if data.get("status") == "success":
                            logger.info("Model pulled successfully", model=model_name)
                            return True
                    except json.JSONDecodeError:
                        continue
            
            return True
            
        except httpx.HTTPError as e:
            logger.error("Failed to pull model", model=model_name, error=str(e))
            raise OllamaError(f"モデルの取得に失敗しました: {e}")
        except Exception as e:
            logger.error("Unexpected error in pull_model", model=model_name, error=str(e))
            raise OllamaError(f"予期しないエラー: {e}")
    
    async def check_model_exists(self, model_name: str = None) -> bool:
        """モデル存在確認"""
        model_name = model_name or self.model
        
        try:
            models = await self.list_models()
            model_names = [model["name"] for model in models]
            exists = model_name in model_names
            
            logger.info("Model existence check", 
                       model=model_name,
                       exists=exists)
            return exists
            
        except Exception as e:
            logger.error("Model existence check failed", 
                        model=model_name,
                        error=str(e))
            return False
    
    async def generate_summary(self, 
                             text: str,
                             summary_type: str = "meeting",
                             max_tokens: int = 1000) -> Dict[str, Any]:
        """AI要約生成"""
        try:
            # プロンプトテンプレート選択
            prompt = self._build_summary_prompt(text, summary_type)
            
            logger.info("Generating summary",
                       text_length=len(text),
                       summary_type=summary_type,
                       model=self.model)
            
            # Ollama API呼び出し
            response = await self.client.post(
                "/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": max_tokens,
                        "temperature": 0.7,
                        "top_p": 0.9
                    }
                }
            )
            
            response.raise_for_status()
            result = response.json()
            
            # レスポンス解析
            generated_text = result.get("response", "")
            if not generated_text:
                raise OllamaError("空の要約が生成されました")
            
            # 要約結果構造化
            summary_data = self._parse_summary_response(generated_text, summary_type)
            
            logger.info("Summary generated successfully",
                       output_length=len(generated_text),
                       summary_type=summary_type)
            
            return {
                "text": summary_data.get("summary", generated_text),
                "formatted_text": self._format_summary(summary_data, summary_type),
                "confidence": 0.85,  # Ollamaは信頼度を返さないので固定値
                "model_used": self.model,
                "details": summary_data.get("details", {}),
                "type": summary_type
            }
            
        except httpx.HTTPError as e:
            logger.error("HTTP error in generate_summary", error=str(e))
            raise OllamaError(f"要約生成に失敗しました: {e}")
        except Exception as e:
            logger.error("Unexpected error in generate_summary", error=str(e))
            raise OllamaError(f"予期しないエラー: {e}")

    async def correct_transcription(self, text: str) -> Dict[str, Any]:
        """AI文脈補正：書き起こしテキストの誤字脱字・文脈を補正"""
        try:
            # 文脈補正用プロンプト
            prompt = f"""以下は音声認識システムで書き起こされた日本語テキストです。
音声認識の誤りや不自然な表現を修正し、読みやすく整形してください。

修正のルール:
1. 誤字脱字を修正する
2. 文脈から明らかに間違っている単語を正しい単語に置き換える
3. 句読点を適切に追加する
4. 改行を適切に追加して読みやすくする
5. 元の意味を変えない
6. 敬語や話し言葉はそのまま残す
7. 専門用語や固有名詞は文脈から推測して正確に修正する

【元のテキスト】
{text}

【修正後のテキスト】
"""
            
            logger.info("Correcting transcription text",
                       text_length=len(text),
                       model=self.model)
            
            # Ollama API呼び出し
            response = await self.client.post(
                "/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": 2000,
                        "temperature": 0.3,  # 低めの温度で一貫性を保つ
                        "top_p": 0.9
                    }
                }
            )
            
            response.raise_for_status()
            result = response.json()
            
            corrected_text = result.get("response", "").strip()
            if not corrected_text:
                logger.warning("Empty correction result, returning original text")
                corrected_text = text
            
            logger.info("Transcription corrected successfully",
                       original_length=len(text),
                       corrected_length=len(corrected_text))
            
            return {
                "corrected_text": corrected_text,
                "original_text": text,
                "model_used": self.model,
                "corrections_made": len(text) != len(corrected_text)
            }
            
        except httpx.HTTPError as e:
            logger.error("HTTP error in correct_transcription", error=str(e))
            # エラー時は元のテキストを返す
            return {
                "corrected_text": text,
                "original_text": text,
                "model_used": self.model,
                "corrections_made": False,
                "error": str(e)
            }
        except Exception as e:
            logger.error("Unexpected error in correct_transcription", error=str(e))
            return {
                "corrected_text": text,
                "original_text": text,
                "model_used": self.model,
                "corrections_made": False,
                "error": str(e)
            }
    
    
    def _build_summary_prompt(self, text: str, summary_type: str) -> str:
        """要約プロンプト構築"""
        
        if summary_type == "meeting":
            return f"""
以下の会議の転写テキストを分析し、構造化された要約を作成してください。

転写テキスト:
{text}

以下のJSON形式で要約を作成してください:
{{
    "summary": "会議の概要（3-5行）",
    "details": {{
        "summary": "詳細な会議内容",
        "agenda": ["議題・議論内容1", "議題・議論内容2"],
        "decisions": ["決定事項1", "決定事項2"],
        "todo": ["ToDo1（担当者）", "ToDo2（担当者）"],
        "next_actions": ["次のアクション1", "次のアクション2"],
        "next_meeting": "次回会議予定（あれば）"
    }}
}}

必ず日本語で回答してください。
"""
        
        elif summary_type == "interview":
            return f"""
以下の面接の転写テキストを分析し、構造化された要約を作成してください。

転写テキスト:
{text}

以下のJSON形式で要約を作成してください:
{{
    "summary": "面接の概要（3-5行）",
    "details": {{
        "position_applied": "応募職種",
        "experience": "経験・スキルサマリー",
        "career_axis": "キャリアの軸・志向",
        "work_experience": "職務経験詳細",
        "character_analysis": "人物分析",
        "next_steps": "次のステップ・評価"
    }}
}}

日本語で回答してください。
"""
        
        else:  # 汎用
            return f"""
以下のテキストを簡潔に要約してください。

テキスト:
{text}

要点を3-5行でまとめ、日本語で回答してください。
"""
    
    def _parse_summary_response(self, response: str, summary_type: str) -> Dict[str, Any]:
        """要約レスポンス解析"""
        try:
            # JSON形式の場合は解析
            # マークダウンのコードブロックが含まれる場合の対応
            cleaned_response = response.strip()
            if "```json" in cleaned_response:
                import re
                match = re.search(r'```json\s*(.*?)\s*```', cleaned_response, re.DOTALL)
                if match:
                    cleaned_response = match.group(1)
            elif "```" in cleaned_response:
                import re
                match = re.search(r'```\s*(.*?)\s*```', cleaned_response, re.DOTALL)
                if match:
                    cleaned_response = match.group(1)
            
            if cleaned_response.startswith("{"):
                return json.loads(cleaned_response)
            
            # プレーンテキストの場合は構造化
            return {
                "summary": response.strip(),
                "details": {}
            }
            
        except json.JSONDecodeError:
            logger.warning("Failed to parse JSON response, using as plain text")
            return {
                "summary": response.strip(),
                "details": {}
            }
    
    def _format_summary(self, data: Dict[str, Any], summary_type: str) -> str:
        """要約整形 (Markdown)"""
        formatted_lines = []
        
        # 基本要約
        summary = data.get("summary", "")
        if summary:
            formatted_lines.append(f"# 要約\n{summary}")
            formatted_lines.append("")
        
        # 詳細情報
        details = data.get("details", {})
        
        if summary_type == "meeting" and details:
            # 会議要約のフォーマット - 要求仕様: 議題・議論内容, 決定事項, ToDo, 次のアクション
            
            if details.get("agenda"):
                formatted_lines.append("## 議題・議論内容")
                for item in details["agenda"]:
                    formatted_lines.append(f"- {item}")
                formatted_lines.append("")

            if details.get("decisions"):
                formatted_lines.append("## 決定事項")
                for decision in details["decisions"]:
                    formatted_lines.append(f"- {decision}")
                formatted_lines.append("")
            
            if details.get("todo"):
                formatted_lines.append("## ToDo")
                for item in details["todo"]:
                    formatted_lines.append(f"- [ ] {item}")
                formatted_lines.append("")

            if details.get("next_actions"):
                formatted_lines.append("## 次のアクション")
                for item in details["next_actions"]:
                    formatted_lines.append(f"- {item}")
                formatted_lines.append("")
            
            if details.get("next_meeting"):
                formatted_lines.append(f"## 次回会議\n{details['next_meeting']}")
        
        elif summary_type == "interview" and details:
            if details.get("experience"):
                formatted_lines.append("## 経験・スキル")
                formatted_lines.append(details["experience"])
                formatted_lines.append("")
            
            if details.get("character_analysis"):
                formatted_lines.append("## 人物分析")
                formatted_lines.append(details["character_analysis"])
                formatted_lines.append("")
        
        return "\n".join(formatted_lines).strip()
    
    async def health_check(self) -> Dict[str, Any]:
        """Ollamaヘルスチェック"""
        try:
            # 接続確認
            is_connected = await self.check_connection()
            
            if not is_connected:
                return {
                    "status": "error",
                    "message": "Ollamaサーバーに接続できません"
                }
            
            # モデル確認
            model_exists = await self.check_model_exists()
            
            if not model_exists:
                return {
                    "status": "warning", 
                    "message": f"モデル '{self.model}' が見つかりません"
                }
            
            return {
                "status": "healthy",
                "message": "Ollamaサービス正常",
                "model": self.model,
                "base_url": self.base_url
            }
            
        except Exception as e:
            logger.error("Health check failed", error=str(e))
            return {
                "status": "error",
                "message": f"ヘルスチェックエラー: {e}"
            }


# 便利関数
async def get_ollama_service() -> OllamaService:
    """Ollamaサービス取得（依存注入用）"""
    return OllamaService()


async def ensure_model_available(model_name: str = None) -> bool:
    """モデル利用可能確認・自動取得"""
    model_name = model_name or settings.OLLAMA_MODEL
    
    async with OllamaService() as ollama:
        # モデル存在確認
        if await ollama.check_model_exists(model_name):
            logger.info("Model already available", model=model_name)
            return True
        
        # モデル取得
        logger.info("Model not found, pulling...", model=model_name)
        try:
            await ollama.pull_model(model_name)
            return True
        except Exception as e:
            logger.error("Failed to pull model", model=model_name, error=str(e))
            return False