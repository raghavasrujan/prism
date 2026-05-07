"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import Base, create_all, get_engine, init_engine
from app.dev_migrate import add_missing_columns_dev, drop_stale_unique_indexes_dev
from app.logging_config import configure_logging, get_logger
from app.middleware import RequestContextMiddleware, ResponseRequestIdMiddleware
from app.routers import admin as admin_router
from app.routers import analytics as analytics_router
from app.routers import auth as auth_router
from app.routers import conversations as conv_router
from app.routers import health as health_router
from app.routers import mcp as mcp_router
from app.routers import messages as msg_router
from app.routers import models as models_router
from app.routers import stream as stream_router
from app.routers import tools as tools_router
from app.routers import uploads as uploads_router


@asynccontextmanager
async def _lifespan(app: FastAPI):  # noqa: ARG001
    settings = get_settings()
    configure_logging(
        log_level=settings.log_level,
        log_dir=settings.log_dir,
        log_to_stdout=settings.log_to_stdout,
    )
    init_engine(settings.database_url)
    create_all()
    add_missing_columns_dev(get_engine(), Base.metadata)
    drop_stale_unique_indexes_dev(get_engine(), Base.metadata)
    get_logger(__name__).info(
        "app.startup",
        env=settings.app_env,
        db=settings.database_url,
    )
    yield
    get_logger(__name__).info("app.shutdown")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Agent UI API",
        version="0.1.0",
        docs_url="/docs" if settings.app_debug else None,
        redoc_url=None,
        lifespan=_lifespan,
    )

    # Order matters: outermost first. ResponseRequestId writes the header after
    # the response is built; RequestContext must have already set the contextvar.
    app.add_middleware(ResponseRequestIdMiddleware)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-Id"],
    )

    app.include_router(health_router.router)

    api = FastAPI()  # sub-app pattern would work; keep flat prefix for now
    del api

    app.include_router(auth_router.router, prefix="/api/v1")
    app.include_router(models_router.router, prefix="/api/v1")
    app.include_router(tools_router.router, prefix="/api/v1")
    app.include_router(mcp_router.router, prefix="/api/v1")
    app.include_router(conv_router.router, prefix="/api/v1")
    app.include_router(msg_router.router, prefix="/api/v1")
    app.include_router(stream_router.router, prefix="/api/v1")
    app.include_router(uploads_router.router, prefix="/api/v1")
    app.include_router(analytics_router.router, prefix="/api/v1")
    app.include_router(admin_router.router, prefix="/api/v1")

    return app


app = create_app()
