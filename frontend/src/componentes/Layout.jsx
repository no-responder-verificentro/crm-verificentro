import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

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

/**
 * Armazón del panel. Dos formas según el ancho de la pantalla:
 *
 *   - En computadora (lg y arriba) el menú va fijo a la izquierda, siempre
 *     visible, como estaba.
 *   - En celular y tableta el menú se esconde y se abre como cajón encima del
 *     contenido, porque 240px fijos en una pantalla de 360px no dejan nada.
 *
 * Es el mismo menú en los dos casos: un solo <nav>, para que no haya dos
 * listas que se desincronicen cuando agreguemos una sección.
 */
export default function Layout() {
  const { empleado, salir, puede } = useSesion();
  const visibles = SECCIONES.filter((s) => puede(s.permiso));
  const [abierto, setAbierto] = useState(false);
  const { pathname } = useLocation();

  // Al cambiar de sección el cajón se cierra solo: en celular, si no, tapa
  // justo la pantalla a la que acabas de entrar.
  useEffect(() => {
    setAbierto(false);
  }, [pathname]);

  // Mientras el cajón está abierto no se desplaza el fondo, y Escape lo cierra.
  useEffect(() => {
    if (!abierto) return;
    const alTeclear = (e) => e.key === "Escape" && setAbierto(false);
    window.addEventListener("keydown", alTeclear);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", alTeclear);
      document.body.style.overflow = "";
    };
  }, [abierto]);

  return (
    <div className="flex min-h-screen flex-col lg:flex-row">
      {/* Barra superior. Solo existe debajo de lg. */}
      <header
        className="sticky top-0 z-30 flex items-center gap-3 bg-guinda-oscuro
                   px-4 py-3 lg:hidden"
      >
        <button
          onClick={() => setAbierto(true)}
          aria-label="Abrir menú"
          aria-expanded={abierto}
          className="-ml-1 rounded-lg p-2 text-white transition hover:bg-white/10"
        >
          <IconoMenu />
        </button>
        <div className="min-w-0">
          <p className="truncate text-base font-bold text-white">VERIFICENTRO</p>
          <p className="truncate text-[10px] text-dorado">
            {tituloDeRuta(pathname)}
          </p>
        </div>
      </header>

      {/* Fondo oscuro del cajón. Al tocarlo se cierra. */}
      {abierto && (
        <div
          onClick={() => setAbierto(false)}
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          aria-hidden="true"
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-50 flex w-72 max-w-[85vw] flex-col
                    overflow-y-auto bg-guinda-oscuro p-4 transition-transform
                    duration-200
                    lg:static lg:z-auto lg:w-60 lg:max-w-none lg:shrink-0
                    lg:translate-x-0 ${
                      abierto ? "translate-x-0" : "-translate-x-full"
                    }`}
      >
        <div className="flex items-start justify-between px-3 py-4">
          <div>
            <p className="text-lg font-bold text-white">VERIFICENTRO</p>
            <p className="text-[11px] text-dorado">Panel administrativo</p>
          </div>
          <button
            onClick={() => setAbierto(false)}
            aria-label="Cerrar menú"
            className="-mt-1 -mr-1 rounded-lg px-2 text-2xl leading-none
                       text-white/60 transition hover:bg-white/10
                       hover:text-white lg:hidden"
          >
            ×
          </button>
        </div>

        <nav className="mt-2 flex flex-col gap-1">
          {visibles.map((s) => (
            <NavLink
              key={s.a}
              to={s.a}
              end={s.a === "/"}
              className={({ isActive }) =>
                `rounded-lg px-3.5 py-3 text-sm transition lg:py-2.5 ${
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
            className="mt-3 w-full rounded-lg px-3 py-2.5 text-left text-sm
                       text-white/70 transition hover:bg-white/10 hover:text-white"
          >
            Cerrar sesión
          </button>
        </div>
      </aside>

      <main className="min-w-0 flex-1 px-4 py-6 sm:px-7 sm:py-8 lg:p-9">
        <Outlet />
      </main>
    </div>
  );
}

/** Nombre de la sección actual, para la barra superior del celular. */
function tituloDeRuta(ruta) {
  if (ruta.startsWith("/vehiculos")) return "Ficha del vehículo";
  if (ruta.startsWith("/clientes/nuevo")) return "Alta de cliente";
  const exacta = SECCIONES.find((s) => s.a === ruta);
  if (exacta) return exacta.texto;
  const parcial = SECCIONES.find((s) => s.a !== "/" && ruta.startsWith(s.a));
  return parcial ? parcial.texto : "Panel administrativo";
}

function IconoMenu() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth="2" strokeLinecap="round"
         aria-hidden="true">
      <line x1="3" y1="6"  x2="21" y2="6" />
      <line x1="3" y1="12" x2="21" y2="12" />
      <line x1="3" y1="18" x2="21" y2="18" />
    </svg>
  );
}
