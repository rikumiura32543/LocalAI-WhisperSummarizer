/**
 * M4A転写システム - メインJavaScript
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
            this.elements.fileDropArea.addEventListener('click', () => this.elements.fileInput.click());
            this.elements.fileDropArea.addEventListener('dragover', (e) => this.handleDragOver(e));
            this.elements.fileDropArea.addEventListener('dragleave', (e) => this.handleDragLeave(e));
            this.elements.fileDropArea.addEventListener('drop', (e) => this.handleDrop(e));
            
            // キーボードアクセシビリティ
            this.elements.fileDropArea.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    this.elements.fileInput.click();
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
            this.elements.processBtn.addEventListener('click', () => {
                console.log('Process button clicked');
                this.startProcessing();
            });
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
     * APIステータスチェック
     */
    async checkAPIStatus() {
        try {
            const response = await fetch('/api/v1/status');
            const data = await response.json();
            
            if (data.status === 'active') {
                this.showStatus('API接続正常', 'success');
            } else {
                this.showStatus('APIサービスが準備中です', 'info');
            }
        } catch (error) {
            this.showStatus('API接続エラー', 'error');
            console.error('API Status Check Error:', error);
        }
    }

    /**
     * ドラッグオーバー処理
     */
    handleDragOver(e) {
        e.preventDefault();
        e.stopPropagation();
        this.elements.fileDropArea.classList.add('drag-over');
    }
    
    /**
     * ドラッグリーブ処理
     */
    handleDragLeave(e) {
        e.preventDefault();
        e.stopPropagation();
        this.elements.fileDropArea.classList.remove('drag-over');
    }
    
    /**
     * ドロップ処理
     */
    handleDrop(e) {
        e.preventDefault();
        e.stopPropagation();
        this.elements.fileDropArea.classList.remove('drag-over');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            this.handleFileSelection(files[0]);
        }
    }
    
    /**
     * ファイル選択処理
     */
    handleFileSelect(e) {
        const file = e.target.files[0];
        if (file) {
            this.handleFileSelection(file);
        }
    }
    
    /**
     * ファイル選択処理（共通）
     */
    handleFileSelection(file) {
        console.log('handleFileSelection called', { fileName: file.name, fileSize: file.size });
        
        if (this.validateFile(file)) {
            this.selectedFile = file;
            console.log('File selected successfully', { fileName: file.name });
            this.displayFileInfo(file);
            this.updateProcessButtonState();
        } else {
            console.log('File validation failed');
        }
    }
    
    /**
     * ファイル情報表示
     */
    displayFileInfo(file) {
        this.elements.fileName.textContent = file.name;
        this.elements.fileSize.textContent = this.formatFileSize(file.size);
        this.elements.fileInfo.style.display = 'block';
        this.elements.fileDropArea.style.display = 'none';
    }
    
    /**
     * 選択されたファイルを削除
     */
    removeSelectedFile() {
        this.selectedFile = null;
        this.elements.fileInput.value = '';
        this.elements.fileInfo.style.display = 'none';
        this.elements.fileDropArea.style.display = 'block';
        this.updateProcessButtonState();
    }
    
    /**
     * ファイルバリデーション
     */
    validateFile(file) {
        if (!file) {
            this.showToast('ファイルが選択されていません', 'error');
            return false;
        }

        // ファイルサイズチェック（50MB）
        const maxSize = 50 * 1024 * 1024;
        if (file.size > maxSize) {
            this.showToast('ファイルサイズが大きすぎます（最大50MB）', 'error');
            return false;
        }

        // ファイル形式チェック
        const allowedTypes = ['audio/m4a', 'audio/mp4', 'audio/wav', 'audio/mp3', 'audio/mpeg'];
        const fileName = file.name.toLowerCase();
        const allowedExtensions = ['.m4a', '.mp4', '.wav', '.mp3'];
        
        const hasValidType = allowedTypes.includes(file.type);
        const hasValidExtension = allowedExtensions.some(ext => fileName.endsWith(ext));
        
        if (!hasValidType && !hasValidExtension) {
            this.showToast('対応していないファイル形式です（M4A、MP4、WAV、MP3のみ）', 'error');
            return false;
        }

        return true;
    }

    /**
     * 処理開始ボタンの状態更新
     */
    updateProcessButtonState() {
        const hasFile = this.selectedFile !== null;
        const hasUsageType = this.elements.usageType.value !== '';
        
        console.log('updateProcessButtonState', { 
            hasFile, 
            hasUsageType, 
            usageTypeValue: this.elements.usageType.value,
            disabled: !(hasFile && hasUsageType)
        });
        
        this.elements.processBtn.disabled = !(hasFile && hasUsageType);
    }
    
    /**
     * 処理開始
     */
    async startProcessing() {
        console.log('startProcessing called', { 
            selectedFile: this.selectedFile, 
            usageType: this.elements.usageType.value 
        });
        
        if (!this.selectedFile || !this.elements.usageType.value) {
            console.log('Missing file or usage type');
            this.showToast('ファイルと用途を選択してください', 'error');
            return;
        }
        
        try {
            // UI状態を処理中に変更
            this.showProcessingSection();
            this.hideUploadSection();
            
            // ファイルアップロードと処理開始
            console.log('📤 Uploading file...');
            try {
                const jobId = await this.uploadFile();
                console.log('📤 Upload result:', jobId);
                if (jobId) {
                    this.currentJobId = jobId;
                    console.log('✅ Job ID set, starting monitoring...');
                    this.startProgressMonitoring();
                } else {
                    console.error('❌ No job ID received from upload');
                    this.showError('アップロードに失敗しました', 'ジョブIDを取得できませんでした');
                }
            } catch (uploadError) {
                console.error('❌ Upload error:', uploadError);
                this.showError('アップロードエラー', uploadError.message);
                return;
            }
            
        } catch (error) {
            console.error('Processing Error:', error);
            this.showError('処理開始中にエラーが発生しました', error.message);
        }
    }
    
    /**
     * ファイルアップロード
     */
    async uploadFile() {
        const formData = new FormData();
        formData.append('file', this.selectedFile);
        formData.append('usage_type', this.elements.usageType.value);
        
        console.log('📤 Sending POST request to /api/v1/transcriptions');
        const response = await fetch('/api/v1/transcriptions', {
            method: 'POST',
            body: formData
        });
        
        console.log('📡 Upload response status:', response.status);
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: response.statusText }));
            console.error('❌ Upload failed:', errorData);
            throw new Error(errorData.detail || 'アップロードに失敗しました');
        }
        
        const result = await response.json();
        console.log('📊 Upload response data:', result);
        
        // APIからはresult.idでジョブIDが返される
        const jobId = result.id;
        console.log('🆔 Extracted job ID:', jobId);
        return jobId;
    }

    /**
     * 処理キャンセル
     */
    async cancelProcessing() {
        if (!this.currentJobId) return;
        
        try {
            const response = await fetch(`/api/v1/transcriptions/${this.currentJobId}`, {
                method: 'DELETE'
            });
            
            if (response.ok) {
                this.stopProgressMonitoring();
                this.resetToUploadState();
                this.showToast('処理をキャンセルしました', 'info');
            }
        } catch (error) {
            console.error('Cancel Error:', error);
            this.showToast('キャンセル処理に失敗しました', 'error');
        }
    }
    
    /**
     * 進捗監視開始
     */
    startProgressMonitoring() {
        console.log('🚀 Progress monitoring started for job:', this.currentJobId);
        this.processingInterval = setInterval(async () => {
            console.log('⏰ Checking status for job:', this.currentJobId);
            await this.checkProcessingStatus();
        }, 2000); // 2秒間隔
        
        // 初回チェック
        console.log('📋 Initial status check for job:', this.currentJobId);
        this.checkProcessingStatus();
    }
    
    /**
     * 進捗監視停止
     */
    stopProgressMonitoring() {
        if (this.processingInterval) {
            clearInterval(this.processingInterval);
            this.processingInterval = null;
        }
    }
    
    /**
     * 処理状況チェック
     */
    async checkProcessingStatus() {
        if (!this.currentJobId) {
            console.warn('❌ No currentJobId found, stopping monitoring');
            return;
        }
        
        try {
            console.log('🔍 Fetching job status from:', `/api/v1/transcriptions/${this.currentJobId}`);
            const response = await fetch(`/api/v1/transcriptions/${this.currentJobId}`);
            console.log('📡 API Response status:', response.status);
            
            if (!response.ok) {
                throw new Error(`API request failed with status: ${response.status}`);
            }
            
            const job = await response.json();
            console.log('📊 Received job data:', {
                id: job.id,
                status_code: job.status_code,
                progress: job.progress,
                message: job.message,
                error_message: job.error_message
            });
            
            this.updateProcessingStatus(job);
            
            if (job.status_code === 'completed') {
                console.log('✅ Job completed, stopping monitoring');
                this.stopProgressMonitoring();
                this.showResults(job);
            } else if (job.status_code === 'error' || job.status_code === 'failed') {
                console.log('❌ Job failed, stopping monitoring');
                this.stopProgressMonitoring();
                this.showError('処理に失敗しました', job.error_message || '不明なエラー');
            }
            
        } catch (error) {
            console.error('❌ Status Check Error:', error);
        }
    }

    /**
     * 処理状況の更新
     */
    updateProcessingStatus(job) {
        if (!job) {
            console.warn('❌ No job data provided to updateProcessingStatus');
            return;
        }
        
        // 進行状況バーの更新
        const progress = job.progress || 0;
        console.log('📈 Updating progress bar to:', progress + '%');
        
        if (this.elements.progressBarFill) {
            this.elements.progressBarFill.style.width = `${progress}%`;
            console.log('✅ Progress bar fill updated');
        } else {
            console.warn('❌ Progress bar fill element not found');
        }
        
        if (this.elements.progressText) {
            this.elements.progressText.textContent = `${progress}%`;
            console.log('✅ Progress text updated');
        } else {
            console.warn('❌ Progress text element not found');
        }
        
        // 進行状況バーのaria属性更新
        const progressBar = document.querySelector('.progress-bar');
        if (progressBar) {
            progressBar.setAttribute('aria-valuenow', progress);
        }
        
        // ステータスメッセージの更新
        if (job.message && this.elements.currentStatus) {
            this.elements.currentStatus.textContent = job.message;
            console.log('✅ Status message updated:', job.message);
        }
        
        // ステップインジケーターの更新
        this.updateStepIndicators(job.status_code, progress);
        
        console.log('✅ Processing status updated:', {
            jobId: job.id,
            status: job.status_code,
            progress: progress,
            message: job.message
        });
    }
    
    /**
     * ステップインジケーターの更新
     */
    updateStepIndicators(status, progress) {
        // 全ステップをリセット
        [this.elements.step1, this.elements.step2, this.elements.step3].forEach(step => {
            if (step) {
                step.classList.remove('active', 'completed');
                const spinner = step.querySelector('.step__spinner');
                const check = step.querySelector('.step__check');
                const clock = step.querySelector('.step__clock');
                
                if (spinner) spinner.style.display = 'none';
                if (check) check.style.display = 'none';
                if (clock) clock.style.display = 'none';
            }
        });
        
        // ステップ1: ファイルアップロード（常に完了）
        if (this.elements.step1) {
            this.elements.step1.classList.add('completed');
            const check1 = this.elements.step1.querySelector('.step__check');
            if (check1) check1.style.display = 'inline';
        }
        
        // ステップ2: 音声転写
        if (this.elements.step2) {
            if (status === 'transcribing' || progress < 60) {
                this.elements.step2.classList.add('active');
                const spinner2 = this.elements.step2.querySelector('.step__spinner');
                if (spinner2) spinner2.style.display = 'inline';
            } else if (progress >= 60) {
                this.elements.step2.classList.add('completed');
                const check2 = this.elements.step2.querySelector('.step__check');
                if (check2) check2.style.display = 'inline';
            }
        }
        
        // ステップ3: AI要約生成
        if (this.elements.step3) {
            if (status === 'summarizing' && progress >= 60 && progress < 100) {
                this.elements.step3.classList.add('active');
                const spinner3 = this.elements.step3.querySelector('.step__spinner');
                if (spinner3) spinner3.style.display = 'inline';
            } else if (progress >= 100 || status === 'completed') {
                this.elements.step3.classList.add('completed');
                const check3 = this.elements.step3.querySelector('.step__check');
                if (check3) check3.style.display = 'inline';
            } else {
                const clock3 = this.elements.step3.querySelector('.step__clock');
                if (clock3) clock3.style.display = 'inline';
            }
        }
    }

    /**
     * 読み込み状態の切り替え
     */
    setLoadingState(loading) {
        if (loading) {
            this.uploadBtn.disabled = true;
            this.uploadBtn.classList.add('loading');
        } else {
            this.uploadBtn.disabled = false;
            this.uploadBtn.classList.remove('loading');
        }
    }

    /**
     * ステータスメッセージの表示
     */
    showStatus(message, type) {
        this.statusDiv.textContent = message;
        this.statusDiv.className = 'status-message';
        
        if (message && type) {
            this.statusDiv.classList.add('show', type);
        }
    }

    /**
     * テキストのクリップボードコピー
     */
    async copyToClipboard(elementId) {
        try {
            const element = document.getElementById(elementId);
            const text = element.value || element.textContent;
            
            await navigator.clipboard.writeText(text);
            this.showStatus('クリップボードにコピーしました', 'success');
            
            // 3秒後にメッセージを消去
            setTimeout(() => {
                this.statusDiv.classList.remove('show');
            }, 3000);
        } catch (error) {
            console.error('Copy Error:', error);
            this.showStatus('コピーに失敗しました', 'error');
        }
    }

    /**
     * 要約のクリップボードコピー
     */
    async copySummaryToClipboard() {
        try {
            const overview = document.getElementById('summary-overview').textContent;
            const points = Array.from(document.getElementById('summary-points').children)
                .map(li => `• ${li.textContent}`).join('\n');
            const actions = Array.from(document.getElementById('summary-actions').children)
                .map(li => `• ${li.textContent}`).join('\n');
            
            const summaryText = `【概要】\n${overview}\n\n【主要ポイント】\n${points}\n\n【アクションアイテム】\n${actions}`;
            
            await navigator.clipboard.writeText(summaryText);
            this.showStatus('要約をクリップボードにコピーしました', 'success');
            
            setTimeout(() => {
                this.statusDiv.classList.remove('show');
            }, 3000);
        } catch (error) {
            console.error('Copy Summary Error:', error);
            this.showStatus('要約のコピーに失敗しました', 'error');
        }
    }

    /**
     * 転写結果のダウンロード
     */
    downloadTranscription() {
        const text = document.getElementById('transcription-result').value;
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
        const filename = `transcription_${timestamp}.txt`;
        
        this.downloadTextFile(text, filename);
        this.showStatus('転写ファイルをダウンロードしました', 'success');
    }

    /**
     * 要約結果のダウンロード
     */
    downloadSummary() {
        const overview = document.getElementById('summary-overview').textContent;
        const points = Array.from(document.getElementById('summary-points').children)
            .map(li => `• ${li.textContent}`).join('\n');
        const actions = Array.from(document.getElementById('summary-actions').children)
            .map(li => `• ${li.textContent}`).join('\n');
        
        const summaryText = `【概要】\n${overview}\n\n【主要ポイント】\n${points}\n\n【アクションアイテム】\n${actions}`;
        
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
        const filename = `summary_${timestamp}.txt`;
        
        this.downloadTextFile(summaryText, filename);
        this.showStatus('要約ファイルをダウンロードしました', 'success');
    }

    /**
     * テキストファイルのダウンロード
     */
    downloadTextFile(content, filename) {
        const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        
        URL.revokeObjectURL(url);
    }

    /**
     * ファイルサイズのフォーマット
     */
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    /**
     * ダウンロードボタンのセットアップ
     */
    setupDownloadButtons() {
        // 転写結果ダウンロード
        if (this.elements.downloadTranscriptionTxt) {
            this.elements.downloadTranscriptionTxt.addEventListener('click', () => this.downloadTranscriptionTxt());
        }
        if (this.elements.downloadTranscriptionJson) {
            this.elements.downloadTranscriptionJson.addEventListener('click', () => this.downloadTranscriptionJson());
        }
        
        // 要約結果ダウンロード
        if (this.elements.downloadSummaryTxt) {
            this.elements.downloadSummaryTxt.addEventListener('click', () => this.downloadSummaryTxt());
        }
        if (this.elements.downloadSummaryJson) {
            this.elements.downloadSummaryJson.addEventListener('click', () => this.downloadSummaryJson());
        }
        
        // 全データダウンロード
        if (this.elements.downloadAllBtn) {
            this.elements.downloadAllBtn.addEventListener('click', () => this.downloadAll());
        }
    }
    
    /**
     * コピーボタンのセットアップ
     */
    setupCopyButtons() {
        if (this.elements.copyTranscriptionText) {
            this.elements.copyTranscriptionText.addEventListener('click', () => this.copyTranscriptionText());
        }
        if (this.elements.copySummaryText) {
            this.elements.copySummaryText.addEventListener('click', () => this.copySummaryText());
        }
    }
    
    /**
     * 転写結果テキストダウンロード
     */
    async downloadTranscriptionTxt() {
        if (!this.currentJobId) return;
        
        try {
            const response = await fetch(`/api/v1/files/${this.currentJobId}/transcription.txt`);
            if (!response.ok) throw new Error('ダウンロードに失敗しました');
            
            const text = await response.text();
            const filename = `transcription_${this.currentJobId}_${this.getTimestamp()}.txt`;
            this.downloadTextFile(text, filename);
            this.showToast('転写テキストをダウンロードしました', 'success');
        } catch (error) {
            console.error('Download Error:', error);
            this.showToast('ダウンロードに失敗しました', 'error');
        }
    }
    
    /**
     * 転写結果JSONダウンロード
     */
    async downloadTranscriptionJson() {
        if (!this.currentJobId) return;
        
        try {
            const response = await fetch(`/api/v1/files/${this.currentJobId}/transcription.json`);
            if (!response.ok) throw new Error('ダウンロードに失敗しました');
            
            const jsonText = await response.text();
            const filename = `transcription_${this.currentJobId}_${this.getTimestamp()}.json`;
            this.downloadTextFile(jsonText, filename);
            this.showToast('転写JSONをダウンロードしました', 'success');
        } catch (error) {
            console.error('Download Error:', error);
            this.showToast('ダウンロードに失敗しました', 'error');
        }
    }
    
    /**
     * 要約結果テキストダウンロード
     */
    async downloadSummaryTxt() {
        if (!this.currentJobId) return;
        
        try {
            const response = await fetch(`/api/v1/files/${this.currentJobId}/summary.txt`);
            if (!response.ok) throw new Error('ダウンロードに失敗しました');
            
            const text = await response.text();
            const filename = `summary_${this.currentJobId}_${this.getTimestamp()}.txt`;
            this.downloadTextFile(text, filename);
            this.showToast('要約テキストをダウンロードしました', 'success');
        } catch (error) {
            console.error('Download Error:', error);
            this.showToast('ダウンロードに失敗しました', 'error');
        }
    }
    
    /**
     * 要約結果JSONダウンロード
     */
    async downloadSummaryJson() {
        if (!this.currentJobId) return;
        
        try {
            const response = await fetch(`/api/v1/files/${this.currentJobId}/summary.json`);
            if (!response.ok) throw new Error('ダウンロードに失敗しました');
            
            const jsonText = await response.text();
            const filename = `summary_${this.currentJobId}_${this.getTimestamp()}.json`;
            this.downloadTextFile(jsonText, filename);
            this.showToast('要約JSONをダウンロードしました', 'success');
        } catch (error) {
            console.error('Download Error:', error);
            this.showToast('ダウンロードに失敗しました', 'error');
        }
    }
    
    /**
     * 全データダウンロード
     */
    async downloadAll() {
        if (!this.currentJobId) return;
        
        try {
            const response = await fetch(`/api/v1/files/${this.currentJobId}/export`);
            if (!response.ok) throw new Error('ダウンロードに失敗しました');
            
            const blob = await response.blob();
            const filename = `m4a_transcription_${this.currentJobId}_${this.getTimestamp()}.zip`;
            
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            
            this.showToast('全データをダウンロードしました', 'success');
        } catch (error) {
            console.error('Download All Error:', error);
            this.showToast('ダウンロードに失敗しました', 'error');
        }
    }
    
    /**
     * 転写テキストコピー
     */
    async copyTranscriptionText() {
        try {
            const text = this.elements.transcriptionText.textContent;
            if (!text) {
                this.showToast('コピーするテキストがありません', 'warning');
                return;
            }
            
            await navigator.clipboard.writeText(text);
            this.showToast('転写テキストをコピーしました', 'success');
        } catch (error) {
            console.error('Copy Error:', error);
            this.showToast('コピーに失敗しました', 'error');
        }
    }
    
    /**
     * 要約テキストコピー
     */
    async copySummaryText() {
        try {
            const summaryElement = this.elements.summaryText;
            let text = '';
            
            // HTML内のテキストを整理して取得
            const sections = summaryElement.querySelectorAll('.summary-section');
            if (sections.length > 0) {
                sections.forEach(section => {
                    const title = section.querySelector('h4');
                    const content = section.querySelector('p, ul');
                    
                    if (title) text += `【${title.textContent}】\n`;
                    if (content) {
                        if (content.tagName === 'UL') {
                            const items = content.querySelectorAll('li');
                            items.forEach(item => {
                                text += `• ${item.textContent}\n`;
                            });
                        } else {
                            text += `${content.textContent}\n`;
                        }
                    }
                    text += '\n';
                });
            } else {
                text = summaryElement.textContent;
            }
            
            if (!text.trim()) {
                this.showToast('コピーするテキストがありません', 'warning');
                return;
            }
            
            await navigator.clipboard.writeText(text.trim());
            this.showToast('要約テキストをコピーしました', 'success');
        } catch (error) {
            console.error('Copy Summary Error:', error);
            this.showToast('コピーに失敗しました', 'error');
        }
    }
    
    /**
     * 処理セクションを表示
     */
    showProcessingSection() {
        this.elements.processingSection.style.display = 'block';
        this.elements.resultsSection.style.display = 'none';
        this.elements.errorSection.style.display = 'none';
    }

    /**
     * アップロードセクションを非表示
     */
    hideUploadSection() {
        this.elements.uploadSection.style.display = 'none';
    }

    /**
     * アップロードセクションを表示
     */
    showUploadSection() {
        this.elements.uploadSection.style.display = 'block';
    }

    /**
     * 結果セクションを表示
     */
    showResultsSection() {
        this.elements.resultsSection.style.display = 'block';
        this.elements.processingSection.style.display = 'none';
        this.elements.errorSection.style.display = 'none';
    }

    /**
     * 処理完了時に結果を表示
     */
    async showResults(job) {
        try {
            console.log('📋 Showing results for job:', job.id);
            
            // 結果セクションを表示
            this.showResultsSection();
            
            // 詳細結果を取得
            const response = await fetch(`/api/v1/transcriptions/${job.id}`);
            if (!response.ok) {
                throw new Error(`結果取得エラー: ${response.status}`);
            }
            
            const resultData = await response.json();
            console.log('📊 Result data received:', resultData);
            
            // 結果をUIに表示
            this.displayResults(resultData);
            
            // 成功トースト表示
            this.showToast('処理が完了しました！', 'success');
            
        } catch (error) {
            console.error('❌ Error showing results:', error);
            this.showError('結果表示エラー', error.message);
        }
    }

    /**
     * 結果データをUIに表示
     */
    async displayResults(jobData) {
        if (!jobData) {
            console.warn('❌ No job data to display');
            return;
        }
        
        // 結果セクション内のコンテンツを直接更新
        const resultsSection = this.elements.resultsSection;
        if (!resultsSection) {
            console.warn('❌ Results section not found');
            return;
        }
        
        // 処理時間計算
        const processingTime = jobData.processing_completed_at && jobData.processing_started_at 
            ? (new Date(jobData.processing_completed_at) - new Date(jobData.processing_started_at)) / 1000
            : 0;
        
        // 転写結果の表示準備
        let transcriptionText = '転写結果なし';
        if (jobData.transcription_result && jobData.transcription_result.text) {
            transcriptionText = jobData.transcription_result.text;
        }
        
        // AI要約を取得
        let summaryText = null;
        let summaryAvailable = false;
        
        try {
            const summaryResponse = await fetch(`/api/v1/transcriptions/${jobData.id}/summary`);
            if (summaryResponse.ok) {
                const summaryData = await summaryResponse.json();
                console.log('要約データ受信:', summaryData);
                
                // APIレスポンス構造に合わせて修正
                if (summaryData.formatted_text) {
                    summaryText = summaryData.formatted_text;
                    summaryAvailable = true;
                } else if (summaryData.ai_summary && summaryData.ai_summary.formatted_text) {
                    summaryText = summaryData.ai_summary.formatted_text;
                    summaryAvailable = true;
                } else {
                    console.log('要約データがまだ生成されていません');
                }
            } else if (summaryResponse.status === 404) {
                console.log('要約がまだ生成されていません (404)');
            }
        } catch (error) {
            console.warn('要約データの取得に失敗:', error);
        }
        
        // 音声書き起こしテキストを整形（句読点・改行追加）
        const formattedTranscription = this.formatTranscriptionText(transcriptionText);
        
        // 要約が利用できない場合は待機してから再表示
        if (!summaryAvailable) {
            this.displayResultsWithPendingSummary(jobData, formattedTranscription);
            this.waitForSummaryAndUpdate(jobData.id);
            return;
        }
        
        // AI要約をマークダウン形式に整形
        const formattedSummary = this.formatSummaryText(summaryText);
        
        // 結果を縦並びで表示（AI要約 → 音声書き起こし の順）
        resultsSection.innerHTML = `
            <div class="results-content">
                <div class="result-header">
                    <h2>処理完了</h2>
                    <div class="metadata-info">
                        <p><strong>ファイル名:</strong> ${jobData.original_filename || 'N/A'}</p>
                        <p><strong>処理時間:</strong> ${processingTime.toFixed(1)}秒</p>
                        <p><strong>音声長:</strong> ${jobData.audio_file?.duration_seconds?.toFixed(1) || 0}秒</p>
                    </div>
                </div>
                
                <div class="summary-section">
                    <div class="section-header">
                        <h3>AI要約</h3>
                        <button class="btn btn-sm btn-outline" onclick="window.m4aApp.downloadSummary('${jobData.id}')">
                            要約をダウンロード
                        </button>
                    </div>
                    <div class="result-box summary-box">
                        <div class="markdown-content">${formattedSummary}</div>
                    </div>
                </div>
                
                <div class="transcription-section">
                    <div class="section-header">
                        <h3>音声書き起こし</h3>
                        <button class="btn btn-sm btn-outline" onclick="window.m4aApp.downloadTranscription('${jobData.id}')">
                            書き起こしをダウンロード
                        </button>
                    </div>
                    <div class="result-box transcription-box">
                        <pre>${formattedTranscription}</pre>
                    </div>
                </div>
                
                <div class="action-buttons">
                    <button class="btn btn-secondary" onclick="window.m4aApp.resetApp()">
                        新しいファイルを処理
                    </button>
                </div>
            </div>
        `;
    }

    /**
     * 要約が生成中の状態で結果を表示
     */
    displayResultsWithPendingSummary(jobData, formattedTranscription) {
        const resultsSection = this.elements.resultsSection;
        const processingTime = jobData.processing_completed_at && jobData.processing_started_at 
            ? (new Date(jobData.processing_completed_at) - new Date(jobData.processing_started_at)) / 1000
            : 0;
        
        resultsSection.innerHTML = `
            <div class="results-content">
                <div class="result-header">
                    <h2>処理完了</h2>
                    <div class="metadata-info">
                        <p><strong>ファイル名:</strong> ${jobData.original_filename || 'N/A'}</p>
                        <p><strong>処理時間:</strong> ${processingTime.toFixed(1)}秒</p>
                        <p><strong>音声長:</strong> ${jobData.audio_file?.duration_seconds?.toFixed(1) || 0}秒</p>
                    </div>
                </div>
                
                <div class="summary-section">
                    <div class="section-header">
                        <h3>AI要約</h3>
                        <span class="loading-indicator">生成中...</span>
                    </div>
                    <div class="result-box summary-box">
                        <div class="loading-content">
                            <div class="loading-spinner"></div>
                            <p>AI要約を生成しています。しばらくお待ちください...</p>
                        </div>
                    </div>
                </div>
                
                <div class="transcription-section">
                    <div class="section-header">
                        <h3>音声書き起こし</h3>
                        <button class="btn btn-sm btn-outline" onclick="window.m4aApp.downloadTranscription('${jobData.id}')">
                            書き起こしをダウンロード
                        </button>
                    </div>
                    <div class="result-box transcription-box">
                        <pre>${formattedTranscription}</pre>
                    </div>
                </div>
                
                <div class="action-buttons">
                    <button class="btn btn-secondary" onclick="window.m4aApp.resetApp()">
                        新しいファイルを処理
                    </button>
                </div>
            </div>
        `;
    }

    /**
     * 要約生成完了まで待機して結果を更新
     */
    async waitForSummaryAndUpdate(jobId) {
        const maxAttempts = 30; // 最大30回試行（5分間）
        const retryInterval = 10000; // 10秒間隔
        
        for (let attempt = 1; attempt <= maxAttempts; attempt++) {
            console.log(`要約チェック試行 ${attempt}/${maxAttempts}`);
            
            try {
                await new Promise(resolve => setTimeout(resolve, retryInterval));
                
                const summaryResponse = await fetch(`/api/v1/transcriptions/${jobId}/summary`);
                if (summaryResponse.ok) {
                    const summaryData = await summaryResponse.json();
                    let formattedText = null;
                    
                    if (summaryData.formatted_text) {
                        formattedText = summaryData.formatted_text;
                    } else if (summaryData.ai_summary && summaryData.ai_summary.formatted_text) {
                        formattedText = summaryData.ai_summary.formatted_text;
                    }
                    
                    if (formattedText) {
                        console.log('✅ AI要約生成完了！');
                        this.updateSummarySection(formattedText, jobId);
                        return;
                    }
                }
            } catch (error) {
                console.warn(`要約チェック失敗 (試行 ${attempt}):`, error);
            }
        }
        
        // タイムアウト時の処理
        console.warn('⚠️ AI要約生成がタイムアウトしました');
        this.updateSummarySection('要約生成がタイムアウトしました。後ほど再度お試しください。', jobId, true);
    }

    /**
     * 要約セクションのみを更新
     */
    updateSummarySection(summaryText, jobId, isError = false) {
        const summarySection = document.querySelector('.summary-section');
        if (!summarySection) return;
        
        const formattedSummary = isError ? `<p class="error-text">${summaryText}</p>` : this.formatSummaryText(summaryText);
        
        summarySection.innerHTML = `
            <div class="section-header">
                <h3>AI要約</h3>
                ${isError ? '' : `<button class="btn btn-sm btn-outline" onclick="window.m4aApp.downloadSummary('${jobId}')">要約をダウンロード</button>`}
            </div>
            <div class="result-box summary-box">
                <div class="markdown-content">${formattedSummary}</div>
            </div>
        `;
    }

    /**
     * アプリをリセットして最初の画面に戻る
     */
    resetApp() {
        // プログレスをリセット
        this.currentJobId = null;
        this.stopProgressMonitoring();
        
        // UI表示をリセット
        this.showUploadSection();
        this.elements.processingSection.style.display = 'none';
        this.elements.resultsSection.style.display = 'none';
        this.elements.errorSection.style.display = 'none';
        
        // ファイル入力をリセット
        const fileInput = document.getElementById('audio-file');
        if (fileInput) {
            fileInput.value = '';
        }
        
        console.log('🔄 App reset completed');
    }

    /**
     * 音声書き起こしテキストを整形（句読点・改行追加）
     */
    formatTranscriptionText(text) {
        if (!text || text === '転写結果なし') {
            return 'テキストが取得できませんでした。';
        }
        
        // 基本的な句読点と改行の追加
        let formatted = text
            // 文末に句読点を追加
            .replace(/([。！？])(\s*)([あ-んア-ンa-zA-Z])/g, '$1\n$3')
            // 長い文章を適度に区切る
            .replace(/([、])(\s*)([あ-んア-ンa-zA-Z])/g, '$1 $3')
            // 連続する空白を整理
            .replace(/\s+/g, ' ')
            // 改行を整理
            .replace(/\n\s*\n/g, '\n\n');
        
        return formatted.trim();
    }

    /**
     * AI要約をマークダウン形式に整形
     */
    formatSummaryText(text) {
        if (!text || text === '要約結果なし' || text === '要約データを取得できませんでした') {
            return `
                <h2>📋 概要</h2>
                <p>要約情報を生成中です...</p>
                
                <h2>📋 アクションプラン</h2>
                <p>処理が完了次第、こちらに表示されます。</p>
                
                <h2>📋 議事内容詳細</h2>
                <p>詳細な議事内容は処理完了後に表示されます。</p>
            `;
        }
        
        // マークダウン形式に変換
        let formatted = text
            // ## 見出しをHTMLに変換
            .replace(/^## (.+)$/gm, '<h2>$1</h2>')
            // ### 見出しをHTMLに変換  
            .replace(/^### (.+)$/gm, '<h3>$1</h3>')
            // **太字**をHTMLに変換
            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
            // *斜体*をHTMLに変換
            .replace(/\*(.+?)\*/g, '<em>$1</em>')
            // 改行をHTMLに変換
            .replace(/\n\n/g, '</p><p>')
            .replace(/\n/g, '<br>');
        
        // セクション構造を確保
        if (!formatted.includes('概要') && !formatted.includes('アクションプラン') && !formatted.includes('議事内容')) {
            formatted = `
                <h2>📋 概要</h2>
                <p>${formatted}</p>
                
                <h2>📋 アクションプラン</h2>
                <p>追加のアクションプランは検討中です。</p>
                
                <h2>📋 議事内容詳細</h2>
                <p>詳細な内容については上記概要をご参照ください。</p>
            `;
        }
        
        return formatted;
    }

    /**
     * AI要約をダウンロード
     */
    downloadSummary(jobId) {
        console.log('📥 Download summary for job:', jobId);
        const summaryElement = document.querySelector('.summary-box .markdown-content');
        if (summaryElement) {
            const content = summaryElement.innerText;
            this.downloadTextFile(content, `summary_${jobId}.txt`);
        }
    }

    /**
     * 音声書き起こしをダウンロード
     */
    downloadTranscription(jobId) {
        console.log('📥 Download transcription for job:', jobId);
        const transcriptionElement = document.querySelector('.transcription-box pre');
        if (transcriptionElement) {
            const content = transcriptionElement.innerText;
            this.downloadTextFile(content, `transcription_${jobId}.txt`);
        }
    }

    /**
     * テキストファイルをダウンロード
     */
    downloadTextFile(content, filename) {
        const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    /**
     * タブ切り替え
     */
    switchTab(tabName) {
        // タブボタンの状態を更新
        const allTabs = document.querySelectorAll('.tab-button');
        allTabs.forEach(tab => tab.classList.remove('active'));
        
        if (tabName === 'transcription') {
            this.elements.transcriptionTab.classList.add('active');
            document.getElementById('transcription-content').style.display = 'block';
            document.getElementById('summary-content').style.display = 'none';
        } else if (tabName === 'summary') {
            this.elements.summaryTab.classList.add('active');
            document.getElementById('transcription-content').style.display = 'none';
            document.getElementById('summary-content').style.display = 'block';
        }
    }

    /**
     * エラーセクションを表示
     */
    showError(title, message) {
        this.elements.errorSection.style.display = 'block';
        this.elements.processingSection.style.display = 'none';
        this.elements.resultsSection.style.display = 'none';

        this.elements.errorMessage.innerHTML = `
            <h3>${title}</h3>
            <p>${message}</p>
        `;
    }

    /**
     * トーストメッセージ表示
     */
    showToast(message, type = 'info') {
        console.log('Toast:', { message, type });
        
        const toast = document.createElement('div');
        toast.className = `toast toast--${type}`;
        toast.innerHTML = `
            <div class="toast__content">
                <i class="fas fa-${this.getToastIcon(type)}" aria-hidden="true"></i>
                <span>${message}</span>
            </div>
        `;
        
        this.elements.toastContainer.appendChild(toast);
        
        // アニメーション
        setTimeout(() => toast.classList.add('toast--show'), 100);
        
        // 自動削除
        setTimeout(() => {
            toast.classList.remove('toast--show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    /**
     * トーストアイコン取得
     */
    getToastIcon(type) {
        const icons = {
            success: 'check-circle',
            error: 'exclamation-circle',
            warning: 'exclamation-triangle',
            info: 'info-circle'
        };
        return icons[type] || 'info-circle';
    }

    /**
     * ステータス表示
     */
    showStatus(message, type = 'info') {
        console.log('Status:', { message, type });
        // 簡易実装：トーストで代用
        this.showToast(message, type);
    }

    /**
     * ダウンロードボタンセットアップ
     */
    setupDownloadButtons() {
        console.log('Setting up download buttons');
        // 実装は必要に応じて後で追加
    }

    /**
     * コピーボタンセットアップ
     */
    setupCopyButtons() {
        console.log('Setting up copy buttons');
        // 実装は必要に応じて後で追加
    }

    /**
     * タイムスタンプ生成
     */
    getTimestamp() {
        return new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
    }
}

// アプリケーションの初期化
document.addEventListener('DOMContentLoaded', () => {
    window.m4aApp = new M4ATranscriptionApp();
});