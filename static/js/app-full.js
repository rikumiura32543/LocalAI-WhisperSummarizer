/**
 * M4A転写システム - メインJavaScript (完全版)
 * ファイルアップロード、処理状況管理、結果表示機能
 */

class M4ATranscriptionApp {
    constructor() {
        this.currentJobId = null;
        this.selectedFile = null;
        this.processingInterval = null;
        
        // DOM要素の取得
        this.elements = this.getElements();
        
        // 初期化
        this.init();
    }
    
    /**
     * DOM要素の取得
     */
    getElements() {
        return {
            // ファイル関連
            fileDropArea: document.getElementById('fileDropArea'),
            fileInput: document.getElementById('fileInput'),
            fileInfo: document.getElementById('fileInfo'),
            fileName: document.getElementById('fileName'),
            fileSize: document.getElementById('fileSize'),
            removeFileBtn: document.getElementById('removeFileBtn'),
            
            // フォーム関連
            usageType: document.getElementById('usageType'),
            processBtn: document.getElementById('processBtn'),
            
            // セクション
            uploadSection: document.getElementById('uploadSection'),
            processingSection: document.getElementById('processingSection'),
            resultsSection: document.getElementById('resultsSection'),
            errorSection: document.getElementById('errorSection'),
            
            // 処理状況
            progressBarFill: document.getElementById('progressBarFill'),
            progressText: document.getElementById('progressText'),
            currentStatus: document.getElementById('currentStatus'),
            cancelBtn: document.getElementById('cancelBtn'),
            
            // 処理ステップ
            step1: document.getElementById('step1'),
            step2: document.getElementById('step2'),
            step3: document.getElementById('step3'),
            
            // タブ
            transcriptionTab: document.getElementById('transcriptionTab'),
            summaryTab: document.getElementById('summaryTab'),
            transcriptionPanel: document.getElementById('transcriptionPanel'),
            summaryPanel: document.getElementById('summaryPanel'),
            
            // 結果表示
            processingTime: document.getElementById('processingTime'),
            audioDuration: document.getElementById('audioDuration'),
            detectedLanguage: document.getElementById('detectedLanguage'),
            confidence: document.getElementById('confidence'),
            transcriptionText: document.getElementById('transcriptionText'),
            summaryType: document.getElementById('summaryType'),
            aiModel: document.getElementById('aiModel'),
            summaryConfidence: document.getElementById('summaryConfidence'),
            summaryText: document.getElementById('summaryText'),
            
            // アクションボタン
            downloadTranscriptionTxt: document.getElementById('downloadTranscriptionTxt'),
            downloadTranscriptionJson: document.getElementById('downloadTranscriptionJson'),
            copyTranscriptionText: document.getElementById('copyTranscriptionText'),
            downloadSummaryTxt: document.getElementById('downloadSummaryTxt'),
            downloadSummaryJson: document.getElementById('downloadSummaryJson'),
            copySummaryText: document.getElementById('copySummaryText'),
            downloadAllBtn: document.getElementById('downloadAllBtn'),
            newProcessBtn: document.getElementById('newProcessBtn'),
            
            // エラー関連
            errorMessage: document.getElementById('errorMessage'),
            retryBtn: document.getElementById('retryBtn'),
            resetBtn: document.getElementById('resetBtn'),
            
            // その他
            toastContainer: document.getElementById('toastContainer'),
            loadingOverlay: document.getElementById('loadingOverlay')
        };
    }
    
    /**
     * 初期化
     */
    init() {
        this.setupEventListeners();
        this.updateProcessButtonState();
        
        console.log('M4A転写システム初期化完了');
    }
    
