"""Chunking por estructura, con el baseline conservado como grupo de control.

La decisión central: **cortar por estructura, no por conteo de tokens.**
Un documento en Markdown ya trae su propia segmentación — encabezados, bloques de
código, tablas, listas — y esa segmentación significa algo. Cortar cada N tokens
ignora esa señal y produce fragmentos que empiezan a mitad de una tabla o de una
función.

Las tres decisiones que hay que saber defender:

1. **El conteo de tokens es un techo, no una guía.** Se corta donde la estructura
   lo permite (fin de bloque), y solo se usa el presupuesto de tokens para decidir
   *cuándo* cerrar el fragmento. Un bloque indivisible (código, tabla) que se pasa
   del techo se deja pasar: partir una función por la mitad cuesta más que un
   fragmento grande.
2. **El solapamiento es por bloques, no por tokens.** Repetir los últimos tokens de
   un fragmento corta una frase por la mitad en el borde. Repetir el último *bloque*
   completo (mientras quepa en el presupuesto de overlap) mantiene la coherencia y
   cuesta casi lo mismo.
3. **El encabezado viaja con el fragmento.** Un fragmento se guarda con su ruta de
   encabezados (`H1 › H2`) en el campo `heading`, y además se antepone al texto que
   se vectoriza (`prepend_heading`). Motivo: el embedding de un párrafo suelto no
   sabe de qué documento habla; con el encabezado delante, sí. Sin eso, "Verificado:
   2.95" no se recupera desde la pregunta "¿funciona el ranker en el tier gratis?".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import tiktoken

_ENCODER = tiktoken.get_encoding("cl100k_base")

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*$", re.MULTILINE)
_FENCE = re.compile(r"^\s*(```|~~~)")
_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n{2,}")

# Un bloque indivisible se deja crecer hasta este múltiplo del presupuesto antes de
# que el chunker avise: por encima, el fragmento ya no cabe en un contexto útil.
OVERSIZE_WARN_FACTOR = 2.0


@dataclass
class Chunk:
    """Unidad indexable. `heading` es la ruta de encabezados, no el último título."""

    heading: str
    content: str
    index: int
    tokens: int = 0
    kinds: list[str] = field(default_factory=list)


@dataclass
class Block:
    """Unidad de estructura: no se parte nunca (salvo el párrafo gigante)."""

    kind: str  # heading | code | table | list | para
    text: str
    level: int = 0  # solo para headings
    heading: str = ""


def count_tokens(text: str) -> int:
    return len(_ENCODER.encode(text))


# --------------------------------------------------------------------------- #
# 1. Parseo en bloques
# --------------------------------------------------------------------------- #
def parse_blocks(text: str) -> list[Block]:
    """Markdown → bloques indivisibles, respetando cercas de código.

    El estado importante es `in_fence`: dentro de una cerca, las líneas son texto
    literal. Sin ese estado, un `# comentario` dentro de un bloque de bash se
    confundiría con un encabezado y el fragmento se cortaría por la mitad.
    """
    blocks: list[Block] = []
    buffer: list[str] = []
    in_fence = False
    fence_lines: list[str] = []

    def flush_buffer(kind: str = "para") -> None:
        nonlocal buffer
        if buffer:
            joined = "\n".join(buffer).strip()
            if joined:
                blocks.append(Block(kind=_classify(joined), text=joined))
            buffer = []

    for line in text.splitlines():
        if _FENCE.match(line):
            if in_fence:
                fence_lines.append(line)
                blocks.append(Block(kind="code", text="\n".join(fence_lines)))
                fence_lines = []
                in_fence = False
            else:
                flush_buffer()
                in_fence = True
                fence_lines = [line]
            continue

        if in_fence:
            fence_lines.append(line)
            continue

        match = _HEADING.match(line)
        if match:
            flush_buffer()
            blocks.append(
                Block(kind="heading", text=match.group(2).strip(), level=len(match.group(1)))
            )
            continue

        if not line.strip():
            flush_buffer()
            continue

        buffer.append(line)

    if in_fence:  # cerca sin cerrar: se emite como código, no se pierde
        blocks.append(Block(kind="code", text="\n".join(fence_lines)))
    flush_buffer()
    return blocks


def _classify(text: str) -> str:
    """Párrafo, lista o tabla — cambia cómo se comporta el corte."""
    first = text.lstrip().splitlines()[0]
    if first.startswith("|"):
        return "table"
    if re.match(r"^\s*([-*+]|\d+[.)])\s+", first) or all(
        re.match(r"^\s*([-*+]|\d+[.)])\s+", ln) for ln in text.splitlines() if ln.strip()
    ):
        return "list"
    return "para"


# --------------------------------------------------------------------------- #
# 2. Agrupación con presupuesto
# --------------------------------------------------------------------------- #
def _split_oversized(block: Block, target: int, overlap: int) -> list[Block]:
    """Un párrafo más grande que el presupuesto sí se parte: por oraciones.

    Los bloques de código y las tablas no se parten nunca (ver decisión 1).
    """
    if block.kind in ("code", "table") or count_tokens(block.text) <= target:
        return [block]

    sentences = [s for s in _SENTENCE.split(block.text) if s.strip()]
    pieces: list[Block] = []
    current: list[str] = []
    current_tokens = 0
    for sentence in sentences:
        tokens = count_tokens(sentence)
        if current and current_tokens + tokens > target:
            pieces.append(Block(kind="para", text=" ".join(current)))
            # solapamiento: se arrastra la última oración del fragmento anterior
            carry = [current[-1]] if count_tokens(current[-1]) <= overlap else []
            current = carry
            current_tokens = sum(count_tokens(s) for s in current)
        current.append(sentence)
        current_tokens += tokens
    if current:
        pieces.append(Block(kind="para", text=" ".join(current)))
    return pieces


def chunk_markdown(
    text: str,
    *,
    target_tokens: int = 800,
    overlap_tokens: int = 150,
    prepend_heading: bool = True,
) -> list[Chunk]:
    """Markdown → fragmentos coherentes con su ruta de encabezados.

    `target_tokens` es el techo blando de cada fragmento; `overlap_tokens` es el
    presupuesto que puede repetirse del fragmento anterior, **en bloques completos**.
    """
    blocks = parse_blocks(text)

    # Pila de encabezados: H1 › H2 › H3. Un H2 nuevo descarta los niveles menores.
    stack: list[tuple[int, str]] = []
    chunks: list[Chunk] = []
    pending: list[Block] = []
    pending_tokens = 0
    warned = False
    chunk_heading = ""  # se fija con el primer bloque del fragmento

    def breadcrumb() -> str:
        return " › ".join(title for _, title in stack)

    def emit() -> None:
        nonlocal pending, pending_tokens, warned, chunk_heading
        if not pending:
            return
        body = "\n\n".join(b.text for b in pending).strip()
        if not body:
            pending, pending_tokens = [], 0
            return
        heading = chunk_heading or breadcrumb()
        tokens = count_tokens(body)
        if tokens > target_tokens * OVERSIZE_WARN_FACTOR and not warned:
            print(
                f"  aviso: fragmento de {tokens} tokens > {OVERSIZE_WARN_FACTOR:g}× el techo "
                "(bloque indivisible: código o tabla)"
            )
            warned = True
        content = f"{heading}\n\n{body}" if prepend_heading and heading else body
        chunks.append(
            Chunk(
                heading=heading,
                content=content,
                index=len(chunks),
                tokens=count_tokens(content),
                kinds=[b.kind for b in pending],
            )
        )
        pending, pending_tokens, chunk_heading = [], 0, ""

    for block in blocks:
        if block.kind == "heading":
            # Orden importante: primero se cierra el fragmento pendiente CON la ruta
            # de encabezados vigente, y sólo después se entra en la sección nueva.
            # Al revés, cada fragmento queda etiquetado con el encabezado siguiente
            # — una cita que apunta a la sección equivocada.
            if pending_tokens >= target_tokens * 0.6:
                tail = _overlap_tail(pending, overlap_tokens)
                emit()
                pending = tail
                pending_tokens = sum(count_tokens(b.text) for b in tail)
                chunk_heading = breadcrumb() if tail else ""
            while stack and stack[-1][0] >= block.level:
                stack.pop()
            stack.append((block.level, block.text))
            continue

        for piece in _split_oversized(block, target_tokens, overlap_tokens):
            tokens = count_tokens(piece.text)
            if pending and pending_tokens + tokens > target_tokens:
                tail = _overlap_tail(pending, overlap_tokens)
                emit()
                pending = tail
                pending_tokens = sum(count_tokens(b.text) for b in tail)
                chunk_heading = breadcrumb() if tail else ""
            if not pending:
                chunk_heading = breadcrumb()
            pending.append(piece)
            pending_tokens += tokens

    emit()
    return chunks


def _overlap_tail(blocks: list[Block], budget: int) -> list[Block]:
    """Últimos bloques que caben en el presupuesto de solapamiento (de atrás para
    adelante). Nunca arrastra un bloque de código: repetirlo infla el costo."""
    if budget <= 0:
        return []
    tail: list[Block] = []
    used = 0
    for block in reversed(blocks):
        if block.kind in ("code", "table"):
            break
        tokens = count_tokens(block.text)
        if used + tokens > budget:
            break
        tail.insert(0, block)
        used += tokens
    return tail


# --------------------------------------------------------------------------- #
# 3. Grupo de control
# --------------------------------------------------------------------------- #
def chunk_markdown_naive(
    text: str, *, target_tokens: int = 800, overlap_tokens: int = 150
) -> list[Chunk]:
    """Baseline: ventanas fijas de tokens. Se conserva para medir, no para usar.

    Corta donde caiga el conteo — a mitad de una frase, de una tabla o de una
    función — y arrastra el último encabezado visto como texto. Es el contraste
    honesto contra el que se compara el chunking por estructura.
    """
    tokens = _ENCODER.encode(text)
    if not tokens:
        return []
    step = max(1, target_tokens - overlap_tokens)
    last_heading = ""
    chunks: list[Chunk] = []
    for start in range(0, len(tokens), step):
        window = tokens[start : start + target_tokens]
        if not window:
            break
        body = _ENCODER.decode(window)
        found = _HEADING.search(body)
        if found:
            last_heading = found.group(2).strip()
        chunks.append(
            Chunk(
                heading=last_heading,
                content=body,
                index=len(chunks),
                tokens=len(window),
                kinds=["window"],
            )
        )
        if start + target_tokens >= len(tokens):
            break
    return chunks


# --------------------------------------------------------------------------- #
# 4. Inspección desde la terminal
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Muestra cómo se corta un documento.")
    parser.add_argument("path")
    parser.add_argument("--target", type=int, default=800)
    parser.add_argument("--overlap", type=int, default=150)
    parser.add_argument("--naive", action="store_true", help="corta con el baseline")
    args = parser.parse_args(argv)

    text = Path(args.path).read_text(encoding="utf-8")
    chunks = (chunk_markdown_naive if args.naive else chunk_markdown)(
        text, target_tokens=args.target, overlap_tokens=args.overlap
    )
    print(f"{args.path} → {len(chunks)} chunks ({'naive' if args.naive else 'estructura'})\n")
    for chunk in chunks:
        head = chunk.content.splitlines()[0][:70]
        print(f"[{chunk.index}] {chunk.tokens:4d} tok · {','.join(sorted(set(chunk.kinds)))}")
        print(f"     heading: {chunk.heading or '(ninguno)'}")
        print(f"     first  : {head}…")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
