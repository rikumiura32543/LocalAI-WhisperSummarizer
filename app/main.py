"""
M4A転写システム - FastAPIメインアプリケーション
"""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import structlog
from pathlib import Path

from app.core.config import settings
from app.core.database import initialize_database, cleanup_database, get_database_stats
from app.core.logging import setup_logging
from app.core.middleware import (
    RequestLoggingMiddleware, SecurityHeadersMiddleware, 
    CacheControlMiddleware, FileSizeValidationMiddleware,
    AdvancedRateLimitMiddleware, RequestSizeMiddleware, SecurityEventMiddleware
)
from app.services.monitoring_service import monitoring_service
from app.services.log_management import log_manager
from app.services.health_service import get_health_service
from app.services.auto_recovery_service import get_auto_recovery_service
from app.services.production_monitoring import get_production_monitoring
from app.services.backup_service import get_backup_service
from app.api.v1 import api_router

# ロガー設定
setup_logging()
logger = structlog.get_logger(__name__)


def create_application() -> FastAPI:
    """FastAPIアプリケーション作成"""
    
    # FastAPIアプリケーション初期化
    app = FastAPI(
        title=settings.APP_NAME,
        description="M4A音声ファイルからテキスト転写とAI要約を生成するシステム",
        version=settings.APP_VERSION,
        docs_url="/api/docs" if settings.is_development else None,
        redoc_url="/api/redoc" if settings.is_development else None,
        openapi_url="/api/openapi.json" if settings.ENABLE_SWAGGER_UI else None,
    )
    
    # CORS設定
    if settings.CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.get_cors_origins_list(),
            allow_credentials=settings.CORS_CREDENTIALS,
            allow_methods=settings.CORS_METHODS,
            allow_headers=settings.CORS_HEADERS,
        )
    
    # ミドルウェア追加（逆順で追加 - 最初に追加されたものが最後に実行される）
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(CacheControlMiddleware)
    app.add_middleware(FileSizeValidationMiddleware, max_size_bytes=settings.max_file_size_bytes)
    app.add_middleware(RequestSizeMiddleware, max_request_size=settings.max_file_size_bytes)
    app.add_middleware(SecurityEventMiddleware)
    app.add_middleware(AdvancedRateLimitMiddleware, 
                      requests_per_minute=60, 
                      requests_per_hour=1000,
                      uploads_per_hour=100)
    
    # 静的ファイル配信
    static_path = Path(__file__).parent.parent / "static"
    if static_path.exists():
        app.mount("/static", StaticFiles(directory=str(static_path)), name="static")
    
    # APIルーター追加
    app.include_router(api_router, prefix=settings.API_V1_STR)
    
    # エラーハンドラー設定
    setup_exception_handlers(app)
    
    # イベントハンドラー設定
    setup_event_handlers(app)
    
    return app


def setup_exception_handlers(app: FastAPI):
    """例外ハンドラー設定"""
    
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """HTTPエラーハンドラー"""
        logger.error("HTTP exception", 
                    status_code=exc.status_code,
                    detail=exc.detail,
                    url=str(request.url))
        
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": True,
                "status_code": exc.status_code,
                "message": exc.detail,
                "path": str(request.url.path)
            }
        )
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """バリデーションエラーハンドラー"""
        logger.error("Validation error",
                    errors=exc.errors(),
                    url=str(request.url))
        
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": True,
                "status_code": 422,
                "message": "バリデーションエラー",
                "details": exc.errors(),
                "path": str(request.url.path)
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """一般的な例外ハンドラー"""
        logger.error("Unexpected error",
                    error=str(exc),
                    error_type=type(exc).__name__,
                    url=str(request.url))
        
        if settings.is_development:
            # 開発環境では詳細なエラー情報を返す
            import traceback
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": True,
                    "status_code": 500,
                    "message": "内部サーバーエラー",
                    "detail": str(exc),
                    "traceback": traceback.format_exc(),
                    "path": str(request.url.path)
                }
            )
        else:
            # 本番環境では簡潔なエラー情報のみ
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": True,
                    "status_code": 500,
                    "message": "内部サーバーエラーが発生しました",
                    "path": str(request.url.path)
                }
            )


