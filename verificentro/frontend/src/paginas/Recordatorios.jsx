import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import Aviso from "../componentes/Aviso";
import Cargando from "../componentes/Cargando";
import Indicador from "../componentes/Indicador";
import Pastilla from "../componentes/Pastilla";
import Vacio from "../componentes/Vacio";
import { recordatorios as api } from "../api/recursos";
import { useSesion } from "../contexto/Sesion";

const AVISOS = {
  aviso_1: "Aviso 1 · 15 días antes",
  aviso_2: "Aviso 2 · abre el periodo",
  aviso_3: "Aviso 3 · a la mitad",
  aviso_4: "Aviso 4 · últimos 5 días",
  seguimiento: "Seguimiento · vencido",
};

const ENTREGA = {
  pendiente:    ["Pendiente",    "bg-neutral-400/20 text-neutral-600"],
  enviado:      ["Enviado",      "bg-info/15 text-info"],
  entregado:    ["Entregado",    "bg-exito/15 text-exito"],
  leido:        ["Leído",        "bg-exito/15 text-exito"],
  clic:         ["Hizo clic",    "bg-exito/15 text-exito"],
  rebote_duro:  ["Rebotó",       "bg-error/15 text-error"],
  rebote_suave: ["Rebote temporal", "bg-alerta/15 text-alerta"],
  fallido:      ["No entregado", "bg-error/15 text-error"],
  spam:         ["Marcado spam", "bg-error/15 text-error"],
  baja:         ["Se dio de baja", "bg-error/15 text-error"],
};

const ESTADO = {
  programado: ["Programado", "bg-info/15 text-info"],
  pausado:    ["Pausado",    "bg-alerta/15 text-alerta"],
  cancelado:  ["Cancelado",  "bg-neutral-400/20 text-neutral-600"],
  en_proceso: ["Enviando…",  "bg-info/15 text-info"],
  enviado:    ["Enviado",    "bg-exito/15 text-exito"],
  error:      ["Error",      "bg-error/15 text-error"],
};

function cuando(iso) {
  if (!iso) return "—";
  const f = new Date(iso);
  const hoy = new Date();
  const mismoDia = f.toDateString() === hoy.toDateString();
  const hora = f.toLocaleTimeString("es-MX", { hour: "2-digit", minute: "2-digit" });
  if (mismoDia) return `Hoy · ${hora}`;
  return `${f.toLocaleDateString("es-MX", { day: "2-digit", month: "short" })} · ${hora}`;
}

