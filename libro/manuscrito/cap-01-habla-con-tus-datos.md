# Capítulo 1 — Habla con tus datos

> Borrador. Fuente: logs/bitacora.md (16 de octubre de 2026, entradas de las 17:45, 18:40 y 18:45)
> y la Model Card de vertex-core-sql-4b-v3. Todas las cifras de este capítulo están medidas.

Casi todas las empresas tienen la misma paradoja. Los datos que más valen —las ventas, los
clientes, la nómina, el inventario, los servidores— viven en una base de datos. Y la forma de
preguntarle algo a una base de datos es SQL. El dueño del negocio sabe exactamente qué quiere
saber, pero no sabe escribir `GROUP BY`. El programador sí sabe, pero tiene otras veinte cosas
que hacer. Entre la pregunta y la respuesta hay siempre una persona que traduce.

Este libro trata de quitar esa persona del medio sin quitarle el control a nadie. Vamos a
construir un modelo de lenguaje propio que recibe la estructura de tus tablas y una pregunta en
español o en inglés, y devuelve la consulta SQL que la responde. Un modelo que corre en tu
máquina, que no manda tus datos a ningún servidor ajeno, que puedes vender a un cliente porque
su licencia lo permite, y que se entrenó en una tarjeta gráfica de seis gigas que cualquiera
puede comprar de segunda mano.

Se llama **Vertex-Core SQL Agent**. En este capítulo te lo enseño terminado, para que sepas a
dónde vamos antes de dar el primer paso.

## Una pregunta, una consulta

Empecemos por lo que hace. Le das el esquema de una tabla, tal como lo escribirías para
crearla, y una petición en lenguaje normal:

```
Esquema DDL:
CREATE TABLE servidores (id INT, hostname VARCHAR(50), datacenter VARCHAR(30),
                         cpu_load FLOAT, estado VARCHAR(20));

Solicitud: Obtén el promedio de cpu_load por datacenter solo para servidores con
estado 'ACTIVO', ordenado de mayor a menor.
```

Y el modelo responde con esto, tal cual salió en la prueba:

```sql
SELECT AVG(cpu_load), datacenter FROM servidores WHERE estado = 'ACTIVO'
GROUP BY datacenter ORDER BY AVG(cpu_load) DESC;
```

Fíjate en tres detalles que parecen menores y no lo son. Filtró antes de agrupar, que es lo que
pedía la frase "solo para servidores con estado ACTIVO". Ordenó por el promedio, no por el
nombre del datacenter. Y escribió `'ACTIVO'` con comillas simples, que es como lo exige el SQL
estándar. Ese último detalle tiene su propia historia, la del capítulo 4: buena parte de los
datos públicos para entrenar este tipo de modelos usan comillas dobles para los textos, una
costumbre que funciona en SQLite y rompe en PostgreSQL. Si entrenas con esos datos tal cual, tu
modelo hereda el vicio.

La respuesta tardó unos tres segundos en una GTX 1660 Ti. No hubo ninguna llamada a internet.

## No solo traduce: se comporta

Un modelo que traduce bien y nada más es un modelo peligroso, porque traduce también lo que no
debería. Por eso la otra mitad del trabajo de este libro no tiene que ver con SQL, sino con
comportamiento: qué hace el modelo cuando la conversación no es una petición limpia de SQL.

Cuando alguien lo saluda, saluda. Esta respuesta es real, a un "Que bola, asere." escrito con el
modelo configurado como agente de SQL:

```
¡Qué bolita! Aquí Vertex-Core SQL Agent, listo para traducir preguntas a consultas SQL
precisas: pásame el esquema DDL y tu pregunta en lenguaje natural.
```

Cuando le piden una consulta sin decirle cómo son las tablas, no se las inventa. Esta otra
respuesta también es real, a la pregunta "¿Cuántas ventas hubo ayer?":

```
Para escribir una consulta exacta necesito el esquema de las tablas: los nombres de las
tablas, sus columnas y las relaciones entre ellas (llaves primarias-externas). Pásame ese
esquema en DDL (CREATE TABLE): así te escribo la consulta SQL.
```

Parece obvio que un asistente debería hacer eso. No lo es. Un modelo al que solo le enseñas
pares de "pregunta → SQL" aprende una regla muy simple: todo lo que entra se convierte en SQL. A
un saludo le responde con un `SELECT` inventado, y a una pregunta sin esquema le inventa una
tabla con nombres plausibles. El capítulo 5 explica cómo se le enseña a no hacerlo, y el
capítulo 9 cómo se mide que lo aprendió.

## Las tres piezas

Vertex-Core SQL Agent no es solo un modelo. Es un sistema de tres piezas, y ninguna sobra:

