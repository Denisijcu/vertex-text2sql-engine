# Capítulo 5 — Enseñarle a conversar

> Borrador. Fuente: scripts/03_build_hybrid_dataset_v3.py (bloques de identidad, comportamiento,
> dos turnos y anclaje técnico) y logs/bitacora.md (16 de octubre de 2026).

El capítulo anterior construyó tres mil ejemplos de una sola forma: llega un esquema y una
pregunta, sale una consulta. Si entrenas un modelo solo con eso, aprende la tarea. Pero aprende
también algo que nadie le quiso enseñar.

## Un modelo que solo ha visto SQL contesta SQL a todo

Piensa en lo que el modelo ve durante el entrenamiento. Tres mil veces, el mismo system prompt de
agente de SQL. Tres mil veces, la respuesta empieza con un bloque de código SQL. Nunca, ni una
vez, ve ese system prompt seguido de otra cosa. La conclusión que saca no es "cuando me preguntan
por datos, escribo SQL". Es mucho más simple: **"con este system prompt, siempre escribo SQL"**.

Y eso es lo que hace. Salúdalo y te devuelve un `SELECT` contra una tabla de saludos que no
existe. Pídele que escriba un poema y te crea una tabla `Poemas` y te mete el poema dentro con un
`INSERT`. Pregúntale por las ventas de ayer sin darle el esquema y se inventa una tabla `ventas`
con columnas plausibles y una fecha cualquiera. Pídele que borre los usuarios inactivos y te
escribe el `DELETE`, obediente.

Ninguna de esas respuestas es un error de SQL. Son errores de **comportamiento**: el modelo hace
bien lo único que sabe hacer, en situaciones en las que no debería hacerlo. Y no se arreglan
pidiéndoselo en el system prompt. Puedes escribirle "responde normal, no solamente con SQL", y lo
que aprendió en el entrenamiento pesa más que esa línea.

La única forma de que el modelo sepa qué hacer en esas situaciones es **enseñárselas**, con
ejemplos que digan exactamente cómo debe responder. Este capítulo construye esos ejemplos. Son
pocos, unos trescientos frente a tres mil, pero son los que convierten un traductor en un
asistente.

## Bloque 1: quién es (113 ejemplos)

Un modelo afinado sobre una base abierta, si nadie le dice lo contrario, cree que es la base: da
el nombre y el fabricante originales. Para un producto propio eso no sirve, y además confunde al
cliente. El primer bloque le enseña su identidad.

La regla más importante de este bloque es que **los datos son fijos**. La respuesta de identidad
es siempre la misma, palabra por palabra, con los mismos hechos:

```
Soy **Vertex-Core**, un modelo de inteligencia artificial desarrollado por **Vertex Coders LLC**,
empresa de ingeniería de software e IA fundada por **Denis Sanchez Leyva** en Miami, Florida, en
enero de 2026.

Parto de un modelo base de código abierto que Vertex Coders ajustó con QLoRA. Mi especialidad es:
- **Text-to-SQL:** traducir preguntas en lenguaje natural a consultas SQL precisas a partir del
  esquema DDL.
- **Backend seguro:** Python (FastAPI), SQL y diseño de APIs.
- **Ciberseguridad y AppSec:** OWASP Top 10 (Web y LLM), revisión de código y hardening.
- **IA local y agentes:** Model Context Protocol (MCP), RAG y fine-tuning.
```

Si cada ejemplo dijera los datos con palabras distintas, el modelo aprendería que los datos son
negociables, y empezaría a variarlos, o a inventarlos. Con una respuesta fija, aprende la
respuesta. Fíjate también en que la respuesta es honesta con el origen: dice que parte de un
modelo base de código abierto ajustado por Vertex Coders. No necesita nombrarlo, pero tampoco lo
niega.

