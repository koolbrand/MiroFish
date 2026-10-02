# Estrategia · Público con datos reales por país

*Simuloo · 2-oct-2026 · rama `feat/poblacion-por-pais` · estado: aplicado en el código y probado con los datos reales del CIS (5 estudios); pendiente de la autorización escrita del CIS y de llevar el banco a producción.*

## 1. El problema, en una frase

Los agentes del público los inventa el modelo, y el modelo, sin datos, se parece al público de EE. UU. y de los países
occidentales. Un ama de casa de EE. UU. no es una de España, y una persona inventada por un modelo suele ser el tópico de
su grupo. **Objetivo:** que las personas del público *surjan de datos estadísticos reales del país del público*, no del
estereotipo que el modelo tiene de ese país.

## 2. Qué dice la evidencia (y qué no)

> **Procedencia.** Las referencias las reunió un agente de investigación el 1-oct-2026; aquí se resume lo que de ellas
> usa el diseño. Los originales no se han vuelto a leer en esta sesión. Lo único comprobado hoy en páginas oficiales son
> las licencias de la sección 5.

| Hallazgo | Fuente | Qué cambia en el diseño |
|---|---|---|
| El modelo, por defecto, responde como un público de EE. UU. y de países occidentales | Durmus et al. 2023 · Santurkar et al. 2023 · AlKhamissi et al. 2024 · Tao et al. 2024 | Hay que **fijar el país**; no fiarse del que el modelo suponga |
| Acertar el **país** es lo que más rinde: el nombre del país aporta casi toda la mejora; recuperar a la persona concreta ≈ 0; un promedio sin modelo de países vecinos puede ganar al modelo | Wang (LSE), arXiv 2609.16395 | Anclar al país y al grupo; **no vender predicción individual**; medir siempre contra una línea base sin modelo |
| Los personajes generados arrastran estereotipos y los modelos aplanan a los grupos identitarios | Cheng et al. 2023 · Wang et al., *Nature Machine Intelligence* 2025 | Reglas antiestereotipo explícitas y **medir la dispersión dentro del grupo** |
| Con una entrevista o una encuesta del propio individuo, el modelo reproduce sus respuestas casi tanto como la persona se repite a sí misma (74 % con solo demografía, 82 % con encuesta, 86 % con encuesta y entrevista, respecto a su propia repetición) | Park et al., Stanford 2024, arXiv 2411.10109 | Es la base de anclar cada agente a **un encuestado real con sus respuestas**, no solo a su demografía |
| Persona a persona y ante estímulos nuevos la correlación es baja (r ≈ 0,20) | arXiv 2509.19088 | Se vende como **ensayo de reacciones**, no como predicción |
| Condicionar con datos demográficos reproduce patrones de subgrupos en EE. UU. (Argyle et al. 2023), pero las muestras sintéticas son frágiles ante cambios de enunciado y de modelo (Bisbee et al. 2024) | Argyle et al. 2023 · Bisbee et al. 2024 | Mismo banco, mismo método, medir antes de fiarse |
| Ninguna fuente evaluó datos de España | — | **Lo desconocemos**: hay que medirlo con el CIS (fase 1) |

## 3. La estrategia en siete principios

1. **El país primero.** Cada país tiene su propia encuesta oficial; una sola mezcla no sirve. Cada fuente es una entrada de `fuentes.py` con su vocabulario de regiones.
2. **Datos, no inventiva.** Cada persona del público se ancla a **un encuestado real y anónimo** (sexo, edad, región, estudios, situación laboral y sus respuestas). Edad, género y país son del dato; no se inventa MBTI.
3. **Grupos, no un cajón único.** El grafo da los grupos (la entidad y sus variantes); cada grupo pide a **su** segmento. Los más estrechos eligen primero y nadie se repite. La variedad dentro del grupo la pone la encuesta.
4. **Filtrar solo por lo que el texto dice.** «Jubilados» → jubilado; «madres» → mujer. Nunca se deduce edad, sexo o ingresos de una afición o un producto: así el cliché no entra por la puerta de atrás al elegir a la gente.
5. **El modelo redacta, no decide.** El prompt prohíbe inferir rasgos, política o gustos del sexo, la edad, la región o el trabajo, y manda quedarse neutral donde la ficha calla. No se le pide inventar edad ni familia ni ser «distinto de los demás».
6. **Honestidad ante la duda.** Si el país no está claro, o no hay banco de ese país, **no se ancla** y se dice (`poblacion.json` → `sin_datos` + motivo). Es mejor no anclar que anclar a la gente equivocada.
7. **Medir, no creer.** La muestra se compara con su segmento (Jensen–Shannon contra el ruido de muestreo esperable, dispersión de edad) y, con LLM, contra una línea base sin modelo.

