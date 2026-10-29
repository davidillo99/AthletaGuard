from fastapi.testclient import TestClient

from src.api.main import app

from src.backend import database

client = TestClient(app)


def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "AthletaGuard API"
    }

def test_root():
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "project": "AthletaGuard",
        "message": "API funcionando correctamente"
    }

def test_crear_y_obtener_deportista(tmp_path, monkeypatch):
    # Usamos una base de datos temporal solo para este test
    test_db = tmp_path / "test_athletaguard.db"

    monkeypatch.setattr(database, "DB_PATH", test_db)

    database.init_db()

    nuevo_deportista = {
        "alias": "atleta_test",
        "edad": 25,
        "sexo": "M",
        "nivel": "avanzado"
    }

    response_post = client.post(
        "/athletes",
        json=nuevo_deportista
    )

    assert response_post.status_code == 200
    assert response_post.json()["alias"] == "atleta_test"
    assert response_post.json()["id_deportista"] == 1

    response_get = client.get("/athletes")

    assert response_get.status_code == 200

    deportistas = response_get.json()

    assert len(deportistas) == 1
    assert deportistas[0]["alias"] == "atleta_test"

def test_crear_sesion_y_obtener_historial(tmp_path, monkeypatch):
    test_db = tmp_path / "test_athletaguard.db"

    monkeypatch.setattr(database, "DB_PATH", test_db)

    database.init_db()

    deportista = database.crear_deportista(
        alias="runner_test",
        edad=22,
        sexo="M",
        nivel="intermedio"
    )

    nueva_sesion = {
        "id_deportista": deportista["id_deportista"],
        "fecha": "2026-10-29",
        "tipo": "carrera",
        "duracion": 60,
        "volumen": 12,
        "rpe": 7,
        "fc_media": 158,
        "fc_max": 181,
        "hrv": 62,
        "potencia": 310,
        "descanso": 24
    }

    response_post = client.post(
        "/sessions",
        json=nueva_sesion
    )

    assert response_post.status_code == 200
    assert response_post.json()["tipo"] == "carrera"
    assert response_post.json()["id_sesion"] == 1

    response_get = client.get(
        f"/athletes/{deportista['id_deportista']}/history"
    )

    assert response_get.status_code == 200

    historial = response_get.json()

    assert len(historial) == 1
    assert historial[0]["volumen"] == 12
    assert historial[0]["rpe"] == 7