# Conclusión — Lo que cuesta un modelo propio

Al empezar este libro dije que un modelo propio ya no es cosa de laboratorios con presupuesto.
Después de once capítulos, puedo decir con más precisión cuánto cuesta.

En **hardware**, una tarjeta de 6 GB que ya tenía y un disco con espacio. En **tiempo de máquina**,
cuatro horas y veintiocho minutos de entrenamiento y unos minutos de exportación y de evaluación.
En **dinero**, la electricidad de una tarde. Si alguien te dice que afinar un modelo exige
servidores alquilados y presupuestos de empresa grande, este proyecto es la prueba de lo
contrario.

Pero esa no es la parte cara. La parte cara es todo lo que no se ve en la barra de progreso.

Es leer una muestra del dataset antes de entrenar, y descubrir que las comillas de tres mil
consultas solo funcionan en SQLite. Es escribir a mano, una por una, las respuestas de los
trescientos ejemplos que enseñan al modelo a saludar en vez de inventarse una tabla de saludos. Es construir un firewall con su
propio examen, sabiendo que el modelo va a fallar. Es pasar una tarde persiguiendo cuatro tokens
invisibles y descubrir que la primera corrección lo empeoraba todo. Es escribir dos evaluadores,
encontrarles bugs, corregirlos y volver a medir. Y es tener la honestidad de dedicar un capítulo
entero a lo que todavía falla.

Ese trabajo no lo hace ninguna GPU. Y es exactamente lo que separa un modelo que funciona en una
demo de uno que se puede poner delante de un cliente.

## Lo que queda

Vertex-Core SQL, tal como se publica con este libro, hace bien su trabajo principal. Con 95
preguntas que nunca había visto, devuelve el resultado correcto en el 78,9 % de los casos, todo
lo que genera es de solo lectura, casi todo se ejecuta sin errores, y lo hace cuatro veces y media
más rápido que un modelo de código de casi el doble de tamaño. Saluda, pide el esquema cuando le
falta y no se mete donde no le llaman.

Y tiene tres fallos documentados, cada uno con su mitigación y su plan de corrección. El
siguiente modelo ya está diseñado, y se diseñó con el examen de este: más peso para lo
minoritario, más variedad en las peticiones destructivas, una vuelta completa al dataset y un
examen que no se pueda memorizar. Ese es el ciclo que este libro quería enseñarte, más que
cualquier configuración concreta: **construir, medir, documentar lo que falla y volver a
construir con lo aprendido.**

## Lo que te llevas

Si has seguido el libro con tu máquina al lado, ahora tienes algo más que un modelo. Tienes un
proceso que puedes repetir para cualquier otra tarea concreta: clasificar tickets, extraer datos
de facturas, responder sobre la documentación de tu empresa. Las piezas son las mismas. Una base
con una licencia que te permita usarla. Un dataset limpio, con su zona de examen reservada.
Ejemplos que enseñen a comportarse, no solo a acertar. Una capa de seguridad que no dependa del
modelo. Un entrenamiento que quepa en tu hardware. Una exportación que respete la plantilla. Y dos
exámenes, uno de la tarea y otro del comportamiento, que te digan la verdad.

Ojalá construyas el tuyo. Y cuando lo hagas, mídelo.
