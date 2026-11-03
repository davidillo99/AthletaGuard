"""Ingesta: lee SoccerMon, limpia los datos y los carga en data/processed y en SQLite.

Uso desde la raíz del repositorio: python -m src.pipeline.ingest
Aviso: recrea la base de datos, así que borra las predicciones guardadas.
"""

import json
import sqlite3

import pandas as pd

from src.backend.models import SQL_TABLAS
from src.config import DB_PATH, RAIZ
from src.pipeline.features import construir_dataset_modelado, construir_metricas

DIR_DATOS = RAIZ / "data" / "raw" / "subjective"
DIR_PROCESADOS = RAIZ / "data" / "processed"

# Archivo original -> nombre de la variable en el proyecto.
ARCHIVOS_BIENESTAR = {
    "fatigue.csv": "fatiga",
    "mood.csv": "animo",
    "readiness.csv": "disposicion",
    "sleep_duration.csv": "horas_sueno",
    "sleep_quality.csv": "calidad_sueno",
    "soreness.csv": "dolor_muscular",
    "stress.csv": "estres",
}

# Rango válido de cada variable, según las escalas observadas y el artículo original.
RANGOS_BIENESTAR = {
    "fatiga": (1, 5),
    "animo": (1, 5),
    "disposicion": (1, 10),
    "calidad_sueno": (1, 5),
    "dolor_muscular": (1, 5),
    "estres": (1, 5),
}

# Menos de 3 horas seguidas no se considera un dato de sueño creíble.
HORAS_SUENO_MIN_EXCLUIDA = 3
HORAS_SUENO_MAX = 24


def leer_sesiones(ruta):
    """Convierte session.json en una tabla con una fila por sesión."""
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    filas = [
        {
            "id_origen": id_origen,
            "fecha": sesion.get("date"),
            "srpe": sesion.get("srpe"),
            "rpe": sesion.get("rpe"),
            "duracion": sesion.get("duration"),
        }
        for id_origen, sesiones in datos.items()
        for sesion in sesiones
    ]
    return pd.DataFrame(filas)


def limpiar_sesiones(sesiones):
    """Valida las sesiones y devuelve las válidas junto con el recuento de descartes."""
    limpias = sesiones.copy()
    descartes = {}

    # Los errores se cuentan sin perder el resto de los registros (HU01 y HU07).
    limpias["fecha"] = pd.to_datetime(limpias["fecha"], format="%d.%m.%Y", errors="coerce")
    for columna in ("srpe", "rpe", "duracion"):
        limpias[columna] = pd.to_numeric(limpias[columna], errors="coerce")

    invalida = limpias[["fecha", "srpe", "rpe", "duracion"]].isna().any(axis=1)
    descartes["fecha o valor no valido"] = int(invalida.sum())
    limpias = limpias[~invalida]

    fuera_rango = ~limpias["rpe"].between(0, 10) | (limpias["duracion"] < 0)
    descartes["rpe o duracion fuera de rango"] = int(fuera_rango.sum())
    limpias = limpias[~fuera_rango]

    # Una sesión sin carga (RPE o duración 0) no aporta entrenamiento real.
    sin_carga = limpias["srpe"] == 0
    descartes["srpe igual a 0"] = int(sin_carga.sum())
    limpias = limpias[~sin_carga]

    # Filas idénticas: se tratan como dobles envíos. No se puede saber con certeza.
    duplicada = limpias.duplicated(["id_origen", "fecha", "srpe", "rpe", "duracion"])
    descartes["duplicados exactos"] = int(duplicada.sum())
    limpias = limpias[~duplicada]

    return limpias.reset_index(drop=True), descartes


def leer_bienestar(carpeta):
    """Une los CSV de bienestar (formato ancho) en una tabla por jugadora y fecha."""
    tablas = []
    for archivo, variable in ARCHIVOS_BIENESTAR.items():
        ancho = pd.read_csv(carpeta / archivo)
        # El nombre de la primera columna varía según el archivo, pero siempre es la fecha.
        ancho = ancho.rename(columns={ancho.columns[0]: "fecha"})
        largo = ancho.melt(id_vars="fecha", var_name="id_origen", value_name=variable)
        tablas.append(largo.set_index(["id_origen", "fecha"]))
    return pd.concat(tablas, axis=1).reset_index()


def limpiar_bienestar(bienestar):
    """Valida el bienestar: anula valores imposibles y elimina días sin ningún reporte."""
    limpio = bienestar.copy()
    descartes = {}

    limpio["fecha"] = pd.to_datetime(limpio["fecha"], format="%d.%m.%Y", errors="coerce")
    fecha_invalida = limpio["fecha"].isna()
    descartes["fecha no valida"] = int(fecha_invalida.sum())
    limpio = limpio[~fecha_invalida].copy()

    # Se anula solo el valor erróneo: el resto del reporte de ese día sigue siendo válido.
    for variable, (minimo, maximo) in RANGOS_BIENESTAR.items():
        fuera = limpio[variable].notna() & ~limpio[variable].between(minimo, maximo)
        descartes[f"{variable} fuera de rango (a nulo)"] = int(fuera.sum())
        limpio.loc[fuera, variable] = float("nan")

    horas = limpio["horas_sueno"]
    no_creible = horas.notna() & ((horas <= HORAS_SUENO_MIN_EXCLUIDA) | (horas > HORAS_SUENO_MAX))
    descartes["horas de sueno no creibles (a nulo)"] = int(no_creible.sum())
    limpio.loc[no_creible, "horas_sueno"] = float("nan")

    # Una fila sin ningún valor no es un reporte: es un día sin datos.
    variables = list(ARCHIVOS_BIENESTAR.values())
    limpio = limpio.dropna(subset=variables, how="all")
    return limpio.reset_index(drop=True), descartes


