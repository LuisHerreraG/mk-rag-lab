# Evaluación de un sistema RAG

## Qué se mide y qué no
La evaluación de recuperación mide si el material correcto llega al contexto. La
métrica más simple es **hit@5**: la proporción de preguntas en las que al menos uno
de los cinco fragmentos recuperados contiene la respuesta esperada. Es una métrica
generosa: no distingue si el fragmento correcto estaba primero o quinto, y no dice
nada sobre la calidad de la respuesta generada.

## Métricas complementarias
- **MRR** (mean reciprocal rank): premia que el acierto esté arriba.
- **Precisión del contexto**: cuántos de los fragmentos recuperados eran relevantes.
- **Fidelidad**: si la respuesta generada se sostiene en el contexto recuperado.
- **Latencia** p50 y p95: la cola es lo que el usuario percibe.
- **Costo por consulta**: tokens de entrada y salida, más el costo de la recuperación.

## Un conjunto de preguntas honesto
Un conjunto útil mezcla preguntas fáciles, preguntas que exigen cruzar dos
documentos y preguntas cuya respuesta no está en el corpus. Estas últimas son las
que revelan si el sistema alucina: la respuesta correcta es "no está en las fuentes".

## Reproducibilidad
La evaluación debe correr con un comando, sobre un corpus congelado, y escribir un
resultado versionado. Un número que no se puede volver a producir no es evidencia.
