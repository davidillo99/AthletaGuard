# AthletaGuard

Sistema de analítica deportiva que, a partir de series temporales de carga de entrenamiento y bienestar, estima un **riesgo de sobrecarga (bajo, moderado o alto)**, expresado como indicador de fatiga percibida para el día siguiente, y lo muestra en un dashboard.

> **Aviso:** las predicciones son orientativas. **No son un diagnóstico médico** ni sustituyen el criterio profesional. El modelo no predice lesiones.

## Integrantes

| Integrante | Rol |
|---|---|
| David | Project Lead & ML Engineer / Data Scientist |
| Iván | Backend & Data Pipeline Engineer |
| Arnau | Frontend Specialist & BI / UI Analyst |

## Arquitectura

```text
Datos (SoccerMon) -> Feature Engineering -> Modelo ML -> API FastAPI -> Persistencia SQLite -> Dashboard
```

La explicación completa y la comparación con el diseño de NF2 están en [docs/arquitectura.md](docs/arquitectura.md).

## Tecnologías

Python 3.14, pandas, NumPy, scikit-learn, joblib, FastAPI, Uvicorn, Pydantic, SQLite, HTML, JavaScript, Chart.js 4.4.9 (incluido en el repositorio) y pytest.

## Requisitos previos

- **Python 3.14.** Es la única versión con la que se ha probado el proyecto.
- **Git.**
- **Conexión a internet** solo para clonar e instalar dependencias. El dashboard funciona sin internet.
- No hacen falta Node, Docker ni un servidor de base de datos.

## Puesta en marcha desde cero

Ejecuta los comandos en este orden, desde la raíz del repositorio. La ingesta y el entrenamiento son obligatorios, porque la base de datos y el modelo no se versionan: se regeneran con estos comandos.

### Windows (PowerShell)

```powershell
git clone https://github.com/davidillo99/AthletaGuard.git
cd AthletaGuard
py -3.14 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m src.pipeline.ingest
python -m src.pipeline.train
uvicorn src.backend.main:app
```

Si PowerShell bloquea la activación del entorno, ejecuta antes `Set-ExecutionPolicy -Scope Process RemoteSigned`.

### Linux y macOS

```bash
git clone https://github.com/davidillo99/AthletaGuard.git
cd AthletaGuard
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m src.pipeline.ingest
python -m src.pipeline.train
uvicorn src.backend.main:app
```

Estos comandos no se han ejecutado en Linux ni en macOS: el proyecto se ha verificado en Windows 11.

### Uso

| Dirección | Contenido |
|---|---|
| <http://localhost:8000> | Dashboard |
| <http://localhost:8000/docs> | Documentación interactiva de la API (Swagger) |
| <http://localhost:8000/health> | Estado del servicio |

Para detener el servidor, pulsa `Ctrl+C`.

**Orden de arranque:** ingesta → entrenamiento → servidor → navegador.

| Comando | Qué hace | Duración aproximada |
|---|---|---|
| `python -m src.pipeline.ingest` | Limpia los datos, calcula las features y crea la base de datos | Unos segundos |
| `python -m src.pipeline.train` | Entrena y evalúa el modelo y guarda sus métricas | Menos de 1 minuto |
| `uvicorn src.backend.main:app` | Arranca la API y el dashboard | Unos segundos |

> Volver a ejecutar la ingesta **recrea la base de datos y borra las predicciones guardadas**.

## Variables de entorno

Son opcionales: sin ellas se usan los valores por defecto. Para cambiarlas, copia `.env.example` como `.env`. El proyecto no necesita secretos.

| Variable | Valor por defecto | Uso |
|---|---|---|
| `DB_PATH` | `data/processed/athletaguard.db` | Base de datos SQLite |
| `MODEL_PATH` | `models/modelo.joblib` | Modelo entrenado |
| `PORT` | `8000` | Puerto al arrancar con `python -m src.backend.main` |

El comando `uvicorn` no lee `PORT`: para cambiar el puerto, usa `uvicorn src.backend.main:app --port 9000`.

## API

| Método y ruta | Descripción |
|---|---|
| `POST /predict` | Recibe `{"id_deportista": 2, "fecha": "2021-10-15"}` (la fecha es opcional) y devuelve el riesgo, la probabilidad y el aviso; guarda la predicción |
| `GET /athletes` | Lista las deportistas |
| `GET /athletes/{id}/history` | Métricas, carga semanal, bienestar, sesiones y predicciones; admite `desde` y `hasta` |
| `GET /health` | Estado de la base de datos y del modelo |

Errores: `422` si la entrada no es válida o no se puede predecir para esa fecha, `404` si la deportista no existe y `503` si falta el modelo o la base de datos.

## Pruebas

Con el entorno activado:

```text
python -m pytest
```

El resultado de la última ejecución está en [docs/evidencias/pytest_resultado.txt](docs/evidencias/pytest_resultado.txt). La prueba del modelo real se omite si todavía no se ha ejecutado el entrenamiento.

## Estructura del repositorio

```text
data/raw/        Datos originales sin modificar, con su ficha y licencia
data/processed/  Datos limpios y base de datos (se generan, no se versionan)
models/          Modelo entrenado (se genera) y metadata.json
src/config.py    Configuración por variables de entorno
src/pipeline/    Ingesta, features y entrenamiento
src/backend/     API FastAPI, esquemas y servicios
src/frontend/    Dashboard en HTML, JavaScript y Chart.js
tests/           Pruebas automatizadas
notebooks/       Exploración reproducible de los datos
environment/     Versión de Python utilizada
docs/            Documentos de NF1 y NF2, documentación de NF3, experimentos y evidencias
```

El árbol completo y la explicación por módulo están en [docs/estructura_repo.txt](docs/estructura_repo.txt).

## Datos y licencia

Se utiliza el subconjunto subjetivo de **SoccerMon**, con licencia [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/):

> Midoglu C, Winther AK, Boeker M, et al. *A large-scale multivariate soccer athlete health, performance, and position monitoring dataset.* Scientific Data. 2024;11:553. doi:[10.1038/s41597-024-03386-x](https://doi.org/10.1038/s41597-024-03386-x). Dataset: doi:[10.5281/zenodo.10033832](https://doi.org/10.5281/zenodo.10033832).

Los archivos originales están en `data/raw/subjective/` sin modificar, con identificadores anónimos. Más detalle en [data/raw/README.md](data/raw/README.md).

Chart.js 4.4.9 se incluye en `src/frontend/chart.umd.js` bajo licencia MIT.

## Estado actual

- **Completo:** ciclo datos → features → modelo → API → persistencia → dashboard, reproducible desde cero.
- **Resultado en test (01/07/2021 a 31/12/2021):** AUC-PR de 0,470, frente a 0,246 de la referencia de persistencia y 0,156 de la Dummy. Detalle en [docs/experiments/metricas_v1.0.md](docs/experiments/metricas_v1.0.md).
- **Limitaciones principales:** el modelo predice fatiga percibida, no lesiones; en riesgo alto, unas 6 de cada 10 alertas son falsas; rinde peor en uno de los equipos; y la carga aporta poco frente al bienestar. La lista completa está en [docs/limitaciones.md](docs/limitaciones.md).
