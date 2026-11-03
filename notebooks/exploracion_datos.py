"""Exploración de SoccerMon: reproduce las cifras con las que se decidió el tratamiento de datos.

Uso desde la raíz del repositorio:
    python notebooks/exploracion_datos.py > docs/evidencias/exploracion_datos.txt

Es un análisis previo, no forma parte del pipeline. El sondeo de etiquetas entrena
con 2020 y valida con el primer semestre de 2021: no evalúa ningún modelo sobre el
periodo de test del proyecto (desde 01/07/2021), que se reserva para train.py.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import average_precision_score, roc_auc_score

DIR_DATOS = Path(__file__).resolve().parents[1] / "data" / "raw" / "subjective"
FORMATO_FECHA = "%d.%m.%Y"
BIENESTAR = ["fatigue", "mood", "readiness", "sleep_duration", "sleep_quality", "soreness", "stress"]
# Dos reportes separados por más de estos días se consideran episodios distintos.
DIAS_ENTRE_EPISODIOS = 7


def leer_ancho(ruta):
    """Lee un CSV con una fila por día y una columna por jugadora."""
    tabla = pd.read_csv(ruta)
    tabla = tabla.rename(columns={tabla.columns[0]: "fecha"})
    tabla["fecha"] = pd.to_datetime(tabla["fecha"], format=FORMATO_FECHA)
    return tabla.set_index("fecha")


def leer_sesiones():
    """Lee session.json como tabla con una fila por sesión."""
    datos = json.loads((DIR_DATOS / "training-load" / "session.json").read_text(encoding="utf-8"))
    sesiones = pd.DataFrame([{"jugadora": j, **s} for j, lista in datos.items() for s in lista])
    sesiones["fecha"] = pd.to_datetime(sesiones["date"], format=FORMATO_FECHA)
    return sesiones


def leer_episodios():
    """Agrupa los reportes de lesión en episodios por jugadora."""
    lesiones = pd.read_csv(DIR_DATOS / "injury" / "injury.csv")
    lesiones["fecha"] = pd.to_datetime(lesiones["timestamp"], format=FORMATO_FECHA)
    unicos = lesiones.sort_values(["player_name", "fecha"]).drop_duplicates(["player_name", "fecha"])
    salto = unicos.groupby("player_name")["fecha"].diff().dt.days.fillna(999) > DIAS_ENTRE_EPISODIOS
    episodios = unicos.assign(ep=salto.cumsum()).groupby("ep").agg(
        jugadora=("player_name", "first"), inicio=("fecha", "min"), fin=("fecha", "max")
    )
    return lesiones, episodios


def resumir_archivos(sesiones, lesiones, carga, bienestar):
    """Muestra el tamaño y la calidad básica de los datos."""
    print("== Archivos ==")
    print(f"Jugadoras: {carga.shape[1]} | Dias: {carga.shape[0]} | {carga.index.min().date()} a {carga.index.max().date()}")
    print(f"Sesiones: {len(sesiones)} | srpe != rpe*duracion: {(sesiones.srpe != sesiones.rpe * sesiones.duration).sum()}")
    print(f"Duplicados exactos: {sesiones.duplicated(['jugadora', 'date', 'srpe', 'rpe', 'duration']).sum()} | srpe=0: {(sesiones.srpe == 0).sum()}")
    print("Sesiones por jugadora y dia:", sesiones.groupby(["jugadora", "fecha"]).size().value_counts().sort_index().to_dict())
    for nombre, tabla in bienestar.items():
        valores = tabla.to_numpy().ravel()
        valores = valores[~np.isnan(valores)]
        print(f"{nombre}: n={len(valores)} min={valores.min()} max={valores.max()} nulos={tabla.isna().mean().mean():.1%}")
    print(f"Lesiones: {len(lesiones)} filas, {lesiones.player_name.nunique()} jugadoras")


def comparar_carga(sesiones, carga):
    """Compara daily_load.csv con la suma de srpe de session.json."""
    suma = sesiones.pivot_table(index="fecha", columns="jugadora", values="srpe", aggfunc="sum")
    suma = suma.reindex(index=carga.index, columns=carga.columns).fillna(0)
    distinto = carga != suma
    print("\n== daily_load frente a session.json ==")
    print(f"Dias distintos: {distinto.sum().sum()} | jugadoras: {(distinto.sum() > 0).sum()} | daily_load mayor: {(carga > suma).sum().sum()}")


def analizar_ceros(carga, fatiga, inicio, fin):
    """Relaciona la longitud de las rachas sin carga con el reporte de bienestar."""
    partes = []
    for jugadora in carga.columns:
        tramo = carga.loc[inicio[jugadora]:fin[jugadora], jugadora]
        es_cero = tramo == 0
        grupo = (es_cero != es_cero.shift()).cumsum()
        partes.append(
            pd.DataFrame(
                {
                    "cero": es_cero,
                    "racha": es_cero.groupby(grupo).transform("size"),
                    "reporta": fatiga.loc[tramo.index, jugadora].notna(),
                }
            ).query("cero")
        )
    ceros = pd.concat(partes)
    print("\n== Reporte de bienestar segun la racha sin carga ==")
    tabla = ceros.groupby(pd.cut(ceros.racha, [0, 1, 2, 3, 6, 13, 27, 1000]), observed=True).reporta.agg(["size", "mean"])
    print(tabla.round(3).to_string())


def analizar_escalas_y_historial(carga, bienestar, inicio, fin):
    """Muestra los indicios sobre el sentido de las escalas y el historial por jugadora."""
    print("
== Sentido de las escalas e historial ==")
    carga_ayer = carga.shift(1).stack().rename("carga_ayer")
    for nombre in ("fatigue", "soreness"):
        tabla = pd.concat([bienestar[nombre].stack().rename("valor"), carga_ayer], axis=1).dropna()
        print(f"Spearman {nombre} frente a la carga de ayer: {tabla.valor.corr(tabla.carga_ayer, method='spearman'):.3f}")
    dias_activos = (carga > 0).sum()
    print(f"Jugadoras con menos de 100 dias con carga: {(dias_activos < 100).sum()} | menos de 60: {(dias_activos < 60).sum()}")
    con_carga = sin_carga = reportes_con = reportes_sin = 0
    for jugadora in carga.columns:
        tramo = carga.loc[inicio[jugadora]:fin[jugadora], jugadora]
        reporta = bienestar["fatigue"].loc[tramo.index, jugadora].notna()
        con_carga += (tramo > 0).sum(); reportes_con += reporta[tramo > 0].sum()
        sin_carga += (tramo == 0).sum(); reportes_sin += reporta[tramo == 0].sum()
    print(f"Reporte de bienestar: {reportes_con / con_carga:.1%} con carga, {reportes_sin / sin_carga:.1%} sin carga")


def analizar_lesiones(lesiones, episodios, carga, acwr, inicio, fin):
    """Muestra cuántas lesiones hay y si el ACWR las anticipa."""
    print("\n== Lesiones ==")
    print(f"Filas por trimestre: {lesiones.groupby(lesiones.fecha.dt.to_period('Q')).size().to_dict()}")
    print(f"Episodios: {len(episodios)} | por equipo: {episodios.jugadora.str[:5].value_counts().to_dict()}")
    print(f"Episodios desde 2021-07-01: {(episodios.inicio >= '2021-07-01').sum()}")

    filas = []
    for jugadora in carga.columns:
        tramo = acwr.loc[inicio[jugadora] + pd.Timedelta(days=28):fin[jugadora], jugadora]
        propios = episodios[episodios.jugadora == jugadora]
        for fecha, valor in tramo.items():
            durante = ((propios.inicio <= fecha) & (propios.fin >= fecha)).any()
            pronto = ((propios.inicio > fecha) & (propios.inicio <= fecha + pd.Timedelta(days=7))).any()
            if not durante:
                filas.append((valor, pronto))
    tabla = pd.DataFrame(filas, columns=["acwr", "lesion_7d"])
    tabla["banda"] = pd.cut(tabla.acwr, [-0.01, 1.3, 1.5, 99], labels=["bajo", "moderado", "alto"], right=False)
    print("Lesion en 7 dias por banda de ACWR original:")
    print(tabla.groupby("banda", observed=True).lesion_7d.agg(["size", "sum", "mean"]).round(4).to_string())


def crear_features_sondeo(carga, bienestar, inicio, fin):
    """Crea features sencillas, parecidas a las del proyecto, solo para comparar etiquetas."""
    partes = []
    for jugadora in carga.columns:
        serie = carga[jugadora]
        filas = pd.DataFrame(index=carga.index)
        filas["carga_7d"] = serie.rolling(7).sum()
        filas["carga_28d"] = serie.rolling(28).sum()
        filas["acwr"] = (filas.carga_7d / 7) / (filas.carga_28d / 28).replace(0, np.nan)
        filas["descanso_7d"] = (serie == 0).rolling(7).sum()
        filas["carga_hoy"] = serie
        for nombre in BIENESTAR:
            valores = bienestar[nombre][jugadora]
            filas[f"{nombre}_7d"] = valores.rolling(7, min_periods=3).mean()
            filas[f"{nombre}_var"] = valores.rolling(3, min_periods=1).mean() - valores.rolling(28, min_periods=7).mean()
        filas["jugadora"] = jugadora
        partes.append(filas.loc[inicio[jugadora] + pd.Timedelta(days=28):fin[jugadora]])
    return pd.concat(partes).rename_axis("fecha").reset_index()


def valor_futuro(tabla_ancha, filas, dias):
    """Devuelve para cada fila el valor de la misma jugadora dentro de `dias` días."""
    futuro = tabla_ancha.shift(-dias).stack(future_stack=True).rename("v").rename_axis(["fecha", "jugadora"]).reset_index()
    return filas[["fecha", "jugadora"]].merge(futuro, on=["fecha", "jugadora"], how="left")["v"].to_numpy()


def etiqueta_lesion(filas, episodios, dias):
    """Etiqueta 1 si empieza un episodio en los próximos días; nula durante un episodio."""
    y = np.zeros(len(filas))
    for _, ep in episodios.iterrows():
        propia = filas.jugadora == ep.jugadora
        y[propia & (filas.fecha >= ep.inicio - pd.Timedelta(days=dias)) & (filas.fecha < ep.inicio)] = 1
    for _, ep in episodios.iterrows():
        y[(filas.jugadora == ep.jugadora) & (filas.fecha >= ep.inicio) & (filas.fecha <= ep.fin)] = np.nan
    return y


def umbralizar(valores, condicion):
    """Aplica una condición conservando como nulos los valores que faltan."""
    return np.where(np.isnan(valores), np.nan, condicion(valores).astype(float))


def sondear_etiquetas(filas, etiquetas):
    """Entrena un modelo rápido por etiqueta, con todas las features y solo con las de carga."""
    print("\n== Sondeo de etiquetas (train 2020, validacion 2021-S1; no es un resultado del proyecto) ==")
    solo_carga = ["carga_7d", "carga_28d", "acwr", "descanso_7d", "carga_hoy"]
    todas = [c for c in filas.columns if c not in ("fecha", "jugadora")]
    for nombre, y in etiquetas.items():
        en_train = (filas.fecha < "2021-01-01").to_numpy() & ~np.isnan(y)
        en_valid = ((filas.fecha >= "2021-01-01") & (filas.fecha < "2021-07-01")).to_numpy() & ~np.isnan(y)
        for grupo, columnas in (("todas", todas), ("solo carga", solo_carga)):
            modelo = RandomForestClassifier(
                n_estimators=150, min_samples_leaf=5, class_weight="balanced", random_state=42, n_jobs=-1
            ).fit(filas.loc[en_train, columnas].fillna(-1), y[en_train])
            p = modelo.predict_proba(filas.loc[en_valid, columnas].fillna(-1))[:, 1]
            print(
                f"{nombre:28s} {grupo:10s} pos train={int(y[en_train].sum()):5d} pos valid={int(y[en_valid].sum()):5d} "
                f"base={y[en_valid].mean():.3f} AUC-PR={average_precision_score(y[en_valid], p):.3f} "
                f"ROC={roc_auc_score(y[en_valid], p):.3f}"
            )


def main():
    """Ejecuta todos los análisis."""
    carga = leer_ancho(DIR_DATOS / "training-load" / "daily_load.csv")
    acwr = leer_ancho(DIR_DATOS / "training-load" / "acwr.csv")
    bienestar = {n: leer_ancho(DIR_DATOS / "wellness" / f"{n}.csv") for n in BIENESTAR}
    sesiones = leer_sesiones()
    lesiones, episodios = leer_episodios()

    activa = carga > 0
    inicio, fin = activa.idxmax(), activa[::-1].idxmax()

    resumir_archivos(sesiones, lesiones, carga, bienestar)
    comparar_carga(sesiones, carga)
    analizar_ceros(carga, bienestar["fatigue"], inicio, fin)
    analizar_escalas_y_historial(carga, bienestar, inicio, fin)
    analizar_lesiones(lesiones, episodios, carga, acwr, inicio, fin)

    filas = crear_features_sondeo(carga, bienestar, inicio, fin)
    fatiga_dolor = bienestar["fatigue"] + bienestar["soreness"]
    etiquetas = {
        "A lesion en 7 dias": etiqueta_lesion(filas, episodios, 7),
        "A lesion en 28 dias": etiqueta_lesion(filas, episodios, 28),
        "B ACWR>1.5 hoy (circular)": umbralizar(valor_futuro(acwr, filas, 0), lambda v: v > 1.5),
        "B2 ACWR>1.5 en 7 dias": umbralizar(valor_futuro(acwr, filas, 7), lambda v: v > 1.5),
        "C1 fatiga<=2 manana": umbralizar(valor_futuro(bienestar["fatigue"], filas, 1), lambda v: v <= 2),
        "C2 readiness<=5 manana": umbralizar(valor_futuro(bienestar["readiness"], filas, 1), lambda v: v <= 5),
        "C3 fatiga+dolor<=5 manana": umbralizar(valor_futuro(fatiga_dolor, filas, 1), lambda v: v <= 5),
    }
    sondear_etiquetas(filas, etiquetas)


if __name__ == "__main__":
    main()
