# Apéndice B — Glosario

**Adaptador (LoRA).** Conjunto de matrices pequeñas que se entrenan al lado de un modelo congelado y
que, sumadas a él, cambian su comportamiento. En este proyecto, 16,5 millones de parámetros, unos
63 MB.

**Allowlist (lista blanca).** Enfoque de seguridad que enumera lo permitido y rechaza todo lo demás.
Lo contrario de una *blacklist* o lista negra, que enumera lo prohibido.

**Apache 2.0.** Licencia de software permisiva: permite el uso comercial, la modificación y la
redistribución, con la condición de incluir una copia de la licencia y conservar los avisos de
autoría.

**Árbol sintáctico (AST).** Representación de un texto de código como una estructura de nodos,
donde cada nodo sabe qué es: una sentencia, una tabla, una columna, una condición. Permite
analizar una consulta SQL con precisión, en vez de buscar palabras.

**bf16 / fp16.** Dos formatos numéricos de media precisión. bf16 es más estable para entrenar,
pero las tarjetas de arquitectura Turing, como la GTX 1660 Ti, solo soportan fp16.

**Checkpoint (punto de control).** Copia del estado completo del entrenamiento en un paso dado, desde
la que se puede continuar si se corta.

**Cuantización.** Reducir los bits con los que se guarda cada peso del modelo. De 16 bits a 4, un
modelo ocupa cuatro veces menos, con una pérdida de calidad pequeña.

**DDL.** *Data Definition Language*: la parte de SQL que define la estructura de las tablas, como
`CREATE TABLE`. En este libro, "el esquema".

**DPO.** Método de entrenamiento que aprende de comparaciones entre pares de respuestas. Usa datos de
preferencias.

**Epoch.** Una vuelta completa al dataset de entrenamiento. Este modelo se entrenó 0,73 epochs.

**Exec match (coincidencia de resultados).** Métrica que compara el resultado de ejecutar la consulta
del modelo con el de la consulta de referencia. Es más justa que comparar el texto.

**Fine-tuning (afinado).** Continuar el entrenamiento de un modelo ya entrenado con datos propios,
para especializarlo en una tarea.

**Firewall SQL.** En este libro, el validador que solo deja pasar una consulta de lectura entre el
modelo y la base de datos.

**Fusionar (merge).** Sumar los pesos de un adaptador a los del modelo base para obtener un modelo
completo, sin adaptador aparte.

**GGUF.** Formato de archivo de los modelos que usa llama.cpp, y con él LM Studio y Ollama. Contiene
los pesos, el vocabulario y metadatos como el nombre y la plantilla de chat.

**grad_norm.** Tamaño de las correcciones que el entrenamiento aplica en cada paso. Si aparece `nan`
o `inf`, el entrenamiento se ha roto.

**Gradient accumulation (acumulación de gradientes).** Procesar varios ejemplos de uno en uno y
aplicar una sola actualización con todos. Simula lotes grandes con la memoria de un lote pequeño.

**Gradient checkpointing.** Guardar solo algunas activaciones intermedias y recalcular las demás
cuando hacen falta. Ahorra mucha memoria a cambio de algo de tiempo.

**Hugging Face.** Plataforma donde se publican y descargan modelos y conjuntos de datos.

**Inyección SQL / apilamiento (stacking).** Ataque que esconde una sentencia peligrosa junto a una
legítima, por ejemplo después de un punto y coma.

**Learning rate (tasa de aprendizaje).** Cuánto cambian los pesos en cada actualización.

**llama.cpp.** Motor de código abierto para ejecutar modelos en formato GGUF en hardware de
consumo.

**LM Studio.** Aplicación de escritorio para descargar, configurar y usar modelos en local, con un
servidor compatible con la API de OpenAI.

**Loss.** Medida de cuánto se equivoca el modelo al predecir las respuestas de entrenamiento. Que
baje significa que imita mejor el dataset, no necesariamente que el modelo sea mejor.

**Model Card.** Ficha de un modelo publicado: qué hace, cómo se midió, cómo se usa, dónde falla y
bajo qué licencia.

**NOTICE.** Archivo de atribución que acompaña a una obra derivada, como exige la licencia Apache
2.0.

**Ollama.** Herramienta de línea de comandos para ejecutar modelos en local, configurados con un
`Modelfile`.

**Plantilla de chat.** Pequeño programa, escrito en Jinja, que convierte una conversación en el
texto exacto que lee el modelo, con sus marcas especiales.

**Q4_K_M.** Método de cuantización de GGUF que guarda la mayoría de los pesos en unos 4 bits, con
más precisión en las partes sensibles. Equilibrio habitual entre tamaño y calidad.

**QLoRA.** Afinado con adaptadores LoRA sobre un modelo base cuantizado a 4 bits. Permite afinar
modelos de varios miles de millones de parámetros en tarjetas de consumo.

**SFT (Supervised Fine-Tuning).** Afinado supervisado: el modelo aprende a imitar las respuestas de
los ejemplos.

**sqlglot.** Librería de Python que analiza, transforma y traduce SQL entre dialectos.

**System prompt.** Mensaje inicial que define el papel del modelo en una conversación.

**Temperatura.** Cuánta aleatoriedad usa el modelo al elegir cada token. Con 0, elige siempre el más
probable.

**Token.** Unidad mínima de texto que procesa el modelo: una palabra, parte de una palabra o un
símbolo. Los **tokens especiales**, como `<|im_start|>` o `<think>`, marcan la estructura de la
conversación.

**Text-to-SQL.** Tarea de convertir una pregunta en lenguaje natural en una consulta SQL.
