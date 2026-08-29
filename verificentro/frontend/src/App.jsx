import { Navigate, Route, Routes } from "react-router-dom";

import Layout from "./componentes/Layout";
import RutaProtegida from "./componentes/RutaProtegida";
import ClienteNuevo from "./paginas/ClienteNuevo";
import Clientes from "./paginas/Clientes";
import EnConstruccion from "./paginas/EnConstruccion";
import Login from "./paginas/Login";

export default function App() {
  return (
    <Routes>
      <Route path="/entrar" element={<Login />} />

      <Route
        element={
          <RutaProtegida>
            <Layout />
          </RutaProtegida>
        }
      >
        <Route index element={<EnConstruccion titulo="Panel de control"
          detalle="Los indicadores y la tabla de seguimiento se conectan cuando esté el job de recordatorios." />} />
        <Route path="clientes" element={<Clientes />} />
        <Route path="clientes/nuevo" element={<ClienteNuevo />} />
        <Route path="vehiculos/:id" element={<EnConstruccion titulo="Ficha del vehículo"
          detalle="Historial de verificaciones y bitácora de recordatorios." />} />
        <Route path="verificaciones" element={<EnConstruccion titulo="Verificaciones"
          detalle="La API ya está lista; falta conectar la pantalla." />} />
        <Route path="recordatorios" element={<EnConstruccion titulo="Recordatorios"
          detalle="Pendiente el job que llena la cola." />} />
        <Route path="chatbot" element={<EnConstruccion titulo="Chatbot" />} />
        <Route path="reportes" element={<EnConstruccion titulo="Reportes" />} />
        <Route path="empleados" element={<EnConstruccion titulo="Empleados y permisos"
          detalle="La API ya está lista; falta conectar la pantalla." />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
