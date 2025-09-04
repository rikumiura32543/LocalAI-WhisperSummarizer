"""API v1パッケージ"""

from fastapi import APIRouter

from app.api.v1 import transcriptions, status, files, health, monitoring, backup

# メインAPIルーター
api_router = APIRouter()

# サブルーター追加
api_router.include_router(
    status.router,
    prefix="/status",
    tags=["status"]
)

api_router.include_router(
    transcriptions.router,
    prefix="/transcriptions",
    tags=["transcriptions"]
)

api_router.include_router(
    files.router,
    prefix="/files",
    tags=["files"]
)

api_router.include_router(
    health.router,
    prefix="/health",
    tags=["health"]
)

api_router.include_router(
    monitoring.router,
    prefix="/monitoring",
    tags=["monitoring"]
)

api_router.include_router(
    backup.router,
    prefix="/backup",
    tags=["backup"]
)