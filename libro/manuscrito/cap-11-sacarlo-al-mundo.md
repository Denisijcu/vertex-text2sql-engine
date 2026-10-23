# Capítulo 11 — Sacarlo al mundo

> Borrador. Fuente: models/vertex-coders/vertex-core-sql-4b-v3/ (README.md, Modelfile, NOTICE,
> LICENSE), README.md del proyecto y logs/bitacora.md (16 de octubre de 2026: Model Card y
> subida a Hugging Face).

Un modelo que solo funciona en la máquina de quien lo entrenó es un experimento. Este capítulo lo
convierte en algo que otra persona puede descargar, cargar en su aplicación favorita y conectar a
su propio programa, con todo lo necesario para hacerlo bien y legalmente. Son cuatro destinos:
LM Studio, Ollama, llama.cpp y tu propio código. Y una publicación: Hugging Face.

## LM Studio

LM Studio es la forma más cómoda de usar el modelo en Windows: una aplicación de escritorio con
chat, gestor de modelos y un servidor local compatible con la API de OpenAI. Es la que se usó en
todo este proyecto.

**Antes de importar, decide dónde vivirán los modelos.** Por defecto, LM Studio guarda los modelos
en una carpeta de tu perfil de usuario, en C:, y cuando importas un archivo, lo copia allí. Con el
principio del capítulo 3, todo en un disco con espacio, conviene cambiar una sola vez la carpeta
de modelos, desde la sección de modelos de la aplicación, a una ruta del disco grande. La otra
opción es elegir, al importar, enlazar el archivo en vez de copiarlo.

