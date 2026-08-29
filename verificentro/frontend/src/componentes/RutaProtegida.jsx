import { Navigate, useLocation } from "react-router-dom";

import Cargando from "./Cargando";
import { useSesion } from "../contexto/Sesion";

/** Manda al login si no hay sesión. El permiso de verdad lo impone el
 *  backend; esto solo evita pantallas rotas. */
export default function RutaProtegida({ children }) {
  const { empleado, cargando } = useSesion();
  const ubicacion = useLocation();

  if (cargando) return <Cargando texto="Verificando sesión…" />;
  if (!empleado) return <Navigate to="/entrar" replace state={{ de: ubicacion }} />;
  return children;
}
