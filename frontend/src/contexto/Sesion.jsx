/**
 * Sesión del empleado.
 *
 * El permiso real lo impone el backend en cada petición; esto es solo para
 * la interfaz, para no mostrar botones que van a devolver 403. Nunca al revés:
 * ocultar un botón NO es una medida de seguridad.
 */

import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { auth } from "../api/recursos";
import { borrarToken, guardarToken, leerToken } from "../api/cliente";

const ContextoSesion = createContext(null);

/** Qué puede hacer cada perfil. Espeja la matriz de permisos del backend. */
const PERMISOS = {
  administrador: [
    "ver_dashboard", "ver_clientes", "ver_citas", "capturar", "editar_contacto",
    "ver_verificaciones", "ver_recordatorios", "ver_chatbot",
    "ver_reportes", "ver_empleados",
  ],
  tecnico: [
    "ver_dashboard", "ver_clientes", "ver_citas", "capturar",
    "ver_verificaciones",
  ],
  // Atención agenda citas por el chatbot, así que necesita ver la agenda.
  atencion: ["ver_clientes", "ver_citas", "ver_verificaciones", "ver_chatbot"],
};

export function ProveedorSesion({ children }) {
  const [empleado, setEmpleado] = useState(null);
  const [cargando, setCargando] = useState(true);

  // Al abrir la app, si hay token guardado se valida contra el backend.
  // Si el empleado fue dado de baja, el token ya no sirve y se limpia.
  useEffect(() => {
    if (!leerToken()) {
      setCargando(false);
      return;
    }
    auth
      .yo()
      .then(setEmpleado)
      .catch(() => borrarToken())
      .finally(() => setCargando(false));
  }, []);

  const entrar = useCallback(async (correo, contrasena) => {
    const respuesta = await auth.entrar(correo, contrasena);
    guardarToken(respuesta.access_token);
    const yo = await auth.yo();
    setEmpleado(yo);
    return yo;
  }, []);

  const salir = useCallback(() => {
    borrarToken();
    setEmpleado(null);
  }, []);

  const puede = useCallback(
    (permiso) => (PERMISOS[empleado?.perfil] || []).includes(permiso),
    [empleado]
  );

  return (
    <ContextoSesion.Provider
      value={{ empleado, cargando, entrar, salir, puede }}
    >
      {children}
    </ContextoSesion.Provider>
  );
}

export function useSesion() {
  const contexto = useContext(ContextoSesion);
  if (!contexto) {
    throw new Error("useSesion debe usarse dentro de <ProveedorSesion>");
  }
  return contexto;
}
