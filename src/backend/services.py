"""Servicios del backend: acceso a la base de datos, carga del modelo e inferencia."""

import sqlite3
from contextlib import closing
from datetime import date, datetime, timedelta

import joblib
import pandas as pd

from src.backend.models import AVISO_NO_MEDICO
from src.config import DB_PATH, MODEL_PATH
from src.pipeline.train import clasificar_riesgo

# El modelo se guarda aquí tras cargarlo, para no leer el archivo en cada petición.
_artefacto = None


class BaseDatosNoDisponible(Exception):
    """No existe la base de datos: falta ejecutar la ingesta."""


class ModeloNoDisponible(Exception):
    """No se ha podido cargar el modelo: falta ejecutar el entrenamiento."""


class DeportistaNoEncontrado(Exception):
    """El id de deportista no existe."""


class FechaNoValida(Exception):
    """La deportista existe, pero no se puede predecir para esa fecha."""


def obtener_conexion():
    """Abre una conexión a SQLite con claves foráneas activadas."""
    # Sin esta comprobación, sqlite3 crearía un archivo vacío y fallaría más tarde
    # con un error confuso de "tabla inexistente".
    if not DB_PATH.exists():
        raise BaseDatosNoDisponible("No existe la base de datos. Ejecuta: python -m src.pipeline.ingest")
    conexion = sqlite3.connect(DB_PATH)
    conexion.row_factory = sqlite3.Row
    # SQLite no activa las claves foráneas por defecto.
    conexion.execute("PRAGMA foreign_keys = ON")
    return conexion


def obtener_modelo():
    """Devuelve el modelo con sus metadatos, o None si no se puede cargar."""
    global _artefacto
    # Si antes no estaba, se reintenta: así no hay que reiniciar el servidor tras entrenar.
    if _artefacto is None and MODEL_PATH.exists():
        try:
            _artefacto = joblib.load(MODEL_PATH)
        except Exception as error:
            # Un archivo dañado o de otra versión no debe tumbar el servidor: se responde 503.
            print(f"No se pudo cargar el modelo {MODEL_PATH}: {error}")
    return _artefacto


def base_datos_disponible():
    """Indica si la base de datos existe y tiene deportistas."""
    try:
        with closing(obtener_conexion()) as conexion:
            return conexion.execute("SELECT COUNT(*) FROM deportista").fetchone()[0] > 0
    except (BaseDatosNoDisponible, sqlite3.Error):
        return False


def obtener_salud():
    """Resume el estado del servicio para GET /health."""
    disponible = base_datos_disponible()
    artefacto = obtener_modelo()
    return {
        "estado": "ok" if disponible and artefacto else "degradado",
        "base_datos_disponible": disponible,
        "modelo_cargado": artefacto is not None,
        "version_modelo": artefacto["version"] if artefacto else None,
        "aviso": AVISO_NO_MEDICO,
    }


# Consulta común: cada deportista con la primera y última fecha de sus métricas.
SQL_DEPORTISTAS = """
    SELECT d.id_deportista, d.alias, d.equipo,
           MIN(m.fecha) AS fecha_primera, MAX(m.fecha) AS fecha_ultima
    FROM deportista d
    JOIN metricas_derivadas m ON m.id_deportista = d.id_deportista
"""


def listar_deportistas():
    """Devuelve todas las deportistas."""
    with closing(obtener_conexion()) as conexion:
        filas = conexion.execute(f"{SQL_DEPORTISTAS} GROUP BY d.id_deportista ORDER BY d.id_deportista").fetchall()
    return [dict(fila) for fila in filas]


def _buscar_deportista(conexion, id_deportista):
    """Devuelve una deportista o lanza DeportistaNoEncontrado."""
    fila = conexion.execute(
        f"{SQL_DEPORTISTAS} WHERE d.id_deportista = ? GROUP BY d.id_deportista", (id_deportista,)
    ).fetchone()
    if fila is None:
        raise DeportistaNoEncontrado(f"No existe la deportista con id {id_deportista}")
    return dict(fila)


def _consultar(conexion, sql, id_deportista, desde, hasta, columna_fecha="fecha"):
    """Ejecuta una consulta de una deportista filtrando por fechas si se indican."""
    # Las fechas se guardan como texto ISO, que ordena igual que las fechas reales.
    condicion = f" AND {columna_fecha} >= ? AND {columna_fecha} <= ?"
    limites = (desde.isoformat() if desde else "0000-01-01", hasta.isoformat() if hasta else "9999-12-31")
    filas = conexion.execute(sql.format(filtro=condicion), (id_deportista, *limites)).fetchall()
    return [dict(fila) for fila in filas]


