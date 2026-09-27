import { NavLink, Outlet } from "react-router-dom";

import { useSesion } from "../contexto/Sesion";

const SECCIONES = [
  { a: "/",               texto: "Dashboard",      permiso: "ver_dashboard" },
  { a: "/clientes",       texto: "Clientes",       permiso: "ver_clientes" },
  { a: "/citas",          texto: "Citas",          permiso: "ver_citas" },
  { a: "/verificaciones", texto: "Verificaciones", permiso: "ver_verificaciones" },
  { a: "/recordatorios",  texto: "Recordatorios",  permiso: "ver_recordatorios" },
  { a: "/chatbot",        texto: "Chatbot",        permiso: "ver_chatbot" },
  { a: "/reportes",       texto: "Reportes",       permiso: "ver_reportes" },
  { a: "/empleados",      texto: "Empleados",      permiso: "ver_empleados" },
];

const PERFILES = {
  administrador: "Administrador",
  tecnico: "Técnico",
  atencion: "Atención",
};

export default function Layout() {
  const { empleado, salir, puede } = useSesion();
  const visibles = SECCIONES.filter((s) => puede(s.permiso));

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-60 shrink-0 flex-col bg-guinda-oscuro p-4">
        <div className="px-3 py-4">
          <p className="text-lg font-bold text-white">VERIFICENTRO</p>
          <p className="text-[11px] text-dorado">Panel administrativo</p>
        </div>

        <nav className="mt-4 flex flex-col gap-1">
          {visibles.map((s) => (
            <NavLink
              key={s.a}
              to={s.a}
              end={s.a === "/"}
              className={({ isActive }) =>
                `rounded-lg px-3.5 py-2.5 text-sm transition ${
                  isActive
                    ? "bg-guinda font-semibold text-white"
                    : "text-white/70 hover:bg-white/10 hover:text-white"
                }`
              }
            >
              {s.texto}
            </NavLink>
          ))}
        </nav>

        <div className="mt-auto border-t border-white/15 pt-4">
          <p className="px-3 text-sm font-semibold text-white">
            {empleado?.nombre}
          </p>
          <p className="px-3 text-[11px] text-dorado">
            {PERFILES[empleado?.perfil] || empleado?.perfil}
          </p>
          <button
            onClick={salir}
            className="mt-3 w-full rounded-lg px-3 py-2 text-left text-sm
                       text-white/70 transition hover:bg-white/10 hover:text-white"
          >
            Cerrar sesión
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-x-auto p-9">
        <Outlet />
      </main>
    </div>
  );
}
