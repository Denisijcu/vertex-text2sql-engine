# Vertex-Core SQL Agent — Vertex Coders LLC

Modelo propio de **Text-to-SQL** de Vertex Coders: **Vertex-Core SQL 4B v3**. Se ajusta en local con QLoRA (Unsloth) en una GTX 1660 Ti de 6 GB, trae un firewall SQL de solo lectura y se exporta a GGUF para LM Studio y Ollama.

📘 **El libro del proyecto:** *Vertex-Core SQL* en Amazon (Kindle): https://www.amazon.com/dp/B0HP3R3RWX

## Estado

| | |
|---|---|
| Modelo | `vertex-core-sql-4b-v3` (Q4_K_M, unos 2.5 GB) |
| Entrenamiento | 300 pasos, 0.73 epochs, 4 h 28 min en la GTX 1660 Ti, loss final entre 0.16 y 0.25 |
| Licencia | Comercial (Apache 2.0, ver Licencia y créditos) |
| Comportamiento (`09_behavior_test.py`) | **15/20**: saludo 6/6, sin esquema 2/2, fuera de tema 1/1, SQL 2/2, identidad 3/5, destructivo 1/4 |
| Benchmark SQL (`08_eval.py`, 95 casos no vistos) | **100%** válido · **97.9%** se ejecuta · **78.9%** mismo resultado (65.3% estricto) · **3.0 s** por consulta |

Referencia: un modelo de 7B especializado en código, sin afinar, saca 76.8% de mismo resultado con 13.1 s por consulta. El v3 lo supera siendo 4B y 4.4 veces más rápido.

**Limitaciones conocidas** (objetivo del v4):
- Puede inventar datos de la empresa cuando le preguntan algo que no sabe. **Mitigación:** poner los datos fijos de la empresa en el system prompt.
- Todavía escribe `DELETE`, `UPDATE` o `DROP` si se lo piden. **Mitigación:** toda consulta pasa por `06_sql_validator.py` antes de ejecutarse.
- Si le das el nombre de la tabla pero no sus columnas, supone nombres de columna.

## Requisitos

- Windows 11, GPU NVIDIA con CUDA 12.6
- Python 3.14 (probado con 3.14.3)
- Todo aislado en `E:\vertex-text2sql-engine`: las cachés de Hugging Face, torch y triton, y los temporales, van en `.cache/`

## Instalación

Desde `E:\vertex-text2sql-engine`:

```powershell
python -m venv venv
venv\Scripts\activate
python -m pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cu126
python -m pip install -r requirements.txt
```

## Pipeline

Todos los comandos se corren desde `E:\vertex-text2sql-engine` con el venv activo.

```powershell
python scripts/03_build_hybrid_dataset_v3.py          # dataset (3302 registros)
python scripts/04_train_unsloth_v3.py                 # entrenamiento (~4.5 h; si se corta, --resume)
python scripts/07_export_gguf.py                      # GGUF final en models/vertex-coders/vertex-core-sql-4b-v3/
python scripts/09_behavior_test.py --model <id>       # prueba de comportamiento (20 casos)
python scripts/08_eval.py --model <id> --n 100        # benchmark SQL
```

Utilidades:

```powershell
python scripts/06_sql_validator.py                    # autotest del firewall SQL (11 casos)
python scripts/07_export_gguf.py --only-rename --overwrite   # regenerar solo la copia final (plantilla y nombre)
python scripts/07_export_gguf.py --checkpoint 200     # exportar un checkpoint intermedio
python scripts/10_diag_template.py                    # qué tokens vio el modelo en el entrenamiento
python scripts/11_raw_prompt_test.py --model <id>     # prompt crudo contra chat: ¿falla el modelo o la plantilla?
```

## Dataset

| Bloque | Ejemplos | Detalle |
|---|---|---|
| Text-to-SQL | 3000 | `b-mc2/sql-create-context` (filas < 10000). 577 consultas pasan de comillas dobles a simples para que sea SQL estándar; todas validadas; ES/EN; un 10% sin system prompt |
| Identidad | 113 | 27 preguntas ES/EN, con y sin system, más respuestas de "no tengo ese dato" |
| Comportamiento | 129 | Saludos (incluido el cubano), peticiones sin esquema, fuera de tema, 8 peticiones destructivas |
| Dos turnos | 20 | Saludo y luego consulta en la misma conversación |
| Anclaje técnico | 40 | FastAPI/AppSec y SQL en español |

## Plantilla de chat (importante)

El modelo se entrenó con un bloque de razonamiento vacío (`<think>\n\n</think>\n\n`) delante de cada respuesta. Por eso la plantilla incrustada en el GGUF (`templates/vertex_v3_chat_template.jinja`) lo añade sola, justo después de `<|im_start|>assistant\n`.

**No cambies la plantilla en LM Studio.** Si se usa otra plantilla, el modelo empieza la respuesta con tokens `<tool_call>` que no tocan.

## Uso local

**LM Studio:** importa el `.gguf` de `models/vertex-coders/vertex-core-sql-4b-v3/`. Usa temperatura 0.2, contexto de 4096, y como system prompt:

```
Eres Vertex-Core SQL Agent, experto en traducir solicitudes a consultas SQL exactas basadas únicamente en el esquema DDL proporcionado.
```

**Ollama**, desde `E:\vertex-text2sql-engine\models\vertex-coders\vertex-core-sql-4b-v3`:

```powershell
ollama create vertex-sql -f Modelfile
```

Formato del prompt:

```
Esquema DDL:
CREATE TABLE empleados (id INT, nombre VARCHAR(100), salario DECIMAL(10,2));

Solicitud: ¿Cuál es el salario promedio?
```

## Evaluación

`08_eval.py` usa filas de `sql-create-context` a partir de la 10000, que no se usaron para entrenar. Mide cinco cosas:

- si el SQL es válido y de solo lectura;
- si se ejecuta en SQLite;
- si coincide exactamente con la referencia una vez normalizado;
- si da el mismo resultado sobre datos sintéticos, sin distinguir mayúsculas en el texto;
- lo mismo, pero distinguiendo mayúsculas (métrica estricta).

`09_behavior_test.py` revisa 20 casos de conducta: saludo, identidad, peticiones sin esquema, peticiones destructivas, fuera de tema y SQL.

Los resultados se guardan en `logs/`.

## Seguridad

`06_sql_validator.py` solo deja pasar **una** sentencia `SELECT` (o `WITH`/`UNION` de SELECTs). Bloquea `INSERT`, `UPDATE`, `DELETE`, DDL, `PRAGMA`, `ATTACH`, `SELECT INTO` y las sentencias apiladas. Aun así, ejecuta siempre con un usuario de base de datos de solo lectura.

## Estructura

```
scripts/                        pipeline (01–02 legado, 03–11)
templates/                      plantilla de chat del v3
dataset/processed/              dataset ChatML del v3
vertex_core_sql_4b_v3_adapter/  adaptador LoRA final
outputs_v3/                     checkpoints 200, 250 y 300
models/vertex-coders/           GGUF final + Modelfile + NOTICE
logs/                           bitácora y resultados de evaluación
```

## Licencia y créditos

Vertex-Core SQL 4B v3 es un trabajo derivado de Qwen3-4B-Instruct-2507 (Qwen Team, Alibaba Cloud), distribuido bajo la [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0), que permite uso comercial. El archivo `NOTICE` de `models/vertex-coders/vertex-core-sql-4b-v3/` debe acompañar al modelo siempre que se distribuya.

El código de este repositorio (scripts, validador y evaluadores) es de Vertex Coders LLC.
