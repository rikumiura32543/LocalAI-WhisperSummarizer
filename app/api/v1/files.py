"""
ファイル関連API
"""

from typing import List
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.transcription_service import TranscriptionService
from app.services.summary_service import SummaryService
from app.api.models import GeneratedFileResponse, BaseResponse
import structlog

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/{job_id}/transcription/txt")
async def download_transcription_txt(
    job_id: str,
    db: Session = Depends(get_db)
):
    """転写結果テキストファイルダウンロード"""
    
    service = TranscriptionService(db)
    
    # ジョブ存在確認
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="指定されたジョブが見つかりません"
        )
    
    # 転写結果取得
    result = service.get_transcription_result(job_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="転写結果が見つかりません"
        )
    
    # ファイル名生成
    safe_filename = job.original_filename.replace(" ", "_").replace("/", "_")
    filename = f"transcription_{safe_filename.split('.')[0]}.txt"
    
    # テキストコンテンツ生成
    content = f"""転写結果
ファイル名: {job.original_filename}
処理日時: {result.created_at.strftime('%Y-%m-%d %H:%M:%S')}
使用モデル: {result.model_used}
信頼度: {result.confidence:.2f}
音声長: {result.duration_seconds:.1f}秒
言語: {result.language}

--- 転写テキスト ---
{result.text}
"""
    
    # ダウンロードログ記録
    logger.info("Transcription text downloaded", 
               job_id=job_id,
               filename=filename)
    
    return Response(
        content=content,
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}"
        }
    )


@router.get("/{job_id}/transcription/json")
async def download_transcription_json(
    job_id: str,
    include_segments: bool = True,
    db: Session = Depends(get_db)
):
    """転写結果JSONファイルダウンロード"""
    
    service = TranscriptionService(db)
    
    # ジョブ存在確認
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="指定されたジョブが見つかりません"
        )
    
    # 転写結果取得
    result = service.get_transcription_result(job_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="転写結果が見つかりません"
        )
    
    # JSON データ生成
    data = {
        "job": {
            "id": job.id,
            "original_filename": job.original_filename,
            "usage_type": job.usage_type_code,
            "created_at": job.created_at.isoformat(),
            "file_size": job.file_size
        },
        "transcription": {
            "text": result.text,
            "confidence": result.confidence,
            "language": result.language,
            "duration_seconds": result.duration_seconds,
            "model_used": result.model_used,
            "processing_time_seconds": result.processing_time_seconds,
            "segments_count": result.segments_count,
            "created_at": result.created_at.isoformat()
        }
    }
    
    # セグメント追加
    if include_segments:
        segments = service.get_transcription_segments(job_id)
        data["transcription"]["segments"] = [
            {
                "index": seg.segment_index,
                "start_time": seg.start_time,
                "end_time": seg.end_time,
                "text": seg.text,
                "confidence": seg.confidence,
                "speaker_id": seg.speaker_id,
                "speaker_name": seg.speaker_name
            }
            for seg in segments
        ]
    
    # ファイル名生成
    safe_filename = job.original_filename.replace(" ", "_").replace("/", "_")
    filename = f"transcription_{safe_filename.split('.')[0]}.json"
    
    # ダウンロードログ記録
    logger.info("Transcription JSON downloaded", 
               job_id=job_id,
               filename=filename,
               include_segments=include_segments)
    
    import json
    return Response(
        content=json.dumps(data, ensure_ascii=False, indent=2),
        media_type="application/json; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}"
        }
    )


@router.get("/{job_id}/summary/txt")
async def download_summary_txt(
    job_id: str,
    db: Session = Depends(get_db)
):
    """要約結果テキストファイルダウンロード"""
    
    # ジョブ存在確認
    transcription_service = TranscriptionService(db)
    job = transcription_service.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="指定されたジョブが見つかりません"
        )
    
    # 要約取得
    summary_service = SummaryService(db)
    summary = summary_service.get_complete_summary(job_id)
    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="要約が見つかりません"
        )
    
    # ファイル名生成
    safe_filename = job.original_filename.replace(" ", "_").replace("/", "_")
    filename = f"summary_{safe_filename.split('.')[0]}.txt"
    
    # テキストコンテンツ生成
    content_lines = [
        f"{job.usage_type_code.upper()}要約結果",
        f"ファイル名: {job.original_filename}",
        f"処理日時: {summary['created_at'].split('T')[0]}",
        f"使用モデル: {summary['model_used']}",
        f"信頼度: {summary['confidence']:.2f}",
        "",
        "--- 要約内容 ---",
        summary["formatted_text"],
        ""
    ]
    
    # タイプ別詳細追加
    if summary["type"] == "meeting" and summary["details"]:
        details = summary["details"]
        content_lines.extend([
            "--- 会議詳細 ---",
            f"概要: {details.get('summary', '')}",
            "",
            "決定事項:",
        ])
        for decision in details.get('decisions', []):
            content_lines.append(f"• {decision}")
        
        content_lines.extend([
            "",
            "アクションプラン:",
        ])
        for action in details.get('action_plans', []):
            content_lines.append(f"• {action}")
        
        if details.get('next_meeting'):
            content_lines.extend([
                "",
                f"次回会議: {details['next_meeting']}"
            ])
    
    elif summary["type"] == "interview" and summary["details"]:
        details = summary["details"]
        content_lines.extend([
            "--- 面接詳細 ---",
            f"応募職種: {details.get('position_applied', '未指定')}",
            "",
            f"経験・スキル:\n{details.get('experience', '')}",
            "",
            f"キャリアの軸:\n{details.get('career_axis', '')}",
            "",
            f"職務経験:\n{details.get('work_experience', '')}",
            "",
            f"人物分析:\n{details.get('character_analysis', '')}",
            "",
            f"次のステップ:\n{details.get('next_steps', '')}"
        ])
    
    content = "\n".join(content_lines)
    
    # ダウンロードログ記録
    logger.info("Summary text downloaded", 
               job_id=job_id,
               filename=filename)
    
    return Response(
        content=content,
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}"
        }
    )


