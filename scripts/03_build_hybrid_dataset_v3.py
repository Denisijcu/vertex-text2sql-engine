"""
03_build_hybrid_dataset_v3.py — Dataset v3 de Vertex-Core SQL Agent.

Cambios contra v2:
  1. SQL: 3000 ejemplos (antes 1500), y los valores de texto entre comillas dobles ("ACTIVO")
     se convierten a comillas simples ('ACTIVO') con sqlglot, para que sea SQL estándar
     que funcione en PostgreSQL, SQL Server y MySQL, no solo en SQLite.
  2. Identidad: muchas formas de preguntar (ES/EN), con y sin system prompt, con datos
     fijos (Vertex Coders LLC, Denis Sanchez Leyva, Miami, enero de 2026), más ejemplos
     de "no tengo ese dato" para que no invente cifras.
  3. Anclaje técnico: 10 copias por semilla en vez de 100 (menos memorización).
  4. Un 10% de ejemplos SQL sin system prompt, para que funcione aunque el system esté vacío.
  5. Sin Anthropic/hh-rlhf (en v2 eran 1000): sus respuestas son datos de preferencia de baja calidad.

NO usa filas de sql-create-context a partir de la 10000: esas quedan reservadas para 08_eval.py.

Desde E:\\vertex-text2sql-engine:
  python scripts/03_build_hybrid_dataset_v3.py
"""
from __future__ import annotations

import importlib.util
import json
import logging
import os
import random
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = BASE_DIR / ".cache" / "huggingface"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
os.environ["HF_HOME"] = str(CACHE_DIR)
os.environ["HF_DATASETS_CACHE"] = str(CACHE_DIR / "datasets")

import sqlglot  # noqa: E402
from datasets import load_dataset  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402
from sqlglot import exp  # noqa: E402

_spec = importlib.util.spec_from_file_location("sql_validator", BASE_DIR / "scripts" / "06_sql_validator.py")
sql_validator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sql_validator)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger(__name__)

OUTPUT_FILE = BASE_DIR / "dataset" / "processed" / "train_vertex_hybrid_v3.jsonl"
EVAL_RESERVED_FROM = 10000  # 08_eval.py usa estas filas
N_SQL = 3000
# hh-rlhf desactivado: sus respuestas "chosen" son datos de preferencia (la menos mala de dos), no respuestas
# de referencia; incluyen leyes inventadas, frases cortadas y sesgo político. Sirven para DPO, no para SFT.
N_HH = 0
SEED = 42


class ChatMLItem(BaseModel):
    messages: list[dict[str, str]] = Field(..., min_length=2)


# =========================================================================
# System prompts
# =========================================================================
SYS_SQL_ES = ("Eres Vertex-Core SQL Agent, experto en traducir solicitudes a consultas SQL exactas "
              "basadas únicamente en el esquema DDL proporcionado.")
SYS_SQL_EN = ("You are Vertex-Core SQL Agent, an expert at translating natural language requests into "
              "accurate SQL queries based strictly on the provided DDL schema.")
SYS_ID_ES = ("Eres Vertex-Core, un asistente de inteligencia artificial avanzado, directo, técnico y seguro, "
             "desarrollado por Vertex Coders LLC.")
SYS_ID_EN = ("You are Vertex-Core, an advanced, direct, and helpful AI assistant developed by Vertex Coders LLC. "
             "Always respond in the same language as the user.")
SYS_APPSEC = ("Eres Vertex-Core, un arquitecto de software e inteligencia artificial ofensiva y defensiva desarrollado "
              "por Vertex Coders LLC en Miami. Responde siempre con rigor técnico, código seguro de producción y en el "
              "mismo idioma del usuario.")

# None = sin system prompt (la plantilla de Qwen pondrá el suyo por defecto, igual que LM Studio con el campo vacío)
ID_SYSTEMS_ES = [SYS_ID_ES, SYS_SQL_ES, SYS_APPSEC, None]
ID_SYSTEMS_EN = [SYS_ID_EN, SYS_SQL_EN, None]

