# Prefacio

Este es el segundo libro que nace de una tarjeta gráfica de seis gigas.

El primero, *Vertex-Core*, contaba cómo construí mi propio modelo de lenguaje en casa, con
hardware modesto y sin atajos. Al terminarlo me quedó una idea dando vueltas: si un modelo
general se podía afinar en mi máquina, un modelo especializado en una sola tarea debía poder
hacerla mejor que modelos mucho más grandes. Y había una tarea que tenía delante cada día: la de
preguntarle cosas a una base de datos.

Todas las empresas con las que trabajo tienen sus datos importantes en una base de datos. Y en
todas, entre la persona que quiere saber algo y la respuesta, hay alguien que tiene que escribir
el SQL. A veces ese alguien soy yo. Los asistentes en la nube pueden escribirlo, pero para eso
hay que mandarles la estructura de tus tablas, y muchas veces tus datos. Para un negocio con
datos de clientes, de pacientes o de nóminas, eso no es un detalle. Por eso quise un modelo que
hiciera ese trabajo sin salir de la máquina.

Lo que vas a leer es cómo lo construí, en el orden en que lo hice, con las cifras que medí y con
los problemas que me encontré. Hay capítulos de los que estoy orgulloso, como el del firewall o
el de la evaluación, y hay uno entero dedicado a lo que el modelo todavía hace mal. Lo escribí
porque creo que un libro técnico que solo enseña lo que salió bien no te prepara para lo que te va
a pasar a ti. Y porque, si vas a poner un modelo delante de un cliente, necesitas saber dónde
falla antes que él.

Sigo trabajando de noche en un almacén y programando en las horas que me quedan. Vertex-Core SQL
se entrenó en una de esas horas libres, una tarde: cuatro horas y media con la tarjeta al 99 %
mientras yo miraba la barra de progreso preguntándome si se había colgado. No se había colgado. El capítulo 7
cuenta cómo saberlo.

Ojalá este libro te sirva para construir el tuyo. Y ojalá, cuando le preguntes algo a tus datos
en tu propio idioma y te conteste con la consulta exacta, sientas lo mismo que sentí yo.

— Denis Sánchez Leyva
Miami, 2026
