"""Retrieval — three modes over the same index.

    uv run python -m mk_rag_lab.search "¿qué es un handoff?" --mode hybrid

keyword   BM25 only            — the control group
vector    embeddings only      — semantic recall, no exact terms
hybrid    both, fused by RRF  — + semantic ranker when the tier allows it

The eval compares the three. Do not delete a mode: the comparison is the point.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass

from azure.search.documents.models import VectorizedQuery

from .clients import embed, search_client

MODES = ("keyword", "vector", "hybrid")


@dataclass
class Hit:
    path: str
    heading: str
    content: str
    score: float | None
    reranker_score: float | None = None


def retrieve(
    query: str,
    *,
    mode: str = "hybrid",
    top: int = 5,
    semantic: bool = False,
    index: str | None = None,
) -> list[Hit]:
    if mode not in MODES:
        raise ValueError(f"mode debe ser uno de {MODES}")

    kwargs: dict = {"search_text": query, "top": top, "select": ["path", "heading", "content"]}

    if mode in ("vector", "hybrid"):
        # Embedding en el cliente: el mismo `embed()` que usa la ingesta, así el
        # vector de la consulta y el del índice salen del mismo modelo y la misma
        # función. La alternativa es un vectorizer del lado del servicio en el
        # perfil del índice (VectorizableTextQuery), que evita el viaje de ida y
        # vuelta pero ata el índice a un recurso de OpenAI.
        kwargs["vector_queries"] = [
            VectorizedQuery(
                vector=embed([query])[0],
                k_nearest_neighbors=top,
                fields="content_vector",
            )
        ]
    if mode == "vector":
        kwargs["search_text"] = None
    if semantic and mode == "hybrid":
        kwargs["query_type"] = "semantic"
        kwargs["semantic_configuration_name"] = "default-semantic"

    results = search_client(index).search(**kwargs)
    return [
        Hit(
            path=r.get("path", ""),
            heading=r.get("heading", ""),
            content=r.get("content", ""),
            score=r.get("@search.score"),
            reranker_score=r.get("@search.reranker_score"),
        )
        for r in results
    ]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("query")
    p.add_argument("--mode", default="hybrid", choices=MODES)
    p.add_argument("--top", type=int, default=5)
    p.add_argument("--semantic", action="store_true")
    p.add_argument("--index", default=None, help="índice a consultar")
    args = p.parse_args(argv)

    for i, hit in enumerate(
        retrieve(
            args.query,
            mode=args.mode,
            top=args.top,
            semantic=args.semantic,
            index=args.index,
        ),
        1,
    ):
        score = f"{hit.score:.4f}" if hit.score is not None else "-"
        rerank = f" rerank={hit.reranker_score:.2f}" if hit.reranker_score else ""
        print(f"{i}. [{score}{rerank}] {hit.path} › {hit.heading}")
        print(f"   {hit.content[:160].replace(chr(10), ' ')}…")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