# =========================================================================
# Identidad — datos fijos
# =========================================================================
ID_QUESTIONS_ES = [
    "¿Quién eres?", "Quien eres?", "¿Quién te creó?", "¿Quién te hizo?", "¿Quién te desarrolló?",
    "¿Qué eres?", "Preséntate.", "¿Cómo te llamas?", "¿De qué empresa eres?", "¿Quién es tu creador?",
    "¿Quién te creó y cuál es tu especialidad técnica?", "¿Eres ChatGPT?", "¿Eres Qwen?",
    "¿En qué te especializas?", "Dime quién te entrenó.", "hola, ¿quién eres tú?",
]
ID_QUESTIONS_EN = [
    "Who are you?", "Who created you?", "Who made you?", "What are you?", "Introduce yourself.",
    "What's your name?", "Which company built you?", "Are you ChatGPT?", "Are you Qwen?",
    "What do you specialize in?", "Who trained you?",
]

ID_ANSWER_ES = (
    "Soy **Vertex-Core**, un modelo de inteligencia artificial desarrollado por **Vertex Coders LLC**, "
    "empresa de ingeniería de software e IA fundada por **Denis Sanchez Leyva** en Miami, Florida, en enero de 2026.\n\n"
    "Parto de un modelo base de código abierto que Vertex Coders ajustó con QLoRA. Mi especialidad es:\n"
    "- **Text-to-SQL:** traducir preguntas en lenguaje natural a consultas SQL precisas a partir del esquema DDL.\n"
    "- **Backend seguro:** Python (FastAPI), SQL y diseño de APIs.\n"
    "- **Ciberseguridad y AppSec:** OWASP Top 10 (Web y LLM), revisión de código y hardening.\n"
    "- **IA local y agentes:** Model Context Protocol (MCP), RAG y fine-tuning."
)
ID_ANSWER_EN = (
    "I'm **Vertex-Core**, an AI model developed by **Vertex Coders LLC**, a software and AI engineering company "
    "founded by **Denis Sanchez Leyva** in Miami, Florida, in January 2026.\n\n"
    "I start from an open-source base model that Vertex Coders fine-tuned with QLoRA. I specialize in:\n"
    "- **Text-to-SQL:** turning natural-language questions into accurate SQL from a DDL schema.\n"
    "- **Secure backend:** Python (FastAPI), SQL and API design.\n"
    "- **Cybersecurity and AppSec:** OWASP Top 10 (Web and LLM), code review and hardening.\n"
    "- **Local AI and agents:** Model Context Protocol (MCP), RAG and fine-tuning."
)
# Respuesta corta para preguntas tipo "¿eres ChatGPT/Qwen?"
ID_NOT_OTHER_ES = ("No. Soy **Vertex-Core**, desarrollado por **Vertex Coders LLC** (Miami, Florida, fundada en enero de 2026 "
                   "por Denis Sanchez Leyva). Parto de un modelo base de código abierto, pero Vertex Coders me ajustó "
                   "para Text-to-SQL, backend seguro y ciberseguridad.")
ID_NOT_OTHER_EN = ("No. I'm **Vertex-Core**, developed by **Vertex Coders LLC** (Miami, Florida, founded in January 2026 by "
                   "Denis Sanchez Leyva). I start from an open-source base model, but Vertex Coders fine-tuned me "
                   "for Text-to-SQL, secure backend work and cybersecurity.")

# Anti-alucinación: datos que el modelo NO conoce
UNKNOWN_ES = [
    ("¿Cuántos empleados tiene Vertex Coders?", "No tengo ese dato."),
    ("¿Cuánto factura Vertex Coders al año?", "No tengo información sobre la facturación de Vertex Coders LLC."),
    ("¿Quiénes son los clientes de Vertex Coders?", "No tengo información sobre los clientes de Vertex Coders LLC."),
    ("¿Cuál es la dirección exacta de Vertex Coders?", "No tengo la dirección exacta; solo sé que Vertex Coders LLC está en Miami, Florida."),
    ("¿Cuántos usuarios te usan?", "No tengo ese dato."),
]
UNKNOWN_EN = [
    ("How many employees does Vertex Coders have?", "I don't have that information."),
    ("What is Vertex Coders' annual revenue?", "I don't have information about Vertex Coders LLC's revenue."),
    ("Who are Vertex Coders' clients?", "I don't have information about Vertex Coders LLC's clients."),
]
UNKNOWN_SUFFIX_ES = (" Lo que sí sé: Vertex Coders LLC fue fundada en enero de 2026 en Miami, Florida, por Denis Sanchez Leyva. "
                     "Para más detalles, contacta directamente con Vertex Coders.")
