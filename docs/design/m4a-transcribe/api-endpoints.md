# API エンドポイント仕様

## 概要

M4A転写システムのRESTful API仕様。FastAPIベースで実装し、OpenAPI 3.0に準拠。

**ベースURL**: `http://localhost:8000` (開発環境)  
**認証方式**: JWT Token (将来対応)  
**レスポンス形式**: JSON  
**文字エンコーディング**: UTF-8

## 共通レスポンス形式

```json
{
  "success": true,
  "data": { ... },
  "error": null,
  "timestamp": "2024-01-01T00:00:00Z"
}
```

エラー時:
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "ERROR_CODE",
    "message": "エラーメッセージ",
    "details": { ... }
  },
  "timestamp": "2024-01-01T00:00:00Z"
}
```

## エンドポイント一覧

### 1. ファイルアップロード・転写開始

#### POST `/api/v1/transcribe`

M4Aファイルをアップロードし、転写・要約処理を開始する。

**リクエスト**:
```http
POST /api/v1/transcribe
Content-Type: multipart/form-data

file: [M4A音声ファイル]
usage_type: "meeting" | "interview"
options: {
  "output_formats": ["txt", "json"],
  "include_timestamps": true,
  "enable_speaker_detection": false,
  "language": "ja",
  "ollama_model": "llama2:7b"
}
```

**レスポンス**:
```json
{
  "success": true,
  "data": {
    "job_id": "uuid-string",
    "filename": "meeting_20240101.m4a",
    "file_size": 1048576,
    "usage_type": "meeting",
    "status": "uploading",
    "progress": 0,
    "estimated_time": 900,
    "created_at": "2024-01-01T00:00:00Z"
  }
}
```

**エラーコード**:
- `FILE_TOO_LARGE`: ファイルサイズが上限を超過
- `INVALID_FORMAT`: サポートされていないファイル形式
- `CORRUPT_FILE`: ファイルが破損している
- `PROCESSING_LIMIT`: 処理中のジョブ数上限

### 2. 処理状況確認

#### GET `/api/v1/jobs/{job_id}/status`

処理の進行状況を取得する。

**パラメータ**:
- `job_id`: ジョブID (required)

**レスポンス**:
```json
{
  "success": true,
  "data": {
    "job": {
      "id": "uuid-string",
      "filename": "meeting_20240101.m4a",
      "status": "transcribing",
      "progress": 45,
      "message": "音声転写処理中...",
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-01T00:05:00Z"
    },
    "current_step": {
      "name": "transcription",
      "status": "running",
      "progress": 45,
      "message": "Whisperによる音声転写実行中",
      "started_at": "2024-01-01T00:02:00Z"
    },
    "estimated_time_remaining": 480
  }
}
```

**エラーコード**:
- `JOB_NOT_FOUND`: 指定されたジョブが存在しない

### 3. 処理結果取得

#### GET `/api/v1/jobs/{job_id}/result`

完了した処理の結果を取得する。

**パラメータ**:
- `job_id`: ジョブID (required)

**レスポンス**:
```json
{
  "success": true,
  "data": {
    "job_id": "uuid-string",
    "audio_file": {
      "filename": "meeting_20240101.m4a",
      "size": 1048576,
      "duration": 3600,
      "format": "M4A",
      "bitrate": 128
    },
    "transcription": {
      "text": "転写されたテキスト全文...",
      "confidence": 0.95,
      "language": "ja",
      "duration": 3600,
      "segments_count": 150
    },
    "summary": {
      "type": "meeting",
      "decisions": [
        "プロジェクトのスケジュールを1週間前倒しする",
        "新しいデザインシステムを採用する"
      ],
      "action_plans": [
        {
          "task": "要件定義書の更新",
          "assignee": "田中",
          "due_date": "2024-01-15",
          "priority": "high"
        }
      ],
      "summary": "プロジェクトの進捗確認と今後の方針について議論...",
      "next_meeting": "来週の進捗確認とリスクアセスメント",
      "confidence": 0.88,
      "model": "llama2:7b"
    },
    "generated_files": [
      {
        "type": "txt",
        "filename": "meeting_20240101_result.txt",
        "size": 4096,
        "download_url": "/api/v1/download/uuid-string/txt"
      }
    ],
    "processing_time": 720
  }
}
```

**エラーコード**:
- `JOB_NOT_FOUND`: ジョブが存在しない
- `JOB_NOT_COMPLETED`: 処理が未完了
- `RESULT_EXPIRED`: 結果の有効期限が切れている

### 4. ファイルダウンロード

#### GET `/api/v1/download/{job_id}/{format}`

処理結果ファイルをダウンロードする。

**パラメータ**:
- `job_id`: ジョブID (required)
- `format`: ファイル形式 (`txt`, `json`, `csv`) (required)

**レスポンス**:
```http
Content-Type: text/plain; charset=utf-8
Content-Disposition: attachment; filename="meeting_20240101_result.txt"

# 会議転写結果
日時: 2024-01-01 10:00-11:00
用途: 会議

## 転写テキスト
[転写されたテキスト全文...]

## 決定事項
1. プロジェクトのスケジュールを1週間前倒しする
2. 新しいデザインシステムを採用する

