import sqlite3
from pathlib import Path


DB_PATH = Path("data/processed/athletaguard.db")


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row

    # SQLite no activa las foreign keys por defecto
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def init_db():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS deportista (
            id_deportista INTEGER PRIMARY KEY AUTOINCREMENT,
            alias TEXT NOT NULL,
            edad INTEGER,
            sexo TEXT,
            nivel TEXT,
            fecha_alta TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sesion (
            id_sesion INTEGER PRIMARY KEY AUTOINCREMENT,
            id_deportista INTEGER NOT NULL,
            fecha TEXT NOT NULL,
            tipo TEXT,
            duracion REAL,
            volumen REAL,
            rpe REAL,
            fc_media REAL,
            fc_max REAL,
            hrv REAL,
            potencia REAL,
            descanso REAL,
            FOREIGN KEY (id_deportista)
                REFERENCES deportista(id_deportista)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metricas_derivadas (
            id_metricas INTEGER PRIMARY KEY AUTOINCREMENT,
            id_sesion INTEGER NOT NULL UNIQUE,
            carga_7d REAL,
            carga_28d REAL,
            acwr REAL,
            media_movil REAL,
            variacion_hrv REAL,
            FOREIGN KEY (id_sesion)
                REFERENCES sesion(id_sesion)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prediccion (
            id_prediccion INTEGER PRIMARY KEY AUTOINCREMENT,
            id_deportista INTEGER NOT NULL,
            fecha TEXT DEFAULT CURRENT_TIMESTAMP,
            probabilidad REAL,
            riesgo TEXT,
            modelo TEXT,
            version TEXT,
            FOREIGN KEY (id_deportista)
                REFERENCES deportista(id_deportista)
        )
    """)

    connection.commit()
    connection.close()

def crear_deportista(alias, edad=None, sexo=None, nivel=None):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO deportista (alias, edad, sexo, nivel)
        VALUES (?, ?, ?, ?)
    """, (alias, edad, sexo, nivel))

    connection.commit()

    id_deportista = cursor.lastrowid

    fila = connection.execute("""
        SELECT *
        FROM deportista
        WHERE id_deportista = ?
    """, (id_deportista,)).fetchone()

    connection.close()

    return dict(fila)


def obtener_deportistas():
    connection = get_connection()

    filas = connection.execute("""
        SELECT *
        FROM deportista
        ORDER BY id_deportista
    """).fetchall()

    connection.close()

    return [dict(fila) for fila in filas]

def crear_sesion(
    id_deportista,
    fecha,
    tipo=None,
    duracion=None,
    volumen=None,
    rpe=None,
    fc_media=None,
    fc_max=None,
    hrv=None,
    potencia=None,
    descanso=None
):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO sesion (
            id_deportista,
            fecha,
            tipo,
            duracion,
            volumen,
            rpe,
            fc_media,
            fc_max,
            hrv,
            potencia,
            descanso
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        id_deportista,
        fecha,
        tipo,
        duracion,
        volumen,
        rpe,
        fc_media,
        fc_max,
        hrv,
        potencia,
        descanso
    ))

    connection.commit()

    id_sesion = cursor.lastrowid

    fila = connection.execute("""
        SELECT *
        FROM sesion
        WHERE id_sesion = ?
    """, (id_sesion,)).fetchone()

    connection.close()

    return dict(fila)

def obtener_historial_deportista(id_deportista):
    connection = get_connection()

    filas = connection.execute("""
        SELECT *
        FROM sesion
        WHERE id_deportista = ?
        ORDER BY fecha DESC, id_sesion DESC
    """, (id_deportista,)).fetchall()

    connection.close()

    return [dict(fila) for fila in filas]

def obtener_ultima_prediccion(id_deportista):
    connection = get_connection()

    fila = connection.execute("""
        SELECT *
        FROM prediccion
        WHERE id_deportista = ?
        ORDER BY fecha DESC, id_prediccion DESC
        LIMIT 1
    """, (id_deportista,)).fetchone()

    connection.close()

    if fila is None:
        return None

    return dict(fila)