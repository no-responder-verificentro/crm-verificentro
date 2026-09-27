import { useEffect, useRef, useState } from "react";

import { chatbot } from "../api/recursos";

const SALUDO = {
  de: "bot",
  texto:
    "Hola. Soy el asistente del Verificentro. Puedo decirte cuándo te toca " +
    "verificar, qué documentos llevar y nuestro horario.\n\n" +
    "Escríbeme tu duda o la placa de tu vehículo.",
};

/**
 * Chat de la página pública.
 *
 * Corre contra el mismo motor que después atenderá WhatsApp, así que todo lo
 * que se afine aquí —las palabras clave, los textos— sirve igual allá.
 */
export default function Chat() {
  const [abierto, setAbierto] = useState(false);
  const [mensajes, setMensajes] = useState([SALUDO]);
  const [sugerencias, setSugerencias] = useState([]);
  const [texto, setTexto] = useState("");
  const [escribiendo, setEscribiendo] = useState(false);

  const fondo = useRef(null);

  useEffect(() => {
    if (abierto && sugerencias.length === 0) {
      chatbot.sugerencias().then(setSugerencias).catch(() => {});
    }
  }, [abierto, sugerencias.length]);

  // Siempre mostrar lo último.
  useEffect(() => {
    fondo.current?.scrollIntoView({ behavior: "smooth" });
  }, [mensajes, escribiendo]);

  async function enviar(contenido) {
    const limpio = (contenido ?? texto).trim();
    if (!limpio || escribiendo) return;

    setMensajes((previos) => [...previos, { de: "yo", texto: limpio }]);
    setTexto("");
    setEscribiendo(true);

    try {
      const r = await chatbot.mensaje(limpio);
      setMensajes((previos) => [
        ...previos,
        { de: "bot", texto: r.texto, entendida: r.entendida },
      ]);
      if (r.sugerencias?.length) setSugerencias(r.sugerencias);
    } catch (e) {
      setMensajes((previos) => [
        ...previos,
        { de: "bot", texto: `No pude responder: ${e.message}`, error: true },
      ]);
    } finally {
      setEscribiendo(false);
    }
  }

  if (!abierto) {
    return (
      <button
        onClick={() => setAbierto(true)}
        className="fixed right-5 bottom-5 z-40 rounded-full bg-guinda px-6 py-4
                   text-sm font-bold text-white shadow-lg transition
                   hover:bg-guinda-oscuro"
      >
        ¿Tienes dudas? Pregúntame
      </button>
    );
  }

  return (
    <div
      className="fixed right-5 bottom-5 z-40 flex h-[min(34rem,80vh)] w-[min(24rem,92vw)]
                 flex-col overflow-hidden rounded-2xl border border-borde
                 bg-white shadow-2xl"
    >
      <header className="flex items-center justify-between bg-guinda-oscuro px-5 py-4">
        <div>
          <p className="text-sm font-bold text-white">Asistente Verificentro</p>
          <p className="text-[11px] text-dorado">
            Responde al instante, todos los días
          </p>
        </div>
        <button
          onClick={() => setAbierto(false)}
          aria-label="Cerrar el chat"
          className="rounded-lg px-2 text-xl leading-none text-white/70
                     transition hover:bg-white/10 hover:text-white"
        >
          ×
        </button>
      </header>

      <div className="flex-1 space-y-3 overflow-y-auto bg-crema px-4 py-4">
        {mensajes.map((m, i) => (
          <div key={i} className={m.de === "yo" ? "text-right" : ""}>
            <div
              className={`inline-block max-w-[85%] rounded-2xl px-4 py-2.5 text-sm
                          whitespace-pre-line ${
                m.de === "yo"
                  ? "bg-guinda text-left text-white"
                  : m.error
                    ? "bg-error/10 text-error"
                    : "bg-white text-neutral-800"
              }`}
            >
              {m.texto}
            </div>
          </div>
        ))}

        {escribiendo && (
          <div className="inline-block rounded-2xl bg-white px-4 py-2.5">
            <span className="flex gap-1">
              {[0, 150, 300].map((retraso) => (
                <span
                  key={retraso}
                  className="h-1.5 w-1.5 animate-bounce rounded-full bg-neutral-400"
                  style={{ animationDelay: `${retraso}ms` }}
                />
              ))}
            </span>
          </div>
        )}

        <div ref={fondo} />
      </div>

      {sugerencias.length > 0 && !escribiendo && (
        <div className="flex flex-wrap gap-2 border-t border-borde bg-white px-4 py-3">
          {sugerencias.slice(0, 3).map((s) => (
            <button
              key={s}
              onClick={() => enviar(s)}
              className="rounded-full border border-guinda/40 px-3 py-1.5
                         text-[11px] font-semibold text-guinda transition
                         hover:bg-guinda hover:text-white"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          enviar();
        }}
        className="flex gap-2 border-t border-borde bg-white px-4 py-3"
      >
        <input
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          placeholder="Escribe tu duda o tu placa…"
          maxLength={500}
          className="flex-1 rounded-lg border border-borde px-3 py-2 text-sm
                     outline-none focus:border-guinda"
        />
        <button
          type="submit"
          disabled={!texto.trim() || escribiendo}
          className="rounded-lg bg-guinda px-4 py-2 text-sm font-bold text-white
                     transition hover:bg-guinda-oscuro disabled:opacity-40"
        >
          Enviar
        </button>
      </form>
    </div>
  );
}
