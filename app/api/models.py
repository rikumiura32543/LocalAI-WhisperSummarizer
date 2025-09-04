"""
APIレスポンス・リクエストモデル定義
"""

from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field, validator
from enum import Enum


# Enum定義
class UsageTypeEnum(str, Enum):
    """使用用途列挙"""
    MEETING = "meeting"
    INTERVIEW = "interview"
    LECTURE = "lecture"
    OTHER = "other"


class JobStatusEnum(str, Enum):
    """ジョブステータス列挙"""
    UPLOADING = "uploading"
    TRANSCRIBING = "transcribing"
    SUMMARIZING = "summarizing"
    COMPLETED = "completed"
    ERROR = "error"


class FileFormatEnum(str, Enum):
    """ファイル形式列挙"""
    TXT = "txt"
    JSON = "json"
    CSV = "csv"


# 基本レスポンスモデル
class BaseResponse(BaseModel):
    """基本レスポンス"""
    success: bool = True
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorResponse(BaseModel):
    """エラーレスポンス"""
    error: bool = True
    status_code: int
    message: str
    details: Optional[Dict[str, Any]] = None
    path: str


class PaginationMeta(BaseModel):
    """ページネーション情報"""
    total: int
    page: int
    per_page: int
    pages: int
    has_next: bool
    has_prev: bool


class PaginatedResponse(BaseResponse):
    """ページネーションレスポンス"""
    data: List[Any]
    meta: PaginationMeta


# 転写関連モデル
class TranscriptionJobRequest(BaseModel):
    """転写ジョブ作成リクエスト"""
    usage_type: UsageTypeEnum = Field(..., description="使用用途（meeting/interview）")
    
    @validator("usage_type")
    def validate_usage_type(cls, v):
        if v not in [UsageTypeEnum.MEETING, UsageTypeEnum.INTERVIEW]:
            raise ValueError("usage_type must be 'meeting' or 'interview'")
        return v


class AudioFileInfo(BaseModel):
    """音声ファイル情報"""
    duration_seconds: Optional[float] = None
    bitrate: Optional[int] = None
    sample_rate: Optional[int] = None
    channels: Optional[int] = None
    format_details: Optional[Dict[str, Any]] = None


class TranscriptionSegment(BaseModel):
    """転写セグメント"""
    segment_index: int
    start_time: float
    end_time: float
    text: str
    confidence: float
    speaker_id: Optional[str] = None
    speaker_name: Optional[str] = None


class TranscriptionResult(BaseModel):
    """転写結果"""
    text: str
    confidence: float
    language: Optional[str] = None
    duration_seconds: float
    model_used: str
    processing_time_seconds: float
    segments_count: int = 0
    segments: Optional[List[TranscriptionSegment]] = None


class TranscriptionJobResponse(BaseModel):
    """転写ジョブレスポンス"""
    id: str
    filename: str
    original_filename: str
    file_size: int
    file_size_formatted: Optional[str] = None
    mime_type: str
    usage_type_code: str
    status_code: JobStatusEnum
    progress: int
    message: Optional[str] = None
    error_message: Optional[str] = None
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    # 関連データ
    audio_file: Optional[AudioFileInfo] = None
    transcription_result: Optional[TranscriptionResult] = None
    
    class Config:
        from_attributes = True
    
    @validator("file_size_formatted", always=True)
    def format_file_size(cls, v, values):
        if "file_size" in values:
            size = values["file_size"]
            if size < 1024:
                return f"{size} B"
            elif size < 1024 * 1024:
                return f"{size / 1024:.1f} KB"
            else:
                return f"{size / (1024 * 1024):.1f} MB"
        return v


class TranscriptionJobListResponse(BaseResponse):
    """転写ジョブ一覧レスポンス"""
    jobs: List[TranscriptionJobResponse]
    total: int


# AI要約関連モデル
class MeetingSummaryDetails(BaseModel):
    """会議要約詳細"""
    summary: str
    decisions: List[str]
    action_plans: List[str]
    next_meeting: Optional[str] = None
    participants_count: Optional[int] = None
    meeting_duration_minutes: Optional[int] = None
    topics_discussed: Optional[List[str]] = None


class InterviewSummaryDetails(BaseModel):
    """面接要約詳細"""
    evaluation: Dict[str, Any]
    experience: str
    career_axis: str
    work_experience: str
    character_analysis: str
    next_steps: str
    interview_duration_minutes: Optional[int] = None
    position_applied: Optional[str] = None
    interviewer_notes: Optional[Dict[str, Any]] = None


class AISummaryResponse(BaseModel):
    """AI要約レスポンス"""
    job_id: str
    type: UsageTypeEnum
    model_used: str
    confidence: float
    processing_time_seconds: float
    formatted_text: str
    created_at: datetime
    
    # タイプ別詳細
    meeting_details: Optional[MeetingSummaryDetails] = None
    interview_details: Optional[InterviewSummaryDetails] = None


# ファイル関連モデル
class GeneratedFileResponse(BaseModel):
    """生成ファイルレスポンス"""
    id: int
    job_id: str
    file_type: FileFormatEnum
    filename: str
    file_size: int
    file_size_formatted: str
    download_count: int
    last_downloaded_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


# ステータス関連モデル
class ServiceStatus(BaseModel):
    """サービスステータス"""
    name: str
    status: str
    details: Optional[Dict[str, Any]] = None


class SystemStatusResponse(BaseModel):
    """システムステータスレスポンス"""
    api_version: str
    status: str
    environment: str
    app_version: str
    services: Dict[str, str]
    statistics: Dict[str, int]
    configuration: Dict[str, Any]


class HealthCheckResponse(BaseModel):
    """ヘルスチェックレスポンス"""
    status: str
    version: str
    environment: str
    services: Optional[Dict[str, ServiceStatus]] = None
    configuration: Optional[Dict[str, Any]] = None


# 統計関連モデル
class JobStatistics(BaseModel):
    """ジョブ統計"""
    status_distribution: Dict[str, int]
    usage_distribution: Dict[str, int]
    total_file_size_bytes: int
    average_processing_time_seconds: Optional[float] = None
    total_jobs: int


class SummaryStatistics(BaseModel):
    """要約統計"""
    type_distribution: Dict[str, Dict[str, Union[int, float]]]
    model_distribution: Dict[str, int]
    total_summaries: int


# バリデーション関連モデル
class FileValidationError(BaseModel):
    """ファイルバリデーションエラー"""
    field: str
    message: str
    code: str


class ValidationErrorResponse(ErrorResponse):
    """バリデーションエラーレスポンス"""
    errors: List[FileValidationError]


# プロセス関連モデル
class ProcessingLogResponse(BaseModel):
    """処理ログレスポンス"""
    id: int
    job_id: Optional[str] = None
    log_level: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime
    
    class Config:
        from_attributes = True


# エクスポート用モデル
class ExportDataResponse(BaseModel):
    """データエクスポートレスポンス"""
    metadata: Dict[str, Any]
    transcription: Optional[TranscriptionResult] = None
    summary: Optional[AISummaryResponse] = None
    files: List[GeneratedFileResponse] = []
    logs: List[ProcessingLogResponse] = []