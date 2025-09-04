#!/bin/bash

# M4A転写システム - 本番環境デプロイメントスクリプト
# Google Cloud E2での自動デプロイメント対応

set -euo pipefail

# スクリプトディレクトリ
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# カラー出力
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

# 設定
ENVIRONMENT="${ENVIRONMENT:-production}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
PROJECT_ID="${GCP_PROJECT_ID:-}"
ZONE="${GCE_ZONE:-asia-northeast1-a}"
INSTANCE_NAME="${GCE_INSTANCE_NAME:-m4a-transcribe-vm}"

# 使用方法表示
usage() {
    cat << EOF
使用方法: $0 [COMMAND] [OPTIONS]

コマンド:
  build        - Dockerイメージをビルド
  test         - テスト実行
  deploy       - 本番環境にデプロイ
  rollback     - 前のバージョンにロールバック
  health       - ヘルスチェック実行
  logs         - アプリケーションログ表示
  backup       - 手動バックアップ作成
  help         - このヘルプを表示

環境変数:
  ENVIRONMENT     - デプロイ環境 (production|staging) デフォルト: production
  IMAGE_TAG       - Dockerイメージのタグ デフォルト: latest
  GCP_PROJECT_ID  - Google Cloud プロジェクトID
  GCE_ZONE       - Google Compute Engine ゾーン
  GCE_INSTANCE_NAME - インスタンス名

例:
  $0 build
  $0 deploy
  ENVIRONMENT=staging $0 deploy
  $0 rollback
EOF
}

