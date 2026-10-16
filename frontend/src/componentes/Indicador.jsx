/**
 * Tarjeta de número grande para los encabezados.
 *
 * El `min-w` es lo que hace que funcione en celular: va dentro de un
 * `flex flex-wrap`, y `flex-1` sin ancho mínimo dejaría las cuatro tarjetas
 * apretadas en un solo renglón de 80px cada una en lugar de acomodarse de dos
 * en dos.
 */
export default function Indicador({ etiqueta, valor, detalle, color = "text-guinda" }) {
  return (
    <div className="tarjeta min-w-37 flex-1 px-5 py-4 sm:px-6 sm:py-5">
      <p className="text-xs font-bold text-neutral-500">{etiqueta}</p>
      <p className={`mt-1 text-2xl font-bold sm:text-3xl ${color}`}>{valor}</p>
      {detalle && <p className="mt-1 text-xs text-neutral-500">{detalle}</p>}
    </div>
  );
}
