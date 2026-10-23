# Capítulo 4 — El dataset de SQL

> Borrador. Fuente: scripts/03_build_hybrid_dataset_v3.py y logs/bitacora.md (16 de octubre de
> 2026: generación del dataset, 577 consultas corregidas, 0 descartadas; exclusión de los datos
> de preferencias).

Si hay una idea que conviene grabarse antes de entrenar cualquier modelo, es esta: **el modelo es
el dataset**. El entrenamiento no le enseña al modelo lo que tú quieres que sepa, sino lo que hay
en los ejemplos que le das, con todas sus virtudes y todos sus vicios. Un vicio repetido tres mil
veces deja de ser un detalle y se convierte en el comportamiento del modelo.

Este capítulo construye la parte más grande del dataset: tres mil ejemplos de pregunta y
respuesta en SQL. Y la mayor parte del trabajo no está en conseguirlos, sino en limpiarlos.

## La fuente: preguntas, esquemas y respuestas

Para enseñar a un modelo a escribir SQL a partir de un esquema hacen falta tres cosas por
ejemplo: la estructura de las tablas, una pregunta en lenguaje natural y la consulta que la
responde. Existen varios conjuntos de datos públicos con ese formato. Este proyecto usa
`b-mc2/sql-create-context`, publicado en Hugging Face, que reúne preguntas de dos conjuntos
clásicos de investigación, WikiSQL y Spider, y les añade a cada una el `CREATE TABLE` de las
tablas que intervienen.

Una fila tiene este aspecto:

```
context:  CREATE TABLE head (age INTEGER)
question: How many heads of the departments are older than 56 ?
answer:   SELECT COUNT(*) FROM head WHERE age > 56
```

El `context` es justo lo que el usuario le dará al modelo como esquema, la `question` es la
pregunta y el `answer` es lo que el modelo tiene que aprender a producir. Las preguntas están en
inglés. El capítulo enseña cómo se convierten en ejemplos bilingües sin traducir nada.

El dataset se lee en modo *streaming*, fila a fila, sin descargarlo entero:

```python
ds = load_dataset("b-mc2/sql-create-context", split="train", streaming=True)
```

## Primera regla: reservar el examen antes de empezar

Antes de tomar una sola fila para entrenar, hay que decidir qué filas **no** se van a usar
nunca. Un modelo examinado con preguntas que vio durante el entrenamiento saca notas que no
significan nada: no estás midiendo si sabe SQL, sino si se acuerda de las respuestas.

La regla del proyecto es simple: el entrenamiento usa filas anteriores a la 10.000, y el examen
del capítulo 9 usa filas a partir de la 10.000. Para que la regla no dependa de la memoria de
nadie, el script de construcción la vigila él mismo:

```python
EVAL_RESERVED_FROM = 10000  # 08_eval.py usa estas filas

for i, row in enumerate(ds):
    if len(records) >= N_SQL:
        break
    if i >= EVAL_RESERVED_FROM:
        raise SystemExit("Se alcanzó la zona reservada para evaluación sin completar N_SQL.")
```

Si algún día alguien sube `N_SQL` sin pensar y el script necesita más filas de las disponibles
antes del límite, se para con un error en vez de comerse en silencio las preguntas del examen.
Una regla que se puede romper sin que nadie se entere no es una regla.

Con `N_SQL = 3000`, el script recorrió las primeras filas válidas del conjunto y se detuvo mucho
antes del límite.

## El vicio escondido: las comillas dobles

Ahora viene el problema que hace que este capítulo exista. Mira esta respuesta, escrita al estilo
de las del conjunto de datos:

```sql
SELECT name FROM people WHERE country = "Spain"
```

Parece correcta, y en SQLite funciona. Pero en el SQL estándar las comillas dobles no sirven para
textos: sirven para **nombres de columnas y tablas**. Los textos van entre comillas simples. SQLite
es permisivo: cuando encuentra `"Spain"` y no hay ninguna columna que se llame así, decide que
seguramente querías decir el texto `'Spain'` y sigue adelante. PostgreSQL, SQL Server o MySQL en
modo estándar no son tan amables: buscan una columna llamada `Spain`, no la encuentran y la
consulta falla con un error del tipo *column "Spain" does not exist*.

Buena parte de las respuestas del conjunto están escritas así. Si entrenas con ellas tal cual, tu
modelo aprende a escribir SQL que solo funciona en SQLite, y lo hace con total seguridad. Y como
la mayoría de las empresas no tienen sus datos en SQLite, sino en PostgreSQL, SQL Server o MySQL,
el primer cliente que lo pruebe se encontrará con errores.

### Corregirlo sin romper nada

