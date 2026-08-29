/** Formatos de presentación. Nada de lógica de negocio aquí. */

/** '+522281009584' -> '228 100 9584' */
export function telefonoLegible(e164) {
  if (!e164) return "—";
  const d = e164.replace(/\D/g, "");
  if (d.length === 12 && d.startsWith("52")) {
    const n = d.slice(2);
    return `${n.slice(0, 3)} ${n.slice(3, 6)} ${n.slice(6)}`;
  }
  return e164;
}

/** '2026-08-28' -> '28 ago 2026'. Se parte a mano para evitar el corrimiento
 *  de zona horaria que mete `new Date('2026-08-28')`. */
export function fechaLegible(iso) {
  if (!iso) return "—";
  const MESES = ["ene", "feb", "mar", "abr", "may", "jun",
                 "jul", "ago", "sep", "oct", "nov", "dic"];
  const [a, m, d] = iso.slice(0, 10).split("-").map(Number);
  return `${d} ${MESES[m - 1]} ${a}`;
}

/** Cómo se ve cada estado del calendario en pantalla. */
export const ESTADOS = {
  al_corriente:    { texto: "Ya verificó",     clase: "bg-exito/15 text-exito" },
  periodo_abierto: { texto: "Periodo abierto", clase: "bg-info/15 text-info" },
  por_vencer:      { texto: "Por vencer",      clase: "bg-alerta/15 text-alerta" },
  vencido:         { texto: "Vencido",         clase: "bg-error/15 text-error" },
  programado:      { texto: "Programado",      clase: "bg-neutral-500/15 text-neutral-600" },
};

export function describirEstado(estado) {
  return ESTADOS[estado] || {
    texto: "Sin calendario",
    clase: "bg-neutral-400/15 text-neutral-500",
  };
}

/** Texto corto del tiempo que queda, para la fila del listado. */
export function tiempoRestante(vehiculo) {
  const { estado, dias_restantes: dias } = vehiculo || {};
  if (dias === null || dias === undefined) return "—";
  if (estado === "vencido") return `vencido hace ${Math.abs(dias)} días`;
  if (estado === "al_corriente") return "—";
  if (dias < 0) return `abre en ${Math.abs(dias)} días`;
  if (dias === 0) return "cierra hoy";
  return `${dias} día${dias === 1 ? "" : "s"}`;
}
