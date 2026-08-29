import { useState } from "react";
import { useNavigate } from "react-router-dom";

import Aviso from "../componentes/Aviso";
import { clientes as apiClientes } from "../api/recursos";

/* --------------------------------------------------------------------------
   El cálculo del periodo se hace también aquí, en el navegador, para que el
   técnico vea de inmediato qué le toca al auto conforme teclea la placa.
   La fuente de verdad sigue siendo el backend: esto es solo retroalimentación
   visual, y lo que se guarda es lo que calcula la base.
   -------------------------------------------------------------------------- */
const PERIODOS = {
  5: "Enero – Febrero y Julio – Agosto",
  6: "Enero – Febrero y Julio – Agosto",
  7: "Febrero – Marzo y Agosto – Septiembre",
  8: "Febrero – Marzo y Agosto – Septiembre",
  3: "Marzo – Abril y Septiembre – Octubre",
  4: "Marzo – Abril y Septiembre – Octubre",
  1: "Abril – Mayo y Octubre – Noviembre",
  2: "Abril – Mayo y Octubre – Noviembre",
  9: "Mayo – Junio y Noviembre – Diciembre",
  0: "Mayo – Junio y Noviembre – Diciembre",
};

/** Último carácter NUMÉRICO: las placas de Veracruz terminan en letra. */
function ultimoDigito(placa) {
  const digitos = (placa || "").replace(/\D/g, "");
  return digitos ? Number(digitos.at(-1)) : null;
}

const VACIO = {
  nombre: "",
  telefono: "",
  correo: "",
  consentWhatsapp: true,
  consentCorreo: true,
  avisoPrivacidad: false,
  conVehiculo: true,
  placa: "",
  niv: "",
  folioTarjeta: "",
  marca: "",
  linea: "",
  modeloAnio: "",
  color: "",
  combustible: "gasolina",
  entidadPlaca: "VER",
};

