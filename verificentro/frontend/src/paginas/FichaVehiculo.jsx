import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import Aviso from "../componentes/Aviso";
import Cargando from "../componentes/Cargando";
import FormularioVerificacion from "../componentes/FormularioVerificacion";
import Modal from "../componentes/Modal";
import Pastilla from "../componentes/Pastilla";
import Vacio from "../componentes/Vacio";
import { clientes, vehiculos as apiVehiculos } from "../api/recursos";
import { useSesion } from "../contexto/Sesion";
import {
  describirEstado,
  fechaLegible,
  telefonoLegible,
  tiempoRestante,
} from "../utils/formato";

export default function FichaVehiculo() {
  const { id } = useParams();
  const { puede } = useSesion();

  const [vehiculo, setVehiculo] = useState(null);
  const [cliente, setCliente] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [ventana, setVentana] = useState(null);   // 'verificar' | 'placa'
  const [aviso, setAviso] = useState(null);

  const cargar = useCallback(async () => {
    setCargando(true);
    setError(null);
    try {
      const v = await apiVehiculos.detalle(id);
      setVehiculo(v);
      // El detalle trae cliente_id pero no su nombre ni su teléfono.
      setCliente(await clientes.ficha(v.cliente_id));
    } catch (e) {
      setError(e.message);
    } finally {
      setCargando(false);
    }
  }, [id]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  if (cargando) return <Cargando texto="Cargando la ficha…" />;
  if (error) return <Aviso>{error}</Aviso>;
  if (!vehiculo) return null;

  const estado = describirEstado(vehiculo.estado);
  const descripcion = [vehiculo.marca, vehiculo.linea, vehiculo.modelo_anio]
    .filter(Boolean)
    .join(" ");

  return (
    <div className="max-w-5xl space-y-5">
      <div>
        <Link to="/clientes" className="text-xs font-semibold text-info hover:underline">
          ← Volver a clientes
        </Link>
        <h1 className="mt-2 text-3xl font-bold text-guinda-oscuro">
          {cliente?.nombre}
        </h1>
        <p className="mt-1 text-sm text-neutral-500">
          {descripcion || "Sin datos del vehículo"} · Placa {vehiculo.placa} ·{" "}
          {telefonoLegible(cliente?.telefono_e164)}
        </p>
      </div>

      {aviso && <Aviso tono="exito">{aviso}</Aviso>}

      <EstadoDelPeriodo
        vehiculo={vehiculo}
        estado={estado}
        puedeCapturar={puede("capturar")}
        alVerificar={() => setVentana("verificar")}
        alCambiarPlaca={() => setVentana("placa")}
      />

      <section className="tarjeta overflow-hidden">
        <header className="px-6 py-4">
          <h2 className="text-lg font-bold text-guinda">
            Historial de verificaciones
          </h2>
          <p className="text-xs text-neutral-500">
            Solo las aprobadas cuentan como cumplimiento. Un rechazo obliga a
            volver dentro del mismo periodo.
          </p>
        </header>

        {vehiculo.verificaciones.length === 0 ? (
          <Vacio
            titulo="Todavía no ha verificado con ustedes"
            detalle="En cuanto se registre la primera, aparecerá aquí y el vehículo dejará de recibir recordatorios de ese periodo."
          />
        ) : (
          <div className="overflow-x-auto">
          <table className="w-full min-w-3xl text-sm">
            <thead className="bg-neutral-50 text-left text-[11px] font-bold text-neutral-500">
              <tr>
                <th className="px-6 py-3">FECHA</th>
                <th className="px-6 py-3">RESULTADO</th>
                <th className="px-6 py-3">HOLOGRAMA</th>
                <th className="px-6 py-3">FOLIO</th>
              </tr>
            </thead>
            <tbody>
              {vehiculo.verificaciones.map((v) => (
                <tr key={v.id} className="border-t border-borde">
                  <td className="px-6 py-3 font-semibold">
                    {fechaLegible(v.fecha)}
                  </td>
                  <td className="px-6 py-3">
                    <Pastilla
                      texto={v.resultado === "aprobado" ? "Aprobado" : "Rechazado"}
                      clase={
                        v.resultado === "aprobado"
                          ? "bg-exito/15 text-exito"
                          : "bg-error/15 text-error"
                      }
                    />
                  </td>
                  <td className="px-6 py-3">{v.holograma || "—"}</td>
                  <td className="px-6 py-3 text-neutral-500">
                    {v.folio_certificado || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}
      </section>

      <DatosDelVehiculo vehiculo={vehiculo} />

      {ventana === "verificar" && (
        <Modal
          titulo="Registrar verificación"
          descripcion="Al guardarla, el vehículo queda al corriente y deja de recibir avisos de este periodo."
          onCerrar={() => setVentana(null)}
        >
          <FormularioVerificacion
            vehiculo={vehiculo}
            alCancelar={() => setVentana(null)}
            alGuardar={(respuesta) => {
              setVentana(null);
              setAviso(
                respuesta.resultado === "aprobado"
                  ? "Verificación registrada. El vehículo quedó al corriente."
                  : "Verificación rechazada registrada. Los recordatorios siguen activos."
              );
              cargar();
            }}
          />
        </Modal>
      )}

      {ventana === "placa" && (
        <Modal
          titulo="Cambio de placa"
          descripcion="La placa anterior se conserva en el historial. Ojo: al cambiar puede cambiarle el periodo que le toca."
          onCerrar={() => setVentana(null)}
        >
          <FormularioCambioDePlaca
            vehiculo={vehiculo}
            alCancelar={() => setVentana(null)}
            alGuardar={(nuevo) => {
              setVentana(null);
              setAviso(
                `Placa actualizada a ${nuevo.placa}. Ahora le toca en ${
                  nuevo.ventana?.etiqueta || "su nuevo periodo"
                }.`
              );
              cargar();
            }}
          />
        </Modal>
      )}
    </div>
  );
}

function EstadoDelPeriodo({ vehiculo, estado, puedeCapturar, alVerificar, alCambiarPlaca }) {
  return (
    <section className="tarjeta flex flex-wrap items-center justify-between gap-4 bg-guinda-oscuro p-6">
      <div>
        <p className="text-[11px] font-bold tracking-wide text-dorado">
          {vehiculo.ventana
            ? `PERIODO ${vehiculo.ventana.etiqueta.toUpperCase()}`
            : "SIN CALENDARIO"}
        </p>
        <p className="mt-1 text-2xl font-bold text-white">
          {vehiculo.estado
            ? `${estado.texto} · ${tiempoRestante(vehiculo)}`
            : "Fuera del programa estatal"}
        </p>
        <p className="mt-1 text-sm text-white/80">
          {vehiculo.ventana
            ? `Cierra el ${fechaLegible(vehiculo.ventana.fin)}`
            : vehiculo.ultimo_digito === null
              ? "La placa no contiene ningún número, así que no se puede calcular el periodo."
              : `Placa de ${vehiculo.entidad_placa}: no le aplica el calendario de Veracruz.`}
        </p>
      </div>

      {puedeCapturar && (
        <div className="flex gap-3">
          <button onClick={alVerificar}
                  className="rounded-lg bg-dorado px-5 py-2.5 text-sm font-bold text-white transition hover:brightness-110">
            Registrar verificación
          </button>
          <button onClick={alCambiarPlaca}
                  className="rounded-lg border border-white/30 px-5 py-2.5 text-sm font-bold text-white transition hover:bg-white/10">
            Cambio de placa
          </button>
        </div>
      )}
    </section>
  );
}

function DatosDelVehiculo({ vehiculo }) {
  const campos = [
    ["Número de serie (NIV)", vehiculo.niv],
    ["Placa", vehiculo.placa],
    ["Último dígito", vehiculo.ultimo_digito ?? "sin dígito"],
    ["Entidad", vehiculo.entidad_placa],
    ["Marca", vehiculo.marca],
    ["Línea", vehiculo.linea],
    ["Modelo", vehiculo.modelo_anio],
    ["Color", vehiculo.color],
    ["Combustible", vehiculo.combustible],
  ];
  return (
    <section className="tarjeta p-6">
      <h2 className="mb-4 text-lg font-bold text-guinda">Datos del vehículo</h2>
      <dl className="grid gap-x-8 gap-y-3 sm:grid-cols-3">
        {campos.map(([etiqueta, valor]) => (
          <div key={etiqueta}>
            <dt className="text-[11px] font-bold text-neutral-500">
              {etiqueta.toUpperCase()}
            </dt>
            <dd className="text-sm">{valor || "—"}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function FormularioCambioDePlaca({ vehiculo, alGuardar, alCancelar }) {
  const [placa, setPlaca] = useState("");
  const [desde, setDesde] = useState(new Date().toISOString().slice(0, 10));
  const [motivo, setMotivo] = useState("reemplazo");
  const [error, setError] = useState(null);
  const [enviando, setEnviando] = useState(false);

  async function enviar(evento) {
    evento.preventDefault();
    setError(null);
    setEnviando(true);
    try {
      alGuardar(
        await apiVehiculos.cambiarPlaca(vehiculo.id, {
          placa_nueva: placa,
          vigente_desde: desde,
          motivo,
        })
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <form onSubmit={enviar} className="space-y-4">
      <div className="rounded-xl bg-crema px-4 py-3 text-sm">
        Placa actual: <span className="font-bold">{vehiculo.placa}</span>
      </div>

      <label className="block">
        <span className="etiqueta">PLACA NUEVA</span>
        <input className="campo uppercase" value={placa}
               onChange={(e) => setPlaca(e.target.value)}
               placeholder="YUN-047-A" required minLength={4} />
      </label>

      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block">
          <span className="etiqueta">VIGENTE DESDE</span>
          <input type="date" className="campo" value={desde}
                 onChange={(e) => setDesde(e.target.value)} required />
        </label>
        <label className="block">
          <span className="etiqueta">MOTIVO</span>
          <select className="campo" value={motivo}
                  onChange={(e) => setMotivo(e.target.value)}>
            <option value="reemplazo">Reemplazo de placa</option>
            <option value="cambio_entidad">Cambio de entidad</option>
            <option value="correccion">Corrección de captura</option>
          </select>
        </label>
      </div>

      <Aviso>{error}</Aviso>

      <div className="flex gap-3 pt-1">
        <button type="submit" className="boton-principal" disabled={enviando}>
          {enviando ? "Guardando…" : "Cambiar placa"}
        </button>
        <button type="button" className="boton-secundario" onClick={alCancelar}>
          Cancelar
        </button>
      </div>
    </form>
  );
}
