"""Generación — la G de RAG. Convertir fragmentos recuperados en una respuesta citada.

La regla del módulo, y la única que importa: **el modelo responde con el contexto
recuperado o dice que no está.** No hay tercera opción. Un RAG que improvisa cuando
el contexto no alcanza es más peligroso que un buscador, porque suena seguro.

Tres decisiones:

1. **El contexto va numerado `[1]…[n]`** y el modelo cita con ese número. La cita no
   la inventa el modelo: la resuelve este módulo contra el fragmento n, así que un
   `[3]` siempre apunta al fragmento 3 y no a una paráfrasis de la ruta.
2. **El prompt prohíbe el conocimiento previo**, explícitamente y con la frase de
   negativa incluida, para que "no está en las fuentes" sea una salida de primera
   clase y no un fallo.
3. **La respuesta se arma por streaming**, token a token: la primera palabra sale
   antes de que el modelo termine. La latencia percibida baja a la latencia del
   primer token, y eso es lo que el usuario siente.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from .clients import chat, settings
from .search import Hit

REFUSAL = "No está en las fuentes que tengo indexadas."

SYSTEM_PROMPT = f"""Sos un asistente que responde únicamente con el CONTEXTO entregado.

Reglas, en orden de prioridad:
1. Usá sólo el CONTEXTO. No uses conocimiento propio, no completes huecos, no supongas.
2. Citá cada afirmación con el número del fragmento entre corchetes: [1], [2].
3. Si el CONTEXTO no alcanza para responder, respondé exactamente: "{REFUSAL}"
   Esa frase de negativa va SOLA: sin números, sin corchetes, sin explicaciones."
4. Si el contexto responde en parte, respondé esa parte y aclarí qué falta.
5. Respondé en español, breve y concreto. Sin preámbulos ni disculpas.
"""


@dataclass
class Citation:
    number: int
    path: str
    heading: str
    tokens: int

    def __str__(self) -> str:
        anchor = f"{self.path} › {self.heading}" if self.heading else self.path
        return f"[{self.number}] {anchor}"


@dataclass
class Answer:
    text: str
    citations: list[Citation]
    model: str


def build_context(hits: list[Hit]) -> tuple[str, list[Citation]]:
    """Fragmentos → bloque numerado + la lista de citas resueltas."""
    blocks, citations = [], []
    for number, hit in enumerate(hits, 1):
        anchor = f"{hit.path} › {hit.heading}" if hit.heading else hit.path
        blocks.append(f"[{number}] ({anchor})\n{hit.content.strip()}")
        citations.append(
            Citation(
                number=number, path=hit.path, heading=hit.heading, tokens=len(hit.content)
            )
        )
    return "\n\n".join(blocks), citations


def build_messages(question: str, hits: list[Hit]) -> list[dict[str, str]]:
    context, _ = build_context(hits)
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"CONTEXTO:\n{context}\n\nPREGUNTA: {question}",
        },
    ]


_CITE_RE = __import__("re").compile(r"\s*\[\d+\]")


def _clean_refusal(text: str) -> str:
    """Una negativa no cita: si el modelo le pegó un [1], se lo saca.

    Barato de arreglar en el camino sin streaming; en el streaming manda el prompt,
    porque no hay texto completo que corregir hasta que termina.
    """
    stripped = text.strip()
    if stripped.startswith(REFUSAL):
        return REFUSAL
    return _CITE_RE.sub("", stripped) if REFUSAL in stripped else stripped


def answer(question: str, hits: list[Hit]) -> Answer:
    """Respuesta completa (sin streaming) — para el CLI y para los tests.

    Sin `temperature`: **gpt-5-mini sólo acepta la temperatura por defecto (1)**; pasar
    `temperature=0` devuelve 400. Consecuencia para el eval: la generación no es
    determinista, así que las métricas de recuperación son las reproducibles y las de
    respuesta no. Si algún día se compara calidad de respuesta, hay que fijar `seed`
    o promediar varias corridas.
    """
    text = _clean_refusal(chat(build_messages(question, hits)))
    _, citations = build_context(hits)
    return Answer(text=text, citations=citations, model=settings().chat_deployment)


def stream_answer(question: str, hits: list[Hit]) -> Iterator[str]:
    """Tokens a medida que llegan. El llamador decide qué hacer con ellos."""
    from .clients import openai_client

    stream = openai_client().chat.completions.create(
        model=settings().chat_deployment,
        messages=build_messages(question, hits),
        stream=True,
    )
    for event in stream:
        if not event.choices:
            continue
        delta = event.choices[0].delta.content
        if delta:
            yield delta


def main(argv: list[str] | None = None) -> int:
    import argparse

    from .search import retrieve

    parser = argparse.ArgumentParser(description="Pregunta al corpus, con citas.")
    parser.add_argument("question")
    parser.add_argument("--mode", default="hybrid")
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--semantic", action="store_true")
    parser.add_argument("--index", default=None)
    parser.add_argument("--no-stream", action="store_true")
    args = parser.parse_args(argv)

    hits = retrieve(
        args.question, mode=args.mode, top=args.top, semantic=args.semantic, index=args.index
    )
    if not hits:
        print(REFUSAL)
        return 0

    if args.no_stream:
        result = answer(args.question, hits)
        print(result.text)
        print("\nFuentes:")
        for citation in result.citations:
            print(" ", citation)
        return 0

    for token in stream_answer(args.question, hits):
        print(token, end="", flush=True)
    print("\n\nFuentes:")
    for citation in build_context(hits)[1]:
        print(" ", citation)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
