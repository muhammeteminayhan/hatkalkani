"""FastAPI application factory."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from .routes import router
from .store import ROOT, load_store

log = logging.getLogger("hatkalkani.api")


def _selected_aoi(config_dir: Path) -> str:
    cfg = yaml.safe_load((config_dir / "aoi.yaml").read_text(encoding="utf-8"))
    aoi = (cfg or {}).get("selected")
    if not aoi:
        raise ValueError("config/aoi.yaml has no `selected` AOI; pass aoi_id explicitly")
    return str(aoi)


def create_app(
    data_root: Path | str | None = None,
    aoi_id: str | None = None,
    *,
    config_dir: Path | str | None = None,
    web_dir: Path | str | None = None,
) -> FastAPI:
    """Build the app. ``data_root`` is the ``data/processed`` folder (holds ``<aoi>/``)."""
    cfg_dir = Path(config_dir) if config_dir else ROOT / "config"
    root = Path(data_root) if data_root else ROOT / "data" / "processed"
    aoi = aoi_id or _selected_aoi(cfg_dir)
    static_dir = Path(web_dir) if web_dir else ROOT / "web"

    app = FastAPI(
        title="HatKalkanı API", version="0.2",
        docs_url="/api/docs", openapi_url="/api/openapi.json",
    )
    app.state.store = load_store(root, aoi, cfg_dir)
    if not app.state.store.by_asof:
        log.warning("no risk_<as_of> files under %s", app.state.store.aoi_dir)
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict):
            body: dict[str, Any] = exc.detail
        else:
            hint = "Uç nokta listesi: /api/docs" if exc.status_code == 404 else ""
            body = {"error": str(exc.detail), "hint": hint}
        return JSONResponse(body, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        where = ".".join(str(p) for p in first.get("loc", ())[1:])
        return JSONResponse(
            {"error": f"Geçersiz parametre: {where}", "hint": str(first.get("msg", ""))},
            status_code=422,
        )

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error")
        return JSONResponse(
            {"error": "Sunucu hatası.", "hint": type(exc).__name__}, status_code=500
        )

    app.include_router(router)
    # Registered last so /api always wins; unknown /api/* falls through to a JSON 404.
    app.mount("/", StaticFiles(directory=static_dir, html=True, check_dir=False), name="web")
    return app
