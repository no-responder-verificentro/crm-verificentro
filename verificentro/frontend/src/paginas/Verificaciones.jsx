import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import Aviso from "../componentes/Aviso";
import Cargando from "../componentes/Cargando";
import Indicador from "../componentes/Indicador";
import Pastilla from "../componentes/Pastilla";
import Vacio from "../componentes/Vacio";
import { verificaciones as api } from "../api/recursos";
import { fechaLegible } from "../utils/formato";

/** Fecha de hace N días, en formato ISO. */
function haceDias(n) {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 10);
}

const HOY = new Date().toISOString().slice(0, 10);

export default function Verificaciones() {
  const [filtros, setFiltros] = useState({
    desde: haceDias(30),
    hasta: HOY,
    resultado: "",
    buscar: "",
  });
  const [lista, setLista] = useState([]);
  const [resumen, setResumen] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);

  const peticion = useRef(0);

  const consultar = useCallback(async (f) => {
    const mia = ++peticion.current;
    setCargando(true);
    setError(null);
    try {
      const [filas, totales] = await Promise.all([
        api.listar({ ...f, resultado: f.resultado || undefined }),
        api.resumen({ desde: f.desde, hasta: f.hasta }),
      ]);
      if (mia !== peticion.current) return;
      setLista(filas);
      setResumen(totales);
    } catch (e) {
      if (mia === peticion.current) setError(e.message);
    } finally {
      if (mia === peticion.current) setCargando(false);
    }
  }, []);

  useEffect(() => {
    const t = setTimeout(() => consultar(filtros), 300);
    return () => clearTimeout(t);
  }, [filtros, consultar]);

  const cambiar = (campo) => (e) =>
    setFiltros({ ...filtros, [campo]: e.target.value });

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-3xl font-bold text-guinda-oscuro">Verificaciones</h1>
        <p className="mt-1 text-sm text-neutral-500">
          Bitácora de todo lo que ha pasado por el centro. Cada registro aprobado
          deja al vehículo al corriente y detiene sus recordatorios.
        </p>
      </div>

      {resumen && (
        <div className="flex flex-wrap gap-4">
          <Indicador etiqueta="Total del periodo" valor={resumen.total} />
          <Indicador etiqueta="Aprobadas" valor={resumen.aprobadas}
                     color="text-exito" />
          <Indicador etiqueta="Rechazadas" valor={resumen.rechazadas}
                     color="text-error" />
          <Indicador etiqueta="Índice de rechazo"
                     valor={`${resumen.indice_rechazo}%`} color="text-alerta" />
          <Indicador etiqueta="Fuera de su periodo"
                     valor={resumen.fuera_de_periodo} color="text-neutral-600"
                     detalle="verificaron en un mes que no les tocaba" />
        </div>
      )}

      <div className="flex flex-wrap items-end gap-3">
        <label className="block">
          <span className="etiqueta">DESDE</span>
          <input type="date" className="campo" value={filtros.desde}
                 onChange={cambiar("desde")} />
        </label>
        <label className="block">
          <span className="etiqueta">HASTA</span>
          <input type="date" className="campo" value={filtros.hasta}
                 onChange={cambiar("hasta")} />
        </label>
        <label className="block">
          <span className="etiqueta">RESULTADO</span>
          <select className="campo" value={filtros.resultado}
                  onChange={cambiar("resultado")}>
            <option value="">Todos</option>
            <option value="aprobado">Aprobadas</option>
            <option value="rechazado">Rechazadas</option>
          </select>
        </label>
        <label className="block min-w-64 flex-1">
          <span className="etiqueta">BUSCAR</span>
          <input className="campo" value={filtros.buscar}
                 onChange={cambiar("buscar")}
                 placeholder="Placa, cliente o folio…" />
        </label>
      </div>

      <Aviso>{error}</Aviso>

      {cargando && lista.length === 0 ? (
        <Cargando />
      ) : lista.length === 0 ? (
        <div className="tarjeta">
          <Vacio
            titulo="No hay verificaciones en ese rango"
            detalle="Prueba con otras fechas o quita los filtros."
          />
        </div>
      ) : (
        <div className="tarjeta overflow-x-auto">
          <table className="w-full min-w-3xl text-sm">
            <thead className="bg-neutral-50 text-left text-[11px] font-bold text-neutral-500">
              <tr>
                <th className="px-5 py-3">FOLIO</th>
                <th className="px-5 py-3">FECHA</th>
                <th className="px-5 py-3">PLACA</th>
                <th className="px-5 py-3">CLIENTE</th>
                <th className="px-5 py-3">VEHÍCULO</th>
                <th className="px-5 py-3">RESULTADO</th>
                <th className="px-5 py-3">TÉCNICO</th>
              </tr>
            </thead>
            <tbody>
              {lista.map((v) => (
                <tr key={v.id} className="border-t border-borde">
                  <td className="px-5 py-3 font-semibold text-info">
                    {v.folio_certificado || "—"}
                  </td>
                  <td className="px-5 py-3 whitespace-nowrap">
                    {fechaLegible(v.fecha)}
                    {!v.dentro_de_su_periodo && (
                      <span
                        className="ml-2 text-[11px] font-bold text-alerta"
                        title="Verificó en un mes que no le tocaba"
                      >
                        fuera de periodo
                      </span>
                    )}
                  </td>
                  <td className="px-5 py-3 font-bold">
                    <Link to={`/vehiculos/${v.vehiculo_id}`}
                          className="hover:underline">
                      {v.placa}
                    </Link>
                  </td>
                  <td className="px-5 py-3">{v.cliente_nombre}</td>
                  <td className="px-5 py-3 text-neutral-500">
                    {v.vehiculo_descripcion || "—"}
                  </td>
                  <td className="px-5 py-3">
                    <Pastilla
                      texto={v.resultado === "aprobado" ? "Aprobado" : "Rechazado"}
                      clase={
                        v.resultado === "aprobado"
                          ? "bg-exito/15 text-exito"
                          : "bg-error/15 text-error"
                      }
                    />
                  </td>
                  <td className="px-5 py-3 text-neutral-500">
                    {v.tecnico_nombre || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="text-xs text-neutral-400">
        Para registrar una verificación, entra a la ficha del vehículo desde
        Clientes o desde la placa de esta tabla.
      </p>
    </div>
  );
}
