"""Endpoints de la API: validan la entrada y traducen los errores a códigos HTTP."""

from datetime import date

from fastapi import APIRouter, HTTPException

from src.backend import services
from src.backend.models import (
    Deportista,
    RespuestaHistorial,
    RespuestaPrediccion,
    RespuestaSalud,
    SolicitudPrediccion,
)

router = APIRouter()


@router.get("/health", response_model=RespuestaSalud)
def health():
    """Indica si el servicio tiene base de datos y modelo disponibles."""
    return services.obtener_salud()


@router.get("/athletes", response_model=list[Deportista])
def get_athletes():
    """Lista las deportistas."""
    try:
        return services.listar_deportistas()
    except services.BaseDatosNoDisponible as error:
        raise HTTPException(status_code=503, detail=str(error))


@router.get("/athletes/{id_deportista}/history", response_model=RespuestaHistorial)
def get_athlete_history(id_deportista: int, desde: date | None = None, hasta: date | None = None):
    """Devuelve el histórico de una deportista, con filtro temporal opcional."""
    if desde and hasta and desde > hasta:
        raise HTTPException(status_code=422, detail="'desde' no puede ser posterior a 'hasta'")
    try:
        return services.obtener_historial(id_deportista, desde, hasta)
    except services.DeportistaNoEncontrado as error:
        raise HTTPException(status_code=404, detail=str(error))
    except services.BaseDatosNoDisponible as error:
        raise HTTPException(status_code=503, detail=str(error))


@router.post("/predict", response_model=RespuestaPrediccion)
def predict(solicitud: SolicitudPrediccion):
    """Estima el riesgo de fatiga percibida alta para el día siguiente y lo guarda."""
    try:
        return services.predecir(solicitud.id_deportista, solicitud.fecha)
    except services.DeportistaNoEncontrado as error:
        raise HTTPException(status_code=404, detail=str(error))
    except services.FechaNoValida as error:
        raise HTTPException(status_code=422, detail=str(error))
    except (services.ModeloNoDisponible, services.BaseDatosNoDisponible) as error:
        raise HTTPException(status_code=503, detail=str(error))
