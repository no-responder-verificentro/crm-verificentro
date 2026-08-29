/** Etiqueta de color para estados. */
export default function Pastilla({ texto, clase = "" }) {
  return <span className={`pastilla ${clase}`}>{texto}</span>;
}
