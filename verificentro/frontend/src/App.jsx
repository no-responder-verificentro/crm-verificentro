import { Navigate, Route, Routes } from "react-router-dom";

import Layout from "./componentes/Layout";
import RutaProtegida from "./componentes/RutaProtegida";
import Chatbot from "./paginas/Chatbot";
import Citas from "./paginas/Citas";
import Consulta from "./paginas/Consulta";
import Empleados from "./paginas/Empleados";
import ClienteNuevo from "./paginas/ClienteNuevo";
import Dashboard from "./paginas/Dashboard";
import FichaVehiculo from "./paginas/FichaVehiculo";
import Clientes from "./paginas/Clientes";
import EnConstruccion from "./paginas/EnConstruccion";
import Login from "./paginas/Login";
import Recordatorios from "./paginas/Recordatorios";
import Reportes from "./paginas/Reportes";
import Verificaciones from "./paginas/Verificaciones";

export default function App() {
  return (
    <Routes>
      <Route path="/entrar" element={<Login />} />
      {/* Pública: es a donde llega el cliente desde el correo. */}
      <Route path="/consulta" element={<Consulta />} />

      <Route
        element={
          <RutaProtegida>
            <Layout />
          </RutaProtegida>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="clientes" element={<Clientes />} />
        <Route path="clientes/nuevo" element={<ClienteNuevo />} />
        <Route path="citas" element={<Citas />} />
        <Route path="vehiculos/:id" element={<FichaVehiculo />} />
        <Route path="verificaciones" element={<Verificaciones />} />
        <Route path="recordatorios" element={<Recordatorios />} />
        <Route path="chatbot" element={<Chatbot />} />
        <Route path="reportes" element={<Reportes />} />
        <Route path="empleados" element={<Empleados />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