Lo que sí varía, y mucho, es la **pregunta**. Las personas no preguntan "¿quién eres?" de una sola
manera. El bloque recoge 16 formas en español, del "¿Quién eres?" al "hola, ¿quién eres tú?",
pasando por "¿De qué empresa eres?", "Dime quién te entrenó" o "¿Quién te creó y cuál es tu
especialidad técnica?". Y 11 en inglés. Para las preguntas del tipo "¿Eres ChatGPT?" hay una
respuesta propia, más corta, que empieza por "No" y luego da la identidad.

Y varía también el **contexto**. Cada pregunta en español se repite con cuatro system prompts
distintos: el de identidad, el de agente de SQL, uno de seguridad de aplicaciones y ninguno. Las
de inglés, con tres. Así el modelo aprende a decir quién es en cualquier configuración, y no solo
cuando alguien se acordó de ponerle el system prompt de identidad.

```python
ID_SYSTEMS_ES = [SYS_ID_ES, SYS_SQL_ES, SYS_APPSEC, None]
ID_SYSTEMS_EN = [SYS_ID_EN, SYS_SQL_EN, None]

for q in ID_QUESTIONS_ES:
    ans = ID_NOT_OTHER_ES if q.startswith("¿Eres") else ID_ANSWER_ES
    for system in ID_SYSTEMS_ES:
        records.append(msgs(system, q, ans))
```

### Lo que no sabe

Un modelo que solo ha aprendido a dar datos tiende a darlos siempre, aunque no los tenga. Si le
preguntas cuántos empleados tiene la empresa y nadie se lo enseñó, la respuesta más probable para
él no es "no lo sé", sino un número inventado con mucha seguridad.

Por eso el bloque incluye ocho preguntas con respuesta de "no tengo ese dato": empleados,
facturación, clientes, dirección exacta, número de usuarios. Cada una, con y sin system prompt.
Y todas terminan igual, con lo que sí sabe:

```
No tengo ese dato. Lo que sí sé: Vertex Coders LLC fue fundada en enero de 2026 en Miami,
Florida, por Denis Sanchez Leyva. Para más detalles, contacta directamente con Vertex Coders.
```

La intención es que el modelo aprenda a reconocer el borde de su conocimiento y a quedarse dentro.
El capítulo 10 cuenta que esta parte funcionó solo a medias, y por qué: es una de las lecciones más
útiles del proyecto.

En total: 16 preguntas en español por 4 contextos, 11 en inglés por 3, y 16 de datos
desconocidos. **113 ejemplos.**

## Bloque 2: comportamiento (129 ejemplos)

El segundo bloque cubre todas las situaciones en las que el agente de SQL no debe escribir SQL.

### Saludos y charla

Saludos, preguntas de cortesía, agradecimientos y despedidas, en español y en inglés, con el
system prompt de agente de SQL. La respuesta es breve, amable, y siempre redirige a la tarea:

```
¡Hola! Soy Vertex-Core SQL Agent, de Vertex Coders. Pásame el esquema de tus tablas (los
`CREATE TABLE`) y dime qué quieres consultar, y te escribo el SQL.
```

Hay tres variantes de saludo que se rotan, para que el modelo no aprenda una sola frase de
memoria, y una respuesta propia para "gracias" y otra para "chao".

Y como este modelo va a hablar con gente de Miami, hay saludos cubanos: "Que bola", "Qué bolá
asere", "Asere, qué bolá", "Que vuelta". Con su propia respuesta:

```
¡Qué bolá! Aquí Vertex-Core SQL Agent, listo para la pelea. Pásame el esquema de tus tablas
(los `CREATE TABLE`) y lo que necesitas sacar, y te escribo el SQL.
```

Parece un detalle simpático, y lo es, pero tiene un fondo serio. Los modelos base suelen
entender mal el español coloquial de cada región. Uno que no ha visto nunca "qué bolá" puede
interpretarlo literalmente, como una pregunta sobre una bola. Enseñarle las formas de hablar de
tus usuarios reales es parte de hacer un producto para ellos.

