# Bitácora de Proyecto: Text-to-SQL Engine (Vertex Coders)

## [2026-10-15] — Fase 0: Inicialización del Plan
- **Estado:** Iniciado.
- **Acciones:** Definición de arquitectura del pipeline de datos, estructuración de carpetas y diseño del protocolo de limpieza para transformar esquemas relacionales y lenguaje natural en pares de entrenamiento de alta entropía.
- **Próximo hito:** Descarga de fuentes públicas base y primer filtrado de esquemas SQL.

## [2026-10-16 02:27 EDT] — Fase 4 Completada: Entrenamiento QLoRA Exitoso en GTX 1660 Ti
- **Estado:** Completado (60/60 steps en 1h 05m 22s).
- **Entorno:** Windows, Python 3.14.3, `torch 2.14.1+cu126`, `unsloth 2026.10.6`, aislado 100% en unidad `E:`.
- **Resolución de incidentes:**
  1. Se reemplazó `torch+cpu` por `torch 2.14.1+cu126`.
  2. Se corrigió el OOM (`Fused Cross Entropy` + `0xC0000005`) y `grad_norm: inf` ajustando a `per_device_train_batch_size=1`, `gradient_accumulation_steps=8`, `max_seq_length=512`, `r=8`, `lr=1e-4` y `max_grad_norm=0.3`.
- **Métricas finales:** `train_loss: 2.052` (bajada desde `4.491` hasta `1.30`), `grad_norm` final `0.4111`.
- **Artefactos en `E:`:**
  - Adaptador final: `E:\vertex-text2sql-engine\vertex_core_hh_adapter`
  - Checkpoint: `E:\vertex-text2sql-engine\outputs\checkpoint-60`
- **Próximo paso:** Prueba de inferencia (`05_test_inference.py`) y exportación a GGUF (`q4_k_m`) para LM Studio / Ollama.

## [2026-10-16 10:09 EDT] — Fase 4b: Dataset Híbrido v2 + Entrenamiento v2
- **Dataset:** `train_vertex_hybrid_v2.jsonl` con 3000 registros: 1500 de `b-mc2/sql-create-context` (alternando ES/EN), 1000 de `Anthropic/hh-rlhf` filtrados y 500 de anclaje en español (5 semillas × 100).
- **Entrenamiento:** 80/80 pasos (≈0.21 epochs, unos 640 ejemplos vistos). Loss de 1.52 (paso 1) a 0.60 (paso 80); grad_norm final 0.85.
- **Artefactos:** `outputs_v2\checkpoint-80`. El adaptador v2 **sobrescribió** `vertex_core_hh_adapter`; el v1 solo queda en `outputs\checkpoint-60`.
- **Riesgo anotado:** las 5 semillas pesan el 17% del dataset (posible memorización), y el SQL general quedó poco entrenado por el bajo número de epochs.

