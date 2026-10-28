"""Tests que no tocan la red: la estructura y el esquema, nada más."""

from __future__ import annotations

from mk_rag_lab.chunking import chunk_markdown, count_tokens
from mk_rag_lab.schema import EMBEDDING_DIMS, build_index


def test_schema_has_required_fields():
    index = build_index("test-index")
    names = {f.name for f in index.fields}
    assert {"id", "content", "heading", "path", "chunk_index", "content_vector"} <= names
    vector = next(f for f in index.fields if f.name == "content_vector")
    assert vector.vector_search_dimensions == EMBEDDING_DIMS


def test_chunking_splits_and_keeps_heading():
    text = "# Título\n\n" + ("una frase de relleno. " * 400)
    chunks = chunk_markdown(text, target_tokens=200, overlap_tokens=40)
    assert len(chunks) > 1
    assert chunks[0].heading == "Título"
    assert all(count_tokens(c.content) <= 200 for c in chunks)


def test_chunking_of_empty_document_is_empty():
    assert chunk_markdown("") == []
