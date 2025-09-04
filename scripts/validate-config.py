#!/usr/bin/env python3
"""
M4A転写システム設定検証スクリプト
本番環境デプロイ前の設定確認
"""

import os
import sys
import json
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional
import structlog

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.environment import ConfigManager, SecretManager

# ログ設定
logging_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {
            "format": "%(levelname)s: %(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
            "level": "INFO"
        }
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO"
    }
}

logger = structlog.get_logger(__name__)

class ConfigValidator:
    """設定検証クラス"""
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.secret_manager = SecretManager()
        self.issues: List[str] = []
        self.warnings: List[str] = []
        
    def validate_all(self) -> Dict[str, Any]:
        """全ての設定を検証"""
        print("🔍 M4A転写システム設定検証開始")
        print("=" * 50)
        
        # 基本設定検証
        self._validate_basic_config()
        
        # 環境別設定検証
        self._validate_environment_config()
        
        # セキュリティ設定検証
        self._validate_security_config()
        
        # ファイルシステム設定検証
        self._validate_filesystem_config()
        
        # 外部サービス設定検証
        self._validate_external_services()
        
        # 本番環境固有の検証
        if self.config_manager.is_production():
            self._validate_production_config()
        
        # 結果表示
        self._display_results()
        
        return {
            "valid": len(self.issues) == 0,
            "issues": self.issues,
            "warnings": self.warnings,
            "environment": self.config_manager.current_env.value,
            "config": self.config_manager.export_config(include_sensitive=False)
        }
    
    def _validate_basic_config(self):
        """基本設定検証"""
        print("📋 基本設定検証中...")
        
        config = self.config_manager.get_config()
        
        # 必須設定項目チェック
        if not config.name:
            self.issues.append("アプリケーション名が設定されていません")
        
        # ワーカー数設定
        if config.workers < 1:
            self.issues.append("ワーカー数は1以上である必要があります")
        elif config.workers > 4:
            self.warnings.append("ワーカー数が多すぎます（Google Cloud E2の制約を考慮）")
        
        # ファイルサイズ制限
        if config.max_file_size_mb > 100:
            self.warnings.append("最大ファイルサイズが大きすぎます（メモリ制限を考慮）")
        
        print(f"  ✓ 環境: {config.name}")
        print(f"  ✓ ワーカー数: {config.workers}")
        print(f"  ✓ 最大ファイルサイズ: {config.max_file_size_mb}MB")
    
    def _validate_environment_config(self):
        """環境別設定検証"""
        print("🌍 環境別設定検証中...")
        
        env = self.config_manager.current_env.value
        config = self.config_manager.get_config()
        
        print(f"  ✓ 現在の環境: {env}")
        print(f"  ✓ デバッグモード: {config.debug}")
        print(f"  ✓ ログレベル: {config.log_level}")
        
        # 環境固有の検証を実行
        config_issues = self.config_manager.validate_config()
        self.issues.extend(config_issues)
        
        if config_issues:
            print(f"  ⚠️ 設定問題が検出されました: {len(config_issues)}件")
    
    def _validate_security_config(self):
        """セキュリティ設定検証"""
        print("🔒 セキュリティ設定検証中...")
        
        config = self.config_manager.get_config()
        
        # CORS設定チェック
        if "*" in config.cors_origins and self.config_manager.is_production():
            self.issues.append("本番環境でCORS設定にワイルドカードは使用できません")
        
        # データベースURL検証
        if "sqlite:///:memory:" in config.database_url and self.config_manager.is_production():
            self.issues.append("本番環境でインメモリデータベースは使用できません")
        
        print(f"  ✓ CORS設定: {len(config.cors_origins)}個のオリジン")
        print(f"  ✓ データベース: {config.database_url.split('://')[0]}://...")
    
    def _validate_filesystem_config(self):
        """ファイルシステム設定検証"""
        print("📁 ファイルシステム検証中...")
        
        # 必要なディレクトリ
        required_dirs = ["data", "uploads", "logs", "backups"]
        
        for dir_name in required_dirs:
            dir_path = Path(dir_name)
            
            # ディレクトリ作成試行
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
                
                # 書き込み権限確認
                if not os.access(dir_path, os.W_OK):
                    self.issues.append(f"ディレクトリ '{dir_name}' に書き込み権限がありません")
                else:
                    print(f"  ✓ ディレクトリ: {dir_name}")
                    
            except PermissionError:
                self.issues.append(f"ディレクトリ '{dir_name}' の作成権限がありません")
    
    def _validate_external_services(self):
        """外部サービス設定検証"""
        print("🔌 外部サービス接続検証中...")
        
        # この部分は実際の接続テストを含めることができます
        # 現在は設定の存在確認のみ
        
        # 環境変数確認
        ollama_url = os.getenv("OLLAMA_BASE_URL")
        if ollama_url:
            print(f"  ✓ Ollama URL: {ollama_url}")
        else:
            self.warnings.append("OLLAMA_BASE_URL環境変数が設定されていません")
        
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            print(f"  ✓ Redis URL: {redis_url}")
        else:
            self.warnings.append("Redis設定が見つかりません（キャッシュ機能は無効）")
    
    def _validate_production_config(self):
        """本番環境固有の設定検証"""
        print("🚀 本番環境設定検証中...")
        
        config = self.config_manager.get_config()
        
        # デバッグモード確認
        if config.debug:
            self.issues.append("本番環境でデバッグモードが有効になっています")
        
        # 必須環境変数確認
        required_prod_vars = [
            "SECRET_KEY",
            "DATABASE_URL",
            "GOOGLE_CLOUD_PROJECT",
        ]
        
        for var in required_prod_vars:
            if not os.getenv(var):
                self.issues.append(f"本番環境で必須の環境変数 '{var}' が設定されていません")
        
        # バックアップ設定確認
        if not config.backup_enabled:
            self.warnings.append("バックアップが無効になっています")
        
        # 監視設定確認
        if not config.enable_monitoring:
            self.warnings.append("監視機能が無効になっています")
        
        print(f"  ✓ バックアップ: {'有効' if config.backup_enabled else '無効'}")
        print(f"  ✓ 監視: {'有効' if config.enable_monitoring else '無効'}")
    
    def _display_results(self):
        """検証結果表示"""
        print("\n" + "=" * 50)
        print("📊 検証結果")
        print("=" * 50)
        
        if not self.issues and not self.warnings:
            print("✅ すべての設定が正常です！")
            return
        
        if self.issues:
            print(f"❌ エラー: {len(self.issues)}件")
            for i, issue in enumerate(self.issues, 1):
                print(f"  {i}. {issue}")
            print()
        
        if self.warnings:
            print(f"⚠️ 警告: {len(self.warnings)}件")
            for i, warning in enumerate(self.warnings, 1):
                print(f"  {i}. {warning}")
            print()
        
        # 結果サマリー
        if self.issues:
            print("❌ 設定に問題があります。デプロイ前に修正してください。")
            sys.exit(1)
        else:
            print("✅ 警告はありますが、デプロイ可能です。")

async def main():
    """メイン実行関数"""
    validator = ConfigValidator()
    result = validator.validate_all()
    
    # JSON出力オプション
    if "--json" in sys.argv:
        print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(main())