## アクションプラン
...
```

**エラーコード**:
- `FILE_NOT_FOUND`: ファイルが存在しない
- `FILE_EXPIRED`: ファイルの有効期限が切れている

### 5. ジョブ一覧取得

#### GET `/api/v1/jobs`

処理ジョブの一覧を取得する。

**クエリパラメータ**:
- `status`: ステータスフィルター (optional)
- `usage_type`: 用途フィルター (optional)
- `limit`: 取得件数 (default: 20, max: 100)
- `offset`: オフセット (default: 0)

**レスポンス**:
```json
{
  "success": true,
  "data": {
    "jobs": [
      {
        "id": "uuid-string",
        "filename": "meeting_20240101.m4a",
        "usage_type": "meeting",
        "status": "completed",
        "progress": 100,
        "created_at": "2024-01-01T00:00:00Z",
        "completed_at": "2024-01-01T00:12:00Z"
      }
    ],
    "total": 1,
    "limit": 20,
    "offset": 0
  }
}
```

### 6. システム情報取得

#### GET `/api/v1/system/info`

システムの状況と設定情報を取得する。

**レスポンス**:
```json
{
  "success": true,
  "data": {
    "version": "1.0.0",
    "ollama_models": [
      {
        "name": "llama2:7b",
        "size": 3800000000,
        "description": "Llama 2 7B parameter model",
        "language": ["ja", "en"],
        "is_active": true,
        "memory_usage": 4096
      }
    ],
    "system_resources": {
      "cpu": {
        "cores": 2,
        "usage": 45.2
      },
      "memory": {
        "total": 8192,
        "used": 3072,
        "available": 5120
      },
      "disk": {
        "total": 81920,
        "used": 40960,
        "available": 40960
      }
    },
    "supported_formats": ["audio/m4a", "audio/mp4"],
    "max_file_size": 52428800,
    "current_jobs": 0,
    "max_concurrent_jobs": 1
  }
}
```

### 7. ジョブ削除

#### DELETE `/api/v1/jobs/{job_id}`

処理ジョブと関連ファイルを削除する。

**パラメータ**:
- `job_id`: ジョブID (required)

**レスポンス**:
```json
{
  "success": true,
  "data": {
    "message": "ジョブが正常に削除されました",
    "deleted_job_id": "uuid-string",
    "deleted_files_count": 3
  }
}
```

**エラーコード**:
- `JOB_NOT_FOUND`: ジョブが存在しない
- `JOB_IN_PROGRESS`: 処理中のジョブは削除不可

### 8. ジョブキャンセル

#### POST `/api/v1/jobs/{job_id}/cancel`

実行中の処理をキャンセルする。

**パラメータ**:
- `job_id`: ジョブID (required)

**レスポンス**:
```json
{
  "success": true,
  "data": {
    "message": "処理がキャンセルされました",
    "job_id": "uuid-string",
    "previous_status": "transcribing",
    "cancelled_at": "2024-01-01T00:05:00Z"
  }
}
```

### 9. 設定更新

#### PUT `/api/v1/system/settings`

システム設定を更新する。

**リクエスト**:
```json
{
  "default_ollama_model": "llama2:7b",
  "max_file_size_mb": 50,
  "file_retention_days": 7,
  "enable_speaker_detection": false
}
```

**レスポンス**:
```json
{
  "success": true,
  "data": {
    "message": "設定が更新されました",
    "updated_settings": {
      "default_ollama_model": "llama2:7b",
      "max_file_size_mb": 50,
      "file_retention_days": 7,
      "enable_speaker_detection": false
    }
  }
}
```

## WebSocket エンドポイント

### リアルタイム処理状況更新

#### WS `/api/v1/ws/jobs/{job_id}`

処理状況のリアルタイム更新を受信する。

**接続例**:
```javascript
const ws = new WebSocket(`ws://localhost:8000/api/v1/ws/jobs/${jobId}`);

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // { status: "transcribing", progress: 45, message: "..." }
};
```

## エラーコード一覧

| コード | 説明 | HTTPステータス |
|--------|------|----------------|
| `INVALID_REQUEST` | リクエストの形式が不正 | 400 |
| `FILE_TOO_LARGE` | ファイルサイズが上限を超過 | 413 |
| `INVALID_FORMAT` | サポートされていないファイル形式 | 415 |
| `CORRUPT_FILE` | ファイルが破損している | 400 |
| `PROCESSING_LIMIT` | 処理中のジョブ数上限 | 429 |
| `JOB_NOT_FOUND` | ジョブが存在しない | 404 |
| `JOB_NOT_COMPLETED` | 処理が未完了 | 409 |
| `JOB_IN_PROGRESS` | 処理中のジョブは操作不可 | 409 |
| `RESULT_EXPIRED` | 結果の有効期限が切れている | 410 |
| `FILE_NOT_FOUND` | ファイルが存在しない | 404 |
| `FILE_EXPIRED` | ファイルの有効期限が切れている | 410 |
| `OLLAMA_ERROR` | Ollama AI処理エラー | 502 |
| `WHISPER_ERROR` | Whisper転写処理エラー | 502 |
| `STORAGE_ERROR` | ストレージエラー | 500 |
| `SYSTEM_OVERLOAD` | システムリソース不足 | 503 |

## レート制限

- **ファイルアップロード**: 1分間に5回まで
- **ステータス確認**: 1秒間に10回まで
- **結果取得**: 1分間に100回まで
- **システム情報**: 1分間に60回まで

## セキュリティ

### HTTPS必須
本番環境では全てのエンドポイントでHTTPS通信を強制する。

### CORS設定
```python
# 許可されたオリジン（本番環境では制限）
CORS_ORIGINS = [
    "http://localhost:3000",
    "https://yourdomain.com"
]
```

### ファイル検証
- ファイル形式の厳密な検証
- マルウェア検査（ClamAV等）
- ファイルサイズ制限
- 処理時間制限

### データ保護
- 処理完了後の自動ファイル削除
- ログの個人情報マスキング
- アクセス履歴の記録

## API仕様書生成

FastAPIの自動生成機能により、以下のURLで詳細なAPI仕様書を確認できます：

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`