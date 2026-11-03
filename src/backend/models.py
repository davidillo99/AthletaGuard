"""Modelos de datos: esquemas Pydantic de la API y definición de las tablas SQLite."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

# Aviso obligatorio (NF2 HU09): acompaña a las respuestas de la API y al dashboard.
AVISO_NO_MEDICO = (
    "Indicador orientativo de fatiga percibida para el día siguiente. "
    "No es un diagnóstico médico ni sustituye el criterio profesional."
)


class SolicitudPrediccion(BaseModel):
    """Entrada de POST /predict. Sin fecha, se usa el último día válido de la deportista."""

    # Un campo desconocido se rechaza con 422 en lugar de ignorarse en silencio.
    model_config = ConfigDict(extra="forbid")

    id_deportista: int = Field(gt=0)
    fecha: date | None = None


class Prediccion(BaseModel):
    """Predicción guardada en la base de datos."""

    id_prediccion: int
    id_deportista: int
    fecha: str
    fecha_objetivo: str
    probabilidad: float
    riesgo: str
    modelo: str
    version: str
    creada_en: str


class RespuestaPrediccion(Prediccion):
    """Salida de POST /predict."""

    alias: str
    aviso: str


class Deportista(BaseModel):
    """Deportista con el periodo en el que tiene datos."""

    id_deportista: int
    alias: str
    equipo: str
    fecha_primera: str
    fecha_ultima: str


class MetricaDiaria(BaseModel):
    """Métricas de carga de un día. Un valor nulo indica ventana incompleta."""

    fecha: str
    carga_dia: float
    carga_7d: float | None
    carga_28d: float | None
    acwr: float | None
    fatiga_media_7d: float | None
    dolor_muscular_media_7d: float | None
    calidad_sueno_media_7d: float | None
    sin_seguimiento: int


class CargaSemanal(BaseModel):
    """Carga total de una semana (lunes a domingo)."""

    semana_inicio: str
    carga: float


class ReporteBienestar(BaseModel):
    """Reporte diario de bienestar. Sustituye a la HRV de NF2."""

    fecha: str
    fatiga: float | None
    animo: float | None
    disposicion: float | None
    horas_sueno: float | None
    calidad_sueno: float | None
    dolor_muscular: float | None
    estres: float | None


class Sesion(BaseModel):
    """Sesión de entrenamiento."""

    id_sesion: int
    fecha: str
    duracion: float
    rpe: float
    srpe: float


class RespuestaHistorial(BaseModel):
    """Salida de GET /athletes/{id}/history."""

    deportista: Deportista
    metricas: list[MetricaDiaria]
    carga_semanal: list[CargaSemanal]
    bienestar: list[ReporteBienestar]
    sesiones: list[Sesion]
    predicciones: list[Prediccion]
    aviso: str


class RespuestaSalud(BaseModel):
    """Salida de GET /health."""

    estado: str
    base_datos_disponible: bool
    modelo_cargado: bool
    version_modelo: str | None
    aviso: str


# Definición de las tablas SQLite. Los nombres siguen las entidades de NF2 §6.1.
# La tabla bienestar es nueva: sustituye a las columnas de HRV, que SoccerMon no tiene.
SQL_TABLAS = """
CREATE TABLE deportista (
    id_deportista INTEGER PRIMARY KEY,
    alias TEXT NOT NULL UNIQUE,
    equipo TEXT NOT NULL,
    id_origen TEXT NOT NULL UNIQUE
);

CREATE TABLE sesion (
    id_sesion INTEGER PRIMARY KEY AUTOINCREMENT,
    id_deportista INTEGER NOT NULL REFERENCES deportista(id_deportista),
    fecha TEXT NOT NULL,
    duracion REAL NOT NULL,
    rpe REAL NOT NULL,
    srpe REAL NOT NULL
);

CREATE TABLE bienestar (
    id_bienestar INTEGER PRIMARY KEY AUTOINCREMENT,
    id_deportista INTEGER NOT NULL REFERENCES deportista(id_deportista),
    fecha TEXT NOT NULL,
    fatiga REAL,
    animo REAL,
    disposicion REAL,
    horas_sueno REAL,
    calidad_sueno REAL,
    dolor_muscular REAL,
    estres REAL,
    UNIQUE (id_deportista, fecha)
);

CREATE TABLE metricas_derivadas (
    id_metricas INTEGER PRIMARY KEY AUTOINCREMENT,
    id_deportista INTEGER NOT NULL REFERENCES deportista(id_deportista),
    fecha TEXT NOT NULL,
    carga_dia REAL NOT NULL,
    carga_7d REAL,
    carga_28d REAL,
    acwr REAL,
    media_movil REAL,
    sesiones_7d REAL,
    dias_descanso_7d REAL,
    cambio_carga_semanal REAL,
    fatiga_media_7d REAL,
    fatiga_var REAL,
    animo_media_7d REAL,
    animo_var REAL,
    disposicion_media_7d REAL,
    disposicion_var REAL,
    horas_sueno_media_7d REAL,
    horas_sueno_var REAL,
    calidad_sueno_media_7d REAL,
    calidad_sueno_var REAL,
    dolor_muscular_media_7d REAL,
    dolor_muscular_var REAL,
    estres_media_7d REAL,
    estres_var REAL,
    sin_seguimiento INTEGER NOT NULL,
    UNIQUE (id_deportista, fecha)
);

CREATE TABLE prediccion (
    id_prediccion INTEGER PRIMARY KEY AUTOINCREMENT,
    id_deportista INTEGER NOT NULL REFERENCES deportista(id_deportista),
    fecha TEXT NOT NULL,
    fecha_objetivo TEXT NOT NULL,
    probabilidad REAL NOT NULL,
    riesgo TEXT NOT NULL,
    modelo TEXT NOT NULL,
    version TEXT NOT NULL,
    creada_en TEXT NOT NULL
);
"""
