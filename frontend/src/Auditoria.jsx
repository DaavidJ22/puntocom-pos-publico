import React, { useEffect, useState } from "react";
import { RefreshCw, Eye, ChevronLeft, ChevronRight, History } from "lucide-react";
import { api } from "./api";
import { Heading, Table, Modal, Notice } from "./components";

const nombres = {
  MFA_PREPARADO: "Vinculación de 2FA iniciada", MFA_ACTIVADO: "2FA activado", MFA_DESACTIVADO: "2FA desactivado",
  MFA_SOLICITADO: "Segundo factor solicitado", MFA_VERIFICADO: "Segundo factor verificado", MFA_RECHAZADO: "Verificación 2FA rechazada",
  MFA_RESPALDO_USADO: "Código de respaldo utilizado", MFA_RESPALDOS_RENOVADOS: "Respaldos 2FA renovados",
  accesos: "Accesos", productos: "Productos", categorias: "Categorías", clientes: "Clientes",
  proveedores: "Proveedores", usuarios: "Usuarios", ventas: "Ventas", compras: "Compras",
  pagos: "Pagos y saldos", abono: "Abono", caja: "Caja", inventario: "Inventario", CREAR: "Creación", ACTUALIZAR: "Modificación",
  ELIMINAR: "Eliminación", ACTIVAR: "Activación", DESACTIVAR: "Desactivación", ANULAR: "Anulación",
  ABRIR_CAJA: "Apertura de caja", CERRAR_CAJA: "Cierre de caja", APROBAR_AJUSTE: "Ajuste aprobado",
  RECHAZAR_AJUSTE: "Ajuste rechazado", CAMBIAR_ROL: "Cambio de rol", CAMBIAR_CLAVE: "Cambio de contraseña",
  VACIAR_TABLA: "Vaciado de tabla", INICIAR_SESION: "Inicio de sesión", INGRESO_RECHAZADO: "Ingreso rechazado",
  RENOVAR_SESION: "Renovación de sesión", CERRAR_SESION: "Cierre de sesión", REFRESH_REUTILIZADO: "Reutilización de token detectada",
  producto: "Producto", categoria: "Categoría", cliente: "Cliente", proveedor: "Proveedor", usuario: "Usuario",
  rol: "Rol", venta: "Venta", detalle_venta: "Detalle de venta", compra: "Compra", detalle_compra: "Detalle de compra",
  turno_caja: "Turno de caja", movimiento_caja: "Movimiento de caja", movimiento_inventario: "Movimiento de inventario",
  solicitud_ajuste: "Solicitud de ajuste", sesion: "Sesión", api: "Sistema web", monolito: "Aplicación anterior",
  base_datos: "Acceso directo a la base", precio_venta: "Precio de venta", costo_unitario_historico: "Costo histórico",
  credencial_modificada: "Contraseña modificada (valor protegido)", nombre_razon_social: "Nombre o razón social",
};
const nombre = (v) => nombres[v] || v.replaceAll("_", " ");
const valor = (v) => v === null || v === undefined ? "—" : typeof v === "boolean" ? (v ? "Sí" : "No") : String(v);
const fecha = (v) => new Date(v).toLocaleString("es-GT", { timeZone: "America/Guatemala", dateStyle: "short", timeStyle: "medium" });

