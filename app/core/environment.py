"""
環境別設定管理システム
"""

import os
from enum import Enum
from typing import Dict, Any, Optional, List
from pathlib import Path
import json
import structlog
from dataclasses import dataclass

logger = structlog.get_logger(__name__)


class Environment(Enum):
    """環境種別"""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class EnvironmentConfig:
    """環境設定"""
    name: str
    debug: bool
    log_level: str
    database_url: str
    redis_url: Optional[str]
    cors_origins: List[str]
    max_file_size_mb: int
    workers: int
    enable_monitoring: bool
    backup_enabled: bool
    
    def __post_init__(self):
        """設定値の検証と正規化"""
        # ファイルサイズをバイト単位に変換
        self.max_file_size_bytes = self.max_file_size_mb * 1024 * 1024
        
        # CORS設定の正規化
        if isinstance(self.cors_origins, str):
            self.cors_origins = [self.cors_origins]


class ConfigManager:
    """設定管理システム"""
    
    def __init__(self):
        self.current_env = self._detect_environment()
        self.config = self._load_configuration()
        
        logger.info("Configuration loaded",
                   environment=self.current_env.value,
                   debug=self.config.debug)
    
    def _detect_environment(self) -> Environment:
        """環境自動検出"""
        env_name = os.getenv("ENVIRONMENT", "development").lower()
        
        try:
            return Environment(env_name)
        except ValueError:
            logger.warning("Invalid environment name, defaulting to development",
                          env_name=env_name)
            return Environment.DEVELOPMENT
    
    def _load_configuration(self) -> EnvironmentConfig:
        """環境別設定読み込み"""
        configs = {
            Environment.DEVELOPMENT: self._get_development_config(),
            Environment.TESTING: self._get_testing_config(),
            Environment.STAGING: self._get_staging_config(),
            Environment.PRODUCTION: self._get_production_config(),
        }
        
        base_config = configs[self.current_env]
        
        # 環境変数による上書き
        self._apply_environment_overrides(base_config)
        
        return base_config
    
    def _get_development_config(self) -> EnvironmentConfig:
        """開発環境設定"""
        return EnvironmentConfig(
            name="development",
            debug=True,
            log_level="DEBUG",
            database_url=os.getenv("DATABASE_URL", "sqlite:///data/m4a_transcribe_dev.db"),
            redis_url=os.getenv("REDIS_URL"),
            cors_origins=["http://localhost:3000", "http://localhost:8100"],
            max_file_size_mb=50,
            workers=1,
            enable_monitoring=True,
            backup_enabled=False
        )
    
    def _get_testing_config(self) -> EnvironmentConfig:
        """テスト環境設定"""
        return EnvironmentConfig(
            name="testing",
            debug=True,
            log_level="WARNING",
            database_url=os.getenv("DATABASE_URL", "sqlite:///:memory:"),
            redis_url=None,
            cors_origins=["*"],
            max_file_size_mb=10,
            workers=1,
            enable_monitoring=False,
            backup_enabled=False
        )
    
    def _get_staging_config(self) -> EnvironmentConfig:
        """ステージング環境設定"""
        return EnvironmentConfig(
            name="staging",
            debug=False,
            log_level="INFO",
            database_url=os.getenv("DATABASE_URL", "sqlite:///data/m4a_transcribe_staging.db"),
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/1"),
            cors_origins=["https://staging.m4a-transcribe.example.com"],
            max_file_size_mb=50,
            workers=2,
            enable_monitoring=True,
            backup_enabled=True
        )
    
    def _get_production_config(self) -> EnvironmentConfig:
        """本番環境設定"""
        return EnvironmentConfig(
            name="production",
            debug=False,
            log_level="INFO",
            database_url=os.getenv("DATABASE_URL", "sqlite:///data/m4a_transcribe_production.db"),
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            cors_origins=["https://m4a-transcribe.example.com"],
            max_file_size_mb=50,
            workers=2,
            enable_monitoring=True,
            backup_enabled=True
        )
    
    def _apply_environment_overrides(self, config: EnvironmentConfig):
        """環境変数による設定上書き"""
        overrides = {
            "DEBUG": ("debug", self._str_to_bool),
            "LOG_LEVEL": ("log_level", str),
            "DATABASE_URL": ("database_url", str),
            "REDIS_URL": ("redis_url", str),
            "CORS_ORIGINS": ("cors_origins", self._str_to_list),
            "MAX_FILE_SIZE_MB": ("max_file_size_mb", int),
            "WORKERS": ("workers", int),
            "ENABLE_MONITORING": ("enable_monitoring", self._str_to_bool),
            "BACKUP_ENABLED": ("backup_enabled", self._str_to_bool),
        }
        
        for env_var, (attr_name, converter) in overrides.items():
            value = os.getenv(env_var)
            if value is not None:
                try:
                    converted_value = converter(value)
                    setattr(config, attr_name, converted_value)
                    logger.debug("Configuration override applied",
                               attribute=attr_name,
                               value=converted_value)
                except (ValueError, TypeError) as e:
                    logger.warning("Failed to apply configuration override",
                                 attribute=attr_name,
                                 value=value,
                                 error=str(e))
    
    def _str_to_bool(self, value: str) -> bool:
        """文字列をbooleanに変換"""
        return value.lower() in ("true", "1", "yes", "on", "enabled")
    
    def _str_to_list(self, value: str) -> List[str]:
        """文字列をリストに変換"""
        if not value:
            return []
        return [item.strip() for item in value.split(",") if item.strip()]
    
    def get_config(self) -> EnvironmentConfig:
        """現在の設定を取得"""
        return self.config
    
    def is_development(self) -> bool:
        """開発環境かどうか"""
        return self.current_env == Environment.DEVELOPMENT
    
    def is_testing(self) -> bool:
        """テスト環境かどうか"""
        return self.current_env == Environment.TESTING
    
    def is_staging(self) -> bool:
        """ステージング環境かどうか"""
        return self.current_env == Environment.STAGING
    
    def is_production(self) -> bool:
        """本番環境かどうか"""
        return self.current_env == Environment.PRODUCTION
    
    def export_config(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """設定をエクスポート（デバッグ用）"""
        config_dict = {
            "environment": self.current_env.value,
            "name": self.config.name,
            "debug": self.config.debug,
            "log_level": self.config.log_level,
            "cors_origins": self.config.cors_origins,
            "max_file_size_mb": self.config.max_file_size_mb,
            "workers": self.config.workers,
            "enable_monitoring": self.config.enable_monitoring,
            "backup_enabled": self.config.backup_enabled,
        }
        
        if include_sensitive:
            config_dict.update({
                "database_url": self.config.database_url,
                "redis_url": self.config.redis_url,
            })
        else:
            # センシティブ情報はマスク
            config_dict.update({
                "database_url": "***" if self.config.database_url else None,
                "redis_url": "***" if self.config.redis_url else None,
            })
        
        return config_dict
    
    def validate_config(self) -> List[str]:
        """設定値の妥当性チェック"""
        issues = []
        
        # 本番環境での必須チェック
        if self.is_production():
            if self.config.debug:
                issues.append("本番環境でデバッグモードが有効になっています")
            
            if self.config.database_url.startswith("sqlite:///:memory:"):
                issues.append("本番環境でインメモリデータベースは使用できません")
            
            if "*" in self.config.cors_origins:
                issues.append("本番環境でCORS設定にワイルドカードは推奨されません")
        
        # ワーカー数チェック
        if self.config.workers < 1:
            issues.append("ワーカー数は1以上である必要があります")
        
        if self.config.workers > 8:
            issues.append("ワーカー数が多すぎます（Google Cloud E2の制限）")
        
        # ファイルサイズチェック
        if self.config.max_file_size_mb > 100:
            issues.append("最大ファイルサイズが大きすぎます（メモリ制限を考慮）")
        
        return issues


class SecretManager:
    """シークレット管理"""
    
    def __init__(self):
        self.secrets_path = Path(".secrets")
        self.gcp_project = os.getenv("GOOGLE_CLOUD_PROJECT")
    
    def get_secret(self, secret_name: str, default: Optional[str] = None) -> Optional[str]:
        """シークレット取得"""
        # 1. 環境変数から取得
        env_value = os.getenv(secret_name.upper())
        if env_value:
            return env_value
        
        # 2. ローカルファイルから取得（開発環境）
        if self.secrets_path.exists():
            try:
                with open(self.secrets_path) as f:
                    secrets = json.load(f)
                    return secrets.get(secret_name, default)
            except Exception as e:
                logger.warning("Failed to load local secrets", error=str(e))
        
        # 3. Google Secret Manager（本番環境）
        if self.gcp_project:
            return self._get_gcp_secret(secret_name, default)
        
        return default
    
    def _get_gcp_secret(self, secret_name: str, default: Optional[str] = None) -> Optional[str]:
        """Google Secret Managerからシークレット取得"""
        try:
            from google.cloud import secretmanager
            
            client = secretmanager.SecretManagerServiceClient()
            name = f"projects/{self.gcp_project}/secrets/{secret_name}/versions/latest"
            
            response = client.access_secret_version(request={"name": name})
            return response.payload.data.decode("UTF-8")
            
        except Exception as e:
            logger.warning("Failed to get secret from GCP Secret Manager",
                          secret_name=secret_name,
                          error=str(e))
            return default
    
    def set_secret(self, secret_name: str, secret_value: str):
        """ローカル環境でのシークレット設定（開発用）"""
        if not self.secrets_path.exists():
            self.secrets_path.write_text("{}")
        
        try:
            with open(self.secrets_path) as f:
                secrets = json.load(f)
            
            secrets[secret_name] = secret_value
            
            with open(self.secrets_path, "w") as f:
                json.dump(secrets, f, indent=2)
                
            logger.info("Secret stored locally", secret_name=secret_name)
            
        except Exception as e:
            logger.error("Failed to store secret locally",
                        secret_name=secret_name,
                        error=str(e))


# グローバルインスタンス
config_manager = ConfigManager()
secret_manager = SecretManager()