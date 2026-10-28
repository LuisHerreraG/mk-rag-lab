"""La generación con citas: numeración, contexto y negativa."""

from __future__ import annotations

from mk_rag_lab.rag import REFUSAL, _clean_refusal, build_context, build_messages
from mk_rag_lab.search import Hit

HITS = [
    Hit(path="a.md", heading="Sección A", content="contenido uno", score=1.0),
    Hit(path="b.md", heading="", content="contenido dos", score=0.5),
]


def test_context_is_numbered_in_order():
    context, citations = build_context(HITS)
    assert context.startswith("[1] (a.md › Sección A)")
    assert "[2] (b.md)" in context
    assert [c.number for c in citations] == [1, 2]


def test_messages_put_context_before_question():
    messages = build_messages("¿qué dice?", HITS)
    assert messages[0]["role"] == "system"
    assert REFUSAL in messages[0]["content"], "el prompt debe ofrecer la salida de negativa"
    user = messages[1]["content"]
    assert user.index("CONTEXTO:") < user.index("PREGUNTA:")


def test_refusal_never_carries_a_citation():
    assert _clean_refusal(f"{REFUSAL} [1]") == REFUSAL
    assert _clean_refusal("No está en las fuentes que tengo indexadas.") == REFUSAL


def test_answer_keeps_its_citations():
    # lo contrario del test anterior: en una respuesta real las citas NO se tocan
    text = "El hit@5 mide [1] la proporción de aciertos en el top 5 [2]."
    assert _clean_refusal(text) == text
