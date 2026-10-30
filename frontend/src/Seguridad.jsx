import React, { useCallback, useEffect, useState } from "react";
import { ShieldCheck, Smartphone, Download, KeyRound } from "lucide-react";
import { api, changeSecurity } from "./api";
import { Heading, Notice } from "./components";

function Password() {
  return <label className="field"><span>Contraseña actual</span><input type="password" name="password" autoComplete="current-password" required maxLength={512} /></label>;
}
function Code({ backup = true }) {
  return <label className="field"><span>{backup ? "Código del autenticador o de respaldo" : "Código del autenticador"}</span>
    <input name="codigo" type="text" inputMode={backup ? "text" : "numeric"} autoComplete="one-time-code"
      required maxLength={backup ? 30 : 6} pattern={backup ? "[0-9a-fA-F \\-]{6,30}" : "[0-9]{6}"} /></label>;
}

export default function Seguridad({ user }) {
  const [estado, setEstado] = useState(null), [setup, setSetup] = useState(null), [codigos, setCodigos] = useState(null),
    [accion, setAccion] = useState(""), [error, setError] = useState(""), [mensaje, setMensaje] = useState(""),
    [busy, setBusy] = useState(false), [guardados, setGuardados] = useState(false);
  const cargar = useCallback(async () => {
    try { setEstado(await api("/auth/mfa")); } catch (e) { setError(e.message); }
  }, []);
  useEffect(() => { cargar(); }, [cargar]);
  async function ejecutar(e, operacion) {
    e.preventDefault(); setError(""); setMensaje(""); setBusy(true);
    const form = e.currentTarget;
    try {
      const datos = Object.fromEntries(new FormData(form));
      const res = await changeSecurity(operacion, datos);
      form.reset();
      if (operacion === "preparar") setSetup(res);
      if (res.codigos_respaldo) {
        setCodigos(res.codigos_respaldo); setGuardados(false); setSetup(null); setAccion("");
        setMensaje(operacion === "confirmar" ? "La verificación en dos pasos está activa. Las demás sesiones se cerraron." : "Se generaron códigos nuevos. Los anteriores ya no funcionan y las demás sesiones se cerraron.");
      }
      if (operacion === "desactivar") { setAccion(""); setMensaje("Desactivaste la verificación en dos pasos. Las demás sesiones se cerraron."); }
      await cargar();
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  async function cancelar() {
    setBusy(true); setError("");
    try { await changeSecurity("cancelar", {}); setSetup(null); } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  function descargar() {
    const texto = ["PUNTO COM · CÓDIGOS DE RESPALDO", user.correo, "", "Privados. Cada código solo funciona una vez; requieren también tu contraseña.", "Guárdalos fuera de este dispositivo. No los envíes por chat ni los subas al repositorio.", "", ...codigos].join("\n");
    const url = URL.createObjectURL(new Blob([texto], { type: "text/plain;charset=utf-8" }));
    const link = document.createElement("a"); link.href = url; link.download = "PuntoCom-codigos-respaldo.txt"; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <>
    <Heading title="Mi seguridad" description="Protege tu cuenta con una segunda verificación al ingresar." />
    <Notice message={error} />
    {mensaje && <p className="security-success" role="status">{mensaje}</p>}
    {!estado && !error && <p role="status">Consultando tu seguridad…</p>}
    {!estado && error && <button className="btn" onClick={cargar}>Volver a intentar</button>}
    {estado && <div className="security-layout">
      <section className="surface security-summary">
        <ShieldCheck size={32} aria-hidden="true" />
        <h2>Verificación en dos pasos</h2>
        <span className={"status " + (estado.activo ? "good" : "neutral")}>{estado.activo ? "Activa" : "Sin activar"}</span>
        <p>Además de tu contraseña, utilizarás un código de 6 dígitos de tu aplicación autenticadora.</p>
        {estado.activo ? <p><strong>{estado.respaldos_restantes}</strong> códigos de respaldo disponibles.</p> : <p>Solo se activa después de que vincules tu autenticador y confirmes un primer código.</p>}
        <p className="muted">Esta configuración corresponde únicamente a tu cuenta: {user.correo}.</p>
      </section>
      <section className="surface security-panel">
        {codigos ? <>
          <h2><KeyRound size={20} /> Guarda tus códigos de respaldo</h2>
          <p>Solo se muestran esta vez. Cada código reemplaza al del autenticador en un ingreso y no se puede reutilizar. Guárdalos en un lugar privado separado de tu celular.</p>
          <div className="recovery-codes">{codigos.map((codigo) => <code key={codigo}>{codigo}</code>)}</div>
          <button className="btn" type="button" onClick={descargar}><Download size={17} /> Descargar códigos</button>
          <label className="security-check"><input className="filled-in" type="checkbox" checked={guardados} onChange={(e) => setGuardados(e.target.checked)} /><span>Ya guardé mis códigos en un lugar privado.</span></label>
          <button className="btn" disabled={!guardados} onClick={() => { setCodigos(null); setMensaje(""); }}>Finalizar</button>
        </> : setup ? <>
          <h2><Smartphone size={20} /> Vincula tu autenticador</h2>
          <p>Abre tu aplicación autenticadora y añade una cuenta escaneando este QR. Se genera dentro del sistema; no se envía a un servicio de imágenes.</p>
          <img className="security-qr" src={setup.qr} alt="Código QR privado para vincular tu autenticador" />
          <p>Si estás usando el mismo celular, agrega la cuenta manualmente con esta clave:</p>
          <code className="security-manual-key">{setup.secreto}</code>
          <p className="muted">Selecciona código basado en tiempo (TOTP). Esta vinculación vence en 10 minutos.</p>
          <form onSubmit={(e) => ejecutar(e, "confirmar")}>
            <Password /><Code backup={false} />
            <p className="muted">Después de activar, espera a que aparezca un código nuevo para usarlo en otro ingreso.</p>
            <div className="form-actions"><button className="btn" disabled={busy}>Activar y mostrar respaldos</button>
              <button className="btn-flat" type="button" disabled={busy} onClick={cancelar}>Cancelar vinculación</button></div>
          </form>
        </> : !estado.activo ? <>
          <h2>Vincula una aplicación autenticadora</h2>
          <p>Usa una aplicación compatible con TOTP. Los códigos se generan en tu celular y no requieren recibir SMS ni correos.</p>
          <form onSubmit={(e) => ejecutar(e, "preparar")}><Password />
            <button className="btn" disabled={busy}>{busy ? "Verificando…" : "Preparar vinculación"}</button></form>
        </> : accion ? <>
          <h2>{accion === "desactivar" ? "Desactivar la verificación en dos pasos" : "Renovar códigos de respaldo"}</h2>
          <p>{accion === "desactivar" ? "Tu cuenta volverá a ingresar únicamente con contraseña. Para continuar, verifica tu contraseña y un código del autenticador o un respaldo sin utilizar." : "Los códigos anteriores dejarán de funcionar. Verifica tu contraseña y un código del autenticador o un respaldo sin utilizar para generar otros 10."}</p>
          <form onSubmit={(e) => ejecutar(e, accion)}><Password /><Code />
            <div className="form-actions"><button className="btn" disabled={busy}>{busy ? "Verificando…" : "Confirmar"}</button>
              <button className="btn-flat" type="button" disabled={busy} onClick={() => setAccion("")}>Cancelar</button></div></form>
        </> : <>
          <h2>Tu cuenta tiene una segunda verificación</h2>
          <p>Al ingresar, escribe tu contraseña y después un código de tu autenticador. Si pierdes el celular, utiliza un respaldo sin usar.</p>
          <div className="security-actions"><button className="btn" onClick={() => { setAccion("respaldos"); setMensaje(""); setError(""); }}>Renovar códigos de respaldo</button>
            <button className="btn-flat" onClick={() => { setAccion("desactivar"); setMensaje(""); setError(""); }}>Desactivar 2FA</button></div>
        </>}
      </section>
    </div>}
  </>;
}
