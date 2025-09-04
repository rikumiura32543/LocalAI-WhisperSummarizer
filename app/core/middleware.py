"""
FastAPIミドルウェア実装
"""

import time
import uuid
import hashlib
import secrets
from typing import Callable, Dict, Optional
from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

logger = structlog.get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """リクエストログミドルウェア"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # リクエストID生成
        request_id = str(uuid.uuid4())
        
        # リクエスト開始時間
        start_time = time.time()
        
        # リクエスト情報ログ出力
        logger.info(
            "Request started",
            request_id=request_id,
            method=request.method,
            url=str(request.url),
            client_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent")
        )
        
        # リクエストIDをヘッダーに追加
        request.state.request_id = request_id
        
        try:
            # リクエスト処理実行
            response = await call_next(request)
            
            # レスポンス時間計算
            process_time = time.time() - start_time
            
            # レスポンス情報ログ出力
            logger.info(
                "Request completed",
                request_id=request_id,
                method=request.method,
                url=str(request.url),
                status_code=response.status_code,
                process_time_ms=round(process_time * 1000, 2)
            )
            
            # レスポンスヘッダーに情報追加
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = str(round(process_time * 1000, 2))
            
            return response
            
        except Exception as e:
            # エラー時間計算
            process_time = time.time() - start_time
            
            # エラーログ出力
            logger.error(
                "Request failed",
                request_id=request_id,
                method=request.method,
                url=str(request.url),
                error=str(e),
                error_type=type(e).__name__,
                process_time_ms=round(process_time * 1000, 2)
            )
            
            raise


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """強化されたセキュリティヘッダーミドルウェア"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # 基本セキュリティヘッダー
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # セキュリティヘッダー強化
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        response.headers["X-Download-Options"] = "noopen"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"
        response.headers["Cross-Origin-Resource-Policy"] = "cross-origin"
        
        from app.core.config import settings
        
        # 本番環境でのセキュリティ強化
        if not settings.is_development:
            # HSTS（HTTP Strict Transport Security）
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )
            
            # Content Security Policy（厳格版）
            csp_directives = [
                "default-src 'self'",
                "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://fonts.googleapis.com",
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com",
                "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com",
                "img-src 'self' data: https:",
                "connect-src 'self'",
                "object-src 'none'",
                "base-uri 'self'",
                "form-action 'self'",
                "frame-ancestors 'none'",
                "upgrade-insecure-requests"
            ]
            response.headers["Content-Security-Policy"] = "; ".join(csp_directives)
            
            # セキュリティ関連の追加ヘッダー
            response.headers["Permissions-Policy"] = (
                "camera=(), microphone=(), geolocation=(), "
                "payment=(), usb=(), magnetometer=(), gyroscope=()"
            )
        else:
            # 開発環境用の緩い設定
            csp_directives = [
                "default-src 'self'",
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' https:",
                "style-src 'self' 'unsafe-inline' https:",
                "font-src 'self' https:",
                "img-src 'self' data: https:",
                "connect-src 'self' ws: wss:",
                "object-src 'none'"
            ]
            response.headers["Content-Security-Policy"] = "; ".join(csp_directives)
        
        # API応答のセキュリティ強化
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        
        return response


