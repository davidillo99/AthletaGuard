"""Punto de entrada: crea la aplicación FastAPI y sirve la API y el dashboard.

Uso desde la raíz del repositorio: uvicorn src.backend.main:app
"""

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.backend.api import router
from src.backend.services import obtener_modelo
from src.config import PORT, RAIZ


@asynccontextmanager
async def ciclo_de_vida(app):
    """Carga el modelo al arrancar, para que la primera predicción no tarde más."""
    obtener_modelo()
    yield


app = FastAPI(
    title="AthletaGuard API",
    description=(
        "API de AthletaGuard. Las predicciones son orientativas y "
        "nunca constituyen un diagnóstico médico."
    ),
    version="1.0",
    lifespan=ciclo_de_vida,
)
app.include_router(router)

# El dashboard se monta el último: si no, "/" taparía las rutas de la API.
# Se sirve desde el mismo servidor, por lo que no hace falta configurar CORS.
app.mount("/", StaticFiles(directory=RAIZ / "src" / "frontend", html=True), name="frontend")


if __name__ == "__main__":
    # Alternativa a uvicorn por consola: respeta la variable de entorno PORT.
    uvicorn.run(app, host="127.0.0.1", port=PORT)
