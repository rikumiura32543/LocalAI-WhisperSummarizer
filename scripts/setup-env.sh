#!/bin/bash
# =============================================
# M4A転写システム 環境設定セットアップスクリプト
# =============================================

set -euo pipefail

# カラー出力の設定
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ログ関数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 使用方法の表示
show_usage() {
    echo "使用方法: $0 [ENVIRONMENT]"
    echo ""
    echo "ENVIRONMENT:"
    echo "  development  開発環境用の設定（デフォルト）"
    echo "  production   本番環境用の設定"
    echo "  test         テスト環境用の設定"
    echo ""
    echo "例:"
    echo "  $0                    # 開発環境用"
    echo "  $0 development        # 開発環境用"
    echo "  $0 production         # 本番環境用"
}

# 環境変数の設定
setup_environment() {
    local env_type="${1:-development}"
    
    log_info "環境設定を開始します: $env_type"
    
    # 必要なディレクトリを作成
    log_info "ディレクトリを作成中..."
    mkdir -p data
    mkdir -p logs
    mkdir -p uploads
    mkdir -p static
    
    # .envファイルの設定
    case "$env_type" in
        "production")
            setup_production_env
            ;;
        "test")
            setup_test_env
            ;;
        "development"|*)
            setup_development_env
            ;;
    esac
    
    # 権限設定
    log_info "権限を設定中..."
    chmod 755 scripts/*.sh || true
    chmod 644 .env || true
    
    log_success "環境設定が完了しました: $env_type"
}

# 開発環境用の設定
setup_development_env() {
    log_info "開発環境用の.envファイルを作成中..."
    
    if [ ! -f .env ]; then
        cp .env.example .env
        log_success ".env.exampleから.envを作成しました"
    else
        log_warning ".envファイルが既に存在します"
        read -p "上書きしますか？ (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            cp .env.example .env
            log_success ".envファイルを更新しました"
        fi
    fi
    
    # 開発環境固有の設定を適用
    sed -i.bak 's/ENV=development/ENV=development/' .env
    sed -i.bak 's/DEBUG=true/DEBUG=true/' .env
    sed -i.bak 's/LOG_LEVEL=DEBUG/LOG_LEVEL=DEBUG/' .env
    
    # バックアップファイルを削除
    rm -f .env.bak
    
    log_info "Ollamaサーバーの起動を確認してください"
    log_info "起動方法: nix develop --command ollama serve"
}

# 本番環境用の設定
setup_production_env() {
    log_info "本番環境用の.envファイルを作成中..."
    
    if [ ! -f .env ]; then
        cp .env.production .env
        log_success ".env.productionから.envを作成しました"
    else
        log_warning ".envファイルが既に存在します"
        read -p "本番環境用設定で上書きしますか？ (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            cp .env.production .env
            log_success ".envファイルを本番環境用に更新しました"
        fi
    fi
    
    # 本番環境用のセキュリティ設定を促す
    log_warning "本番環境では以下の設定を必ず変更してください:"
    echo "  - SECRET_KEY: 強力なランダム文字列"
    echo "  - JWT_SECRET_KEY: JWTトークン用の秘密鍵"
    echo "  - REDIS_PASSWORD: Redisのパスワード"
    echo "  - SENTRY_DSN: エラートラッキング用DSN"
}

# テスト環境用の設定
setup_test_env() {
    log_info "テスト環境用の.envファイルを作成中..."
    
    cp .env.example .env
    
    # テスト環境固有の設定を適用
    sed -i.bak 's/ENV=development/ENV=test/' .env
    sed -i.bak 's/DEBUG=true/DEBUG=false/' .env
    sed -i.bak 's/LOG_LEVEL=DEBUG/LOG_LEVEL=WARNING/' .env
    sed -i.bak 's/DATABASE_URL=sqlite:\/\/\/\.\/data\/m4a_transcribe\.db/DATABASE_URL=sqlite:\/\/\/\.\/test.db/' .env
    
    # バックアップファイルを削除
    rm -f .env.bak
    
    log_success "テスト環境用の設定を適用しました"
}

# シークレットキーの生成
generate_secret_keys() {
    log_info "セキュリティキーを生成中..."
    
    # Python環境が利用可能か確認
    if command -v python3 &> /dev/null; then
        SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
        JWT_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
        
        log_success "生成されたキー:"
        echo "SECRET_KEY=$SECRET_KEY"
        echo "JWT_SECRET_KEY=$JWT_SECRET_KEY"
        echo ""
        log_warning "これらのキーを.envファイルに設定してください"
    else
        log_warning "Python3が見つかりません。手動でキーを生成してください"
    fi
}

# 環境の検証
validate_environment() {
    log_info "環境設定を検証中..."
    
    # 必要なファイルの確認
    local required_files=(".env" "pyproject.toml" "docker-compose.yml")
    local missing_files=()
    
    for file in "${required_files[@]}"; do
        if [ ! -f "$file" ]; then
            missing_files+=("$file")
        fi
    done
    
    if [ ${#missing_files[@]} -ne 0 ]; then
        log_error "以下のファイルが見つかりません:"
        printf ' - %s\n' "${missing_files[@]}"
        return 1
    fi
    
    # 必要なディレクトリの確認
    local required_dirs=("data" "logs" "uploads")
    for dir in "${required_dirs[@]}"; do
        if [ ! -d "$dir" ]; then
            log_error "ディレクトリが見つかりません: $dir"
            return 1
        fi
    done
    
    # .envファイルの内容確認
    if ! grep -q "SECRET_KEY=" .env; then
        log_error ".envファイルにSECRET_KEYが設定されていません"
        return 1
    fi
    
    log_success "環境設定の検証が完了しました"
}

# Docker環境の確認
check_docker() {
    log_info "Docker環境を確認中..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Dockerがインストールされていません"
        return 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Composeがインストールされていません"
        return 1
    fi
    
    # Docker Composeファイルの構文確認
    if ! docker-compose config &> /dev/null; then
        log_error "Docker Composeファイルに構文エラーがあります"
        return 1
    fi
    
    log_success "Docker環境の確認が完了しました"
}

# メイン処理
main() {
    local env_type="${1:-}"
    
    # ヘルプの表示
    if [[ "$env_type" == "-h" || "$env_type" == "--help" ]]; then
        show_usage
        exit 0
    fi
    
    # キー生成モード
    if [[ "$env_type" == "generate-keys" ]]; then
        generate_secret_keys
        exit 0
    fi
    
    # 環境設定の実行
    setup_environment "$env_type"
    
    # 検証の実行
    validate_environment
    
    # Docker環境の確認（オプション）
    if command -v docker &> /dev/null; then
        check_docker
    fi
    
    # 完了メッセージ
    echo ""
    log_success "🎉 環境設定が正常に完了しました！"
    echo ""
    echo "次のステップ:"
    echo "1. .envファイルの内容を確認・編集してください"
    echo "2. Ollamaサーバーを起動してください: ollama serve"
    echo "3. アプリケーションを起動してください:"
    echo "   - 開発環境: nix develop --command uvicorn app.main:app --reload"
    echo "   - Docker環境: docker-compose up"
}

# スクリプトの実行
main "$@"