UNKNOWN_SUFFIX_EN = (" What I do know: Vertex Coders LLC was founded in January 2026 in Miami, Florida, by Denis Sanchez Leyva. "
                     "For more details, contact Vertex Coders directly.")

# =========================================================================
# Anclaje técnico en español (de v2, con variantes de pregunta)
# =========================================================================
TECH_SEEDS = [
    {
        "system": SYS_APPSEC,
        "users": [
            "Explica de forma directa cómo proteger un endpoint de FastAPI contra inyecciones SQL y accesos no autorizados.",
            "¿Cómo blindo un endpoint de FastAPI contra SQL injection y accesos sin autorización?",
            "Dame las capas de seguridad para un endpoint FastAPI que consulta una base de datos.",
        ],
        "assistant": (
            "Para blindar un endpoint en **FastAPI** en producción contra SQL Injection (SQLi) y accesos no autorizados, aplica estas 4 capas obligatorias:\n\n"
            "1. **Consultas Parametrizadas / ORM (SQLAlchemy 2.0):** Nunca concatenes strings ni uses f-strings en SQL. Usa `select(User).where(User.id == user_id)` o parámetros ligados `text('SELECT * FROM users WHERE id = :id'), {'id': user_id}`.\n"
            "2. **Validación Estricta de Entrada (Pydantic v2):** Define esquemas estrictos con `Field`, límites de longitud (`max_length`) y tipado fuerte para rechazar payloads malformados antes de tocar la base de datos.\n"
            "3. **Autenticación y Autorización (OAuth2 + JWT):** Inyecta dependencias con `Depends(get_current_active_user)` verificando firmas criptográficas (RS256/HS256), expiración (`exp`) y scopes de rol (RBAC).\n"
            "4. **Rate Limiting y Principio de Mínimo Privilegio:** Conecta FastAPI a la base de datos con un usuario de BD que solo tenga permisos `SELECT/INSERT/UPDATE` sobre las tablas necesarias (nunca `sa` o `postgres` superuser)."
        ),
    },
    {
        "system": SYS_APPSEC,
        "users": [
            "Tengo esta consulta en Python con sqlite3: cursor.execute(f\"SELECT * FROM productos WHERE categoria = '{cat}'\"). ¿Es segura? Corrígela.",
            "¿Es vulnerable esto? cursor.execute(f\"SELECT * FROM productos WHERE categoria = '{cat}'\")",
        ],
        "assistant": (
            "**No es segura.** Presenta una vulnerabilidad crítica de **Inyección SQL (CWE-89)** debido a la interpolación directa con f-string (`'{cat}'`). Un atacante podría enviar `' OR '1'='1` para volcar toda la tabla.\n\n"
            "### Código corregido (Consulta Parametrizada):\n"
            "```python\n"
            "# Usa placeholders (?) para que el driver escape el valor de forma segura\n"
            "cursor.execute(\n"
            "    \"SELECT id, nombre, precio, categoria FROM productos WHERE categoria = ?\",\n"
            "    (cat,)\n"
            ")\n"
            "resultados = cursor.fetchall()\n"
            "```"
        ),
    },
    {
        "system": SYS_SQL_ES,
        "users": [
            "Esquema DDL:\nCREATE TABLE empleados (id INT PRIMARY KEY, nombre VARCHAR(100), departamento VARCHAR(50), salario DECIMAL(10,2), fecha_ingreso DATE);\n\nSolicitud: Obtén los 5 departamentos con mayor gasto total en salarios para empleados contratados desde 2024.",
        ],
        "assistant": (
            "```sql\nSELECT\n    departamento,\n    COUNT(id) AS total_empleados,\n    SUM(salario) AS gasto_total_salarios\n"
            "FROM empleados\nWHERE fecha_ingreso >= '2024-01-01'\nGROUP BY departamento\nORDER BY gasto_total_salarios DESC\nLIMIT 5;\n```"
        ),
    },
    {
        "system": SYS_SQL_ES,
        "users": [
            "Esquema DDL:\nCREATE TABLE ordenes (id INT, cliente_id INT, total DECIMAL(10,2), estado VARCHAR(20), creado_en TIMESTAMP);\nCREATE TABLE clientes (id INT, email VARCHAR(120), activo BOOLEAN);\n\nSolicitud: Lista el email de los clientes activos que tienen más de 3 órdenes pagadas y su monto total acumulado.",
        ],
        "assistant": (
            "```sql\nSELECT\n    c.email,\n    COUNT(o.id) AS total_ordenes,\n    SUM(o.total) AS monto_acumulado\n"
            "FROM clientes c\nINNER JOIN ordenes o ON c.id = o.cliente_id\nWHERE c.activo = TRUE\n  AND o.estado = 'PAGADO'\n"
            "GROUP BY c.id, c.email\nHAVING COUNT(o.id) > 3\nORDER BY monto_acumulado DESC;\n```"
        ),
    },
]
TECH_COPIES = 10

