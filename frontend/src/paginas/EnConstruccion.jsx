import Vacio from "../componentes/Vacio";

/** Marcador para las secciones que todavía no se programan. Deja el menú
 *  completo para la demostración sin fingir que la pantalla ya existe. */
export default function EnConstruccion({ titulo, detalle }) {
  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-bold text-guinda-oscuro sm:text-3xl">{titulo}</h1>
      <div className="tarjeta">
        <Vacio titulo="Esta sección todavía no se programa" detalle={detalle} />
      </div>
    </div>
  );
}