# 必要なコマンドチェック
check_dependencies() {
    local missing_deps=()
    
    for cmd in docker gcloud; do
        if ! command -v "$cmd" &> /dev/null; then
            missing_deps+=("$cmd")
        fi
    done
    
    if [[ ${#missing_deps[@]} -gt 0 ]]; then
        log_error "以下のコマンドが見つかりません: ${missing_deps[*]}"
        log_error "必要な依存関係をインストールしてください"
        exit 1
    fi
}

# Google Cloudの認証チェック
check_gcloud_auth() {
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
        log_error "Google Cloudに認証されていません"
        log_info "次のコマンドで認証してください: gcloud auth login"
        exit 1
    fi
    
    if [[ -z "${PROJECT_ID}" ]]; then
        PROJECT_ID=$(gcloud config get-value project)
        if [[ -z "${PROJECT_ID}" ]]; then
            log_error "Google CloudプロジェクトIDが設定されていません"
            log_info "次のコマンドでプロジェクトを設定してください: gcloud config set project YOUR_PROJECT_ID"
            exit 1
        fi
    fi
}

# Dockerイメージビルド
build_image() {
    log_info "Dockerイメージをビルド中..."
    
    cd "${PROJECT_ROOT}"
    
    # マルチステージビルドで本番用イメージ作成
    docker build \
        --target production \
        --build-arg ENVIRONMENT="${ENVIRONMENT}" \
        -t "gcr.io/${PROJECT_ID}/m4a-transcribe:${IMAGE_TAG}" \
        -t "gcr.io/${PROJECT_ID}/m4a-transcribe:latest" \
        .
    
    log_success "Dockerイメージビルド完了"
}

# イメージをGoogle Container Registryにプッシュ
push_image() {
    log_info "イメージをGoogle Container Registryにプッシュ中..."
    
    # Dockerの認証設定
    gcloud auth configure-docker --quiet
    
    # イメージプッシュ
    docker push "gcr.io/${PROJECT_ID}/m4a-transcribe:${IMAGE_TAG}"
    docker push "gcr.io/${PROJECT_ID}/m4a-transcribe:latest"
    
    log_success "イメージプッシュ完了"
}

# テスト実行
run_tests() {
    log_info "テストを実行中..."
    
    cd "${PROJECT_ROOT}"
    
    # Docker Composeでテスト環境構築
    docker-compose -f docker-compose.yml -f docker-compose.test.yml up -d
    
    # テスト実行
    docker-compose exec -T app pytest tests/ -v --tb=short
    
    # テスト環境クリーンアップ
    docker-compose -f docker-compose.yml -f docker-compose.test.yml down
    
    log_success "テスト完了"
}

# デプロイメント実行
deploy() {
    log_info "本番環境にデプロイ中..."
    
    # 現在の状態バックアップ
    create_deployment_backup
    
    # インスタンスにSSH接続してデプロイ実行
    gcloud compute ssh "${INSTANCE_NAME}" \
        --zone="${ZONE}" \
        --project="${PROJECT_ID}" \
        --command="
            set -euo pipefail
            cd /opt/m4a-transcribe
            
            # 最新のDocker Composeファイル取得
            curl -fsSL https://raw.githubusercontent.com/your-repo/m4a-transcribe/main/docker-compose.prod.yml \
                -o docker-compose.prod.yml
            
            # 新しいイメージをプル
            docker pull gcr.io/${PROJECT_ID}/m4a-transcribe:${IMAGE_TAG}
            
            # アプリケーション停止（グレースフル）
            docker-compose -f docker-compose.prod.yml stop app
            
            # データベースバックアップ
            if [[ -f data/m4a_transcribe.db ]]; then
                cp data/m4a_transcribe.db data/m4a_transcribe.db.backup-\$(date +%Y%m%d_%H%M%S)
            fi
            
            # 新しいイメージで起動
            IMAGE_TAG=${IMAGE_TAG} docker-compose -f docker-compose.prod.yml up -d
            
            # ヘルスチェック待機
            echo 'アプリケーション起動待機中...'
            sleep 30
            
            # ヘルスチェック
            for i in {1..10}; do
                if curl -f http://localhost:8000/health > /dev/null 2>&1; then
                    echo 'ヘルスチェック成功'
                    break
                fi
                if [[ \$i -eq 10 ]]; then
                    echo 'ヘルスチェック失敗 - ロールバック実行'
                    docker-compose -f docker-compose.prod.yml stop app
                    IMAGE_TAG=latest docker-compose -f docker-compose.prod.yml up -d
                    exit 1
                fi
                echo \"ヘルスチェック試行 \$i/10\"
                sleep 10
            done
            
            echo 'デプロイ完了'
        "
    
    # デプロイ後の検証
    verify_deployment
    
    log_success "デプロイ完了"
}

# デプロイメント検証
verify_deployment() {
    log_info "デプロイメント検証中..."
    
    # 外部IPアドレス取得
    local external_ip
    external_ip=$(gcloud compute addresses describe m4a-transcribe-global-ip \
        --global \
        --format="value(address)" \
        --project="${PROJECT_ID}")
    
    if [[ -z "${external_ip}" ]]; then
        log_warning "外部IPアドレスが取得できませんでした"
        return
    fi
    
    # ヘルスチェック
    local health_url="http://${external_ip}/health"
    log_info "ヘルスチェック: ${health_url}"
    
    for i in {1..5}; do
        if curl -f -s "${health_url}" > /dev/null; then
            log_success "ヘルスチェック成功"
            break
        fi
        if [[ $i -eq 5 ]]; then
            log_error "ヘルスチェック失敗"
            return 1
        fi
        log_info "ヘルスチェック試行 $i/5"
        sleep 10
    done
    
    # APIエンドポイント確認
    local api_url="http://${external_ip}/api/v1/status"
    if curl -f -s "${api_url}" > /dev/null; then
        log_success "API確認成功"
    else
        log_warning "API確認に失敗しました"
    fi
}

# ロールバック
rollback() {
    log_warning "前のバージョンにロールバック中..."
    
    gcloud compute ssh "${INSTANCE_NAME}" \
        --zone="${ZONE}" \
        --project="${PROJECT_ID}" \
        --command="
            set -euo pipefail
            cd /opt/m4a-transcribe
            
            # 現在のコンテナ停止
            docker-compose -f docker-compose.prod.yml stop app
            
            # 最新の安定版に戻す
            IMAGE_TAG=latest docker-compose -f docker-compose.prod.yml up -d
            
            # ヘルスチェック
            sleep 20
            if curl -f http://localhost:8000/health > /dev/null 2>&1; then
                echo 'ロールバック成功'
            else
                echo 'ロールバック失敗'
                exit 1
            fi
        "
    
    log_success "ロールバック完了"
}

# バックアップ作成
create_deployment_backup() {
    log_info "デプロイメント前バックアップ作成中..."
    
    gcloud compute ssh "${INSTANCE_NAME}" \
        --zone="${ZONE}" \
        --project="${PROJECT_ID}" \
        --command="
            cd /opt/m4a-transcribe
            
            # データベースバックアップ
            if [[ -f data/m4a_transcribe.db ]]; then
                backup_name=\"deployment-backup-\$(date +%Y%m%d_%H%M%S).db\"
                cp data/m4a_transcribe.db \"backups/\$backup_name\"
                gzip \"backups/\$backup_name\"
                echo \"バックアップ作成: \$backup_name.gz\"
            fi
        "
    
    log_success "バックアップ作成完了"
}

# 手動バックアップ
create_backup() {
    log_info "手動バックアップ作成中..."
    
    gcloud compute ssh "${INSTANCE_NAME}" \
        --zone="${ZONE}" \
        --project="${PROJECT_ID}" \
        --command="
            cd /opt/m4a-transcribe
            
            # APIを使用してバックアップ作成
            curl -X POST http://localhost:8000/api/v1/backup/create \
                -H 'Content-Type: application/json' \
                -d '{\"backup_type\": \"full\", \"description\": \"Manual backup via deploy script\"}'
        "
    
    log_success "手動バックアップ完了"
}

# ログ表示
show_logs() {
    log_info "アプリケーションログを表示中..."
    
    gcloud compute ssh "${INSTANCE_NAME}" \
        --zone="${ZONE}" \
        --project="${PROJECT_ID}" \
        --command="
            cd /opt/m4a-transcribe
            docker-compose -f docker-compose.prod.yml logs -f --tail=100 app
        "
}

# ヘルスチェック
health_check() {
    log_info "ヘルスチェック実行中..."
    
    # ローカルからの確認
    local external_ip
    external_ip=$(gcloud compute addresses describe m4a-transcribe-global-ip \
        --global \
        --format="value(address)" \
        --project="${PROJECT_ID}" 2>/dev/null || echo "")
    
    if [[ -n "${external_ip}" ]]; then
        log_info "外部ヘルスチェック: http://${external_ip}/health"
        curl -s "http://${external_ip}/health" | jq '.' || echo "Failed to get health status"
    fi
    
    # インスタンス内部からの確認
    gcloud compute ssh "${INSTANCE_NAME}" \
        --zone="${ZONE}" \
        --project="${PROJECT_ID}" \
        --command="
            echo 'Internal health check:'
            curl -s http://localhost:8000/health/comprehensive | jq '.'
        "
}

# メイン実行部分
main() {
    case "${1:-help}" in
        build)
            check_dependencies
            check_gcloud_auth
            build_image
            push_image
            ;;
        test)
            check_dependencies
            run_tests
            ;;
        deploy)
            check_dependencies
            check_gcloud_auth
            build_image
            push_image
            deploy
            ;;
        rollback)
            check_dependencies
            check_gcloud_auth
            rollback
            ;;
        health)
            check_dependencies
            check_gcloud_auth
            health_check
            ;;
        logs)
            check_dependencies
            check_gcloud_auth
            show_logs
            ;;
        backup)
            check_dependencies
            check_gcloud_auth
            create_backup
            ;;
        help)
            usage
            ;;
        *)
            log_error "不明なコマンド: $1"
            usage
            exit 1
            ;;
    esac
}

# スクリプト実行
main "$@"