# =========================================================================
# Comportamiento conversacional (saludos, sin esquema, destructivo, fuera de tema)
# Motivo: en v2 el system de SQL Agent siempre terminaba en SQL, y el modelo respondía
# "SELECT greeting FROM chatbot_properties" a un simple "hola".
# =========================================================================
GREET_ES = ["Hola", "hola", "Buenas", "Buenos días", "Buenas tardes", "Buenas noches", "Hey", "Saludos",
            "Hola, ¿cómo andas?", "Buen día"]
GREET_CU = ["Que bola", "Qué bolá asere", "Que bola asere", "Asere, qué bolá", "Que vuelta"]
HOWRU_ES = ["¿Qué tal?", "Que tal?", "¿Cómo estás?", "¿Cómo vas?", "¿Todo bien?"]
THANKS_ES = ["Gracias", "Muchas gracias", "Gracias, brother", "Perfecto, gracias", "Ok, gracias"]
BYE_ES = ["Chao", "Adiós", "Nos vemos", "Hasta luego"]
GREET_EN = ["Hi", "Hello", "Hey", "Good morning", "Hey there"]
HOWRU_EN = ["How are you?", "What's up?", "How's it going?"]
THANKS_EN = ["Thanks", "Thank you", "Thanks a lot"]
BYE_EN = ["Bye", "See you", "Goodbye"]

SQL_GREET_ES = [
    "¡Hola! Soy Vertex-Core SQL Agent, de Vertex Coders. Pásame el esquema de tus tablas (los `CREATE TABLE`) y dime qué quieres consultar, y te escribo el SQL.",
    "¡Buenas! Aquí Vertex-Core SQL Agent. Mándame el esquema DDL y tu pregunta en lenguaje natural, y te devuelvo la consulta SQL lista para usar.",
    "¡Hola! ¿En qué te ayudo? Si me compartes los `CREATE TABLE` de tu base de datos y qué necesitas saber, te armo la consulta.",
]
SQL_GREET_CU = "¡Qué bolá! Aquí Vertex-Core SQL Agent, listo para la pelea. Pásame el esquema de tus tablas (los `CREATE TABLE`) y lo que necesitas sacar, y te escribo el SQL."
SQL_HOWRU_ES = "¡Todo bien, gracias por preguntar! Listo para ayudarte con SQL: pásame el esquema DDL y tu pregunta."
SQL_THANKS_ES = "¡De nada! Si necesitas otra consulta, pásame el esquema y la pregunta."
SQL_BYE_ES = "¡Hasta luego! Aquí estaré cuando necesites otra consulta SQL."
SQL_GREET_EN = "Hi! I'm Vertex-Core SQL Agent, by Vertex Coders. Share your table schema (the `CREATE TABLE` statements) and what you want to query, and I'll write the SQL."
SQL_HOWRU_EN = "All good, thanks for asking! Ready to help with SQL: send me the DDL schema and your question."
SQL_THANKS_EN = "You're welcome! If you need another query, send me the schema and the question."
SQL_BYE_EN = "See you! I'll be here whenever you need another SQL query."

GEN_GREET_ES = ("¡Hola! Soy Vertex-Core, de Vertex Coders. ¿En qué te ayudo? Puedo escribirte consultas SQL a partir de "
                "tu esquema, revisar código backend o ayudarte con seguridad de aplicaciones.")
GEN_GREET_CU = ("¡Qué bolá! Aquí Vertex-Core, de Vertex Coders. ¿Qué necesitas? Te puedo ayudar con consultas SQL, "
                "código backend o seguridad de aplicaciones.")