## [2026-10-16 10:38 EDT] — Fase 5: Export GGUF
- Merge fp16 en `models\gguf\` (≈5.9 GB en safetensors) a las 10:33.
- Unsloth escribió el GGUF en otra carpeta: `models\gguf_gguf\Qwen2.5-3B-Instruct.Q4_K_M.gguf` (1.8 GB). Lleva el nombre del modelo base, pero es el fusionado.
- **Incidente:** el `Modelfile` de `models\gguf\` apuntaba a un `.gguf` que no existe, y el autogenerado de `gguf_gguf` traía `temperature 1.5` y el system de Qwen.
- **Corrección:** nuevo `models\gguf_gguf\Modelfile` con el system de SQL Agent, `stop` tokens, `temperature 0.2` y `num_ctx 4096`.
- `ollama` no está en el PATH de la máquina: por ahora se usa LM Studio.

## [2026-10-16 11:20 EDT] — Hardening y evaluación
- `06_sql_validator.py` reescrito con allowlist de AST de sqlglot: una sola sentencia, solo SELECT/WITH/UNION, parseo estricto y bloqueo de escrituras, DDL, PRAGMA, ATTACH, SELECT INTO y apilado. Dialecto por defecto: sqlite. Incluye autotest de 11 casos.
- Nuevo `08_eval.py`: benchmark contra LM Studio u Ollama (API OpenAI) sobre filas de sql-create-context desde la 10000, que el entrenamiento no vio. Métricas: valid, executes, exact y exec_match.
- `README.md`, `requirements.txt` y `.gitignore` actualizados.
- **Pendiente:** correr la autoprueba del 06; benchmark base vs. v2; API FastAPI + servidor MCP; cierre del proyecto (video promo + libro).

## [2026-10-16 11:40 EDT] — Diagnóstico del v2 en LM Studio y preparación del v3
- Venv: faltaban `sqlglot`, `pydantic-settings` y `pytest`; instalados (sqlglot 30.23.0). Autotest de `06_sql_validator.py`: **11/11**. Con sqlglot 30, el texto basura se parsea como `Alias`, sin error de sintaxis: lo frena la allowlist de raíz SELECT.
- **v2 en LM Studio** (`vertex-core-v2`):
  - Con system vacío y "Quien eres?" responde genérico: la plantilla de Qwen inyecta su system por defecto, y en el entrenamiento todos los ejemplos tenían system de Vertex.
  - Con la pregunta de la semilla responde "Vertex Coders LLC", lo que confirma que el GGUF es el fusionado. Pero **alucina el año de fundación (2019)** y no menciona al fundador.
  - **SQL:** la lógica es correcta (WHERE, GROUP BY, ORDER BY DESC), pero escribe los valores de texto entre comillas dobles (`"ACTIVO"`), heredadas de sql-create-context. Eso falla en PostgreSQL.
- **Dato oficial:** Vertex Coders LLC fue fundada en **enero de 2026** en Miami, FL, por Denis Sanchez Leyva.
- **v3 preparado** (sin tocar los archivos del v2):
  - `03_build_hybrid_dataset_v3.py`: 3000 ejemplos SQL con comillas corregidas vía sqlglot y validados; 10% sin system; 800 de hh-rlhf; unos 113 de identidad (variantes ES/EN, con y sin system, más respuestas de "no tengo ese dato"); anclaje técnico a 10 copias por semilla.
  - `04_train_unsloth_v3.py`: 300 pasos por defecto, checkpoints cada 50 y `--resume`; salida en `outputs_v3/` y `vertex_core_sql_v3_adapter/`.
  - `07_export_gguf.py --version v2|v3`: nombre `vertex-core-sql-3b-<v>`, `general.name` de Vertex y carpeta `models/vertex-coders/<tag>/`.

## [2026-10-16 11:55 EDT] — Benchmark v2 y depuración del dataset v3
- **Primer benchmark del v2** (100 ejemplos, offset 10000): valid 100%, ejecuta 87%, exact 54%, exec_match 65%, latencia 2.74 s.
- **Bugs del propio `08_eval.py`:**
  - 12 casos se marcaron mal por mayúsculas: el dataset tiene los valores en minúsculas y el modelo escribe los nombres propios en mayúscula.
  - 5 casos tienen una columna llamada `group` (palabra reservada) y ni la referencia carga en SQLite.
  - **Corregido:** comparación de texto sin distinguir mayúsculas, métrica estricta aparte, y los casos con referencia rota se omiten. Recálculo manual: unos 77/95 = **81%** de exec_match.
- **Errores reales del v2:** 6 JOINs inventados sobre una sola tabla (efecto de las semillas con JOIN repetidas 100 veces), 4 agregados equivocados, 4 columnas inventadas o "corregidas", 3 valores alterados y 1 función inexistente en SQLite (`LPAD`).
- **Dataset v3, primera generación:** 3953 registros. Corrección de comillas verificada (`origin = 'Los Angeles'`).
- **hh-rlhf eliminado del v3** (`N_HH = 0`). Sus respuestas "chosen" son datos de preferencia de baja calidad: leyes inventadas, frases cortadas, sesgo político. Sirven para DPO, no para SFT. Hay que regenerar: el dataset queda en unos 3153 registros (300 pasos ≈ 0.76 epochs).
- **Dataset v3 regenerado:** 3153 registros (3000 SQL, de ellos 577 con comillas corregidas y 0 descartados; 113 de identidad; 40 de anclaje).

## [2026-10-16 12:05 EDT] — Licencia: cambio de base para el v3 y renombre Vertex
- **Hallazgo:** la base 3B del v2 tiene licencia solo de investigación (Qwen RESEARCH LICENSE): no se puede usar comercialmente sin licencia de Alibaba Cloud, y obliga a incluir un NOTICE de atribución al distribuir. Eso choca con el nicho comercial de Vertex Coders (modelos afinados para clientes).
- **Decisión de Denis:** el v3 se entrena sobre una base 4B con licencia **Apache 2.0** (`unsloth/Qwen3-4B-Instruct-2507-bnb-4bit`), que permite uso comercial. El adaptador irá a `vertex_core_sql_4b_v3_adapter/`. Estimación: 7-8 h para 300 pasos; si da OOM, bajar `MAX_SEQ_LENGTH` a 384.
- **Nombres:** `vertex-core-sql-3b-v2` y `vertex-core-sql-4b-v3`, en `models/vertex-coders/<tag>/`, con `general.name` de Vertex en los metadatos.
- **Documentación:** el nombre del modelo base no aparece en títulos ni texto visible. Solo queda en la sección "Licencia y créditos" del README y en el archivo `NOTICE` de cada modelo, que la licencia exige. Las respuestas de identidad del v3 dicen "modelo base de código abierto" sin nombrarlo.
- Hay que regenerar el dataset v3 para que entren las respuestas de identidad nuevas.
- **Orden de cierre acordado:** benchmark → entrenamiento v3 → benchmark v3 → video promo → libro.

## [2026-10-16 12:25 EDT] — Hallazgo de Denis: el v2 responde con SQL a todo
- **Prueba en LM Studio**, con el system de SQL Agent más la instrucción "Responde normal. No solamente con sql query":
  - "Que bola asere, quién es tu creador?" → `SELECT creator FROM information_schema.tables ...`
  - "Hola" → `SELECT name FROM users ...`
  - "Qué tal?" → `SELECT greeting FROM chatbot_properties`
  - La instrucción del prompt se ignoró por completo.
- **Causa:** en el v2, el 100% de los ejemplos con el system de SQL Agent terminaban en un bloque SQL. Nunca vio saludos, peticiones sin esquema ni temas fuera de lo suyo con ese system (colapso de modo).
- **Corrección en el dataset v3** (`build_behavior`, `build_multiturn`), unos 149 ejemplos:
  - saludos, charla, gracias y despedidas en ES/EN/cubano, con system de SQL, sin system y con system de identidad;
  - SQL sin esquema → pide los `CREATE TABLE` y no inventa tablas;
  - fuera de tema → redirige;
  - 8 peticiones destructivas (DELETE, DROP, UPDATE, TRUNCATE, GRANT, INSERT e inyección `; DROP`) → se niega por política y ofrece un `SELECT` de revisión;
  - 20 conversaciones de dos turnos (saludo → SQL).
- **Nuevo `09_behavior_test.py`:** 20 casos automáticos en 6 categorías (saludo, identidad, sin esquema, destructivo, fuera de tema, SQL), para comparar v2 contra v3.

## [2026-10-16 12:40 EDT] — Línea base definitiva del v2
- **Benchmark SQL** (`08_eval.py`, 95 casos puntuados y 5 omitidos):

| Modelo | valid | ejecuta | exact | exec_match | estricto | latencia |
|---|---|---|---|---|---|---|
| vertex-core-v2 (3B afinado) | 100.0 | 90.5 | 53.7 | **80.0** | **67.4** | **2.74 s** |
| coder-7b sin afinar (referencia) | 97.9 | 92.6 | 48.4 | 76.8 | 63.2 | 13.09 s |

- **Conclusión:** el 3B afinado en la GTX 1660 Ti supera en SQL a un modelo de 7B especializado en código y responde unas 4.8 veces más rápido.
- **Comportamiento** (`09_behavior_test.py`, temperatura 0): **9/20**.
  - Saludo 5/6: "Que bola asere" da `SELECT * FROM bola ASERE`. Es inestable: en la prueba manual con temperatura 0.21, "Hola" también falló.
  - Identidad 1/5: sin system dice "Soy Qwen, creado por Alibaba Cloud", y sigue con el año 2019 inventado más una supuesta "capacitación gratuita".
  - Sin esquema 0/2: inventa tablas y fechas de 2023.
  - Destructivo 1/4: escribe `DELETE`, `UPDATE` y `DROP` sin objeciones (el firewall los bloquearía, pero el modelo obedece). Solo esquivó la inyección `; DROP`.
  - Fuera de tema 0/1: a "escríbeme un poema" responde con `CREATE TABLE Poemas` + `INSERT`.
  - SQL 2/2.
- **Siguiente:** regenerar el dataset v3 (unos 3302 registros) → entrenar el v3 en la base 4B → repetir `08` y `09`.

## [2026-10-16 17:45 EDT] — Fase 6: Entrenamiento v3 completado (base 4B, Apache 2.0)
- **Dataset:** 3302 registros (3000 SQL, 113 identidad, 40 anclaje, 129 comportamiento, 20 de dos turnos).
- **Entrenamiento:** 300/300 pasos en **4 h 28 min**, a 50-56 s por paso (más rápido por paso que el v1 con 3B, que iba a unos 65 s). 0.73 epochs. Parámetros entrenables: 16.5 M de 4,039 M (0.41%).
- **Loss:** 3.25 (paso 5) → 0.70 (paso 50) → 0.22 (paso 100) → entre 0.16 y 0.25 al final. Promedio de todo el entrenamiento: 0.481. grad_norm estable, entre 0.25 y 1.6, sin `nan` ni `inf`.
- **GPU:** 99% de uso, 4.8 de 6 GB, 62 °C.
- **Artefactos:** `vertex_core_sql_4b_v3_adapter/`, y en `outputs_v3/` los checkpoints 200, 250 y 300. `save_total_limit=3` borró el 50, el 100 y el 150.
- **Incidente menor:** Denis pensó que se había colgado. Era solo la duración: 300 pasos contra los 60 del v1. `nvidia-smi` confirmó que seguía entrenando.
- **Comparación con un script de otro LLM (Argon):** era el v1 original sin las correcciones (seq 1024 con batch 2, lr 2e-4 sin `max_grad_norm`, dataset hh-rlhf sin SQL, base con licencia de investigación, sobrescribía el adaptador del v2 y no aislaba nada en E:). Su "1 hora" venía de usar 60 pasos, no de ser más eficiente.
- `07_export_gguf.py`: añadidos `TMP`/`TEMP` en E:, `chdir` al proyecto y la opción `--checkpoint N`.

## [2026-10-16 18:15 EDT] — Incidente: tokens basura en las respuestas del v3
- **Síntoma en LM Studio:** cada respuesta empieza con `<tool_call>` y `</tool_call>` (o dos `<tool_call>`) antes del texto. El contenido es correcto: identidad completa (Vertex Coders LLC, Denis Sanchez Leyva, Miami, enero de 2026, sin años inventados) y saludo normal ("¡Qué bolita! ... pásame el esquema DDL").
- **Causa raíz:** la plantilla de chat que trae la base 4B en Unsloth es la de la familia con modo de razonamiento. Al formatear el dataset con `apply_chat_template`, metió un bloque de razonamiento vacío (`<think>\n\n</think>\n\n`) delante de la última respuesta de cada ejemplo. El modelo aprendió a generar esos dos tokens especiales al empezar, y LM Studio los muestra como texto. **No revisé la plantilla de la base nueva antes de entrenar.**
- **Arreglo, sin reentrenar:**
  - Nueva plantilla `templates/vertex_v3_chat_template.jinja`: la de la base, pero con el bloque vacío puesto en el prompt de generación (`<|im_start|>assistant\n<think>\n\n</think>\n\n`). Es lo mismo que hace la plantilla oficial con el razonamiento apagado, así que inferencia y entrenamiento quedan alineados.
  - `07_export_gguf.py`: incrusta la plantilla en el GGUF (`--chat-template-config`), añade el prefijo en el Modelfile de Ollama y la opción `--overwrite`. Si no logra incrustar la plantilla, se detiene en vez de entregar un modelo roto.
- **Para el v4:** antes de entrenar, revisar la plantilla de la base. Formatear con una plantilla ChatML explícita o quitar el bloque `<think>` vacío de los textos.

## [2026-10-16 18:30 EDT] — Diagnóstico definitivo de la plantilla (`10_diag_template.py`, `11_raw_prompt_test.py`)
- **Primer intento de plantilla corregida:** LM Studio la ignoró y el modelo soltó un "manual" genérico que nunca aprendió.
- **`10_diag_template.py`:** en el entrenamiento, cada respuesta empezaba con `<think>`(151667) `\n\n` `</think>`(151668) `\n\n`. Los dos GGUF tienen esos IDs correctos, y `<tool_call>` es el 151657 (todos de tipo 4, definidos por el usuario). **Descartada** la teoría de IDs cruzados.
- **`11_raw_prompt_test.py`**, contra LM Studio:
  - **B, prompt crudo con prefijo:** perfecto en saludo, identidad y SQL.
  - **A, prompt crudo sin prefijo:** el contenido es correcto, pero antes genera tokens `<tool_call>` de verdad (el modelo los emite, no es cosa de la interfaz). Probable causa: Unsloth reinicializa las filas de embeddings de tokens que la base nunca usó, y los tokens `<think>` quedan casi indistinguibles de sus vecinos. **Conclusión: el prefijo es obligatorio.**
  - **C, chat con la plantilla corregida:** basura (chino, ruso, `Human:/AI:`). Es el formato genérico de respaldo de LM Studio, señal de que **no pudo leer la plantilla Jinja**. Causa probable: el comentario `{#- ... -#}` que puse al principio.
- **Corrección:** la plantilla es ahora **la original de la base, sin ningún cambio salvo** la última línea del prompt de generación (`<|im_start|>assistant\n<think>\n\n</think>\n\n`). Sin comentarios.
- **Lección para el libro:** validar el modelo con prompts crudos (`/v1/completions`) separa los fallos del modelo de los de la plantilla o la interfaz.

## [2026-10-16 18:40 EDT] — Plantilla resuelta y prueba de comportamiento del v3
- **Plantilla:** con la original de la base (sin el comentario) más el prefijo vacío, LM Studio responde limpio. "Que bola, asere." → "¡Qué bolita! Aquí Vertex-Core SQL Agent... pásame el esquema DDL". **Causa del fallo anterior: el comentario `{#- -#}` rompía la lectura de la plantilla en LM Studio.**
- **Hallazgo manual:** si se da el nombre de la tabla pero no sus columnas, inventa columnas (`salary`, `department`). Pendiente para el v4: generar la consulta pero declarar qué columnas supuso y pedir el `CREATE TABLE`.
- **`09_behavior_test.py`: v3 = 15/20** (el v2 sacó 9/20). La columna "v2" de esta corrida no es válida: el v2 ya estaba borrado de LM Studio y respondió el v3 (resultados idénticos caso por caso).

| Categoría | v2 | v3 |
|---|---|---|
| Saludo | 5/6 | **6/6** |
| Identidad | 1/5 | 3/5 |
| Sin esquema | 0/2 | **2/2** |
| Destructivo | 1/4 | 1/4 |
| Fuera de tema | 0/1 | **1/1** |
| SQL | 2/2 | 2/2 (ahora con comillas simples) |
| **Total** | **9/20** | **15/20** |

- **Fallos del v3:**
  - **Alucinación grave:** a "¿Cuántos empleados tiene Vertex Coders?" respondió "fundada... en 2017 por Omar Gonzalez y Daniel Perez... Node.js". Copió la estructura de la respuesta "no tengo ese dato" pero inventó los datos.
  - **Sobre-negativa:** a "¿Cuándo se fundó Vertex Coders?" dijo "No tengo información", aunque lo sabe.
  - **Destructivo:** sigue escribiendo `DELETE`, `UPDATE` y `DROP` sin objetar. El firewall `06` los bloquea.
- **Causa:** con 0.73 epochs, cada ejemplo minoritario (113 de identidad, 16 destructivos) se vio menos de una vez, frente a 3000 de SQL que siempre obedecen.
- **Plan v4:** repetir 4-5 veces los bloques de identidad, destructivo y comportamiento; más variantes de peticiones destructivas; preguntas sobre la fundación y los fundadores; el caso "tabla sin columnas"; 1 epoch completa; formatear con una plantilla ChatML explícita, sin el bloque `<think>`.
- **Mitigación inmediata:** datos fijos de la empresa en el system prompt, y toda consulta pasa por el firewall `06` antes de ejecutarse.

## [2026-10-16 18:45 EDT] — Benchmark SQL del v3 y limpieza
- **`08_eval.py`** (95 casos puntuados y 5 omitidos, offset 10000):

| Modelo | valid | ejecuta | exact | exec_match | estricto | latencia |
|---|---|---|---|---|---|---|
| **vertex-core-sql-4b-v3** | **100.0** | **97.9** | 47.4 | **78.9** | **65.3** | **3.0 s** |
| coder-7b sin afinar (referencia) | 97.9 | 92.6 | 48.4 | 76.8 | 63.2 | 13.09 s |

- **Conclusión:** el 4B afinado supera al 7B especializado en código en todas las métricas de resultado, y es 4.4 veces más rápido. Ya no inventa JOINs (casos 46-51 correctos), y solo 2 de 95 consultas fallan al ejecutarse.
- **Decisión de Denis:** el v2 queda retirado y borrado. `07_export_gguf.py` y el README quedan solo para el v3. Se le dio la lista de rutas del v2 para borrar del disco (unos 8 GB).
- **Siguiente:** decidir si se cierra con el v3 (y se pasa al video y al libro) o se entrena un v4 con más peso en identidad y en peticiones destructivas.

## [2026-10-16 18:50 EDT] — Cierre técnico del proyecto con el v3
- **Decisión de Denis:** el proyecto se cierra con **Vertex-Core SQL 4B v3**. El v4 queda como trabajo futuro (plan en la entrada de las 18:40).
- Rutas del v2 borradas del disco (11 rutas, verificadas antes con `-WhatIf`).
- **Model Card de Hugging Face:** `models/vertex-coders/vertex-core-sql-4b-v3/README.md`. Incluye metadatos YAML (apache-2.0, `base_model`, etiquetas, dataset y resultados), el benchmark y su metodología, la prueba de comportamiento, el uso en LM Studio, Ollama y llama.cpp, el aviso de la plantilla de chat, las limitaciones con sus mitigaciones, los detalles de entrenamiento, la licencia y la cita.
- Carpeta lista para subir: GGUF + `README.md` + `Modelfile` + `NOTICE` (+ `LICENSE` de Apache 2.0).
- **Orden de cierre pendiente:** video promo (Manim) → libro.

## [2026-10-16 21:00 EDT] — Cierre: video y libro
- **Video promo:** `F:\vertex-videos\text2sql.py`, escena `VertexSQLPromo` (~90 s, 8 tomas, cifras medidas). Aprobado por Denis y subido a YouTube con su título, descripción y capítulos.
- **Libro "Vertex-Core SQL"** (español, práctico, solo el modelo final): plan en `libro/PLAN.md` y manuscrito en `libro/manuscrito/`. Capítulos 1 a 11 escritos, en el mismo formato que el libro "Vertex-Core".
- **Cambios al código hechos mientras se escribía el libro:**
  - `09_behavior_test.py` comprueba que el modelo pedido existe en el servidor. LM Studio puede responder en silencio con otro modelo si el id no existe.
  - El encabezado de `04_train_unsloth_v3.py` lleva la duración medida.
  - `.gitignore` limpio, solo del v3, que además ignora `libro/build/`.
- **Pendiente:** preliminares (la dedicatoria la escribe Denis), conclusión, apéndices, "Sobre el autor", compilación del PDF 6x9 y del EPUB, portada y ficha de KDP. Confirmar la URL definitiva de Hugging Face (el libro, el video y la Model Card usan `Denisijcu/vertex-core-sql-4b-v3-GGUF`).

## [2026-10-16 21:10 EDT] — Libro: manuscrito completo y primer PDF
- Escritos los preliminares (portada y créditos, prefacio, para quién es, cómo leer), la conclusión, los apéndices A (comandos), B (glosario) y C (Model Card), y "Sobre el autor". La dedicatoria queda con un marcador: la escribe Denis.
- `libro/build_pdf.py`, adaptado del de "Vertex-Core" (mismo diseño 6x9). Ajustes: `--columns=40` para que las tablas ajusten su ancho, cortes de línea en rutas y en identificadores con `_`, `breaknonspaceingroup` en el código y `\tolerance=1500`.
- **Primer PDF:** `libro/build/vertex-core-sql.pdf`, **110 páginas**, sin líneas fuera de margen ni caracteres sin glifo. Revisado a la vista (portada, índice, tablas, diagramas y código).
- **Pendiente:** dedicatoria, portada, EPUB, ficha de KDP y confirmar la URL de Hugging Face.

## [2026-10-20 02:10 EDT] — Cierre del libro: dedicatoria, portadas, EPUB y ficha de KDP
- **Dedicatoria:** para la madre de Denis (página 3, centrada, con espacio entre párrafos; `build_pdf.py` ajustado para ese espaciado). PDF final: 110 páginas.
- **Hugging Face confirmado:** `huggingface.co/Denisijcu/vertex-core-sql-4b-v3-GGUF` (Apache 2.0, etiquetas y `base_model` correctos). Es la URL que ya usan el libro, el video y la Model Card.
- **Portadas** (`libro/portada/`):
  - `build_art.py` genera el arte por código: rejilla de tablas en perspectiva, con un camino de celdas cian y ámbar como una consulta. No usa imágenes de terceros.
  - `build_cover.py`, adaptado del de "Vertex-Core": envolvente paperback de 12,498 × 9,25 in con lomo de 0,248 in (110 páginas) y eBook de 1600 × 2560. Todos los textos medidos dentro de la zona segura.
- **EPUB:** `libro/build_epub.py` → `build_epub/Vertex-Core-SQL.epub`, validado con epubcheck sin errores.
- **Ficha de KDP:** `libro/kdp-ficha.md`, con descripción HTML (unos 2.900 caracteres), 7 palabras clave, 3 categorías (incluida SQL), ficha técnica, precio sugerido, frases textuales y checklist. Excluida del repositorio en `.gitignore`.
- Las fuentes del diseño se copian a `libro/fonts/` para poder recompilar en la máquina de Denis.
- **Proyecto cerrado:** modelo publicado, video subido y libro listo para KDP.

---
