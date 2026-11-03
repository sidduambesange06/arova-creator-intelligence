from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.routes.collections import router as collections_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.ml_eval import router as ml_eval_router
from app.api.routes.search import router as search_router
from app.api.routes.videos import router as videos_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.security import require_api_auth, validate_server_binding_and_security
from app.database.session import init_db

try:
    from app.api.routes.database_explorer import router as db_explorer_router
except ImportError:
    db_explorer_router = None

logger = configure_logging(settings.LOG_LEVEL)
validate_server_binding_and_security()
init_db()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Local Video RAG & MCP Engine for AI Agents and Developers",
)


class HostAndOriginSecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1. Validate Host header (DNS-rebinding protection)
        host_header = request.headers.get("host", "").split(":")[0].strip().lower()
        if host_header:
            allowed_hosts = settings.allowed_host_list
            if host_header not in allowed_hosts:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": f"Invalid Host header '{host_header}'."},
                )

        # 2. Validate Origin header for state-changing browser requests and admin endpoints
        if request.method in ("POST", "PUT", "DELETE", "PATCH") or request.url.path.startswith("/api/v1/admin/"):
            origin_header = request.headers.get("origin")
            if origin_header:
                norm_origin = origin_header.strip().rstrip("/")
                allowed_origins = [o.rstrip("/") for o in settings.cors_origin_list]
                if norm_origin not in allowed_origins:
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={"detail": f"Untrusted Origin header '{origin_header}'."},
                    )

        return await call_next(request)


app.add_middleware(HostAndOriginSecurityMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS", "PUT", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-Requested-With"],
)

# Protect all application routers with configurable local authentication
app.include_router(videos_router, dependencies=[Depends(require_api_auth)])
app.include_router(collections_router, dependencies=[Depends(require_api_auth)])
app.include_router(jobs_router, dependencies=[Depends(require_api_auth)])
app.include_router(search_router, dependencies=[Depends(require_api_auth)])
app.include_router(ml_eval_router, dependencies=[Depends(require_api_auth)])
if db_explorer_router is not None:
    app.include_router(db_explorer_router)


@app.get("/api/v1/health")
def get_health() -> dict[str, str]:
    logger.info("Health check requested")
    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
