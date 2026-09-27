import { useCallback, useEffect, useState } from "react";

import Aviso from "../componentes/Aviso";
import Cargando from "../componentes/Cargando";
import { api } from "../api/cliente";
import { reportes } from "../api/recursos";

const ANIO = new Date().getFullYear();

export default function Reportes() {
  const [anio, setAnio] = useState(ANIO);
  const [datos, setDatos] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);

  const cargar = useCallback(async (a) => {
    setCargando(true);
    setError(null);
    try {
      const [efectividad, cumplimiento, canales, meses] = await Promise.all([
        reportes.efectividad(a),
        reportes.cumplimiento(a),
        reportes.canales(),
        reportes.porMes(12),
      ]);
      setDatos({ efectividad, cumplimiento, canales, meses });
    } catch (e) {
      setError(e.message);
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    cargar(anio);
  }, [anio, cargar]);

  if (cargando && !datos) return <Cargando texto="Calculando reportes…" />;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-guinda-oscuro">Reportes</h1>
          <p className="mt-1 text-sm text-neutral-500">
            Los números para decidir. Solo se cuentan los periodos que ya
            cerraron.
          </p>
        </div>
        <div className="flex items-end gap-3">
          <label className="block">
            <span className="etiqueta">AÑO</span>
            <select className="campo" value={anio}
                    onChange={(e) => setAnio(Number(e.target.value))}>
              {[ANIO, ANIO - 1, ANIO - 2].map((a) => (
                <option key={a} value={a}>{a}</option>
              ))}
            </select>
          </label>
          <BotonExportar anio={anio} />
        </div>
      </div>

      <Aviso>{error}</Aviso>

      {datos && (
        <>
          <Efectividad datos={datos.efectividad} />
          <div className="grid gap-5 lg:grid-cols-2">
            <Cumplimiento filas={datos.cumplimiento} />
            <Canales filas={datos.canales} />
          </div>
          {datos.meses.length > 1 && <PorMes datos={datos.meses} />}
        </>
      )}
    </div>
  );
}

// Por debajo de esto, la diferencia entre los dos grupos es ruido. Con 10
// casos, que uno verifique o no mueve el porcentaje diez puntos.
const MUESTRA_MINIMA = 30;

function Efectividad({ datos }) {
  const sinDatos = datos.con_aviso_total === 0 && datos.sin_aviso_total === 0;
  const muestraChica =
    !sinDatos &&
    (datos.con_aviso_total < MUESTRA_MINIMA ||
      datos.sin_aviso_total < MUESTRA_MINIMA);

  return (
    <section className="tarjeta space-y-4 bg-guinda-oscuro p-7">
      <div>
        <h2 className="text-2xl font-bold text-white">
          ¿Sirve mandar recordatorios?
        </h2>
        <p className="mt-1 text-sm text-white/70">
          De los periodos ya cerrados de {datos.anio}: cuántos regresaron a
          verificar dentro de su plazo.
        </p>
      </div>

      {sinDatos ? (
        <p className="rounded-xl bg-white/10 px-5 py-6 text-center text-sm text-white/80">
          Todavía no hay periodos cerrados este año con datos suficientes.
          Este número empieza a tener sentido después del primer ciclo completo
          de avisos.
        </p>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <Caja
              etiqueta="SÍ recibieron recordatorio"
              valor={`${datos.con_aviso_porcentaje}%`}
              detalle={`${datos.con_aviso_verificaron} de ${datos.con_aviso_total} regresaron a tiempo`}
              color="text-exito"
            />
            <Caja
              etiqueta="NO recibieron recordatorio"
              valor={`${datos.sin_aviso_porcentaje}%`}
              detalle={`${datos.sin_aviso_verificaron} de ${datos.sin_aviso_total} regresaron a tiempo`}
              color="text-dorado"
            />
            <Caja
              etiqueta="Diferencia"
              valor={`${datos.diferencia_puntos > 0 ? "+" : ""}${datos.diferencia_puntos} pts`}
              detalle={`equivale a ${datos.verificaciones_atribuibles} verificaciones más`}
              color="text-white"
            />
          </div>

          {muestraChica && (
            <p className="rounded-xl border border-dorado/50 bg-dorado/20 px-5 py-3
                          text-xs leading-relaxed text-white">
              <span className="font-bold">Muestra insuficiente.</span> Con{" "}
              {datos.con_aviso_total} y {datos.sin_aviso_total} casos, estos
              porcentajes todavía no dicen nada: un solo cliente mueve el
              resultado varios puntos. El número empieza a ser confiable
              después de un ciclo completo de avisos, con al menos{" "}
              {MUESTRA_MINIMA} casos de cada lado.
            </p>
          )}

          <p className="rounded-xl bg-white/10 px-5 py-3 text-xs leading-relaxed text-white/80">
            <span className="font-bold">Cómo leerlo.</span> No es un experimento
            controlado: quien no recibió aviso suele ser quien no dejó
            consentimiento o tiene los datos mal, y esa gente probablemente ya
            era distinta de entrada. La diferencia es una señal útil, no una
            medición limpia de causa y efecto.
          </p>
        </>
      )}
    </section>
  );
}

