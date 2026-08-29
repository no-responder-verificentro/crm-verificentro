export default function Cargando({ texto = "Cargando…" }) {
  return (
    <div className="flex items-center justify-center gap-3 py-16 text-sm text-neutral-500">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-borde border-t-guinda" />
      {texto}
    </div>
  );
}
