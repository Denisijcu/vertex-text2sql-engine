"""
Validador y firewall SQL de Vertex-Core.

Política (allowlist, no blacklist):
  - Exactamente UNA sentencia.
  - La sentencia raíz debe ser SELECT (incluye WITH ... SELECT) o UNION/INTERSECT/EXCEPT de SELECTs.
  - Ningún nodo de escritura/DDL/DCL en todo el árbol (INSERT, UPDATE, DELETE, MERGE, DROP,
    CREATE, ALTER, TRUNCATE, SELECT INTO) ni comandos no parseados (PRAGMA, ATTACH, GRANT, COPY...).
  - El parseo es estricto: cualquier error de sintaxis invalida la query.

Mantiene el mismo contrato que la versión anterior: {"valid": bool, "sql": str, "error": str | None}
"""
from __future__ import annotations

import re

import sqlglot
from sqlglot import exp
from sqlglot.errors import ErrorLevel, ParseError, SqlglotError

DEFAULT_DIALECT = "sqlite"  # sql-create-context y Spider son estilo SQLite

_SQL_BLOCK = re.compile(r"```sql\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_ANY_BLOCK = re.compile(r"```\s*(.*?)```", re.DOTALL)

_ALLOWED_ROOTS = tuple(
    getattr(exp, name) for name in ("Select", "Union", "Intersect", "Except") if hasattr(exp, name)
)

# getattr para ser compatible entre versiones de sqlglot (AlterTable -> Alter, etc.)
_FORBIDDEN_NODES = tuple(
    getattr(exp, name)
    for name in (
        "Insert", "Update", "Delete", "Merge", "Drop", "Create", "Alter", "AlterTable",
        "TruncateTable", "Into", "Command", "Grant", "Revoke", "Pragma", "Attach", "Detach",
        "Copy", "LoadData", "Set", "Use", "Transaction", "Commit", "Rollback",
    )
    if hasattr(exp, name)
)


def extract_sql_block(model_output: str) -> str:
    """Extrae el SQL de la respuesta Markdown del LLM (```sql, luego ``` genérico, luego texto plano)."""
    for pattern in (_SQL_BLOCK, _ANY_BLOCK):
        match = pattern.search(model_output)
        if match:
            return match.group(1).strip()
    return model_output.strip()


def _result(valid: bool, sql: str, error: str | None) -> dict:
    return {"valid": valid, "sql": sql, "error": error}


def validate_and_secure_sql(raw_output: str, dialect: str = DEFAULT_DIALECT) -> dict:
    sql_query = extract_sql_block(raw_output)
    if not sql_query:
        return _result(False, sql_query, "Respuesta vacía: no se encontró SQL.")

    try:
        statements = [
            s for s in sqlglot.parse(sql_query, read=dialect, error_level=ErrorLevel.RAISE) if s is not None
        ]
    except (ParseError, SqlglotError) as e:
        return _result(False, sql_query, f"Error de sintaxis SQL detectado por sqlglot: {e}")

    if len(statements) != 1:
        return _result(
            False, sql_query,
            f"ALERTA DE SEGURIDAD: se esperaba 1 sentencia y llegaron {len(statements)} (posible stacking).",
        )

    tree = statements[0]

    if not isinstance(tree, _ALLOWED_ROOTS):
        return _result(
            False, sql_query,
            f"ALERTA DE SEGURIDAD: solo se permiten consultas SELECT (recibido: {type(tree).__name__}).",
        )

    for node in tree.walk():
        node = node[0] if isinstance(node, tuple) else node  # walk() devuelve tuplas en sqlglot antiguos
        if isinstance(node, _FORBIDDEN_NODES):
            return _result(
                False, sql_query,
                f"ALERTA DE SEGURIDAD: operación bloqueada por la política de Vertex-Core ({type(node).__name__}).",
            )

    try:
        normalized = tree.sql(dialect=dialect, pretty=True)
    except SqlglotError as e:
        return _result(False, sql_query, f"No se pudo regenerar el SQL: {e}")

    return _result(True, normalized, None)


if __name__ == "__main__":
    casos = {
        "select_ok": "```sql\nSELECT datacenter, AVG(cpu_load) AS avg_load FROM servidores "
                     "WHERE estado = 'ACTIVO' GROUP BY datacenter ORDER BY avg_load DESC;\n```",
        "cte_ok": "WITH t AS (SELECT id FROM a) SELECT * FROM t",
        "union_ok": "SELECT id FROM a UNION SELECT id FROM b",
        "delete_sin_where": "DELETE FROM users",
        "delete_con_where": "DELETE FROM users WHERE 1=1;",
        "update": "UPDATE users SET admin = 1",
        "stacking": "SELECT 1; DROP TABLE users;",
        "pragma": "PRAGMA table_info(users)",
        "attach": "ATTACH DATABASE 'x.db' AS x",
        "select_into": "SELECT * INTO copia FROM users",
        "basura": "SELEC * FRM users",
    }
    esperado_valido = {"select_ok", "cte_ok", "union_ok"}
    fallos = 0
    for nombre, sql in casos.items():
        r = validate_and_secure_sql(sql)
        ok = r["valid"] == (nombre in esperado_valido)
        fallos += not ok
        print(f"[{'OK ' if ok else 'FALLO'}] {nombre:18} valid={r['valid']!s:5} {r['error'] or ''}")
    print(f"\n{len(casos) - fallos}/{len(casos)} casos correctos")
    raise SystemExit(1 if fallos else 0)