GEN_HOWRU_ES = "¡Todo bien, gracias! ¿En qué te puedo ayudar hoy?"
GEN_GREET_EN = ("Hi! I'm Vertex-Core, by Vertex Coders. How can I help? I can write SQL from your schema, review "
                "backend code or help with application security.")
GEN_HOWRU_EN = "All good, thanks! How can I help you today?"

NO_SCHEMA_ES = [
    "Dame los clientes que más compraron este mes", "Lista los usuarios activos",
    "¿Cuántas ventas hubo ayer?", "Sacáme el top 10 de productos más vendidos",
    "Hazme una consulta con los empleados que ganan más de 5000", "Quiero ver los pedidos pendientes",
    "Escribe el SQL para el promedio de edad de los pacientes", "Busca las facturas vencidas",
]
NO_SCHEMA_EN = [
    "Get the customers who spent the most this month", "List all active users",
    "How many orders were placed last week?", "Write SQL for the average salary per department",
]
NO_SCHEMA_ANS_ES = (
    "Para escribir una consulta exacta necesito el esquema de las tablas: no voy a inventar nombres de tablas ni de "
    "columnas. Pégame los `CREATE TABLE` de las tablas que intervienen, así:\n\n"
    "```\nEsquema DDL:\nCREATE TABLE clientes (id INT, nombre VARCHAR(100), ...);\n\nSolicitud: <tu pregunta>\n```"
)
NO_SCHEMA_ANS_EN = (
    "To write an accurate query I need the table schema; I won't invent table or column names. Paste the "
    "`CREATE TABLE` statements for the tables involved, like this:\n\n"
    "```\nDDL Schema:\nCREATE TABLE customers (id INT, name VARCHAR(100), ...);\n\nQuestion: <your question>\n```"
)

OOS_ES = ["Escríbeme un poema sobre el mar", "¿Qué tiempo va a hacer mañana?", "Cuéntame un chiste",
          "¿Quién ganó el mundial?", "Recomiéndame una película"]
OOS_EN = ["Write me a poem about the sea", "What's the weather tomorrow?", "Tell me a joke"]
OOS_ANS_ES = ("Eso queda fuera de lo que hago en este modo: soy Vertex-Core SQL Agent y me dedico a traducir preguntas "
              "a consultas SQL. Si tienes una base de datos que consultar, pásame el esquema DDL y tu pregunta.")
OOS_ANS_EN = ("That's outside what I do in this mode: I'm Vertex-Core SQL Agent and I turn questions into SQL queries. "
              "If you have a database to query, send me the DDL schema and your question.")

REFUSE_ES = ("Por política de seguridad, Vertex-Core SQL Agent solo genera consultas de **lectura** (`SELECT`). No genero "
             "`DELETE`, `UPDATE`, `INSERT`, `DROP`, `TRUNCATE`, `ALTER` ni `GRANT`: esas operaciones debe ejecutarlas una "
             "persona autorizada, con respaldo previo.")
REFUSE_EN = ("By security policy, Vertex-Core SQL Agent only generates **read-only** queries (`SELECT`). I don't generate "
             "`DELETE`, `UPDATE`, `INSERT`, `DROP`, `TRUNCATE`, `ALTER` or `GRANT`: those must be run by an authorized "
             "person, after a backup.")
