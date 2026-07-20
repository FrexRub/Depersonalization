from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import logging
from time import monotonic
from typing import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.engine import DisabledModelRedactor, OPFModelRedactor, RedactionService
from app.schemas import ErrorResponse, HealthResponse, RedactRequest, RedactResponse
from app.security import BearerTokenVerifier
from app.settings import Settings, load_settings


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


class InferenceGate:
    def __init__(self, concurrency: int, queue_capacity: int, wait_seconds: float) -> None:
        self._running = asyncio.Semaphore(concurrency)
        self._slots = asyncio.Semaphore(concurrency + queue_capacity)
        self._wait_seconds = wait_seconds

    async def run(self, callback, /, *args, **kwargs):
        try:
            await asyncio.wait_for(self._slots.acquire(), timeout=self._wait_seconds)
        except TimeoutError as exc:
            raise HTTPException(status_code=429, detail="Inference queue is full") from exc
        try:
            async with self._running:
                return await asyncio.to_thread(callback, *args, **kwargs)
        finally:
            self._slots.release()


def create_app(
    settings: Settings | None = None,
    service: RedactionService | None = None,
) -> FastAPI:
    config = (settings or load_settings()).validate()
    if service is None:
        model = (
            OPFModelRedactor(model_path=config.model_path, device=config.device)
            if config.opf_enabled
            else DisabledModelRedactor()
        )
        service = RedactionService(model)

    gate = InferenceGate(
        config.inference_concurrency,
        config.queue_capacity,
        config.queue_wait_seconds,
    )
    verifier = BearerTokenVerifier(config.api_token)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        started = monotonic()
        try:
            await asyncio.to_thread(service.load)
        except Exception:
            logger.error("Service started but is not ready")
        else:
            logger.info("Privacy model ready in %.2f seconds", monotonic() - started)
        yield

    docs_url = "/docs" if config.docs_enabled else None
    app = FastAPI(
        title="Privacy Filter API",
        version="1.0.0",
        docs_url=docs_url,
        redoc_url="/redoc" if config.docs_enabled else None,
        openapi_url="/openapi.json" if config.docs_enabled else None,
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def request_size_limit(request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                too_large = int(content_length) > config.max_request_bytes
            except ValueError:
                return JSONResponse(status_code=400, content={"detail": "Invalid Content-Length"})
            if too_large:
                return JSONResponse(status_code=413, content={"detail": "Request body is too large"})
        return await call_next(request)

    @app.get("/health/live", response_model=HealthResponse)
    async def live() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.get(
        "/health/ready",
        response_model=HealthResponse,
        responses={503: {"model": ErrorResponse}},
    )
    async def ready() -> HealthResponse:
        if not service.ready:
            raise HTTPException(status_code=503, detail="Model is not ready")
        return HealthResponse(status="ready")

    @app.post(
        "/v1/redact",
        response_model=RedactResponse,
        dependencies=[Depends(verifier)],
        responses={
            401: {"model": ErrorResponse},
            413: {"model": ErrorResponse},
            429: {"model": ErrorResponse},
            503: {"model": ErrorResponse},
        },
    )
    async def redact(payload: RedactRequest) -> RedactResponse:
        if not service.ready:
            raise HTTPException(status_code=503, detail="Model is not ready")
        if len(payload.text) > config.max_text_chars:
            raise HTTPException(status_code=413, detail="Text is too large")
        try:
            result = await gate.run(
                service.redact,
                payload.text,
                mode=payload.mode,
                policy=payload.policy,
            )
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("Redaction failed: %s", type(exc).__name__)
            raise HTTPException(status_code=500, detail="Redaction failed") from None
        return RedactResponse(redacted_text=result.redacted_text, summary=result.summary)

    return app


app = create_app()

