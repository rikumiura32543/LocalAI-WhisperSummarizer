#!/usr/bin/env python3
"""
フロントエンドテスト用の簡易サーバー
"""

import json
import time
from typing import Dict, Any
from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import uuid

app = FastAPI(
    title="M4A Transcription Test Server",
    description="フロントエンドテスト用の模擬API"
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静的ファイル設定
app.mount("/static", StaticFiles(directory="static"), name="static")

# 模擬データベース
jobs: Dict[str, Dict[str, Any]] = {}

@app.get("/")
async def read_root():
    return FileResponse("static/index.html")

@app.get("/health")
async def health_check():
    return {"status": "active", "timestamp": time.time()}

@app.get("/api/v1/status")
async def get_status():
    return {
        "status": "active",
        "version": "1.0.0-test",
        "services": {
            "whisper": "ready",
            "ollama": "ready"
        }
    }

@app.post("/api/v1/transcriptions")
async def create_transcription(
    audio_file: UploadFile = File(...),
    usage_type: str = Form(...)
):
    job_id = str(uuid.uuid4())
    
    # ファイルサイズを模擬データとして計算
    content = await audio_file.read()
    file_size = len(content)
    
    job_data = {
        "id": job_id,
        "filename": audio_file.filename,
        "file_size": file_size,
        "usage_type": usage_type,
        "status": "processing",
        "processing_step": "upload",
        "created_at": time.time(),
        "processing_duration": None,
        "audio_duration": 120,  # 2分の音声として模擬
        "detected_language": "ja",
        "confidence": 0.95
    }
    
    jobs[job_id] = job_data
    
    return {"job_id": job_id, "status": "processing"}

@app.get("/api/v1/transcriptions/{job_id}")
async def get_transcription_status(job_id: str):
    if job_id not in jobs:
        return JSONResponse(
            status_code=404,
            content={"detail": "Job not found"}
        )
    
    job = jobs[job_id]
    
    # 模擬的な処理進捗更新
    elapsed = time.time() - job["created_at"]
    
    if elapsed < 5:
        job["status"] = "processing"
        job["processing_step"] = "upload"
    elif elapsed < 15:
        job["status"] = "processing"
        job["processing_step"] = "transcription"
    elif elapsed < 25:
        job["status"] = "processing"
        job["processing_step"] = "summarization"
    elif elapsed < 30:
        job["status"] = "processing"
        job["processing_step"] = "finalization"
    else:
        # 処理完了
        job["status"] = "completed"
        job["processing_duration"] = elapsed
        job["transcription_result"] = {
            "text": f"これは{job['usage_type']}の転写結果のサンプルです。実際のWhisperによる音声認識結果がここに表示されます。音声の内容に応じて適切な日本語テキストが生成されます。"
        }
        job["summary_result"] = {
            "summary": {
                "overview": f"{job['usage_type']}の主要な議論点について話し合われました。",
                "key_points": [
                    "重要なポイント1：プロジェクトの進捗について",
                    "重要なポイント2：次回までのアクションアイテム",
                    "重要なポイント3：予算と資源の配分"
                ],
                "action_items": [
                    "来週までに資料を準備する",
                    "関係者への連絡と調整を行う"
                ]
            },
            "model": "llama3.2:3b",
            "confidence": 0.88
        }
    
    return job

@app.delete("/api/v1/transcriptions/{job_id}")
async def cancel_transcription(job_id: str):
    if job_id not in jobs:
        return JSONResponse(
            status_code=404,
            content={"detail": "Job not found"}
        )
    
    del jobs[job_id]
    return {"message": "Job cancelled"}

@app.get("/api/v1/files/{job_id}/transcription.txt")
async def download_transcription_txt(job_id: str):
    if job_id not in jobs:
        return JSONResponse(
            status_code=404,
            content={"detail": "Job not found"}
        )
    
    job = jobs[job_id]
    if job["status"] != "completed":
        return JSONResponse(
            status_code=400,
            content={"detail": "Job not completed"}
        )
    
    text = job.get("transcription_result", {}).get("text", "")
    
    return JSONResponse(
        content=text,
        headers={
            "Content-Type": "text/plain; charset=utf-8",
            "Content-Disposition": f"attachment; filename=transcription_{job_id}.txt"
        }
    )

@app.get("/api/v1/files/{job_id}/transcription.json")
async def download_transcription_json(job_id: str):
    if job_id not in jobs:
        return JSONResponse(
            status_code=404,
            content={"detail": "Job not found"}
        )
    
    job = jobs[job_id]
    if job["status"] != "completed":
        return JSONResponse(
            status_code=400,
            content={"detail": "Job not completed"}
        )
    
    return JSONResponse(
        content=job.get("transcription_result", {}),
        headers={
            "Content-Disposition": f"attachment; filename=transcription_{job_id}.json"
        }
    )

@app.get("/api/v1/files/{job_id}/summary.txt")
async def download_summary_txt(job_id: str):
    if job_id not in jobs:
        return JSONResponse(
            status_code=404,
            content={"detail": "Job not found"}
        )
    
    job = jobs[job_id]
    if job["status"] != "completed":
        return JSONResponse(
            status_code=400,
            content={"detail": "Job not completed"}
        )
    
    summary = job.get("summary_result", {}).get("summary", {})
    text = f"【概要】\n{summary.get('overview', '')}\n\n"
    
    if summary.get('key_points'):
        text += "【主要ポイント】\n"
        for point in summary['key_points']:
            text += f"• {point}\n"
        text += "\n"
    
    if summary.get('action_items'):
        text += "【アクションアイテム】\n"
        for item in summary['action_items']:
            text += f"• {item}\n"
    
    return JSONResponse(
        content=text,
        headers={
            "Content-Type": "text/plain; charset=utf-8",
            "Content-Disposition": f"attachment; filename=summary_{job_id}.txt"
        }
    )

@app.get("/api/v1/files/{job_id}/summary.json")
async def download_summary_json(job_id: str):
    if job_id not in jobs:
        return JSONResponse(
            status_code=404,
            content={"detail": "Job not found"}
        )
    
    job = jobs[job_id]
    if job["status"] != "completed":
        return JSONResponse(
            status_code=400,
            content={"detail": "Job not completed"}
        )
    
    return JSONResponse(
        content=job.get("summary_result", {}),
        headers={
            "Content-Disposition": f"attachment; filename=summary_{job_id}.json"
        }
    )

@app.get("/api/v1/files/{job_id}/export")
async def download_export(job_id: str):
    # 模擬的なZIPファイル応答
    return JSONResponse(
        status_code=501,
        content={"detail": "Export functionality not implemented in test server"}
    )

if __name__ == "__main__":
    print("🚀 フロントエンドテスト用サーバー起動中...")
    print("📱 http://localhost:8002 でアクセス可能です")
    print("⚠️  これは開発・テスト専用のサーバーです")
    uvicorn.run(app, host="0.0.0.0", port=8002)