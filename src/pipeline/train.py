"""Entrenamiento: validación temporal, métricas y guardado del modelo.

Uso desde la raíz del repositorio: python -m src.pipeline.train
Requiere haber ejecutado antes: python -m src.pipeline.ingest
"""

import json
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
)
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
from sklearn.pipeline import Pipeline

from src.config import MODEL_PATH, RAIZ
from src.pipeline.features import FEATURES, UMBRAL_FATIGA_ALTA

RUTA_DATASET = RAIZ / "data" / "processed" / "dataset_modelado.csv"
RUTA_METADATA = RAIZ / "models" / "metadata.json"
DIR_EXPERIMENTOS = RAIZ / "docs" / "experiments"

VERSION = "1.0"
NOMBRE_MODELO = "RandomForest"
SEMILLA = 42

# Todo lo anterior a esta fecha se usa para entrenar. El periodo de test
# (01/07/2021 a 31/12/2021) solo se evalúa una vez, al final.
INICIO_TEST = pd.Timestamp("2021-07-01")

N_CORTES = 5
REJILLA = {
    "clasificador__max_depth": [None, 10],
    "clasificador__min_samples_leaf": [1, 5, 20],
}

# Recall mínimo que debe cumplir el umbral de riesgo moderado.
RECALL_OBJETIVO = 0.80


def crear_pipeline():
    """Crea el preprocesado y el modelo, que se guardan juntos para no desincronizarse."""
    return Pipeline(
        [
            # La mediana se calcula solo con los datos de entrenamiento de cada ajuste.
            ("imputador", SimpleImputer(strategy="median")),
            (
                "clasificador",
                RandomForestClassifier(
                    n_estimators=300,
                    class_weight="balanced",
                    random_state=SEMILLA,
                    n_jobs=-1,
                ),
            ),
        ]
    )


def separar_train_test(dataset):
    """Separa los datos por fecha, sin mezclar pasado y futuro."""
    return dataset[dataset["fecha"] < INICIO_TEST], dataset[dataset["fecha"] >= INICIO_TEST]


def crear_cortes_temporales(fechas, n_cortes=N_CORTES):
    """Crea cortes de TimeSeriesSplit sobre fechas únicas.

    Si se cortara por filas, un mismo día podría quedar a ambos lados del corte.
    """
    fechas = pd.Series(fechas).reset_index(drop=True)
    fechas_unicas = np.sort(fechas.unique())
    cortes = []
    for indices_train, indices_valid in TimeSeriesSplit(n_splits=n_cortes).split(fechas_unicas):
        en_train = fechas.isin(fechas_unicas[indices_train]).to_numpy()
        en_valid = fechas.isin(fechas_unicas[indices_valid]).to_numpy()
        cortes.append((np.where(en_train)[0], np.where(en_valid)[0]))
    return cortes


def predecir_fuera_de_muestra(modelo, X, y, cortes):
    """Predice cada corte de validación con un modelo entrenado solo con su pasado."""
    indices = np.concatenate([valid for _, valid in cortes])
    probabilidades = np.concatenate(
        [modelo.fit(X.iloc[train], y.iloc[train]).predict_proba(X.iloc[valid])[:, 1] for train, valid in cortes]
    )
    return y.iloc[indices].to_numpy(), probabilidades


def elegir_umbrales(y, probabilidades, recall_objetivo=RECALL_OBJETIVO):
    """Elige los umbrales: moderado por Recall mínimo y alto por F1 máximo."""
    precision, recall, umbrales = precision_recall_curve(y, probabilidades)
    # precision y recall tienen un valor más que umbrales: se quita el último.
    precision, recall = precision[:-1], recall[:-1]

    umbral_moderado = float(umbrales[recall >= recall_objetivo].max())

    denominador = precision + recall
    f1 = np.divide(2 * precision * recall, denominador, out=np.zeros_like(denominador), where=denominador > 0)
    umbral_alto = float(umbrales[f1.argmax()])

    # Moderado debe quedar por debajo de alto para que existan los tres niveles.
    if umbral_alto <= umbral_moderado:
        raise ValueError(f"Umbrales incoherentes: moderado={umbral_moderado}, alto={umbral_alto}")
    return {"moderado": umbral_moderado, "alto": umbral_alto}


