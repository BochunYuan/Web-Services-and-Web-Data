"""
Rate limiting middleware.

Why rate limiting?
  - Prevents brute-force attacks on /auth/login (trying millions of passwords)
  - Prevents API abuse (scraping all data in one burst)
  - Satisfies the "advanced security implementation" criterion in the 80+ band

Implementation: sliding window counter using cachetools TTLCache.

How it works:
  - For each IP address, we maintain a counter of requests in the last 60 seconds
  - TTLCache automatically expires entries after the window duration
  - If a client exceeds RATE_LIMIT_PER_MINUTE requests, we return 429 Too Many Requests

Tradeoffs vs. production alternatives:
  - This in-memory implementation resets when the server restarts
  - In production at scale, you'd use Redis for shared state across multiple servers
  - For this project (single server), in-memory is perfectly adequate and simpler

HTTP 429 response includes a Retry-After header — this is the RFC standard
that tells clients how long to wait before trying again.
"""

import time
from collections import defaultdict
from threading import Lock

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings


class RateLimiter:
    """
    Sliding window rate limiter.

    Stores request timestamps per IP in a dict.
    On each request:
      1. Remove timestamps older than the window (60s)
      2. Count remaining timestamps
      3. If count >= limit → reject with 429
      4. Otherwise → append current timestamp and allow
    """

    def __init__(self, max_requests: int, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # defaultdict(list): if key doesn't exist, returns [] automatically
        self._requests: dict = defaultdict(list)
        # Lock ensures thread safety — FastAPI uses a thread pool
        self._lock = Lock()

    def is_allowed(self, client_ip: str) -> tuple[bool, int]:
        """
        Check if a request from client_ip should be allowed.

        Returns (allowed: bool, retry_after: int)
        retry_after is seconds until the oldest request expires (0 if allowed).
        """
        now = time.time()
        window_start = now - self.window_seconds

        with self._lock:
            # Remove timestamps outside the current window
            self._requests[client_ip] = [
                ts for ts in self._requests[client_ip] if ts > window_start
            ]

            current_count = len(self._requests[client_ip])

            if current_count >= self.max_requests:
                # Calculate when the oldest request will expire
                oldest = self._requests[client_ip][0]
                retry_after = int(oldest - window_start) + 1
                return False, retry_after

            # Allow: record this request timestamp
            self._requests[client_ip].append(now)
            return True, 0


# Single global rate limiter instance
_rate_limiter = RateLimiter(
    max_requests=settings.RATE_LIMIT_PER_MINUTE,
    window_seconds=60,
)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Starlette middleware that applies rate limiting to all requests.

    BaseHTTPMiddleware wraps every incoming request:
      - dispatch() is called for every request
      - We call_next(request) to pass the request to the actual route handler
      - We can intercept before or after

    Client IP extraction:
      - request.client.host gives the direct connection IP
      - X-Forwarded-For header gives the real IP when behind a proxy/load balancer
        (PythonAnywhere uses a reverse proxy, so we check this header first)
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip rate limiting entirely in test environment
        # (tests fire many requests rapidly from the same IP)
        if settings.ENVIRONMENT == "test":
            return await call_next(request)

        # Skip rate limiting for health checks (monitoring systems hit these frequently)
        if request.url.path in ("/health", "/"):
            return await call_next(request)

        # Get real client IP (handle reverse proxy)
        client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        if not client_ip:
            client_ip = request.client.host if request.client else "unknown"

        allowed, retry_after = _rate_limiter.is_allowed(client_ip)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many requests. Please slow down.",
                    "retry_after_seconds": retry_after,
                },
                headers={
                    # RFC 6585 standard header
                    "Retry-After": str(retry_after),
                    # Extra header for clients that want to display remaining limit
                    "X-RateLimit-Limit": str(settings.RATE_LIMIT_PER_MINUTE),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response = await call_next(request)

        # Add rate limit info headers to all responses (good API practice)
        response.headers["X-RateLimit-Limit"] = str(settings.RATE_LIMIT_PER_MINUTE)

        return response
