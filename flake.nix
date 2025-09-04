{
  description = "M4A転写システム - 音声ファイルからテキスト転写とAI要約を生成するシステム";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        
        # Python環境の構築
        python = pkgs.python311;
        pythonPackages = python.pkgs;
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            # Python環境
            python
            pythonPackages.pip
            pythonPackages.virtualenv
            uv  # Python package manager

            # システム依存関係
            ffmpeg-full
            sqlite
            curl
            wget
            git

            # Ollama関連
            ollama

            # 開発ツール
            nodejs
            docker
            docker-compose
            
            # セキュリティ・暗号化
            openssl
            
            # システムライブラリ（音声処理用）
            pkg-config
            libsndfile
          ];

          shellHook = ''
            echo "🚀 M4A転写システム開発環境にようこそ!"
            echo ""
            echo "利用可能なコマンド:"
            echo "  uv run app             - アプリケーション起動"  
            echo "  docker-compose up      - Docker環境起動"
            echo "  ollama serve           - Ollama AI サーバー起動"
            echo ""
            echo "環境情報:"
            echo "  Python: $(python --version)"
            echo "  Node.js: $(node --version)"
            echo "  Docker: $(docker --version)"
            echo "  FFmpeg: $(ffmpeg -version | head -n1)"
            echo ""

            # Python仮想環境の作成と有効化（必要に応じて）
            if [ ! -d ".venv" ]; then
              echo "Python仮想環境を初期化中..."
              uv venv
            fi
            
            # 仮想環境の有効化
            source .venv/bin/activate
            
            # Ollamaの初期化確認
            if ! pgrep -x "ollama" > /dev/null; then
              echo "💡 Ollamaサーバーを起動するには 'ollama serve' を実行してください"
            fi
            
            export PYTHONPATH="$PWD:$PYTHONPATH"
          '';

          # 環境変数
          OLLAMA_HOST = "127.0.0.1:11434";
          WHISPER_MODEL = "base";
          DATABASE_URL = "sqlite:///./m4a_transcribe.db";
          
          # セキュリティ設定
          PYTHONDONTWRITEBYTECODE = "1";
          PYTHONUNBUFFERED = "1";
        };

        # アプリケーション実行用の設定
        packages.default = pkgs.writeShellApplication {
          name = "m4a-transcribe";
          runtimeInputs = with pkgs; [ python ffmpeg-full sqlite ollama ];
          text = ''
            cd ${./.}
            source .venv/bin/activate
            exec python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8100
          '';
        };

        # 開発用アプリケーション
        apps = {
          default = flake-utils.lib.mkApp {
            drv = self.packages.${system}.default;
          };
          
          # データベース初期化
          init-db = flake-utils.lib.mkApp {
            drv = pkgs.writeShellApplication {
              name = "init-db";
              runtimeInputs = [ python pkgs.sqlite ];
              text = ''
                cd ${./.}
                source .venv/bin/activate
                python scripts/init_db.py
              '';
            };
          };

          # テスト実行
          test = flake-utils.lib.mkApp {
            drv = pkgs.writeShellApplication {
              name = "test";
              runtimeInputs = [ python ];
              text = ''
                cd ${./.}
                source .venv/bin/activate
                python -m pytest tests/ -v
              '';
            };
          };
        };
      }
    );
}