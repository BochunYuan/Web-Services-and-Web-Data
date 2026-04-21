from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Mapping

from asgiref.sync import async_to_sync
from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from app.main import app as fastapi_app


STATIC_DIR = Path(settings.BASE_DIR) / "static"
API_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]
HOP_BY_HOP_RESPONSE_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


def root_index(request: HttpRequest) -> HttpResponse:
    index = STATIC_DIR / "index.html"
    if index.exists():
        html = index.read_text(encoding="utf-8")
        html = html.replace(
            '<script src="/static/app.js"></script>',
            (
                f'<script>window.__API_BASE_PREFIX__ = "{settings.API_V1_PREFIX}";</script>\n'
                '<script src="/static/app.js"></script>'
            ),
        )
        return HttpResponse(html)
    return JsonResponse(
        {
            "name": settings.PROJECT_NAME,
            "version": settings.PROJECT_VERSION,
            "status": "ok",
            "docs": "/docs",
        }
    )


def health_check(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok"})


def openapi_schema(request: HttpRequest) -> HttpResponse:
    return _proxy_fastapi_path(request, "/openapi.json")


def docs(request: HttpRequest) -> HttpResponse:
    return _proxy_fastapi_path(request, "/docs")


def docs_oauth2_redirect(request: HttpRequest) -> HttpResponse:
    return _proxy_fastapi_path(request, "/docs/oauth2-redirect")


def redoc(request: HttpRequest) -> HttpResponse:
    return _proxy_fastapi_path(request, "/redoc")


@csrf_exempt
def api_proxy(request: HttpRequest, subpath: str = "") -> HttpResponse:
    if request.method not in API_METHODS:
        return HttpResponseNotAllowed(API_METHODS)

    return _proxy_fastapi_path(request, _build_fastapi_path(subpath))


def _build_fastapi_path(subpath: str) -> str:
    prefix = settings.API_V1_PREFIX.rstrip("/")
    tail = subpath.lstrip("/")
    return f"{prefix}/{tail}" if tail else prefix


def _proxy_fastapi_path(request: HttpRequest, path: str) -> HttpResponse:
    scope = _build_asgi_scope(request, path)
    body = request.body
    response = async_to_sync(_call_fastapi)(scope, body)
    return _to_django_response(response)


def _build_asgi_scope(request: HttpRequest, path: str) -> dict:
    raw_path = path.encode("utf-8")
    query_string = request.META.get("QUERY_STRING", "").encode("utf-8")
    headers = _collect_headers(request)
    client_ip = request.META.get("REMOTE_ADDR", "127.0.0.1")
    client_port = int(request.META.get("REMOTE_PORT") or 0)
    server_name = request.get_host().split(":", 1)[0] if request.get_host() else "testserver"
    server_port = int(request.get_port() or 80)

    return {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": request.method,
        "scheme": request.scheme,
        "path": path,
        "raw_path": raw_path,
        "query_string": query_string,
        "headers": headers,
        "client": (client_ip, client_port),
        "server": (server_name, server_port),
        "root_path": "",
        "state": {},
    }


def _collect_headers(request: HttpRequest) -> list[tuple[bytes, bytes]]:
    headers: list[tuple[bytes, bytes]] = []
    for key, value in request.META.items():
        if key.startswith("HTTP_"):
            name = key[5:].replace("_", "-").lower()
            headers.append((name.encode("latin-1"), value.encode("latin-1")))

    if request.content_type:
        headers.append((b"content-type", request.content_type.encode("latin-1")))
    if request.content_params:
        params = "; ".join(f"{k}={v}" for k, v in request.content_params.items())
        content_type = request.content_type
        if params:
            content_type = f"{content_type}; {params}"
        headers = [pair for pair in headers if pair[0] != b"content-type"]
        headers.append((b"content-type", content_type.encode("latin-1")))

    content_length = request.META.get("CONTENT_LENGTH")
    if content_length:
        headers.append((b"content-length", str(content_length).encode("latin-1")))

    return headers


async def _call_fastapi(scope: dict, body: bytes) -> dict:
    response_start: dict | None = None
    response_body = bytearray()
    body_sent = False

    async def receive() -> dict:
        nonlocal body_sent
        if not body_sent:
            body_sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        await asyncio.sleep(0)
        return {"type": "http.disconnect"}

    async def send(message: Mapping) -> None:
        nonlocal response_start
        if message["type"] == "http.response.start":
            response_start = dict(message)
            return
        if message["type"] == "http.response.body":
            response_body.extend(message.get("body", b""))

    await fastapi_app(scope, receive, send)

    if response_start is None:
        raise RuntimeError("FastAPI app did not send an HTTP response start event")

    return {
        "status": response_start["status"],
        "headers": list(response_start.get("headers", [])),
        "body": bytes(response_body),
    }


def _to_django_response(response: dict) -> HttpResponse:
    django_response = HttpResponse(
        content=response["body"],
        status=response["status"],
    )

    for raw_name, raw_value in response["headers"]:
        name = raw_name.decode("latin-1")
        if name.lower() in HOP_BY_HOP_RESPONSE_HEADERS:
            continue
        django_response[name] = raw_value.decode("latin-1")

    return django_response
