"""Pruebas de la API con una base de datos temporal y un modelo pequeño de prueba."""

import sqlite3

import joblib
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

from src.backend import services
from src.backend.main import app
from src.backend.models import SQL_TABLAS
from src.pipeline.features import FEATURES

# Fechas de la base de datos de prueba.
DIA_VALIDO = "2021-03-10"
DIA_SIN_HISTORIAL = "2021-03-09"
DIA_SIN_SEGUIMIENTO = "2021-03-11"


def crear_base_datos(ruta):
    """Crea una base de datos con una deportista y tres días de métricas."""
    conexion = sqlite3.connect(ruta)
    conexion.executescript(SQL_TABLAS)
    conexion.execute("INSERT INTO deportista VALUES (1, 'TeamA-01', 'TeamA', 'TeamA-uuid')")
    conexion.execute(
        "INSERT INTO sesion (id_deportista, fecha, duracion, rpe, srpe) VALUES (1, ?, 60, 5, 300)",
        (DIA_VALIDO,),
    )
    conexion.execute("INSERT INTO bienestar (id_deportista, fecha, fatiga) VALUES (1, ?, 3)", (DIA_VALIDO,))
    # Solo el día válido tiene carga_28d. El resto de las features quedan nulas:
    # el imputador del modelo debe resolverlas igual que en producción.
    conexion.execute(
        """INSERT INTO metricas_derivadas (id_deportista, fecha, carga_dia, carga_28d, sin_seguimiento)
           VALUES (1, ?, 0, NULL, 0), (1, ?, 300, 8000, 0), (1, ?, 0, 7000, 1)""",
        (DIA_SIN_HISTORIAL, DIA_VALIDO, DIA_SIN_SEGUIMIENTO),
    )
    conexion.commit()
    conexion.close()


def crear_modelo(ruta):
    """Entrena un modelo mínimo con datos aleatorios: aquí se prueba la API, no el modelo."""
    aleatorio = np.random.default_rng(0)
    X = pd.DataFrame(aleatorio.random((40, len(FEATURES))), columns=FEATURES)
    y = np.array([0, 1] * 20)
    pipeline = Pipeline(
        [("imputador", SimpleImputer(strategy="median")), ("clasificador", RandomForestClassifier(5, random_state=0))]
    ).fit(X, y)
    joblib.dump(
        {
            "pipeline": pipeline,
            "modelo": "ModeloPrueba",
            "version": "test",
            "features": FEATURES,
            "umbrales": {"moderado": 0.3, "alto": 0.6},
        },
        ruta,
    )


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    """Devuelve un cliente de la API que no toca los datos ni el modelo reales."""
    ruta_bd, ruta_modelo = tmp_path / "prueba.db", tmp_path / "modelo.joblib"
    crear_base_datos(ruta_bd)
    crear_modelo(ruta_modelo)
    monkeypatch.setattr(services, "DB_PATH", ruta_bd)
    monkeypatch.setattr(services, "MODEL_PATH", ruta_modelo)
    # Se vacía la caché para que cada prueba cargue su propio modelo.
    monkeypatch.setattr(services, "_artefacto", None)
    with TestClient(app) as cliente_prueba:
        yield cliente_prueba


def test_health(cliente):
    respuesta = cliente.get("/health")
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["estado"] == "ok"
    assert datos["modelo_cargado"] is True
    assert "No es un diagnóstico médico" in datos["aviso"]


def test_listar_deportistas(cliente):
    deportistas = cliente.get("/athletes").json()
    assert deportistas == [
        {
            "id_deportista": 1,
            "alias": "TeamA-01",
            "equipo": "TeamA",
            "fecha_primera": DIA_SIN_HISTORIAL,
            "fecha_ultima": DIA_SIN_SEGUIMIENTO,
        }
    ]


def test_predict_valido_y_se_guarda_en_el_historial(cliente):
    respuesta = cliente.post("/predict", json={"id_deportista": 1, "fecha": DIA_VALIDO})
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["riesgo"] in {"bajo", "moderado", "alto"}
    assert 0 <= datos["probabilidad"] <= 1
    assert datos["fecha_objetivo"] == "2021-03-11"
    assert datos["version"] == "test"
    assert "No es un diagnóstico médico" in datos["aviso"]

    historial = cliente.get("/athletes/1/history").json()
    assert [p["id_prediccion"] for p in historial["predicciones"]] == [datos["id_prediccion"]]


def test_predict_sin_fecha_usa_el_ultimo_dia_valido(cliente):
    respuesta = cliente.post("/predict", json={"id_deportista": 1})
    assert respuesta.status_code == 200
    assert respuesta.json()["fecha"] == DIA_VALIDO


@pytest.mark.parametrize(
    "cuerpo",
    [
        {},
        {"id_deportista": "abc"},
        {"id_deportista": -1},
        {"id_deportista": 1, "fecha": "10/03/2021"},
        {"id_deportista": 1, "campo_desconocido": 1},
    ],
)
def test_predict_entrada_invalida_devuelve_422(cliente, cuerpo):
    assert cliente.post("/predict", json=cuerpo).status_code == 422


@pytest.mark.parametrize("fecha", [DIA_SIN_HISTORIAL, DIA_SIN_SEGUIMIENTO, "2030-01-01"])
def test_predict_fecha_no_valida_devuelve_422_y_no_guarda(cliente, fecha):
    assert cliente.post("/predict", json={"id_deportista": 1, "fecha": fecha}).status_code == 422
    assert cliente.get("/athletes/1/history").json()["predicciones"] == []


def test_deportista_inexistente_devuelve_404(cliente):
    assert cliente.post("/predict", json={"id_deportista": 999}).status_code == 404
    assert cliente.get("/athletes/999/history").status_code == 404


def test_sin_modelo_devuelve_503(cliente, tmp_path, monkeypatch):
    monkeypatch.setattr(services, "MODEL_PATH", tmp_path / "no_existe.joblib")
    monkeypatch.setattr(services, "_artefacto", None)
    assert cliente.post("/predict", json={"id_deportista": 1}).status_code == 503
    salud = cliente.get("/health").json()
    assert salud["estado"] == "degradado"
    assert salud["modelo_cargado"] is False


def test_sin_base_de_datos_devuelve_503(cliente, tmp_path, monkeypatch):
    monkeypatch.setattr(services, "DB_PATH", tmp_path / "no_existe.db")
    assert cliente.get("/athletes").status_code == 503
    assert cliente.get("/health").json()["base_datos_disponible"] is False
    # No debe crear un archivo vacío al intentar conectar.
    assert not (tmp_path / "no_existe.db").exists()


def test_historial_filtra_por_fechas(cliente):
    datos = cliente.get("/athletes/1/history", params={"desde": DIA_VALIDO, "hasta": DIA_VALIDO}).json()
    assert [m["fecha"] for m in datos["metricas"]] == [DIA_VALIDO]
    assert cliente.get("/athletes/1/history", params={"desde": "2021-03-11", "hasta": "2021-03-10"}).status_code == 422


def test_el_dashboard_se_sirve_en_la_raiz(cliente):
    respuesta = cliente.get("/")
    assert respuesta.status_code == 200
    assert "text/html" in respuesta.headers["content-type"]