@router.get("/{job_id}/summary/json")
async def download_summary_json(
    job_id: str,
    db: Session = Depends(get_db)
):
    """要約結果JSONファイルダウンロード"""
    
    # ジョブ存在確認
    transcription_service = TranscriptionService(db)
    job = transcription_service.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="指定されたジョブが見つかりません"
        )
    
    # 要約取得
    summary_service = SummaryService(db)
    summary = summary_service.export_summary_data(job_id)
    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="要約が見つかりません"
        )
    
    # ファイル名生成
    safe_filename = job.original_filename.replace(" ", "_").replace("/", "_")
    filename = f"summary_{safe_filename.split('.')[0]}.json"
    
    # ダウンロードログ記録
    logger.info("Summary JSON downloaded", 
               job_id=job_id,
               filename=filename)
    
    import json
    return Response(
        content=json.dumps(summary, ensure_ascii=False, indent=2),
        media_type="application/json; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}"
        }
    )


@router.get("/{job_id}/export")
async def export_job_data(
    job_id: str,
    format: str = "json",
    db: Session = Depends(get_db)
):
    """ジョブデータ完全エクスポート"""
    
    if format not in ["json", "txt"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="サポートされていない形式です（json, txt）"
        )
    
    # ジョブ存在確認
    transcription_service = TranscriptionService(db)
    job = transcription_service.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="指定されたジョブが見つかりません"
        )
    
    # データ収集
    export_data = {
        "job": {
            "id": job.id,
            "original_filename": job.original_filename,
            "usage_type": job.usage_type_code,
            "status": job.status_code,
            "created_at": job.created_at.isoformat(),
            "file_size": job.file_size
        }
    }
    
    # 転写結果追加
    transcription_result = transcription_service.get_transcription_result(job_id)
    if transcription_result:
        segments = transcription_service.get_transcription_segments(job_id)
        export_data["transcription"] = {
            "text": transcription_result.text,
            "confidence": transcription_result.confidence,
            "language": transcription_result.language,
            "duration_seconds": transcription_result.duration_seconds,
            "model_used": transcription_result.model_used,
            "segments": [
                {
                    "start_time": seg.start_time,
                    "end_time": seg.end_time,
                    "text": seg.text,
                    "confidence": seg.confidence
                }
                for seg in segments
            ]
        }
    
    # 要約結果追加
    summary_service = SummaryService(db)
    summary = summary_service.get_complete_summary(job_id)
    if summary:
        export_data["summary"] = summary
    
    # ファイル名生成
    safe_filename = job.original_filename.replace(" ", "_").replace("/", "_")
    filename = f"export_{safe_filename.split('.')[0]}.{format}"
    
    # ダウンロードログ記録
    logger.info("Job data exported", 
               job_id=job_id,
               format=format,
               filename=filename)
    
    if format == "json":
        import json
        return Response(
            content=json.dumps(export_data, ensure_ascii=False, indent=2),
            media_type="application/json; charset=utf-8",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{filename}"
            }
        )
    
    else:  # txt
        # テキスト形式でエクスポート
        lines = [
            "M4A転写システム データエクスポート",
            "=" * 40,
            f"ファイル名: {export_data['job']['original_filename']}",
            f"処理日時: {export_data['job']['created_at']}",
            f"使用用途: {export_data['job']['usage_type']}",
            f"ステータス: {export_data['job']['status']}",
            ""
        ]
        
        if "transcription" in export_data:
            lines.extend([
                "転写結果",
                "-" * 20,
                export_data["transcription"]["text"],
                ""
            ])
        
        if "summary" in export_data:
            lines.extend([
                "AI要約",
                "-" * 20,
                export_data["summary"]["formatted_text"],
                ""
            ])
        
        content = "\n".join(lines)
        
        return Response(
            content=content,
            media_type="text/plain; charset=utf-8",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{filename}"
            }
        )