    /**
     * イベントリスナーの設定
     */
    setupEventListeners() {
        // ファイルドロップエリア
        if (this.elements.fileDropArea) {
            this.elements.fileDropArea.addEventListener('click', () => this.elements.fileInput?.click());
            this.elements.fileDropArea.addEventListener('dragover', (e) => this.handleDragOver(e));
            this.elements.fileDropArea.addEventListener('dragleave', (e) => this.handleDragLeave(e));
            this.elements.fileDropArea.addEventListener('drop', (e) => this.handleDrop(e));
            
            // キーボードアクセシビリティ
            this.elements.fileDropArea.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    this.elements.fileInput?.click();
                }
            });
        }
        
        // ファイル選択
        if (this.elements.fileInput) {
            this.elements.fileInput.addEventListener('change', (e) => this.handleFileSelect(e));
        }
        
        // ファイル削除
        if (this.elements.removeFileBtn) {
            this.elements.removeFileBtn.addEventListener('click', () => this.removeSelectedFile());
        }
        
        // 用途選択
        if (this.elements.usageType) {
            this.elements.usageType.addEventListener('change', () => this.updateProcessButtonState());
        }
        
        // 処理開始
        if (this.elements.processBtn) {
            this.elements.processBtn.addEventListener('click', () => this.startProcessing());
        }
        
        // キャンセル
        if (this.elements.cancelBtn) {
            this.elements.cancelBtn.addEventListener('click', () => this.cancelProcessing());
        }
        
        // タブ切り替え
        if (this.elements.transcriptionTab) {
            this.elements.transcriptionTab.addEventListener('click', () => this.switchTab('transcription'));
        }
        if (this.elements.summaryTab) {
            this.elements.summaryTab.addEventListener('click', () => this.switchTab('summary'));
        }
        
        // ダウンロードボタン
        this.setupDownloadButtons();
        
        // コピーボタン
        this.setupCopyButtons();
        
        // その他のアクションボタン
        if (this.elements.newProcessBtn) {
            this.elements.newProcessBtn.addEventListener('click', () => this.resetToUploadState());
        }
        
        if (this.elements.retryBtn) {
            this.elements.retryBtn.addEventListener('click', () => this.retryProcessing());
        }
        
        if (this.elements.resetBtn) {
            this.elements.resetBtn.addEventListener('click', () => this.resetToUploadState());
        }
    }
    
    /**
     * ドラッグオーバー処理
     */
    handleDragOver(e) {
        e.preventDefault();
        this.elements.fileDropArea?.classList.add('file-drop-area--dragover');
    }
    
    /**
     * ドラッグリーブ処理
     */
    handleDragLeave(e) {
        e.preventDefault();
        this.elements.fileDropArea?.classList.remove('file-drop-area--dragover');
    }
    
    /**
     * ドロップ処理
     */
    handleDrop(e) {
        e.preventDefault();
        this.elements.fileDropArea?.classList.remove('file-drop-area--dragover');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            this.processSelectedFile(files[0]);
        }
    }
    
    /**
     * ファイル選択処理
     */
    handleFileSelect(e) {
        const files = e.target.files;
        if (files.length > 0) {
            this.processSelectedFile(files[0]);
        }
    }
    
    /**
     * 選択されたファイルの処理
     */
    processSelectedFile(file) {
        // ファイル形式チェック
        const allowedTypes = ['.m4a', '.mp4', '.wav', '.mp3'];
        const fileExtension = '.' + file.name.split('.').pop().toLowerCase();
        
        if (!allowedTypes.includes(fileExtension)) {
            this.showToast('error', `サポートされていないファイル形式です。対応形式: ${allowedTypes.join(', ')}`);
            return;
        }
        
        // ファイルサイズチェック (50MB)
        const maxSize = 50 * 1024 * 1024;
        if (file.size > maxSize) {
            this.showToast('error', 'ファイルサイズが制限を超えています（最大: 50MB）');
            return;
        }
        
        this.selectedFile = file;
        this.displaySelectedFile(file);
        this.updateProcessButtonState();
    }
    
    /**
     * 選択されたファイルの表示
     */
    displaySelectedFile(file) {
        if (this.elements.fileName) this.elements.fileName.textContent = file.name;
        if (this.elements.fileSize) this.elements.fileSize.textContent = this.formatFileSize(file.size);
        if (this.elements.fileInfo) {
            this.elements.fileInfo.style.display = 'block';
            this.elements.fileInfo.classList.add('fade-in');
        }
    }
    
    /**
     * ファイル選択の削除
     */
    removeSelectedFile() {
        this.selectedFile = null;
        if (this.elements.fileInfo) this.elements.fileInfo.style.display = 'none';
        if (this.elements.fileInput) this.elements.fileInput.value = '';
        this.updateProcessButtonState();
    }
    
    /**
     * 処理ボタンの状態更新
     */
    updateProcessButtonState() {
        const hasFile = this.selectedFile !== null;
        const hasUsageType = this.elements.usageType?.value !== '';
        
        if (this.elements.processBtn) {
            this.elements.processBtn.disabled = !(hasFile && hasUsageType);
        }
    }
    
    /**
     * 処理開始
     */
    async startProcessing() {
        if (!this.selectedFile || !this.elements.usageType?.value) {
            this.showToast('error', 'ファイルと用途を選択してください');
            return;
        }
        
        try {
            // UI状態変更
            this.showSection('processing');
            this.updateProgress(0, 'ファイルをアップロード中...');
            this.updateStep(1, 'active');
            
            // ジョブ作成API呼び出し
            const formData = new FormData();
            formData.append('file', this.selectedFile);
            formData.append('usage_type', this.elements.usageType.value);
            
            const response = await fetch('/api/v1/transcriptions', {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.message || `HTTP ${response.status}: ${response.statusText}`);
            }
            
            const jobData = await response.json();
            this.currentJobId = jobData.id;
            
            // 処理状況の監視開始
            this.updateProgress(20, 'ジョブを開始しました');
            this.updateStep(1, 'completed');
            this.updateStep(2, 'active');
            
            this.startProgressMonitoring();
            
        } catch (error) {
            console.error('処理開始エラー:', error);
            this.showError(`処理の開始に失敗しました: ${error.message}`);
        }
    }
    
    /**
     * 処理状況監視開始
     */
    startProgressMonitoring() {
        if (this.processingInterval) {
            clearInterval(this.processingInterval);
        }
        
        this.processingInterval = setInterval(() => {
            this.checkJobStatus();
        }, 2000); // 2秒間隔で状況確認
        
        // 初回実行
        this.checkJobStatus();
    }
    
    /**
     * ジョブ状況確認
     */
    async checkJobStatus() {
        if (!this.currentJobId) return;
        
        try {
            const response = await fetch(`/api/v1/transcriptions/${this.currentJobId}`);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const jobData = await response.json();
            this.handleJobStatusUpdate(jobData);
            
        } catch (error) {
            console.error('状況確認エラー:', error);
            // 最大3回のリトライ後にエラー表示
            this.retryCount = (this.retryCount || 0) + 1;
            if (this.retryCount >= 3) {
                this.showError(`処理状況の確認に失敗しました: ${error.message}`);
                this.stopProgressMonitoring();
            }
        }
    }
    
    /**
     * ジョブ状況更新処理
     */
    handleJobStatusUpdate(jobData) {
        const status = jobData.status_code;
        const progress = jobData.progress || 0;
        const message = jobData.message || '';
        
        this.updateProgress(progress, message);
        
        switch (status) {
            case 'uploading':
                this.updateStep(1, 'active');
                break;
                
            case 'processing':
                this.updateStep(1, 'completed');
                this.updateStep(2, 'active');
                break;
                
            case 'summarizing':
                this.updateStep(1, 'completed');
                this.updateStep(2, 'completed');
                this.updateStep(3, 'active');
                break;
                
            case 'completed':
                this.handleProcessingCompleted(jobData);
                break;
                
            case 'error':
                this.showError(jobData.error_message || '処理中にエラーが発生しました');
                break;
        }
    }
    
    /**
     * 処理完了処理
     */
    async handleProcessingCompleted(jobData) {
        this.stopProgressMonitoring();
        
        // 最終ステップを完了状態に
        this.updateStep(1, 'completed');
        this.updateStep(2, 'completed');
        this.updateStep(3, 'completed');
        this.updateProgress(100, '処理が完了しました！');
        
        try {
            // 結果データを取得して表示
            await this.loadAndDisplayResults();
            this.showSection('results');
            this.showToast('success', '転写・要約が完了しました！');
            
        } catch (error) {
            console.error('結果表示エラー:', error);
            this.showError(`結果の表示に失敗しました: ${error.message}`);
        }
    }
    
    /**
     * 結果データの読み込みと表示
     */
    async loadAndDisplayResults() {
        if (!this.currentJobId) return;
        
        try {
            // 転写結果を取得
            const jobResponse = await fetch(`/api/v1/transcriptions/${this.currentJobId}`);
            const jobData = await jobResponse.json();
            
            // 転写結果表示
            if (jobData.transcription_result) {
                this.displayTranscriptionResult(jobData.transcription_result, jobData);
            }
            
            // 要約結果取得・表示
            try {
                const summaryResponse = await fetch(`/api/v1/transcriptions/${this.currentJobId}/summary`);
                if (summaryResponse.ok) {
                    const summaryData = await summaryResponse.json();
                    this.displaySummaryResult(summaryData);
                }
            } catch (summaryError) {
                console.warn('要約取得エラー:', summaryError);
            }
            
        } catch (error) {
            throw new Error(`結果データの取得に失敗: ${error.message}`);
        }
    }
    
    /**
     * 転写結果表示
     */
    displayTranscriptionResult(transcriptionData, jobData) {
        // メタデータ更新
        if (this.elements.processingTime) {
            this.elements.processingTime.textContent = this.formatProcessingTime(transcriptionData.processing_time_seconds);
        }
        if (this.elements.audioDuration) {
            this.elements.audioDuration.textContent = this.formatDuration(transcriptionData.duration_seconds);
        }
        if (this.elements.detectedLanguage) {
            this.elements.detectedLanguage.textContent = transcriptionData.language || '日本語';
        }
        if (this.elements.confidence) {
            this.elements.confidence.textContent = `${Math.round((transcriptionData.confidence || 0) * 100)}%`;
        }
        
        // 転写テキスト表示
        if (this.elements.transcriptionText) {
            this.elements.transcriptionText.textContent = transcriptionData.text || '転写結果がありません。';
        }
    }
    
    /**
     * 要約結果表示
     */
    displaySummaryResult(summaryData) {
        // メタデータ更新
        if (this.elements.summaryType) {
            this.elements.summaryType.textContent = this.getSummaryTypeLabel(summaryData.type);
        }
        if (this.elements.aiModel) {
            this.elements.aiModel.textContent = summaryData.model_used || 'llama2:7b';
        }
        if (this.elements.summaryConfidence) {
            this.elements.summaryConfidence.textContent = `${Math.round((summaryData.confidence || 0) * 100)}%`;
        }
        
        // 要約テキスト表示
        if (this.elements.summaryText) {
            this.elements.summaryText.innerHTML = this.formatSummaryText(summaryData.formatted_text);
        }
    }
    
    /**
     * 処理キャンセル
     */
    async cancelProcessing() {
        if (!this.currentJobId) return;
        
        try {
            // キャンセル処理
            this.stopProgressMonitoring();
            this.resetToUploadState();
            this.showToast('info', '処理をキャンセルしました');
            
        } catch (error) {
            console.error('キャンセルエラー:', error);
        }
    }
    
    /**
     * 処理再試行
     */
    async retryProcessing() {
        if (this.selectedFile && this.elements.usageType?.value) {
            await this.startProcessing();
        } else {
            this.resetToUploadState();
        }
    }
    
    /**
     * 進捗更新
     */
    updateProgress(percentage, message) {
        if (this.elements.progressBarFill) {
            this.elements.progressBarFill.style.width = `${percentage}%`;
            this.elements.progressBarFill.setAttribute('aria-valuenow', percentage.toString());
        }
        if (this.elements.progressText) {
            this.elements.progressText.textContent = `${percentage}%`;
        }
        
        if (message && this.elements.currentStatus) {
            this.elements.currentStatus.textContent = message;
        }
    }
    
    /**
     * ステップ状態更新
     */
    updateStep(stepNumber, state) {
        const step = this.elements[`step${stepNumber}`];
        if (!step) return;
        
        // 既存の状態クラスを削除
        step.classList.remove('step--active', 'step--completed');
        
        // 新しい状態クラスを追加
        if (state === 'active') {
            step.classList.add('step--active');
        } else if (state === 'completed') {
            step.classList.add('step--completed');
        }
    }
    
    /**
     * セクション表示切り替え
     */
    showSection(sectionName) {
        // すべてのセクションを非表示
        ['uploadSection', 'processingSection', 'resultsSection', 'errorSection'].forEach(section => {
            if (this.elements[section]) {
                this.elements[section].style.display = 'none';
            }
        });
        
        // 指定されたセクションを表示
        const targetSection = this.elements[sectionName];
        if (targetSection) {
            targetSection.style.display = 'block';
            targetSection.classList.add('fade-in');
        }
    }
    
    /**
     * エラー表示
     */
    showError(message) {
        this.stopProgressMonitoring();
        if (this.elements.errorMessage) {
            this.elements.errorMessage.textContent = message;
        }
        this.showSection('errorSection');
    }
    
    /**
     * アップロード状態にリセット
     */
    resetToUploadState() {
        this.stopProgressMonitoring();
        this.currentJobId = null;
        this.removeSelectedFile();
        if (this.elements.usageType) this.elements.usageType.value = '';
        this.showSection('uploadSection');
        this.updateProcessButtonState();
    }
    
    /**
     * 進捗監視停止
     */
    stopProgressMonitoring() {
        if (this.processingInterval) {
            clearInterval(this.processingInterval);
            this.processingInterval = null;
        }
        this.retryCount = 0;
    }
    
    /**
     * タブ切り替え
     */
    switchTab(tabName) {
        // タブボタンの状態更新
        document.querySelectorAll('.tab-nav__item').forEach(tab => {
            tab.classList.remove('tab-nav__item--active');
            tab.setAttribute('aria-selected', 'false');
        });
        
        // パネルの表示切り替え
        document.querySelectorAll('.tab-panel').forEach(panel => {
            panel.classList.remove('tab-panel--active');
            panel.hidden = true;
        });
        
        // アクティブタブとパネルの設定
        const activeTab = this.elements[`${tabName}Tab`];
        const activePanel = this.elements[`${tabName}Panel`];
        
        if (activeTab && activePanel) {
            activeTab.classList.add('tab-nav__item--active');
            activeTab.setAttribute('aria-selected', 'true');
            activePanel.classList.add('tab-panel--active');
            activePanel.hidden = false;
        }
    }
    
    /**
     * ダウンロードボタンの設定
     */
    setupDownloadButtons() {
        const downloadButtons = [
            { id: 'downloadTranscriptionTxt', endpoint: 'transcription/txt' },
            { id: 'downloadTranscriptionJson', endpoint: 'transcription/json' },
            { id: 'downloadSummaryTxt', endpoint: 'summary/txt' },
            { id: 'downloadSummaryJson', endpoint: 'summary/json' },
            { id: 'downloadAllBtn', endpoint: 'export?format=json' }
        ];
        
        downloadButtons.forEach(({ id, endpoint }) => {
            const button = this.elements[id];
            if (button) {
                button.addEventListener('click', () => this.downloadFile(endpoint));
            }
        });
    }
    
    /**
     * コピーボタンの設定
     */
    setupCopyButtons() {
        if (this.elements.copyTranscriptionText) {
            this.elements.copyTranscriptionText.addEventListener('click', () => {
                this.copyToClipboard(this.elements.transcriptionText?.textContent || '');
            });
        }
        
        if (this.elements.copySummaryText) {
            this.elements.copySummaryText.addEventListener('click', () => {
                this.copyToClipboard(this.elements.summaryText?.textContent || '');
            });
        }
    }
    
    /**
     * ファイルダウンロード
     */
    async downloadFile(endpoint) {
        if (!this.currentJobId) return;
        
        try {
            const response = await fetch(`/api/v1/files/${this.currentJobId}/${endpoint}`);
            
            if (!response.ok) {
                throw new Error(`ダウンロードに失敗しました: HTTP ${response.status}`);
            }
            
            const blob = await response.blob();
            const filename = this.getFilenameFromResponse(response) || 'download.txt';
            
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
            
            this.showToast('success', 'ファイルをダウンロードしました');
            
        } catch (error) {
            console.error('ダウンロードエラー:', error);
            this.showToast('error', `ダウンロードに失敗しました: ${error.message}`);
        }
    }
    
    /**
     * クリップボードにコピー
     */
    async copyToClipboard(text) {
        try {
            if (navigator.clipboard && window.isSecureContext) {
                await navigator.clipboard.writeText(text);
            } else {
                // フォールバック実装
                const textArea = document.createElement('textarea');
                textArea.value = text;
                textArea.style.position = 'fixed';
                textArea.style.opacity = '0';
                document.body.appendChild(textArea);
                textArea.focus();
                textArea.select();
                document.execCommand('copy');
                document.body.removeChild(textArea);
            }
            
            this.showToast('success', 'クリップボードにコピーしました');
            
        } catch (error) {
            console.error('コピーエラー:', error);
            this.showToast('error', 'コピーに失敗しました');
        }
    }
    
    /**
     * トースト通知表示
     */
    showToast(type, message, duration = 5000) {
        const toast = document.createElement('div');
        toast.className = `toast toast--${type}`;
        toast.innerHTML = `
            <div class="toast__content">
                <i class="fas ${this.getToastIcon(type)}" aria-hidden="true"></i>
                <span>${message}</span>
            </div>
        `;
        
        if (this.elements.toastContainer) {
            this.elements.toastContainer.appendChild(toast);
        }
        
        // アニメーション
        setTimeout(() => toast.classList.add('toast--show'), 100);
        
        // 自動削除
        setTimeout(() => {
            toast.classList.remove('toast--show');
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.parentNode.removeChild(toast);
                }
            }, 300);
        }, duration);
    }
    
    /**
     * ユーティリティ関数群
     */
    
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    formatDuration(seconds) {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);
        
        if (hours > 0) {
            return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        } else {
            return `${minutes}:${secs.toString().padStart(2, '0')}`;
        }
    }
    
    formatProcessingTime(seconds) {
        if (seconds < 60) {
            return `${Math.round(seconds)}秒`;
        } else {
            return `${Math.round(seconds / 60)}分${Math.round(seconds % 60)}秒`;
        }
    }
    
    getSummaryTypeLabel(type) {
        const labels = {
            'meeting': '会議',
            'interview': '面接',
            'lecture': '講義',
            'other': 'その他'
        };
        return labels[type] || type;
    }
    
    formatSummaryText(text) {
        if (!text) return '';
        
        // 改行を<br>に変換
        return text.replace(/\n/g, '<br>');
    }
    
    getFilenameFromResponse(response) {
        const contentDisposition = response.headers.get('Content-Disposition');
        if (contentDisposition) {
            const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
            if (filenameMatch && filenameMatch[1]) {
                return filenameMatch[1].replace(/['"]/g, '');
            }
        }
        return null;
    }
    
    getToastIcon(type) {
        const icons = {
            'success': 'fa-check-circle',
            'error': 'fa-exclamation-circle',
            'warning': 'fa-exclamation-triangle',
            'info': 'fa-info-circle'
        };
        return icons[type] || 'fa-info-circle';
    }
}

// DOMコンテンツ読み込み完了後に初期化
document.addEventListener('DOMContentLoaded', () => {
    window.m4aApp = new M4ATranscriptionApp();
});

// エラーハンドリング
window.addEventListener('error', (event) => {
    console.error('グローバルエラー:', event.error);
});

window.addEventListener('unhandledrejection', (event) => {
    console.error('未処理のPromise拒否:', event.reason);
});