def setup_event_handlers(app: FastAPI):
    """イベントハンドラー設定"""
    
    @app.on_event("startup")
    async def startup_event():
        """アプリケーション起動時の処理"""
        logger.info("M4A転写システム起動中...",
                   version=settings.APP_VERSION,
                   environment=settings.ENVIRONMENT)
        
        try:
            # データベース初期化
            initialize_database()
            
            # 必要なディレクトリ作成
            Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
            Path("data").mkdir(exist_ok=True)
            Path("logs").mkdir(exist_ok=True)
            
            # モニタリングサービス開始
            await monitoring_service.start()
            
            # ログ管理サービス開始
            await log_manager.start_rotation_scheduler()
            
            # 本番環境専用サービス開始
            if settings.is_production:
                # 本番監視サービス開始
                production_monitoring = get_production_monitoring()
                await production_monitoring.start_production_monitoring()
                
                # 自動復旧サービス開始
                auto_recovery = get_auto_recovery_service()
                await auto_recovery.start_monitoring()
                
                # バックアップスケジューラー開始
                backup_service = get_backup_service()
                await backup_service.start_backup_scheduler()
                
                logger.info("Production services started",
                           services=["production_monitoring", "auto_recovery", "backup_scheduler"])
            
            logger.info("M4A転写システムが正常に起動しました",
                       version=settings.APP_VERSION,
                       database_url=settings.DATABASE_URL,
                       upload_dir=settings.UPLOAD_DIR)
            
        except Exception as e:
            logger.error("起動時エラー", error=str(e))
            raise
    
    @app.on_event("shutdown")
    async def shutdown_event():
        """アプリケーション終了時の処理"""
        logger.info("M4A転写システム終了中...")
        
        try:
            # モニタリングサービス停止
            await monitoring_service.stop()
            
            # ログ管理サービス停止
            await log_manager.stop_rotation_scheduler()
            
            # 本番環境サービス停止
            if settings.is_production:
                try:
                    production_monitoring = get_production_monitoring()
                    await production_monitoring.stop_production_monitoring()
                    
                    auto_recovery = get_auto_recovery_service()
                    await auto_recovery.stop_monitoring()
                    
                    backup_service = get_backup_service()
                    await backup_service.stop_backup_scheduler()
                    
                    logger.info("Production services stopped")
                except Exception as e:
                    logger.error("Error stopping production services", error=str(e))
            
            cleanup_database()
            logger.info("M4A転写システムが正常に終了しました")
        except Exception as e:
            logger.error("終了時エラー", error=str(e))


# FastAPIアプリケーション作成
app = create_application()


# ルートエンドポイント
@app.get("/", response_class=HTMLResponse)
async def root():
    """ルートエンドポイント - HTMLページを返す"""
    static_path = Path(__file__).parent.parent / "static" / "index.html"
    if static_path.exists():
        with open(static_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    
    return HTMLResponse(
        content="""
        <!DOCTYPE html>
        <html>
        <head><title>M4A転写システム</title></head>
        <body>
            <h1>M4A転写システム</h1>
            <p>APIサーバーが稼働中です</p>
            <ul>
                <li><a href="/api/docs">API Documentation</a></li>
                <li><a href="/health">Health Check</a></li>
                <li><a href="/api/v1/status">API Status</a></li>
            </ul>
        </body>
        </html>
        """
    )


@app.get("/health")
async def health_check():
    """ヘルスチェックエンドポイント"""
    try:
        # データベースヘルスチェック
        db_stats = get_database_stats()
        db_healthy = db_stats.get("health_status", False)
        
        status_code = status.HTTP_200_OK if db_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
        
        return JSONResponse(
            status_code=status_code,
            content={
                "status": "healthy" if db_healthy else "unhealthy",
                "version": settings.APP_VERSION,
                "environment": settings.ENVIRONMENT,
                "timestamp": str(Path().cwd()),
                "database": {
                    "status": "connected" if db_healthy else "disconnected",
                    "url": settings.DATABASE_URL
                },
                "services": {
                    "transcription": "ready",
                    "summarization": "ready",
                    "database": "connected" if db_healthy else "error"
                }
            }
        )
    
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "version": settings.APP_VERSION,
                "environment": settings.ENVIRONMENT,
                "error": str(e) if settings.is_development else "Service unavailable"
            }
        )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        log_level=settings.LOG_LEVEL.lower(),
        reload=settings.is_development,
        workers=1 if settings.is_development else settings.WORKERS,
    )