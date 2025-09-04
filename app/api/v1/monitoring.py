"""
モニタリング・ダッシュボードAPI
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, text

from app.core.database import get_db
from app.services.monitoring_service import monitoring_service
from app.services.cache_service import cache_service
from app.core.enhanced_logging import get_logger
from app.models.transcription import TranscriptionJob
from app.models.master import JobStatus, UsageType
from app.services.performance_analyzer import performance_profiler, resource_analyzer
from app.services.error_tracking import error_tracker
from app.services.log_management import log_manager

logger = get_logger("monitoring_api")
router = APIRouter()


@router.get("/system-status")
async def get_system_status():
    """システム状態取得"""
    try:
        status = monitoring_service.get_system_status()
        
        # キャッシュ統計追加
        cache_stats = cache_service.get_stats()
        status["cache"] = cache_stats
        
        logger.info("System status requested", **status)
        return {
            "status": "success",
            "data": status,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error("Failed to get system status", error=str(e))
        raise HTTPException(status_code=500, detail="システム状態取得に失敗しました")


@router.get("/health")
async def get_health_check():
    """詳細ヘルスチェック"""
    try:
        health_results = await monitoring_service.health_checker.run_all_checks()
        
        logger.info("Health check performed", 
                   status=health_results["overall_status"],
                   checks=len(health_results["checks"]))
        
        return {
            "status": "success",
            "data": health_results
        }
        
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        raise HTTPException(status_code=500, detail="ヘルスチェックに失敗しました")


@router.get("/metrics")
async def get_metrics(
    metric_name: Optional[str] = Query(None, description="特定のメトリクス名"),
    hours: int = Query(1, ge=1, le=24, description="取得する時間範囲（時間）"),
    db: Session = Depends(get_db)
):
    """メトリクス取得"""
    try:
        since = datetime.now() - timedelta(hours=hours)
        
        if metric_name:
            metrics = monitoring_service.metrics_collector.get_metrics(metric_name, since=since)
            summary = monitoring_service.metrics_collector.get_metric_summary(metric_name, since=since)
        else:
            # すべてのメトリクス概要を取得
            system_metrics = [
                "system_cpu_percent",
                "system_memory_percent", 
                "system_disk_percent",
                "process_memory_percent",
                "process_cpu_percent",
                "network_connections"
            ]
            
            metrics = {}
            summary = {}
            
            for metric in system_metrics:
                metrics[metric] = monitoring_service.metrics_collector.get_metrics(metric, since=since)
                summary[metric] = monitoring_service.metrics_collector.get_metric_summary(metric, since=since)
        
        return {
            "status": "success",
            "data": {
                "metrics": metrics,
                "summary": summary,
                "time_range": {
                    "from": since.isoformat(),
                    "to": datetime.now().isoformat(),
                    "hours": hours
                }
            }
        }
        
    except Exception as e:
        logger.error("Failed to get metrics", error=str(e), metric_name=metric_name)
        raise HTTPException(status_code=500, detail="メトリクス取得に失敗しました")


@router.get("/performance")
async def get_performance_stats():
    """パフォーマンス統計取得"""
    try:
        performance_summary = monitoring_service.performance_tracker.get_performance_summary()
        
        logger.info("Performance stats requested")
        return {
            "status": "success",
            "data": performance_summary
        }
        
    except Exception as e:
        logger.error("Failed to get performance stats", error=str(e))
        raise HTTPException(status_code=500, detail="パフォーマンス統計取得に失敗しました")


@router.get("/database-stats")
async def get_database_stats(db: Session = Depends(get_db)):
    """データベース統計取得"""
    try:
        # ジョブ統計
        job_stats = db.query(
            JobStatus.code,
            func.count(TranscriptionJob.id).label('count')
        ).join(
            TranscriptionJob, TranscriptionJob.status_code == JobStatus.code
        ).group_by(JobStatus.code).all()
        
        # 使用タイプ別統計
        usage_stats = db.query(
            UsageType.code,
            func.count(TranscriptionJob.id).label('count')
        ).join(
            TranscriptionJob, TranscriptionJob.usage_type_code == UsageType.code
        ).group_by(UsageType.code).all()
        
        # 時間別統計（過去24時間）
        time_stats = db.query(
            func.date_trunc('hour', TranscriptionJob.created_at).label('hour'),
            func.count(TranscriptionJob.id).label('count')
        ).filter(
            TranscriptionJob.created_at >= datetime.now() - timedelta(hours=24)
        ).group_by('hour').order_by('hour').all()
        
        # ファイルサイズ統計
        size_stats = db.query(
            func.avg(TranscriptionJob.file_size).label('avg_size'),
            func.min(TranscriptionJob.file_size).label('min_size'),
            func.max(TranscriptionJob.file_size).label('max_size'),
            func.sum(TranscriptionJob.file_size).label('total_size')
        ).first()
        
        # 処理時間統計
        duration_stats = db.query(
            func.avg(
                func.extract('epoch', TranscriptionJob.processing_completed_at - TranscriptionJob.processing_started_at)
            ).label('avg_duration_seconds'),
            func.min(
                func.extract('epoch', TranscriptionJob.processing_completed_at - TranscriptionJob.processing_started_at)
            ).label('min_duration_seconds'),
            func.max(
                func.extract('epoch', TranscriptionJob.processing_completed_at - TranscriptionJob.processing_started_at)
            ).label('max_duration_seconds')
        ).filter(
            TranscriptionJob.processing_completed_at.isnot(None),
            TranscriptionJob.processing_started_at.isnot(None)
        ).first()
        
        result = {
            "job_status_distribution": [{"status": row.code, "count": row.count} for row in job_stats],
            "usage_type_distribution": [{"usage_type": row.code, "count": row.count} for row in usage_stats],
            "hourly_activity": [{"hour": row.hour.isoformat(), "count": row.count} for row in time_stats],
            "file_size_stats": {
                "average_bytes": float(size_stats.avg_size) if size_stats.avg_size else 0,
                "minimum_bytes": size_stats.min_size or 0,
                "maximum_bytes": size_stats.max_size or 0,
                "total_bytes": size_stats.total_size or 0
            },
            "processing_duration_stats": {
                "average_seconds": float(duration_stats.avg_duration_seconds) if duration_stats.avg_duration_seconds else 0,
                "minimum_seconds": float(duration_stats.min_duration_seconds) if duration_stats.min_duration_seconds else 0,
                "maximum_seconds": float(duration_stats.max_duration_seconds) if duration_stats.max_duration_seconds else 0
            }
        }
        
        logger.info("Database stats requested")
        return {
            "status": "success", 
            "data": result
        }
        
    except Exception as e:
        logger.error("Failed to get database stats", error=str(e))
        raise HTTPException(status_code=500, detail="データベース統計取得に失敗しました")


@router.get("/alerts")
async def get_active_alerts():
    """アクティブアラート取得"""
    try:
        active_alerts = []
        
        for alert_name, alert_info in monitoring_service.alert_manager.active_alerts.items():
            active_alerts.append({
                "name": alert_name,
                "rule": alert_info["rule"],
                "started_at": alert_info["started_at"].isoformat(),
                "latest_value": alert_info["latest_value"],
                "duration_minutes": (datetime.now() - alert_info["started_at"]).total_seconds() / 60
            })
        
        logger.info("Active alerts requested", alert_count=len(active_alerts))
        return {
            "status": "success",
            "data": {
                "alerts": active_alerts,
                "count": len(active_alerts)
            }
        }
        
    except Exception as e:
        logger.error("Failed to get active alerts", error=str(e))
        raise HTTPException(status_code=500, detail="アラート取得に失敗しました")


@router.post("/alerts/check")
async def trigger_alert_check():
    """アラートチェック手動実行"""
    try:
        await monitoring_service.alert_manager.check_alerts()
        
        logger.info("Manual alert check triggered")
        return {
            "status": "success",
            "message": "アラートチェックを実行しました"
        }
        
    except Exception as e:
        logger.error("Manual alert check failed", error=str(e))
        raise HTTPException(status_code=500, detail="アラートチェックに失敗しました")


@router.get("/dashboard-data")
async def get_dashboard_data(db: Session = Depends(get_db)):
    """ダッシュボード用統合データ"""
    try:
        # 各種データを並行取得
        system_status = monitoring_service.get_system_status()
        performance_stats = monitoring_service.performance_tracker.get_performance_summary()
        
        # データベース概要統計
        total_jobs = db.query(func.count(TranscriptionJob.id)).scalar()
        completed_jobs = db.query(func.count(TranscriptionJob.id)).filter(
            TranscriptionJob.status_code == 'completed'
        ).scalar()
        
        # 過去24時間の活動
        recent_jobs = db.query(func.count(TranscriptionJob.id)).filter(
            TranscriptionJob.created_at >= datetime.now() - timedelta(hours=24)
        ).scalar()
        
        # エラー率計算
        error_jobs = db.query(func.count(TranscriptionJob.id)).filter(
            TranscriptionJob.status_code == 'error',
            TranscriptionJob.created_at >= datetime.now() - timedelta(hours=24)
        ).scalar()
        
        error_rate = (error_jobs / recent_jobs * 100) if recent_jobs > 0 else 0
        
        # アクティブアラート数
        active_alert_count = len(monitoring_service.alert_manager.active_alerts)
        
        # キャッシュ統計
        cache_stats = cache_service.get_stats()
        
        dashboard_data = {
            "overview": {
                "total_jobs": total_jobs,
                "completed_jobs": completed_jobs,
                "completion_rate": (completed_jobs / total_jobs * 100) if total_jobs > 0 else 0,
                "recent_jobs_24h": recent_jobs,
                "error_rate_24h": error_rate,
                "active_alerts": active_alert_count
            },
            "system": {
                "cpu_percent": system_status.get("cpu_percent", 0),
                "memory_percent": system_status.get("memory_percent", 0),
                "uptime_hours": system_status.get("uptime", 0) / 3600
            },
            "performance": performance_stats,
            "cache": cache_stats,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info("Dashboard data requested")
        return {
            "status": "success",
            "data": dashboard_data
        }
        
    except Exception as e:
        logger.error("Failed to get dashboard data", error=str(e))
        raise HTTPException(status_code=500, detail="ダッシュボードデータ取得に失敗しました")


@router.get("/export/metrics")
async def export_metrics(
    format: str = Query("json", regex="^(json|csv)$"),
    hours: int = Query(24, ge=1, le=168)  # 最大1週間
):
    """メトリクスエクスポート"""
    try:
        since = datetime.now() - timedelta(hours=hours)
        
        # すべてのシステムメトリクス取得
        system_metrics = [
            "system_cpu_percent",
            "system_memory_percent", 
            "system_disk_percent",
            "process_memory_percent",
            "process_cpu_percent",
            "network_connections"
        ]
        
        export_data = []
        
        for metric_name in system_metrics:
            metrics = monitoring_service.metrics_collector.get_metrics(metric_name, since=since)
            
            for metric in metrics:
                export_data.append({
                    "timestamp": datetime.fromtimestamp(metric.timestamp).isoformat(),
                    "metric_name": metric.name,
                    "value": metric.value,
                    "labels": metric.labels
                })
        
        if format == "csv":
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=["timestamp", "metric_name", "value", "labels"])
            writer.writeheader()
            
            for row in export_data:
                row["labels"] = str(row["labels"])  # CSVではJSON文字列として出力
                writer.writerow(row)
            
            csv_content = output.getvalue()
            output.close()
            
            from fastapi.responses import Response
            return Response(
                content=csv_content,
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=metrics_{hours}h.csv"}
            )
        
        logger.info("Metrics exported", format=format, hours=hours, records=len(export_data))
        return {
            "status": "success",
            "data": export_data,
            "metadata": {
                "format": format,
                "time_range_hours": hours,
                "record_count": len(export_data),
                "exported_at": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error("Failed to export metrics", error=str(e), format=format)
        raise HTTPException(status_code=500, detail="メトリクスエクスポートに失敗しました")


@router.get("/performance")
async def get_performance_analysis(hours: int = Query(1, ge=1, le=24)):
    """パフォーマンス分析取得"""
    try:
        endpoint_performance = performance_profiler.get_endpoint_performance(hours)
        slowest_requests = performance_profiler.get_slowest_requests(limit=20)
        performance_anomalies = performance_profiler.detect_performance_anomalies()
        resource_trends = resource_analyzer.analyze_resource_trends()
        
        logger.info("Performance analysis requested", hours=hours)
        return {
            "status": "success",
            "data": {
                "endpoint_performance": endpoint_performance,
                "slowest_requests": slowest_requests,
                "anomalies": performance_anomalies,
                "resource_trends": resource_trends,
                "analysis_period_hours": hours
            }
        }
        
    except Exception as e:
        logger.error("Failed to get performance analysis", error=str(e))
        raise HTTPException(status_code=500, detail="パフォーマンス分析取得に失敗しました")


@router.get("/errors")
async def get_error_statistics(hours: int = Query(24, ge=1, le=168)):
    """エラー統計取得"""
    try:
        error_stats = error_tracker.get_error_statistics(hours)
        top_errors = error_tracker.get_top_errors(limit=20)
        
        logger.info("Error statistics requested", hours=hours)
        return {
            "status": "success",
            "data": {
                "statistics": error_stats,
                "top_errors": top_errors,
                "analysis_period_hours": hours
            }
        }
        
    except Exception as e:
        logger.error("Failed to get error statistics", error=str(e))
        raise HTTPException(status_code=500, detail="エラー統計取得に失敗しました")


@router.get("/errors/{error_hash}")
async def get_error_details(error_hash: str):
    """エラー詳細取得"""
    try:
        error_details = error_tracker.get_error_details(error_hash)
        
        if not error_details:
            raise HTTPException(status_code=404, detail="エラーパターンが見つかりません")
        
        logger.info("Error details requested", error_hash=error_hash)
        return {
            "status": "success",
            "data": error_details
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get error details", error=str(e), error_hash=error_hash)
        raise HTTPException(status_code=500, detail="エラー詳細取得に失敗しました")


@router.post("/logs/search")
async def search_logs(
    query: str = Query(..., description="検索クエリ"),
    log_types: Optional[List[str]] = Query(None, description="ログタイプフィルター"),
    hours: int = Query(24, ge=1, le=168, description="検索範囲（時間）"),
    limit: int = Query(100, ge=1, le=1000, description="結果件数制限")
):
    """ログ検索"""
    try:
        start_time = datetime.now() - timedelta(hours=hours)
        
        search_results = await log_manager.search_logs(
            query=query,
            log_types=log_types,
            start_time=start_time,
            limit=limit
        )
        
        logger.audit(
            "Log search performed",
            query=query,
            log_types=log_types,
            results_count=len(search_results)
        )
        
        return {
            "status": "success",
            "data": {
                "results": search_results,
                "query": query,
                "log_types": log_types,
                "time_range_hours": hours,
                "result_count": len(search_results)
            }
        }
        
    except Exception as e:
        logger.error("Log search failed", error=str(e), query=query)
        raise HTTPException(status_code=500, detail="ログ検索に失敗しました")


@router.post("/logs/rotate")
async def manual_log_rotation():
    """手動ログローテーション"""
    try:
        rotation_stats = log_manager.manual_rotation()
        
        logger.audit("Manual log rotation executed", **rotation_stats)
        return {
            "status": "success",
            "data": rotation_stats,
            "message": "ログローテーションが完了しました"
        }
        
    except Exception as e:
        logger.error("Manual log rotation failed", error=str(e))
        raise HTTPException(status_code=500, detail="ログローテーションに失敗しました")


@router.get("/logs/stats")
async def get_log_statistics():
    """ログ統計取得"""
    try:
        log_stats = log_manager.get_log_statistics()
        
        logger.info("Log statistics requested")
        return {
            "status": "success",
            "data": log_stats
        }
        
    except Exception as e:
        logger.error("Failed to get log statistics", error=str(e))
        raise HTTPException(status_code=500, detail="ログ統計取得に失敗しました")