import { useCallback, useEffect, useState } from "react";

import Aviso from "../componentes/Aviso";
import Cargando from "../componentes/Cargando";
import Modal from "../componentes/Modal";
import Pastilla from "../componentes/Pastilla";
import { empleados as api } from "../api/recursos";
import { useSesion } from "../contexto/Sesion";

const PERFILES = {
  administrador: ["Administrador", "bg-guinda/15 text-guinda"],
  tecnico:       ["Técnico",       "bg-info/15 text-info"],
  atencion:      ["Atención",      "bg-alerta/15 text-alerta"],
};

/** Espeja la matriz que aprobó el cliente. El permiso real lo impone el
 *  backend; esto es la referencia visible para quien administra. */
const MATRIZ = [
  ["Registrar clientes y vehículos",            1, 1, 0],
  ["Registrar verificaciones",                  1, 1, 0],
  ["Apartar y cancelar citas",                  1, 1, 0],
  ["Consultar a quién le toca y quién verificó", 1, 1, 1],
  ["Ver datos de contacto del cliente",         1, 2, 2],
  ["Editar datos de contacto",                  1, 0, 0],
  ["Pausar o cancelar recordatorios",           1, 0, 0],
  ["Ver reportes y exportar",                   1, 0, 0],
  ["Registrar y dar de baja empleados",         1, 0, 0],
];

function fecha(iso) {
  if (!iso) return "nunca";
  const f = new Date(iso);
  const hoy = new Date();
  if (f.toDateString() === hoy.toDateString()) {
    return `Hoy · ${f.toLocaleTimeString("es-MX", { hour: "2-digit", minute: "2-digit" })}`;
  }
  return f.toLocaleDateString("es-MX", { day: "2-digit", month: "short", year: "numeric" });
}

