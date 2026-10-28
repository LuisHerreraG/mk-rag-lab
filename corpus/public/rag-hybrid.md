# Búsqueda híbrida

## Dos señales distintas
La búsqueda por **palabra clave** (BM25) puntúa coincidencias exactas de términos,
con peso por frecuencia y rareza. Es fuerte en nombres propios, siglas, códigos y
números de versión. La búsqueda **vectorial** compara embeddings: encuentra texto
que significa lo mismo con otras palabras, y falla con identificadores exactos que
nunca vio.

## Fusión
La búsqueda **híbrida** ejecuta ambas y combina los resultados. Azure AI Search usa
Reciprocal Rank Fusion (RRF) por defecto: cada lista aporta según la posición del
resultado, no según su puntaje crudo, porque los puntajes de dos motores distintos
no son comparables entre sí.

## Reranking
Sobre el resultado fusionado se puede aplicar un **reranker** semántico, que relee la
consulta y los fragmentos con un modelo más caro y reordena solo el top. El
reranking suele mejorar la precisión del primer resultado; no mejora el recall,
porque no trae documentos que la recuperación no encontró.

## Cuándo no usarla
Si el corpus es diminuto y el vocabulario cerrado, la búsqueda por palabra clave
basta. La hibridación se paga en latencia y en complejidad; se adopta cuando hay
evidencia de que una sola señal falla.
