#!/usr/bin/env python3
"""El nivel de azar de un eval — antes de creerle a un número, saber qué es ruido.

    uv run python eval/chance.py

Hace dos cosas:

1. **Nivel de azar empírico**: lanza consultas deliberadamente ajenas al corpus
   ("receta de tamales", "zzz") y mide cuántas veces el top-k sigue conteniendo la
   cadena esperada. Si eso da alto, el hit@5 no está midiendo recuperación.
2. **Nivel de azar analítico**: con N chunks y top-k, la probabilidad de que un
   chunk que *sí* contiene la respuesta caiga en el top-k por pura suerte es k/N.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mk_rag_lab.search import retrieve

QUESTIONS = Path(__file__).with_name("questions.jsonl")
NOISE = [
    "receta de tamales verdes",
    "zzz qqq xxx",
    "cómo cambio una llanta",
    "historia del imperio romano",
    "precio del dólar hoy",
    "mejor playa del norte",
    "instalar windows once",
    "quién ganó el mundial",
    "síntomas de gripe",
    "como criar cuyes",
]


def corpus_size(index: str | None = None) -> int:
    from mk_rag_lab.clients import search_client

    results = search_client(index).search(search_text="*", top=1000, include_total_count=True)
    return results.get_count() or 0


def main() -> int:
    questions = [
        json.loads(line)
        for line in QUESTIONS.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]
    n_chunks = corpus_size()
    top = 5
    print(f"corpus: {n_chunks} chunks · preguntas: {len(questions)} · top-{top}")
    if n_chunks:
        print(f"azar analítico (1 chunk relevante): {top}/{n_chunks} = {top / n_chunks * 100:.0f} %\n")

    random.seed(7)
    hits, trials = 0, 0
    for item in questions:
        for _ in range(10):
            query = random.choice(NOISE)
            results = retrieve(query, mode="hybrid", top=top)
            blob = " ".join(r.content.lower() for r in results)
            trials += 1
            hits += any(n.lower() in blob for n in item["expect"])

    rate = hits / trials if trials else 0.0
    print(f"azar empírico (consultas ajenas al corpus): {hits}/{trials} = {rate * 100:.0f} %")
    print(
        "\nSi el azar empírico es alto, el eval no distingue recuperar de adivinar:\n"
        "el corpus es demasiado chico respecto de k."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