export default function Auditoria() {
  const [filtros, setFiltros] = useState({}), [pagina, setPagina] = useState(1),
    [version, setVersion] = useState(0), [data, setData] = useState(null),
    [error, setError] = useState(""), [cargando, setCargando] = useState(true),
    [seleccionado, setSeleccionado] = useState(null);
  const query = new URLSearchParams({ ...filtros, pagina, limite: 25 }).toString();
  useEffect(() => {
    let activa = true;
    setCargando(true); setError("");
    api("/auditoria?" + query).then((res) => { if (activa) setData(res); })
      .catch((e) => { if (activa) setError(e.message); })
      .finally(() => { if (activa) setCargando(false); });
    return () => { activa = false; };
  }, [query, version]);
  function filtrar(e) {
    e.preventDefault();
    const entradas = [...new FormData(e.currentTarget)].filter(([,v]) => v);
    setFiltros(Object.fromEntries(entradas)); setPagina(1); setVersion((v) => v + 1);
  }
  const cambios = seleccionado ? [...new Set([
    ...Object.keys(seleccionado.antes || {}), ...Object.keys(seleccionado.despues || {}),
  ])].filter((campo) => JSON.stringify(seleccionado.antes?.[campo]) !== JSON.stringify(seleccionado.despues?.[campo]))
    .map((campo) => ({ campo, antes: seleccionado.antes?.[campo], despues: seleccionado.despues?.[campo] })) : [];
  return <>
    <Heading title="Bitácora de auditoría" description="Consulta quién realizó cada acción y revisa los cambios del sistema.">
      <button className="btn" disabled={cargando} onClick={() => setVersion((v) => v + 1)}><RefreshCw size={17} /> Actualizar</button>
    </Heading>
    <Notice message={error} />
    {data && <>
      <form className="surface audit-filters" key={JSON.stringify(filtros)} onSubmit={filtrar} aria-label="Filtros de auditoría">
        <label>Desde<input name="desde" type="date" required defaultValue={filtros.desde || data.desde} /></label>
        <label>Hasta<input name="hasta" type="date" required defaultValue={filtros.hasta || data.hasta} /></label>
        <label>Responsable<select className="browser-default" name="usuario" defaultValue={filtros.usuario || ""}>
          <option value="">Todos los responsables</option>
          {data.usuarios.map((u) => <option key={u.id_usuario + u.usuario_nombre} value={u.id_usuario}>{u.usuario_nombre} (#{u.id_usuario})</option>)}
        </select></label>
        <label>Módulo<select className="browser-default" name="modulo" defaultValue={filtros.modulo || ""}>
          <option value="">Todos los módulos</option>{data.modulos.map((v) => <option key={v} value={v}>{nombre(v)}</option>)}
        </select></label>
        <label>Acción<select className="browser-default" name="accion" defaultValue={filtros.accion || ""}>
          <option value="">Todas las acciones</option>{data.acciones.map((v) => <option key={v} value={v}>{nombre(v)}</option>)}
        </select></label>
        <label>N.º de registro<input name="registro" type="text" maxLength={100} placeholder="Ej.: 15" defaultValue={filtros.registro || ""} /></label>
        <div className="audit-filter-actions">
          <button className="btn" disabled={cargando} type="submit">Aplicar filtros</button>
          <button className="btn-flat" disabled={cargando} type="button" onClick={() => { setFiltros({}); setPagina(1); }}>Limpiar</button>
        </div>
      </form>
      {!error && <section className="surface" aria-busy={cargando}>
        <div className="section-heading"><div><h2><History size={19} /> Historial de acciones</h2>
          <p>{data.total} registros encontrados · Hora de Guatemala · Solo lectura</p></div></div>
        {cargando && <p role="status">Actualizando historial…</p>}
        <Table data={data.data} empty="No hay acciones registradas para estos filtros." columns={[
          ["fecha_hora", "Fecha y hora", fecha],
          ["usuario_nombre", "Responsable", (v,r) => <><strong>{v}</strong><small className="audit-secondary">{r.usuario_rol || "Sin sesión de usuario"}</small></>],
          ["modulo", "Módulo", nombre], ["accion", "Acción", nombre],
          ["entidad", "Referencia", (v,r) => nombre(v) + (r.registro ? " #" + r.registro : "")],
          ["id_evento", "Detalle", (v,r) => <button className="btn-flat audit-detail-button" onClick={() => setSeleccionado(r)} aria-label={"Ver evento " + v}><Eye size={17} /> Ver</button>],
        ]} />
        <div className="audit-pagination">
          <span>Página {data.pagina} de {Math.max(1, data.paginas)}</span>
          <div><button className="btn-flat" disabled={cargando || pagina <= 1} onClick={() => setPagina((p) => p - 1)}><ChevronLeft size={18} /> Anterior</button>
            <button className="btn-flat" disabled={cargando || pagina >= data.paginas} onClick={() => setPagina((p) => p + 1)}>Siguiente <ChevronRight size={18} /></button></div>
        </div>
      </section>}
      <p className="audit-note">El historial comienza al instalar la bitácora. Los cambios que se cancelan por un error no se registran como operaciones completadas.</p>
    </>}
    {!data && cargando && <p role="status">Cargando historial…</p>}
    {seleccionado && <Modal title={nombre(seleccionado.accion) + " · Evento #" + seleccionado.id_evento} onClose={() => setSeleccionado(null)}>
      <dl className="audit-metadata">
        <div><dt>Responsable</dt><dd>{seleccionado.usuario_nombre} {seleccionado.id_usuario ? "(#" + seleccionado.id_usuario + ")" : ""}</dd></div>
        <div><dt>Fecha y hora</dt><dd>{fecha(seleccionado.fecha_hora)} · Guatemala</dd></div>
        <div><dt>Registro</dt><dd>{nombre(seleccionado.entidad)} {seleccionado.registro ? "#" + seleccionado.registro : ""}</dd></div>
        <div><dt>Origen</dt><dd>{nombre(seleccionado.origen)}</dd></div>
        <div><dt>Operación relacionada</dt><dd>{seleccionado.solicitud || "Transacción " + seleccionado.transaccion}</dd></div>
      </dl>
      {cambios.length ? <Table data={cambios} columns={[
        ["campo", "Campo", nombre], ["antes", "Antes", valor], ["despues", "Después", valor],
      ]} /> : <p>Este evento no contiene cambios de campos. Las credenciales y los tokens están protegidos.</p>}
    </Modal>}
  </>;
}
