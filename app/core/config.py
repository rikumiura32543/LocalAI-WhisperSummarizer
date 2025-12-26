"""
アプリケーション設定管理
"""

import os
from typing import List, Optional
try:
    from pydantic import BaseSettings, validator
except ImportError:
    from pydantic_settings import BaseSettings
    from pydantic import validator
from pathlib import Path


class Settings(BaseSettings):
    """アプリケーション設定クラス"""
    
    # 基本設定
    APP_NAME: str = "LocalAI-WhisperSummarizer"
    APP_VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # 環境設定
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # サーバー設定
    HOST: str = "0.0.0.0"
    PORT: int = 8100
    WORKERS: int = 2
    
    # セキュリティ設定
    SECRET_KEY: str = "your-secret-key-change-this-in-production"
    JWT_SECRET_KEY: str = "your-jwt-secret-key"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # データベース設定
    DATABASE_URL: str = "sqlite:///./data/m4a_transcribe.db"
    DATABASE_ECHO: bool = False
    
    # CORS設定
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8080"]
    CORS_CREDENTIALS: bool = True
    CORS_METHODS: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    CORS_HEADERS: List[str] = ["*"]
    
    # ファイル処理設定
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: List[str] = ["m4a", "mp4", "wav", "mp3"]
    AUTO_CLEANUP_HOURS: int = 24
    
    # AI処理設定
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2:7b"  # 利用可能なモデルに変更
    OLLAMA_TIMEOUT: int = 300
    WHISPER_MODEL: str = "base"
    WHISPER_DEVICE: str = "cpu"
    
    # Redis設定
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: int = 0
    
    # ログ設定
    LOG_LEVEL: str = "DEBUG"
    LOG_FORMAT: str = "json"
    LOG_FILE: Optional[str] = "./logs/app.log"
    LOG_ROTATION: str = "daily"
    LOG_RETENTION_DAYS: int = 30
    
    # 機能フラグ
    ENABLE_METRICS: bool = False
    ENABLE_HEALTH_CHECK: bool = True
    ENABLE_SWAGGER_UI: bool = True
    ENABLE_FILE_VALIDATION: bool = True
    
    # パフォーマンス設定
    PROCESSING_TIMEOUT_SECONDS: int = 900
    SUMMARY_TIMEOUT_SECONDS: int = 300
    MAX_CONCURRENT_JOBS: int = 1
    
    # Google Cloud設定
    GCP_PROJECT_ID: Optional[str] = None
    GCP_REGION: str = "asia-northeast1"
    GCP_STORAGE_BUCKET: Optional[str] = None
    
    # 監視設定
    SENTRY_DSN: Optional[str] = None
    SENTRY_ENVIRONMENT: str = "development"
    
    @validator("CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v):
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        return v
    
    @validator("ALLOWED_EXTENSIONS", pre=True)
    def assemble_allowed_extensions(cls, v):
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, list):
            return v
        return v
    
    @validator("CORS_METHODS", pre=True) 
    def assemble_cors_methods(cls, v):
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, list):
            return v
        return v
    
    @validator("CORS_HEADERS", pre=True)
    def assemble_cors_headers(cls, v):
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, list):
            return v  
        return v
    
    @validator("UPLOAD_DIR")
    def create_upload_dir(cls, v):
        Path(v).mkdir(parents=True, exist_ok=True)
        return v
    
    @validator("ENVIRONMENT")
    def validate_environment(cls, v):
        allowed = ["development", "staging", "production", "test"]
        if v not in allowed:
            raise ValueError(f"Environment must be one of {allowed}")
        return v
    
    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"
    
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"
    
    @property
    def is_test(self) -> bool:
        return self.ENVIRONMENT == "test"
    
    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024
    
    @property
    def database_url_sync(self) -> str:
        """同期データベースURL（非async）"""
        return self.DATABASE_URL
    
    def get_cors_origins_list(self) -> List[str]:
        """CORS許可オリジンリスト取得"""
        if self.is_development:
            return ["*"]  # 開発環境では全許可
        return self.CORS_ORIGINS
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # 不明な環境変数を無視  # 不明な環境変数を無視


# グローバル設定インスタンス
settings = Settings()


def get_settings() -> Settings:
    """設定取得（依存注入用）"""
    return settings


# 便利な関数
def is_allowed_file(filename: str) -> bool:
    """許可されたファイル形式かチェック"""
    if not filename:
        return False
    
    extension = filename.lower().split('.')[-1] if '.' in filename else ''
    return extension in [ext.lower() for ext in settings.ALLOWED_EXTENSIONS]


def get_upload_path(filename: str) -> Path:
    """アップロードファイルパス取得"""
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir / filename


def get_logs_path() -> Path:
    """ログディレクトリパス取得"""
    if settings.LOG_FILE:
        log_path = Path(settings.LOG_FILE)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        return log_path.parent
    return Path("./logs")


def format_file_size(size_bytes: int) -> str:
    """ファイルサイズを読みやすい形式で表示"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"