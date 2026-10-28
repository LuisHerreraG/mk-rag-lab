#!/usr/bin/env python3
"""The evaluation harness — the artifact the CV quotes.

    uv run python eval/run.py            # los tres modos
    uv run python eval/run.py --answer   # + latencia de generación

Each question carries the strings a correct retrieval must surface. hit@5 is
"was at least one expected string inside the top 5 chunks". Latencies are
measured on retrieval only unless --answer is passed.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mk_rag_lab.search import MODES, retrieve

QUESTIONS = Path(__file__).with_name("questions.jsonl")
RESULTS = Path(__file__).with_name("results.md")


def load_questions() -> list[dict]:
    rows = []
    for line in QUESTIONS.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            rows.append(json.loads(line))
    return rows


def p95(values: list[float]) -> float:
    if len(values) < 2:
        return values[0] if values else 0.0
    return statistics.quantiles(values, n=20)[18]


def first_hit_rank(results: list, expects: list[str]) -> int | None:
    """Posición (1-based) del primer fragmento que contiene alguna cadena esperada.

    Se mira fragmento por fragmento y no el texto concatenado: un hit en el puesto
    5 y uno en el puesto 1 no valen lo mismo, y promediarlos esconde la diferencia.
    """
    needles = [n.lower() for n in expects]
    for rank, hit in enumerate(results, 1):
        body = hit.content.lower()
        if any(needle in body for needle in needles):
            return rank
    return None


def run_mode(questions: list[dict], mode: str, top: int, semantic: bool, index: str | None = None) -> dict:
    ranks: list[int | None] = []
    latencies: list[float] = []
    for item in questions:
        started = time.perf_counter()
        results = retrieve(item["q"], mode=mode, top=top, semantic=semantic, index=index)
        latencies.append((time.perf_counter() - started) * 1000)
        ranks.append(first_hit_rank(results, item["expect"]))

    found = [r for r in ranks if r]
    n = len(questions) or 1
    return {
        "mode": mode + ("+semantic" if semantic else ""),
        "hit@1": sum(1 for r in found if r == 1) / n,
        "hit@5": len(found) / n,
        "MRR": sum(1.0 / r for r in found) / n,
        "p50_ms": statistics.median(latencies) if latencies else 0.0,
        "p95_ms": p95(latencies),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--top", type=int, default=5)
    p.add_argument("--semantic", action="store_true", help="usa el ranker semántico en híbrido")
    p.add_argument("--index", default=None, help="índice a evaluar (por defecto AZURE_SEARCH_INDEX)")
    args = p.parse_args(argv)

    questions = load_questions()
    print(f"{len(questions)} preguntas · top-{args.top}\n")

    rows = [run_mode(questions, m, args.top, args.semantic, args.index) for m in MODES]
    header = f"{'modo':22s} {'hit@1':>7s} {'hit@5':>7s} {'MRR':>6s} {'p50(ms)':>9s} {'p95(ms)':>9s}"
    print(header)
    print("-" * len(header))
    for r in rows:
        print(
            f"{r['mode']:22s} {r['hit@1']*100:6.1f}% {r['hit@5']*100:6.1f}% "
            f"{r['MRR']:6.3f} {r['p50_ms']:9.0f} {r['p95_ms']:9.0f}"
        )

    lines = [
        "| modo | hit@1 | hit@5 | MRR | p50 (ms) | p95 (ms) |",
        "|---|---|---|---|---|---|",
    ]
    lines += [
        f"| {r['mode']} | {r['hit@1']*100:.0f} % | {r['hit@5']*100:.0f} % | "
        f"{r['MRR']:.3f} | {r['p50_ms']:.0f} | {r['p95_ms']:.0f} |"
        for r in rows
    ]
    RESULTS.write_text("\n".join(lines) + "\n")
    print(f"\nescrito: {RESULTS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
