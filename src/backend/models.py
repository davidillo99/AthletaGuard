from pydantic import BaseModel
from typing import Optional


class DeportistaCreate(BaseModel):
    alias: str
    edad: Optional[int] = None
    sexo: Optional[str] = None
    nivel: Optional[str] = None


class DeportistaResponse(DeportistaCreate):
    id_deportista: int
    fecha_alta: str

class SesionCreate(BaseModel):
    id_deportista: int
    fecha: str
    tipo: Optional[str] = None
    duracion: Optional[float] = None
    volumen: Optional[float] = None
    rpe: Optional[float] = None
    fc_media: Optional[float] = None
    fc_max: Optional[float] = None
    hrv: Optional[float] = None
    potencia: Optional[float] = None
    descanso: Optional[float] = None


class SesionResponse(SesionCreate):
    id_sesion: int

class PrediccionResponse(BaseModel):
    id_prediccion: int
    id_deportista: int
    fecha: str
    probabilidad: Optional[float] = None
    riesgo: Optional[str] = None
    modelo: Optional[str] = None
    version: Optional[str] = None

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