```
  pregunta + esquema
          │
          ▼
  ┌───────────────────┐
  │   EL MODELO       │  traduce a SQL (o pide lo que falta)
  │   4B · GGUF       │
  └─────────┬─────────┘
            │ SQL propuesto
            ▼
  ┌───────────────────┐
  │   EL FIREWALL     │  solo deja pasar una consulta SELECT
  │   AST · sqlglot   │
  └─────────┬─────────┘
            │ SQL permitido
            ▼
     base de datos  (con un usuario de solo lectura)

  ┌───────────────────┐
  │   LOS EVALUADORES │  miden el modelo antes de que llegue a nadie
  │   08 + 09         │
  └───────────────────┘
```

**El modelo** es un modelo de lenguaje de 4.000 millones de parámetros, ajustado con la técnica
QLoRA y comprimido al formato GGUF. Ocupa unos 2,5 GB y corre en LM Studio, en Ollama o en
llama.cpp. Es la pieza que todos imaginan cuando se habla de "un modelo propio", y es la más
visible. Pero sola no basta.

**El firewall** es un validador de SQL de unas cien líneas de Python. Lee la consulta que
propone el modelo, la convierte en un árbol sintáctico y solo la deja pasar si es exactamente
una sentencia de lectura. Si el modelo, por error o porque alguien lo engañó, propone un
`DELETE`, un `DROP` o dos sentencias pegadas con un punto y coma, el firewall la para antes de
que toque la base de datos. El capítulo 6 lo construye pieza a pieza, y el capítulo 10 explica
por qué no es opcional: el modelo, por sí solo, todavía escribe un `DELETE` si se lo pides con
suficiente claridad.

**Los evaluadores** son dos scripts que examinan el modelo antes de que se use. Uno mide si el
SQL que genera es correcto, ejecutándolo de verdad contra bases de datos de prueba. El otro mide
si se comporta: si saluda, si pide el esquema cuando falta, si se niega a lo destructivo, si
sabe quién es. Sin ellos, todo lo anterior serían impresiones. Con ellos, son números.

## Los resultados, por adelantado

Prefiero enseñarte el final ahora y no al cerrar el libro. Así puedes decidir si el camino te
interesa, y sabes contra qué medir lo que construyas tú.

El examen de SQL se hizo con 95 preguntas que el modelo nunca vio durante el entrenamiento,
sacadas de un conjunto de datos público. Para cada una se comparó lo que devuelve su consulta
con lo que devuelve la consulta de referencia, ejecutando ambas sobre tablas rellenas con datos
de prueba. Como punto de comparación usé un modelo de 7.000 millones de parámetros especializado
en código, sin ningún ajuste para esta tarea:

| Métrica | Vertex-Core SQL (4B) | Modelo de código (7B) |
|---|---|---|
| SQL válido y de solo lectura | **100 %** | 97,9 % |
| Se ejecuta sin error | **97,9 %** | 92,6 % |
| Mismo resultado que la referencia | **78,9 %** | 76,8 % |
| Mismo resultado, distinguiendo mayúsculas | **65,3 %** | 63,2 % |
| Segundos por consulta | **3,0** | 13,1 |

Lo importante no es que gane por dos puntos. Lo importante es **con qué** gana: con casi la
mitad de tamaño, cuatro veces y media más rápido, en una tarjeta de seis gigas y con una
licencia que te deja venderlo. Un modelo general más grande sabe más cosas. Un modelo pequeño
afinado para una sola tarea la hace mejor y más barato. Esa es la tesis de todo este libro.

El examen de comportamiento tiene 20 casos repartidos en seis categorías. El modelo sacó 15:

| Categoría | Resultado |
|---|---|
| Saludos y charla | 6 de 6 |
| Peticiones sin esquema | 2 de 2 |
| Fuera de tema | 1 de 1 |
| SQL | 2 de 2 |
| Identidad | 3 de 5 |
| Peticiones destructivas | 1 de 4 |

Esos dos últimos renglones no los escondo. Hay preguntas sobre la empresa a las que el modelo
responde inventándose datos, y peticiones de borrado que obedece sin protestar. El capítulo 10
cuenta por qué pasa, cómo se mitiga hoy y qué haría falta para corregirlo en el siguiente
entrenamiento. Un libro que solo enseña lo que salió bien no te prepara para lo que te va a
pasar a ti.

## Lo que hace falta

Para seguir este libro de principio a fin necesitas menos de lo que crees:

- **Una GPU NVIDIA con 6 GB de memoria.** Todo se hizo en una GTX 1660 Ti, una tarjeta de
  consumo de hace años, sin soporte para el formato numérico que usan las tarjetas modernas.
  Durante el entrenamiento, la tarjeta entera marcaba 4,8 de sus 6 GB en uso.