La tentación es hacer un reemplazo de texto: cambiar todas las `"` por `'`. Pero eso rompería las
consultas que sí usan comillas dobles para lo que deben, nombres de columnas con espacios o con
palabras reservadas, como `"group"` o `"order date"`. Hace falta entender la consulta, no solo
leerla.

Para eso está **sqlglot**, una librería que convierte una consulta SQL en un árbol sintáctico: una
estructura donde cada pieza sabe lo que es. En ese árbol, `"Spain"` aparece como una *columna* con
el nombre entre comillas. La regla de corrección es entonces precisa: si un nodo es una columna,
no lleva tabla delante, está entre comillas y su nombre no coincide con ninguna columna real del
esquema, entonces no es una columna, es un texto. Se reemplaza por un literal de texto, y al
volver a escribir la consulta, sqlglot lo pone entre comillas simples.

El esquema real sale del propio `context`, leyendo los `CREATE TABLE`:

```python
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
```

Y la corrección recorre el árbol y cambia solo lo que cumple la regla:

```python
def fix_double_quoted_literals(sql: str, context: str) -> str | None:
    """Convierte "valor" (que SQLite trata como texto) en 'valor'
    cuando no es una columna real del esquema."""
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
```

Fíjate en que la consulta se lee con el dialecto de SQLite, que es el que entiende las comillas
dobles a su manera, y se escribe con el dialecto genérico, que es el estándar. La corrección es a
la vez una traducción.

Si la consulta no se puede analizar, la función devuelve `None` y el ejemplo se descarta. Es
preferible perder un ejemplo a entrenar con uno que no se entiende.

### El resultado

De los 3.000 ejemplos, **577 cambiaron**: el 19 %. Y **ninguno se descartó**. Ese 19 % tiene
sentido cuando se mira de dónde viene cada fila. Las primeras filas del conjunto salen de Spider,
con consultas de varias tablas, `JOIN` y agrupaciones, y pocas comparaciones con textos. Las
siguientes salen de WikiSQL, donde casi todas las consultas son un `WHERE columna = "valor"`. Un
ejemplo corregido del dataset final:

```sql
SELECT ... WHERE origin = 'Los Angeles' AND destination = 'Honolulu'
```

El efecto se nota en el modelo terminado. Cuando le preguntas por los servidores con estado
`ACTIVO`, escribe `estado = 'ACTIVO'`, con comillas simples. El capítulo 9 lo comprueba
automáticamente: una de las pruebas falla si aparece `"ACTIVO"` con comillas dobles.

## Segunda regla: todo ejemplo pasa por el firewall

Antes de entrar al dataset, cada consulta corregida pasa por el mismo validador que protegerá la
base de datos en producción, el del capítulo 6, en modo PostgreSQL:

```python
clean = fix_double_quoted_literals(ans, ctx)
if clean is None or not sql_validator.validate_and_secure_sql(clean, dialect="postgres")["valid"]:
    dropped += 1
    continue
```

Esto garantiza dos cosas. Que todas las consultas del entrenamiento son SQL válido en un dialecto
estándar, y no solo en el permisivo. Y que son todas de lectura: si el conjunto de datos tuviera
algún `DELETE` o `UPDATE` escondido, no llegaría a enseñarse. El modelo aprende de lo que ve, y lo
que no queremos que haga no debe aparecer en sus ejemplos como algo correcto.

Las 3.000 pasaron. Pero la comprobación no es una formalidad: es lo que te permite afirmarlo.

## La forma del ejemplo

Cada fila se convierte en una pequeña conversación en formato ChatML: un mensaje de sistema, uno
del usuario y uno del asistente. El usuario le da el esquema y la pregunta, y el asistente
responde con la consulta dentro de un bloque de código marcado como `sql`.

Aquí hay tres decisiones de diseño.

**Bilingüe sin traducir.** Las preguntas del conjunto están en inglés, pero los usuarios de este
modelo van a escribir sobre todo en español. En vez de traducir tres mil preguntas, con el riesgo
de introducir errores, se alterna el *envoltorio*: la mitad de los ejemplos llevan el system
prompt y las etiquetas en español, y la otra mitad en inglés.

```
Esquema DDL:                          DDL Schema:
CREATE TABLE ...                      CREATE TABLE ...

Solicitud: <pregunta>                 Question: <pregunta>
```

El modelo base ya entiende español. Lo que necesita aprender es que, cuando le llega un esquema
seguido de una petición, la tarea es la misma esté el envoltorio en un idioma o en otro.

**Un 10 % sin system prompt.** Uno de cada diez ejemplos no lleva mensaje de sistema. Así el
modelo aprende a hacer su trabajo aunque quien lo use se olvide de configurar el system prompt, o
lo deje en blanco. Un modelo que solo funciona con el prompt perfecto es frágil en la práctica.

