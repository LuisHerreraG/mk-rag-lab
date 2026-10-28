"""API HTTP — FastAPI con streaming SSE y citas.

    uv run uvicorn mk_rag_lab.api:app --port 8080
    curl -N "http://127.0.0.1:8080/ask?q=¿qué+mide+hit@5?&semantic=true"

Contrato de `/ask`: `text/event-stream` con tres tipos de evento, en este orden:

    event: citations   →  data: [{"number":1,"path":"…","heading":"…"}]
    data: <token>      →  un evento por token, sin nombre de evento
    event: done        →  data: {"model":"gpt-5-mini","ms":1234}

Las citas van **primero** por una razón: el cliente puede pintar las fuentes antes
de que exista la primera palabra de la respuesta, y quien lee nunca ve una
afirmación sin saber de dónde salió.
"""

from __future__ import annotations

import json
import os
import time
from collections import defaultdict, deque
from collections.abc import Iterator

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from .clients import settings
from .rag import REFUSAL, build_context, stream_answer
from .search import MODES, retrieve

app = FastAPI(
    title="mk-rag-lab",
    description="RAG sobre un corpus de documentos: recuperación híbrida + respuesta con citas.",
    version="0.1.0",
)


# Límite por IP: una demo pública sin esto es una factura abierta. En memoria y por
# proceso — suficiente para una demo; para producción, el límite va en el proxy.
RATE_LIMIT_PER_MINUTE = int(os.environ.get("RAG_RATE_LIMIT", "10"))
_hits: dict[str, deque[float]] = defaultdict(deque)


def _rate_limit(request: Request) -> None:
    if RATE_LIMIT_PER_MINUTE <= 0:
        return
    client = request.client.host if request.client else "unknown"
    now = time.time()
    window = _hits[client]
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= RATE_LIMIT_PER_MINUTE:
        raise HTTPException(
            status_code=429,
            detail=f"límite de {RATE_LIMIT_PER_MINUTE} consultas por minuto",
        )
    window.append(now)


def _require_key(request: Request) -> None:
    """API key opcional: si RAG_API_KEY está definida, se exige el header.

    En local no hace falta; expuesto a una red o a internet, sí. La clave no viaja al
    repo: se lee del entorno, igual que las credenciales de Azure.
    """
    expected = os.environ.get("RAG_API_KEY")
    if not expected:
        return
    if request.headers.get("x-api-key") != expected:
        raise HTTPException(status_code=401, detail="x-api-key inválida")


@app.get("/health")
def health() -> dict:
    s = settings()
    return {"status": "ok", "index": s.index_name, "model": s.chat_deployment}


def _events(question: str, mode: str, top: int, semantic: bool, index: str | None) -> Iterator[str]:
    started = time.perf_counter()
    hits = retrieve(question, mode=mode, top=top, semantic=semantic, index=index)
    if not hits:
        yield f"event: answer\ndata: {json.dumps({'text': REFUSAL})}\n\n"
        yield "event: done\ndata: {}\n\n"
        return

    _, citations = build_context(hits)
    payload = [
        {"number": c.number, "path": c.path, "heading": c.heading} for c in citations
    ]
    yield f"event: citations\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

    emitted = 0
    for token in stream_answer(question, hits):
        emitted += 1
        # un evento por token; \n escapado para no romper el framing de SSE
        yield f"data: {json.dumps(token, ensure_ascii=False)}\n\n"

    if not emitted:
        # el techo de tokens se gastó razonando: se dice, no se devuelve vacío
        note = "El presupuesto de tokens se consumió razonando. Subí RAG_MAX_TOKENS."
        yield f"event: error\ndata: {json.dumps({'detail': note})}\n\n"

    elapsed = int((time.perf_counter() - started) * 1000)
    done = {"model": settings().chat_deployment, "ms": elapsed}
    yield f"event: done\ndata: {json.dumps(done)}\n\n"


@app.get("/ask")
def ask(
    request: Request,
    q: str = Query(..., min_length=3, description="la pregunta"),
    mode: str = Query("hybrid", description="keyword | vector | hybrid"),
    top: int = Query(5, ge=1, le=20),
    semantic: bool = Query(False, description="reranker semántico sobre el híbrido"),
    index: str | None = Query(None, description="índice alternativo"),
) -> StreamingResponse:
    _require_key(request)
    _rate_limit(request)
    if mode not in MODES:
        raise HTTPException(status_code=400, detail=f"mode debe ser uno de {MODES}")
    return StreamingResponse(
        _events(q, mode, top, semantic, index),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