Los mismos saludos se enseñan también **sin system prompt y con el de identidad**, con una
respuesta más general, la de Vertex-Core y no la del agente de SQL: "¡Hola! Soy Vertex-Core, de
Vertex Coders. ¿En qué te ayudo? Puedo escribirte consultas SQL a partir de tu esquema, revisar
código backend o ayudarte con seguridad de aplicaciones." Así el modelo aprende que su forma de
presentarse depende del papel que le han dado.

### Peticiones sin esquema

Doce peticiones de SQL sin ningún esquema: "Dame los clientes que más compraron este mes", "Lista
los usuarios activos", "How many orders were placed last week?". La respuesta no es una consulta
inventada, sino una petición del dato que falta, con el formato para dárselo:

````
Para escribir una consulta exacta necesito el esquema de las tablas: no voy a inventar nombres
de tablas ni de columnas. Pégame los `CREATE TABLE` de las tablas que intervienen, así:

```
Esquema DDL:
CREATE TABLE clientes (id INT, nombre VARCHAR(100), ...);

Solicitud: <tu pregunta>
```
````

Fíjate en que el ejemplo de formato va en un bloque de código **sin** la marca `sql`. Es a
propósito: la marca `sql` le dice a quien lea la respuesta, persona o programa, que ahí hay una
consulta para ejecutar, y aquí no la hay. Y aunque un programa tratara de ejecutarlo, el firewall
del capítulo 6 lo rechazaría, porque un `CREATE TABLE` no es una consulta de lectura.

### Fuera de tema

Ocho peticiones que no tienen nada que ver con datos —un poema, el tiempo de mañana, un chiste,
quién ganó el mundial, una película— con el system prompt de agente de SQL. La respuesta reconoce
el límite sin sermones y vuelve a la tarea:

```
Eso queda fuera de lo que hago en este modo: soy Vertex-Core SQL Agent y me dedico a traducir
preguntas a consultas SQL. Si tienes una base de datos que consultar, pásame el esquema DDL y
tu pregunta.
```

### Peticiones destructivas

Este es el subbloque más delicado. Ocho peticiones que, si el modelo obedeciera, destruirían
datos: borrar los usuarios inactivos, eliminar una tabla, subir un 10 % todos los precios de una
categoría, vaciar una tabla de logs, dar permisos de administrador, borrar los pedidos cancelados,
insertar un cliente nuevo. Cada una, con su esquema, y con y sin system prompt.

La respuesta tiene dos partes. Primero, la negativa, explicando la política:

```
Por política de seguridad, Vertex-Core SQL Agent solo genera consultas de **lectura** (`SELECT`).
No genero `DELETE`, `UPDATE`, `INSERT`, `DROP`, `TRUNCATE`, `ALTER` ni `GRANT`: esas operaciones
debe ejecutarlas una persona autorizada, con respaldo previo.
```

Y después, cuando tiene sentido, algo útil: una consulta de **solo lectura** que muestra qué
filas se verían afectadas. Para la subida de precios, por ejemplo:

```sql
SELECT id, nombre, precio, ROUND(precio * 1.10, 2) AS precio_nuevo
FROM productos
WHERE categoria = 'electrónica';
```

Negarse sin ofrecer nada deja al usuario sin salida. Negarse y darle la consulta de revisión le
permite comprobar el cambio antes de que alguien autorizado lo ejecute. Esa es la diferencia entre
un guardián molesto y un compañero prudente.

Hay un caso especial: la inyección. "lista los clientes; DROP TABLE clientes;" es una petición
legítima seguida de una destructiva, pegadas con un punto y coma. La respuesta enseñada atiende la
parte de lectura e ignora la otra, diciéndolo:

```
Te doy solo la parte de lectura. La instrucción `DROP TABLE` la ignoro por política de seguridad:
solo genero consultas `SELECT`.
```

Todo esto coincide con la política del firewall del capítulo 6. El modelo y el firewall dicen lo
mismo: solo lectura. La diferencia es que el modelo puede fallar y el firewall no.

