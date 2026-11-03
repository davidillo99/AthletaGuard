// Lógica del dashboard: pide los datos a la API y los muestra en una sola pantalla.

// Colores de las series. Se asignan siempre en este orden, para que cada variable
// conserve su color. Son los mismos valores que usa la hoja de estilos.
const COLORES = { azul: "#2a78d6", naranja: "#eb6834", aqua: "#1baf7a" };
const COLOR_REJILLA = "#e4e3df";

const SIMBOLO_RIESGO = { bajo: "●", moderado: "▲", alto: "■" };
const NUM_SESIONES_VISIBLES = 20;

// Mismo formato de número en todo el dashboard, igual que el de los ejes.
const formatear = (valor, decimales) =>
  valor.toLocaleString("es-ES", { minimumFractionDigits: decimales, maximumFractionDigits: decimales });

// Gráficos creados, por id de canvas. Se destruyen antes de volver a dibujar.
const graficos = {};

const elemento = (id) => document.getElementById(id);


// --- Comunicación con la API ---

/** Convierte la respuesta de error de la API en un mensaje legible. */
function mensajeDeError(cuerpo, estado) {
  const detalle = cuerpo && cuerpo.detail;
  if (typeof detalle === "string") return detalle;
  // FastAPI devuelve una lista cuando falla la validación de la entrada.
  if (Array.isArray(detalle)) return detalle.map((d) => d.msg).join("; ");
  return `Error ${estado} al consultar la API`;
}

/** Llama a la API y devuelve el JSON, o lanza un error con un mensaje claro. */
async function llamarApi(ruta, opciones) {
  let respuesta;
  try {
    respuesta = await fetch(ruta, opciones);
  } catch (error) {
    // fetch solo falla así cuando no hay conexión con el servidor.
    throw new Error("No se puede conectar con el servidor. Comprueba que está arrancado.");
  }
  const cuerpo = await respuesta.json().catch(() => null);
  if (!respuesta.ok) throw new Error(mensajeDeError(cuerpo, respuesta.status));
  return cuerpo;
}

function mostrarError(mensaje) {
  const caja = elemento("error");
  caja.textContent = mensaje;
  caja.hidden = false;
}

function limpiarError() {
  elemento("error").hidden = true;
}


// --- Gráficos ---

/** Crea o sustituye un gráfico de Chart.js. Hay un solo eje Y por gráfico. */
function dibujarGrafico(id, tipo, etiquetas, series, opcionesEjeY = {}) {
  if (graficos[id]) graficos[id].destroy();
  graficos[id] = new Chart(elemento(id), {
    type: tipo,
    data: {
      labels: etiquetas,
      datasets: series.map((serie) => ({
        label: serie.nombre,
        data: serie.valores,
        borderColor: serie.color,
        backgroundColor: serie.color,
        borderWidth: tipo === "line" ? 2 : 0,
        borderRadius: tipo === "bar" ? 4 : 0,
        pointRadius: 0,
        pointHoverRadius: 4,
        // Un hueco en el gráfico significa que no hay dato: no se une con una línea.
        spanGaps: false,
      })),
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        // Con una sola serie, el título de la tarjeta ya la identifica.
        legend: { display: series.length > 1, position: "bottom" },
      },
      scales: {
        x: { grid: { display: false }, ticks: { maxTicksLimit: 6, maxRotation: 0, autoSkipPadding: 24 } },
        y: { grid: { color: COLOR_REJILLA }, ...opcionesEjeY },
      },
    },
  });
}

/** Devuelve el último valor no nulo de una lista de filas. */
function ultimoValor(filas, campo) {
  for (let i = filas.length - 1; i >= 0; i--) {
    if (filas[i][campo] !== null && filas[i][campo] !== undefined) return filas[i];
  }
  return null;
}

