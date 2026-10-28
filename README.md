# mk-rag-lab

**RAG sobre un corpus de documentos con Azure OpenAI + Azure AI Search, y una evaluación que se puede volver a correr.**

El artefacto no es el chat: es la tabla de métricas y el código que la produce.

```
corpus/ ──ingest──► chunks + embeddings ──► Azure AI Search (índice vectorial + BM25)
                                                     │
consulta ────────────────────────────► retrieve ◄───┘   keyword · vector · hybrid(+rerank)
                                             │
                                             ▼
                                    respuesta con citas
```

## Estado

| bloque | estado |
|---|---|
| 0 · cuenta y recursos | ✅ provisionado (ver *Entorno*) |
| 1 · ingesta | ✅ chunking por estructura + baseline medible |
| 2 · recuperación | ✅ tres modos (+ ranker semántico) — **pendiente: tus decisiones con números** |
| 3 · API con streaming | ⬜ `mk_rag_lab/api.py` |
| 4 · MCP + UI + entrega | ⬜ |

## Quickstart

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e .
.venv/bin/python scripts/check_azure.py          # las tres patas: embeddings, chat, índice
.venv/bin/python -m mk_rag_lab.ingest --corpus corpus/public --recreate
.venv/bin/python -m mk_rag_lab.search "tu pregunta" --mode hybrid --semantic
.venv/bin/python eval/run.py
```

Las credenciales **no viven en el repo**: el código lee
`/mk-rag-lab/env` (modo 600) o la ruta que indique
`MK_RAG_ENV_FILE`. Ver `.env.example` para los nombres.

## Chunking: dos estrategias, medidas

`chunking.py` expone la estrategia por estructura (por defecto) y conserva el
baseline de ventanas fijas como **grupo de control**, para que la comparación sea
reproducible y no una opinión:

```bash
# el mismo corpus, dos estrategias, dos índices
uv run python -m mk_rag_lab.ingest --corpus corpus/public --recreate --strategy structure --target 150 --overlap 50
uv run python -m mk_rag_lab.ingest --corpus corpus/public --recreate --strategy naive    --target 150 --overlap 50 --index mk-rag-lab-naive
```

Con techo de 150 tokens sobre el corpus público (5 documentos, ~900 palabras):

| estrategia | chunks | cercas de código partidas | citas con sección exacta |
|---|---|---|---|
| estructura | 12 | 0 | sí (`… › Contrato de la respuesta`) |
| naive | 14 | 1 de 14 | a veces (a veces solo el título del documento) |

Las tres decisiones y su porqué están en el docstring de `chunking.py`. La prueba de
que el baseline falla de verdad vive en `tests/test_chunking.py`: un bloque de código
más grande que la ventana del baseline termina partido por la mitad.

## Métricas

`eval/run.py` escribe `eval/results.md` con **hit@1, hit@5 y MRR**. La posición del
acierto importa: acertar en el puesto 1 y acertar en el 5 no son el mismo sistema, y
un hit@5 agregado esconde esa diferencia. El MRR premia que el acierto esté arriba.

Última corrida (3 preguntas, 12 chunks):

| modo | hit@1 | hit@5 | MRR | p50 (ms) | p95 (ms) |
|---|---|---|---|---|---|
| keyword | 67 % | 100 % | 0.833 | 146 | 1672 |
| vector | 100 % | 100 % | 1.000 | 398 | 2118 |
| hybrid | 67 % | 100 % | 0.833 | 439 | 624 |

### El nivel de azar, antes de creerle a un número

`eval/chance.py` mide qué tan bueno es el eval mismo:

```bash
uv run python eval/chance.py
# corpus: 12 chunks · top-5 → azar analítico 5/12 = 42 %
# azar empírico (consultas ajenas al corpus): 12/30 = 40 %
```

Con 12 chunks y top-5, **cuatro de cada diez aciertos ocurren por suerte**: un 100 %
de hit@5 sobre 3 preguntas es perfectamente compatible con el azar. El eval necesita
~30 documentos y preguntas que crucen dos fuentes — y algunas cuya respuesta **no**
esté en el corpus, que son las únicas que revelan si el sistema alucina.

## Entorno (lo que este recurso permite, medido)

- **Azure for Students**, región del recurso `eastus2` para OpenAI.
- **`gpt-5-mini`** (GlobalStandard, 50k TPM de 500k disponibles) es el único modelo de
  chat con cuota. Toda la familia `gpt-6-*` y los `*-nano` están en **0/0**: existen
  en el catálogo y no se pueden desplegar sin una solicitud de cuota.
- **`text-embedding-3-small`**, 1536 dimensiones.
- **AI Search tier Free** (50 MB, 3 índices) en `eastus`: `eastus2` estaba sin
  capacidad y otras tres regiones las rechazó una política de Azure (un servicio
  gratuito por suscripción).
- **El ranker semántico sí funciona en el tier gratuito** en esta región — la página
  de precios dice lo contrario. Verificado: `rerank=2.95` en la primera consulta.

## Dos decisiones documentadas

1. **Embeddings en el cliente, no en el servicio.** La consulta se vectoriza con el
   mismo `embed()` que usa la ingesta (`VectorizedQuery`), en vez de declarar un
   *vectorizer* en el perfil del índice (`VectorizableTextQuery`). Un solo modelo, un
   solo camino, y el índice no queda atado a un recurso de OpenAI. El costo es un
   viaje de ida y vuelta extra por consulta.
2. **La evaluación vive en el repo.** `eval/questions.jsonl` es el contrato: cada
   pregunta declara qué cadenas debe recuperar el top-5. Sin eso, "funciona" es una
   opinión.

## Corpus

- `corpus/public/` — material público, lo que se commitea y se puede deployar.
- `corpus/private/` — gitignoreado. Se indexa localmente y **nunca** sale de la
  máquina: es para la demo privada, no para el deploy.

## Lo que falta, en orden

1. **Chunking propio** (corte por estructura, tamaño y solapamiento justificados) y
   la comparación contra el baseline en el eval.
2. **Rerank y modos**: decidir cuándo híbrido y cuándo basta keyword, con números.
3. **`api.py`**: FastAPI + SSE + citas en el payload.
4. **MCP** (`search_docs`, `ask`) + UI con streaming + Dockerfile en el Pi.
