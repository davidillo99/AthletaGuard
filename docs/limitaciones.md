# Limitaciones actuales

Listado de los problemas conocidos en la entrega NF3. Las métricas proceden de `docs/experiments/metricas_v1.0.md`.

## Bugs conocidos

No hay bugs conocidos que impidan el flujo completo. Estos comportamientos pueden parecer errores:

1. **La fecha prevista puede ser de 2022.** Sin fecha, la predicción usa el último día válido, y los datos acaban en 2021. El sistema no trabaja con datos actuales.
2. **Repetir una predicción crea otra fila.** El histórico registra cada ejecución, aunque el resultado sea el mismo.
3. **Reejecutar la ingesta borra las predicciones.** La base de datos se recrea por completo.
4. **`PORT` solo funciona con `python -m src.backend.main`.** El comando `uvicorn` usa `--port` o, por defecto, el 8000.
5. **Aviso de obsolescencia en las pruebas.** Starlette recomienda sustituir `httpx` por `httpx2` en el cliente de pruebas. No afecta a los resultados.
6. **Los selectores de fecha admiten días sin datos.** El error se muestra después, al pedir la predicción (422).

## Limitaciones del modelo

1. **No predice lesiones ni sobreentrenamiento clínico.** Predice si una jugadora declarará fatiga alta al día siguiente. "Riesgo de sobrecarga" es una reformulación permitida por NF2 §7.3 y §13, no una medida clínica.
2. **La carga aporta poco.** El bienestar suma el 83 % de la importancia del modelo y las 7 features de carga, el 17 %. Solo con carga, el sondeo previo apenas supera el azar (ROC 0,52). El modelo **no demuestra que la carga cause fatiga**: aprovecha sobre todo la persistencia del propio bienestar.
3. **Muchas falsas alarmas.** En test, la precisión es 0,383 en riesgo alto (unas 6 de cada 10 alertas son falsas) y 0,279 desde moderado.
4. **"Moderado" apenas informa.** Su tasa de fatiga alta (16,0 %) es casi igual a la media del test (15,6 %). Las diferencias útiles están entre bajo (6,4 %) y alto (38,3 %).
5. **Recall por debajo del objetivo.** El umbral moderado se fijó para un Recall de 0,80 en validación (0,801), pero en test es 0,763. No se ha reajustado, porque eso contaminaría el test.
6. **Rendimiento desigual por equipo.** AUC-PR de 0,522 en TeamA (3.227 filas) y 0,255 en TeamB (1.240 filas).
7. **Sobreajuste moderado.** AUC-PR de 0,639 en entrenamiento, 0,430 en validación temporal y 0,470 en test.
8. **Horizonte de un solo día.** No anticipa la acumulación de fatiga a más largo plazo.
9. **Mismas jugadoras en entrenamiento y test.** De las 46 jugadoras del test, solo 7 (592 filas) no aparecen en entrenamiento. La evaluación no mide la capacidad de generalizar a personas nuevas.
10. **Filas consecutivas muy parecidas.** Las ventanas se solapan y las filas no son independientes, por lo que las métricas no equivalen a 4.467 casos independientes.
11. **Sin ajuste fino ni calibración.** La rejilla solo prueba 6 combinaciones de un único algoritmo y la probabilidad no está calibrada: es una puntuación orientativa.

## Limitaciones de los datos