function Caja({ etiqueta, valor, detalle, color }) {
  return (
    <div className="rounded-xl bg-white/10 px-5 py-4">
      <p className="text-[11px] font-bold text-dorado">{etiqueta}</p>
      <p className={`mt-1 text-4xl font-bold ${color}`}>{valor}</p>
      <p className="mt-1 text-xs text-white/80">{detalle}</p>
    </div>
  );
}

function Cumplimiento({ filas }) {
  return (
    <section className="tarjeta overflow-hidden">
      <header className="px-6 py-4">
        <h2 className="text-lg font-bold text-guinda">
          Cumplimiento por último dígito
        </h2>
        <p className="text-xs text-neutral-500">
          Cuántos del padrón verificaron dentro de su periodo.
        </p>
      </header>
      <table className="w-full text-sm">
        <thead className="bg-neutral-50 text-left text-[11px] font-bold text-neutral-500">
          <tr>
            <th className="px-6 py-3">DÍGITOS</th>
            <th className="px-6 py-3">PADRÓN</th>
            <th className="px-6 py-3">VERIFICARON</th>
            <th className="px-6 py-3">%</th>
          </tr>
        </thead>
        <tbody>
          {filas.map((f) => (
            <tr key={f.digitos} className="border-t border-borde">
              <td className="px-6 py-3 font-bold text-guinda">{f.digitos}</td>
              <td className="px-6 py-3 text-neutral-500">{f.padron}</td>
              <td className="px-6 py-3 font-semibold">{f.verificaron}</td>
              <td className="px-6 py-3">
                <div className="flex items-center gap-3">
                  <div className="h-2 w-24 overflow-hidden rounded-full bg-neutral-200">
                    <div
                      className={`h-full rounded-full ${
                        f.porcentaje >= 75 ? "bg-exito"
                          : f.porcentaje >= 60 ? "bg-alerta" : "bg-error"
                      }`}
                      style={{ width: `${f.porcentaje}%` }}
                    />
                  </div>
                  <span className="font-bold">{f.porcentaje}%</span>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function Canales({ filas }) {
  return (
    <section className="tarjeta overflow-hidden">
      <header className="px-6 py-4">
        <h2 className="text-lg font-bold text-guinda">Entrega por canal</h2>
        <p className="text-xs text-neutral-500">
          Si un canal baja mucho, conviene depurar esos contactos.
        </p>
      </header>
      <table className="w-full text-sm">
        <thead className="bg-neutral-50 text-left text-[11px] font-bold text-neutral-500">
          <tr>
            <th className="px-6 py-3">CANAL</th>
            <th className="px-6 py-3">ENVIADOS</th>
            <th className="px-6 py-3">ENTREGADOS</th>
            <th className="px-6 py-3">FALLIDOS</th>
            <th className="px-6 py-3">TASA</th>
          </tr>
        </thead>
        <tbody>
          {filas.map((f) => (
            <tr key={f.canal} className="border-t border-borde">
              <td className={`px-6 py-3 font-semibold ${
                f.canal === "whatsapp" ? "text-exito" : "text-info"}`}>
                {f.canal === "whatsapp" ? "WhatsApp" : "Correo"}
              </td>
              <td className="px-6 py-3">{f.enviados}</td>
              <td className="px-6 py-3">{f.entregados}</td>
              <td className={`px-6 py-3 ${f.fallidos ? "font-bold text-error" : ""}`}>
                {f.fallidos}
              </td>
              <td className="px-6 py-3 font-bold">{f.tasa_entrega}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function PorMes({ datos }) {
  const maximo = Math.max(...datos.map((d) => d.verificaciones), 1);
  return (
    <section className="tarjeta p-6">
      <h2 className="text-lg font-bold text-guinda">Verificaciones por mes</h2>
      <p className="mb-5 text-xs text-neutral-500">Solo las aprobadas.</p>
      <div className="flex h-52 items-end gap-2">
        {datos.map((d, i) => (
          <div key={d.mes} className="flex flex-1 flex-col items-center gap-2">
            <span className="text-[11px] font-bold text-neutral-500">
              {d.verificaciones}
            </span>
            <div
              className={`w-full rounded-t-md ${
                i === datos.length - 1 ? "bg-dorado" : "bg-guinda"}`}
              style={{ height: `${Math.max((d.verificaciones / maximo) * 100, 2)}%` }}
            />
            <span className="text-[10px] font-semibold">{d.mes}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function BotonExportar({ anio }) {
  const [bajando, setBajando] = useState(false);

  async function exportar() {
    setBajando(true);
    try {
      // No se puede usar un <a href> normal: el endpoint pide el token en la
      // cabecera, así que se descarga con fetch y se arma el archivo aquí.
      const texto = await api.descargar(`/reportes/exportar?anio=${anio}`);
      const url = URL.createObjectURL(
        new Blob([texto], { type: "text/csv;charset=utf-8" })
      );
      const enlace = document.createElement("a");
      enlace.href = url;
      enlace.download = `verificaciones-${anio}.csv`;
      enlace.click();
      URL.revokeObjectURL(url);
    } finally {
      setBajando(false);
    }
  }

  return (
    <button onClick={exportar} className="boton-principal" disabled={bajando}>
      {bajando ? "Preparando…" : "Exportar a Excel"}
    </button>
  );
}
