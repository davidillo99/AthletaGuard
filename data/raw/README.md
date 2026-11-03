# Datos originales: SoccerMon (subconjunto subjetivo)

La carpeta `subjective/` contiene los 19 archivos de `subjective.zip` **sin ninguna modificación**. La limpieza se aplica después, en `src/pipeline/ingest.py`, y su resultado no se escribe aquí.

## Fuente y licencia

- **Dataset:** SoccerMon: A Large-Scale Multivariate Soccer Athlete Health, Performance, and Position Monitoring Dataset.
- **DOI del dataset:** [10.5281/zenodo.10033832](https://doi.org/10.5281/zenodo.10033832)
- **Licencia:** [Creative Commons Attribución 4.0 Internacional (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/). Se permite redistribuir citando la fuente.
- **Artículo:** Midoglu C, Winther AK, Boeker M, Dahl Pettersen S, Pedersen S, Ragab N, Kupka T, Hicks SA, Bredsgaard Randers M, Jain R, Dagenborg HJ, Pettersen SA, Johansen D, Riegler MA, Halvorsen P. *A large-scale multivariate soccer athlete health, performance, and position monitoring dataset.* Scientific Data. 2024;11:553. doi:[10.1038/s41597-024-03386-x](https://doi.org/10.1038/s41597-024-03386-x).

## Población y privacidad

50 jugadoras (27 del TeamA y 23 del TeamB) de dos equipos femeninos de élite de la liga noruega, en las temporadas 2020 y 2021. Los datos son autoinformados.

Los identificadores tienen la forma `TeamX-UUID`. Según el artículo, se eliminaron los metadatos de las jugadoras y los archivos se renombraron con cadenas aleatorias. No incluyen nombre, edad, sexo por persona ni datos de contacto.

## Archivos

| Carpeta | Archivos | Formato | Uso en el proyecto |
|---|---|---|---|
| `training-load/` | `session.json` | Sesiones por jugadora: `srpe`, `rpe`, `duration`, `date` | **Sí: fuente de la carga** |
| `training-load/` | `daily_load`, `weekly_load`, `atl`, `ctl28`, `ctl42`, `acwr`, `monotony`, `strain` (`.csv`) | Una fila por día y una columna por jugadora | No: se recalculan |
| `wellness/` | `fatigue`, `mood`, `readiness`, `sleep_duration`, `sleep_quality`, `soreness`, `stress` (`.csv`) | Una fila por día y una columna por jugadora | **Sí** |
| `injury/` | `injury.csv` | Reportes de dolor autoinformado | No: pocos casos para entrenar |
| `illness/` | `illness.csv` | Síntomas autoinformados | No |
| `game-performance/` | `game-performance.csv` | Valoración de partidos | No |

Las fechas tienen formato `dd.mm.yyyy` y van del 01.01.2020 al 31.12.2021.