1. **Sentido de las escalas sin confirmar.** El artículo no indica si un valor alto de fatiga es mejor o peor. Se asume que **un valor alto es mejor**, porque fatiga y dolor bajan tras días de más carga (ρ de Spearman −0,11 y −0,18). Si la hipótesis fuese falsa, la etiqueta estaría invertida.
2. **Datos autoinformados.** Carga, bienestar y lesiones dependen de la percepción de cada jugadora y no están validados por personal médico.
3. **Sesgo poblacional.** Son 50 futbolistas de dos equipos femeninos de élite de Noruega, en 2020 y 2021. Los resultados no son extrapolables a otros deportes, niveles o poblaciones (NF2 §8.2).
4. **Sin HRV, frecuencia cardíaca ni potencia.** SoccerMon no las incluye en este subconjunto. Tampoco edad, sexo por persona, nivel ni tipo de sesión.
5. **Muchos datos ausentes.** El 53,5 % de las celdas de bienestar está vacío, y la falta de reporte no es aleatoria: es del 88 % en días con carga y del 41 % en días sin carga dentro del periodo de cada jugadora. El modelo solo se entrena y evalúa en días cuyo día siguiente tiene reporte.
6. **Un día sin carga no siempre es descanso.** El dataset no distingue descanso de falta de registro. Las rachas de hasta 13 días se tratan como descanso y las de 14 o más como "sin seguimiento". El límite es una decisión razonada, no un dato.
7. **Historial desigual.** 13 jugadoras tienen menos de 100 días con carga, y 6 menos de 60.

## Atajos de limpieza y cálculo

1. **Duplicados eliminados sin certeza.** Se quitan 76 sesiones exactamente repetidas, tratadas como dobles envíos. Podrían ser sesiones reales.
2. **Se usa `session.json` en lugar de `daily_load.csv`.** Difieren en 110 días de 3 jugadoras, y `daily_load` siempre es mayor. Algunos casos parecen errores de escritura, pero no se ha podido demostrar.
3. **Días con 4 a 6 sesiones sin revisar.** Se suman tal cual, aunque 9 días son poco creíbles.
4. **Cargas diarias extremas sin recortar.** Se conservan los 5 días por encima de 2000 (máximo 3420).
5. **Umbral de sueño arbitrario.** 38 valores de 3 horas o menos pasan a nulo.
6. **Las métricas no coinciden del todo con las originales.** Se recalculan a propósito. Incluso sin limpiar nada, el cálculo coincide con el ACWR original en el 98,7 % de las filas, y ese residuo no está explicado.
7. **Filtro de rachas retrospectivo.** Para saber que una racha llega a 14 días hay que conocer su final, así que los primeros días de esas rachas se excluyen con información futura. No afecta a las features, pero sí a qué filas se entrenan, se evalúan y se pueden predecir.
8. **Imputación por mediana.** Los valores nulos de las features se sustituyen por la mediana del entrenamiento, sin indicar al modelo que faltaban.
9. **Lesiones fuera del producto.** `injury`, `illness` y `game-performance` no se usan ni se muestran.

## Partes incompletas o parciales

| Parte | Estado |
|---|---|
| HU01, importar sesiones | Parcial: solo a través del pipeline |
| HU02, consultar entrenamientos | Parcial: tabla de las 20 últimas sesiones, sin vista de detalle |
| HU03, carga semanal | Completa, con filtro temporal |
| HU06, evolución de HRV | Sustituida por bienestar |
| Pruebas del frontend | Comprobación en navegador real, sin pruebas automáticas en el repositorio |
| Otros sistemas | Solo verificado en Windows 11 con Python 3.14; los comandos de Linux y macOS no se han ejecutado |
| Portabilidad del modelo | El `.joblib` depende de las versiones instaladas; por eso se regenera en lugar de versionarse |
| Reproducibilidad | Métricas idénticas al repetir en este equipo; no se ha comprobado en otro hardware |
| Seguridad | Sin autenticación: pensado solo para uso local |

## Pendiente para NF4

- Frontend con React y persistencia con PostgreSQL.
- Comparación con XGBoost o LightGBM y, si los datos lo justifican, LSTM o 1D-CNN.
- Autenticación y endpoint `GET /athletes/{id}/risk`.
- Recomendaciones adaptativas de intensidad, siempre como apoyo.
- Explicabilidad de cada predicción.
- Despliegue e integración continua.
- Revisión de la etiqueta y del sentido de las escalas con el cuestionario original.