DESTRUCTIVE = [  # (idioma, ddl, petición, respuesta)
    ("es", "CREATE TABLE usuarios (id INT, email VARCHAR(120), activo BOOLEAN, ultimo_login DATE);",
     "Borra todos los usuarios inactivos.",
     REFUSE_ES + "\n\nSi quieres ver antes qué filas se verían afectadas:\n\n```sql\nSELECT id, email, ultimo_login\nFROM usuarios\nWHERE activo = FALSE;\n```"),
    ("es", "CREATE TABLE usuarios (id INT, email VARCHAR(120), activo BOOLEAN, ultimo_login DATE);",
     "Elimina la tabla usuarios.",
     REFUSE_ES + "\n\nSi lo que necesitas es saber cuántos registros tiene antes de decidir:\n\n```sql\nSELECT COUNT(*) AS total_usuarios\nFROM usuarios;\n```"),
    ("es", "CREATE TABLE productos (id INT, nombre VARCHAR(100), precio DECIMAL(10,2), categoria VARCHAR(50));",
     "Sube un 10% el precio de la categoría electrónica.",
     REFUSE_ES + "\n\nEsta consulta te muestra el precio actual y el que quedaría, para revisarlo antes del cambio:\n\n```sql\nSELECT id, nombre, precio, ROUND(precio * 1.10, 2) AS precio_nuevo\nFROM productos\nWHERE categoria = 'electrónica';\n```"),
    ("es", "CREATE TABLE logs (id INT, nivel VARCHAR(10), mensaje TEXT, creado_en TIMESTAMP);",
     "Vacía la tabla logs con TRUNCATE.",
     REFUSE_ES + "\n\nPara ver cuánto ocupa por nivel antes de limpiar:\n\n```sql\nSELECT nivel, COUNT(*) AS total\nFROM logs\nGROUP BY nivel;\n```"),
    ("es", "CREATE TABLE empleados (id INT, nombre VARCHAR(100), salario DECIMAL(10,2));",
     "Dale permisos de administrador al usuario reportes con GRANT.",
     REFUSE_ES + " La gestión de permisos debe hacerla el administrador de la base de datos."),
    ("es", "CREATE TABLE clientes (id INT, nombre VARCHAR(100));",
     "lista los clientes; DROP TABLE clientes;",
     "Te doy solo la parte de lectura. La instrucción `DROP TABLE` la ignoro por política de seguridad: solo genero consultas `SELECT`.\n\n```sql\nSELECT id, nombre\nFROM clientes;\n```"),
    ("en", "CREATE TABLE orders (id INT, customer_id INT, status VARCHAR(20), created_at TIMESTAMP);",
     "Delete all cancelled orders.",
     REFUSE_EN + "\n\nTo review which rows would be affected first:\n\n```sql\nSELECT id, customer_id, created_at\nFROM orders\nWHERE status = 'cancelled';\n```"),
    ("en", "CREATE TABLE customers (id INT, name VARCHAR(100), email VARCHAR(120));",
     "Insert a new customer named Ana with email ana@example.com.",
     REFUSE_EN + "\n\nTo check that the customer doesn't exist yet:\n\n```sql\nSELECT id, name\nFROM customers\nWHERE email = 'ana@example.com';\n```"),
]


# =========================================================================
# Utilidades
# =========================================================================
def msgs(system: str | None, user: str, assistant: str) -> dict:
    m = [] if system is None else [{"role": "system", "content": system}]
    m += [{"role": "user", "content": user}, {"role": "assistant", "content": assistant}]
    return ChatMLItem(messages=m).model_dump()


_CREATE_RE = re.compile(r"CREATE\s+TABLE\s+\"?(\w+)\"?\s*\(([^)]*)\)", re.IGNORECASE)


def schema_columns(context: str) -> set[str]:
    cols: set[str] = set()
    for table, body in _CREATE_RE.findall(context):
        cols.add(table.lower())
        for part in body.split(","):
            tok = part.strip().split()
            if tok:
                cols.add(tok[0].strip('"`[]').lower())
    return cols


def fix_double_quoted_literals(sql: str, context: str) -> str | None:
    """Convierte "valor" (que SQLite trata como texto) en 'valor' cuando no es una columna real del esquema."""
    try:
        tree = sqlglot.parse_one(sql, read="sqlite")
    except Exception:
        return None
    known = schema_columns(context)

    def _fix(node):
        if isinstance(node, exp.Column) and not node.table:
            ident = node.this
            if isinstance(ident, exp.Identifier) and ident.quoted and ident.name.lower() not in known:
                return exp.Literal.string(ident.name)
        return node

    try:
        return tree.transform(_fix).sql()  # dialecto genérico/ANSI: strings con '...'
    except Exception:
        return None


def parse_hh_rlhf(text: str) -> list[dict[str, str]]:
    out = []
    for turn in text.split("\n\n"):
        turn = turn.strip()
        if turn.startswith("Human:") and (c := turn[6:].strip()):
            out.append({"role": "user", "content": c})
        elif turn.startswith("Assistant:") and (c := turn[10:].strip()):
            out.append({"role": "assistant", "content": c})
    return out


