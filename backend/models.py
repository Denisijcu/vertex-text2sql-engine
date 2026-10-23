from pydantic import BaseModel, Field

class RawItem(BaseModel):
    db_id: str = Field(..., description="Identificador único de la base de datos")
    query: str = Field(..., description="Consulta SQL de referencia")
    question: str = Field(..., description="Pregunta en lenguaje natural")

class ProcessedItem(BaseModel):
    messages: list[dict[str, str]] = Field(..., description="Formato ChatML con system, user y assistant")
    valid_sql: bool = Field(..., description="Indica si la query pasó la validación sintáctica de sqlglot")