# M4A転写システム - 開発環境起動方法

## 🚀 クイックスタート

### 1. NIX環境での起動（推奨）

```bash
# プロジェクトディレクトリに移動
cd /Users/bl32543/Git/m4a_transcribe

# NIXパスを設定（毎回必要）
export PATH="/nix/store/qm174m9g5zj8pzwizpms9n8n64pldrxg-nix-2.30.2/bin:$PATH"

# NIX開発環境に入る（実験的機能を有効化）
nix --extra-experimental-features 'nix-command flakes' develop

# 依存関係インストール（初回のみ）
uv sync

# データベース初期化（初回のみ）
source .venv/bin/activate && python scripts/init_db.py

# 開発サーバー起動
source .venv/bin/activate && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8100
```

### 2. ワンライナーでの起動

```bash
# NIX環境で直接起動
export PATH="/nix/store/qm174m9g5zj8pzwizpms9n8n64pldrxg-nix-2.30.2/bin:$PATH" && \
nix --extra-experimental-features 'nix-command flakes' develop --command bash -c \
"source .venv/bin/activate && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8100"
```

## 📋 利用可能なエンドポイント

サーバー起動後、以下のURLでアクセス可能：

- **メイン画面**: http://localhost:8100/
- **API仕様書**: http://localhost:8100/api/docs (開発環境のみ)
- **ヘルスチェック**: http://localhost:8100/health
- **システム状態**: http://localhost:8100/api/v1/status
- **監視ダッシュボード**: http://localhost:8100/static/dashboard.html

## 🔧 開発環境設定

### 環境変数ファイル
`.env` ファイルが自動作成されますが、必要に応じて編集可能：
```bash
# 現在の設定確認
cat .env
```

### 必要な外部サービス

1. **Ollama AI サービス**（AI要約機能用）- **必須**
```bash
# Ollamaサービス起動（バックグラウンド）
export PATH="/nix/store/qm174m9g5zj8pzwizpms9n8n64pldrxg-nix-2.30.2/bin:$PATH" && ollama serve &

# 利用可能モデル確認
curl -s http://localhost:11434/api/tags | jq .

# 現在設定中のモデル: qwen2:7b
```

2. **Redis**（キャッシュ機能用）- オプション
```bash
# Docker Composeで起動
docker-compose up redis
```

## 🧪 テスト実行

```bash
# NIX環境でテスト実行
nix --extra-experimental-features 'nix-command flakes' develop --command bash -c \
"source .venv/bin/activate && python -m pytest tests/ -v"
```

## 🐳 Docker環境での起動

```bash
# Docker Composeでの起動
docker-compose up --build

# 本番環境設定での起動
docker-compose -f docker-compose.prod.yml up --build
```

## ⚡ NIX環境の機能

NIX環境に入ると以下が利用可能：
- Python 3.11.13
- Node.js v22.18.0  
- Docker
- FFmpeg 7.1.1
- SQLite
- Ollama
- UV (高速Python パッケージマネージャー)

## 🔍 トラブルシューティング

### NIXが見つからない場合
```bash
# NIXの場所を確認
find /nix /usr/local /opt -name "nix" -type f 2>/dev/null
```

### 依存関係エラー
```bash
# 依存関係を再インストール
uv sync --reinstall
```

### データベースエラー
```bash
# データベースを再初期化
rm data/m4a_transcribe.db*
python scripts/init_db.py
```

## 🎯 主要機能の動作確認

### 進捗表示システム
- 音声ファイルアップロード後、リアルタイムで進捗が0%→100%まで表示される
- 処理中画面のアイコンが円の中央に正しく配置される
- ファイルアップロード → 音声書き起こし → AI要約生成の各段階を視覚化

### システムヘルス
- 全サービス正常動作: `curl http://localhost:8100/health`
- データベース接続正常
- Ollama AI要約機能正常
- SQLAlchemy 2.0対応済み

## 🔄 最新の修正内容

### v2025.09.03 更新内容
1. **Ollama設定修正**: モデルを`llama2:7b`→`qwen2:7b`に変更
2. **UI改善**: 処理中画面のステップアイコンを円の中央に配置
3. **SQLAlchemy対応**: text()を使用してSQLクエリを明示的に宣言
4. **エラー解消**: 全ての404エラーとSQLエラーを修正

### 現在の動作状況
- ✅ FastAPIサーバー正常動作（localhost:8100）
- ✅ Ollamaサービス正常動作（qwen2:7bモデル）
- ✅ 進捗表示機能完全動作（0%→100%）
- ✅ データベース接続正常（SQLite）
- ✅ UI/UXの視覚的改善完了