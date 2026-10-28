# Fragmentación (chunking) en RAG

## Por qué se fragmenta
Un modelo de recuperación no puede indexar un documento entero con precisión: si el
fragmento es enorme, el vector representa un promedio vago de muchos temas y la
búsqueda pierde resolución. Si es diminuto, el fragmento pierde el contexto que le
da sentido. El tamaño del fragmento es una decisión de compromiso, no un valor
mágico.

## Solapamiento
El **solapamiento** (overlap) repite una porción del final de un fragmento al
comienzo del siguiente. Sirve para que una idea que cae justo en el corte no quede
partida en dos mitades inútiles: al menos uno de los dos fragmentos la contiene
completa. Un solapamiento típico es del 10 al 20 por ciento del tamaño del fragmento.
El costo es almacenamiento y redundancia en los resultados.

## Corte por estructura
Cortar por encabezados, listas y bloques de código produce fragmentos coherentes
para un humano y mejores vectores. Un fragmento que empieza a mitad de una tabla
suele recuperarse mal. Cuando el documento tiene estructura, la estructura manda
sobre el conteo de tokens; el conteo se usa como límite superior.

## Metadatos
Cada fragmento debe conservar de dónde vino: ruta del documento, encabezado activo y
posición. Sin metadatos no hay cita, y sin cita el sistema no es verificable.
