/**
 * Una función por operación de la API. Las pantallas llaman a estas y nunca
 * arman rutas a mano: si mañana cambia una ruta, se corrige en un solo lugar.
 */

import { api } from "./cliente";

export const auth = {
  entrar: (correo, contrasena) =>
    api.crear("/auth/login", { correo, contrasena }),
  yo: () => api.obtener("/auth/yo"),
};

export const clientes = {
  listar: ({ buscar, limite = 50, desplazamiento = 0 } = {}) =>
    api.obtener("/clientes", { buscar, limite, desplazamiento }),
  ficha: (id) => api.obtener(`/clientes/${id}`),
  registrar: (datos) => api.crear("/clientes", datos),
  editar: (id, datos) => api.editar(`/clientes/${id}`, datos),
  bajaDeContacto: (id) => api.crear(`/clientes/${id}/baja-de-contacto`, {}),
  agregarVehiculo: (id, datos) => api.crear(`/clientes/${id}/vehiculos`, datos),
};

export const vehiculos = {
  detalle: (id) => api.obtener(`/vehiculos/${id}`),
  editar: (id, datos) => api.editar(`/vehiculos/${id}`, datos),
  cambiarPlaca: (id, datos) =>
    api.crear(`/vehiculos/${id}/cambio-de-placa`, datos),
};

export const verificaciones = {
  listar: (filtros) => api.obtener("/verificaciones", filtros),
  resumen: ({ desde, hasta } = {}) =>
    api.obtener("/verificaciones/resumen", { desde, hasta }),
  registrar: (datos) => api.crear("/verificaciones", datos),
};

export const citas = {
  disponibilidad: (fecha) => api.obtener("/citas/disponibilidad", { fecha }),
  agenda: (fecha) => api.obtener("/citas", { fecha }),
  agendar: (datos) => api.crear("/citas", datos),
  cancelar: (id, motivo) => api.crear(`/citas/${id}/cancelar`, { motivo }),
  noAsistio: (id) => api.crear(`/citas/${id}/no-asistio`, {}),
};

export const recordatorios = {
  cola: (horas = 48) => api.obtener("/recordatorios/cola", { horas }),
  historial: (limite = 100) => api.obtener("/recordatorios/historial", { limite }),
  resumen: () => api.obtener("/recordatorios/resumen"),
  pausar: (id, motivo) => api.crear(`/recordatorios/${id}/pausar`, { motivo }),
  reanudar: (id) => api.crear(`/recordatorios/${id}/reanudar`, {}),
  cancelar: (id) => api.crear(`/recordatorios/${id}/cancelar`, {}),
};

export const panel = {
  indicadores: () => api.obtener("/panel/indicadores"),
  seguimiento: (estado, limite = 100) =>
    api.obtener("/panel/seguimiento", { estado, limite }),
  grafica: (meses = 8) => api.obtener("/panel/grafica", { meses }),
};

export const chatbot = {
  /** Público: no requiere token. */
  mensaje: (texto, canal = "web") =>
    api.crear("/chatbot/mensaje", { texto, canal }),
  sugerencias: () => api.obtener("/chatbot/sugerencias"),

  respuestas: (incluirInactivas = false) =>
    api.obtener("/chatbot/respuestas", { incluir_inactivas: incluirInactivas }),
  crear: (datos) => api.crear("/chatbot/respuestas", datos),
  editar: (id, datos) => api.editar(`/chatbot/respuestas/${id}`, datos),
  desactivar: (id) => api.eliminar(`/chatbot/respuestas/${id}`),
  pendientes: () => api.obtener("/chatbot/pendientes"),
  resolverPendiente: (id, respuestaId) =>
    api.crear(`/chatbot/pendientes/${id}/resolver?respuesta_id=${respuestaId}`, {}),
};

export const reportes = {
  efectividad: (anio) => api.obtener("/reportes/efectividad", { anio }),
  cumplimiento: (anio) => api.obtener("/reportes/cumplimiento", { anio }),
  canales: () => api.obtener("/reportes/canales"),
  porMes: (meses = 12) =>
    api.obtener("/reportes/verificaciones-por-mes", { meses }),
};

export const empleados = {
  listar: (incluirBajas = false) =>
    api.obtener("/empleados", { incluir_bajas: incluirBajas }),
  registrar: (datos) => api.crear("/empleados", datos),
  editar: (id, datos) => api.editar(`/empleados/${id}`, datos),
  darDeBaja: (id) => api.eliminar(`/empleados/${id}`),
};

export const calendario = {
  /** Público: no requiere token. Es el mismo que usa el chatbot. */
  consultar: (placa, anio) => api.obtener("/calendario/consultar", { placa, anio }),
};