def crear_deportistas(ids_origen):
    """Asigna id numérico y alias legible a cada identificador original."""
    filas = []
    contador_equipo = {}
    for numero, id_origen in enumerate(ids_origen, start=1):
        equipo = id_origen.split("-")[0]
        contador_equipo[equipo] = contador_equipo.get(equipo, 0) + 1
        filas.append(
            {
                "id_deportista": numero,
                "alias": f"{equipo}-{contador_equipo[equipo]:02d}",
                "equipo": equipo,
                "id_origen": id_origen,
            }
        )
    return pd.DataFrame(filas)


def con_id_deportista(tabla, deportistas):
    """Sustituye el identificador original por el id numérico interno."""
    mapa = deportistas.set_index("id_origen")["id_deportista"]
    resultado = tabla.assign(id_deportista=tabla["id_origen"].map(mapa))
    return resultado.drop(columns="id_origen")


def fechas_a_texto(tabla):
    """Convierte la fecha a texto ISO, el formato que se guarda en SQLite."""
    return tabla.assign(fecha=tabla["fecha"].dt.strftime("%Y-%m-%d"))


def guardar_en_sqlite(ruta, deportistas, sesiones, bienestar, metricas):
    """Recrea la base de datos y carga todas las tablas."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.unlink(missing_ok=True)
    conexion = sqlite3.connect(ruta)
    try:
        conexion.executescript(SQL_TABLAS)
        deportistas.to_sql("deportista", conexion, if_exists="append", index=False)
        sesiones.to_sql("sesion", conexion, if_exists="append", index=False)
        bienestar.to_sql("bienestar", conexion, if_exists="append", index=False)
        metricas.to_sql("metricas_derivadas", conexion, if_exists="append", index=False)
        conexion.commit()
    finally:
        conexion.close()


def mostrar_descartes(titulo, total, descartes):
    """Muestra por consola cuántas filas se descartan y por qué."""
    print(f"{titulo}: {total} filas leidas")
    for motivo, cantidad in descartes.items():
        print(f"  - {motivo}: {cantidad}")


def main():
    """Ejecuta la ingesta completa."""
    sesiones_brutas = leer_sesiones(DIR_DATOS / "training-load" / "session.json")
    sesiones, descartes = limpiar_sesiones(sesiones_brutas)
    mostrar_descartes("Sesiones", len(sesiones_brutas), descartes)

    bienestar_bruto = leer_bienestar(DIR_DATOS / "wellness")
    bienestar, descartes = limpiar_bienestar(bienestar_bruto)
    mostrar_descartes("Bienestar (jugadora x dia)", len(bienestar_bruto), descartes)

    # El orden de session.json es el de los CSV, así que los alias son estables.
    deportistas = crear_deportistas(list(dict.fromkeys(sesiones_brutas["id_origen"])))
    sesiones = con_id_deportista(sesiones, deportistas)
    bienestar = con_id_deportista(bienestar, deportistas)

    metricas = construir_metricas(sesiones, bienestar)
    dataset = construir_dataset_modelado(metricas)

    # fatiga_hoy y etiqueta solo se usan para modelar: no van a la base de datos.
    metricas_bd = metricas.drop(columns=["fatiga_hoy", "etiqueta"])

    DIR_PROCESADOS.mkdir(parents=True, exist_ok=True)
    deportistas.to_csv(DIR_PROCESADOS / "deportistas.csv", index=False)
    sesiones.to_csv(DIR_PROCESADOS / "sesiones_limpias.csv", index=False)
    bienestar.to_csv(DIR_PROCESADOS / "bienestar_limpio.csv", index=False)
    dataset.to_csv(DIR_PROCESADOS / "dataset_modelado.csv", index=False)

    guardar_en_sqlite(
        DB_PATH,
        deportistas,
        fechas_a_texto(sesiones),
        fechas_a_texto(bienestar),
        fechas_a_texto(metricas_bd),
    )

    print(f"Deportistas: {len(deportistas)}")
    print(f"Sesiones validas: {len(sesiones)}")
    print(f"Reportes de bienestar: {len(bienestar)}")
    print(f"Metricas diarias: {len(metricas_bd)}")
    print(f"Dataset de modelado: {len(dataset)} filas, {int(dataset['etiqueta'].sum())} positivos")
    print(f"Base de datos: {DB_PATH}")


if __name__ == "__main__":
    main()
