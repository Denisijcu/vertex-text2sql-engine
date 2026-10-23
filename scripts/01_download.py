import os
import json
import logging
from pathlib import Path
import requests
from backend.config import settings

logging.basicConfig(level=settings.LOG_LEVEL, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# URL pública de ejemplo de un dataset de Text-to-SQL (Spider sample oficial o equivalente JSON)
SAMPLE_URL = "https://raw.githubusercontent.com/taoyds/spider/master/train_spider.json"

def download_raw_dataset() -> None:
    raw_path = Path(settings.RAW_DATA_PATH)
    raw_path.parent.mkdir(parents=True, exist_ok=True)

    if raw_path.exists():
        logger.info(f"El archivo raw ya existe en {raw_path}. Omitiendo descarga.")
        return

    logger.info(f"Descargando dataset bruto desde {SAMPLE_URL}...")
    try:
        response = requests.get(SAMPLE_URL, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        # Guardamos una muestra representativa o el archivo completo
        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        logger.info(f"Dataset bruto descargado y guardado exitosamente en {raw_path} ({len(data)} registros).")
    except Exception as e:
        logger.error(f"Error crítico al descargar el dataset: {str(e)}")
        raise

if __name__ == "__main__":
    download_raw_dataset()