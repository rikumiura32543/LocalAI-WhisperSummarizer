// =================================
// M4A転写システム TypeScript型定義
// =================================

// 基本型定義
export type JobId = string;
export type UsageType = 'meeting' | 'interview';
export type JobStatus = 'uploading' | 'transcribing' | 'summarizing' | 'completed' | 'error';
export type FileFormat = 'txt' | 'json' | 'csv';

// =================================
// エンティティ定義
// =================================

/**
 * 処理ジョブ
 */
export interface TranscriptionJob {
  id: JobId;
  filename: string;
  fileSize: number;
  usageType: UsageType;
  status: JobStatus;
  progress: number; // 0-100
  message?: string;
  createdAt: Date;
  updatedAt: Date;
  completedAt?: Date;
  errorMessage?: string;
}

/**
 * 音声ファイル情報
 */
export interface AudioFile {
  filename: string;
  size: number;
  type: string; // MIME type
  duration?: number; // 秒
  format: string; // 'M4A'
  bitrate?: number;
  sampleRate?: number;
}

/**
 * 転写結果
 */
export interface TranscriptionResult {
  text: string;
  confidence: number; // 0-1
  language?: string;
  duration: number;
  segments?: TranscriptionSegment[];
  createdAt: Date;
}

/**
 * 転写セグメント（タイムスタンプ付き）
 */
export interface TranscriptionSegment {
  start: number; // 秒
  end: number; // 秒
  text: string;
  confidence: number;
  speaker?: string; // 話者識別（オプション）
}

/**
 * AI要約結果（基底型）
 */
export interface BaseSummary {
  type: UsageType;
  createdAt: Date;
  confidence: number;
  model: string; // Ollamaモデル名
}

/**
 * 会議要約
 */
export interface MeetingSummary extends BaseSummary {
  type: 'meeting';
  decisions: string[]; // 決定事項
  actionPlans: ActionPlan[]; // アクションプラン
  summary: string; // 会議要約
  nextMeeting: string; // 次回会議内容
}

/**
 * 面接要約
 */
export interface InterviewSummary extends BaseSummary {
  type: 'interview';
  evaluation: CandidateEvaluation; // 候補者評価
  experience: string; // これまでの経験
  careerAxis: string; // 就活の軸
  workExperience: string; // 職務経験
  character: string; // キャラクター
  nextSteps: string; // 次回への申し送り
}

/**
 * アクションプラン
 */
export interface ActionPlan {
  task: string;
  assignee: string;
  dueDate?: string;
  priority: 'high' | 'medium' | 'low';
  status: 'pending' | 'in_progress' | 'completed';
}

/**
 * 候補者評価
 */
export interface CandidateEvaluation {
  strengths: string[]; // 良かったところ
  weaknesses: string[]; // 悪かったところ
  overallRating: number; // 1-5
  recommendation: 'hire' | 'maybe' | 'pass';
  comments: string;
}

/**
 * 最終結果
 */
export interface ProcessingResult {
  jobId: JobId;
  audioFile: AudioFile;
  transcription: TranscriptionResult;
  summary: MeetingSummary | InterviewSummary;
  generatedFiles: GeneratedFile[];
  processingTime: number; // 秒
}

/**
 * 生成ファイル
 */
export interface GeneratedFile {
  type: FileFormat;
  filename: string;
  size: number;
  downloadUrl: string;
  createdAt: Date;
}

// =================================
// APIリクエスト/レスポンス型
// =================================

/**
 * API共通レスポンス
 */
export interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  error?: ApiError;
  timestamp: string;
}

/**
 * APIエラー
 */
export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, any>;
}

/**
 * ファイルアップロードリクエスト
 */
export interface UploadRequest {
  file: File;
  usageType: UsageType;
  options?: ProcessingOptions;
}

/**
 * 処理オプション
 */
export interface ProcessingOptions {
  outputFormats?: FileFormat[];
  includeTimestamps?: boolean;
  enableSpeakerDetection?: boolean;
  language?: string;
  ollamaModel?: string;
}

/**
 * ジョブステータスレスポンス
 */
export interface JobStatusResponse {
  job: TranscriptionJob;
  currentStep?: ProcessingStep;
  estimatedTimeRemaining?: number; // 秒
}

/**
 * 処理ステップ
 */
export interface ProcessingStep {
  name: string;
  status: 'pending' | 'running' | 'completed' | 'error';
  progress: number;
  message?: string;
  startedAt?: Date;
  completedAt?: Date;
}

/**
 * 結果取得レスポンス
 */
export interface ResultResponse {
  result: ProcessingResult;
  downloadUrls: Record<FileFormat, string>;
}

/**
 * システム情報レスポンス
 */
export interface SystemInfoResponse {
  version: string;
  ollamaModels: OllamaModelInfo[];
  systemResources: SystemResources;
  supportedFormats: string[];
  maxFileSize: number; // bytes
}

/**
 * Ollamaモデル情報
 */
export interface OllamaModelInfo {
  name: string;
  size: number; // bytes
  description: string;
  language: string[];
  isActive: boolean;
  memoryUsage: number; // MB
}