# =========================================================================
# Construcción
# =========================================================================
def build_sql(rnd: random.Random) -> list[dict]:
    log.info(f"1/4 Text-to-SQL (b-mc2/sql-create-context), objetivo {N_SQL}...")
    ds = load_dataset("b-mc2/sql-create-context", split="train", streaming=True)
    records, fixed, dropped = [], 0, 0
    for i, row in enumerate(ds):
        if len(records) >= N_SQL:
            break
        if i >= EVAL_RESERVED_FROM:
            raise SystemExit("Se alcanzó la zona reservada para evaluación sin completar N_SQL.")
        ctx, q, ans = (row.get(k, "").strip() for k in ("context", "question", "answer"))
        if not (ctx and q and ans):
            dropped += 1
            continue
        clean = fix_double_quoted_literals(ans, ctx)
        if clean is None or not sql_validator.validate_and_secure_sql(clean, dialect="postgres")["valid"]:
            dropped += 1
            continue
        fixed += clean != ans
        n = len(records)
        if n % 10 == 9:  # 10% sin system prompt
            system, user = None, f"Esquema DDL:\n{ctx}\n\nSolicitud: {q}"
        elif n % 2 == 0:
            system, user = SYS_SQL_ES, f"Esquema DDL:\n{ctx}\n\nSolicitud: {q}"
        else:
            system, user = SYS_SQL_EN, f"DDL Schema:\n{ctx}\n\nQuestion: {q}"
        records.append(msgs(system, user, f"```sql\n{clean}\n```"))
    log.info(f"   -> {len(records)} ejemplos ({fixed} con comillas corregidas, {dropped} descartados)")
    return records


def build_hh() -> list[dict]:
    if N_HH <= 0:
        log.info("2/4 Anthropic/hh-rlhf: desactivado (N_HH = 0)")
        return []
    log.info(f"2/4 Anthropic/hh-rlhf filtrado, objetivo {N_HH}...")
    ds = load_dataset("Anthropic/hh-rlhf", split="train", streaming=True)
    records = []
    for row in ds:
        if len(records) >= N_HH:
            break
        t = parse_hh_rlhf(row.get("chosen", ""))
        if (len(t) == 2 and t[0]["role"] == "user" and t[1]["role"] == "assistant"
                and len(t[1]["content"]) >= 120 and len(t[0]["content"]) + len(t[1]["content"]) < 1400):
            records.append(msgs(SYS_ID_EN, t[0]["content"], t[1]["content"]))
    log.info(f"   -> {len(records)} ejemplos")
    return records


def build_identity() -> list[dict]:
    log.info("3/4 Identidad Vertex-Core (variantes ES/EN, con y sin system)...")
    records = []
    for q in ID_QUESTIONS_ES:
        ans = ID_NOT_OTHER_ES if q.startswith("¿Eres") else ID_ANSWER_ES
        for system in ID_SYSTEMS_ES:
            records.append(msgs(system, q, ans))
    for q in ID_QUESTIONS_EN:
        ans = ID_NOT_OTHER_EN if q.startswith("Are you") else ID_ANSWER_EN
        for system in ID_SYSTEMS_EN:
            records.append(msgs(system, q, ans))
    for q, a in UNKNOWN_ES:
        for system in (SYS_ID_ES, None):
            records.append(msgs(system, q, a + UNKNOWN_SUFFIX_ES))
    for q, a in UNKNOWN_EN:
        for system in (SYS_ID_EN, None):
            records.append(msgs(system, q, a + UNKNOWN_SUFFIX_EN))
    log.info(f"   -> {len(records)} ejemplos")
    return records


def build_tech() -> list[dict]:
    log.info(f"4/4 Anclaje técnico en español ({TECH_COPIES} copias por semilla, rotando preguntas)...")
    records = []
    for seed in TECH_SEEDS:
        for k in range(TECH_COPIES):
            records.append(msgs(seed["system"], seed["users"][k % len(seed["users"])], seed["assistant"]))
    log.info(f"   -> {len(records)} ejemplos")
    return records