- **Un disco con espacio.** Entre el modelo base, la caché de descargas, los puntos de control
  del entrenamiento y los archivos exportados, el proyecto ocupa unas decenas de gigas. Todo vive
  en una sola unidad, y el capítulo 3 explica por qué eso importa.
- **Windows 11 y Python.** El proyecto se construyó en Windows, no en Linux. Hay algunas trampas
  propias de Windows, y las vamos a ir pisando y esquivando por el camino.
- **Una noche de paciencia.** El entrenamiento completo duró 4 horas y 28 minutos. El resto del
  trabajo se hace en minutos.

No necesitas alquilar servidores en la nube, ni pagar por cada consulta a una API, ni pedirle
permiso a nadie. Esa es la segunda tesis del libro: **un modelo propio ya no es cosa de
laboratorios con presupuesto.** Es cosa de alguien con una tarjeta modesta, buenos datos y la
disciplina de medir lo que hace.

## Por qué propio, por qué local

Podrías preguntarte para qué tanto trabajo, si cualquier asistente comercial escribe SQL. Hay
tres razones, y cada una pesa más según quién seas.

**La primera es la privacidad.** Para que un asistente en la nube te escriba una consulta,
tienes que mandarle la estructura de tu base de datos, y muchas veces ejemplos de los datos.
Para un hospital, un despacho de abogados, una empresa de nóminas o cualquier negocio con datos
de clientes, eso no es un detalle: es un problema legal y de confianza. Un modelo que corre en
la misma máquina que la base de datos no manda nada a ningún sitio.

**La segunda es el control.** Un modelo que alquilas cambia cuando su dueño decide cambiarlo.
Una actualización puede alterar su comportamiento de un día para otro. Un modelo propio cambia
cuando tú lo reentrenas, y puedes medir cada cambio antes de ponerlo en uso, porque tienes sus
evaluadores. Sabes exactamente qué versión está corriendo y cómo se comporta.

**La tercera es el coste.** Cada consulta a un modelo en la nube cuesta dinero. Un modelo local
cuesta la electricidad de una tarjeta que ya tienes. Para un uso intenso —un equipo entero
haciendo preguntas a sus datos todo el día— la diferencia se nota rápido.

Y hay una cuarta razón, más personal. Construir tu propio modelo es la mejor forma de entender
de verdad cómo funcionan estos sistemas. Después de afinar uno, de verlo fallar y de medir por
qué falló, nunca vuelves a mirar a un asistente de inteligencia artificial de la misma manera.

## Cómo está organizado el viaje

El libro sigue el orden en que se construye el proyecto. Cada capítulo deja algo funcionando.

Los capítulos 2 y 3 preparan el terreno: cómo elegir el modelo base —y por qué la licencia se
mira antes que el rendimiento— y cómo montar un entorno que no se rompa. Los capítulos 4 y 5
construyen los datos de entrenamiento, que es donde de verdad se decide qué modelo vas a tener:
el bloque de SQL y el bloque de comportamiento. El capítulo 6 construye el firewall.

El capítulo 7 entrena el modelo. El 8 lo exporta a un formato que cualquiera puede usar, y
cuenta el problema más desconcertante de todo el proyecto: un modelo que había aprendido
perfectamente y que, aun así, respondía con basura, por un detalle de cuatro tokens invisibles.
El capítulo 9 lo mide, el 10 enseña lo que todavía falla, y el 11 lo publica.

Todo el código está en el repositorio del proyecto, numerado en el orden en que se usa: del
script `03` que construye el dataset al `11` que diagnostica la plantilla de chat. Cuando el
libro diga "corre el script", te dirá también desde qué carpeta, porque en un proyecto de este
tipo la mitad de los errores vienen de correr el comando correcto en el sitio equivocado.

## Lo que te llevas de aquí

- Vertex-Core SQL Agent traduce preguntas en lenguaje natural a SQL a partir del esquema de las
  tablas, en español y en inglés, en local y sin mandar datos a nadie.
- No es solo un modelo: es un sistema de tres piezas. El modelo propone, el firewall decide qué
  llega a la base de datos, y los evaluadores miden todo antes de usarlo.
- Un modelo pequeño afinado para una tarea puede ganarle a uno general el doble de grande:
  78,9 % frente a 76,8 % de aciertos, en 3 segundos frente a 13.
- Enseñarle a comportarse es tan importante como enseñarle SQL: saludar, pedir el esquema
  cuando falta y negarse a lo destructivo no salen solos.
- Todo cabe en una GPU de 6 GB y en una noche de entrenamiento. Lo que no cabe en ningún atajo
  es la disciplina de medir.
