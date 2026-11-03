"""Feature engineering: métricas diarias por deportista y dataset de modelado.

Regla principal: las features del día t usan solo información hasta t, incluido.
La etiqueta es lo único que mira al futuro (la fatiga del día t+1).
"""

import pandas as pd

# Variables de bienestar disponibles en SoccerMon. Sustituyen a la HRV de NF2.
VARIABLES_BIENESTAR = [
    "fatiga",
    "animo",
    "disposicion",
    "horas_sueno",
    "calidad_sueno",
    "dolor_muscular",
    "estres",
]

FEATURES_CARGA = [
    "carga_7d",
    "carga_28d",
    "acwr",
    "media_movil",
    "sesiones_7d",
    "dias_descanso_7d",
    "cambio_carga_semanal",
]

FEATURES_BIENESTAR = [
    f"{variable}_{sufijo}"
    for variable in VARIABLES_BIENESTAR
    for sufijo in ("media_7d", "var")
]

# Lista completa, en el orden en que la recibe el modelo.
FEATURES = FEATURES_CARGA + FEATURES_BIENESTAR

# Una racha sin carga de esta longitud o más se considera "sin seguimiento", no
# descanso: en esas rachas casi nadie reporta bienestar (ver docs/limitaciones.md).
DIAS_RACHA_SIN_SEGUIMIENTO = 14

# Con fatiga <= 2 (escala de 1 a 5, asumiendo que un valor alto es mejor) se
# considera fatiga percibida alta.
UMBRAL_FATIGA_ALTA = 2


def marcar_sin_seguimiento(carga_dia):
    """Marca los días que pertenecen a una racha larga sin carga."""
    es_cero = carga_dia == 0
    # Cada cambio entre "con carga" y "sin carga" abre un grupo nuevo.
    grupo = (es_cero != es_cero.shift()).cumsum()
    longitud_racha = es_cero.groupby(grupo).transform("size")
    return es_cero & (longitud_racha >= DIAS_RACHA_SIN_SEGUIMIENTO)


def calcular_features_carga(carga_dia, sesiones_dia):
    """Calcula las features de carga a partir de series diarias sin huecos."""
    salida = pd.DataFrame(index=carga_dia.index)

    # Se exige la ventana completa: así se evita el ACWR inflado de los primeros
    # días, que aparecería al promediar con pocos días de historia.
    salida["carga_7d"] = carga_dia.rolling(7, min_periods=7).sum()
    salida["carga_28d"] = carga_dia.rolling(28, min_periods=28).sum()

    carga_cronica = salida["carga_28d"] / 28
    # Sin carga crónica el ratio no está definido: se deja nulo en vez de dar infinito.
    salida["acwr"] = (salida["carga_7d"] / 7) / carga_cronica.where(carga_cronica > 0)

    salida["media_movil"] = salida["carga_7d"] / 7
    salida["sesiones_7d"] = sesiones_dia.rolling(7, min_periods=7).sum()
    salida["dias_descanso_7d"] = (carga_dia == 0).rolling(7, min_periods=7).sum()
    salida["cambio_carga_semanal"] = salida["carga_7d"] - salida["carga_7d"].shift(7)
    return salida


def calcular_features_bienestar(bienestar):
    """Calcula media de 7 días y variación (3 frente a 28 días) de cada variable."""
    salida = pd.DataFrame(index=bienestar.index)
    for variable in VARIABLES_BIENESTAR:
        serie = bienestar[variable]
        # Con menos de 3 reportes en 7 días la media no es fiable: queda nula.
        salida[f"{variable}_media_7d"] = serie.rolling(7, min_periods=3).mean()
        # Compara lo reciente con la referencia habitual de la propia jugadora.
        reciente = serie.rolling(3, min_periods=1).mean()
        referencia = serie.rolling(28, min_periods=7).mean()
        salida[f"{variable}_var"] = reciente - referencia
    return salida


def calcular_etiqueta(fatiga):
    """Devuelve 1 si mañana hay fatiga alta, 0 si no, y nulo si no hay reporte mañana."""
    fatiga_manana = fatiga.shift(-1)
    # where() conserva los nulos: un día sin reporte no se trata como "sin fatiga".
    return (fatiga_manana <= UMBRAL_FATIGA_ALTA).astype(float).where(fatiga_manana.notna())


def calcular_deportista(sesiones, bienestar):
    """Calcula las métricas diarias de una deportista entre su primera y última sesión."""
    fechas = pd.date_range(sesiones["fecha"].min(), sesiones["fecha"].max(), freq="D")

    # Se rellenan con 0 solo los días dentro del periodo con sesiones. Antes de la
    # primera sesión no hay filas, por lo que esos días no cuentan como descanso.
    por_dia = sesiones.groupby("fecha")["srpe"]
    carga_dia = por_dia.sum().reindex(fechas, fill_value=0).astype(float)
    sesiones_dia = por_dia.size().reindex(fechas, fill_value=0)

    bienestar_diario = (
        bienestar.set_index("fecha")
        .reindex(fechas)
        .reindex(columns=VARIABLES_BIENESTAR)
        .astype(float)
    )

    metricas = pd.concat(
        [calcular_features_carga(carga_dia, sesiones_dia), calcular_features_bienestar(bienestar_diario)],
        axis=1,
    )
    metricas["carga_dia"] = carga_dia
    metricas["sin_seguimiento"] = marcar_sin_seguimiento(carga_dia).astype(int)
    metricas["fatiga_hoy"] = bienestar_diario["fatiga"]
    metricas["etiqueta"] = calcular_etiqueta(bienestar_diario["fatiga"])
    return metricas.rename_axis("fecha").reset_index()


def construir_metricas(sesiones, bienestar):
    """Calcula las métricas de todas las deportistas."""
    partes = []
    for id_deportista, sesiones_deportista in sesiones.groupby("id_deportista"):
        bienestar_deportista = bienestar[bienestar["id_deportista"] == id_deportista]
        parte = calcular_deportista(sesiones_deportista, bienestar_deportista)
        parte.insert(0, "id_deportista", id_deportista)
        partes.append(parte)
    return pd.concat(partes, ignore_index=True)


def construir_dataset_modelado(metricas):
    """Selecciona las filas válidas para entrenar y evaluar el modelo."""
    con_historial = metricas["carga_28d"].notna()
    en_seguimiento = metricas["sin_seguimiento"] == 0
    con_etiqueta = metricas["etiqueta"].notna()
    dataset = metricas[con_historial & en_seguimiento & con_etiqueta]
    # fatiga_hoy no es una feature: solo se usa para la referencia de persistencia.
    columnas = ["id_deportista", "fecha"] + FEATURES + ["fatiga_hoy", "etiqueta"]
    return dataset[columnas].sort_values(["fecha", "id_deportista"]).reset_index(drop=True)
