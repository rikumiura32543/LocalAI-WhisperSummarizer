# =============================================
# M4A転写システム Dockerfile
# =============================================

# ベースイメージ
FROM python:3.11-slim as base

# メタデータ
LABEL maintainer="M4A Transcribe Team"
LABEL description="M4A音声ファイル転写・AI要約システム"
LABEL version="1.0.0"

# システムの更新と必要パッケージのインストール
RUN apt-get update && apt-get install -y \
    # システム依存関係
    curl \
    wget \
    git \
    build-essential \
    pkg-config \
    # 音声処理ライブラリ
    ffmpeg \
    libsndfile1 \
    libasound2-dev \
    # その他のユーティリティ
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Python環境設定
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 作業ディレクトリ
WORKDIR /app

# UVのインストール
RUN pip install uv

# 開発ステージ
FROM base as development

# 開発用パッケージの追加インストール
RUN apt-get update && apt-get install -y \
    vim \
    htop \
    && rm -rf /var/lib/apt/lists/*

# プロジェクトファイルのコピー
COPY pyproject.toml ./

# 依存関係のインストール（開発用も含む）
RUN uv venv && \
    . .venv/bin/activate && \
    uv pip install -e ".[dev]"

# アプリケーションコードのコピー
COPY . .

# 権限設定
RUN chmod +x scripts/*.sh || true

# ポート公開
EXPOSE 8000

# ヘルスチェック
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 開発用エントリーポイント
CMD ["sh", "-c", ". .venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"]

# =============================================
# 本番ステージ
# =============================================
FROM base as production

# 本番用のセキュリティ設定
RUN groupadd -r appuser && useradd -r -g appuser appuser

# プロジェクトファイルのコピー
COPY pyproject.toml ./

# 本番用依存関係のインストール（Google Cloud E2最適化）
RUN uv venv && \
    . .venv/bin/activate && \
    uv pip install . && \
    # Pythonキャッシュクリーンアップ
    find /app/.venv -name "*.pyc" -delete && \
    find /app/.venv -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# アプリケーションコードのコピー
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY static/ ./static/

# 必要なディレクトリ作成
RUN mkdir -p uploads data logs && \
    chown -R appuser:appuser /app

# 権限設定
RUN chmod +x scripts/*.sh || true

# 非rootユーザーに切り替え
USER appuser

# ポート公開
EXPOSE 8000

# ヘルスチェック
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 環境変数設定
ENV WORKERS=2 \
    MAX_REQUESTS=1000 \
    MAX_REQUESTS_JITTER=50 \
    TIMEOUT=30 \
    KEEP_ALIVE=2

# 本番用エントリーポイント（Google Cloud E2最適化）
CMD ["sh", "-c", ". .venv/bin/activate && gunicorn app.main:app -w $WORKERS -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 --max-requests $MAX_REQUESTS --max-requests-jitter $MAX_REQUESTS_JITTER --timeout $TIMEOUT --keep-alive $KEEP_ALIVE --preload --access-logfile - --error-logfile -"]

# =============================================
# テスト専用ステージ
# =============================================
FROM development as test

# テスト実行
RUN . .venv/bin/activate && pytest tests/ --cov=app --cov-report=html --cov-report=term-missing

# =============================================
# CI/CD用ステージ
# =============================================
FROM base as ci

# CI/CD用ツールのインストール
RUN pip install uv

# プロジェクトファイルのコピー
COPY pyproject.toml ./

# CI用依存関係のインストール
RUN uv venv && \
    . .venv/bin/activate && \
    uv pip install -e ".[dev,test]"

# アプリケーションコードのコピー  
COPY . .

# リンター・テストの実行
RUN . .venv/bin/activate && \
    black --check app/ tests/ && \
    isort --check-only app/ tests/ && \
    flake8 app/ tests/ && \
    mypy app/ && \
    pytest tests/ --cov=app --cov-fail-under=80

# ビルド成果物の出力
RUN . .venv/bin/activate && \
    uv build