## 4. Lo que ya está aplicado (rama `feat/poblacion-por-pais`)

```
brief + pregunta ──► detectar país (pedido / automático entre países con banco / ninguno)
grafo ──► Jev marca el público ──► expand_audience (variantes) ──► grupos (__simuloo_group)
                                                       │
            filtros por grupo (LLM propone, se valida contra el vocabulario de la fuente)
                                                       │
            banco del país ──► segmento (relajación honesta si es corto) ──► muestreo ponderado sin repetir
                                                       │
            ficha de datos reales ──► persona redactada (reglas antiestereotipo) ──► agente OASIS
                                                       │
            poblacion.json: país, quién lo decidió, grupos, reparto, avisos, calidad ──► interfaz, informe, PDF
```

| Pieza | Archivo |
|---|---|
| Registro de fuentes por país y su licencia | `services/poblacion/fuentes.py` |
| Detección del país | `services/poblacion/pais.py` |
| Banco genérico, filtrado, muestreo | `services/poblacion/banco.py` |
| Asignación por grupos, resumen, cita | `services/poblacion/__init__.py` |
| Filtros con la regla «solo lo explícito» | `services/poblacion/filtros.py` |
| Calidad de la muestra | `services/poblacion/metricas.py` |
| Integración con la generación de agentes | `services/oasis_profile_generator.py`, `entity_role_filter.py`, `simulation_manager.py` |
| API y interfaz (selector de país, «uso interno», aviso de «sin datos») | `api/simulation.py`, `Step2EnvSetup.vue`, `Step4Report.vue` |
| Constructor y medición de fidelidad | `scripts/poblacion/build_banco_cis.py`, `fidelidad.py` |

Comprobado: las pruebas pasan, incluidas las de **dos países sintéticos** que demuestran que cada país usa su banco, sus
regiones y su ficha, y que la misma descripción («mujeres de 25 a 64») da gente distinta según el país. La interfaz se
revisó con la API simulada (escritorio, móvil, español e inglés). **Con datos reales** (sección 7): banco de 20.128
encuestados y 1,4 millones de respuestas de 5 estudios del CIS, personas generadas desde fichas reales y medición con el
modelo de producción.

## 5. Fuentes por país y licencias (leídas en páginas oficiales el 2-oct-2026)

No se descargó ningún microdato ni se envió ningún formulario. «NO CONFIRMADO» = la página no lo dice o no pude leerla.