def clasificar_riesgo(probabilidad, umbrales):
    """Convierte una probabilidad en nivel de riesgo: bajo, moderado o alto."""
    if probabilidad >= umbrales["alto"]:
        return "alto"
    if probabilidad >= umbrales["moderado"]:
        return "moderado"
    return "bajo"


def metricas_binarias(y, prediccion):
    """Calcula Recall, Precision, F1 y matriz de confusión."""
    negativos_ok, falsos_pos, falsos_neg, positivos_ok = confusion_matrix(y, prediccion, labels=[0, 1]).ravel()
    return {
        "recall": float(recall_score(y, prediccion, zero_division=0)),
        "precision": float(precision_score(y, prediccion, zero_division=0)),
        "f1": float(f1_score(y, prediccion, zero_division=0)),
        "matriz_confusion": {
            "vn": int(negativos_ok),
            "fp": int(falsos_pos),
            "fn": int(falsos_neg),
            "vp": int(positivos_ok),
        },
    }


def evaluar_modelo(y, probabilidades, umbrales):
    """Evalúa el modelo con AUC-PR y con cada umbral de alerta."""
    return {
        "auc_pr": float(average_precision_score(y, probabilidades)),
        "alerta_desde_moderado": metricas_binarias(y, probabilidades >= umbrales["moderado"]),
        "alerta_solo_alto": metricas_binarias(y, probabilidades >= umbrales["alto"]),
    }


def evaluar_referencias(train, test):
    """Evalúa las dos referencias con las que se compara el modelo."""
    dummy = DummyClassifier(strategy="prior").fit(train[FEATURES], train["etiqueta"])
    probabilidad_dummy = dummy.predict_proba(test[FEATURES])[:, 1]

    # Persistencia: "mañana, igual que hoy". Sin reporte hoy, predice que no habrá fatiga.
    persistencia = (test["fatiga_hoy"] <= UMBRAL_FATIGA_ALTA).astype(int)
    return {
        "dummy": {
            "auc_pr": float(average_precision_score(test["etiqueta"], probabilidad_dummy)),
            **metricas_binarias(test["etiqueta"], dummy.predict(test[FEATURES])),
        },
        "persistencia": {
            "auc_pr": float(average_precision_score(test["etiqueta"], persistencia)),
            **metricas_binarias(test["etiqueta"], persistencia),
        },
    }


def resumir_por_nivel(y, probabilidades, umbrales):
    """Calcula, por nivel de riesgo, cuántos casos hay y qué fracción tuvo fatiga alta."""
    tabla = pd.DataFrame(
        {"y": np.asarray(y), "riesgo": [clasificar_riesgo(p, umbrales) for p in probabilidades]}
    )
    resumen = {}
    for nivel in ("bajo", "moderado", "alto"):
        grupo = tabla.loc[tabla["riesgo"] == nivel, "y"]
        resumen[nivel] = {"n": int(len(grupo)), "tasa_fatiga_alta": float(grupo.mean()) if len(grupo) else None}
    return resumen


def resumir_por_equipo(test, probabilidades, ids_equipo):
    """Calcula el AUC-PR por equipo, para revisar el rendimiento por subgrupos (NF2 §8.2)."""
    equipo = test["id_deportista"].map(ids_equipo).to_numpy()
    y = test["etiqueta"].to_numpy()
    return {
        nombre: {
            "n": int((equipo == nombre).sum()),
            "tasa_base": float(y[equipo == nombre].mean()),
            "auc_pr": float(average_precision_score(y[equipo == nombre], probabilidades[equipo == nombre])),
        }
        for nombre in np.unique(equipo)
    }


