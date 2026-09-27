import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import Aviso from "../componentes/Aviso";
import Cargando from "../componentes/Cargando";
import Modal from "../componentes/Modal";
import Pastilla from "../componentes/Pastilla";
import Vacio from "../componentes/Vacio";
import { citas as api } from "../api/recursos";
import { useSesion } from "../contexto/Sesion";
import { telefonoLegible } from "../utils/formato";

const HOY = new Date().toISOString().slice(0, 10);

const ESTADOS = {
  agendada:   ["Agendada",     "bg-info/15 text-info"],
  confirmada: ["Confirmada",   "bg-info/15 text-info"],
  atendida:   ["Atendida",     "bg-exito/15 text-exito"],
  no_asistio: ["No se presentó", "bg-error/15 text-error"],
  cancelada:  ["Cancelada",    "bg-neutral-400/20 text-neutral-600"],
};

const ORIGENES = {
  mostrador: "Mostrador",
  chatbot_whatsapp: "WhatsApp",
  chatbot_facebook: "Facebook",
  web: "Web",
  telefono: "Teléfono",
};

const hora = (t) => (t || "").slice(0, 5);

export default function Citas() {
  const { puede } = useSesion();

  const [fecha, setFecha] = useState(HOY);
  const [agenda, setAgenda] = useState([]);
  const [libres, setLibres] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [aviso, setAviso] = useState(null);
  const [apartando, setApartando] = useState(null);   // hora elegida

  const cargar = useCallback(async (dia) => {
    setCargando(true);
    setError(null);
    try {
      const [lista, disponibilidad] = await Promise.all([
        api.agenda(dia),
        api.disponibilidad(dia),
      ]);
      setAgenda(lista);
      setLibres(disponibilidad);
    } catch (e) {
      setError(e.message);
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    cargar(fecha);
  }, [fecha, cargar]);

  async function accion(fn, id, mensaje) {
    setError(null);
    try {
      await fn(id);
      setAviso(mensaje);
      cargar(fecha);
    } catch (e) {
      setError(e.message);
    }
  }

  const activas = agenda.filter((c) => ["agendada", "confirmada"].includes(c.estado));

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-guinda-oscuro">Citas</h1>
          <p className="mt-1 text-sm text-neutral-500">
            Una línea, bloques de 20 minutos. Se aparta una cita por hora y los
            demás espacios quedan libres para quien llega sin avisar.
          </p>
        </div>
        <label className="block">
          <span className="etiqueta">DÍA</span>
          <input type="date" className="campo" value={fecha}
                 onChange={(e) => setFecha(e.target.value)} />
        </label>
      </div>

      {aviso && <Aviso tono="exito">{aviso}</Aviso>}
      <Aviso>{error}</Aviso>

      {cargando ? (
        <Cargando />
      ) : (
        <>
          <HorariosLibres
            libres={libres}
            puedeApartar={puede("capturar")}
            alElegir={setApartando}
          />

          <section className="tarjeta overflow-hidden">
            <header className="px-6 py-4">
              <h2 className="text-lg font-bold text-guinda">
                Agenda del día
              </h2>
              <p className="text-xs text-neutral-500">
                {activas.length === 0
                  ? "Nadie tiene cita este día."
                  : `${activas.length} cita(s) por atender. Al registrar su verificación se cierran solas.`}
              </p>
            </header>

            {agenda.length === 0 ? (
              <Vacio
                titulo="Sin citas este día"
                detalle="Los clientes pueden apartar desde el chatbot, o el mostrador puede hacerlo con los horarios de arriba."
              />
            ) : (
              <table className="w-full text-sm">
                <thead className="bg-neutral-50 text-left text-[11px] font-bold text-neutral-500">
                  <tr>
                    <th className="px-6 py-3">HORA</th>
                    <th className="px-6 py-3">PLACA</th>
                    <th className="px-6 py-3">CONTACTO</th>
                    <th className="px-6 py-3">ORIGEN</th>
                    <th className="px-6 py-3">ESTADO</th>
                    <th className="px-6 py-3" />
                  </tr>
                </thead>
                <tbody>
                  {agenda.map((c) => (
                    <tr key={c.id} className="border-t border-borde">
                      <td className="px-6 py-3 text-base font-bold whitespace-nowrap">
                        {hora(c.hora_inicio)}
                      </td>
                      <td className="px-6 py-3 font-bold">
                        {c.vehiculo_id ? (
                          <Link to={`/vehiculos/${c.vehiculo_id}`}
                                className="hover:underline">
                            {c.placa_capturada}
                          </Link>
                        ) : (
                          <>
                            {c.placa_capturada}
                            <span className="ml-2 text-[11px] font-bold text-alerta"
                                  title="Esta placa aún no está en el padrón">
                              sin registrar
                            </span>
                          </>
                        )}
                      </td>
                      <td className="px-6 py-3">
                        {c.nombre_contacto}
                        <span className="block text-xs text-neutral-500">
                          {telefonoLegible(c.telefono_contacto)}
                        </span>
                      </td>
                      <td className="px-6 py-3 text-neutral-500">
                        {ORIGENES[c.origen] || c.origen}
                      </td>
                      <td className="px-6 py-3">
                        <Pastilla texto={ESTADOS[c.estado]?.[0] || c.estado}
                                  clase={ESTADOS[c.estado]?.[1] || ""} />
                      </td>
                      <td className="px-6 py-3 text-right whitespace-nowrap">
                        {puede("capturar") &&
                          ["agendada", "confirmada"].includes(c.estado) && (
                            <>
                              <button
                                onClick={() =>
                                  accion(api.noAsistio, c.id, "Marcada como no presentada.")
                                }
                                className="text-xs font-bold text-alerta hover:underline"
                              >
                                No se presentó
                              </button>
                              <button
                                onClick={() =>
                                  accion((id) => api.cancelar(id, null), c.id,
                                         "Cita cancelada. El horario quedó libre.")
                                }
                                className="ml-3 text-xs font-bold text-error hover:underline"
                              >
                                Cancelar
                              </button>
                            </>
                          )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          <div className="rounded-xl border border-dorado/45 bg-dorado-claro px-5 py-4 text-sm">
            <span className="font-bold text-dorado">Importante</span>{" "}
            <span className="text-guinda-oscuro">
              La cita solo sirve si se respeta. Si el cliente de las 10:00 llega
              y lo forman detrás de cinco autos sin cita, no vuelve a agendar.
            </span>
          </div>
        </>
      )}

      {apartando && (
        <Modal
          titulo={`Apartar cita · ${hora(apartando)}`}
          descripcion={`Para el ${fecha}. Se puede cancelar después y el horario queda libre.`}
          onCerrar={() => setApartando(null)}
        >
          <FormularioCita
            fecha={fecha}
            hora={apartando}
            alCancelar={() => setApartando(null)}
            alGuardar={() => {
              setApartando(null);
              setAviso("Cita apartada.");
              cargar(fecha);
            }}
          />
        </Modal>
      )}
    </div>
  );
}

function HorariosLibres({ libres, puedeApartar, alElegir }) {
  if (!libres) return null;

  if (!libres.atiende) {
    return (
      <Aviso tono="alerta">
        {libres.motivo || "Ese día no se atiende."}
      </Aviso>
    );
  }

  return (
    <section className="tarjeta p-6">
      <h2 className="text-lg font-bold text-guinda">Horarios libres</h2>
      <p className="mb-4 text-xs text-neutral-500">
        Estos son los espacios que se pueden apartar. Los intermedios existen,
        pero se reservan para quien llega sin cita.
      </p>

      {libres.horarios.length === 0 ? (
        <p className="text-sm text-neutral-500">
          No quedan horarios disponibles para este día.
        </p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {libres.horarios.map((h) => (
            <button
              key={h.hora}
              disabled={!puedeApartar}
              onClick={() => alElegir(h.hora)}
              className="rounded-lg border border-verde/40 bg-verde/5 px-4 py-2.5
                         text-sm font-bold text-verde transition
                         hover:bg-verde hover:text-white
                         disabled:cursor-default disabled:opacity-60
                         disabled:hover:bg-verde/5 disabled:hover:text-verde"
            >
              {hora(h.hora)}
            </button>
          ))}
        </div>
      )}
    </section>
  );
}

function FormularioCita({ fecha, hora: horaElegida, alGuardar, alCancelar }) {
  const [f, setF] = useState({ placa: "", nombre: "", telefono: "", notas: "" });
  const [error, setError] = useState(null);
  const [enviando, setEnviando] = useState(false);

  const cambiar = (campo) => (e) => setF({ ...f, [campo]: e.target.value });

  async function enviar(evento) {
    evento.preventDefault();
    setError(null);
    setEnviando(true);
    try {
      await api.agendar({
        placa: f.placa,
        nombre: f.nombre,
        telefono: f.telefono || null,
        fecha,
        hora: horaElegida,
        origen: "mostrador",
        notas: f.notas || null,
      });
      alGuardar();
    } catch (e) {
      setError(e.message);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <form onSubmit={enviar} className="space-y-4">
      <label className="block">
        <span className="etiqueta">PLACA</span>
        <input className="campo uppercase" value={f.placa}
               onChange={cambiar("placa")} placeholder="YUN-047-A"
               required minLength={4} autoFocus />
      </label>

      <label className="block">
        <span className="etiqueta">NOMBRE DE QUIEN VIENE</span>
        <input className="campo" value={f.nombre} onChange={cambiar("nombre")}
               required minLength={3} />
      </label>

      <label className="block">
        <span className="etiqueta">TELÉFONO (OPCIONAL)</span>
        <input className="campo" value={f.telefono} onChange={cambiar("telefono")}
               placeholder="228 100 9584" inputMode="tel" />
      </label>

      <label className="block">
        <span className="etiqueta">NOTAS (OPCIONAL)</span>
        <input className="campo" value={f.notas} onChange={cambiar("notas")}
               maxLength={255} />
      </label>

      <p className="text-xs text-neutral-500">
        Si la placa ya está en el padrón, la cita se vincula sola al vehículo.
        Si no, se registra igual y se vincula cuando llegue al mostrador.
      </p>

      <Aviso>{error}</Aviso>

      <div className="flex gap-3 pt-1">
        <button type="submit" className="boton-principal" disabled={enviando}>
          {enviando ? "Apartando…" : "Apartar cita"}
        </button>
        <button type="button" className="boton-secundario" onClick={alCancelar}>
          Cancelar
        </button>
      </div>
    </form>
  );
}
