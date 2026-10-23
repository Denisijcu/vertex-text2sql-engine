import json
import logging
from pathlib import Path
import sqlglot
from sqlglot.errors import ParseError
from backend.config import settings
from backend.models import ProcessedItem

logging.basicConfig(level=settings.LOG_LEVEL, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def clean_and_format_sql() -> None:
    raw_path = Path(settings.RAW_DATA_PATH)
    processed_path = Path(settings.PROCESSED_DATA_PATH)
    processed_path.parent.mkdir(parents=True, exist_ok=True)

    if not raw_path.exists():
        logger.error(f"No se encuentra el archivo raw en {raw_path}. Ejecuta 01_download.py primero.")
        return

    logger.info("Iniciando limpieza y validación sintáctica con sqlglot...")
    
    with open(raw_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    processed_items = []
    dropped_count = 0

    for item in raw_data:
        question = item.get("question", "").strip()
        query = item.get("query", "").strip()
        db_id = item.get("db_id", "unknown")

        if not question or not query:
            dropped_count += 1
            continue

        # Validación sintáctica estricta con sqlglot (dialecto sqlite por defecto en Spider)
        try:
            parsed = sqlglot.transpile(query, read="sqlite", write="sqlite")
            if not parsed:
                raise ParseError("Query vacía tras transpilación")
            normalized_query = parsed[0]
        except Exception as e:
            logger.warning(f"Descartada query inválida [{query}]: {str(e)}")
            dropped_count += 1
            continue

        # Estructura ChatML estricta para QLoRA / Unsloth
        chatml_entry = {
            "messages": [
                {
                    "role": "system",
                    "content": f"Eres Vertex-Core SQL Agent, un modelo experto en traducir lenguaje natural a consultas SQL precisas y seguras para la base de datos '{db_id}'."
                },
                {
                    "role": "user",
                    "content": f"Esquema de BD: [{db_id}]. Pregunta: {question}"
                },
                {
                    "role": "assistant",
                    "content": f"```sql\n{normalized_query}\n```"
                }
            ],
            "valid_sql": True
        }

        try:
            validated_item = ProcessedItem(**chatml_entry)
            processed_items.append(validated_item.model_dump())
        except Exception as val_err:
            logger.warning(f"Error de validación Pydantic en registro: {str(val_err)}")
            dropped_count += 1

    # Escritura en formato JSON Lines (.jsonl)
    with open(processed_path, "w", encoding="utf-8") as f:
        for p_item in processed_items:
            f.write(json.dumps(p_item, ensure_ascii=False) + "\n")

    logger.info(f"Limpieza finalizada con éxito.")
    logger.info(f"Registros procesados y válidos: {len(processed_items)}")
    logger.info(f"Registros descartados por errores sintácticos/vacíos: {dropped_count}")
    logger.info(f"Salida guardada en: {processed_path}")

if __name__ == "__main__":
    clean_and_format_sql()