**Importa el GGUF** de `models\vertex-coders\vertex-core-sql-4b-v3\` y cárgalo. Aparecerá con el
nombre de los metadatos, *Vertex-Core SQL 4B v3*.

**Configúralo una vez y guárdalo como preset:**

- System prompt: `Eres Vertex-Core SQL Agent, experto en traducir solicitudes a consultas SQL
  exactas basadas únicamente en el esquema DDL proporcionado.` Si lo vas a usar delante de
  clientes, añade los datos fijos de la empresa, como explica el capítulo 10.
- Temperatura: 0,2. Para SQL interesa la respuesta más probable, no la más creativa.
- Contexto: 4.096 tokens. Suficiente para esquemas de varias tablas.
- **No cambies la plantilla de chat.** La correcta va incrustada en el archivo. Si LM Studio te
  ofrece usar otra, o si alguna vez ves que las respuestas empiezan con `<tool_call>`, vuelve a la
  del modelo. Es la lección entera del capítulo 8.

**Comprueba el servidor.** Con el servidor local activo, desde PowerShell:

```powershell
(Invoke-RestMethod http://localhost:1234/v1/models).data.id
```

El identificador que aparezca es el que usarás en los scripts y en tu código. En este proyecto era
`vertex-core-v3`. Y recuerda lo del capítulo 9: comprueba que el identificador existe antes de
pedirle nada, porque si no existe, el servidor puede contestar con otro modelo sin avisar.

## Ollama

Ollama funciona por línea de comandos y es muy usado en servidores. En la carpeta del modelo está
el `Modelfile`, que le dice a Ollama qué archivo cargar, con qué system prompt, con qué plantilla y
con qué parámetros:

```
FROM ./vertex-core-sql-4b-v3.Q4_K_M.gguf

SYSTEM """Eres Vertex-Core SQL Agent, experto en traducir solicitudes a consultas SQL exactas
basadas únicamente en el esquema DDL proporcionado."""

TEMPLATE """...plantilla con el prefijo del capítulo 8..."""

PARAMETER stop "<|im_end|>"
PARAMETER stop "<|endoftext|>"
PARAMETER temperature 0.2
PARAMETER top_p 0.9
PARAMETER repeat_penalty 1.1
PARAMETER num_ctx 4096
```

Desde `E:\vertex-text2sql-engine\models\vertex-coders\vertex-core-sql-4b-v3`:

```powershell
ollama create vertex-sql -f Modelfile
ollama run vertex-sql
```

Ollama también ofrece una API compatible con la de OpenAI, en `http://localhost:11434/v1`. Los
scripts de evaluación del capítulo 9 la aceptan con `--base-url`.

## llama.cpp

Para quien quiera el motor sin capas de por medio, llama.cpp trae un servidor propio. La opción
importante es `--jinja`, que le dice que use la plantilla incrustada en el archivo:

```bash
llama-server -m vertex-core-sql-4b-v3.Q4_K_M.gguf --jinja -c 4096 --temp 0.2
```

## Conectarlo a tu código

Ahora, lo que convierte el modelo en un producto: usarlo desde un programa, **con el firewall en
medio**. Este es el esqueleto mínimo, en Python, de una función que recibe un esquema y una
pregunta y devuelve una consulta segura o una respuesta de texto:

```python
import importlib.util
import requests

# El firewall del capítulo 6 (el nombre del archivo empieza con un dígito: se carga así)
spec = importlib.util.spec_from_file_location("sql_validator", "scripts/06_sql_validator.py")
sql_validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sql_validator)

SERVIDOR = "http://localhost:1234/v1"
MODELO = "vertex-core-v3"
SYSTEM = ("Eres Vertex-Core SQL Agent, experto en traducir solicitudes a consultas SQL exactas "
          "basadas únicamente en el esquema DDL proporcionado.")


def preguntar(esquema: str, pregunta: str) -> dict:
    r = requests.post(f"{SERVIDOR}/chat/completions", timeout=120, json={
        "model": MODELO,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Esquema DDL:\n{esquema}\n\nSolicitud: {pregunta}"},
        ],
    })
    r.raise_for_status()
    texto = r.json()["choices"][0]["message"]["content"]

    if "```sql" not in texto:
        # El modelo no propuso una consulta: saluda, pide el esquema o se niega.
        return {"tipo": "texto", "respuesta": texto}

    v = sql_validator.validate_and_secure_sql(texto, dialect="postgres")
    if not v["valid"]:
        # El modelo propuso algo que no es una lectura: NO se ejecuta.
        return {"tipo": "bloqueado", "motivo": v["error"]}
    return {"tipo": "sql", "consulta": v["sql"]}
```

La función nunca ejecuta nada por su cuenta. Devuelve una de tres cosas: texto para mostrar, una
consulta bloqueada con su motivo, o una consulta validada. Solo esta última se ejecuta, y siempre
con una conexión de solo lectura.

### El usuario de solo lectura

En PostgreSQL, crear ese usuario son unas pocas órdenes. Este ejemplo crea un rol que solo puede
leer las tablas del esquema `public` de una base llamada `nominas`, con las transacciones en modo
de solo lectura por defecto y un tiempo máximo por consulta:

```sql
CREATE ROLE vertex_lector LOGIN PASSWORD 'cambia-esta-clave';
GRANT CONNECT ON DATABASE nominas TO vertex_lector;
GRANT USAGE ON SCHEMA public TO vertex_lector;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO vertex_lector;
ALTER ROLE vertex_lector SET default_transaction_read_only = on;
ALTER ROLE vertex_lector SET statement_timeout = '5s';
```

Con esto, aunque una escritura atravesara el firewall, la base de datos la rechazaría, y una
consulta de lectura que tarde demasiado se cortaría a los cinco segundos. Son las capas de defensa
del capítulo 6, aplicadas.

### El esquema lo pone la máquina

Y para el tercer fallo del capítulo 10, las columnas supuestas: no le pidas el esquema al usuario.
Léelo del catálogo de la base de datos antes de cada pregunta, por ejemplo de
`information_schema.columns` en PostgreSQL, y constrúyelo como `CREATE TABLE`. El usuario solo
escribe su pregunta, y el modelo recibe siempre el esquema completo y actualizado.

## La Model Card

Antes de publicar, el modelo necesita su ficha: la **Model Card**. En Hugging Face es el
`README.md` del repositorio del modelo, y es lo primero que ve cualquiera que llegue a él. Una buena
ficha responde a las preguntas que se haría alguien antes de descargarlo: qué hace, qué tal lo
hace, cómo se usa, dónde falla, cómo se entrenó y bajo qué licencia se puede usar.

La de este proyecto empieza con un bloque de metadatos que Hugging Face lee automáticamente:

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
datasets:
  - b-mc2/sql-create-context
---
```

Cada campo tiene su función. `license` hace que la página muestre la licencia. `base_model` enlaza
tu modelo con su base en el árbol de modelos de Hugging Face, y es también parte de la atribución
que exige la licencia. Las etiquetas y el idioma hacen que el modelo aparezca en las búsquedas. La
ficha completa añade un bloque `model-index` con las métricas, para que Hugging Face pinte la tabla
de resultados.

Después de los metadatos van las secciones:

- **Qué es**, en dos frases, con un resumen en español para los usuarios hispanohablantes.
- **Resultados**, con las dos tablas del capítulo 9 y una explicación de **cómo** se midieron. Un
  porcentaje sin metodología no significa nada.
- **Cómo usarlo**, con el formato del prompt, el system prompt recomendado, los ajustes y los
  comandos para LM Studio, Ollama y llama.cpp.
- **El aviso de la plantilla de chat**, en lugar visible: es la causa número uno de que alguien
  diga que tu modelo "no funciona".
- **Limitaciones**, sin maquillaje: las tres del capítulo 10, cada una con su mitigación.
- **Detalles de entrenamiento**: el método, los hiperparámetros, el hardware, la duración y la
  composición del dataset.
- **Licencia y créditos.**

La sección de limitaciones merece una defensa, porque es la que más cuesta escribir. Decir en la
portada de tu producto que a veces obedece un `DELETE` parece una mala idea comercial. Es lo
contrario. Un cliente técnico va a probar tu modelo y va a encontrar esos fallos en diez minutos.
Si ya estaban en la ficha, con su mitigación, eres el proveedor que sabe lo que vende. Si no
estaban, eres el que lo escondió.

La ficha completa está en el apéndice C.

## La licencia y el aviso

El capítulo 2 explicó por qué la licencia se elige antes que nada. Este es el momento de cumplir lo
que exige. La licencia Apache 2.0 pide dos cosas a quien distribuye una obra derivada: incluir una
copia de la licencia y conservar los avisos de atribución.

Por eso la carpeta del modelo lleva dos archivos además del GGUF. El `NOTICE`, que escribe el
script de exportación:

```
Vertex-Core SQL 4B v3 — Vertex Coders LLC

Este modelo es un trabajo derivado de Qwen3-4B-Instruct-2507 (Qwen Team, Alibaba Cloud),
distribuido bajo la Apache License, Version 2.0: https://www.apache.org/licenses/LICENSE-2.0

Modificaciones de Vertex Coders LLC: ajuste fino QLoRA para Text-to-SQL, identidad y AppSec.
```

Y el `LICENSE`, con el texto oficial, que se descarga una vez desde
`E:\vertex-text2sql-engine`:

```powershell
Invoke-WebRequest https://www.apache.org/licenses/LICENSE-2.0.txt -OutFile models\vertex-coders\vertex-core-sql-4b-v3\LICENSE
```

## Publicar en Hugging Face

Con la carpeta completa, publicarla es un comando. Lo que suele dar problemas es la autenticación,
así que empieza por ahí.

### El token

Hugging Face usa tokens de acceso en vez de contraseñas para las herramientas de línea de comandos.
Hay dos detalles que conviene conocer antes de crear uno.

**El tipo importa.** Un token de tipo *Read* sirve para descargar, no para subir. Para publicar
necesitas uno de tipo *Write*. Si eliges el tipo *fine-grained*, tienes que marcar a mano los
permisos de escritura sobre tus repositorios. Un token sin esos permisos se rechaza al subir.

**Los tokens caducan o se revocan.** En este proyecto, la herramienta decía que ya había una sesión
iniciada, pero al comprobarla respondió:

```
Error: Invalid user token. The token stored is invalid.
```

El token guardado de una sesión anterior ya no servía. La solución es crear uno nuevo en la
configuración de tu cuenta, en la sección de tokens de acceso, e iniciar sesión otra vez,
forzándola:

```powershell
hf auth login --force
hf auth whoami
```

`whoami` tiene que devolver tu usuario. Si da error, el problema es el token, y no tiene sentido
intentar subir nada todavía.

**Y trata el token como una contraseña.** Pégalo solo cuando la herramienta te lo pida. No lo
escribas dentro de un comando, como `$env:HF_TOKEN = "hf_..."`, porque PowerShell guarda en texto
plano un historial de todo lo que escribes. Si quieres el token solo para una sesión, pídelo así,
y en el historial solo quedará el comando:

```powershell
$env:HF_TOKEN = Read-Host "Pega tu token de Hugging Face"
```

### La subida

Con la sesión iniciada, desde `E:\vertex-text2sql-engine`:

```powershell
hf upload Denisijcu/vertex-core-sql-4b-v3-GGUF models\vertex-coders\vertex-core-sql-4b-v3 . --repo-type model
```

Si el repositorio no existe, `hf upload` lo crea. Sube los cinco archivos de la carpeta: el GGUF,
la Model Card, el `Modelfile`, el `NOTICE` y la licencia. Al terminar, abre la página del
repositorio y comprueba tres cosas: que la Model Card se ve bien, que aparece la licencia Apache
2.0 y que la tabla de resultados sale con sus números.

El sufijo `-GGUF` en el nombre del repositorio es una convención de Hugging Face: dice de un vistazo
en qué formato está el modelo, y separa esta publicación de otras que algún día podrías hacer en
otros formatos.

## Lo que te llevas de aquí

- En LM Studio: carpeta de modelos en el disco grande, el system prompt y los ajustes guardados
  como preset, y la plantilla incrustada sin tocar.
- En Ollama, el `Modelfile` lleva la plantilla con el prefijo. En llama.cpp, usa `--jinja`.
- En tu código, el modelo propone y el firewall decide, y lo que se ejecuta va siempre por una
  conexión de solo lectura con límite de tiempo.
- Pon el esquema desde el catálogo de la base de datos, no desde la memoria del usuario.
- La Model Card dice qué hace el modelo, cómo se midió, cómo se usa y dónde falla. Las limitaciones
  escritas son un argumento de venta, no un riesgo.
- Cumple la licencia: `NOTICE` más `LICENSE` junto al modelo, siempre.
- Para publicar: token de tipo *Write*, `hf auth whoami` antes de subir, y el token nunca dentro de
  un comando.
