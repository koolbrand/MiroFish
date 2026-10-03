# Reparación de calidad de simulaciones — octubre de 2026

## Problema y comportamiento nuevo

Una entidad que representaba a una persona identificada podía convertirse en un
grupo de público y recibir perfiles de encuestados anónimos. Ahora la naturaleza
semántica distingue colectivos poblacionales y personas concretas. Solo colectivos
confirmados pueden ampliarse y anclarse a datos poblacionales; la duda conserva al
actor y su identidad, sin autorizar el reemplazo por microdatos.

Los mensajes iniciales no aceptan un autor explícito desconocido o incompatible
para sustituirlo por un id o tipo arbitrario. El material original y las reglas de
incertidumbre preceden al contexto del grafo al preparar la configuración. Las nuevas
configuraciones llevan `generation_version=2`.

Los informes nuevos conservan una ficha `evidence.version=1`: escala, acciones,
población anclada conocida, duración configurada/ejecutada y disponibilidad del
material original. La fuente se obtiene exclusivamente por la relación
simulación → proyecto → grafo, con lectura acotada, y su texto no sale en los listados.
El registro de actividad no se transforma en votos, ganador o escaños. El mismo
registro persistido se incluye en el texto y el PDF. Las citas Markdown se rotulan
como simuladas y los enlaces que no constan en el material aportado se retiran.

La redacción que devuelve una sección vacía o un marcador de fallo no puede terminar
con estado `completed`. Una comprobación conservadora rechaza determinadas
declaraciones explícitas de ganador o mayoría electoral sin medición. El uso de un
esquema de respaldo se comunica en los avisos del informe.

En las etapas de configuración, ejecución e informe se explica el alcance de la
conversación simulada, la duración efectiva y, donde se dispone del calendario, las
horas pico que quedan fuera. Las vistas históricas conservan sus resultados y avisan
de la ausencia de los controles actuales. Cerrar una vista durante una petición no
inicia después una preparación ni vuelve a activar sus sondeos.

Las entrevistas globales y en lote comparten un límite de entrevistas efectivas:
consultar a una persona en ambas plataformas consume dos, no una. La validación se
hace antes de ejecutar la orden y se repite al expandir la configuración global.

## Preparación y regeneración

La preparación incorpora el material original en los perfiles y verifica los hechos
de los mensajes iniciales con citas literales, índices cerrados y comprobación de
cifras. La revisión semántica sigue dependiendo del modelo. Una respuesta truncada
no permite aprobar mensajes: se registra un código de error seguro y el intento
falla si no queda ninguno aceptado. Cada lote tiene una sola llamada, sin reintentos
del SDK, hasta 240 segundos y hasta el menor de `LLM_MAX_TOKENS_CAP` y 32.768 tokens
de salida, incluidos los tokens de pensamiento.

Los índices de revisión deben cubrir todo el lote una sola vez. Un fallo de esa
correspondencia invalida el lote; con índices inequívocos, una cita, cifra o fila
defectuosa descarta su mensaje y conserva las otras revisiones válidas. No se
aproximan citas ni se modifican mensajes para hacerlos pasar.

Una regeneración invalida primero la preparación anterior. Los archivos conservados
no acreditan el intento nuevo: iniciar exige bandera válida y correspondencia de
IDs y nombres entre configuración y perfiles de las plataformas habilitadas. Una
lectura no convierte una preparación en curso en terminada. Los relanzamientos de
ejecuciones históricas con preparación coherente continúan disponibles.

Antes de modificar archivos se comprueba, bajo el mismo candado del arranque,
si existe un proceso vivo de esa simulación, incluso si espera entrevistas tras
terminar. El conflicto rechaza la preparación sin invalidar ni matar ese proceso;
un estado histórico sin proceso vivo no bloquea por sí solo la regeneración.

El reparto poblacional muestra tamaño y fuentes sin equiparar compatibilidad de
muestreo con representatividad nacional; la expansión informa cuántas personas
añade dentro de los topes, sin prometer una proporción que no haya alcanzado.

La pantalla borra configuración y semillas del intento anterior al regenerar o
fallar, y descarta respuestas tardías. Reabrir un fallo conserva el error y los
ajustes de país/alcance; una nueva preparación exige pulsar «Reintentar» y conocer
que el runner está en reposo.

## Aplicación a resultados antiguos

El despliegue no transforma una simulación ya ejecutada en una prueba corregida.
Para repetirla con los controles nuevos hace falta una preparación nueva y una nueva
ejecución. No se migran ni se reescriben en una lectura los informes o perfiles antiguos.

## Límites que siguen vigentes

OASIS sigue siendo el motor social. No se ha incorporado un panel electoral validado,
un modelo territorial de escaños ni una calibración externa. Los controles semánticos
dependen de la clasificación del proveedor; los de redacción no verifican todas las
afirmaciones del modelo. Las fuentes aportadas tampoco se verifican automáticamente
contra internet. La ficha declara estas fronteras: un relato plausible no es una
medición ni demuestra capacidad de anticipar resultados reales.

El ensayo real posterior encontró todavía pérdida de condicionales, alteración de
cifras y mezcla de acontecimientos en biografías generadas. Añadir el texto original
al prompt no basta para certificar la memoria factual. Queda pendiente separar
pasajes acreditados y caracterización ficticia en los campos que consume OASIS,
y comprobarlos con material reservado para evaluación. Los tests de infraestructura
y los controles de mensajes iniciales no aprueban esa fidelidad individual.

## Comprobaciones reproducibles

- `bash init.sh`: guía completa en `docs/guia-operativa.md`, enlazada desde AGENTS.
- Backend: `cd backend && uv run pytest -q` con proveedores falsos y Neo4j inaccesible.
- Frontend: `cd frontend && node --test tests/*.test.js && npm run build`.
- Contratos de despliegue: `uv lock --check` en backend y `docker compose config --quiet`.
- Los tests de PDF requieren las bibliotecas del sistema descritas en la guía.

Las regresiones usan datos sintéticos; no suben microdatos ni documentos privados.
