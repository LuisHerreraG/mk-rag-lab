# Imagen del lab: API + herramientas, sin secretos adentro.
# Multi-arch (arm64 para el Pi 5, amd64 para lo demás).
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1 \
    UV_COMPILE_BYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN uv pip install --system .

# usuario sin privilegios: el contenedor no necesita root después de instalar
RUN useradd --create-home --uid 10001 raglab
USER raglab

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
    CMD curl -fsS http://127.0.0.1:8080/health || exit 1

CMD ["uvicorn", "mk_rag_lab.api:app", "--host", "0.0.0.0", "--port", "8080"]
