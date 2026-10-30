from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.collections import router as collections_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.videos import router as videos_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.database.session import init_db

logger = configure_logging(settings.LOG_LEVEL)
init_db()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Local Video RAG & MCP Engine for AI Agents and Developers",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(videos_router)
app.include_router(collections_router)
app.include_router(jobs_router)


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
