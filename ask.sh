#!/usr/bin/env bash
# Preguntas al corpus en bucle, sin reiniciar el proceso por cada una.
#
#   ./ask.sh                       híbrido + reranker semántico (lo recomendado)
#   ./ask.sh --mode keyword        un solo modo
#   ./ask.sh --top 3               menos contexto
#   ./ask.sh --index mk-rag-lab-naive   comparar contra el índice del baseline
#
# Variables: MODE, TOP, SEMANTIC=0 para desactivar el reranker.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
  echo "falta el entorno: uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -e ." >&2
  exit 1
fi

export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}src"

args=(--repl)
[ -n "${MODE:-}" ] && args+=(--mode "$MODE")
[ -n "${TOP:-}" ] && args+=(--top "$TOP")
[ "${SEMANTIC:-1}" = "1" ] && args+=(--semantic)

exec .venv/bin/python -m mk_rag_lab.rag "${args[@]}" "$@"
