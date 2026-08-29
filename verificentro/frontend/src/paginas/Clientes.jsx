import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import Aviso from "../componentes/Aviso";
import Cargando from "../componentes/Cargando";
import Pastilla from "../componentes/Pastilla";
import Vacio from "../componentes/Vacio";
import { clientes as apiClientes } from "../api/recursos";
import { useSesion } from "../contexto/Sesion";
import {
  describirEstado,
  fechaLegible,
  telefonoLegible,
  tiempoRestante,
} from "../utils/formato";

export default function Clientes() {
  const { puede } = useSesion();

  const [busqueda, setBusqueda] = useState("");
  const [lista, setLista] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);

  // Se guarda la petición en curso para descartar respuestas viejas: si el
  // usuario teclea rápido, la respuesta de "YU" puede llegar después de la
  // de "YUN" y pisar los resultados correctos.
  const peticionActual = useRef(0);

  const consultar = useCallback(async (texto) => {
    const mia = ++peticionActual.current;
    setCargando(true);
    setError(null);
    try {
      const datos = await apiClientes.listar({ buscar: texto });
      if (mia === peticionActual.current) setLista(datos);
    } catch (e) {
      if (mia === peticionActual.current) setError(e.message);
    } finally {
      if (mia === peticionActual.current) setCargando(false);
    }
  }, []);

  // Se espera a que deje de teclear para no lanzar una petición por letra.
  useEffect(() => {
    const temporizador = setTimeout(() => consultar(busqueda), 300);
    return () => clearTimeout(temporizador);
  }, [busqueda, consultar]);

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-guinda-oscuro">Clientes</h1>
          <p className="mt-1 text-sm text-neutral-500">
            Un cliente puede tener varios vehículos. La búsqueda acepta nombre,
            teléfono, correo, placa o número de serie.
          </p>
        </div>
        {puede("capturar") && (
          <Link to="/clientes/nuevo" className="boton-principal shrink-0">
            Nuevo cliente
          </Link>
        )}
      </div>

      <input
        className="campo max-w-2xl"
        value={busqueda}
        onChange={(e) => setBusqueda(e.target.value)}
        placeholder="Buscar por nombre, teléfono, placa o número de serie…"
      />

      <Aviso>{error}</Aviso>

      {cargando && lista.length === 0 ? (
        <Cargando />
      ) : lista.length === 0 ? (
        <div className="tarjeta">
          <Vacio
            titulo={busqueda ? "Sin resultados" : "Todavía no hay clientes"}
            detalle={
              busqueda
                ? `Nada coincide con “${busqueda}”. Prueba con la placa sin guiones o con parte del nombre.`
                : "Los clientes se dan de alta en el mostrador, cuando el auto llega a verificar."
            }
          />
        </div>
      ) : (
        <div className="space-y-4">
          {lista.map((cliente) => (
            <TarjetaCliente key={cliente.id} cliente={cliente} />
          ))}
        </div>
      )}
    </div>
  );
}

function TarjetaCliente({ cliente }) {
  return (
    <article className="tarjeta overflow-hidden">
      <header className="flex flex-wrap items-center justify-between gap-3 px-6 py-4">
        <div>
          <h2 className="text-lg font-bold text-guinda-oscuro">{cliente.nombre}</h2>
          <p className="text-xs text-neutral-500">
            {telefonoLegible(cliente.telefono_e164)} ·{" "}
            {cliente.correo || "sin correo registrado"} · alta{" "}
            {fechaLegible(cliente.creado_en)}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Pastilla
            texto={cliente.consent_whatsapp ? "WhatsApp autorizado" : "Sin WhatsApp"}
            clase={
              cliente.consent_whatsapp
                ? "bg-exito/15 text-exito"
                : "bg-error/15 text-error"
            }
          />
          <Pastilla
            texto={cliente.consent_correo ? "Correo autorizado" : "Sin correo"}
            clase={
              cliente.consent_correo
                ? "bg-exito/15 text-exito"
                : "bg-neutral-400/20 text-neutral-500"
            }
          />
          {cliente.estado_contacto === "baja" && (
            <Pastilla texto="Dado de baja" clase="bg-error/15 text-error" />
          )}
          <span className="text-xs font-semibold text-neutral-500">
            {cliente.vehiculos.length}{" "}
            {cliente.vehiculos.length === 1 ? "vehículo" : "vehículos"}
          </span>
        </div>
      </header>

      {cliente.vehiculos.length === 0 ? (
        <p className="border-t border-borde px-6 py-4 text-sm text-neutral-400">
          Sin vehículos registrados.
        </p>
      ) : (
        <ul>
          {cliente.vehiculos.map((v) => (
            <FilaVehiculo key={v.id} vehiculo={v} />
          ))}
        </ul>
      )}
    </article>
  );
}

function FilaVehiculo({ vehiculo }) {
  const estado = describirEstado(vehiculo.estado);
  const descripcion = [vehiculo.marca, vehiculo.linea, vehiculo.modelo_anio]
    .filter(Boolean)
    .join(" ");

  return (
    <li className="flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-borde bg-neutral-50/60 px-6 py-3.5 text-sm">
      <span className="w-28 font-bold">{vehiculo.placa}</span>
      <span className="w-52 text-neutral-500">{descripcion || "—"}</span>

      <span className="w-24 font-semibold text-guinda">
        {vehiculo.ultimo_digito === null ? (
          <span className="text-error" title="La placa no contiene ningún número">
            sin dígito
          </span>
        ) : (
          `Dígito ${vehiculo.ultimo_digito}`
        )}
      </span>

      <span className="w-48 text-neutral-500">
        {vehiculo.ventana?.etiqueta ||
          (vehiculo.en_programa_estatal ? "—" : "Fuera del programa estatal")}
      </span>

      <span className="w-32 font-semibold">{tiempoRestante(vehiculo)}</span>

      <Pastilla texto={estado.texto} clase={estado.clase} />

      <Link
        to={`/vehiculos/${vehiculo.id}`}
        className="ml-auto text-xs font-semibold text-info hover:underline"
      >
        Ver ficha
      </Link>
    </li>
  );
}