def escribir_informe(ruta, metricas):
    """Escribe un resumen legible de las métricas en Markdown."""
    test = metricas["test"]["modelo"]
    referencias = metricas["test"]["referencias"]

    def fila(nombre, datos, auc):
        return f"| {nombre} | {auc:.3f} | {datos['recall']:.3f} | {datos['precision']:.3f} | {datos['f1']:.3f} |"

    lineas = [
        f"# Experimento {metricas['modelo']} v{metricas['version']}",
        "",
        f"- **Etiqueta:** {metricas['etiqueta']}",
        f"- **Entrenamiento:** {metricas['datos']['train_n']} filas, {metricas['datos']['train_positivos']} positivos",
        f"- **Test:** {metricas['datos']['test_n']} filas, {metricas['datos']['test_positivos']} positivos, "
        f"desde {metricas['datos']['inicio_test']}",
        f"- **Mejores hiperparámetros:** `{metricas['mejores_parametros']}`",
        f"- **Umbrales:** moderado {metricas['umbrales']['moderado']:.3f}, alto {metricas['umbrales']['alto']:.3f}",
        f"- **AUC-PR en validación temporal:** {metricas['validacion']['auc_pr']:.3f}",
        f"- **AUC-PR en entrenamiento:** {metricas['train_auc_pr']:.3f}",
        "",
        "## Resultados en el test temporal",
        "",
        "| Modelo | AUC-PR | Recall | Precision | F1 |",
        "|---|---|---|---|---|",
        fila("Dummy", referencias["dummy"], referencias["dummy"]["auc_pr"]),
        fila("Persistencia", referencias["persistencia"], referencias["persistencia"]["auc_pr"]),
        fila("Random Forest (alerta desde moderado)", test["alerta_desde_moderado"], test["auc_pr"]),
        fila("Random Forest (alerta solo en alto)", test["alerta_solo_alto"], test["auc_pr"]),
        "",
        "## Matrices de confusión del Random Forest",
        "",
        f"- **Desde moderado:** `{test['alerta_desde_moderado']['matriz_confusion']}`",
        f"- **Solo alto:** `{test['alerta_solo_alto']['matriz_confusion']}`",
        "",
        "## Fatiga alta observada por nivel de riesgo",
        "",
        "| Nivel | Casos | Tasa de fatiga alta |",
        "|---|---|---|",
    ]
    for nivel, datos in metricas["test"]["por_nivel"].items():
        tasa = "sin casos" if datos["tasa_fatiga_alta"] is None else f"{datos['tasa_fatiga_alta']:.3f}"
        lineas.append(f"| {nivel} | {datos['n']} | {tasa} |")

    lineas += ["", "## Por equipo", "", "| Equipo | Casos | Tasa base | AUC-PR |", "|---|---|---|---|"]
    for equipo, datos in metricas["test"]["por_equipo"].items():
        lineas.append(f"| {equipo} | {datos['n']} | {datos['tasa_base']:.3f} | {datos['auc_pr']:.3f} |")

    lineas += ["", "## Importancia de variables", "", "| Variable | Importancia |", "|---|---|"]
    for variable, importancia in metricas["importancias"].items():
        lineas.append(f"| {variable} | {importancia:.3f} |")

    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")


