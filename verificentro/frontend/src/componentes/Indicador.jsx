/** Tarjeta de número grande para los encabezados. */
export default function Indicador({ etiqueta, valor, detalle, color = "text-guinda" }) {
  return (
    <div className="tarjeta flex-1 px-6 py-5">
      <p className="text-xs font-bold text-neutral-500">{etiqueta}</p>
      <p className={`mt-1 text-3xl font-bold ${color}`}>{valor}</p>
      {detalle && <p className="mt-1 text-xs text-neutral-500">{detalle}</p>}
    </div>
  );
}
