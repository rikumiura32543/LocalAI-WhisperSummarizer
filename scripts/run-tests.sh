#!/bin/bash
# M4A転写システム - テスト実行スクリプト

set -e

# カラーコード定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ヘルプ表示
show_help() {
    echo "M4A転写システム テスト実行スクリプト"
    echo ""
    echo "使用方法:"
    echo "  $0 [オプション] [テストタイプ]"
    echo ""
    echo "テストタイプ:"
    echo "  unit        - ユニットテスト実行"
    echo "  integration - 統合テスト実行"
    echo "  e2e         - エンドツーエンドテスト実行"
    echo "  all         - 全テスト実行 (デフォルト)"
    echo "  coverage    - カバレッジ付きテスト実行"
    echo "  fast        - 高速テスト実行（slowマーク除外）"
    echo ""
    echo "オプション:"
    echo "  -h, --help     - このヘルプを表示"
    echo "  -v, --verbose  - 詳細出力"
    echo "  -q, --quiet    - 簡潔出力"
    echo "  -f, --fail-fast- 最初の失敗で停止"
    echo "  -c, --clean    - 事前にキャッシュクリア"
    echo "  -r, --reports  - HTMLレポート生成"
    echo ""
    echo "例:"
    echo "  $0 unit -v              # ユニットテストを詳細出力で実行"
    echo "  $0 all -c -r            # 全テストをクリーン状態でレポート生成付きで実行"
    echo "  $0 coverage --fail-fast # カバレッジテストを最初の失敗で停止"
}

# デフォルト値設定
TEST_TYPE="all"
VERBOSE=""
QUIET=""
FAIL_FAST=""
CLEAN=false
REPORTS=false
PYTEST_ARGS=""

# 引数解析
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -v|--verbose)
            VERBOSE="-v"
            shift
            ;;
        -q|--quiet)
            QUIET="-q"
            shift
            ;;
        -f|--fail-fast)
            FAIL_FAST="--maxfail=1"
            shift
            ;;
        -c|--clean)
            CLEAN=true
            shift
            ;;
        -r|--reports)
            REPORTS=true
            shift
            ;;
        unit|integration|e2e|all|coverage|fast)
            TEST_TYPE="$1"
            shift
            ;;
        *)
            echo -e "${RED}不明なオプション: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# 関数定義
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

# 環境確認
check_environment() {
    log_info "環境確認中..."
    
    if ! command -v python &> /dev/null; then
        log_error "Pythonが見つかりません"
        exit 1
    fi
    
    if ! command -v pytest &> /dev/null; then
        log_error "pytestが見つかりません。uv sync --devを実行してください"
        exit 1
    fi
    
    python_version=$(python --version 2>&1)
    pytest_version=$(pytest --version 2>&1 | head -n1)
    log_info "Python: $python_version"
    log_info "pytest: $pytest_version"
}

# キャッシュクリア
clean_cache() {
    log_info "キャッシュクリア中..."
    
    # pytest キャッシュ
    find . -name ".pytest_cache" -type d -exec rm -rf {} + 2>/dev/null || true
    
    # Python キャッシュ
    find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    find . -name "*.pyc" -delete 2>/dev/null || true
    
    # カバレッジファイル
    rm -f .coverage* 2>/dev/null || true
    rm -rf htmlcov/ 2>/dev/null || true
    
    # 古いレポート
    rm -rf reports/ 2>/dev/null || true
    
    log_success "キャッシュクリア完了"
}

# レポートディレクトリ準備
setup_reports() {
    if [ "$REPORTS" = true ]; then
        mkdir -p reports
        log_info "レポートディレクトリを作成: reports/"
    fi
}

# テスト実行
run_tests() {
    local test_path=""
    local extra_args=""
    local description=""
    
    case $TEST_TYPE in
        "unit")
            test_path="tests/unit/"
            description="ユニットテスト"
            extra_args="--cov=app --cov-report=term-missing"
            ;;
        "integration")
            test_path="tests/integration/"
            description="統合テスト"
            ;;
        "e2e")
            test_path="tests/e2e/"
            description="エンドツーエンドテスト"
            extra_args="-m 'not slow'"
            ;;
        "coverage")
            test_path="tests/"
            description="カバレッジテスト"
            extra_args="--cov=app --cov-report=term-missing --cov-report=html --cov-fail-under=80"
            ;;
        "fast")
            test_path="tests/"
            description="高速テスト"
            extra_args="-m 'not slow'"
            ;;
        "all")
            test_path="tests/"
            description="全テスト"
            ;;
    esac
    
    # レポート生成オプション
    if [ "$REPORTS" = true ]; then
        extra_args="$extra_args --html=reports/${TEST_TYPE}-report.html --self-contained-html"
        extra_args="$extra_args --json-report --json-report-file=reports/${TEST_TYPE}-report.json"
    fi
    
    # pytest引数構築
    PYTEST_ARGS="$test_path $VERBOSE $QUIET $FAIL_FAST $extra_args"
    
    log_info "${description}を実行中..."
    log_info "コマンド: pytest $PYTEST_ARGS"
    
    # テスト実行
    start_time=$(date +%s)
    
    if pytest $PYTEST_ARGS; then
        end_time=$(date +%s)
        duration=$((end_time - start_time))
        log_success "${description}が完了しました (実行時間: ${duration}秒)"
        return 0
    else
        end_time=$(date +%s)
        duration=$((end_time - start_time))
        log_error "${description}が失敗しました (実行時間: ${duration}秒)"
        return 1
    fi
}

# メイン処理
main() {
    echo "======================================"
    echo "M4A転写システム テスト実行"
    echo "======================================"
    
    # 環境確認
    check_environment
    
    # キャッシュクリア
    if [ "$CLEAN" = true ]; then
        clean_cache
    fi
    
    # レポートディレクトリ準備
    setup_reports
    
    # テスト実行
    if run_tests; then
        echo ""
        log_success "全てのテストが正常に完了しました！"
        
        if [ "$REPORTS" = true ]; then
            log_info "レポートが生成されました: reports/"
            if [ -f "reports/${TEST_TYPE}-report.html" ]; then
                log_info "HTMLレポート: reports/${TEST_TYPE}-report.html"
            fi
        fi
        
        if [ "$TEST_TYPE" = "coverage" ] || [[ "$extra_args" == *"--cov"* ]]; then
            if [ -d "htmlcov" ]; then
                log_info "カバレッジレポート: htmlcov/index.html"
            fi
        fi
        
        exit 0
    else
        echo ""
        log_error "テストが失敗しました。"
        
        if [ "$REPORTS" = true ]; then
            log_info "エラーレポートを確認してください: reports/"
        fi
        
        exit 1
    fi
}

# スクリプト実行
main "$@"