| Fuente | Cobertura | Uso comercial | Acceso | Veredicto |
|---|---|---|---|---|
| **CIS** (España) | Barómetros mensuales, ≥18 años; el último, septiembre 2026 (3577), 4.042 entrevistas por teléfono con cuotas de sexo y edad | Las [condiciones de reutilización](https://www.cis.es/es/condiciones-reutilizaci%C3%B3n-datos-del-cis) lo permiten (incluso datos en bruto) citando «Origen de los datos: Centro de Investigaciones Sociológicas»; la ficha declara CC BY 4.0. **Pero** la [Orden PRE/3188/2008, art. 6](https://www.boe.es/buscar/doc.php?id=BOE-A-2008-17961) exige autorización expresa del CIS para el uso comercial | Zip con CSV etiquetado y numérico; no probé si pide formulario | **Permitido con salvedad: confirmar por escrito** |
| **INE** (España) | Estructura sociodemográfica y hábitos (no actitudes) | Sí, CC BY 4.0 citando la fuente | Descarga directa de microdatos anonimizados | Permitido |
| **GSS** (NORC, EE. UU.) | 1972–2024; 2024 con 3.986 casos; `REGION` solo 4 regiones | No dice nada de uso comercial (copyright NORC) | Descarga directa | **No confirmado** → pedir permiso |
| **ANES** (EE. UU.) | Electorado, Time Series 2024 | «Investigación o estadística»: ambiguo | Descarga sin login | **No confirmado** |
| **Pew** | Global Attitudes 2025: 25 países, incluye Argentina, México, España, EE. UU. | Sí para los datasets que no son del American Trends Panel, con atribución; solo extractos | Cuenta gratuita | Permitido con condiciones (ATP: no confirmado) |
| **Latinobarómetro** | 2024: 17 países, ~1.200 entrevistas por país (Argentina, Chile, Colombia, México…); sin España ni EE. UU. | No: solo investigación | Descarga | Pedir licencia |
| **LAPOP** | AmericasBarometer 2023: 26 países, 1.500–1.650 por país | No; prohíbe compartir los datos y limita a análisis agregado | Aceptar acuerdo | Pedir licencia |
| **ESS** (Europa) | Ronda 11 (2023/24); ~30 países europeos | No: comercial «caso por caso» | Registro gratuito | Pedir licencia |
| **WVS / EVS** | Ola 7 (2017–22); fichero conjunto EVS/WVS con ES, US, MX, AR, CL, CO | No lucrativo | Registro | Pedir licencia (datos de 2017–18) |
| **Eurobarómetro** (GESIS) | UE-27 | No: solo investigación académica; prohíbe ceder y cruzar | Registro en GESIS | Pedir licencia |

Enlaces de las condiciones: [ESS](https://www.europeansocialsurvey.org/data/data-citation-requirements) ·
[WVS](https://www.worldvaluessurvey.org/AJDownloadLicense.jsp) · [GSS](https://gss.norc.org/terms-and-conditions.html) ·
[Latinobarómetro](https://www.latinobarometro.org/agregados) ·
[LAPOP](https://www.vanderbilt.edu/center-for-global-democracy/data/) · [Pew](https://www.pewresearch.org/about/terms-and-conditions/).

**Lo que significa para el diseño**

- **España es el único mercado con microdatos de actitudes y uso comercial publicado.** Por eso se empieza ahí.
- **Para Chile y Colombia no hay ninguna fuente con uso comercial confirmado** entre las leídas.
- **Riesgo que cambia el diseño:** LAPOP, GESIS, Pew y ANES limitan el uso a análisis agregados y prohíben investigar a individuos o ceder ficheros. Anclar *cada persona simulada a un único encuestado* y enviar ese registro a un modelo externo puede chocar con esas cláusulas. Con el CIS (reutilización abierta) no. Con las demás hay dos salidas: **autorización escrita que cubra expresamente ese uso**, o pasar a **perfiles recombinados / distribuciones conjuntas** en lugar de registros individuales (decisión de diseño pendiente, no implementada).
- Por eso **toda fuente nace como «uso interno de I+D»** y la interfaz lo muestra con una etiqueta. Solo pasa a `autorizada` con permiso escrito.

## 6. Plan por fases

| Fase | Qué | Quién | Estado |
|---|---|---|---|
| **0** | Capa por país aplicada a la generación de agentes, con CIS como primera fuente y pruebas con dos países sintéticos | Claude | ✅ en esta rama (PR abierto, sin desplegar) |
| **1** | Descargar los ZIP del CIS (MD3577, MD3535, MD3571, MD3530, MD3505), construir el banco, **revisar los normalizadores con los ficheros reales** y medir la fidelidad | Claude, con el correo de Adrián en el formulario del CIS | ✅ hecho el 2-oct-2026 (sección 7) |
| **2** | Pedir al CIS **confirmación escrita** del uso comercial ([contacto](https://www.cis.es/es/sala-prensa/contacto)). Mientras tanto, uso interno | Adrián decide · Claude redacta | ⏳ |
| **3** | Antes/después con los dos proyectos reales de producción (northkin y la cafetería): diversidad y distancia a los marginales de España con y sin datos reales; lectura humana de una muestra (Víctor) con la lista «¿la persona dice algo que su ficha no respalda?»; probar la hipótesis de la distribución real del segmento (sección 7) | Claude + Víctor | ⏳ falta llevar el banco a producción |
| **4** | Segundo país: **EE. UU.** (es el contraste del ejemplo del ama de casa). GSS (`WRKSTAT`, `SEX`, `AGE`, `DEGREE`, `MARITAL`, `XNORCSIZ`, `REGION`, peso `WTSSNRPS`); permiso de NORC. Ojo: su región son solo 4 | Claude construye · Adrián pide permiso | ⏳ |
| **5** | Latinoamérica (México, Argentina, Chile, Colombia) con Latinobarómetro (una sola entidad para los cuatro) y licencia comercial | Adrián | ⏳ |
| **6** | Europa con el ESS (un constructor cubre ~30 países). Requiere que un banco pueda tener **varios países** (hoy: un banco por fuente y país) y licencia | Claude + Adrián | ⏳ |

## 7. Resultados con datos reales del CIS (2-oct-2026)

**Banco.** 5 estudios (3505, 3530, 3535, 3571, 3577), 20.128 encuestados de 18 años o más, 156 preguntas distintas, 1,4 millones
de respuestas. Las 19 comunidades y ciudades autónomas están presentes.

**Lo que destapó el primer volcado con ficheros reales** (los normalizadores se habían escrito con etiquetas supuestas):
«F.P.» salía sin categoría de estudios; «En paro y ha trabajado antes» salía como «trabaja» (el paro quedaba en 77 de 20.128
y ahora son 1.633); y el trabajo de campo (hora, día y mes de la entrevista, tipo de teléfono, rechazos, supervisión) entraba
como si fueran respuestas de la persona. Corregido y con pruebas hechas con las etiquetas reales. También: «(NO LEER) N.S.,
duda» ya cuenta como no sabe, las preguntas que son solo un nombre propio («Sara Aagesen → Conoce») o sin enunciado
(«La bandera → Mucho») van al final de la ficha, y de las respuestas políticas entran como mucho cuatro.

**Fidelidad con el modelo de producción (MiniMax-M3).** 150 encuestados del 3535, 8 preguntas de actitud escondidas (se
excluyen sociodemografía y trabajo de campo), 300 llamadas, ≈ 0,64 $ por pasada (estimado por el script, no medido):

| Condición | Acierto | Intervalo del 95 % |
|---|---|---|
| Modelo con solo sociodemografía | 31,1 % | 28,2 – 33,7 |
| Modelo con sociodemografía **y el resto de sus respuestas reales** | 36,9 % | 34,2 – 39,8 |
| **Sin modelo:** la respuesta más común de su grupo (sexo × edad) | **43,5 %** | 40,0 – 46,7 |
| Azar | 22,9 % | — |

- Anclar a las respuestas reales **sí mejora** al modelo con solo demografía: +6,1 puntos (intervalo +3,1 a +9,2).
- **Pero el modelo no supera a la respuesta más común del grupo**, ni con las respuestas reales (−6,4 puntos; intervalo −10,0 a −3,0) ni sin ellas (−12,5). En distancia entre distribuciones (Jensen–Shannon) el modelo queda peor incluso que el azar (0,21–0,28 frente a 0,14): sus respuestas se concentran en pocas opciones, el aplanamiento que avisa la bibliografía.
- Coincide con la advertencia de Wang (LSE): una línea base sin modelo puede ganar al modelo. **Es la razón por la que Simuloo no se vende como predicción.**
- Las dos mediciones anteriores se descartaron: la primera eligió como «preguntas» el día de la semana de la entrevista y los ingresos, y la segunda repetía siete veces la misma batería y no traía intervalos. Con ellas el orden de las condiciones era el mismo.
- Límites: un solo estudio, ocho preguntas casi todas sobre tecnología y trabajo, la línea base sale de las otras 149 personas de la muestra (con todo el banco sería más fuerte), y las cifras no son comparables con las de Park et al., que están normalizadas por la propia repetición de cada persona.

**Qué implica para el diseño.** Donde el CIS ya preguntó, se usan las respuestas **reales** de esa persona (no las inferidas por el modelo); eso es lo que aporta el anclaje. Para lo que el CIS no preguntó, el modelo no mejora al promedio de su grupo: hipótesis a probar (no implementada) es dar a cada agente la **distribución real de su segmento** en las preguntas cercanas al tema del brief, en lugar de dejar que el modelo la invente.

**Personas generadas desde fichas reales.** Con un brief de producto de limpieza, tres personas (dos amas de casa de 80 y 64 años, un jubilado de 65) salieron distintas entre sí y coherentes con su ficha. Antes de que el tema mandara en la ficha, una de ellas giraba en torno a Ceuta, los incendios y los ministros porque eso preguntó el barómetro; ahora gira en torno al brief. Los temas de interés ya no incluyen cocina para el ama de casa ni bricolaje para el jubilado. Siguen quedando matices que no vienen del dato («tiene sus marcas de referencia», «rezando por los suyos»): el prompt los frena, no los elimina, y por eso la lectura humana de la fase 3.

### Antes y después con el mismo público (40 personas, mismo código de producción)

Diez grupos cuya descripción no dice nada de edad ni de sexo («quienes toman café a diario», «sensibles al precio»…) × 4 personas, mismo brief y
mismo modelo; solo cambia el interruptor. Frente a la población adulta real de España (CIS):

| | Inventadas por el modelo | Ancladas a datos reales |
|---|---|---|
| De 25 a 34 años | **45 %** (real: 12 %) | 15 % |
| Mujeres | 72 % (real: 50 %) | 40 % (dentro del ruido de una muestra de 40) |
| Distancia de edad con España (JSD) | 0,116 (ruido esperable 0,094) | **0,018** |
| Dispersión de edad | 14,3 (real: 16,3) | 16,8 |
| Profesiones más repetidas | «diseñadora gráfica freelance», «desarrollador web freelance» | «jubilado» (6, el 25 % real son 65+) |

En las personas que ya había en producción (proyectos northkin y cafetería) el sesgo era mayor: entre el 79 y el 88 % de 25 a 34 años y entre el 74 y el 82 % mujeres,
pero eran públicos acotados por el brief, así que esa cifra por sí sola no prueba el sesgo.

## Prueba completa en producción con el Kool Café (2-oct-2026)

Flujo entero (brief → ontología → grafo → preparación → 10 rondas → informe → PDF) en producción, cuatro pasadas con el mismo brief: una **sin** datos reales y tres **con**
ellos. Después, jueces independientes **a ciegas** (3 por dimensión, orden A/B alternado, sin saber cuál es la «nueva»).

**Lo que destapó, ya corregido** (PR #67–#70): el fichero final de perfiles perdía la marca de dato real; con un tema que la encuesta no cubre (el precio del café) los agentes
hablaban de lo que preguntó el barómetro (Ceuta, incendios, el Papa) → ahora un modelo ELIGE, una vez por simulación y solo de la lista de preguntas, las 15 relevantes;
el modelo de razonamiento devolvía vacío 4 de cada 6 veces → reintento con más espacio; «Universidad de Vigo» salía como una jubilada de 80 años → las instituciones no se anclan;
la cita «Fuente de datos» no salía en pantalla en el informe (sí en el PDF); el interruptor aparecía apagado al volver a una simulación ya preparada con datos reales.

**Veredicto de los jueces a ciegas** (versión sin datos reales contra cada versión con datos reales):

| Dimensión | Con datos reales (1.ª) | Con datos reales (versión final) |
|---|---|---|
| Personas: menos tópicos y más variedad | **3 de 3** | **3 de 3** |
| Informe: más creíble y útil para decidir el precio | 0 de 3 | 0 de 3 |
| Global: refleja mejor a la gente de Vigo | 1 de 3 | 0 de 3 |

**Cómo leerlo, sin adornos.**
- Las personas con datos reales son menos tópicas y más variadas, y los jueces lo ven los seis de seis.
- Pero el informe y el conjunto lo prefieren, también por unanimidad en el informe, con las personas inventadas: más color local (barrios, alquileres, apellidos gallegos), reacciones más viscerales y
  menos «consenso amable». **El color inventado no es realismo**: los 280 € de alquiler o el gato «Rust» no vienen de ningún dato. Los jueces premian lo que suena a Vigo, no lo que es cierto.
- Falla algo real: el banco es **nacional** y el brief es **local**. Con datos reales salió una teletrabajadora de Extremadura y una estudiante de Madrid como público de un café de Vigo. Solo se filtra
  por región cuando el nombre del grupo cita un lugar, y si el segmento queda corto la región es lo primero que se relaja.
- Límites: una ejecución por brazo, jueces que son modelos (con sesgo a favor de lo vistoso), muestras de 3 a 4 personas de público, y que la ontología cambia de una ejecución a otra (9, 10 y 6 agentes).

**Siguientes pasos, sin implementar:** (1) aplicar a **todos** los grupos la región que sitúa el brief y bajar el mínimo de casos para no relajarla; (2) probar la hipótesis de dar a cada agente la
**distribución real de su segmento** en las preguntas cercanas al tema; (3) pedir a Jev que no marque instituciones como público; (4) repetir con más agentes y con un segundo brief.

## Alcance geográfico de la simulación (3-oct-2026)

**Por qué.** Tras la prueba del Kool Café, Adrián señaló el fallo de fondo: el banco era nacional y el brief local (salió una teletrabajadora de Extremadura para un café de Vigo), y a la inversa, para un problema nacional no tiene sentido sacar a todo el mundo de una ciudad. El sistema tiene que decidir **dónde vive el público** antes de montar el ecosistema, y el agente del informe tiene que saberlo.

**Qué hace cada nivel.**

| Nivel | A quién se busca | Personas que no salen de la encuesta | Informe |
|---|---|---|---|
| Local (ciudad, comarca, provincia) | Región + provincia que el banco conoce, en TODOS los grupos | «vive en la zona del estudio» (con el sitio, si el modelo grande lo dio) | no extrapolar al país; sin inventar competencia ni cifras |
| Regional | La región (o varias comunidades) | de cualquier ciudad de la región | no extrapolar al país |
| Nacional | Todo el país, sin acotar por lugar | de cualquier parte, sin la sede por defecto | no atribuir lo observado a una ciudad |
| Multinacional / Mundial | No se ancla a la encuesta de un solo país | una cultura distinta por persona, repartidas a propósito | no generalizar a un país; muestras pequeñas por cultura |

**Cómo se decide.** Jev (TypeSafe System One) responde en ~0,5 s con una sola petición: el nivel, una pregunta de sí/no por cada región del banco y la provincia. Si duda, falla o es multinacional, decide el modelo grande, que además extrae el nombre del sitio y los países. La persona puede fijarlo a mano (selector del paso 2).

**Medido** con 50 briefs etiquetados a mano (`scripts/poblacion/evaluar_alcance.py`): el modelo grande solo acierta el nivel exacto en 48–49 de 50 y es aceptable en 50 de 50; con Jev primero, Jev decide 37 de 50 con el 100 % bien (mediana 0,5 s) y los 13 restantes pasan al modelo grande. Es decir, Jev no baja la calidad y quita el coste de espera en tres de cada cuatro casos.

**Revisión adversarial** (4 lentes, 2 escépticos por hallazgo): 38 hallazgos, 29 confirmados. Los que importaban: con Jev el «lugar» salía como la provincia (Vigo → Pontevedra) o vacío; en nacional salía siempre «España» por haber un solo banco; una provincia sin región no filtraba nada; una provincia clara se perdía por un «sí» suelto a otra región; al fijar a mano local/regional se perdía el lugar; los grupos de visitantes se forzaban al lugar; el informe local mandaba «contextualizar con competencia y estacionalidad» sin datos (invitaba a inventar); en pantalla, volver a generar sobre una simulación ya preparada se daba por terminado a los 2 s con los datos viejos. Todos corregidos con su test. **Lección:** un modelo rápido decide bien el *nivel*, pero no extrae *nombres*; lo que no extrae se queda vacío y se dice la zona real, no se rellena con otra cosa.

**Límites.** Jev no extrae ciudades ni países; el reparto de culturas es parejo (no pondera por población mundial) y con pocos agentes por cultura las diferencias son orientativas; no hay una opción «el brief no dice dónde» (se elige el nivel más razonable y se dice el motivo); no se ha medido todavía si el alcance mejora el informe (solo que las personas dejan de ser de otro sitio).

## 8. Cómo sabremos que funciona (criterios de aceptación)

Criterios de aceptación de la fase 1 (se fijan *antes* de mirar los resultados):

1. **Marginales:** Jensen–Shannon de sexo, edad, región, estudios y situación laboral de un público sin filtros frente al país, dentro del ruido de muestreo esperable (`metricas.umbral_ruido`).
2. **Variedad:** dispersión de edad dentro de cada grupo ≥ la que corresponde a su segmento (el aviso «aplanado» no salta).
3. **Fidelidad con LLM** (`fidelidad.py`): la condición b (con respuestas) supera a la a (solo demografía) ✅ y las dos a la **línea base sin modelo** (moda del grupo) ❌ (resultado de la sección 7). Si el modelo no gana a la moda, no aporta y se dice.
4. **Sin tópicos:** en una muestra leída por una persona, ninguna persona afirma nada que su ficha no respalde.
5. **Por subgrupo, no solo en media:** el acierto no cae en mujeres, mayores o regiones pequeñas más que en el resto.

Ya se mide en cada generación: `poblacion.json → calidad` (por grupo y global). El coste de una medición con LLM se calcula con
`--estimar` antes de gastar nada; no se ha ejecutado ninguna.

## 9. Qué NO hace (y lo que desconocemos)

- **No predice a individuos**: la evidencia dice que la recuperación individual es casi nula. Se presenta como ensayo de reacciones.
- **No hay evidencia publicada con datos de España**: hasta medirlo con el CIS, que funcione aquí es una hipótesis.
- Los barómetros del CIS son telefónicos con cuotas de sexo y edad, no probabilísticos puros: se usa el peso del estudio.
- Las respuestas son de la fecha de cada estudio; el mundo se mueve. Cada ficha cita su estudio.
- Una encuesta solo contiene lo que preguntó: si el tema del brief no está en ella, la ficha calla y la persona queda neutral.
- El texto de la persona sigue escribiéndolo un modelo: las reglas lo frenan, no lo eliminan. Por eso la lectura humana de la fase 3.
- Minimización de datos: la ficha que llega al modelo lleva la **región** (comunidad autónoma) pero **no la provincia**, que se queda en el banco. Junto a edad, sexo, estudios y respuestas sería un cuasi-identificador de más (decidido el 2-oct-2026).

## 10. Decisiones que necesito de Adrián

1. **¿Pido al CIS confirmación escrita?** Redacto el correo; no sale nada sin su «sí, envíalo».
2. **Llevar el banco (117 MB, en tu Mac) a producción.** No tengo SSH al servidor de Coolify; ¿lo subimos por el almacenamiento persistente de Coolify o me das acceso? Sin ello el interruptor no aparece en producción.
3. **País siguiente:** recomiendo EE. UU. (contraste directo con España). ¿O Latinoamérica antes?
4. **¿La etiqueta «Uso interno de I+D» la ve todo el mundo o solo el administrador?** Ahora la ve todo el mundo.
5. **Para las fuentes con cláusula de «solo agregados»:** ¿pedimos permiso que cubra el uso, o pasamos a perfiles recombinados?
