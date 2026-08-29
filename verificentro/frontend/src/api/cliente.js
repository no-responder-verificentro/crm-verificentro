/**
 * Único punto por donde sale una petición al backend.
 *
 * Se encarga de tres cosas para que ninguna pantalla tenga que repetirlas:
 * adjuntar el token, traducir los errores de FastAPI a un mensaje legible en
 * español, y avisar cuando la sesión ya no sirve.
 */

const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";
const LLAVE_TOKEN = "verificentro_token";

export function guardarToken(token) {
  localStorage.setItem(LLAVE_TOKEN, token);
}

export function leerToken() {
  return localStorage.getItem(LLAVE_TOKEN);
}

export function borrarToken() {
  localStorage.removeItem(LLAVE_TOKEN);
}

/** Error con el mensaje ya listo para mostrarle a la persona. */
export class ErrorApi extends Error {
  constructor(mensaje, estado, detalles = null) {
    super(mensaje);
    this.estado = estado;
    this.detalles = detalles;
  }

  get esSesionVencida() {
    return this.estado === 401;
  }

  get esSinPermiso() {
    return this.estado === 403;
  }
}

/**
 * FastAPI devuelve `detail` como texto en los errores de negocio, pero como
 * lista de objetos en los de validación (422). Esto lo aplana a algo que se
 * pueda leer.
 */
function mensajeDeError(cuerpo, estado) {
  const detalle = cuerpo?.detail;

  if (typeof detalle === "string") return detalle;

  if (Array.isArray(detalle)) {
    return detalle
      .map((e) => {
        // e.loc viene como ["body", "vehiculo", "placa"]; el último es el campo.
        const campo = Array.isArray(e.loc) ? e.loc[e.loc.length - 1] : null;
        const texto = (e.msg || "").replace(/^Value error,\s*/, "");
        return campo && campo !== "body" ? `${campo}: ${texto}` : texto;
      })
      .join(" · ");
  }

  if (estado === 401) return "Tu sesión expiró. Vuelve a entrar.";
  if (estado === 403) return "Tu perfil no tiene permiso para esta operación.";
  if (estado >= 500) return "El servidor tuvo un problema. Intenta de nuevo.";
  return "No se pudo completar la operación.";
}

async function peticion(ruta, opciones = {}) {
  const token = leerToken();

  let respuesta;
  try {
    respuesta = await fetch(`${BASE}${ruta}`, {
      ...opciones,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...opciones.headers,
      },
    });
  } catch {
    // fetch solo truena así cuando no hubo respuesta del servidor.
    throw new ErrorApi(
      "No se pudo conectar con el servidor. ¿Está corriendo el backend?",
      0
    );
  }

  if (respuesta.status === 204) return null;

  let cuerpo = null;
  try {
    cuerpo = await respuesta.json();
  } catch {
    cuerpo = null;
  }

  if (!respuesta.ok) {
    throw new ErrorApi(
      mensajeDeError(cuerpo, respuesta.status),
      respuesta.status,
      cuerpo?.detail
    );
  }

  return cuerpo;
}

function conParametros(ruta, parametros) {
  const limpios = Object.entries(parametros || {}).filter(
    ([, v]) => v !== undefined && v !== null && v !== ""
  );
  if (limpios.length === 0) return ruta;
  return `${ruta}?${new URLSearchParams(limpios)}`;
}

export const api = {
  obtener: (ruta, parametros) => peticion(conParametros(ruta, parametros)),
  crear: (ruta, datos) =>
    peticion(ruta, { method: "POST", body: JSON.stringify(datos) }),
  editar: (ruta, datos) =>
    peticion(ruta, { method: "PATCH", body: JSON.stringify(datos) }),
  eliminar: (ruta) => peticion(ruta, { method: "DELETE" }),
};
