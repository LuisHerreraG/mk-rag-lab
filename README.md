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
| 3 · generación + API | ✅ respuesta con citas, SSE, negativa explícita |
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
`~/.config/mk-rag-lab/env` (modo 600) o la ruta que indique `MK_RAG_ENV_FILE`. Ver `.env.example` para los nombres.

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

## Generación con citas (`rag.py` + `api.py`)

```bash
./ask.sh                                        # bucle de preguntas (lo más rápido para probar)
uv run python -m mk_rag_lab.rag "¿qué mide hit@5?" --semantic             # una sola, streaming
uv run uvicorn mk_rag_lab.api:app --port 8080                             # API
curl -N "http://127.0.0.1:8080/ask?q=¿qué+mide+hit@5?&semantic=true"      # eventos SSE
```

El REPL no tiene memoria de conversación a propósito: cada turno se recupera desde cero,
así lo que se evalúa es la misma cosa que se mide en `eval/run.py`.

El contrato de `/ask` es `text/event-stream` en tres pasos: **citas primero**, después un
evento por token, y al final `done` con el modelo y la latencia. Las citas van antes que
la primera palabra a propósito: nadie lee una afirmación sin poder ver la fuente.

Tres reglas duras del módulo:

1. **Responde con el contexto o dice que no.** Una pregunta fuera del corpus devuelve
   `"No está en las fuentes que tengo indexadas."`, sin citas pegadas.
2. **La cita la resuelve el código, no el modelo.** El `[3]` del texto siempre apunta
   al fragmento 3 de la lista que se envió.
3. **`/health` y `/ask`** comparten proceso; con `RAG_API_KEY` definida, `/ask` exige
   el header `x-api-key` (401 sin él, verificado).

**Dos datos de `gpt-5-mini` que afectan al eval y al costo:**

- **No acepta `temperature=0`** (400: sólo la default, 1). La recuperación es
  reproducible; la generación no. Comparar calidad de respuesta exigiría `seed` o
  promediar corridas.
- **`max_completion_tokens` incluye los tokens de razonamiento**, que no se ven. Con un
  techo de 400 el modelo devuelve **texto vacío de forma intermitente**. El default es
  1200, y si la respuesta sale vacía la API emite `event: error` en vez de un stream
  vacío silencioso.

## Costo y exposición

- **Comparar vectores no se factura por consulta.** La búsqueda se cobra por capacidad
  (Search units/mes); en el tier Free es **$0**. La similitud coseno es cómputo interno
  del servicio.
- **El ranker semántico sí tiene tope**: **1.000 consultas gratis al mes**, después
  ~$1 por 1.000. Es el límite que hay que mirar si el demo se hace público.
- **El costo real son los tokens** de embeddings y de chat, no la búsqueda.
- Por eso `/ask` trae **límite por IP** (`RAG_RATE_LIMIT`, 10/min por defecto), **techo de
  tokens por respuesta** (`RAG_MAX_TOKENS`) y **API key opcional** (`RAG_API_KEY`). Debajo
  de Tailscale no hace falta ninguna; expuesto a internet, las tres son obligatorias.
- **El repo no lleva secretos**: las credenciales viven en
  `~/.config/mk-rag-lab/env` (600) y `.env` está gitignoreado. Verificado
  también en el historial de git: nunca se commiteó una clave.

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
