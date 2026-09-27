import { useEffect } from "react";

/** Ventana emergente. Se cierra con Escape o haciendo clic fuera. */
export default function Modal({ titulo, descripcion, onCerrar, children }) {
  useEffect(() => {
    const alTeclear = (e) => e.key === "Escape" && onCerrar();
    window.addEventListener("keydown", alTeclear);
    // Se bloquea el desplazamiento del fondo mientras está abierta.
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", alTeclear);
      document.body.style.overflow = "";
    };
  }, [onCerrar]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto
                 bg-black/40 p-6"
      onClick={onCerrar}
    >
      <div
        className="tarjeta my-8 w-full max-w-xl p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-5 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold text-guinda-oscuro">{titulo}</h2>
            {descripcion && (
              <p className="mt-1 text-sm text-neutral-500">{descripcion}</p>
            )}
          </div>
          <button
            onClick={onCerrar}
            aria-label="Cerrar"
            className="rounded-lg px-2 text-2xl leading-none text-neutral-400
                       transition hover:bg-crema hover:text-neutral-600"
          >
            ×
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
