from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from src.backend.database import (
    init_db,
    crear_deportista,
    obtener_deportistas,
    crear_sesion,
    obtener_historial_deportista,
    obtener_ultima_prediccion
)

from src.api.schemas import (
    DeportistaCreate,
    DeportistaResponse,
    SesionCreate,
    SesionResponse,
    PrediccionResponse
)


app = FastAPI(
    title="AthletaGuard API",
    description="API REST para el sistema AthletaGuard",
    version="0.1.0"
)

@app.on_event("startup")
def startup_event():
    init_db()


# Permitimos las peticiones del frontend durante el desarrollo local
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "project": "AthletaGuard",
        "message": "API funcionando correctamente"
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "AthletaGuard API"
    }

@app.post("/athletes", response_model=DeportistaResponse)
def create_athlete(deportista: DeportistaCreate):
    return crear_deportista(
        alias=deportista.alias,
        edad=deportista.edad,
        sexo=deportista.sexo,
        nivel=deportista.nivel
    )


@app.get("/athletes", response_model=list[DeportistaResponse])
def get_athletes():
    return obtener_deportistas()

@app.post("/sessions", response_model=SesionResponse)
def create_session(sesion: SesionCreate):
    return crear_sesion(
        id_deportista=sesion.id_deportista,
        fecha=sesion.fecha,
        tipo=sesion.tipo,
        duracion=sesion.duracion,
        volumen=sesion.volumen,
        rpe=sesion.rpe,
        fc_media=sesion.fc_media,
        fc_max=sesion.fc_max,
        hrv=sesion.hrv,
        potencia=sesion.potencia,
        descanso=sesion.descanso
    )

@app.get("/athletes/{id_deportista}/history", response_model=list[SesionResponse])
def get_athlete_history(id_deportista: int):
    return obtener_historial_deportista(id_deportista)

@app.get(
    "/athletes/{id_deportista}/risk",
    response_model=PrediccionResponse
)
def get_athlete_risk(id_deportista: int):
    prediccion = obtener_ultima_prediccion(id_deportista)

    if prediccion is None:
        raise HTTPException(
            status_code=404,
            detail="No hay predicciones disponibles para este deportista"
        )

    return prediccion