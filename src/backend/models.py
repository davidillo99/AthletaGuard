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