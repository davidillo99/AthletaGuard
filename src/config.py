"""Configuración común del pipeline y del backend, leída de variables de entorno."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Raíz del repositorio. Se calcula desde este archivo para que las rutas
# funcionen igual sea cual sea la carpeta desde la que se lance el comando.
RAIZ = Path(__file__).resolve().parents[1]

# Si existe un .env en la raíz, se cargan sus valores. Si no existe, no pasa
# nada: se usan los valores por defecto definidos abajo.
load_dotenv(RAIZ / ".env")


def _ruta(variable, por_defecto):
    """Devuelve la ruta de una variable de entorno; si es relativa, parte de la raíz."""
    ruta = Path(os.getenv(variable, por_defecto))
    return ruta if ruta.is_absolute() else RAIZ / ruta


DB_PATH = _ruta("DB_PATH", "data/processed/athletaguard.db")
MODEL_PATH = _ruta("MODEL_PATH", "models/modelo.joblib")
PORT = int(os.getenv("PORT", "8000"))
