/** Mensaje de error o de éxito. Se usa igual en formularios y en listados. */
const TONOS = {
  error: "border-error/35 bg-error/10 text-error",
  exito: "border-exito/35 bg-exito/10 text-exito",
  alerta: "border-alerta/35 bg-alerta/10 text-alerta",
};

export default function Aviso({ tono = "error", children }) {
  if (!children) return null;
  return (
    <div className={`rounded-xl border px-4 py-3 text-sm font-medium ${TONOS[tono]}`}>
      {children}
    </div>
  );
}
