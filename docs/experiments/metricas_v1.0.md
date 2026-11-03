# Experimento RandomForest v1.0

- **Etiqueta:** fatiga del dia siguiente <= 2 (fatiga percibida alta)
- **Entrenamiento:** 11114 filas, 1764 positivos
- **Test:** 4467 filas, 697 positivos, desde 2021-07-01
- **Mejores hiperparámetros:** `{'clasificador__max_depth': 10, 'clasificador__min_samples_leaf': 20}`
- **Umbrales:** moderado 0.376, alto 0.523
- **AUC-PR en validación temporal:** 0.430
- **AUC-PR en entrenamiento:** 0.639

## Resultados en el test temporal

| Modelo | AUC-PR | Recall | Precision | F1 |
|---|---|---|---|---|
| Dummy | 0.156 | 0.000 | 0.000 | 0.000 |
| Persistencia | 0.246 | 0.362 | 0.404 | 0.382 |
| Random Forest (alerta desde moderado) | 0.470 | 0.763 | 0.279 | 0.408 |
| Random Forest (alerta solo en alto) | 0.470 | 0.558 | 0.383 | 0.454 |

## Matrices de confusión del Random Forest

- **Desde moderado:** `{'vn': 2394, 'fp': 1376, 'fn': 165, 'vp': 532}`
- **Solo alto:** `{'vn': 3143, 'fp': 627, 'fn': 308, 'vp': 389}`

## Fatiga alta observada por nivel de riesgo

| Nivel | Casos | Tasa de fatiga alta |
|---|---|---|
| bajo | 2559 | 0.064 |
| moderado | 892 | 0.160 |
| alto | 1016 | 0.383 |

## Por equipo

| Equipo | Casos | Tasa base | AUC-PR |
|---|---|---|---|
| TeamA | 3227 | 0.167 | 0.522 |
| TeamB | 1240 | 0.127 | 0.255 |

## Importancia de variables

| Variable | Importancia |
|---|---|
| fatiga_media_7d | 0.276 |
| disposicion_media_7d | 0.120 |
| dolor_muscular_media_7d | 0.091 |
| fatiga_var | 0.064 |
| horas_sueno_media_7d | 0.043 |
| calidad_sueno_media_7d | 0.041 |
| disposicion_var | 0.040 |
| acwr | 0.033 |
| cambio_carga_semanal | 0.032 |
| media_movil | 0.030 |
| carga_7d | 0.029 |
| carga_28d | 0.028 |
| calidad_sueno_var | 0.027 |
| dolor_muscular_var | 0.025 |
| estres_media_7d | 0.023 |
| horas_sueno_var | 0.023 |
| animo_media_7d | 0.021 |
| estres_var | 0.020 |
| animo_var | 0.018 |
| dias_descanso_7d | 0.009 |
| sesiones_7d | 0.008 |
