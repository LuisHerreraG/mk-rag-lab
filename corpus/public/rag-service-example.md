# Ejemplo de servicio RAG

## Endpoint de consulta

El servicio expone una sola ruta que recibe la pregunta y devuelve la respuesta con
sus citas, en streaming. El contrato es mínimo a propósito: el cliente no necesita
saber cuántos modos de recuperación existen por dentro.

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI()

@app.get("/ask")
def ask(q: str) -> StreamingResponse:
    hits = retrieve(q, mode="hybrid", semantic=True, top=5)
    return StreamingResponse(generate(q, hits), media_type="text/event-stream")
```

## Contrato de la respuesta

| campo | tipo | descripción |
|---|---|---|
| answer | str | texto generado, citando fragmentos |
| citations | list | ruta, encabezado y posición de cada fragmento usado |
| model | str | deployment que respondió, para poder auditar |

## Qué no hace el servicio

No reescribe la pregunta, no reordena más allá del reranker y no guarda historial. Cada
una de esas decisiones tiene un costo en latencia y otro en superficie de error.
