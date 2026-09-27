import { useCallback, useEffect, useState } from "react";

import Aviso from "../componentes/Aviso";
import Cargando from "../componentes/Cargando";
import Modal from "../componentes/Modal";
import Pastilla from "../componentes/Pastilla";
import Vacio from "../componentes/Vacio";
import { chatbot as api } from "../api/recursos";
import { useSesion } from "../contexto/Sesion";

const TIPOS = {
  texto_fijo: ["Texto fijo", "bg-neutral-400/20 text-neutral-600"],
  automatica: ["Automática", "bg-info/15 text-info"],
  con_enlace: ["Con enlace", "bg-alerta/15 text-alerta"],
  transfiere: ["Transfiere", "bg-guinda/15 text-guinda"],
};

function haceCuanto(iso) {
  if (!iso) return "—";
  const horas = Math.round((Date.now() - new Date(iso)) / 3_600_000);
  if (horas < 1) return "hace un momento";
  if (horas < 24) return `hace ${horas} h`;
  return `hace ${Math.round(horas / 24)} días`;
}

export default function Chatbot() {
  const { puede } = useSesion();
  const editable = puede("ver_chatbot");

  const [respuestas, setRespuestas] = useState([]);
  const [pendientes, setPendientes] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [aviso, setAviso] = useState(null);
  const [editando, setEditando] = useState(null);   // objeto o 'nueva'

  const cargar = useCallback(async () => {
    setError(null);
    try {
      const [cat, pend] = await Promise.all([api.respuestas(), api.pendientes()]);
      setRespuestas(cat);
      setPendientes(pend);
    } catch (e) {
      setError(e.message);
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  if (cargando) return <Cargando texto="Cargando el catálogo…" />;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-guinda-oscuro">Chatbot</h1>
          <p className="mt-1 max-w-3xl text-sm text-neutral-500">
            Contesta en la página pública, en{" "}
            <code className="rounded bg-crema px-1.5 py-0.5 text-xs">/consulta</code>.
            Agregar, editar o borrar respuestas es inmediato y no pasa por
            revisión de nadie.
          </p>
        </div>
        {editable && (
          <button onClick={() => setEditando("nueva")}
                  className="boton-principal shrink-0">
            Agregar pregunta
          </button>
        )}
      </div>

      {aviso && <Aviso tono="exito">{aviso}</Aviso>}
      <Aviso>{error}</Aviso>

      <div className="grid gap-5 lg:grid-cols-[3fr_2fr]">
        <section className="tarjeta overflow-hidden">
          <header className="px-6 py-4">
            <h2 className="text-lg font-bold text-guinda">
              Catálogo de respuestas
            </h2>
            <p className="text-xs text-neutral-500">
              {respuestas.length} activas. El bot busca por palabras clave, así
              que entre más formas de preguntar cubras, mejor contesta.
            </p>
          </header>

          {respuestas.length === 0 ? (
            <Vacio titulo="Sin respuestas" detalle="Agrega la primera." />
          ) : (
            <ul>
              {respuestas.map((r) => (
                <li key={r.id}
                    className="flex items-start gap-4 border-t border-borde px-6 py-4">
                  <div className="flex-1">
                    <p className="text-sm font-bold">{r.pregunta}</p>
                    <p className="mt-0.5 text-xs text-neutral-500">{r.respuesta}</p>
                    {r.palabras_clave && (
                      <p className="mt-1 text-[11px] text-neutral-400">
                        palabras clave: {r.palabras_clave}
                      </p>
                    )}
                  </div>
                  <Pastilla texto={TIPOS[r.tipo]?.[0] || r.tipo}
                            clase={TIPOS[r.tipo]?.[1] || ""} />
                  {editable && (
                    <div className="flex shrink-0 gap-3">
                      <button onClick={() => setEditando(r)}
                              className="text-xs font-bold text-info hover:underline">
                        Editar
                      </button>
                      <button
                        onClick={async () => {
                          try {
                            await api.desactivar(r.id);
                            setAviso("Respuesta desactivada.");
                            cargar();
                          } catch (e) { setError(e.message); }
                        }}
                        className="text-xs font-bold text-error hover:underline"
                      >
                        Quitar
                      </button>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="tarjeta overflow-hidden">
          <header className="px-6 py-4">
            <h2 className="text-lg font-bold text-guinda">
              Lo que el bot no supo contestar
            </h2>
            <p className="text-xs text-neutral-500">
              Convertir estas en respuestas es lo que hace que mejore con el uso.
            </p>
          </header>

          {pendientes.length === 0 ? (
            <Vacio
              titulo="Nada pendiente"
              detalle="Cuando alguien pregunte algo que el bot no sepa, aparecerá aquí."
            />
          ) : (
            <ul>
              {pendientes.map((p) => (
                <li key={p.id}
                    className="flex items-start justify-between gap-3 border-t
                               border-borde px-6 py-4">
                  <div>
                    <p className="text-sm font-semibold">{p.pregunta}</p>
                    <p className="mt-0.5 text-[11px] text-neutral-400">
                      preguntada {p.veces} {p.veces === 1 ? "vez" : "veces"} ·
                      última {haceCuanto(p.ultima_vez)}
                    </p>
                  </div>
                  {editable && (
                    <button
                      onClick={() => setEditando({
                        pregunta: p.pregunta.charAt(0).toUpperCase() + p.pregunta.slice(1),
                        respuesta: "", tipo: "texto_fijo",
                        palabras_clave: "", orden: 50, _pendiente: p.id,
                      })}
                      className="shrink-0 rounded-lg border border-guinda px-3 py-1.5
                                 text-[11px] font-bold text-guinda transition
                                 hover:bg-guinda hover:text-white"
                    >
                      Responder
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      {editando && (
        <Modal
          titulo={editando === "nueva" || !editando.id
            ? "Agregar pregunta"
            : "Editar respuesta"}
          descripcion="Los cambios aplican de inmediato en la página pública."
          onCerrar={() => setEditando(null)}
        >
          <Formulario
            inicial={editando === "nueva" ? null : editando}
            alCancelar={() => setEditando(null)}
            alGuardar={(mensaje) => {
              setEditando(null);
              setAviso(mensaje);
              cargar();
            }}
            alFallar={setError}
          />
        </Modal>
      )}
    </div>
  );
}

function Formulario({ inicial, alGuardar, alCancelar, alFallar }) {
  const [f, setF] = useState({
    pregunta: inicial?.pregunta || "",
    respuesta: inicial?.respuesta || "",
    tipo: inicial?.tipo || "texto_fijo",
    palabras_clave: inicial?.palabras_clave || "",
    orden: inicial?.orden ?? 50,
  });
  const [enviando, setEnviando] = useState(false);
  const cambiar = (campo) => (e) => setF({ ...f, [campo]: e.target.value });

  const editandoExistente = Boolean(inicial?.id);

  async function enviar(evento) {
    evento.preventDefault();
    setEnviando(true);
    try {
      const cuerpo = { ...f, orden: Number(f.orden) };
      if (editandoExistente) {
        await api.editar(inicial.id, cuerpo);
      } else {
        const creada = await api.crear(cuerpo);
        if (inicial?._pendiente) {
          await api.resolverPendiente(inicial._pendiente, creada.id);
        }
      }
      alGuardar("El bot ya contesta esto.");
    } catch (e) {
      alFallar(e.message);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <form onSubmit={enviar} className="space-y-4">
      <label className="block">
        <span className="etiqueta">PREGUNTA</span>
        <input className="campo" value={f.pregunta} onChange={cambiar("pregunta")}
               required minLength={5} autoFocus
               placeholder="¿Verifican motocicletas?" />
      </label>

      <label className="block">
        <span className="etiqueta">RESPUESTA</span>
        <textarea className="campo min-h-24" value={f.respuesta}
                  onChange={cambiar("respuesta")} required minLength={2}
                  placeholder="Sí, también verificamos motocicletas." />
      </label>

      <label className="block">
        <span className="etiqueta">PALABRAS CLAVE</span>
        <input className="campo" value={f.palabras_clave}
               onChange={cambiar("palabras_clave")}
               placeholder="motocicleta, moto, motos" />
        <span className="mt-1 block text-xs text-neutral-500">
          Separadas por comas. Son las que el bot busca en el mensaje del
          cliente: incluye las formas en que realmente lo preguntan, no solo la
          correcta.
        </span>
      </label>

      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block">
          <span className="etiqueta">TIPO</span>
          <select className="campo" value={f.tipo} onChange={cambiar("tipo")}>
            <option value="texto_fijo">Texto fijo</option>
            <option value="con_enlace">Con enlace</option>
            <option value="transfiere">Pasa con una persona</option>
            <option value="automatica">Automática (la calcula el sistema)</option>
          </select>
        </label>
        <label className="block">
          <span className="etiqueta">ORDEN</span>
          <input className="campo" type="number" min="1" max="999"
                 value={f.orden} onChange={cambiar("orden")} />
          <span className="mt-1 block text-xs text-neutral-500">
            Menor número, aparece antes.
          </span>
        </label>
      </div>

      <div className="flex gap-3 pt-1">
        <button type="submit" className="boton-principal" disabled={enviando}>
          {enviando ? "Guardando…" : "Guardar"}
        </button>
        <button type="button" className="boton-secundario" onClick={alCancelar}>
          Cancelar
        </button>
      </div>
    </form>
  );
}
