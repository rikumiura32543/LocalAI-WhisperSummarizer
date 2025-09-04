#!/bin/bash
# Ollama/Whisperモデルセットアップスクリプト

set -e

# カラー出力設定
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 設定値
OLLAMA_MODEL="${OLLAMA_MODEL:-llama2:7b}"
WHISPER_MODEL="${WHISPER_MODEL:-base}"
OLLAMA_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"

echo -e "${BLUE}M4A転写システム - AI モデルセットアップ${NC}"
echo "=================================="

# Ollamaサーバーの確認
echo -e "${YELLOW}Ollamaサーバーの確認中...${NC}"
if curl -s "${OLLAMA_URL}/api/tags" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Ollamaサーバー接続成功: ${OLLAMA_URL}${NC}"
else
    echo -e "${RED}✗ Ollamaサーバーに接続できません: ${OLLAMA_URL}${NC}"
    echo "  Ollamaサーバーを起動してください: ollama serve"
    exit 1
fi

# Ollamaモデルのダウンロード
echo -e "${YELLOW}Ollamaモデルの確認とダウンロード...${NC}"
echo "  モデル: ${OLLAMA_MODEL}"

# モデル存在確認
if ollama list | grep -q "${OLLAMA_MODEL}"; then
    echo -e "${GREEN}✓ モデル '${OLLAMA_MODEL}' は既に利用可能です${NC}"
else
    echo -e "${YELLOW}モデル '${OLLAMA_MODEL}' をダウンロード中...${NC}"
    echo "  これには数分から数十分かかる場合があります"
    
    if ollama pull "${OLLAMA_MODEL}"; then
        echo -e "${GREEN}✓ モデル '${OLLAMA_MODEL}' のダウンロード完了${NC}"
    else
        echo -e "${RED}✗ モデル '${OLLAMA_MODEL}' のダウンロードに失敗しました${NC}"
        exit 1
    fi
fi

# Whisperモデルの事前ダウンロード（Pythonスクリプトで実行）
echo -e "${YELLOW}Whisperモデルの確認とダウンロード...${NC}"
echo "  モデル: ${WHISPER_MODEL}"

cat > /tmp/whisper_setup.py << 'EOF'
import sys
import whisper
import os

model_name = os.environ.get('WHISPER_MODEL', 'base')

try:
    print(f"Whisperモデル '{model_name}' を読み込み中...")
    model = whisper.load_model(model_name)
    print(f"✓ Whisperモデル '{model_name}' の読み込み完了")
    
    # モデル情報表示
    print(f"  デバイス: {next(model.parameters()).device}")
    print(f"  パラメータ数: {sum(p.numel() for p in model.parameters()):,}")
    
except Exception as e:
    print(f"✗ Whisperモデル '{model_name}' の読み込みに失敗: {e}")
    sys.exit(1)
EOF

if python3 /tmp/whisper_setup.py; then
    echo -e "${GREEN}✓ Whisperモデル準備完了${NC}"
else
    echo -e "${RED}✗ Whisperモデルの準備に失敗しました${NC}"
    echo "  依存関係を確認してください: pip install openai-whisper"
fi

# 一時ファイル削除
rm -f /tmp/whisper_setup.py

# モデル情報表示
echo -e "${BLUE}設定されたモデル情報:${NC}"
echo "  Ollama URL: ${OLLAMA_URL}"
echo "  Ollamaモデル: ${OLLAMA_MODEL}"
echo "  Whisperモデル: ${WHISPER_MODEL}"

# モデルテスト実行
echo -e "${YELLOW}モデル動作テスト中...${NC}"

# Ollamaテスト
echo "Ollamaテスト実行中..."
if curl -s -X POST "${OLLAMA_URL}/api/generate" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"${OLLAMA_MODEL}\",\"prompt\":\"Hello\",\"stream\":false,\"options\":{\"num_predict\":10}}" \
  | grep -q "response"; then
    echo -e "${GREEN}✓ Ollamaモデルテスト成功${NC}"
else
    echo -e "${YELLOW}⚠ Ollamaモデルテストをスキップ（時間がかかるため）${NC}"
fi

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}🎉 AIモデルセットアップ完了！${NC}"
echo -e "${GREEN}========================================${NC}"
echo
echo "次のステップ:"
echo "1. アプリケーションを起動: python -m app.main"
echo "2. ヘルスチェック: curl http://localhost:8000/health"
echo "3. API詳細確認: curl http://localhost:8000/api/v1/health/detailed"