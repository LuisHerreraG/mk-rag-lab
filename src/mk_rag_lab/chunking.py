"""Chunking — BASELINE, replace it and prove the difference with the eval.

This is a naive fixed-size splitter kept as the control group: it lets the whole
pipeline run end to end today, and it gives the eval something to beat. Your
version should split on structure (headings, code fences, list blocks) and you
should be able to say why the size and the overlap are what they are.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import tiktoken

_ENCODER = tiktoken.get_encoding("cl100k_base")
_HEADING = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)  # sin MULTILINE, $ exige fin de string


@dataclass
class Chunk:
    heading: str
    content: str
    index: int


def count_tokens(text: str) -> int:
    return len(_ENCODER.encode(text))


def chunk_markdown(
    text: str, *, target_tokens: int = 800, overlap_tokens: int = 150
) -> list[Chunk]:
    """BASELINE: fixed-size windows with a fixed overlap, heading carried along."""
    tokens = _ENCODER.encode(text)
    if not tokens:
        return []

    step = max(1, target_tokens - overlap_tokens)
    heading = ""
    chunks: list[Chunk] = []
    for start in range(0, len(tokens), step):
        window = tokens[start : start + target_tokens]
        if not window:
            break
        body = _ENCODER.decode(window)
        found = _HEADING.search(body)
        if found:
            heading = found.group(1).strip()
        chunks.append(Chunk(heading=heading, content=body, index=len(chunks)))
        if start + target_tokens >= len(tokens):
            break
    return chunks