def main():
    """Entrena, evalúa y guarda el modelo con sus metadatos."""
    dataset = pd.read_csv(RUTA_DATASET, parse_dates=["fecha"])
    dataset = dataset.sort_values(["fecha", "id_deportista"]).reset_index(drop=True)
    train, test = separar_train_test(dataset)
    X_train, y_train = train[FEATURES], train["etiqueta"]
    print(f"Train: {len(train)} filas | Test: {len(test)} filas")

    # 1. Búsqueda de hiperparámetros: solo con datos anteriores al test.
    cortes = crear_cortes_temporales(train["fecha"])
    busqueda = GridSearchCV(crear_pipeline(), REJILLA, scoring="average_precision", cv=cortes, refit=False)
    busqueda.fit(X_train, y_train)
    print(f"Mejores hiperparametros: {busqueda.best_params_}")

    # 2. Umbrales: con predicciones fuera de muestra, para que no estén sobreajustados.
    modelo = crear_pipeline().set_params(**busqueda.best_params_)
    y_validacion, p_validacion = predecir_fuera_de_muestra(modelo, X_train, y_train, cortes)
    umbrales = elegir_umbrales(y_validacion, p_validacion)
    print(f"Umbrales: {umbrales}")

    # 3. Modelo final: con todo el periodo de entrenamiento.
    modelo.fit(X_train, y_train)

    # 4. Evaluación final sobre el test temporal.
    p_test = modelo.predict_proba(test[FEATURES])[:, 1]
    p_train = modelo.predict_proba(X_train)[:, 1]

    # El equipo no es una feature: solo se usa aquí, para revisar subgrupos.
    deportistas = pd.read_csv(RUTA_DATASET.parent / "deportistas.csv")
    ids_equipo = deportistas.set_index("id_deportista")["equipo"]

    importancias = pd.Series(modelo.named_steps["clasificador"].feature_importances_, index=FEATURES)
    fecha_entrenamiento = datetime.now().isoformat(timespec="seconds")
    etiqueta = f"fatiga del dia siguiente <= {UMBRAL_FATIGA_ALTA} (fatiga percibida alta)"

    metricas = {
        "modelo": NOMBRE_MODELO,
        "version": VERSION,
        "etiqueta": etiqueta,
        "semilla": SEMILLA,
        "mejores_parametros": busqueda.best_params_,
        "umbrales": umbrales,
        "datos": {
            "train_n": len(train),
            "train_positivos": int(y_train.sum()),
            "test_n": len(test),
            "test_positivos": int(test["etiqueta"].sum()),
            "inicio_test": INICIO_TEST.date().isoformat(),
        },
        "train_auc_pr": float(average_precision_score(y_train, p_train)),
        "validacion": {
            "auc_pr": float(average_precision_score(y_validacion, p_validacion)),
            "alerta_desde_moderado": metricas_binarias(y_validacion, p_validacion >= umbrales["moderado"]),
            "alerta_solo_alto": metricas_binarias(y_validacion, p_validacion >= umbrales["alto"]),
        },
        "test": {
            "modelo": evaluar_modelo(test["etiqueta"], p_test, umbrales),
            "referencias": evaluar_referencias(train, test),
            "por_nivel": resumir_por_nivel(test["etiqueta"], p_test, umbrales),
            "por_equipo": resumir_por_equipo(test, p_test, ids_equipo),
        },
        "importancias": {k: float(v) for k, v in importancias.sort_values(ascending=False).items()},
    }

    # 5. Se guarda el modelo con sus metadatos, para que la API use exactamente
    # las mismas features y umbrales que el entrenamiento.
    metadata = {
        "modelo": NOMBRE_MODELO,
        "version": VERSION,
        "fecha_entrenamiento": fecha_entrenamiento,
        "etiqueta": etiqueta,
        "features": FEATURES,
        "umbrales": umbrales,
        "mejores_parametros": busqueda.best_params_,
    }
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"pipeline": modelo, **metadata}, MODEL_PATH, compress=3)
    RUTA_METADATA.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    DIR_EXPERIMENTOS.mkdir(parents=True, exist_ok=True)
    ruta_json = DIR_EXPERIMENTOS / f"metricas_v{VERSION}.json"
    ruta_json.write_text(json.dumps(metricas, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    escribir_informe(DIR_EXPERIMENTOS / f"metricas_v{VERSION}.md", metricas)

    print(f"AUC-PR test: {metricas['test']['modelo']['auc_pr']:.3f}")
    print(f"Modelo guardado en: {MODEL_PATH}")
    print(f"Metricas guardadas en: {ruta_json}")


if __name__ == "__main__":
    main()