export default function Empleados() {
  const { empleado: yo } = useSesion();

  const [lista, setLista] = useState([]);
  const [incluirBajas, setIncluirBajas] = useState(false);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [aviso, setAviso] = useState(null);
  const [alta, setAlta] = useState(false);

  const cargar = useCallback(async (bajas) => {
    setCargando(true);
    setError(null);
    try {
      setLista(await api.listar(bajas));
    } catch (e) {
      setError(e.message);
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    cargar(incluirBajas);
  }, [incluirBajas, cargar]);

  async function accion(fn, id, mensaje) {
    setError(null);
    try {
      await fn(id);
      setAviso(mensaje);
      cargar(incluirBajas);
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-guinda-oscuro">
            Empleados y permisos
          </h1>
          <p className="mt-1 text-sm text-neutral-500">
            Cada quien entra con su propia cuenta. Todo lo que se captura queda
            firmado con el nombre de quien lo hizo.
          </p>
        </div>
        <button onClick={() => setAlta(true)} className="boton-principal shrink-0">
          Registrar empleado
        </button>
      </div>

      {aviso && <Aviso tono="exito">{aviso}</Aviso>}
      <Aviso>{error}</Aviso>

      <section className="tarjeta overflow-hidden">
        <header className="flex flex-wrap items-center justify-between gap-3 px-6 py-4">
          <div>
            <h2 className="text-lg font-bold text-guinda">Personal registrado</h2>
            <p className="text-xs text-neutral-500">
              Dar de baja desactiva el acceso pero conserva el historial de lo
              que capturó.
            </p>
          </div>
          <label className="flex items-center gap-2 text-xs font-semibold text-neutral-500">
            <input type="checkbox" checked={incluirBajas}
                   onChange={(e) => setIncluirBajas(e.target.checked)}
                   className="h-4 w-4 accent-guinda" />
            Mostrar dados de baja
          </label>
        </header>

        {cargando ? (
          <Cargando />
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-neutral-50 text-left text-[11px] font-bold text-neutral-500">
              <tr>
                <th className="px-6 py-3">NOMBRE</th>
                <th className="px-6 py-3">CUENTA</th>
                <th className="px-6 py-3">PERFIL</th>
                <th className="px-6 py-3">ESTADO</th>
                <th className="px-6 py-3">ÚLTIMO ACCESO</th>
                <th className="px-6 py-3" />
              </tr>
            </thead>
            <tbody>
              {lista.map((e) => {
                const soyYo = e.id === yo?.id;
                return (
                  <tr key={e.id} className="border-t border-borde">
                    <td className="px-6 py-3 font-semibold">
                      {e.nombre}
                      {soyYo && (
                        <span className="ml-2 text-[11px] font-bold text-neutral-400">
                          (tú)
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-3 text-neutral-500">{e.correo}</td>
                    <td className="px-6 py-3">
                      <SelectorPerfil
                        empleado={e}
                        bloqueado={soyYo}
                        alCambiar={async (perfil) => {
                          try {
                            await api.editar(e.id, { perfil });
                            setAviso(`${e.nombre} ahora es ${PERFILES[perfil][0]}.`);
                            cargar(incluirBajas);
                          } catch (err) {
                            setError(err.message);
                          }
                        }}
                      />
                    </td>
                    <td className="px-6 py-3">
                      <Pastilla
                        texto={e.activo ? "Activo" : "Dado de baja"}
                        clase={e.activo
                          ? "bg-exito/15 text-exito"
                          : "bg-error/15 text-error"}
                      />
                    </td>
                    <td className="px-6 py-3 text-neutral-500">
                      {fecha(e.ultimo_acceso)}
                    </td>
                    <td className="px-6 py-3 text-right whitespace-nowrap">
                      {soyYo ? (
                        <span className="text-xs text-neutral-400"
                              title="Nadie puede darse de baja a sí mismo">
                          —
                        </span>
                      ) : e.activo ? (
                        <button
                          onClick={() => accion(api.darDeBaja, e.id,
                                                `${e.nombre} ya no puede entrar.`)}
                          className="text-xs font-bold text-error hover:underline"
                        >
                          Dar de baja
                        </button>
                      ) : (
                        <button
                          onClick={() => accion(
                            (id) => api.editar(id, { activo: true }), e.id,
                            `${e.nombre} puede entrar de nuevo.`)}
                          className="text-xs font-bold text-info hover:underline"
                        >
                          Reactivar
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>

      <Matriz />

      {alta && (
        <Modal
          titulo="Registrar empleado"
          descripcion="La contraseña se la das tú en persona. Puede cambiarla después."
          onCerrar={() => setAlta(false)}
        >
          <FormularioAlta
            alCancelar={() => setAlta(false)}
            alGuardar={(nuevo) => {
              setAlta(false);
              setAviso(`${nuevo.nombre} ya puede entrar.`);
              cargar(incluirBajas);
            }}
          />
        </Modal>
      )}
    </div>
  );
}

function SelectorPerfil({ empleado, bloqueado, alCambiar }) {
  if (bloqueado) {
    const [texto, clase] = PERFILES[empleado.perfil];
    return (
      <span title="No puedes cambiar tu propio perfil">
        <Pastilla texto={texto} clase={clase} />
      </span>
    );
  }
  return (
    <select
      value={empleado.perfil}
      onChange={(e) => alCambiar(e.target.value)}
      disabled={!empleado.activo}
      className="rounded-lg border border-borde bg-white px-2.5 py-1.5 text-xs
                 font-bold outline-none focus:border-guinda disabled:opacity-50"
    >
      {Object.entries(PERFILES).map(([valor, [texto]]) => (
        <option key={valor} value={valor}>{texto}</option>
      ))}
    </select>
  );
}

function Matriz() {
  return (
    <section className="tarjeta overflow-hidden">
      <header className="px-6 py-4">
        <h2 className="text-lg font-bold text-guinda">
          Qué puede hacer cada perfil
        </h2>
        <p className="text-xs text-neutral-500">
          Los permisos van por perfil, no por persona. Si alguien cambia de
          puesto, se le cambia el perfil y listo.
        </p>
      </header>
      <table className="w-full text-sm">
        <thead className="bg-neutral-50 text-left text-[11px] font-bold text-neutral-500">
          <tr>
            <th className="px-6 py-3">PERMISO</th>
            <th className="px-6 py-3 text-center text-guinda">ADMINISTRADOR</th>
            <th className="px-6 py-3 text-center text-info">TÉCNICO</th>
            <th className="px-6 py-3 text-center text-alerta">ATENCIÓN</th>
          </tr>
        </thead>
        <tbody>
          {MATRIZ.map(([permiso, ...valores]) => (
            <tr key={permiso} className="border-t border-borde">
              <td className="px-6 py-3">{permiso}</td>
              {valores.map((v, i) => (
                <td key={i} className="px-6 py-3 text-center">
                  {v === 2 ? (
                    <Pastilla texto="Solo lectura"
                              clase="bg-neutral-400/20 text-neutral-600" />
                  ) : (
                    <span className={`font-bold ${
                      v ? "text-exito" : "text-neutral-300"}`}>
                      {v ? "Sí" : "No"}
                    </span>
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function FormularioAlta({ alGuardar, alCancelar }) {
  const [f, setF] = useState({
    nombre: "", correo: "", contrasena: "", perfil: "tecnico",
  });
  const [error, setError] = useState(null);
  const [enviando, setEnviando] = useState(false);

  const cambiar = (campo) => (e) => setF({ ...f, [campo]: e.target.value });

  async function enviar(evento) {
    evento.preventDefault();
    setError(null);
    setEnviando(true);
    try {
      alGuardar(await api.registrar({
        nombre: f.nombre,
        correo: f.correo.trim().toLowerCase(),
        contrasena: f.contrasena,
        perfil: f.perfil,
      }));
    } catch (e) {
      setError(e.message);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <form onSubmit={enviar} className="space-y-4">
      <label className="block">
        <span className="etiqueta">NOMBRE COMPLETO</span>
        <input className="campo" value={f.nombre} onChange={cambiar("nombre")}
               required minLength={3} autoFocus />
      </label>

      <label className="block">
        <span className="etiqueta">CORREO</span>
        <input className="campo" type="email" value={f.correo}
               onChange={cambiar("correo")}
               placeholder="nombre@verificentro.mx" required />
      </label>

      <label className="block">
        <span className="etiqueta">CONTRASEÑA</span>
        <input className="campo" type="text" value={f.contrasena}
               onChange={cambiar("contrasena")} required
               minLength={8} maxLength={72} />
        <span className="mt-1 block text-xs text-neutral-500">
          Mínimo 8 caracteres. Se muestra a propósito: se la vas a dictar en
          persona.
        </span>
      </label>

      <div>
        <span className="etiqueta">PERFIL</span>
        <div className="space-y-2">
          {[
            ["tecnico", "Técnico",
             "Mostrador: registra clientes, vehículos, verificaciones y citas."],
            ["atencion", "Atención",
             "Responde el chatbot y consulta periodos. No captura."],
            ["administrador", "Administrador",
             "Todo, incluidos reportes, recordatorios y empleados."],
          ].map(([valor, titulo, detalle]) => (
            <label
              key={valor}
              className={`flex cursor-pointer gap-3 rounded-xl border px-4 py-3
                          transition ${
                f.perfil === valor
                  ? "border-guinda bg-guinda-claro"
                  : "border-borde hover:bg-crema"
              }`}
            >
              <input type="radio" name="perfil" value={valor}
                     checked={f.perfil === valor}
                     onChange={cambiar("perfil")}
                     className="mt-0.5 accent-guinda" />
              <span>
                <span className="block text-sm font-bold">{titulo}</span>
                <span className="block text-xs text-neutral-500">{detalle}</span>
              </span>
            </label>
          ))}
        </div>
      </div>

      <Aviso>{error}</Aviso>

      <div className="flex gap-3 pt-1">
        <button type="submit" className="boton-principal" disabled={enviando}>
          {enviando ? "Guardando…" : "Registrar"}
        </button>
        <button type="button" className="boton-secundario" onClick={alCancelar}>
          Cancelar
        </button>
      </div>
    </form>
  );
}