export default function Recordatorios() {
  const { puede } = useSesion();

  const [resumen, setResumen] = useState(null);
  const [cola, setCola] = useState([]);
  const [historial, setHistorial] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);

  const cargar = useCallback(async () => {
    setError(null);
    try {
      const [r, c, h] = await Promise.all([
        api.resumen(),
        api.cola(24 * 30),
        api.historial(50),
      ]);
      setResumen(r);
      setCola(c);
      setHistorial(h);
    } catch (e) {
      setError(e.message);
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  async function accion(fn, id) {
    try {
      await fn(id);
      cargar();
    } catch (e) {
      setError(e.message);
    }
  }

  const [trabajando, setTrabajando] = useState(null);

  async function revisar() {
    setError(null);
    setTrabajando("revisar");
    try {
      const r = await api.generar(90);
      setAviso(
        r.creados > 0
          ? `Se prepararon ${r.creados} avisos nuevos.` +
            (r.cancelados ? ` Se cancelaron ${r.cancelados} de clientes que ya verificaron.` : "")
          : "Revisado. No hay avisos nuevos por preparar: nadie cumple fecha en los próximos 90 días." +
            (r.cancelados ? ` Se cancelaron ${r.cancelados} de clientes que ya verificaron.` : "")
      );
      cargar();
    } catch (e) {
      setError(e.message);
    } finally {
      setTrabajando(null);
    }
  }

  async function enviarAhora() {
    setError(null);
    setTrabajando("enviar");
    try {
      const r = await api.enviar();
      setAviso(
        r.enviados > 0
          ? `Se enviaron ${r.enviados} avisos.` +
            (r.fallidos ? ` ${r.fallidos} no se pudieron entregar.` : "")
          : "No había nada por enviar en este momento."
      );
      cargar();
    } catch (e) {
      setError(e.message);
    } finally {
      setTrabajando(null);
    }
  }

  if (cargando) return <Cargando texto="Cargando recordatorios…" />;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-guinda-oscuro">Recordatorios</h1>
          <p className="mt-1 max-w-2xl text-sm text-neutral-500">
            Lo que está por salir y lo que ya salió. Se cancela solo si el
            cliente verifica antes.
          </p>
        </div>

        {puede("editar_contacto") && (
          <div className="flex shrink-0 gap-3">
            <button onClick={revisar} className="boton-secundario"
                    disabled={Boolean(trabajando)}>
              {trabajando === "revisar" ? "Revisando…" : "Revisar a quién le toca"}
            </button>
            <button onClick={enviarAhora} className="boton-principal"
                    disabled={Boolean(trabajando)}>
              {trabajando === "enviar" ? "Enviando…" : "Enviar ahora"}
            </button>
          </div>
        )}
      </div>

      <Aviso>{error}</Aviso>

      {resumen && (
        <>
          <div className="flex flex-wrap gap-4">
            <Indicador etiqueta="Programados para hoy"
                       valor={resumen.programados_hoy} />
            <Indicador etiqueta="Enviados últimos 7 días"
                       valor={resumen.enviados_7_dias} color="text-info" />
            <Indicador etiqueta="Tasa de entrega"
                       valor={`${resumen.tasa_entrega}%`} color="text-exito" />
            <Indicador etiqueta="No entregados"
                       valor={resumen.no_entregados} color="text-error" />
          </div>

          {resumen.canales_activos &&
            !resumen.canales_activos.includes("whatsapp") && (
              <Aviso tono="alerta">
                Ahora mismo los recordatorios salen <strong>solo por correo</strong>.
                WhatsApp está apagado en la configuración mientras no esté el
                trámite con Meta, así que no se encolan mensajes que no se
                podrían enviar. Los clientes sin correo registrado no reciben
                nada.
              </Aviso>
            )}

          {resumen.contactos_no_localizables > 0 && (
            <Aviso tono="alerta">
              {resumen.contactos_no_localizables} contacto(s) marcados como no
              localizables tras varios intentos fallidos. El sistema dejó de
              gastarles mensajes. Conviene depurarlos.
            </Aviso>
          )}
        </>
      )}

      <Panel
        titulo="En cola"
        detalle="Se puede pausar cualquier envío antes de que salga."
        vacio={{
          titulo: "No hay avisos programados en los próximos 30 días",
          detalle:
            "Es normal. A cada vehículo se le avisa solo en cinco momentos de " +
            "su periodo, así que la mayoría de los días no hay nada que mandar. " +
            "Si quieres adelantarte, usa «Revisar a quién le toca».",
        }}
        filas={cola}
        columnas={["SALE", "CLIENTE", "PLACA", "CANAL", "AVISO", "ESTADO", ""]}
        pintar={(r) => (
          <>
            <td className="px-6 py-3 font-semibold whitespace-nowrap">
              {cuando(r.programado_para)}
            </td>
            <td className="px-6 py-3">{r.cliente_nombre}</td>
            <td className="px-6 py-3">
              <Link to={`/vehiculos/${r.vehiculo_id}`}
                    className="font-bold hover:underline">{r.placa}</Link>
            </td>
            <td className={`px-6 py-3 font-semibold ${
              r.canal === "whatsapp" ? "text-exito" : "text-info"}`}>
              {r.canal === "whatsapp" ? "WhatsApp" : "Correo"}
            </td>
            <td className="px-6 py-3 text-neutral-500">
              {AVISOS[r.aviso_clave] || r.aviso_clave}
              {r.ventana && (
                <span className="block text-[11px]">{r.ventana}</span>
              )}
            </td>
            <td className="px-6 py-3">
              <Pastilla texto={ESTADO[r.estado]?.[0] || r.estado}
                        clase={ESTADO[r.estado]?.[1] || ""} />
            </td>
            <td className="px-6 py-3 text-right whitespace-nowrap">
              {puede("editar_contacto") && (
                r.estado === "pausado" ? (
                  <button onClick={() => accion(api.reanudar, r.id)}
                          className="text-xs font-bold text-info hover:underline">
                    Reanudar
                  </button>
                ) : (
                  <>
                    <button onClick={() => accion((id) => api.pausar(id, null), r.id)}
                            className="text-xs font-bold text-info hover:underline">
                      Pausar
                    </button>
                    <button onClick={() => accion(api.cancelar, r.id)}
                            className="ml-3 text-xs font-bold text-error hover:underline">
                      Cancelar
                    </button>
                  </>
                )
              )}
            </td>
          </>
        )}
      />

      <Panel
        titulo="Últimos envíos"
        detalle="En WhatsApp el «leído» solo llega si el cliente tiene activadas las palomitas azules. En correo se mide el clic, no la apertura."
        vacio={{
          titulo: "Todavía no se ha enviado ningún aviso",
          detalle:
            "En cuanto salga el primero aparecerá aquí, con la hora y si llegó. " +
            "Si ya hay avisos en cola y quieres mandarlos de una vez, usa " +
            "«Enviar ahora».",
        }}
        filas={historial}
        columnas={["FECHA", "CLIENTE", "PLACA", "CANAL", "AVISO", "ENTREGA"]}
        pintar={(r) => (
          <>
            <td className="px-6 py-3 font-semibold whitespace-nowrap">
              {cuando(r.enviado_en)}
            </td>
            <td className="px-6 py-3">{r.cliente_nombre}</td>
            <td className="px-6 py-3">
              <Link to={`/vehiculos/${r.vehiculo_id}`}
                    className="font-bold hover:underline">{r.placa}</Link>
            </td>
            <td className={`px-6 py-3 font-semibold ${
              r.canal === "whatsapp" ? "text-exito" : "text-info"}`}>
              {r.canal === "whatsapp" ? "WhatsApp" : "Correo"}
            </td>
            <td className="px-6 py-3 text-neutral-500">
              {AVISOS[r.aviso_clave] || r.aviso_clave}
            </td>
            <td className="px-6 py-3">
              <Pastilla texto={ENTREGA[r.estado_entrega]?.[0] || r.estado_entrega}
                        clase={ENTREGA[r.estado_entrega]?.[1] || ""} />
              {r.motivo_error && (
                <span className="block text-[11px] text-error">
                  {r.motivo_error}
                </span>
              )}
            </td>
          </>
        )}
      />

      {puede("editar_contacto") && (
        <div className="rounded-xl border border-borde bg-white px-5 py-4 text-sm">
          <span className="font-bold text-guinda">Cómo funcionan los botones</span>
          <p className="mt-1 text-neutral-600">
            <strong>Revisar a quién le toca</strong> busca a los clientes con
            fecha próxima y prepara sus avisos, sin mandar nada. Descarta solo
            a quienes ya verificaron.{" "}
            <strong>Enviar ahora</strong> manda los que ya tocaba enviar.
          </p>
          <p className="mt-1 text-neutral-500">
            Puedes usarlos cuando quieras; no se duplican los avisos.
          </p>
        </div>
      )}

      <div className="rounded-xl border border-dorado/45 bg-dorado-claro px-5 py-4 text-sm">
        <span className="font-bold text-dorado">Nota</span>{" "}
        <span className="text-guinda-oscuro">
          WhatsApp no informa quién bloqueó el número. Lo que sí llega es el
          acuse de cada envío, y tras varios fallos seguidos el sistema marca al
          contacto como no localizable y deja de gastarle mensajes.
        </span>
      </div>
    </div>
  );
}

function Panel({ titulo, detalle, filas, columnas, pintar, vacio }) {
  return (
    <section className="tarjeta overflow-hidden">
      <header className="px-6 py-4">
        <h2 className="text-lg font-bold text-guinda">{titulo}</h2>
        <p className="text-xs text-neutral-500">{detalle}</p>
      </header>
      {filas.length === 0 ? (
        <Vacio titulo={vacio.titulo} detalle={vacio.detalle} />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-3xl text-sm">
          <thead className="bg-neutral-50 text-left text-[11px] font-bold text-neutral-500">
            <tr>
              {columnas.map((c, i) => (
                <th key={i} className="px-6 py-3">{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filas.map((f) => (
              <tr key={f.id} className="border-t border-borde">{pintar(f)}</tr>
            ))}
          </tbody>
        </table>
          </div>
      )}
    </section>
  );
}
