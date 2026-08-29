import { useState } from "react";
import { useNavigate } from "react-router-dom";

import Aviso from "../componentes/Aviso";
import { useSesion } from "../contexto/Sesion";

export default function Login() {
  const { entrar } = useSesion();
  const navegar = useNavigate();

  const [correo, setCorreo] = useState("");
  const [contrasena, setContrasena] = useState("");
  const [error, setError] = useState(null);
  const [enviando, setEnviando] = useState(false);

  async function enviar(evento) {
    evento.preventDefault();
    setError(null);
    setEnviando(true);
    try {
      await entrar(correo.trim().toLowerCase(), contrasena);
      navegar("/", { replace: true });
    } catch (e) {
      setError(e.message);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-bold text-guinda">VERIFICENTRO</h1>
          <p className="mt-1 text-sm text-neutral-500">Panel administrativo</p>
        </div>

        <form onSubmit={enviar} className="tarjeta space-y-4 p-7">
          <div>
            <label className="etiqueta" htmlFor="correo">
              CORREO
            </label>
            <input
              id="correo"
              type="email"
              className="campo"
              value={correo}
              onChange={(e) => setCorreo(e.target.value)}
              placeholder="tu.correo@verificentro.mx"
              autoComplete="username"
              required
              autoFocus
            />
          </div>

          <div>
            <label className="etiqueta" htmlFor="contrasena">
              CONTRASEÑA
            </label>
            <input
              id="contrasena"
              type="password"
              className="campo"
              value={contrasena}
              onChange={(e) => setContrasena(e.target.value)}
              autoComplete="current-password"
              required
            />
          </div>

          <Aviso>{error}</Aviso>

          <button
            type="submit"
            className="boton-principal w-full"
            disabled={enviando || !correo || !contrasena}
          >
            {enviando ? "Entrando…" : "Entrar"}
          </button>
        </form>

        <p className="mt-6 text-center text-xs text-neutral-400">
          Si olvidaste tu contraseña, pídele a un administrador que te la
          restablezca.
        </p>
      </div>
    </div>
  );
}
