"""Ingest a corpus directory into the Search index.

    uv run python -m mk_rag_lab.ingest --corpus corpus/public --recreate

The corpus is an allowlist by construction: only what is inside the directory you
pass gets indexed. `corpus/private/` is gitignored and never leaves this machine.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

from azure.core.exceptions import ResourceNotFoundError

from .chunking import chunk_markdown, chunk_markdown_naive
from .clients import embed, index_client, search_client, settings
from .schema import build_index

TEXT_SUFFIXES = {".md", ".txt", ".markdown"}


def _doc_id(path: Path, chunk_index: int) -> str:
    digest = hashlib.sha1(str(path).encode()).hexdigest()[:12]
    return f"{digest}-{chunk_index}"


def collect_files(corpus: Path) -> list[Path]:
    return sorted(
        p for p in corpus.rglob("*") if p.is_file() and p.suffix.lower() in TEXT_SUFFIXES
    )


STRATEGIES = {
    "structure": chunk_markdown,   # por defecto: corta donde la estructura lo permite
    "naive": chunk_markdown_naive, # grupo de control, para la comparación del eval
}


def build_documents(
    corpus: Path,
    files: list[Path],
    *,
    batch: int = 16,
    strategy: str = "structure",
    target: int = 800,
    overlap: int = 150,
) -> list[dict]:
    chunker = STRATEGIES[strategy]
    documents: list[dict] = []
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        chunks = chunker(text, target_tokens=target, overlap_tokens=overlap)
        if not chunks:
            continue
        for i in range(0, len(chunks), batch):
            window = chunks[i : i + batch]
            vectors = embed([c.content for c in window])
            for chunk, vector in zip(window, vectors):
                documents.append(
                    {
                        "id": _doc_id(path.relative_to(corpus), chunk.index),
                        "content": chunk.content,
                        "heading": chunk.heading or path.stem,
                        "path": str(path.relative_to(corpus)),
                        "chunk_index": chunk.index,
                        "content_vector": vector,
                    }
                )
    return documents


def ensure_index(recreate: bool) -> str:
    s = settings()
    ic = index_client()
    if recreate:
        try:
            ic.delete_index(s.index_name)
            print(f"índice {s.index_name} borrado")
        except ResourceNotFoundError:
            print(f"índice {s.index_name} no existía")
    ic.create_or_update_index(build_index(s.index_name))
    print(f"índice {s.index_name} listo")
    return s.index_name


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Ingesta de un corpus al índice.")
    p.add_argument("--corpus", default="corpus/public")
    p.add_argument("--recreate", action="store_true")
    p.add_argument("--strategy", default="structure", choices=sorted(STRATEGIES))
    p.add_argument("--index", default=None, help="sobrescribe AZURE_SEARCH_INDEX")
    p.add_argument("--target", type=int, default=800, help="techo de tokens por fragmento")
    p.add_argument("--overlap", type=int, default=150, help="presupuesto de solapamiento")
    args = p.parse_args(argv)

    if args.index:
        import os

        os.environ["AZURE_SEARCH_INDEX"] = args.index

    corpus = Path(args.corpus)
    if not corpus.is_dir():
        print(f"no existe: {corpus}", file=sys.stderr)
        return 1

    files = collect_files(corpus)
    if not files:
        print(f"sin documentos en {corpus} ({', '.join(sorted(TEXT_SUFFIXES))})", file=sys.stderr)
        return 1

    ensure_index(recreate=args.recreate)
    documents = build_documents(
        corpus, files, strategy=args.strategy, target=args.target, overlap=args.overlap
    )
    result = search_client().upload_documents(documents=documents)
    ok = sum(1 for r in result if r.succeeded)
    print(f"{len(files)} documentos → {len(documents)} chunks → {ok} subidos")
    return 0 if ok == len(documents) else 1


if __name__ == "__main__":
    raise SystemExit(main())