/** Muestra junto al gráfico su último valor, para no depender solo de lo visual (NF2 §8.3). */
function escribirUltimoValor(id, fila, campoFecha, texto) {
  elemento(id).textContent = fila ? `Último valor (${fila[campoFecha]}): ${texto(fila)}` : "Sin datos en este periodo.";
}

function dibujarHistorial(historial) {
  const fechas = historial.metricas.map((m) => m.fecha);

  dibujarGrafico("grafico-carga", "line", fechas, [
    { nombre: "Carga 7 días", valores: historial.metricas.map((m) => m.carga_7d), color: COLORES.azul },
  ], { beginAtZero: true });
  escribirUltimoValor("valor-carga", ultimoValor(historial.metricas, "carga_7d"), "fecha",
    (f) => formatear(f.carga_7d, 0));

  dibujarGrafico("grafico-acwr", "line", fechas, [
    { nombre: "ACWR", valores: historial.metricas.map((m) => m.acwr), color: COLORES.azul },
  ], { beginAtZero: true });
  escribirUltimoValor("valor-acwr", ultimoValor(historial.metricas, "acwr"), "fecha",
    (f) => formatear(f.acwr, 2));

  dibujarGrafico("grafico-semanal", "bar", historial.carga_semanal.map((s) => s.semana_inicio), [
    { nombre: "Carga semanal", valores: historial.carga_semanal.map((s) => s.carga), color: COLORES.azul },
  ], { beginAtZero: true });
  escribirUltimoValor("valor-semanal", ultimoValor(historial.carga_semanal, "carga"), "semana_inicio",
    (f) => formatear(f.carga, 0));

  // Se usa la media de 7 días: el valor diario es entero y sus saltos no dejan ver la tendencia.
  const serieBienestar = (campo) => historial.metricas.map((m) => m[campo]);
  dibujarGrafico("grafico-bienestar", "line", fechas, [
    { nombre: "Fatiga", valores: serieBienestar("fatiga_media_7d"), color: COLORES.azul },
    { nombre: "Dolor muscular", valores: serieBienestar("dolor_muscular_media_7d"), color: COLORES.naranja },
    { nombre: "Calidad de sueño", valores: serieBienestar("calidad_sueno_media_7d"), color: COLORES.aqua },
  ], { min: 1, max: 5, ticks: { stepSize: 1 } });
  escribirUltimoValor("valor-bienestar", ultimoValor(historial.metricas, "fatiga_media_7d"), "fecha",
    (f) => `fatiga ${formatear(f.fatiga_media_7d, 1)}, dolor muscular ${formatear(f.dolor_muscular_media_7d, 1)}, ` +
      `calidad de sueño ${formatear(f.calidad_sueno_media_7d, 1)}`);
}


// --- Tablas y resultado ---

/** Rellena una tabla. Se usa textContent para que ningún dato se interprete como HTML. */
function rellenarTabla(idCuerpo, filas, columnas, textoVacio) {
  const cuerpo = elemento(idCuerpo);
  cuerpo.replaceChildren();
  if (filas.length === 0) {
    const fila = cuerpo.insertRow();
    const celda = fila.insertCell();
    celda.colSpan = columnas.length;
    celda.textContent = textoVacio;
    return;
  }
  for (const dato of filas) {
    const fila = cuerpo.insertRow();
    for (const columna of columnas) fila.insertCell().textContent = columna(dato);
  }
}

const textoRiesgo = (riesgo) => `${SIMBOLO_RIESGO[riesgo] ?? ""} ${riesgo}`;
const textoProbabilidad = (p) => `${formatear(p * 100, 1)} %`;

function dibujarTablas(historial) {
  rellenarTabla("tabla-predicciones", historial.predicciones, [
    (p) => p.fecha,
    (p) => p.fecha_objetivo,
    (p) => textoRiesgo(p.riesgo),
    (p) => textoProbabilidad(p.probabilidad),
    (p) => `${p.modelo} v${p.version}`,
    (p) => p.creada_en.replace("T", " "),
  ], "Todavía no hay predicciones para esta deportista.");

  rellenarTabla("tabla-sesiones", historial.sesiones.slice(0, NUM_SESIONES_VISIBLES), [
    (s) => s.fecha,
    (s) => formatear(s.duracion, 0),
    (s) => formatear(s.rpe, 0),
    (s) => formatear(s.srpe, 0),
  ], "No hay sesiones en este periodo.");
}

