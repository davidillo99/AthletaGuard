"""Pruebas de la limpieza, de la partición temporal y del modelo guardado."""

import numpy as np
import pandas as pd
import pytest
import joblib

from src.config import MODEL_PATH
from src.pipeline.features import FEATURES
from src.pipeline.ingest import (
    DIR_DATOS,
    crear_deportistas,
    leer_bienestar,
    leer_sesiones,
    limpiar_bienestar,
    limpiar_sesiones,
)
from src.pipeline.train import (
    INICIO_TEST,
    clasificar_riesgo,
    crear_cortes_temporales,
    elegir_umbrales,
    separar_train_test,
)


def test_limpiar_sesiones_descarta_y_cuenta_cada_motivo():
    fila_buena = {"id_origen": "A", "fecha": "01.02.2021", "srpe": 300, "rpe": 5, "duracion": 60}
    sesiones = pd.DataFrame(
        [
            fila_buena,
            fila_buena,  # duplicado exacto
            {**fila_buena, "fecha": "02.02.2021", "srpe": 0, "rpe": 0},  # sin carga
            {**fila_buena, "fecha": "2021-02-03"},  # formato de fecha no válido
            {**fila_buena, "fecha": "04.02.2021", "rpe": 11},  # RPE imposible
            {**fila_buena, "fecha": "05.02.2021", "srpe": None},  # valor ausente
        ]
    )
    limpias, descartes = limpiar_sesiones(sesiones)

    # Los errores se informan sin perder el registro válido (HU01 y HU07).
    assert len(limpias) == 1
    assert limpias["fecha"].iloc[0] == pd.Timestamp("2021-02-01")
    assert descartes == {
        "fecha o valor no valido": 2,
        "rpe o duracion fuera de rango": 1,
        "srpe igual a 0": 1,
        "duplicados exactos": 1,
    }


def test_limpiar_bienestar_anula_solo_el_valor_erroneo():
    columnas = {"animo": 3, "disposicion": 7, "calidad_sueno": 3, "dolor_muscular": 3, "estres": 3}
    bienestar = pd.DataFrame(
        [
            {"id_origen": "A", "fecha": "01.02.2021", "fatiga": 9, "horas_sueno": 8, **columnas},
            {"id_origen": "A", "fecha": "02.02.2021", "fatiga": 3, "horas_sueno": 2, **columnas},
            # Día sin ningún reporte: la fila debe desaparecer.
            {"id_origen": "A", "fecha": "03.02.2021", **{c: np.nan for c in ["fatiga", "horas_sueno", *columnas]}},
        ]
    )
    limpio, descartes = limpiar_bienestar(bienestar)

    assert len(limpio) == 2
    assert np.isnan(limpio["fatiga"].iloc[0])
    assert limpio["horas_sueno"].iloc[0] == 8
    assert np.isnan(limpio["horas_sueno"].iloc[1])
    assert limpio["animo"].iloc[1] == 3
    assert descartes["fatiga fuera de rango (a nulo)"] == 1
    assert descartes["horas de sueno no creibles (a nulo)"] == 1


def test_lectura_de_los_datos_reales():
    """Comprueba que los archivos versionados se leen y conservan su tamaño conocido."""
    sesiones = leer_sesiones(DIR_DATOS / "training-load" / "session.json")
    bienestar = leer_bienestar(DIR_DATOS / "wellness")

    assert len(sesiones) == 16265
    assert sesiones["id_origen"].nunique() == 50
    # 50 jugadoras por 731 días, con una columna por cada una de las 7 variables.
    assert len(bienestar) == 50 * 731
    assert bienestar.drop(columns=["id_origen", "fecha"]).shape[1] == 7
    # Los identificadores son anónimos: equipo y UUID, sin nombres.
    assert sesiones["id_origen"].str.fullmatch(r"Team[AB]-[0-9a-f-]{36}").all()


def test_alias_consecutivos_por_equipo():
    deportistas = crear_deportistas(["TeamA-x", "TeamB-y", "TeamA-z"])
    assert deportistas["alias"].tolist() == ["TeamA-01", "TeamB-01", "TeamA-02"]
    assert deportistas["id_deportista"].tolist() == [1, 2, 3]


def test_separacion_y_cortes_respetan_el_orden_temporal():
    fechas = pd.date_range("2021-06-01", "2021-07-31").repeat(3)
    dataset = pd.DataFrame({"fecha": fechas})
    train, test = separar_train_test(dataset)
    assert train["fecha"].max() < INICIO_TEST <= test["fecha"].min()

    cortes = crear_cortes_temporales(train["fecha"], n_cortes=3)
    assert len(cortes) == 3
    for indices_train, indices_valid in cortes:
        # Todo el entrenamiento es anterior a la validación, y un mismo día no se parte.
        assert train["fecha"].iloc[indices_train].max() < train["fecha"].iloc[indices_valid].min()


def test_umbrales_y_niveles_de_riesgo():
    y = np.array([0, 0, 0, 0, 0, 0, 1, 1, 1, 1])
    probabilidades = np.array([0.1, 0.2, 0.2, 0.3, 0.4, 0.6, 0.35, 0.7, 0.8, 0.9])
    umbrales = elegir_umbrales(y, probabilidades, recall_objetivo=1.0)

    # Moderado: el mayor umbral que detecta todos los positivos. Alto: el de mejor F1.
    assert umbrales == {"moderado": 0.35, "alto": 0.7}

    assert clasificar_riesgo(0.34, umbrales) == "bajo"
    assert clasificar_riesgo(0.35, umbrales) == "moderado"
    assert clasificar_riesgo(0.7, umbrales) == "alto"


def test_umbrales_incoherentes_detienen_el_entrenamiento():
    """Si no se pudieran formar tres niveles, debe fallar en vez de guardar un modelo erróneo."""
    y = np.array([0, 0, 0, 0, 0, 0, 1, 1, 1, 1])
    probabilidades = np.array([0.1, 0.2, 0.2, 0.3, 0.4, 0.6, 0.35, 0.5, 0.7, 0.8])
    with pytest.raises(ValueError, match="Umbrales incoherentes"):
        elegir_umbrales(y, probabilidades, recall_objetivo=0.75)


@pytest.mark.skipif(not MODEL_PATH.exists(), reason="Aún no se ha entrenado: ejecuta python -m src.pipeline.train")
def test_el_modelo_guardado_carga_y_predice():
    """El modelo real debe incluir sus metadatos y predecir con las features actuales."""
    artefacto = joblib.load(MODEL_PATH)

    assert artefacto["features"] == FEATURES
    assert artefacto["umbrales"]["moderado"] < artefacto["umbrales"]["alto"]
    assert artefacto["version"] and artefacto["fecha_entrenamiento"]

    # Una fila totalmente vacía debe resolverse con el imputador guardado junto al modelo.
    fila = pd.DataFrame([[np.nan] * len(FEATURES)], columns=FEATURES)
    probabilidad = artefacto["pipeline"].predict_proba(fila)[0, 1]
    assert 0 <= probabilidad <= 1
