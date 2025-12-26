# LocalAI-WhisperSummarizer - 開発環境起動方法

## 🚀 クイックスタート

### 1. NIX環境での起動（推奨）

```bash
# プロジェクトディレクトリに移動
cd m4a_transcribe

# NIX開発環境に入る（実験的な機能を有効化）
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
ollama serve &

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

### v2025.10.20 AI処理パイプライン最適化
1. **AI文脈補正機能追加**: 書き起こし→AI文脈補正→AI要約の3段階処理
2. **処理フロー改善**:
   - 音声書き起こしエリア: Whisperの初回書き起こし内容を表示
   - AI要約エリア: 文脈補正後のテキストから生成した要約を表示
3. **AIモデル最適化**:
   - Ollama: `schroneko/gemma-2-2b-jpn-it:latest` (日本語特化)
   - Whisper: `large-v3-turbo` (高精度・高速)
4. **MIMEタイプ正規化**: `audio/x-wav`等のバリエーションを標準形式に自動変換
5. **要約表示改善**: JSON形式を廃止し、箇条書き（•）と見出し（■）で整形

### 現在の動作状況
- ✅ FastAPIサーバー正常動作（localhost:8100）
- ✅ Ollamaサービス正常動作（gemma-2-2b-jpn-itモデル）
- ✅ Whisper大規模モデル正常動作（large-v3-turbo）
- ✅ AI文脈補正機能完全動作
- ✅ 進捗表示機能完全動作（0%→100%）
- ✅ データベース接続正常（SQLite）
- ✅ MIMEタイプ正規化機能追加

## 🔬 AI処理パイプライン詳細

### 3段階処理フロー

```
1. 音声書き起こし (Whisper)
   ├─ 進捗: 10% → 50%
   ├─ モデル: large-v3-turbo
   └─ 出力: 元の書き起こしテキスト（transcription_result["text"]）

2. AI文脈補正 (Ollama)
   ├─ 進捗: 50% → 70%
   ├─ モデル: gemma-2-2b-jpn-it
   ├─ 処理内容:
   │  ├─ 誤字脱字の修正
   │  ├─ 文脈から明らかに間違っている単語の修正
   │  ├─ 句読点の適切な追加
   │  ├─ 改行の適切な追加
   │  └─ 専門用語・固有名詞の推測修正
   └─ 出力: 補正後テキスト（transcription_result["corrected_text"]）

3. AI要約生成 (Ollama)
   ├─ 進捗: 70% → 100%
   ├─ モデル: gemma-2-2b-jpn-it
   ├─ 入力: 補正後テキスト
   └─ 出力: 構造化要約
      ├─ 概要（summary）
      ├─ 決定事項（decisions）
      ├─ アクションプラン（action_plans）
      └─ 次回会議（next_meeting）
```

### 表示仕様

**音声書き起こしエリア**
- 表示内容: Whisperの初回書き起こし結果（未補正）
- データソース: `transcription_result["text"]`
- フォーマット: プレーンテキスト（`<pre>`タグ）

**AI要約エリア**
- 表示内容: 文脈補正後のテキストから生成した要約
- データソース: `summary_result["formatted_text"]`
- フォーマット:
  - `■` で始まる行 → `<h3>`見出し
  - `•` で始まる行 → `<li>`箇条書き
  - 通常の行 → `<p>`段落

### ファイル検証・正規化

**MIMEタイプ正規化**
```python
# 検出されたMIMEタイプ → 標準形式
'audio/x-m4a'  → 'audio/m4a'
'audio/wave'   → 'audio/wav'
'audio/x-wav'  → 'audio/wav'
'audio/mpeg'   → 'audio/mp3'
```

**サポート形式**
- M4A (audio/m4a, audio/x-m4a)
- MP4 (audio/mp4)
- WAV (audio/wav, audio/x-wav, audio/wave)
- MP3 (audio/mp3, audio/mpeg)

## 🎨 デザインシステム

### カラーパレット（6色厳守）
```css
--color-white: #FFFFFF;     /* 背景・テキスト */
--color-black: #222222;     /* メインテキスト */
--color-primary: #4CAF50;   /* プライマリボタン・アクセント */
--color-danger: #D32F2F;    /* エラー・警告 */
--color-gray-light: #F5F5F5; /* 軽いセパレーター */
--color-gray-medium: #E0E0E0; /* ボーダー・無効状態 */
```

### デザイン原則
- **完全フラットデザイン**: `box-shadow: none`, `border-radius: 0`
- **44px最小タッチサイズ**: WCAG 2.1 AA準拠
- **絵文字禁止**: テキストのみ使用
- **レスポンシブ**: モバイルファーストデザイン
- **アクセシビリティ**: コントラスト比4.5:1以上

## 📝 開発ガイドライン

### コーディング規約

**Pythonコード**
- PEP 8準拠
- 型ヒント必須（mypy検証）
- docstring必須（Google Style）
- ログ出力はstructlogを使用

**JavaScriptコード**
- Vanilla JS（フレームワーク不使用）
- ES6+構文
- async/awaitパターン
- コメント必須（JSDoc形式）

### データベース設計

**制約ルール**
- CHECK制約でデータ整合性を保証
- FOREIGN KEY制約で参照整合性を保証
- NOT NULL制約で必須項目を明示
- DEFAULT値で初期値を設定

**MIMEタイプ制約**
```sql
CONSTRAINT check_mime_type CHECK (mime_type IN (
    'audio/mp4',
    'audio/m4a',
    'audio/wav',
    'audio/mp3'
))
```
注: バリエーション（audio/x-wav等）は正規化処理で標準形式に変換

### エラーハンドリング

**フロントエンド**
- try-catchで全API呼び出しを囲む
- エラーメッセージはユーザーフレンドリーに
- コンソールに詳細ログを出力

**バックエンド**
- カスタム例外クラスを使用
- structlogで構造化ログ出力
- HTTPステータスコードを適切に設定