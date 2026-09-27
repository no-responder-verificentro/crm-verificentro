import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import Aviso from "../componentes/Aviso";
import Chat from "../componentes/Chat";
import { calendario } from "../api/recursos";

/**
 * Consulta pública: cualquiera puede saber cuándo le toca verificar con solo
 * escribir su placa. No pide contraseña ni muestra ningún dato personal —solo
 * aplica el Artículo 9 a una placa que quien pregunta ya conoce.
 *
 * Es a donde llega el cliente al dar clic en el correo, y es la misma
 * respuesta que dará el chatbot cuando exista.
 */
export default function Consulta() {
  const [parametros, setParametros] = useSearchParams();
  const [placa, setPlaca] = useState(parametros.get("placa") || "");
  const [resultado, setResultado] = useState(null);
  const [error, setError] = useState(null);
  const [buscando, setBuscando] = useState(false);

  const consultar = useCallback(async (valor) => {
    if (!valor || valor.trim().length < 4) return;
    setBuscando(true);
    setError(null);
    setResultado(null);
    try {
      setResultado(await calendario.consultar(valor.trim()));
    } catch (e) {
      setError(e.message);
    } finally {
      setBuscando(false);
    }
  }, []);

  // Si llegó desde el correo, la placa viene en la URL y se consulta sola.
  useEffect(() => {
    const dePrimera = parametros.get("placa");
    if (dePrimera) consultar(dePrimera);
  }, [parametros, consultar]);

  function enviar(evento) {
    evento.preventDefault();
    setParametros(placa ? { placa } : {});
    consultar(placa);
  }

  return (
    <div className="mx-auto max-w-xl px-6 py-14">
      <header className="mb-8 text-center">
        <h1 className="text-2xl font-bold text-guinda">VERIFICENTRO</h1>
        <p className="mt-1 text-sm text-neutral-500">
          Av. Ruíz Cortines No. 256, Col. Centro · Lunes a sábado de 9:00 a 16:00
        </p>
      </header>

      <div className="tarjeta p-7">
        <h2 className="text-xl font-bold text-guinda-oscuro">
          ¿Cuándo me toca verificar?
        </h2>
        <p className="mt-1 mb-5 text-sm text-neutral-500">
          Escribe la placa de tu vehículo. No necesitas registrarte.
        </p>

        <form onSubmit={enviar} className="flex gap-3">
          <input
            className="campo uppercase"
            value={placa}
            onChange={(e) => setPlaca(e.target.value)}
            placeholder="YUN-047-A"
            maxLength={15}
            autoFocus
          />
          <button type="submit" className="boton-principal shrink-0"
                  disabled={buscando || placa.trim().length < 4}>
            {buscando ? "Buscando…" : "Consultar"}
          </button>
        </form>

        {error && <div className="mt-5"><Aviso>{error}</Aviso></div>}

        {resultado && (
          <div className="mt-6 space-y-4">
            <div className="rounded-xl bg-guinda-oscuro px-5 py-4">
              <p className="text-[11px] font-bold text-dorado">
                PLACA {resultado.placa_normalizada} · ÚLTIMO NÚMERO{" "}
                {resultado.ultimo_digito}
              </p>
              <p className="mt-1 font-semibold text-white">{resultado.mensaje}</p>
            </div>

            <div className="space-y-2">
              {resultado.periodos.map((p) => (
                <div
                  key={p.periodo}
                  className={`flex flex-wrap items-center justify-between gap-2
                              rounded-xl border px-5 py-3.5 ${
                    p.abierto_hoy
                      ? "border-exito/40 bg-exito/10"
                      : "border-borde bg-white"
                  }`}
                >
                  <span className="font-bold">{p.etiqueta}</span>
                  <span className="text-sm text-neutral-500">
                    {p.abierto_hoy
                      ? `abierto · quedan ${p.dias_restantes} días`
                      : p.dias_para_abrir > 0
                        ? `abre en ${p.dias_para_abrir} días`
                        : "ya cerró"}
                  </span>
                </div>
              ))}
            </div>

            <p className="text-xs text-neutral-400">
              Los periodos se calculan con el último número de tu placa, según
              el Artículo 9 del Programa de Verificación Vehicular Obligatoria
              del Estado de Veracruz.
            </p>
          </div>
        )}
      </div>

      <Chat />
    </div>
  );
}
