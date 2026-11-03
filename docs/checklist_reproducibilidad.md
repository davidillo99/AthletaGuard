# Lista de comprobación de reproducibilidad

`[x]` indica que está verificado. `[ ]` indica un paso manual pendiente antes de entregar.

## Repositorio

- [ ] Repositorio accesible para el docente: <https://github.com/davidillo99/AthletaGuard>
- [ ] Rama integrada mediante PR, con revisión de al menos un compañero (NF2 §11.1)
- [ ] Tag creado y publicado: `v1.0-nf3`
- [ ] Hash del commit anotado en el PDF
- [ ] La documentación corresponde a ese tag: sin cambios de código después de crearlo

## Contenido versionado

- [x] `README.md` con requisitos, configuración y comandos
- [x] `requirements.txt` con versiones fijadas
- [x] `.env.example` sin secretos
- [x] `.gitignore` excluye `.env`, `.venv/`, `*.db`, el modelo y el zip
- [x] Datos originales con su cita y licencia en `data/raw/README.md`
- [x] Datos versionados idénticos byte a byte al zip original, también al clonar
- [x] Sin datos personales identificables: identificadores anónimos
- [x] Pruebas automatizadas y su resultado en `docs/evidencias/pytest_resultado.txt`
- [x] Métricas del modelo en `docs/experiments/`
- [x] Árbol real y explicación de módulos en `docs/estructura_repo.txt`
- [x] Arquitectura real y desviaciones de NF2 en `docs/arquitectura.md`
- [x] Limitaciones en `docs/limitaciones.md`

## Verificación en limpio

Realizada en Windows 11 sobre un clon nuevo, con un entorno virtual nuevo y siguiendo el README comando a comando.

- [x] `pip install -r requirements.txt` termina sin errores
- [x] `python -m src.pipeline.ingest` crea la base de datos
- [x] `python -m src.pipeline.train` genera el modelo
- [x] Las métricas regeneradas son idénticas a las versionadas
- [x] `python -m pytest` termina sin fallos
- [x] `uvicorn src.backend.main:app` arranca el servidor
- [x] `/`, `/docs` y `/health` responden
- [x] Flujo completo en navegador real: elegir deportista, ver gráficos, calcular riesgo, ver el histórico
- [x] El dashboard no hace peticiones externas
- [ ] Repetir la prueba en otro equipo o por otro integrante (recomendado)

## Condiciones de entrega

- La documentación corresponde al tag o commit indicado en la entrega.
- No se permite modificar código tras la entrega sin autorización para cambiar la puntuación de esta fase.
- El tag o commit y la documentación entregada forman la referencia oficial de corrección.
