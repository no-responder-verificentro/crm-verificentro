import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import Aviso from "../componentes/Aviso";
import Cargando from "../componentes/Cargando";
import Indicador from "../componentes/Indicador";
import Pastilla from "../componentes/Pastilla";
import Vacio from "../componentes/Vacio";
import { panel } from "../api/recursos";
import { describirEstado } from "../utils/formato";

const FILTROS = [
  ["", "Todos"],
  ["vencido", "Vencidos"],
  ["por_vencer", "Por vencer"],
  ["periodo_abierto", "Periodo abierto"],
  ["al_corriente", "Ya verificaron"],
  ["programado", "Programados"],
];

export default function Dashboard() {
  const [indicadores, setIndicadores] = useState(null);
  const [filas, setFilas] = useState([]);
  const [grafica, setGrafica] = useState([]);
  const [filtro, setFiltro] = useState("");
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);

  const cargar = useCallback(async (estado) => {
    setCargando(true);
    setError(null);
    try {
      const [kpis, seguimiento, serie] = await Promise.all([
        panel.indicadores(),
        panel.seguimiento(estado || undefined),
        panel.grafica(),
      ]);
      setIndicadores(kpis);
      setFilas(seguimiento);
      setGrafica(serie);
    } catch (e) {
      setError(e.message);
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    cargar(filtro);
  }, [filtro, cargar]);

  if (cargando && !indicadores) return <Cargando texto="Cargando el panel…" />;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-3xl font-bold text-guinda-oscuro">Panel de control</h1>
        <p className="mt-1 text-sm text-neutral-500">
          Clave 00002025 · Av. Ruíz Cortines No. 256, Col. Centro
        </p>
      </div>

      <Aviso>{error}</Aviso>

      {indicadores && (
        <>
          <div className="flex flex-wrap gap-4">
            <Indicador etiqueta="Verificados este mes"
                       valor={indicadores.verificados_del_mes}
                       color="text-exito" />
            <Indicador etiqueta="Con periodo abierto"
                       valor={indicadores.periodo_abierto}
                       detalle="les toca ahora mismo" color="text-info" />
            <Indicador etiqueta="Por vencer" valor={indicadores.por_vencer}
                       detalle="quedan 15 días o menos" color="text-alerta" />
            <Indicador etiqueta="Vencidos sin verificar"
                       valor={indicadores.vencidos}
                       detalle="requieren seguimiento" color="text-error" />
          </div>

          {indicadores.sin_forma_de_contacto > 0 && (
            <Aviso tono="alerta">
              Hay {indicadores.sin_forma_de_contacto} vehículo(s) cuyo dueño no
              tiene forma de ser contactado: sin consentimiento, sin datos, o
              dado de baja. A esos el sistema no les puede avisar nada.
            </Aviso>
          )}
        </>
      )}

      {grafica.length > 1 && <Grafica datos={grafica} />}

      <section className="tarjeta overflow-hidden">
        <header className="flex flex-wrap items-center justify-between gap-3 px-6 py-4">
          <div>
            <h2 className="text-lg font-bold text-guinda">
              Seguimiento de clientes
            </h2>
            <p className="text-xs text-neutral-500">
              Ordenados por urgencia: primero los vencidos.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {FILTROS.map(([valor, texto]) => (
              <button
                key={valor}
                onClick={() => setFiltro(valor)}
                className={`rounded-full px-3.5 py-1.5 text-xs font-bold transition ${
                  filtro === valor
                    ? "bg-guinda text-white"
                    : "bg-crema text-neutral-500 hover:bg-neutral-200"
                }`}
              >
                {texto}
              </button>
            ))}
          </div>
        </header>

        {filas.length === 0 ? (
          <Vacio
            titulo="Nada que mostrar con ese filtro"
            detalle="Si el sistema es nuevo, empieza dando de alta clientes desde la sección Clientes."
          />
        ) : (
          <div className="overflow-x-auto">
          <table className="w-full min-w-3xl text-sm">
            <thead className="bg-neutral-50 text-left text-[11px] font-bold text-neutral-500">
              <tr>
                <th className="px-6 py-3">CLIENTE</th>
                <th className="px-6 py-3">PLACA</th>
                <th className="px-6 py-3">DÍGITO</th>
                <th className="px-6 py-3">PERIODO</th>
                <th className="px-6 py-3">RESTANTE</th>
                <th className="px-6 py-3">ESTADO</th>
                <th className="px-6 py-3">ÚLTIMO AVISO</th>
              </tr>
            </thead>
            <tbody>
              {filas.map((f) => {
                const estado = describirEstado(f.estado);
                return (
                  <tr key={f.vehiculo_id} className="border-t border-borde">
                    <td className="px-6 py-3 font-semibold">{f.cliente}</td>
                    <td className="px-6 py-3">
                      <Link to={`/vehiculos/${f.vehiculo_id}`}
                            className="font-bold hover:underline">
                        {f.placa}
                      </Link>
                    </td>
                    <td className="px-6 py-3 font-bold text-guinda">
                      {f.ultimo_digito}
                    </td>
                    <td className="px-6 py-3 text-neutral-500">
                      {f.ventana || "—"}
                    </td>
                    <td className="px-6 py-3 font-semibold whitespace-nowrap">
                      {restante(f)}
                    </td>
                    <td className="px-6 py-3">
                      <Pastilla texto={estado.texto} clase={estado.clase} />
                    </td>
                    <td className="px-6 py-3 text-xs text-neutral-500">
                      {f.se_le_puede_escribir ? (
                        f.ultimo_aviso || "sin enviar"
                      ) : (
                        <span className="font-bold text-error">
                          no se le puede escribir
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          </div>
        )}
      </section>
    </div>
  );
}

function restante(fila) {
  const d = fila.dias_restantes;
  if (d === null || d === undefined) return "—";
  if (fila.estado === "al_corriente") return "—";
  if (fila.estado === "vencido") return `venció hace ${Math.abs(d)} d`;
  if (d < 0) return `abre en ${Math.abs(d)} d`;
  return `${d} días`;
}

/** Gráfica de barras en HTML: no hace falta una librería para esto. */
function Grafica({ datos }) {
  const maximo = Math.max(...datos.map((d) => d.verificaciones), 1);
  return (
    <section className="tarjeta p-6">
      <h2 className="text-lg font-bold text-guinda">Verificaciones por mes</h2>
      <p className="mb-5 text-xs text-neutral-500">Solo las aprobadas.</p>
      <div className="flex h-48 items-end gap-3">
        {datos.map((d, i) => (
          <div key={d.mes} className="flex flex-1 flex-col items-center gap-2">
            <span className="text-[11px] font-bold text-neutral-500">
              {d.verificaciones}
            </span>
            <div
              className={`w-full rounded-t-md ${
                i === datos.length - 1 ? "bg-dorado" : "bg-guinda"
              }`}
              style={{
                height: `${Math.max((d.verificaciones / maximo) * 100, 2)}%`,
              }}
            />
            <span className="text-[11px] font-semibold">{d.mes}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
