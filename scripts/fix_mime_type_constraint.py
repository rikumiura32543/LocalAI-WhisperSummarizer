#!/usr/bin/env python3
"""
MIMEタイプ制約を修正するマイグレーションスクリプト
"""
import sqlite3
from pathlib import Path

def fix_mime_type_constraint():
    """MIMEタイプ制約を修正"""
    db_path = Path("data/m4a_transcribe.db")
    if not db_path.exists():
        print("データベースファイルが見つかりません")
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        print("MIMEタイプ制約を修正しています...")
        
        # 既存のテーブル構造を確認
        cursor.execute("PRAGMA table_info(transcription_jobs)")
        columns = cursor.fetchall()
        
        # 一時テーブルを作成（新しい制約付き）
        cursor.execute("""
        CREATE TABLE transcription_jobs_new (
            id VARCHAR(36) NOT NULL,
            filename VARCHAR(255) NOT NULL,
            original_filename VARCHAR(255) NOT NULL,
            file_size INTEGER NOT NULL,
            file_hash VARCHAR(64) NOT NULL,
            mime_type VARCHAR(100) NOT NULL,
            usage_type_code VARCHAR(20) NOT NULL,
            status_code VARCHAR(20) NOT NULL,
            progress INTEGER DEFAULT 0,
            message TEXT,
            error_message TEXT,
            error_code VARCHAR(50),
            processing_started_at DATETIME,
            processing_completed_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            CONSTRAINT check_file_size_positive CHECK (file_size > 0),
            CONSTRAINT check_progress_range CHECK (progress >= 0 AND progress <= 100),
            CONSTRAINT check_mime_type CHECK (mime_type IN (
                'audio/mp4', 
                'audio/m4a', 
                'audio/wav', 
                'audio/mp3'
            )),
            FOREIGN KEY(usage_type_code) REFERENCES usage_types (code),
            FOREIGN KEY(status_code) REFERENCES job_statuses (code)
        )
        """)
        
        # 既存データを新しいテーブルにコピー（MIMEタイプを正規化）
        cursor.execute("""
        INSERT INTO transcription_jobs_new 
        SELECT 
            id, filename, original_filename, file_size, file_hash,
            CASE 
                WHEN mime_type = 'audio/x-m4a' THEN 'audio/m4a'
                WHEN mime_type = 'audio/wave' THEN 'audio/wav'
                WHEN mime_type = 'audio/x-wav' THEN 'audio/wav'
                WHEN mime_type = 'audio/mpeg' THEN 'audio/mp3'
                ELSE mime_type 
            END as mime_type,
            usage_type_code, status_code, progress, message, error_message, error_code,
            processing_started_at, processing_completed_at, created_at, updated_at
        FROM transcription_jobs
        """)
        
        # 古いテーブルを削除
        cursor.execute("DROP TABLE transcription_jobs")
        
        # 新しいテーブルをリネーム
        cursor.execute("ALTER TABLE transcription_jobs_new RENAME TO transcription_jobs")
        
        # インデックスを再作成
        cursor.execute("CREATE INDEX idx_transcription_jobs_status ON transcription_jobs(status_code)")
        cursor.execute("CREATE INDEX idx_transcription_jobs_created_at ON transcription_jobs(created_at DESC)")
        cursor.execute("CREATE INDEX idx_transcription_jobs_usage_type ON transcription_jobs(usage_type_code)")
        
        # トリガーを再作成
        cursor.execute("""
        CREATE TRIGGER trigger_transcription_jobs_updated_at
            AFTER UPDATE ON transcription_jobs
        BEGIN
            UPDATE transcription_jobs SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
        END
        """)
        
        conn.commit()
        print("MIMEタイプ制約の修正が完了しました")
        
    except Exception as e:
        conn.rollback()
        print(f"エラーが発生しました: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    fix_mime_type_constraint()