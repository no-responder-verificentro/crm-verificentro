import { useState } from "react";

import Aviso from "./Aviso";
import { verificaciones } from "../api/recursos";

const HOY = new Date().toISOString().slice(0, 10);

/**
 * Registra una verificación. Se usa desde la ficha del vehículo y desde la
 * bitácora, por eso vive aparte.
 *
 * Al guardar, el backend calcula el periodo y, si el vehículo tenía cita ese
 * día, la cierra sola. `alGuardar` recibe la respuesta completa, que incluye
 * el vehículo con su estado ya actualizado.
 */
export default function FormularioVerificacion({ vehiculo, alGuardar, alCancelar }) {
  const [f, setF] = useState({
    fecha: HOY,
    hora: "",
    resultado: "aprobado",
    holograma: "2",
    folio: "",
    observaciones: "",
  });
  const [error, setError] = useState(null);
  const [enviando, setEnviando] = useState(false);

  const cambiar = (campo) => (e) => setF({ ...f, [campo]: e.target.value });
  const rechazado = f.resultado === "rechazado";

  async function enviar(evento) {
    evento.preventDefault();
    setError(null);
    setEnviando(true);
    try {
      const respuesta = await verificaciones.registrar({
        vehiculo_id: vehiculo.id,
        fecha: f.fecha,
        hora: f.hora || null,
        resultado: f.resultado,
        // Un rechazo no lleva holograma: el vehículo no pasó.
        holograma: rechazado ? null : f.holograma || null,
        folio_certificado: f.folio || null,
        observaciones: f.observaciones || null,
      });
      alGuardar(respuesta);
    } catch (e) {
      setError(e.message);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <form onSubmit={enviar} className="space-y-4">
      <div className="rounded-xl bg-crema px-4 py-3 text-sm">
        <span className="font-bold">{vehiculo.placa}</span>
        <span className="text-neutral-500">
          {" · "}
          {[vehiculo.marca, vehiculo.linea, vehiculo.modelo_anio]
            .filter(Boolean)
            .join(" ") || "sin datos del vehículo"}
        </span>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block">
          <span className="etiqueta">FECHA</span>
          <input type="date" className="campo" value={f.fecha} max={HOY}
                 onChange={cambiar("fecha")} required />
        </label>
        <label className="block">
          <span className="etiqueta">HORA (OPCIONAL)</span>
          <input type="time" className="campo" value={f.hora}
                 onChange={cambiar("hora")} />
        </label>
      </div>

      <div>
        <span className="etiqueta">RESULTADO</span>
        <div className="flex gap-3">
          {[
            ["aprobado", "Aprobado", "border-exito bg-exito/10 text-exito"],
            ["rechazado", "Rechazado", "border-error bg-error/10 text-error"],
          ].map(([valor, texto, activo]) => (
            <button
              key={valor}
              type="button"
              onClick={() => setF({ ...f, resultado: valor })}
              className={`flex-1 rounded-lg border px-4 py-2.5 text-sm font-bold transition ${
                f.resultado === valor
                  ? activo
                  : "border-borde bg-white text-neutral-500 hover:bg-crema"
              }`}
            >
              {texto}
            </button>
          ))}
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block">
          <span className="etiqueta">HOLOGRAMA</span>
          <select className="campo" value={rechazado ? "" : f.holograma}
                  onChange={cambiar("holograma")} disabled={rechazado}>
            <option value="">Sin holograma</option>
            <option value="00">00</option>
            <option value="0">0</option>
            <option value="1">1</option>
            <option value="2">2</option>
          </select>
        </label>
        <label className="block">
          <span className="etiqueta">FOLIO DEL CERTIFICADO</span>
          <input className="campo" value={f.folio} onChange={cambiar("folio")}
                 placeholder="VC-2026-01284" />
        </label>
      </div>

      {rechazado && (
        <Aviso tono="alerta">
          Un rechazo no cancela los recordatorios: el cliente tiene que volver
          dentro del mismo periodo.
        </Aviso>
      )}

      <label className="block">
        <span className="etiqueta">OBSERVACIONES (OPCIONAL)</span>
        <input className="campo" value={f.observaciones}
               onChange={cambiar("observaciones")} maxLength={255} />
      </label>

      <Aviso>{error}</Aviso>

      <div className="flex gap-3 pt-1">
        <button type="submit" className="boton-principal" disabled={enviando}>
          {enviando ? "Guardando…" : "Registrar verificación"}
        </button>
        <button type="button" className="boton-secundario" onClick={alCancelar}>
          Cancelar
        </button>
      </div>
    </form>
  );
}