export default function ClienteNuevo() {
  const navegar = useNavigate();
  const [f, setF] = useState(VACIO);
  const [error, setError] = useState(null);
  const [enviando, setEnviando] = useState(false);

  const cambiar = (campo) => (e) =>
    setF({ ...f, [campo]: e.target.type === "checkbox" ? e.target.checked : e.target.value });

  const digito = ultimoDigito(f.placa);
  const placaSinDigito = f.placa.trim().length > 0 && digito === null;

  async function enviar(evento) {
    evento.preventDefault();
    setError(null);
    setEnviando(true);

    const cuerpo = {
      nombre: f.nombre,
      telefono: f.telefono || null,
      correo: f.correo || null,
      consentimiento: {
        whatsapp: f.consentWhatsapp,
        correo: f.consentCorreo,
        origen: "mostrador",
        aviso_privacidad_ver: f.avisoPrivacidad ? "v1" : null,
      },
    };

    if (f.conVehiculo) {
      cuerpo.vehiculo = {
        placa: f.placa,
        niv: f.niv,
        folio_tarjeta: f.folioTarjeta || null,
        marca: f.marca || null,
        linea: f.linea || null,
        modelo_anio: f.modeloAnio ? Number(f.modeloAnio) : null,
        color: f.color || null,
        combustible: f.combustible || null,
        entidad_placa: f.entidadPlaca,
      };
    }

    try {
      const creado = await apiClientes.registrar(cuerpo);
      navegar(`/clientes?nuevo=${creado.id}`);
    } catch (e) {
      setError(e.message);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="max-w-3xl space-y-5">
      <div>
        <h1 className="text-3xl font-bold text-guinda-oscuro">
          Alta de cliente y vehículo
        </h1>
        <p className="mt-1 text-sm text-neutral-500">
          Se captura una sola vez, copiando la tarjeta de circulación.
        </p>
      </div>

      <form onSubmit={enviar} className="space-y-5">
        <section className="tarjeta space-y-4 p-6">
          <h2 className="text-sm font-bold text-guinda">DATOS DEL CLIENTE</h2>

          <Campo etiqueta="Nombre completo" requerido>
            <input className="campo" value={f.nombre} onChange={cambiar("nombre")}
                   required minLength={3} autoFocus />
          </Campo>

          <div className="grid gap-4 sm:grid-cols-2">
            <Campo etiqueta="Teléfono de WhatsApp">
              <input className="campo" value={f.telefono} onChange={cambiar("telefono")}
                     placeholder="228 100 9584" inputMode="tel" />
            </Campo>
            <Campo etiqueta="Correo electrónico">
              <input className="campo" type="email" value={f.correo}
                     onChange={cambiar("correo")} placeholder="cliente@correo.com" />
            </Campo>
          </div>
        </section>

        <section className="tarjeta space-y-4 p-6">
          <label className="flex items-center gap-2.5">
            <input type="checkbox" checked={f.conVehiculo}
                   onChange={cambiar("conVehiculo")}
                   className="h-4 w-4 accent-verde" />
            <span className="text-sm font-bold text-guinda">
              REGISTRAR TAMBIÉN SU VEHÍCULO
            </span>
          </label>

          {f.conVehiculo && (
            <>
              <p className="text-xs text-neutral-400">
                Estos campos se copian tal cual de la tarjeta de circulación.
              </p>

              <div className="grid gap-4 sm:grid-cols-2">
                <Campo etiqueta="Placa" requerido>
                  <input
                    className={`campo uppercase ${placaSinDigito ? "campo-error" : ""}`}
                    value={f.placa}
                    onChange={cambiar("placa")}
                    placeholder="YUN-047-A"
                    required
                  />
                </Campo>
                <Campo etiqueta="Número de serie (NIV)" requerido>
                  <input className="campo uppercase" value={f.niv}
                         onChange={cambiar("niv")}
                         placeholder="3N1CB51S62K222173" required />
                </Campo>
              </div>

              {placaSinDigito ? (
                <Aviso>
                  Esa placa no contiene ningún número. El calendario se rige por
                  el último dígito, no por el último carácter: revisa la tarjeta
                  antes de guardar.
                </Aviso>
              ) : digito !== null ? (
                <div className="rounded-xl border border-dorado/45 bg-dorado-claro px-5 py-4">
                  <p className="text-[11px] font-bold text-dorado">
                    EL SISTEMA LO CALCULA SOLO
                  </p>
                  <p className="mt-1 font-semibold text-guinda-oscuro">
                    Último número {digito} → le toca verificar en {PERIODOS[digito]}.
                  </p>
                </div>
              ) : null}

              <div className="grid gap-4 sm:grid-cols-2">
                <Campo etiqueta="Marca">
                  <input className="campo" value={f.marca} onChange={cambiar("marca")}
                         placeholder="Nissan" />
                </Campo>
                <Campo etiqueta="Línea">
                  <input className="campo" value={f.linea} onChange={cambiar("linea")}
                         placeholder="Sentra Sedán" />
                </Campo>
                <Campo etiqueta="Modelo (año)">
                  <input className="campo" type="number" min="1900" max="2100"
                         value={f.modeloAnio} onChange={cambiar("modeloAnio")}
                         placeholder="2002" />
                </Campo>
                <Campo etiqueta="Color">
                  <input className="campo" value={f.color} onChange={cambiar("color")}
                         placeholder="Rojo intenso" />
                </Campo>
                <Campo etiqueta="Combustible">
                  <select className="campo" value={f.combustible}
                          onChange={cambiar("combustible")}>
                    <option value="gasolina">Gasolina</option>
                    <option value="diesel">Diésel</option>
                    <option value="gas_lp">Gas LP</option>
                    <option value="gas_natural">Gas natural</option>
                    <option value="hibrido">Híbrido</option>
                    <option value="electrico">Eléctrico</option>
                  </select>
                </Campo>
                <Campo etiqueta="Folio de la tarjeta">
                  <input className="campo" value={f.folioTarjeta}
                         onChange={cambiar("folioTarjeta")} placeholder="E-3426211" />
                </Campo>
              </div>
            </>
          )}
        </section>

        <section className="tarjeta space-y-3 p-6">
          <h2 className="text-sm font-bold text-guinda">
            AUTORIZACIÓN PARA CONTACTARLO
          </h2>

          <Casilla marcada={f.consentWhatsapp} alCambiar={cambiar("consentWhatsapp")}>
            Acepta recibir recordatorios por WhatsApp
          </Casilla>
          <Casilla marcada={f.consentCorreo} alCambiar={cambiar("consentCorreo")}>
            Acepta recibir recordatorios por correo electrónico
          </Casilla>
          <Casilla marcada={f.avisoPrivacidad} alCambiar={cambiar("avisoPrivacidad")}>
            Leyó y aceptó el aviso de privacidad
          </Casilla>

          {f.consentWhatsapp && !f.telefono && (
            <Aviso tono="alerta">
              Marcaste WhatsApp pero no capturaste teléfono. Sin número no se le
              puede escribir.
            </Aviso>
          )}
          {f.consentCorreo && !f.correo && (
            <Aviso tono="alerta">
              Marcaste correo pero no capturaste una dirección.
            </Aviso>
          )}
        </section>

        <Aviso>{error}</Aviso>

        <div className="flex gap-3">
          <button type="submit" className="boton-principal" disabled={enviando}>
            {enviando ? "Guardando…" : "Guardar cliente"}
          </button>
          <button type="button" className="boton-secundario"
                  onClick={() => navegar("/clientes")}>
            Cancelar
          </button>
        </div>
      </form>
    </div>
  );
}

function Campo({ etiqueta, requerido, children }) {
  return (
    <label className="block">
      <span className="etiqueta">
        {etiqueta}
        {requerido && <span className="text-error"> *</span>}
      </span>
      {children}
    </label>
  );
}

function Casilla({ marcada, alCambiar, children }) {
  return (
    <label className="flex items-center gap-3 text-sm">
      <input type="checkbox" checked={marcada} onChange={alCambiar}
             className="h-4 w-4 accent-verde" />
      {children}
    </label>
  );
}