```python
n = len(records)
if n % 10 == 9:  # 10% sin system prompt
    system, user = None, f"Esquema DDL:\n{ctx}\n\nSolicitud: {q}"
elif n % 2 == 0:
    system, user = SYS_SQL_ES, f"Esquema DDL:\n{ctx}\n\nSolicitud: {q}"
else:
    system, user = SYS_SQL_EN, f"DDL Schema:\n{ctx}\n\nQuestion: {q}"
records.append(msgs(system, user, f"```sql\n{clean}\n```"))
```

**Siempre dentro de un bloque `sql`.** La respuesta nunca es SQL suelto, siempre va dentro de un
bloque de código marcado. No es estética: es un contrato. El firewall y los evaluadores buscan
precisamente ese bloque para extraer la consulta, y la interfaz de chat lo muestra con colores y
un botón de copiar. Un formato de salida fijo hace que todo lo que viene detrás sea más simple y
más fiable.

## Lo que no entró: los datos de preferencias

Un modelo que solo ha visto SQL corre el riesgo de olvidar cómo conversar. La idea inicial para
evitarlo era mezclar con el SQL unos cientos de conversaciones generales de un conjunto público
muy conocido, `Anthropic/hh-rlhf`. Antes de entrenar se leyó una muestra del dataset generado, y
esos ejemplos no pasaron la revisión. Había respuestas que se inventaban leyes que no existen,
frases cortadas por la mitad y opiniones políticas sesgadas.

La explicación está en para qué se creó ese conjunto. No es un conjunto de respuestas modelo, sino
de **preferencias**: para cada pregunta trae dos respuestas, y marca cuál de las dos prefirió un
evaluador humano. La respuesta "elegida" no es una buena respuesta; es la *menos mala* de dos. Ese
tipo de datos sirve para métodos que aprenden de comparaciones, como DPO o RLHF, pero no para el
afinado supervisado que usa este proyecto, que trata cada respuesta como el ejemplo a imitar.
Enseñarle a un modelo a imitar la menos mala de dos respuestas es enseñarle a inventarse leyes.

La decisión fue sacarlos del todo. El script los deja desactivados, con el motivo escrito al lado
para que nadie los vuelva a activar sin saber por qué:

```python
# hh-rlhf desactivado: sus respuestas "chosen" son datos de preferencia (la menos mala de dos),
# no respuestas de referencia; incluyen leyes inventadas, frases cortadas y sesgo político.
# Sirven para DPO, no para SFT.
N_HH = 0
```

La capacidad de conversar no se perdió: el capítulo siguiente la enseña con ejemplos escritos a
propósito, que dicen exactamente lo que el modelo debe decir. Pocos ejemplos buenos valen más que
muchos dudosos.

La lección general vale para cualquier dataset que no hayas escrito tú: **antes de entrenar, lee
una muestra con tus propios ojos.** No las estadísticas, los ejemplos. Diez minutos de lectura te
pueden ahorrar una noche de entrenamiento y un modelo que miente.

## El archivo final

Todos los bloques del dataset, el de SQL de este capítulo y los de comportamiento del siguiente,
se validan con un modelo de Pydantic que exige al menos dos mensajes por ejemplo, se mezclan con
una semilla fija (`42`) para que el orden sea reproducible, y se escriben en un archivo JSONL, un
ejemplo por línea:

```powershell
python scripts/03_build_hybrid_dataset_v3.py
```

La línea que importa de la salida, la del bloque de SQL, es esta:

```
-> 3000 ejemplos (577 con comillas corregidas, 0 descartados)
```

Con los bloques del capítulo 5, el archivo `dataset/processed/train_vertex_hybrid_v3.jsonl` tiene
**3.302 ejemplos**. Tres mil enseñan SQL. Los otros trescientos dos enseñan todo lo demás.

## Lo que te llevas de aquí

- El modelo es el dataset: cualquier vicio repetido en los ejemplos se convierte en el
  comportamiento del modelo.
- Reserva las preguntas del examen antes de tocar los datos, y haz que el script vigile esa
  frontera por sí mismo.
- Los datos públicos de Text-to-SQL usan muchas veces comillas dobles para los textos, que solo
  funcionan en SQLite. Corrígelas con un analizador sintáctico, no con un reemplazo de texto: en
  este proyecto cambiaron 577 de 3.000 consultas.
- Pasa cada ejemplo por el mismo firewall que protegerá la base de datos: así todo lo que aprende
  el modelo es SQL válido y de solo lectura.
- Un envoltorio bilingüe, un 10 % de ejemplos sin system prompt y un formato de salida fijo hacen
  al modelo más robusto que más datos.
- Lee una muestra de cualquier dataset ajeno antes de usarlo. Los datos de preferencias no son
  respuestas modelo.
