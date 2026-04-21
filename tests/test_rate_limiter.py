"""
Rate limiter tests.

Covers:
  - Sliding-window algorithm behavior in RateLimiter
  - Middleware bypass in test environment
  - Middleware bypass for /health
  - HTTP 429 response and rate-limit headers in non-test environment
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from app.core.rate_limiter import RateLimiter, RateLimitMiddleware


class TestRateLimiterCore:
    """Unit tests for the in-memory sliding-window limiter."""

    def test_allows_requests_until_limit_then_blocks(self):
        """The limiter allows up to max_requests, then rejects the next request."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)

        assert limiter.is_allowed("1.2.3.4") == (True, 0)
        assert limiter.is_allowed("1.2.3.4") == (True, 0)

        allowed, retry_after = limiter.is_allowed("1.2.3.4")
        assert allowed is False
        assert retry_after > 0

    def test_tracks_each_ip_independently(self):
        """One noisy IP should not block a different client IP."""
        limiter = RateLimiter(max_requests=1, window_seconds=60)

        assert limiter.is_allowed("10.0.0.1") == (True, 0)
        assert limiter.is_allowed("10.0.0.2") == (True, 0)

        allowed, _ = limiter.is_allowed("10.0.0.1")
        assert allowed is False

    def test_old_requests_expire_after_window(self, monkeypatch):
        """Requests outside the sliding window are discarded and no longer count."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        current_time = {"value": 100.0}

        def fake_time():
            return current_time["value"]

        monkeypatch.setattr("app.core.rate_limiter.time.time", fake_time)

        assert limiter.is_allowed("1.2.3.4") == (True, 0)
        current_time["value"] = 120.0
        assert limiter.is_allowed("1.2.3.4") == (True, 0)

        current_time["value"] = 161.0
        # The request at t=100 is now outside the window, so a new request is allowed.
        assert limiter.is_allowed("1.2.3.4") == (True, 0)

    def test_retry_after_reflects_oldest_request_age(self, monkeypatch):
        """Blocked requests return a positive Retry-After derived from the oldest hit."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        current_time = {"value": 10.0}

        def fake_time():
            return current_time["value"]

        monkeypatch.setattr("app.core.rate_limiter.time.time", fake_time)

        assert limiter.is_allowed("1.2.3.4") == (True, 0)
        current_time["value"] = 20.0
        assert limiter.is_allowed("1.2.3.4") == (True, 0)

        current_time["value"] = 30.0
        allowed, retry_after = limiter.is_allowed("1.2.3.4")
        assert allowed is False
        assert retry_after == 41


def _build_rate_limited_test_app() -> FastAPI:
    """Create a minimal app with the real rate-limit middleware attached."""
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware)

    @app.get("/limited")
    async def limited():
        return {"status": "ok"}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/")
    async def root():
        return {"status": "ok"}

    @app.get("/boom")
    async def boom():
        return JSONResponse({"status": "boom"})

    return app


class TestRateLimitMiddleware:
    """Integration-style tests for middleware HTTP behavior."""

    async def test_test_environment_bypasses_rate_limiting(self, monkeypatch):
        """ENVIRONMENT=test skips the limiter entirely."""
        app = _build_rate_limited_test_app()
        monkeypatch.setattr("app.core.rate_limiter.settings.ENVIRONMENT", "test")
        monkeypatch.setattr("app.core.rate_limiter.settings.RATE_LIMIT_PER_MINUTE", 1)

        class FailingLimiter:
            def is_allowed(self, client_ip: str):
                raise AssertionError("Limiter should not be called in test environment")

        monkeypatch.setattr("app.core.rate_limiter._rate_limiter", FailingLimiter())

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            first = await client.get("/limited")
            second = await client.get("/limited")

        assert first.status_code == 200
        assert second.status_code == 200

    async def test_health_endpoint_bypasses_rate_limiting(self, monkeypatch):
        """Health checks are exempt even in non-test environments."""
        app = _build_rate_limited_test_app()
        monkeypatch.setattr("app.core.rate_limiter.settings.ENVIRONMENT", "development")
        monkeypatch.setattr("app.core.rate_limiter.settings.RATE_LIMIT_PER_MINUTE", 1)

        class FailingLimiter:
            def is_allowed(self, client_ip: str):
                raise AssertionError("Limiter should not be called for /health")

        monkeypatch.setattr("app.core.rate_limiter._rate_limiter", FailingLimiter())

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    async def test_rate_limited_request_returns_429_and_headers(self, monkeypatch):
        """Blocked requests return RFC-compliant retry headers and a JSON body."""
        app = _build_rate_limited_test_app()
        monkeypatch.setattr("app.core.rate_limiter.settings.ENVIRONMENT", "development")
        monkeypatch.setattr("app.core.rate_limiter.settings.RATE_LIMIT_PER_MINUTE", 5)

        class BlockingLimiter:
            def is_allowed(self, client_ip: str):
                assert client_ip == "203.0.113.9"
                return False, 17

        monkeypatch.setattr("app.core.rate_limiter._rate_limiter", BlockingLimiter())

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/limited", headers={"X-Forwarded-For": "203.0.113.9, 10.0.0.1"})

        assert response.status_code == 429
        assert response.json() == {
            "detail": "Too many requests. Please slow down.",
            "retry_after_seconds": 17,
        }
        assert response.headers["Retry-After"] == "17"
        assert response.headers["X-RateLimit-Limit"] == "5"
        assert response.headers["X-RateLimit-Remaining"] == "0"

    async def test_allowed_request_adds_rate_limit_header(self, monkeypatch):
        """Successful requests include the configured X-RateLimit-Limit header."""
        app = _build_rate_limited_test_app()
        monkeypatch.setattr("app.core.rate_limiter.settings.ENVIRONMENT", "development")
        monkeypatch.setattr("app.core.rate_limiter.settings.RATE_LIMIT_PER_MINUTE", 7)

        class AllowingLimiter:
            def __init__(self):
                self.seen_ip = None

            def is_allowed(self, client_ip: str):
                self.seen_ip = client_ip
                return True, 0

        limiter = AllowingLimiter()
        monkeypatch.setattr("app.core.rate_limiter._rate_limiter", limiter)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/limited")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert response.headers["X-RateLimit-Limit"] == "7"
        assert limiter.seen_ip == "127.0.0.1"
