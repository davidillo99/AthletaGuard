"""Pruebas del cálculo de features: ventanas, ausencia de datos futuros y etiqueta."""

import numpy as np
import pandas as pd

from src.pipeline.features import (
    FEATURES,
    calcular_deportista,
    calcular_etiqueta,
    construir_dataset_modelado,
    construir_metricas,
    marcar_sin_seguimiento,
)


def crear_sesiones(dias=60, srpe=100, inicio="2021-01-01"):
    """Crea una sesión diaria con carga constante."""
    return pd.DataFrame({"fecha": pd.date_range(inicio, periods=dias), "srpe": float(srpe)})


def crear_bienestar(dias=60, inicio="2021-01-01"):
    """Crea reportes diarios con valores que cambian, para detectar errores de ventana."""
    fechas = pd.date_range(inicio, periods=dias)
    valores = 1 + np.arange(dias) % 5
    return pd.DataFrame(
        {
            "fecha": fechas,
            "fatiga": valores,
            "animo": valores,
            "disposicion": valores,
            "horas_sueno": 8.0,
            "calidad_sueno": valores,
            "dolor_muscular": valores,
            "estres": valores,
        }
    )


def test_las_features_no_usan_datos_futuros():
    """Las features de un día no deben cambiar al eliminar todo lo posterior a ese día."""
    aleatorio = np.random.default_rng(0)
    sesiones = crear_sesiones()
    sesiones["srpe"] = aleatorio.integers(50, 900, len(sesiones)).astype(float)
    bienestar = crear_bienestar()
    corte = pd.Timestamp("2021-02-10")

    completo = calcular_deportista(sesiones, bienestar).set_index("fecha")
    truncado = calcular_deportista(sesiones[sesiones.fecha <= corte], bienestar[bienestar.fecha <= corte])
    truncado = truncado.set_index("fecha")

    np.testing.assert_allclose(
        completo.loc[corte, FEATURES].astype(float), truncado.loc[corte, FEATURES].astype(float)
    )


def test_ventanas_de_carga_y_acwr():
    metricas = calcular_deportista(crear_sesiones(srpe=100), crear_bienestar())

    # Las ventanas quedan nulas hasta estar completas.
    assert metricas["carga_7d"].iloc[5:6].isna().all()
    assert metricas["carga_7d"].iloc[6] == 700
    assert metricas["carga_28d"].iloc[26:27].isna().all()
    assert metricas["carga_28d"].iloc[27] == 2800
    # Con carga constante, la carga aguda y la crónica coinciden.
    assert metricas["acwr"].iloc[27] == 1
    assert metricas["media_movil"].iloc[27] == 100
    assert metricas["sesiones_7d"].iloc[27] == 7


def test_acwr_nulo_sin_carga_cronica():
    """Tras 28 días sin carga, el ACWR debe ser nulo en lugar de un valor infinito."""
    sesiones = pd.concat([crear_sesiones(dias=1), crear_sesiones(dias=1, inicio="2021-03-15")])
    metricas = calcular_deportista(sesiones, crear_bienestar(dias=1)).set_index("fecha")
    dia = pd.Timestamp("2021-03-14")
    assert metricas.loc[dia, "carga_28d"] == 0
    assert np.isnan(metricas.loc[dia, "acwr"])


def test_racha_sin_seguimiento_empieza_en_14_dias():
    def racha(ceros):
        carga = pd.Series([100.0] + [0.0] * ceros + [100.0])
        return marcar_sin_seguimiento(carga).sum()

    assert racha(13) == 0
    assert racha(14) == 14


def test_etiqueta_mira_solo_al_dia_siguiente():
    fatiga = pd.Series([3.0, 2.0, 3.0, np.nan, 1.0, 4.0])
    etiqueta = calcular_etiqueta(fatiga)
    # Mañana 2 -> 1; mañana 3 -> 0; mañana sin reporte -> nulo, nunca 0.
    assert etiqueta[0] == 1
    assert etiqueta[1] == 0
    assert np.isnan(etiqueta[2])
    assert etiqueta[3] == 1
    assert etiqueta[4] == 0
    assert np.isnan(etiqueta[5])


def test_dataset_excluye_filas_no_validas():
    sesiones = crear_sesiones(dias=60).assign(id_deportista=1)
    # Racha de 20 días sin carga, entre los días 35 y 54.
    sesiones = sesiones[(sesiones.index < 35) | (sesiones.index >= 55)]
    bienestar = crear_bienestar(dias=60).assign(id_deportista=1)

    metricas = construir_metricas(sesiones, bienestar)
    dataset = construir_dataset_modelado(metricas)

    assert metricas["sin_seguimiento"].sum() == 20
    assert dataset["fecha"].min() == pd.Timestamp("2021-01-28")  # primer día con 28 días de historia
    assert dataset["carga_28d"].notna().all()
    assert dataset["etiqueta"].notna().all()
    fechas_excluidas = pd.date_range("2021-02-05", periods=20)
    assert not dataset["fecha"].isin(fechas_excluidas).any()
    # Sin identificador de jugadora ni equipo entre las features.
    assert "id_deportista" not in FEATURES
