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
