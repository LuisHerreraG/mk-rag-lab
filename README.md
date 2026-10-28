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
| 1 · ingesta | ✅ baseline funcionando — **pendiente: tu chunking** |
| 2 · recuperación | ✅ tres modos — **pendiente: tu rerank y tus decisiones** |
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

## Métricas

Última corrida (`eval/run.py`, 3 preguntas, 4 documentos):

| modo | hit@5 | p50 (ms) | p95 (ms) |
|---|---|---|---|
| keyword | 100 % | 149 | 1042 |
| vector | 100 % | 429 | 1495 |
| hybrid | 100 % | 444 | 1329 |
| hybrid + semántico | — | — | — |

> Con 4 documentos el hit@5 no discrimina: cualquier modo acierta. La tabla sirve
> cuando el corpus llega a ~30 documentos y las preguntas incluyen las que cruzan
> dos fuentes y las que **no** tienen respuesta en el corpus.

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