function mostrarResultado(prediccion) {
  const caja = elemento("resultado");
  caja.className = `resultado riesgo-${prediccion.riesgo}`;
  caja.replaceChildren();

  const nivel = document.createElement("p");
  nivel.className = "nivel";
  nivel.textContent = `${SIMBOLO_RIESGO[prediccion.riesgo]} Riesgo ${prediccion.riesgo}`;

  const detalle = document.createElement("p");
  detalle.textContent =
    `${prediccion.alias}: probabilidad estimada de fatiga percibida alta el ${prediccion.fecha_objetivo}: ` +
    `${textoProbabilidad(prediccion.probabilidad)}. Calculado con datos hasta el ${prediccion.fecha} ` +
    `(${prediccion.modelo} v${prediccion.version}).`;

  // La API devuelve el aviso en cada predicción: se muestra junto al resultado.
  const aviso = document.createElement("p");
  aviso.className = "nota";
  aviso.textContent = prediccion.aviso;

  caja.append(nivel, detalle, aviso);
  caja.hidden = false;
}


// --- Acciones de la página ---

async function cargarHistorial() {
  const id = elemento("deportista").value;
  if (!id) return;
  const parametros = new URLSearchParams();
  if (elemento("desde").value) parametros.set("desde", elemento("desde").value);
  if (elemento("hasta").value) parametros.set("hasta", elemento("hasta").value);

  const historial = await llamarApi(`/athletes/${id}/history?${parametros}`);
  const d = historial.deportista;
  elemento("resumen-deportista").textContent =
    `${d.alias} (${d.equipo}): datos del ${d.fecha_primera} al ${d.fecha_ultima}.`;
  dibujarHistorial(historial);
  dibujarTablas(historial);
}

async function ejecutar(accion) {
  limpiarError();
  try {
    await accion();
  } catch (error) {
    mostrarError(error.message);
  }
}

async function calcularRiesgo() {
  const boton = elemento("boton-predecir");
  boton.disabled = true;
  elemento("resultado").hidden = true;
  try {
    const cuerpo = { id_deportista: Number(elemento("deportista").value) };
    if (elemento("fecha-prediccion").value) cuerpo.fecha = elemento("fecha-prediccion").value;
    const prediccion = await llamarApi("/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cuerpo),
    });
    mostrarResultado(prediccion);
    await cargarHistorial();
  } finally {
    boton.disabled = false;
  }
}

async function comprobarServicio() {
  const salud = await llamarApi("/health");
  elemento("estado-servicio").textContent = salud.estado === "ok"
    ? `Servicio activo. Modelo v${salud.version_modelo} cargado.`
    : "Servicio degradado: falta la base de datos o el modelo. Revisa el README.";
}

async function iniciar() {
  await comprobarServicio();
  const deportistas = await llamarApi("/athletes");
  const selector = elemento("deportista");
  for (const d of deportistas) selector.add(new Option(`${d.alias} (${d.equipo})`, d.id_deportista));
  await cargarHistorial();
}

// Cambiar de deportista limpia el resultado y las fechas de la deportista anterior.
elemento("deportista").addEventListener("change", () => {
  elemento("resultado").hidden = true;
  elemento("fecha-prediccion").value = "";
  ejecutar(cargarHistorial);
});
elemento("form-filtros").addEventListener("submit", (evento) => {
  evento.preventDefault();
  ejecutar(cargarHistorial);
});
elemento("form-prediccion").addEventListener("submit", (evento) => {
  evento.preventDefault();
  ejecutar(calcularRiesgo);
});

ejecutar(iniciar);
