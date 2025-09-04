-- =====================================
-- M4A転写システム データベーススキーマ
-- =====================================
-- DBMS: SQLite (軽量、ローカル処理に最適)
-- バージョン: SQLite 3.x
-- 文字エンコーディング: UTF-8

-- プラグマ設定
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;

-- =====================================
-- マスターテーブル
-- =====================================

-- 使用用途マスター
CREATE TABLE usage_types (
    id INTEGER PRIMARY KEY,
    code TEXT UNIQUE NOT NULL CHECK(code IN ('meeting', 'interview')),
    name TEXT NOT NULL,
    description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 処理状況マスター
CREATE TABLE job_statuses (
    id INTEGER PRIMARY KEY,
    code TEXT UNIQUE NOT NULL CHECK(code IN ('uploading', 'transcribing', 'summarizing', 'completed', 'error')),
    name TEXT NOT NULL,
    description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ファイル形式マスター
CREATE TABLE file_formats (
    id INTEGER PRIMARY KEY,
    code TEXT UNIQUE NOT NULL CHECK(code IN ('txt', 'json', 'csv')),
    name TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    extension TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- =====================================
-- メインテーブル
-- =====================================

-- 処理ジョブテーブル
CREATE TABLE transcription_jobs (
    id TEXT PRIMARY KEY, -- UUID形式
    filename TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    file_size INTEGER NOT NULL CHECK(file_size > 0),
    file_hash TEXT NOT NULL, -- ファイル整合性チェック用
    mime_type TEXT NOT NULL CHECK(mime_type IN ('audio/mp4', 'audio/m4a')),
    
    usage_type_code TEXT NOT NULL,
    status_code TEXT NOT NULL DEFAULT 'uploading',
    progress INTEGER NOT NULL DEFAULT 0 CHECK(progress >= 0 AND progress <= 100),
    
    message TEXT, -- 進行状況メッセージ
    error_message TEXT, -- エラー詳細
    error_code TEXT, -- エラーコード
    
    processing_started_at DATETIME,
    processing_completed_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- 外部キー
    FOREIGN KEY (usage_type_code) REFERENCES usage_types(code),
    FOREIGN KEY (status_code) REFERENCES job_statuses(code)
);

-- 音声ファイル詳細情報
CREATE TABLE audio_files (
    job_id TEXT PRIMARY KEY,
    duration_seconds REAL, -- 音声長（秒）
    bitrate INTEGER, -- ビットレート
    sample_rate INTEGER, -- サンプリングレート
    channels INTEGER, -- チャンネル数
    format_details TEXT, -- フォーマット詳細（JSON）
    file_path TEXT NOT NULL, -- 一時保存パス
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (job_id) REFERENCES transcription_jobs(id) ON DELETE CASCADE
);

-- 転写結果テーブル
CREATE TABLE transcription_results (
    job_id TEXT PRIMARY KEY,
    text TEXT NOT NULL, -- 転写テキスト
    confidence REAL NOT NULL CHECK(confidence >= 0 AND confidence <= 1), -- 信頼度
    language TEXT, -- 検出言語
    duration_seconds REAL NOT NULL,
    model_used TEXT NOT NULL, -- 使用したWhisperモデル
    
    -- メタデータ
    processing_time_seconds REAL NOT NULL,
    segments_count INTEGER DEFAULT 0,
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (job_id) REFERENCES transcription_jobs(id) ON DELETE CASCADE
);

-- 転写セグメント（タイムスタンプ付きテキスト）
CREATE TABLE transcription_segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    segment_index INTEGER NOT NULL,
    
    start_time REAL NOT NULL, -- 開始時間（秒）
    end_time REAL NOT NULL, -- 終了時間（秒）
    text TEXT NOT NULL,
    confidence REAL NOT NULL CHECK(confidence >= 0 AND confidence <= 1),
    
    speaker_id TEXT, -- 話者識別ID（オプション）
    speaker_name TEXT, -- 話者名（オプション）
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (job_id) REFERENCES transcription_jobs(id) ON DELETE CASCADE,
    CHECK(start_time < end_time)
);

-- AI要約結果（基底テーブル）
CREATE TABLE ai_summaries (
    job_id TEXT PRIMARY KEY,
    type TEXT NOT NULL CHECK(type IN ('meeting', 'interview')),
    model_used TEXT NOT NULL, -- 使用したOllamaモデル
    confidence REAL NOT NULL CHECK(confidence >= 0 AND confidence <= 1),
    processing_time_seconds REAL NOT NULL,
    
    -- 共通フィールド
    raw_response TEXT NOT NULL, -- AI生成の生データ（JSON）
    formatted_text TEXT NOT NULL, -- 整形済みテキスト
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (job_id) REFERENCES transcription_jobs(id) ON DELETE CASCADE
);

-- 会議要約詳細
CREATE TABLE meeting_summaries (
    job_id TEXT PRIMARY KEY,
    
    -- 構造化データ（JSON形式で保存）
    decisions TEXT NOT NULL, -- 決定事項（JSON配列）
    action_plans TEXT NOT NULL, -- アクションプラン（JSON配列）
    summary TEXT NOT NULL, -- 会議要約
    next_meeting TEXT, -- 次回会議内容
    
    -- メタデータ
    participants_count INTEGER,
    meeting_duration_minutes INTEGER,
    topics_discussed TEXT, -- 議論されたトピック（JSON配列）
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (job_id) REFERENCES ai_summaries(job_id) ON DELETE CASCADE
);

-- 面接要約詳細
CREATE TABLE interview_summaries (
    job_id TEXT PRIMARY KEY,
    
    -- 評価データ（JSON形式で保存）
    evaluation TEXT NOT NULL, -- 候補者評価（JSON）
    experience TEXT NOT NULL, -- これまでの経験
    career_axis TEXT NOT NULL, -- 就活の軸
    work_experience TEXT NOT NULL, -- 職務経験
    character_analysis TEXT NOT NULL, -- キャラクター分析
    next_steps TEXT NOT NULL, -- 次回への申し送り
    
    -- メタデータ
    interview_duration_minutes INTEGER,
    position_applied TEXT, -- 応募ポジション
    interviewer_notes TEXT, -- 面接官メモ（JSON）
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (job_id) REFERENCES ai_summaries(job_id) ON DELETE CASCADE
);

-- 生成ファイルテーブル
CREATE TABLE generated_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    
    file_type_code TEXT NOT NULL,
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    
    download_count INTEGER DEFAULT 0,
    last_downloaded_at DATETIME,
    expires_at DATETIME, -- ファイル有効期限
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (job_id) REFERENCES transcription_jobs(id) ON DELETE CASCADE,
    FOREIGN KEY (file_type_code) REFERENCES file_formats(code)
);

-- システム設定テーブル
CREATE TABLE system_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    data_type TEXT NOT NULL CHECK(data_type IN ('string', 'integer', 'float', 'boolean', 'json')),
    description TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Ollamaモデル管理
CREATE TABLE ollama_models (
    name TEXT PRIMARY KEY,
    size_bytes INTEGER NOT NULL,
    description TEXT,
    language_codes TEXT NOT NULL, -- サポート言語（JSON配列）
    is_active BOOLEAN DEFAULT FALSE,
    memory_usage_mb INTEGER,
    last_used_at DATETIME,
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 処理ログテーブル
CREATE TABLE processing_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT,
    log_level TEXT NOT NULL CHECK(log_level IN ('DEBUG', 'INFO', 'WARN', 'ERROR')),
    message TEXT NOT NULL,
    details TEXT, -- 詳細情報（JSON）
    
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (job_id) REFERENCES transcription_jobs(id) ON DELETE SET NULL
);

-- =====================================
-- インデックス定義
-- =====================================

-- メインテーブルのインデックス
CREATE INDEX idx_transcription_jobs_status ON transcription_jobs(status_code);
CREATE INDEX idx_transcription_jobs_created_at ON transcription_jobs(created_at DESC);
CREATE INDEX idx_transcription_jobs_usage_type ON transcription_jobs(usage_type_code);
CREATE INDEX idx_transcription_jobs_filename ON transcription_jobs(filename);

-- セグメントテーブルのインデックス
CREATE INDEX idx_transcription_segments_job_id ON transcription_segments(job_id);
CREATE INDEX idx_transcription_segments_time ON transcription_segments(start_time, end_time);

-- ファイルテーブルのインデックス
CREATE INDEX idx_generated_files_job_id ON generated_files(job_id);
CREATE INDEX idx_generated_files_type ON generated_files(file_type_code);
CREATE INDEX idx_generated_files_expires_at ON generated_files(expires_at);

-- ログテーブルのインデックス
CREATE INDEX idx_processing_logs_job_id ON processing_logs(job_id);
CREATE INDEX idx_processing_logs_level ON processing_logs(log_level);
CREATE INDEX idx_processing_logs_timestamp ON processing_logs(timestamp DESC);

-- =====================================
-- トリガー定義
-- =====================================

-- updated_atの自動更新トリガー
CREATE TRIGGER trigger_transcription_jobs_updated_at
    AFTER UPDATE ON transcription_jobs
BEGIN
    UPDATE transcription_jobs 
    SET updated_at = CURRENT_TIMESTAMP 
    WHERE id = NEW.id;
END;

CREATE TRIGGER trigger_system_settings_updated_at
    AFTER UPDATE ON system_settings
BEGIN
    UPDATE system_settings 
    SET updated_at = CURRENT_TIMESTAMP 
    WHERE key = NEW.key;
END;

CREATE TRIGGER trigger_ollama_models_updated_at
    AFTER UPDATE ON ollama_models
BEGIN
    UPDATE ollama_models 
    SET updated_at = CURRENT_TIMESTAMP 
    WHERE name = NEW.name;
END;

-- ファイル有効期限チェックトリガー
CREATE TRIGGER trigger_check_file_expiration
    AFTER INSERT ON generated_files
BEGIN
    UPDATE generated_files 
    SET expires_at = datetime(CURRENT_TIMESTAMP, '+7 days')
    WHERE id = NEW.id AND expires_at IS NULL;
END;

-- =====================================
-- マスターデータ初期投入
-- =====================================

-- 使用用途マスター
INSERT INTO usage_types (code, name, description) VALUES 
    ('meeting', '会議', '会議録作成用'),
    ('interview', '面接', '面接記録作成用');

-- 処理状況マスター
INSERT INTO job_statuses (code, name, description) VALUES 
    ('uploading', 'アップロード中', 'ファイルアップロード処理中'),
    ('transcribing', '転写中', '音声転写処理中'),
    ('summarizing', '要約中', 'AI要約生成中'),
    ('completed', '完了', '処理完了'),
    ('error', 'エラー', '処理エラー');

-- ファイル形式マスター
INSERT INTO file_formats (code, name, mime_type, extension) VALUES 
    ('txt', 'テキスト', 'text/plain', '.txt'),
    ('json', 'JSON', 'application/json', '.json'),
    ('csv', 'CSV', 'text/csv', '.csv');

-- システム設定初期値
INSERT INTO system_settings (key, value, data_type, description) VALUES 
    ('max_file_size_mb', '50', 'integer', '最大ファイルサイズ（MB）'),
    ('default_ollama_model', 'llama2:7b', 'string', 'デフォルトOllamaモデル'),
    ('transcription_timeout_seconds', '900', 'integer', '転写処理タイムアウト（秒）'),
    ('summary_timeout_seconds', '300', 'integer', 'AI要約処理タイムアウト（秒）'),
    ('file_retention_days', '7', 'integer', 'ファイル保持期間（日）'),
    ('enable_speaker_detection', 'false', 'boolean', '話者識別機能有効フラグ'),
    ('supported_languages', '["ja", "en"]', 'json', 'サポート言語'),
    ('ui_theme', 'light', 'string', 'UIテーマ'),
    ('accessibility_mode', 'true', 'boolean', 'アクセシビリティモード');

-- =====================================
-- ビュー定義
-- =====================================

-- ジョブ詳細ビュー（関連データを結合）
CREATE VIEW job_details AS
SELECT 
    j.id,
    j.filename,
    j.original_filename,
    j.file_size,
    j.usage_type_code,
    ut.name as usage_type_name,
    j.status_code,
    js.name as status_name,
    j.progress,
    j.message,
    j.error_message,
    j.processing_started_at,
    j.processing_completed_at,
    j.created_at,
    j.updated_at,
    
    -- 音声ファイル情報
    af.duration_seconds,
    af.bitrate,
    af.sample_rate,
    
    -- 転写結果情報
    tr.confidence as transcription_confidence,
    tr.language as detected_language,
    
    -- AI要約情報
    ais.model_used as ai_model,
    ais.confidence as summary_confidence
    
FROM transcription_jobs j
LEFT JOIN usage_types ut ON j.usage_type_code = ut.code
LEFT JOIN job_statuses js ON j.status_code = js.code
LEFT JOIN audio_files af ON j.id = af.job_id
LEFT JOIN transcription_results tr ON j.id = tr.job_id
LEFT JOIN ai_summaries ais ON j.id = ais.job_id;

-- 処理統計ビュー
CREATE VIEW processing_statistics AS
SELECT 
    usage_type_code,
    status_code,
    COUNT(*) as job_count,
    AVG(CASE 
        WHEN processing_completed_at IS NOT NULL AND processing_started_at IS NOT NULL 
        THEN (julianday(processing_completed_at) - julianday(processing_started_at)) * 24 * 60 * 60
        ELSE NULL 
    END) as avg_processing_time_seconds,
    MIN(created_at) as first_job_date,
    MAX(created_at) as last_job_date
FROM transcription_jobs 
GROUP BY usage_type_code, status_code;

-- =====================================
-- データベース最適化関数
-- =====================================

-- 期限切れファイル削除用クエリ（定期実行推奨）
-- DELETE FROM generated_files WHERE expires_at < CURRENT_TIMESTAMP;

-- 古いログ削除用クエリ（定期実行推奨）
-- DELETE FROM processing_logs WHERE timestamp < datetime(CURRENT_TIMESTAMP, '-30 days');

-- データベース最適化
-- VACUUM;
-- ANALYZE;