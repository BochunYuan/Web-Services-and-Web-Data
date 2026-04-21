from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import (
    get_swagger_ui_html,
    get_swagger_ui_oauth2_redirect_html,
)
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse

from app.config import settings
from app.database import engine
from app.database_migrations import upgrade_database_to_head
from app.core.rate_limiter import RateLimitMiddleware
import app.models  # noqa: F401 — import models so Base.metadata is populated

STATIC_DIR = Path(__file__).parent.parent / "static"
DOCS_VENDOR_DIR = STATIC_DIR / "vendor"
DOCS_ASSET_VERSION = "20260413-redoc-fix"
LOCAL_FAVICON = f"/static/vendor/fastapi-favicon.png?v={DOCS_ASSET_VERSION}"
EMPTY_FAVICON = "data:,"
LOCAL_SWAGGER_JS = f"/static/vendor/swagger-ui-bundle.js?v={DOCS_ASSET_VERSION}"
LOCAL_SWAGGER_CSS = f"/static/vendor/swagger-ui.css?v={DOCS_ASSET_VERSION}"
LOCAL_REDOC_JS = f"/static/vendor/redoc.next.standalone.js?v={DOCS_ASSET_VERSION}"
CDN_REDOC_JS = "https://cdn.jsdelivr.net/npm/redoc@3.0.0-rc.0/bundle/redoc.standalone.js"


# ---------------------------------------------------------------------------
# Lifespan: startup & shutdown logic
# ---------------------------------------------------------------------------
# FastAPI's `lifespan` replaces the old @app.on_event("startup") pattern.
# Code before `yield` runs at startup; code after `yield` runs at shutdown.

@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP: apply versioned Alembic migrations before serving requests.
    upgrade_database_to_head()

    yield  # Application runs here

    # SHUTDOWN: dispose the connection pool cleanly
    await engine.dispose()


# ---------------------------------------------------------------------------
# FastAPI application instance
# ---------------------------------------------------------------------------

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description=settings.PROJECT_DESCRIPTION,
    # We self-host docs assets below so /docs and /redoc still work when
    # external CDNs or Google Fonts are blocked.
    docs_url=None,
    redoc_url=None,
    # OpenAPI JSON schema at /openapi.json
    openapi_url="/openapi.json",
    swagger_ui_oauth2_redirect_url="/docs/oauth2-redirect",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS Middleware
# ---------------------------------------------------------------------------
# CORS (Cross-Origin Resource Sharing) controls which web origins can call
# this API from a browser. We allow only specified origins (not "*") for
# security — this satisfies the "advanced security" requirement.

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# Rate limiting middleware — must be added AFTER CORSMiddleware
# Middleware is applied in reverse order (last added = first executed)
app.add_middleware(RateLimitMiddleware)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
from app.routers import auth, drivers, teams, circuits, races, results, analytics  # noqa: E402

app.include_router(auth.router,      prefix=settings.API_V1_PREFIX + "/auth",      tags=["Authentication"])
app.include_router(drivers.router,   prefix=settings.API_V1_PREFIX + "/drivers",   tags=["Drivers"])
app.include_router(teams.router,     prefix=settings.API_V1_PREFIX + "/teams",     tags=["Teams"])
app.include_router(circuits.router,  prefix=settings.API_V1_PREFIX + "/circuits",  tags=["Circuits"])
app.include_router(races.router,     prefix=settings.API_V1_PREFIX + "/races",     tags=["Races"])
app.include_router(results.router,   prefix=settings.API_V1_PREFIX + "/results",   tags=["Results"])
app.include_router(analytics.router, prefix=settings.API_V1_PREFIX + "/analytics", tags=["Analytics"])


def _has_local_docs_asset(filename: str) -> bool:
    """Check whether a self-hosted docs asset exists under static/vendor/."""
    return (DOCS_VENDOR_DIR / filename).exists()


# ---------------------------------------------------------------------------
# Custom API docs
# ---------------------------------------------------------------------------
# FastAPI's default docs pages load JS/CSS from public CDNs. That can produce a
# blank page in restricted network environments, so we prefer local assets.

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    swagger_js_url = LOCAL_SWAGGER_JS if _has_local_docs_asset("swagger-ui-bundle.js") else None
    swagger_css_url = LOCAL_SWAGGER_CSS if _has_local_docs_asset("swagger-ui.css") else None

    docs_kwargs = {
        "openapi_url": app.openapi_url,
        "title": f"{app.title} - Swagger UI",
        "oauth2_redirect_url": app.swagger_ui_oauth2_redirect_url,
        "swagger_favicon_url": EMPTY_FAVICON,
    }
    if swagger_js_url:
        docs_kwargs["swagger_js_url"] = swagger_js_url
    if swagger_css_url:
        docs_kwargs["swagger_css_url"] = swagger_css_url

    response = get_swagger_ui_html(**docs_kwargs)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/docs/oauth2-redirect", include_in_schema=False)
async def swagger_ui_redirect():
    return get_swagger_ui_oauth2_redirect_html()


@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    redoc_js_url = LOCAL_REDOC_JS if _has_local_docs_asset("redoc.next.standalone.js") else CDN_REDOC_JS
    redoc_favicon_url = LOCAL_FAVICON if _has_local_docs_asset("fastapi-favicon.png") else EMPTY_FAVICON
    return HTMLResponse(
        f"""
    <!DOCTYPE html>
    <html>
    <head>
    <title>{app.title} - ReDoc</title>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://fonts.googleapis.com/css?family=Montserrat:300,400,700|Roboto:300,400,700" rel="stylesheet">
    <link rel="shortcut icon" href="{redoc_favicon_url}">
    <style>
      body {{
        margin: 0;
        padding: 0;
      }}
    </style>
    </head>
    <body>
    <noscript>
        ReDoc requires Javascript to function. Please enable it to browse the documentation.
    </noscript>
    <redoc spec-url="{app.openapi_url}"></redoc>
    <script type="module" src="{redoc_js_url}"></script>
    </body>
    </html>
    """,
        headers={"Cache-Control": "no-store"},
    )


# ---------------------------------------------------------------------------
# Static files (frontend UI)
# ---------------------------------------------------------------------------
# Serve everything in static/ at the /static URL prefix.
# The frontend HTML/CSS/JS lives here.

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ---------------------------------------------------------------------------
# Root — serve the frontend UI
# ---------------------------------------------------------------------------

@app.get("/", tags=["UI"], include_in_schema=False)
async def root():
    """Serve the frontend dashboard."""
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    # Fallback JSON if static files are missing
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.PROJECT_VERSION,
        "status": "ok",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Minimal health check for uptime monitoring."""
    return {"status": "ok"}