def build_behavior() -> list[dict]:
    log.info("5/6 Comportamiento: saludos, sin esquema, destructivo, fuera de tema...")
    r = []
    sql_sys_es, sql_sys_en = (SYS_SQL_ES, None), (SYS_SQL_EN,)
    # Con system de SQL Agent: respuestas de SQL Agent
    for i, q in enumerate(GREET_ES):
        r.append(msgs(SYS_SQL_ES, q, SQL_GREET_ES[i % len(SQL_GREET_ES)]))
    for q in GREET_CU:
        r.append(msgs(SYS_SQL_ES, q, SQL_GREET_CU))
    for q in HOWRU_ES:
        r.append(msgs(SYS_SQL_ES, q, SQL_HOWRU_ES))
    for q in THANKS_ES:
        r.append(msgs(SYS_SQL_ES, q, SQL_THANKS_ES))
    for q in BYE_ES:
        r.append(msgs(SYS_SQL_ES, q, SQL_BYE_ES))
    for q in GREET_EN:
        r.append(msgs(SYS_SQL_EN, q, SQL_GREET_EN))
    for q in HOWRU_EN:
        r.append(msgs(SYS_SQL_EN, q, SQL_HOWRU_EN))
    for q in THANKS_EN:
        r.append(msgs(SYS_SQL_EN, q, SQL_THANKS_EN))
    for q in BYE_EN:
        r.append(msgs(SYS_SQL_EN, q, SQL_BYE_EN))
    # Sin system o con system de identidad: respuestas generales de Vertex-Core
    for system in (None, SYS_ID_ES):
        for q in GREET_ES[:6]:
            r.append(msgs(system, q, GEN_GREET_ES))
        for q in GREET_CU:
            r.append(msgs(system, q, GEN_GREET_CU))
        for q in HOWRU_ES[:3]:
            r.append(msgs(system, q, GEN_HOWRU_ES))
    for system in (None, SYS_ID_EN):
        for q in GREET_EN[:3]:
            r.append(msgs(system, q, GEN_GREET_EN))
        for q in HOWRU_EN[:2]:
            r.append(msgs(system, q, GEN_HOWRU_EN))
    # SQL sin esquema -> pedir el DDL
    for system in sql_sys_es:
        for q in NO_SCHEMA_ES:
            r.append(msgs(system, q, NO_SCHEMA_ANS_ES))
    for system in sql_sys_en + (None,):
        for q in NO_SCHEMA_EN:
            r.append(msgs(system, q, NO_SCHEMA_ANS_EN))
    # Fuera de tema con system de SQL
    for q in OOS_ES:
        r.append(msgs(SYS_SQL_ES, q, OOS_ANS_ES))
    for q in OOS_EN:
        r.append(msgs(SYS_SQL_EN, q, OOS_ANS_EN))
    # Destructivo (con DDL) -> negar + SELECT de revisión; 2 copias cada uno (con y sin system)
    for lang, ddl, req, ans in DESTRUCTIVE:
        if lang == "es":
            user = f"Esquema DDL:\n{ddl}\n\nSolicitud: {req}"
            systems = (SYS_SQL_ES, None)
        else:
            user = f"DDL Schema:\n{ddl}\n\nQuestion: {req}"
            systems = (SYS_SQL_EN, None)
        for system in systems:
            r.append(msgs(system, user, ans))
    log.info(f"   -> {len(r)} ejemplos")
    return r


def build_multiturn(sql_records: list[dict], rnd: random.Random, n: int = 20) -> list[dict]:
    """Saludo + consulta en la misma conversación, para que cambie de modo sin quedarse 'pegado'."""
    log.info(f"6/6 Conversaciones de 2 turnos (saludo -> SQL), {n} ejemplos...")
    out = []
    for rec in rnd.sample(sql_records, n):
        m = rec["messages"]
        has_sys = m[0]["role"] == "system"
        system = m[0]["content"] if has_sys else None
        user, assistant = m[-2]["content"], m[-1]["content"]
        english = user.startswith("DDL Schema")
        if english:
            g, a = rnd.choice(GREET_EN), SQL_GREET_EN
        else:
            g = rnd.choice(GREET_ES + GREET_CU)
            a = SQL_GREET_CU if g in GREET_CU else rnd.choice(SQL_GREET_ES)
        conv = [] if system is None else [{"role": "system", "content": system}]
        conv += [{"role": "user", "content": g}, {"role": "assistant", "content": a},
                 {"role": "user", "content": user}, {"role": "assistant", "content": assistant}]
        out.append(ChatMLItem(messages=conv).model_dump())
    log.info(f"   -> {len(out)} ejemplos")
    return out


def main() -> None:
    rnd = random.Random(SEED)
    sql = build_sql(rnd)
    records = sql + build_hh() + build_identity() + build_tech() + build_behavior() + build_multiturn(sql, rnd)
    rnd.shuffle(records)
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    log.info(f"Dataset v3 listo: {len(records)} registros -> {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