def obtener_historial(id_deportista, desde=None, hasta=None):
    """Devuelve métricas, bienestar, sesiones y predicciones de una deportista."""
    with closing(obtener_conexion()) as conexion:
        deportista = _buscar_deportista(conexion, id_deportista)
        metricas = _consultar(
            conexion,
            """SELECT fecha, carga_dia, carga_7d, carga_28d, acwr, sin_seguimiento
               FROM metricas_derivadas WHERE id_deportista = ?{filtro} ORDER BY fecha""",
            id_deportista, desde, hasta,
        )
        bienestar = _consultar(
            conexion,
            """SELECT fecha, fatiga, animo, disposicion, horas_sueno, calidad_sueno, dolor_muscular, estres
               FROM bienestar WHERE id_deportista = ?{filtro} ORDER BY fecha""",
            id_deportista, desde, hasta,
        )
        sesiones = _consultar(
            conexion,
            """SELECT id_sesion, fecha, duracion, rpe, srpe
               FROM sesion WHERE id_deportista = ?{filtro} ORDER BY fecha DESC, id_sesion DESC""",
            id_deportista, desde, hasta,
        )
        predicciones = _consultar(
            conexion,
            """SELECT id_prediccion, id_deportista, fecha, fecha_objetivo, probabilidad, riesgo,
                      modelo, version, creada_en
               FROM prediccion WHERE id_deportista = ?{filtro} ORDER BY id_prediccion DESC""",
            id_deportista, desde, hasta,
        )
    return {
        "deportista": deportista,
        "metricas": metricas,
        "carga_semanal": calcular_carga_semanal(metricas),
        "bienestar": bienestar,
        "sesiones": sesiones,
        "predicciones": predicciones,
        "aviso": AVISO_NO_MEDICO,
    }


def calcular_carga_semanal(metricas):
    """Suma la carga diaria por semanas naturales, empezando en lunes (HU03)."""
    semanas = {}
    for metrica in metricas:
        dia = date.fromisoformat(metrica["fecha"])
        lunes = (dia - timedelta(days=dia.weekday())).isoformat()
        semanas[lunes] = semanas.get(lunes, 0.0) + metrica["carga_dia"]
    return [{"semana_inicio": lunes, "carga": carga} for lunes, carga in sorted(semanas.items())]


def _buscar_metricas_validas(conexion, id_deportista, fecha):
    """Devuelve la fila de métricas sobre la que se puede predecir, o lanza FechaNoValida."""
    if fecha is None:
        # Sin fecha: el último día con historial suficiente y en seguimiento.
        fila = conexion.execute(
            """SELECT * FROM metricas_derivadas
               WHERE id_deportista = ? AND carga_28d IS NOT NULL AND sin_seguimiento = 0
               ORDER BY fecha DESC LIMIT 1""",
            (id_deportista,),
        ).fetchone()
        if fila is None:
            raise FechaNoValida("La deportista no tiene ningún día con 28 días de historial en seguimiento")
        return fila

    fila = conexion.execute(
        "SELECT * FROM metricas_derivadas WHERE id_deportista = ? AND fecha = ?",
        (id_deportista, fecha.isoformat()),
    ).fetchone()
    if fila is None:
        raise FechaNoValida(f"La fecha {fecha} está fuera del periodo con datos de la deportista")
    if fila["carga_28d"] is None:
        raise FechaNoValida(f"La fecha {fecha} no tiene 28 días de historial")
    if fila["sin_seguimiento"]:
        raise FechaNoValida(f"La fecha {fecha} está en una racha sin seguimiento (14 días o más sin carga)")
    return fila


def predecir(id_deportista, fecha=None):
    """Calcula el riesgo a partir de las métricas guardadas y registra la predicción."""
    artefacto = obtener_modelo()
    if artefacto is None:
        raise ModeloNoDisponible("No hay modelo cargado. Ejecuta: python -m src.pipeline.train")

    with closing(obtener_conexion()) as conexion:
        deportista = _buscar_deportista(conexion, id_deportista)
        fila = _buscar_metricas_validas(conexion, id_deportista, fecha)

        # La lista de features viene del propio modelo: la API no puede desincronizarse.
        X = pd.DataFrame([dict(fila)])[artefacto["features"]].astype(float)
        probabilidad = float(artefacto["pipeline"].predict_proba(X)[0, 1])

        registro = {
            "id_deportista": id_deportista,
            "fecha": fila["fecha"],
            "fecha_objetivo": (date.fromisoformat(fila["fecha"]) + timedelta(days=1)).isoformat(),
            "probabilidad": probabilidad,
            "riesgo": clasificar_riesgo(probabilidad, artefacto["umbrales"]),
            "modelo": artefacto["modelo"],
            "version": artefacto["version"],
            "creada_en": datetime.now().isoformat(timespec="seconds"),
        }
        cursor = conexion.execute(
            """INSERT INTO prediccion
               (id_deportista, fecha, fecha_objetivo, probabilidad, riesgo, modelo, version, creada_en)
               VALUES (:id_deportista, :fecha, :fecha_objetivo, :probabilidad, :riesgo, :modelo, :version, :creada_en)""",
            registro,
        )
        conexion.commit()

    return {
        **registro,
        "id_prediccion": cursor.lastrowid,
        "alias": deportista["alias"],
        "aviso": AVISO_NO_MEDICO,
    }