/**
 * システムリソース情報
 */
export interface SystemResources {
  cpu: {
    cores: number;
    usage: number; // 0-100
  };
  memory: {
    total: number; // MB
    used: number; // MB
    available: number; // MB
  };
  disk: {
    total: number; // MB
    used: number; // MB
    available: number; // MB
  };
}

// =================================
// フロントエンド固有型
// =================================

/**
 * UI状態
 */
export interface UIState {
  currentJob?: TranscriptionJob;
  isProcessing: boolean;
  uploadProgress: number;
  error?: string;
  results?: ProcessingResult[];
}

/**
 * ファイルドロップイベント
 */
export interface FileDropEvent {
  files: FileList;
  isValid: boolean;
  errors: string[];
}

/**
 * プログレスバー表示情報
 */
export interface ProgressInfo {
  percentage: number;
  message: string;
  step: string;
  timeRemaining?: string;
}

/**
 * フォーム検証結果
 */
export interface ValidationResult {
  isValid: boolean;
  errors: Record<string, string>;
}

/**
 * ダウンロード設定
 */
export interface DownloadConfig {
  format: FileFormat;
  includeMetadata: boolean;
  filename?: string;
}

// =================================
// 設定・環境型
// =================================

/**
 * アプリケーション設定
 */
export interface AppConfig {
  apiBaseUrl: string;
  maxFileSize: number;
  supportedFormats: string[];
  ollamaConfig: OllamaConfig;
  uiConfig: UIConfig;
}

/**
 * Ollama設定
 */
export interface OllamaConfig {
  baseUrl: string;
  defaultModel: string;
  timeoutSeconds: number;
  maxRetries: number;
}

/**
 * UI設定
 */
export interface UIConfig {
  theme: 'light' | 'dark';
  language: 'ja' | 'en';
  colorPalette: ColorPalette;
  accessibility: AccessibilityConfig;
}

/**
 * カラーパレット
 */
export interface ColorPalette {
  white: string;      // #FFFFFF
  black: string;      // #222222
  primary: string;    // #4CAF50
  danger: string;     // #D32F2F
  grayLight: string;  // #F5F5F5
  grayMedium: string; // #E0E0E0
}

/**
 * アクセシビリティ設定
 */
export interface AccessibilityConfig {
  highContrast: boolean;
  largeText: boolean;
  screenReaderOptimized: boolean;
  keyboardNavigation: boolean;
}

// =================================
// ユーティリティ型
// =================================

/**
 * オプショナルフィールドを持つ型
 */
export type Optional<T, K extends keyof T> = Omit<T, K> & Partial<Pick<T, K>>;

/**
 * 必須フィールドを持つ型
 */
export type Required<T, K extends keyof T> = T & Required<Pick<T, K>>;

/**
 * APIレスポンス型のユーティリティ
 */
export type ApiResponseData<T> = T extends ApiResponse<infer U> ? U : never;

/**
 * 非同期処理結果型
 */
export type AsyncResult<T, E = Error> = Promise<
  | { success: true; data: T }
  | { success: false; error: E }
>;

// =================================
// 定数型定義
// =================================

export const USAGE_TYPES = ['meeting', 'interview'] as const;
export const JOB_STATUSES = ['uploading', 'transcribing', 'summarizing', 'completed', 'error'] as const;
export const FILE_FORMATS = ['txt', 'json', 'csv'] as const;
export const SUPPORTED_AUDIO_FORMATS = ['audio/mp4', 'audio/m4a'] as const;

export const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB
export const OLLAMA_TIMEOUT = 300; // 5 minutes
export const POLL_INTERVAL = 1000; // 1 second

// =================================
// 型ガード関数
// =================================

export function isMeetingSummary(summary: BaseSummary): summary is MeetingSummary {
  return summary.type === 'meeting';
}

export function isInterviewSummary(summary: BaseSummary): summary is InterviewSummary {
  return summary.type === 'interview';
}

export function isValidUsageType(value: string): value is UsageType {
  return USAGE_TYPES.includes(value as UsageType);
}

export function isValidJobStatus(value: string): value is JobStatus {
  return JOB_STATUSES.includes(value as JobStatus);
}

export function isValidFileFormat(value: string): value is FileFormat {
  return FILE_FORMATS.includes(value as FileFormat);
}

// =================================
// 型変換ユーティリティ
// =================================

export function createEmptyJob(id: JobId, filename: string, usageType: UsageType): TranscriptionJob {
  return {
    id,
    filename,
    fileSize: 0,
    usageType,
    status: 'uploading',
    progress: 0,
    createdAt: new Date(),
    updatedAt: new Date(),
  };
}

export function createApiResponse<T>(data: T): ApiResponse<T> {
  return {
    success: true,
    data,
    timestamp: new Date().toISOString(),
  };
}

export function createApiError(code: string, message: string, details?: Record<string, any>): ApiResponse {
  return {
    success: false,
    error: { code, message, details },
    timestamp: new Date().toISOString(),
  };
}