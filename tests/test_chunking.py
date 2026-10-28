"""Los comportamientos por los que existe el chunking por estructura."""

from __future__ import annotations

from mk_rag_lab.chunking import (
    chunk_markdown,
    chunk_markdown_naive,
    count_tokens,
    parse_blocks,
)

DOC = """# Manual

## Instalación

Texto de instalación. """ + ("Relleno de instalación. " * 30) + """

```bash
# un bloque de código realista, más grande que una ventana del baseline
pip install paquete
echo "esto no es un encabezado"
python -m paquete --revisar
python -m paquete --ejecutar --verbose
python -m paquete --salida json > resultado.json
cat resultado.json | python -c "import json,sys; print(json.load(sys.stdin)['ok'])"
echo "fin del bloque"
```

## Uso

Texto de uso. """ + ("Relleno de uso. " * 30) + """

| campo | tipo |
|---|---|
| a | str |
"""


def test_code_fence_is_never_split():
    chunks = chunk_markdown(DOC, target_tokens=120, overlap_tokens=20)
    fenced = [c for c in chunks if "```" in c.content]
    assert fenced, "esperaba al menos un fragmento con código"
    for chunk in fenced:
        assert chunk.content.count("```") % 2 == 0, "una cerca de código quedó abierta"


def test_heading_is_the_first_block_of_the_chunk():
    chunks = chunk_markdown(DOC, target_tokens=120, overlap_tokens=0)
    assert chunks[0].heading == "Manual › Instalación"
    assert any(c.heading.endswith("Uso") for c in chunks)


def test_heading_inside_a_fence_is_not_an_heading():
    blocks = parse_blocks(DOC)
    titles = [b.text for b in blocks if b.kind == "heading"]
    assert "Instalación" in titles and "Uso" in titles
    assert not any("esto no es" in t for t in titles)


def test_naive_starts_inside_the_code_fence():
    """El baseline ignora la estructura: con un bloque de código más grande que su
    ventana, algún fragmento empieza en medio del código, sin la cerca de apertura.
    Si esta prueba deja de fallar, la comparación del eval perdió su contraste."""
    naive = chunk_markdown_naive(DOC, target_tokens=100, overlap_tokens=10)
    assert len(naive) > 1
    assert any(c.content.count("```") % 2 for c in naive), "se esperaba una cerca partida"


def test_oversized_paragraph_is_split_with_overlap():
    text = "## Sección\n\n" + ("oración larga para rellenar. " * 300)
    chunks = chunk_markdown(text, target_tokens=100, overlap_tokens=30)
    assert len(chunks) > 3
    assert all(count_tokens(c.content) <= 140 for c in chunks)


def test_plain_text_without_structure_still_chunks():
    chunks = chunk_markdown("palabra " * 500, target_tokens=100, overlap_tokens=20)
    assert chunks and all(c.heading == "" for c in chunks)
