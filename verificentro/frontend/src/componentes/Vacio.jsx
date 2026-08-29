/** Estado vacío. Explica por qué no hay nada, no solo que no hay nada. */
export default function Vacio({ titulo, detalle, accion }) {
  return (
    <div className="flex flex-col items-center gap-2 px-6 py-16 text-center">
      <p className="text-base font-bold text-guinda-oscuro">{titulo}</p>
      {detalle && <p className="max-w-md text-sm text-neutral-500">{detalle}</p>}
      {accion && <div className="mt-3">{accion}</div>}
    </div>
  );
}
