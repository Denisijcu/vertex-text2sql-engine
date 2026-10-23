# Apéndice C — La Model Card

La Model Card de Vertex-Core SQL se publica en inglés, que es el idioma habitual en Hugging Face, con
un resumen en español al principio. La versión completa está en la página del modelo:
`huggingface.co/Denisijcu/vertex-core-sql-4b-v3-GGUF`. Aquí se reproduce el bloque de metadatos
completo, que es la parte que más cuesta escribir bien, y se resume en español cada sección.

## El bloque de metadatos

```yaml
---
license: apache-2.0
base_model: Qwen/Qwen3-4B-Instruct-2507
library_name: gguf
pipeline_tag: text-generation
language:
  - es
  - en
tags:
  - text-to-sql
  - sql
  - gguf
  - qlora
  - unsloth
  - llama.cpp
  - lm-studio
  - ollama
  - vertex-coders
datasets:
  - b-mc2/sql-create-context
model-index:
  - name: Vertex-Core SQL 4B v3
    results:
      - task:
          type: text-to-sql
          name: Text-to-SQL
        dataset:
          type: b-mc2/sql-create-context
          name: sql-create-context (held-out rows 10000+, 95 scored)
        metrics:
          - type: execution_accuracy
            name: Execution match (case-insensitive)
            value: 78.9
          - type: execution_accuracy
            name: Execution match (strict)
            value: 65.3
          - type: valid_sql
            name: Valid read-only SQL
            value: 100.0
---
```

## Las secciones

**Presentación.** Qué hace el modelo en dos frases, un resumen en español y una tabla con lo
esencial: quién lo desarrolló, el tipo de modelo, el tamaño y el formato (4B, GGUF Q4_K_M, unos
2,5 GB), los idiomas, la licencia y el hardware en el que se entrenó (una GTX 1660 Ti de 6 GB, en
4 h 28 min).

**Resultados.** La tabla del examen de SQL del capítulo 9, con el modelo de código de 7B como
referencia, y una explicación de la metodología: 95 preguntas no vistas, cinco omitidas porque la
referencia del dataset no funciona en SQLite, y la comparación de resultados sobre datos
sembrados. Después, la tabla de comportamiento: 15 de 20, por categorías.

**Cómo usarlo.** El formato del prompt con un ejemplo real y su salida, el system prompt
recomendado, los ajustes (temperatura 0,2, top_p 0,9, penalización de repetición 1,1, contexto de
4.096) y los comandos para LM Studio, Ollama y llama.cpp.

**El aviso de la plantilla de chat.** Que el modelo se entrenó con un bloque de razonamiento vacío
delante de cada respuesta, que la plantilla incrustada lo añade sola, y que si se cambia por una
plantilla genérica las respuestas empiezan con tokens `<tool_call>`.

**Limitaciones.** Las tres del capítulo 10, cada una con su mitigación: no se niega por sí solo a
escribir SQL destructivo (usar siempre el firewall y un usuario de solo lectura); puede inventar
datos sobre su creador (poner los datos en el system prompt); supone nombres de columnas si solo
recibe el nombre de la tabla (pasarle el `CREATE TABLE` completo). Más dos avisos: el estilo de su
SQL sigue al de los datos de entrenamiento, y las cifras salen de 95 preguntas de un solo dataset.

**Detalles de entrenamiento.** El método (QLoRA con Unsloth y TRL, aprendiendo solo de las
respuestas), la configuración de LoRA, el optimizador, el tamaño de lote, los pasos y la
duración, el loss final y la composición del dataset por bloques.

**Licencia.** Que es una obra derivada de Qwen3-4B-Instruct-2507 bajo Apache 2.0, que el ajuste de
Vertex Coders se publica con la misma licencia y que el archivo `NOTICE` debe acompañar al modelo.

**Sobre Vertex Coders y cita.** Una línea sobre la empresa y su servicio de modelos privados
afinados, y una entrada BibTeX para citar el modelo.
