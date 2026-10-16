import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import Aviso from "../componentes/Aviso";
import Cargando from "../componentes/Cargando";
import Indicador from "../componentes/Indicador";
import Modal from "../componentes/Modal";
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

/** Concuerda el verbo con la cantidad. «Se prepararon 1 avisos» se lee mal
 *  y es lo primero que nota quien usa el sistema todos los días. */
function cuantos(n, singular, plural) {
  return n === 1 ? singular : plural;
}

export default function Recordatorios() {
  const { puede } = useSesion();

  const [resumen, setResumen] = useState(null);
  const [config, setConfig] = useState(null);
  const [cola, setCola] = useState([]);
  const [historial, setHistorial] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  // El resultado de «Revisar a quién le toca» y «Enviar ahora». Faltaba
  // declararlo: las dos funciones llamaban a setAviso y el botón tronaba con
  // «setAviso is not defined» DESPUÉS de haber hecho el trabajo en el
  // servidor, así que el aviso se veía como un fallo que no era.
  const [aviso, setAviso] = useState(null);

  const cargar = useCallback(async () => {
    setError(null);
    try {
      const [r, c, h, cfg] = await Promise.all([
        api.resumen(),
        api.cola(24 * 30),
        api.historial(50),
        api.configuracion(),
      ]);
      setResumen(r);
      setCola(c);
      setHistorial(h);
      setConfig(cfg);
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
  const [probando, setProbando] = useState(false);

  async function revisar() {
    setError(null);
    setAviso(null);
    setTrabajando("revisar");
    try {
      const r = await api.generar(90);
      const cancelados = r.cancelados
        ? ` Se ${cuantos(r.cancelados, "canceló", "cancelaron")} ` +
          `${r.cancelados} de clientes que ya verificaron.`
        : "";
      setAviso(
        r.creados > 0
          ? `Se ${cuantos(r.creados, "preparó", "prepararon")} ${r.creados} ` +
            `${cuantos(r.creados, "aviso nuevo", "avisos nuevos")}.` + cancelados
          : "Revisado. No hay avisos nuevos por preparar: nadie cumple fecha " +
            "en los próximos 90 días." + cancelados
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
    setAviso(null);
    setTrabajando("enviar");
    try {
      const r = await api.enviar();
      setAviso(
        r.enviados > 0
          ? `Se ${cuantos(r.enviados, "envió", "enviaron")} ${r.enviados} ` +
            `${cuantos(r.enviados, "aviso", "avisos")}.` +
            (r.fallidos
              ? ` ${r.fallidos} no se ${cuantos(r.fallidos, "pudo", "pudieron")} entregar.`
              : "")
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
          <h1 className="text-2xl font-bold text-guinda-oscuro sm:text-3xl">Recordatorios</h1>
          <p className="mt-1 max-w-2xl text-sm text-neutral-500">
            Lo que está por salir y lo que ya salió. Se cancela solo si el
            cliente verifica antes.
          </p>
        </div>

        {puede("editar_contacto") && (
          <div className="flex w-full gap-3 sm:w-auto sm:shrink-0">
            <button onClick={revisar} className="boton-secundario flex-1 sm:flex-none"
                    disabled={Boolean(trabajando)}>
              {trabajando === "revisar" ? "Revisando…" : "Revisar a quién le toca"}
            </button>
            <button onClick={enviarAhora} className="boton-principal flex-1 sm:flex-none"
                    disabled={Boolean(trabajando)}>
              {trabajando === "enviar" ? "Enviando…" : "Enviar ahora"}
            </button>
          </div>
        )}
      </div>

      {puede("editar_contacto") && (
        <div>
          <button
            onClick={() => setProbando(true)}
            className="text-sm font-semibold text-info hover:underline"
          >
            Enviar un correo de prueba
          </button>
        </div>
      )}

      {aviso && <Aviso tono="exito">{aviso}</Aviso>}
      <Aviso>{error}</Aviso>

      {config && !config.manda_de_verdad && <ModoPrueba config={config} />}

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
            <td data-etiqueta="SALE" className="px-6 py-3 font-semibold whitespace-nowrap">
              {cuando(r.programado_para)}
            </td>
            <td className="celda-titulo px-6 py-3">{r.cliente_nombre}</td>
            <td data-etiqueta="PLACA" className="px-6 py-3">
              <Link to={`/vehiculos/${r.vehiculo_id}`}
                    className="font-bold hover:underline">{r.placa}</Link>
            </td>
            <td data-etiqueta="CANAL" className={`px-6 py-3 font-semibold ${
              r.canal === "whatsapp" ? "text-exito" : "text-info"}`}>
              {r.canal === "whatsapp" ? "WhatsApp" : "Correo"}
            </td>
            <td data-etiqueta="AVISO" className="px-6 py-3 text-neutral-500">
              {AVISOS[r.aviso_clave] || r.aviso_clave}
              {r.ventana && (
                <span className="block text-[11px]">{r.ventana}</span>
              )}
            </td>
            <td data-etiqueta="ESTADO" className="px-6 py-3">
              <Pastilla texto={ESTADO[r.estado]?.[0] || r.estado}
                        clase={ESTADO[r.estado]?.[1] || ""} />
            </td>
            <td className="celda-acciones px-6 py-3 text-right whitespace-nowrap">
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
        columnas={["FECHA", "CLIENTE", "PLACA", "CANAL", "AVISO", "ENTREGA", ""]}
        pintar={(r) => (
          <>
            <td data-etiqueta="FECHA" className="px-6 py-3 font-semibold whitespace-nowrap">
              {cuando(r.enviado_en)}
            </td>
            <td className="celda-titulo px-6 py-3">{r.cliente_nombre}</td>
            <td data-etiqueta="PLACA" className="px-6 py-3">
              <Link to={`/vehiculos/${r.vehiculo_id}`}
                    className="font-bold hover:underline">{r.placa}</Link>
            </td>
            <td data-etiqueta="CANAL" className={`px-6 py-3 font-semibold ${
              r.canal === "whatsapp" ? "text-exito" : "text-info"}`}>
              {r.canal === "whatsapp" ? "WhatsApp" : "Correo"}
            </td>
            <td data-etiqueta="AVISO" className="px-6 py-3 text-neutral-500">
              {AVISOS[r.aviso_clave] || r.aviso_clave}
            </td>
            <td data-etiqueta="ENTREGA" className="px-6 py-3">
              <Pastilla texto={ENTREGA[r.estado_entrega]?.[0] || r.estado_entrega}
                        clase={ENTREGA[r.estado_entrega]?.[1] || ""} />
              {r.motivo_error && (
                <span className="block text-[11px] text-error">
                  {r.motivo_error}
                </span>
              )}
            </td>
            <td className="celda-acciones px-6 py-3 text-right whitespace-nowrap">
              {puede("editar_contacto") && r.estado === "error" && (
                <button
                  onClick={() => accion(api.reintentar, r.id)}
                  title="Lo devuelve a la cola para que salga con «Enviar ahora»"
                  className="text-xs font-bold text-info hover:underline"
                >
                  Reintentar
                </button>
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
          <p className="mt-2 text-neutral-600">
            <strong>Reintentar</strong>, en los que salieron mal, los devuelve
            a la cola. Después hay que darle a <strong>Enviar ahora</strong>
            para que salgan.
          </p>
        </div>
      )}

      {probando && <VentanaDePrueba onCerrar={() => setProbando(false)} />}

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

/**
 * Ventana para mandar un aviso de ejemplo a donde se le diga.
 *
 * Existe para no tener que abrir una terminal. Comprobar que el correo sale
 * es algo que hace quien administra el verificentro, no quien programó el
 * sistema, y en una demostración un PowerShell abierto se ve mal.
 *
 * Manda un aviso real —con su formato, su botón y su pie—, no un «hola
 * mundo»: lo que se quiere enseñar es lo que recibe el cliente.
 */
function VentanaDePrueba({ onCerrar }) {
  const [correo, setCorreo] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [resultado, setResultado] = useState(null);

  async function enviar(evento) {
    evento.preventDefault();
    setEnviando(true);
    setResultado(null);
    try {
      setResultado(await api.probar(correo.trim()));
    } catch (e) {
      setResultado({ enviado: false, detalle: e.message });
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Modal
      titulo="Enviar un correo de prueba"
      descripcion="Manda un aviso de ejemplo, igual al que recibe un cliente. No afecta la cola ni la bitácora."
      onCerrar={onCerrar}
    >
      <form onSubmit={enviar} className="space-y-4">
        <label className="block">
          <span className="etiqueta">CORREO DE DESTINO</span>
          <input
            type="email"
            className="campo"
            value={correo}
            onChange={(e) => setCorreo(e.target.value)}
            placeholder="tu.correo@ejemplo.com"
            required
            autoFocus
          />
        </label>

        {resultado && (
          <Aviso tono={resultado.enviado ? "exito" : "error"}>
            {resultado.detalle}
          </Aviso>
        )}

        <div className="flex flex-col gap-3 sm:flex-row">
          <button type="submit" className="boton-principal"
                  disabled={enviando || !correo.trim()}>
            {enviando ? "Enviando…" : "Enviar prueba"}
          </button>
          <button type="button" className="boton-secundario" onClick={onCerrar}>
            Cerrar
          </button>
        </div>
      </form>
    </Modal>
  );
}

/**
 * Letrero de modo prueba.
 *
 * Existe por un día entero perdido: con PROVEEDOR_CORREO=consola el sistema
 * escribe los correos en la bitácora del servidor y reporta el envío como
 * exitoso. En esta pantalla se veía idéntico a un envío real —acuse en
 * «Enviado» y todo— mientras en la bandeja del cliente no llegaba nada, ni a
 * spam. Desde afuera era imposible de distinguir, y ese es justo el tipo de
 * falla que no debe ser silenciosa.
 */
function ModoPrueba({ config }) {
  return (
    <div className="rounded-xl border border-alerta/45 bg-alerta/10 px-5 py-4">
      <p className="text-sm font-bold text-alerta">
        Los avisos no están saliendo de verdad
      </p>
      <p className="mt-1 text-sm text-guinda-oscuro">{config.motivo}</p>
      <p className="mt-2 text-xs text-neutral-600">
        Mientras siga así, los acuses de abajo dicen «Enviado» pero nadie
        recibe nada. Se corrige con las variables del servidor; el paso a paso
        está en <strong>CONECTAR_CORREO.md</strong>.
      </p>
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
          <table className="tabla-responsiva w-full min-w-3xl text-sm">
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