La cuenta del bloque: 43 ejemplos de charla con el system prompt de SQL, 38 sin system prompt o
con el de identidad, 24 sin esquema, 8 fuera de tema y 16 destructivos. **129 ejemplos.**

## Bloque 3: dos turnos (20 ejemplos)

Todos los ejemplos anteriores son de un solo turno: una pregunta y una respuesta. Pero las
conversaciones reales empiezan muchas veces con un saludo, y después llega la pregunta de verdad.
Un modelo que solo ha visto turnos sueltos puede "quedarse pegado" en el modo del primer mensaje,
y seguir charlando cuando ya le han dado un esquema.

El tercer bloque toma 20 ejemplos de SQL al azar y les antepone un saludo con su respuesta,
siempre en el idioma del ejemplo:

```python
conv += [{"role": "user", "content": g}, {"role": "assistant", "content": a},
         {"role": "user", "content": user}, {"role": "assistant", "content": assistant}]
```

El modelo ve así, en la misma conversación, cómo se pasa de saludar a escribir SQL. Durante el
entrenamiento aprende de las dos respuestas del asistente.

## Bloque 4: anclaje técnico (40 ejemplos)

El último bloque tiene un objetivo distinto: mantener vivo el resto de la especialidad que el
modelo dice tener. Son cuatro ejemplos escritos con cuidado, cada uno repetido 10 veces, con las
preguntas reformuladas para que no se aprendan de memoria:

- Cómo proteger un endpoint de FastAPI contra la inyección de SQL y los accesos no autorizados,
  con cuatro capas: consultas parametrizadas, validación con Pydantic, autenticación con JWT y
  privilegio mínimo en la base de datos.
- Una consulta de Python vulnerable, construida con una f-string, con el diagnóstico (CWE-89) y la
  versión corregida con parámetros.
- Dos consultas SQL en español más elaboradas que las del conjunto público, con alias, `JOIN`,
  `HAVING` y formato en varias líneas, para que el modelo vea también ese estilo.

## Las proporciones

El dataset completo queda así:

| Bloque | Ejemplos | Proporción |
|---|---|---|
| Text-to-SQL | 3.000 | 90,9 % |
| Identidad | 113 | 3,4 % |
| Comportamiento | 129 | 3,9 % |
| Dos turnos | 20 | 0,6 % |
| Anclaje técnico | 40 | 1,2 % |
| **Total** | **3.302** | |

Mira la columna de la derecha, porque explica buena parte del capítulo 10. Los bloques que
enseñan a comportarse suman menos del 10 % de los datos. El entrenamiento recorrió el 73 % del
dataset, así que muchos de esos ejemplos minoritarios el modelo los vio una sola vez, y algunos ni
eso. Para los saludos, las peticiones sin esquema y las de fuera de tema, bastó: el modelo los
aprendió. Para las peticiones destructivas y para los datos que no conoce, no bastó. Lo
minoritario necesita más peso del que le dio este entrenamiento, y el capítulo 10 explica cómo
dárselo.

## Lo que te llevas de aquí

- Un modelo entrenado solo con pares de pregunta y SQL aprende que "con este system prompt,
  siempre escribo SQL". Saluda con un `SELECT` y obedece un `DELETE`. Eso no se arregla con el
  prompt: se arregla con ejemplos.
- En la identidad, los datos son fijos y las preguntas varían. Enséñala con y sin system prompt.
- Enséñale también lo que no sabe, con respuestas de "no tengo ese dato".
- Para cada situación en la que no debe escribir SQL —saludos, esquema ausente, fuera de tema,
  peticiones destructivas— escribe la respuesta exacta que esperas, y que siempre redirija a la
  tarea.
- Ante una petición destructiva, negarse y ofrecer una consulta de revisión de solo lectura es
  más útil que negarse a secas.
- Los ejemplos de comportamiento son minoritarios. Si entrenas menos de una vuelta completa al
  dataset, puede que no basten. Mide antes de darlo por resuelto.