class AdvancedRateLimitMiddleware(BaseHTTPMiddleware):
    """高機能レート制限ミドルウェア"""
    
    def __init__(
        self,
        app,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        uploads_per_hour: int = 100,
        burst_limit: int = 10,
        burst_window: int = 1,
        block_duration: int = 3600
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.uploads_per_hour = uploads_per_hour
        self.burst_limit = burst_limit
        self.burst_window = burst_window
        self.block_duration = block_duration
        
        # クライアント情報保存
        self.clients = {}
        self.blocked_clients = {}
        self.suspicious_activity = {}
    
    def _get_client_ip(self, request: Request) -> str:
        """プロキシ対応のクライアントIP取得"""
        # プロキシヘッダーチェック
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
            
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()
            
        return request.client.host if request.client else "unknown"
    
    def _clean_old_requests(self, client_data: Dict, current_time: float):
        """古いリクエストデータをクリーンアップ"""
        # 1分以内のリクエスト
        client_data["minute_requests"] = [
            req_time for req_time in client_data.get("minute_requests", [])
            if current_time - req_time < 60
        ]
        
        # 1時間以内のリクエスト
        client_data["hour_requests"] = [
            req_time for req_time in client_data.get("hour_requests", [])
            if current_time - req_time < 3600
        ]
        
        # 1時間以内のアップロード
        client_data["hour_uploads"] = [
            req_time for req_time in client_data.get("hour_uploads", [])
            if current_time - req_time < 3600
        ]
        
        # バーストウィンドウ内のリクエスト
        client_data["burst_requests"] = [
            req_time for req_time in client_data.get("burst_requests", [])
            if current_time - req_time < self.burst_window
        ]
    
    def _is_upload_request(self, request: Request) -> bool:
        """アップロードリクエストかどうか判定"""
        if request.method != "POST":
            return False
            
        content_type = request.headers.get("content-type", "")
        return (
            "/transcriptions" in str(request.url.path) and
            "multipart/form-data" in content_type
        )
    
    def _check_suspicious_activity(self, client_ip: str, current_time: float) -> bool:
        """不審な活動パターンを検出"""
        if client_ip not in self.suspicious_activity:
            self.suspicious_activity[client_ip] = {
                "rapid_requests": [],
                "error_count": 0,
                "large_requests": 0,
                "last_reset": current_time
            }
        
        activity = self.suspicious_activity[client_ip]
        
        # 1時間ごとにリセット
        if current_time - activity["last_reset"] > 3600:
            activity.update({
                "rapid_requests": [],
                "error_count": 0,
                "large_requests": 0,
                "last_reset": current_time
            })
        
        # 急速なリクエスト履歴をクリーンアップ
        activity["rapid_requests"] = [
            req_time for req_time in activity["rapid_requests"]
            if current_time - req_time < 10
        ]
        
        # 10秒間に20回以上のリクエスト
        if len(activity["rapid_requests"]) >= 20:
            return True
            
        activity["rapid_requests"].append(current_time)
        return False
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_ip = self._get_client_ip(request)
        current_time = time.time()
        
        # ブロックされたクライアントチェック
        if client_ip in self.blocked_clients:
            block_time = self.blocked_clients[client_ip]
            if current_time - block_time < self.block_duration:
                logger.warning(
                    "Blocked client access attempt",
                    client_ip=client_ip,
                    remaining_block_time=self.block_duration - (current_time - block_time)
                )
                return Response(
                    content="Access temporarily blocked due to rate limit violations",
                    status_code=429,
                    headers={
                        "Retry-After": str(int(self.block_duration - (current_time - block_time))),
                        "X-Block-Reason": "Rate limit violations"
                    }
                )
            else:
                # ブロック期間終了
                del self.blocked_clients[client_ip]
        
        # クライアントデータ初期化
        if client_ip not in self.clients:
            self.clients[client_ip] = {
                "minute_requests": [],
                "hour_requests": [],
                "hour_uploads": [],
                "burst_requests": [],
                "violation_count": 0
            }
        
        client_data = self.clients[client_ip]
        self._clean_old_requests(client_data, current_time)
        
        # 不審な活動チェック
        if self._check_suspicious_activity(client_ip, current_time):
            self.blocked_clients[client_ip] = current_time
            logger.error(
                "Client blocked due to suspicious activity",
                client_ip=client_ip,
                activity_pattern="rapid_requests"
            )
            return Response(
                content="Access blocked due to suspicious activity",
                status_code=429,
                headers={"X-Block-Reason": "Suspicious activity detected"}
            )
        
        # バーストリミット チェック
        if len(client_data["burst_requests"]) >= self.burst_limit:
            client_data["violation_count"] += 1
            logger.warning(
                "Burst limit exceeded",
                client_ip=client_ip,
                burst_requests=len(client_data["burst_requests"]),
                limit=self.burst_limit
            )
            
            return Response(
                content="Too many requests in short time",
                status_code=429,
                headers={
                    "Retry-After": str(self.burst_window),
                    "X-RateLimit-Type": "burst"
                }
            )
        
        # 分単位レート制限チェック
        if len(client_data["minute_requests"]) >= self.requests_per_minute:
            client_data["violation_count"] += 1
            logger.warning(
                "Per-minute rate limit exceeded",
                client_ip=client_ip,
                requests=len(client_data["minute_requests"]),
                limit=self.requests_per_minute
            )
            
            return Response(
                content="Rate limit exceeded (per minute)",
                status_code=429,
                headers={
                    "Retry-After": "60",
                    "X-RateLimit-Limit": str(self.requests_per_minute),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(current_time + 60)),
                    "X-RateLimit-Type": "per-minute"
                }
            )
        
        # 時間単位レート制限チェック
        if len(client_data["hour_requests"]) >= self.requests_per_hour:
            client_data["violation_count"] += 1
            logger.warning(
                "Per-hour rate limit exceeded",
                client_ip=client_ip,
                requests=len(client_data["hour_requests"]),
                limit=self.requests_per_hour
            )
            
            return Response(
                content="Rate limit exceeded (per hour)",
                status_code=429,
                headers={
                    "Retry-After": "3600",
                    "X-RateLimit-Type": "per-hour"
                }
            )
        
        # アップロード制限チェック
        is_upload = self._is_upload_request(request)
        if is_upload and len(client_data["hour_uploads"]) >= self.uploads_per_hour:
            client_data["violation_count"] += 1
            logger.warning(
                "Upload rate limit exceeded",
                client_ip=client_ip,
                uploads=len(client_data["hour_uploads"]),
                limit=self.uploads_per_hour
            )
            
            return Response(
                content="Upload rate limit exceeded",
                status_code=429,
                headers={
                    "Retry-After": "3600",
                    "X-RateLimit-Type": "uploads"
                }
            )
        
        # 違反回数チェック（5回以上でブロック）
        if client_data["violation_count"] >= 5:
            self.blocked_clients[client_ip] = current_time
            logger.error(
                "Client blocked due to repeated violations",
                client_ip=client_ip,
                violation_count=client_data["violation_count"]
            )
            
            return Response(
                content="Access blocked due to repeated violations",
                status_code=429,
                headers={"X-Block-Reason": "Repeated violations"}
            )
        
        # リクエスト記録
        client_data["minute_requests"].append(current_time)
        client_data["hour_requests"].append(current_time)
        client_data["burst_requests"].append(current_time)
        
        if is_upload:
            client_data["hour_uploads"].append(current_time)
        
        # リクエスト処理
        response = await call_next(request)
        
        # レスポンスヘッダー追加
        remaining_minute = max(0, self.requests_per_minute - len(client_data["minute_requests"]))
        remaining_hour = max(0, self.requests_per_hour - len(client_data["hour_requests"]))
        remaining_uploads = max(0, self.uploads_per_hour - len(client_data["hour_uploads"]))
        
        response.headers["X-RateLimit-Limit-Minute"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining-Minute"] = str(remaining_minute)
        response.headers["X-RateLimit-Limit-Hour"] = str(self.requests_per_hour)
        response.headers["X-RateLimit-Remaining-Hour"] = str(remaining_hour)
        response.headers["X-RateLimit-Upload-Remaining"] = str(remaining_uploads)
        
        return response


class APIKeyValidationMiddleware(BaseHTTPMiddleware):
    """APIキー検証ミドルウェア"""
    
    def __init__(self, app, api_keys: Optional[Dict[str, str]] = None):
        super().__init__(app)
        self.api_keys = api_keys or {}
        self.require_api_key = bool(api_keys)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # ヘルスチェックとステータスエンドポイントは除外
        excluded_paths = ["/health", "/api/v1/status"]
        if any(request.url.path.startswith(path) for path in excluded_paths):
            return await call_next(request)
        
        # APIキーが必要な場合のみチェック
        if not self.require_api_key:
            return await call_next(request)
        
        # APIキーをヘッダーから取得
        api_key = request.headers.get("X-API-Key") or request.headers.get("Authorization")
        
        if api_key and api_key.startswith("Bearer "):
            api_key = api_key[7:]  # "Bearer "を削除
        
        if not api_key:
            logger.warning(
                "API request without API key",
                path=request.url.path,
                client_ip=request.client.host if request.client else None
            )
            return Response(
                content="API key required",
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # APIキー検証
        if api_key not in self.api_keys:
            logger.warning(
                "Invalid API key used",
                api_key_hash=hashlib.sha256(api_key.encode()).hexdigest()[:8],
                client_ip=request.client.host if request.client else None
            )
            return Response(
                content="Invalid API key",
                status_code=403
            )
        
        # リクエストにAPIキー情報を追加
        request.state.api_key_name = self.api_keys[api_key]
        return await call_next(request)


class RequestSizeMiddleware(BaseHTTPMiddleware):
    """リクエストサイズ制限ミドルウェア"""
    
    def __init__(self, app, max_request_size: int = 50 * 1024 * 1024):  # 50MB
        super().__init__(app)
        self.max_request_size = max_request_size
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        content_length = request.headers.get("content-length")
        
        if content_length:
            size = int(content_length)
            if size > self.max_request_size:
                from app.core.config import format_file_size
                
                logger.warning(
                    "Request size limit exceeded",
                    size_bytes=size,
                    limit_bytes=self.max_request_size,
                    client_ip=request.client.host if request.client else None
                )
                
                return Response(
                    content=f"Request too large ({format_file_size(size)}). Maximum allowed: {format_file_size(self.max_request_size)}",
                    status_code=413,
                    headers={"Content-Type": "text/plain"}
                )
        
        return await call_next(request)


class SecurityEventMiddleware(BaseHTTPMiddleware):
    """セキュリティイベント検出ミドルウェア"""
    
    def __init__(self, app):
        super().__init__(app)
        self.suspicious_patterns = [
            # SQL injection patterns
            r"(?i)(union|select|insert|update|delete|drop|create|alter|exec|execute)",
            # XSS patterns
            r"(?i)(<script|javascript:|vbscript:|onload|onerror|onclick)",
            # Path traversal
            r"(\.\./|\.\.\\|%2e%2e%2f|%2e%2e%5c)",
            # Command injection
            r"(?i)(;|&|\||\$\(|\`|system\(|exec\()",
        ]
        import re
        self.compiled_patterns = [re.compile(pattern) for pattern in self.suspicious_patterns]
    
    def _check_suspicious_content(self, content: str) -> bool:
        """不審なコンテンツパターンをチェック"""
        return any(pattern.search(content) for pattern in self.compiled_patterns)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # URLパスチェック
        if self._check_suspicious_content(str(request.url.path)):
            logger.error(
                "Suspicious URL pattern detected",
                path=request.url.path,
                client_ip=request.client.host if request.client else None
            )
            return Response(
                content="Request rejected due to security policy",
                status_code=400
            )
        
        # クエリパラメータチェック
        if request.url.query and self._check_suspicious_content(request.url.query):
            logger.error(
                "Suspicious query parameter detected",
                query=request.url.query,
                client_ip=request.client.host if request.client else None
            )
            return Response(
                content="Request rejected due to security policy",
                status_code=400
            )
        
        # User-Agentチェック
        user_agent = request.headers.get("user-agent", "")
        if not user_agent or len(user_agent) > 1000:
            logger.warning(
                "Suspicious User-Agent",
                user_agent=user_agent[:100],
                client_ip=request.client.host if request.client else None
            )
        
        # リクエスト処理
        try:
            response = await call_next(request)
            
            # レスポンスステータスが4xx/5xxの場合は記録
            if response.status_code >= 400:
                logger.info(
                    "Error response",
                    status_code=response.status_code,
                    path=request.url.path,
                    method=request.method,
                    client_ip=request.client.host if request.client else None
                )
            
            return response
            
        except Exception as e:
            logger.error(
                "Request processing error",
                error=str(e),
                error_type=type(e).__name__,
                path=request.url.path,
                client_ip=request.client.host if request.client else None
            )
            raise


class FileSizeValidationMiddleware(BaseHTTPMiddleware):
    """ファイルサイズ検証ミドルウェア"""
    
    def __init__(self, app, max_size_bytes: int):
        super().__init__(app)
        self.max_size_bytes = max_size_bytes
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # ファイルアップロードエンドポイントのみチェック
        if (request.method == "POST" and 
            "/transcriptions" in str(request.url.path) and
            request.headers.get("content-type", "").startswith("multipart/form-data")):
            
            content_length = request.headers.get("content-length")
            if content_length:
                size = int(content_length)
                if size > self.max_size_bytes:
                    from app.core.config import format_file_size
                    
                    logger.warning(
                        "File size limit exceeded",
                        size_bytes=size,
                        limit_bytes=self.max_size_bytes,
                        client_ip=request.client.host if request.client else None
                    )
                    
                    return Response(
                        content=f"File size ({format_file_size(size)}) exceeds limit ({format_file_size(self.max_size_bytes)})",
                        status_code=413,
                        headers={"Content-Type": "text/plain"}
                    )
        
        return await call_next(request)


class CacheControlMiddleware(BaseHTTPMiddleware):
    """キャッシュ制御ミドルウェア"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # 静的ファイルにはキャッシュ設定
        if "/static/" in str(request.url.path):
            response.headers["Cache-Control"] = "public, max-age=3600"
        
        # APIエンドポイントはノーキャッシュ
        elif "/api/" in str(request.url.path):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        
        return response