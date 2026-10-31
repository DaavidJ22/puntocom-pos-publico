import React, { useEffect, useState, useCallback } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import {
  Plus,
  Download,
  ShoppingCart,
  Package,
  Users,
  TrendingUp,
  AlertTriangle,
  Trash2,
  Minus,
  CreditCard,
  Printer,
  ArrowLeft,
  Check,
  X,
} from "lucide-react";
import { api, download } from "./api";
import {
  Heading,
  Table,
  SearchBox,
  RecordForm,
  Modal,
  Notice,
  Badge,
  Empty,
  ChartPanel,
  q,
  fecha,
} from "./components";

export function useLoad(path) {
  const [data, setData] = useState(null),
    [error, setError] = useState("");
  const load = useCallback(async () => {
    setError("");
    try {
      setData(await api(path));
    } catch (e) {
      setError(e.message);
    }
  }, [path]);
  useEffect(() => {
    setData(null);
    load();
  }, [load]);
  return { data, error, load };
}
const textField = (name, label, required = false, type = "text") => ({
  name,
  label,
  required,
  type,
});
const moneyColumn = (key, label) => [key, label, q];
const statusColumn = ["estado", "Estado", (v) => <Badge value={v} />];
export function Dashboard() {
  const { data, error } = useLoad("/dashboard");
  return (
    <>
      <Heading
        title="Panel principal"
        description="Una mirada clara a las operaciones de hoy."
      >
        <Link to="/pos" className="btn waves-effect">
          <Plus size={18} /> Nueva venta
        </Link>
      </Heading>
      <Notice message={error} />
      {data && (
        <>
          <div className="metric-grid">
            {[
              ["Ventas de hoy", q(data.resumen.ventas), TrendingUp, "blue"],
              ["Ventas realizadas", data.resumen.nventas, ShoppingCart, "teal"],
              ["Productos activos", data.resumen.productos, Package, "purple"],
              ["Stock bajo", data.resumen.bajos, AlertTriangle, "amber"],
              ["Clientes", data.resumen.clientes, Users, "blue"],
              [
                "Ganancia bruta estimada",
                q(data.resumen.ganancia),
                TrendingUp,
                "teal",
              ],
            ].map(([title, value, Icon, color]) => (
              <section className="metric" key={title}>
                <div className="metric-top">
                  <span>{title}</span>
                  <span className={"metric-icon " + color}>
                    <Icon size={20} />
                  </span>
                </div>
                <strong>{value}</strong>
                <small>
                  {title === "Stock bajo"
                    ? "Productos que necesitan atención"
                    : "Actualizado con los datos del sistema"}
                </small>
              </section>
            ))}
          </div>
          <div className="dashboard-grid">
            <ChartPanel
              data={data.dias}
              title="Ventas de la semana"
              description="Últimos 7 días · Quetzales"
            />
            <section className="surface">
              <div className="section-heading">
                <div>
                  <h2>Atención al inventario</h2>
                  <p>Revisa las existencias a tiempo</p>
                </div>
                <AlertTriangle size={20} />
              </div>
              {data.alertas.length ? (
                data.alertas.slice(0, 5).map((p) => (
                  <div className="stock-alert" key={p.id_producto}>
                    <span className="product-avatar">
                      <Package size={21} />
                    </span>
                    <div>
                      <strong>{p.nombre}</strong>
                      <small>
                        {p.codigo} · Mínimo {p.stock_minimo}
                      </small>
                    </div>
                    <Badge
                      value={
                        p.existencia_actual === 0
                          ? "Agotado"
                          : p.existencia_actual + " disponibles"
                      }
                    />
                  </div>
                ))
              ) : (
                <Empty text="Tus productos tienen existencias suficientes." />
              )}
              <Link className="text-link" to="/inventario">
                Consultar inventario →
              </Link>
            </section>
          </div>
          <div className="section-space">
            <ChartPanel
              data={data.meses}
              title="Ventas mensuales"
              description="Ingresos del año actual · Quetzales"
            />
          </div>
        </>
      )}
    </>
  );
}

const configs = {
  productos: {
    title: "Productos",
    description: "Tu catálogo, precios y existencias en un solo lugar.",
    pk: "id_producto",
    permission: "productos.gestionar",
    create: "productos.gestionar",
    fields: [
      textField("codigo", "Código", true),
      textField("codigo_barras", "Código de barras"),
      textField("nombre", "Nombre del producto", true),
      textField("marca", "Marca"),
      textField("unidad", "Unidad", true),
      {
        name: "costo",
        label: "Costo Q",
        type: "number",
        min: 0,
        step: ".01",
        required: true,
      },
      {
        name: "precio_venta",
        label: "Precio de venta Q",
        type: "number",
        min: 0,
        step: ".01",
        required: true,
      },
      {
        name: "stock_minimo",
        label: "Existencia mínima",
        type: "number",
        min: 0,
        step: 1,
        required: true,
      },
    ],
    columns: [
      ["codigo", "Código"],
      ["nombre", "Producto"],
      ["categoria", "Categoría"],
      moneyColumn("precio_venta", "Precio"),
      ["existencia_actual", "Existencia"],
      statusColumn,
    ],
  },
  categorias: {
    title: "Categorías",
    description: "Organiza tu catálogo por tipo de producto.",
    pk: "id_categoria",
    permission: "productos.gestionar",
    create: "productos.gestionar",
    fields: [
      {
        ...textField("nombre", "Nombre", true),
        maxLength: 100,
        pattern: "[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+( [A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+)*",
        title: "Utiliza letras y un espacio entre palabras.",
      },
      {
        ...textField("descripcion", "Descripción"),
        pattern: "[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+( [A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+)*",
        title: "Utiliza letras y un espacio entre palabras.",
      },
    ],
    columns: [
      ["nombre", "Nombre"],
      ["descripcion", "Descripción"],
      statusColumn,
    ],
  },
  clientes: {
    title: "Clientes",
    description: "Información de tus clientes para cada venta.",
    pk: "id_cliente",
    permission: "clientes.gestionar",
    create: "clientes.crear",
    fields: [
      {
        ...textField("nombre_razon_social", "Nombre o razón social", true),
        maxLength: 150,
        pattern: "[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+( [A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+)*",
        title: "Utiliza letras y un espacio entre palabras.",
      },
      { ...textField("nit_dpi", "NIT o DPI"), maxLength: 30 },
      textField("telefono", "Teléfono de 8 dígitos"),
      textField("correo", "Correo electrónico", false, "email"),
      textField("direccion_fiscal", "Dirección fiscal"),
    ],
    columns: [
      ["nombre_razon_social", "Cliente"],
      ["nit_dpi", "NIT / DPI"],
      ["telefono", "Teléfono"],
      ["correo", "Correo"],
      statusColumn,
    ],
  },
  proveedores: {
    title: "Proveedores",
    description: "Contactos y abastecimiento de tu negocio.",
    pk: "id_proveedor",
    permission: "proveedores.gestionar",
    create: "proveedores.gestionar",
    fields: [
      { ...textField("razon_social", "Razón social", true), maxLength: 150 },
      { ...textField("nit", "NIT"), maxLength: 30 },
      {
        ...textField("contacto", "Contacto"),
        maxLength: 100,
        pattern: "[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+( [A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+)*",
        title: "Utiliza letras y un espacio entre palabras.",
      },
      textField("telefono", "Teléfono de 8 dígitos"),
      textField("correo", "Correo electrónico", false, "email"),
      textField("direccion", "Dirección"),
    ],
    columns: [
      ["razon_social", "Proveedor"],
      ["nit", "NIT"],
      ["contacto", "Contacto"],
      ["telefono", "Teléfono"],
      statusColumn,
    ],
  },
  usuarios: {
    title: "Usuarios y permisos",
    description: "Cada persona accede a las funciones de su perfil.",
    pk: "id_usuario",
    permission: "usuarios.gestionar",
    create: "usuarios.gestionar",
    fields: [
      {
        ...textField("nombre", "Nombre", true),
        maxLength: 100,
        pattern: "[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+( [A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+)*",
        title: "Utiliza letras y un espacio entre palabras.",
      },
      textField("correo", "Correo", true, "email"),
      textField(
        "password",
        "Contraseña de al menos 12 caracteres",
        true,
        "password",
      ),
    ],
    columns: [
      ["nombre", "Nombre"],
      ["correo", "Correo"],
      ["rol", "Perfil"],
      statusColumn,
    ],
  },
};
export function Resource({ module, can, refreshUser }) {
  const cfg = configs[module],
    { data, error, load } = useLoad("/registros/" + module);
  const [search, setSearch] = useState(""),
    [editing, setEditing] = useState(null),
    [actionError, setActionError] = useState(""),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    setSearch("");
    setEditing(null);
    setActionError("");
  }, [module]);
  const columns = [...cfg.columns];
  if (module === "productos" && can("costos.ver"))
    columns.splice(3, 0, moneyColumn("costo", "Costo"));
  async function action(row, kind) {
    if (
      !window.confirm(
        kind === "eliminar"
          ? "¿Eliminar definitivamente este registro sin historial?"
          : "¿" + (row.estado ? "Desactivar" : "Reactivar") + " este registro?",
      )
    )
      return;
    setBusy(true);
    try {
      await api(
        "/registros/" +
          module +
          "/" +
          row[cfg.pk] +
          (kind === "eliminar" ? "" : "/estado"),
        {
          method: kind === "eliminar" ? "DELETE" : "POST",
          ...(kind === "eliminar"
            ? {}
            : { body: { accion: row.estado ? "desactivar" : "activar" } }),
        },
      );
      await load();
    } catch (e) {
      setActionError(e.message);
    } finally {
      setBusy(false);
    }
  }
  if (can(cfg.permission))
    columns.push([
      "actions",
      "Acciones",
      (_, row) => (
        <div className="row-actions">
          <button className="btn-small tonal" onClick={() => setEditing(row)}>
            Editar{module === "usuarios" ? " rol" : ""}
          </button>
          <button
            disabled={busy || row.protegido}
            className="btn-small tonal"
            onClick={() => action(row, "estado")}
          >
            {row.estado ? "Desactivar" : "Reactivar"}
          </button>
          <button
            disabled={busy || !row.puede_eliminar}
            title={row.motivo_eliminacion || "Eliminar registro sin historial"}
            className="icon-button danger"
            aria-label={
              "Eliminar " +
              (row.nombre || row.nombre_razon_social || row.razon_social)
            }
            onClick={() => action(row, "eliminar")}
          >
            <Trash2 size={17} />
          </button>
        </div>
      ),
    ]);
  let fields = [...cfg.fields];
  if (module === "productos")
    fields = [
      {
        name: "id_categoria",
        label: "Categoría",
        required: true,
        options: (data?.categorias || [])
          .filter((c) => c.estado || c.id_categoria === editing?.id_categoria)
          .map((c) => [c.id_categoria, c.nombre]),
      },
      ...fields,
      ...(!editing?.[cfg.pk]
        ? [
            {
              name: "stock_inicial",
              label: "Existencia inicial",
              type: "number",
              min: 0,
              step: 1,
            },
          ]
        : []),
    ];
  if (module === "usuarios")
    fields = [
      ...(editing?.id_usuario ? [] : fields),
      {
        name: "id_rol",
        label: "Perfil",
        required: true,
        options: (data?.roles || []).map((r) => [r.id_rol, r.nombre]),
      },
    ];
  const filtered = (data?.data || []).filter((row) =>
    Object.values(row).join(" ").toLowerCase().includes(search.toLowerCase()),
  );
  return (
    <>
      <Heading title={cfg.title} description={cfg.description}>
        {can(cfg.create) && (
          <button
            className="btn waves-effect"
            onClick={() =>
              setEditing(
                module === "productos"
                  ? {
                      unidad: "Unidad",
                      costo: 0,
                      precio_venta: 0,
                      stock_minimo: 5,
                      stock_inicial: 0,
                    }
                  : {},
              )
            }
          >
            <Plus size={18} />{" "}
            {module === "usuarios" ? "Nuevo usuario" : "Nuevo registro"}
          </button>
        )}
      </Heading>
      <Notice message={error || actionError} />
      <section className="surface">
        <div className="table-toolbar">
          <SearchBox value={search} onChange={setSearch} />
          <span>{filtered.length} registros</span>
        </div>
        <Table columns={columns} data={filtered} />
      </section>
      {editing && (
        <Modal
          title={(editing[cfg.pk] ? "Editar" : "Agregar") + " · " + cfg.title}
          onClose={() => setEditing(null)}
        >
          <RecordForm
            fields={fields}
            initial={editing}
            onCancel={() => setEditing(null)}
            onSave={async (form) => {
              await api(
                "/registros/" +
                  module +
                  (editing[cfg.pk] ? "/" + editing[cfg.pk] : ""),
                { method: editing[cfg.pk] ? "PUT" : "POST", body: form },
              );
              setEditing(null);
              await load();
              if (module === "usuarios") await refreshUser();
            }}
          />
        </Modal>
      )}
    </>
  );
}

export function POS({ can }) {
  const { data, error, load } = useLoad("/catalogo"),
    [search, setSearch] = useState(""),
    [cart, setCart] = useState([]),
    [client, setClient] = useState(""),
    [pay, setPay] = useState(false),
    [method, setMethod] = useState("EFECTIVO"),
    [received, setReceived] = useState(""),
    [payError, setPayError] = useState(""),
    [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  useEffect(() => {
    if (data)
      setClient(
        String(
          data.clientes.find(
            (c) => c.nombre_razon_social === "Consumidor Final",
          )?.id_cliente ||
            data.clientes[0]?.id_cliente ||
            "",
        ),
      );
  }, [data]);
  const totalCents = cart.reduce(
      (a, p) =>
        a +
        Math.round(Number(p.precio_venta) * 100) * p.cantidad -
        Math.round(Number(p.descuento || 0) * 100),
      0,
    ),
    total = totalCents / 100;
  function add(p) {
    setPayError("");
    setCart((old) => {
      const item = old.find((i) => i.id === p.id_producto);
      if ((item?.cantidad || 0) >= Number(p.existencia_actual)) {
        setPayError("No hay más existencias de " + p.nombre);
        return old;
      }
      return item
        ? old.map((i) =>
            i.id === p.id_producto ? { ...i, cantidad: i.cantidad + 1 } : i,
          )
        : [...old, { ...p, id: p.id_producto, cantidad: 1, descuento: 0 }];
    });
  }
  function change(id, key, value) {
    setCart((old) =>
      old.map((i) => {
        if (i.id !== id) return i;
        const n = Number(value);
        if (!Number.isFinite(n)) return i;
        return {
          ...i,
          [key]:
            key === "cantidad"
              ? Math.max(
                  1,
                  Math.min(Number(i.existencia_actual), Math.floor(n)),
                )
              : Math.max(0, n),
        };
      }),
    );
  }
  async function checkout() {
    setBusy(true);
    setPayError("");
    try {
      const res = await api("/ventas", {
        method: "POST",
        body: {
          items: cart.map((p) => ({
            id: p.id,
            cantidad: p.cantidad,
            descuento: can("descuentos.modificar") ? p.descuento : 0,
          })),
          cliente_id: client,
          metodo: method,
          recibido: method === "EFECTIVO" ? received : 0,
        },
      });
      setCart([]);
      setPay(false);
      navigate("/ventas/" + res.resultado.id_venta);
    } catch (e) {
      setPayError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Heading
        title="Punto de venta"
        description="Busca, agrega y cobra. Así de sencillo."
      >
        <Badge value={data?.turno ? "ABIERTO" : "Caja cerrada"} />
      </Heading>
      <Notice message={error} />
      {data && !data.turno && (
        <div className="info-banner">
          <AlertTriangle size={20} />
          <span>Abre tu caja para registrar ventas.</span>
          <Link to="/caja">Ir a caja →</Link>
        </div>
      )}
      <div className="pos-grid">
        <section className="surface">
          <div className="section-heading">
            <h2>Catálogo disponible</h2>
            <span className="muted">
              {data?.productos.length || 0} productos
            </span>
          </div>
          <SearchBox
            value={search}
            onChange={setSearch}
            placeholder="Buscar por nombre, código o barras…"
          />
          <div className="product-grid">
            {data?.productos
              .filter((p) =>
                (p.nombre + " " + p.codigo + " " + (p.codigo_barras || ""))
                  .toLowerCase()
                  .includes(search.toLowerCase()),
              )
              .map((p) => (
                <button
                  className="product-card"
                  disabled={Number(p.existencia_actual) <= 0}
                  key={p.id_producto}
                  onClick={() => add(p)}
                >
                  <span className="product-card-top">
                    <span className="product-avatar">
                      <Package size={24} />
                    </span>
                    <span className="stock-count">
                      {p.existencia_actual} disp.
                    </span>
                  </span>
                  <small>{p.codigo}</small>
                  <strong>{p.nombre}</strong>
                  <span className="product-price">
                    {q(p.precio_venta)} <Plus size={18} />
                  </span>
                </button>
              ))}
          </div>
        </section>
        <section className="surface cart-panel">
          <div className="section-heading">
            <h2>Carrito de venta</h2>
            <span className="count-pill">
              {cart.reduce((a, p) => a + p.cantidad, 0)}
            </span>
          </div>
          <label className="field">
            <span>Cliente</span>
            <select
              className="browser-default"
              value={client}
              onChange={(e) => setClient(e.target.value)}
            >
              {data?.clientes.map((c) => (
                <option key={c.id_cliente} value={c.id_cliente}>
                  {c.nombre_razon_social}
                </option>
              ))}
            </select>
          </label>
          <div className="cart-items">
            {!cart.length ? (
              <Empty text="Agrega productos para comenzar una venta." />
            ) : (
              cart.map((p) => (
                <div className="cart-item" key={p.id}>
                  <div className="cart-name">
                    <strong>{p.nombre}</strong>
                    <button
                      className="icon-button danger"
                      aria-label={"Quitar " + p.nombre}
                      onClick={() => setCart(cart.filter((i) => i.id !== p.id))}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                  <small>{q(p.precio_venta)} por unidad</small>
                  <div className="cart-quantity">
                    <div className="stepper">
                      <button
                        className="icon-button"
                        aria-label={"Reducir cantidad de " + p.nombre}
                        onClick={() => change(p.id, "cantidad", p.cantidad - 1)}
                      >
                        <Minus size={15} />
                      </button>
                      <input
                        aria-label={"Cantidad de " + p.nombre}
                        type="number"
                        min="1"
                        max={p.existencia_actual}
                        value={p.cantidad}
                        onChange={(e) =>
                          change(p.id, "cantidad", e.target.value)
                        }
                      />
                      <button
                        className="icon-button"
                        aria-label={"Aumentar cantidad de " + p.nombre}
                        onClick={() => change(p.id, "cantidad", p.cantidad + 1)}
                      >
                        <Plus size={15} />
                      </button>
                    </div>
                    <strong>
                      {q(
                        Number(p.precio_venta) * p.cantidad -
                          Number(p.descuento),
                      )}
                    </strong>
                  </div>
                  {can("descuentos.modificar") && (
                    <label className="discount-field">
                      Descuento Q
                      <input
                        type="number"
                        min="0"
                        max={Number(p.precio_venta) * p.cantidad}
                        step=".01"
                        value={p.descuento}
                        onChange={(e) =>
                          change(p.id, "descuento", e.target.value)
                        }
                      />
                    </label>
                  )}
                </div>
              ))
            )}
          </div>
          <Notice message={!pay ? payError : ""} />
          <div className="cart-total">
            <span>Total a cobrar</span>
            <strong>{q(total)}</strong>
          </div>
          <button
            className="btn waves-effect full-width checkout-button"
            disabled={!cart.length || !data?.turno || total < 0}
            onClick={() => {
              setPayError("");
              setPay(true);
            }}
          >
            <CreditCard size={20} /> Cobrar venta
          </button>
          {!!cart.length && (
            <button
              className="text-button"
              onClick={() => {
                if (window.confirm("¿Vaciar el carrito?")) setCart([]);
              }}
            >
              Vaciar carrito
            </button>
          )}
        </section>
      </div>
      {pay && (
        <Modal title="Confirmar cobro" onClose={() => setPay(false)}>
          <div className="payment-total">{q(total)}</div>
          <label className="field">
            <span>Método de pago</span>
            <select
              className="browser-default"
              value={method}
              onChange={(e) => setMethod(e.target.value)}
            >
              <option>EFECTIVO</option>
              <option>TARJETA</option>
              <option>TRANSFERENCIA</option>
              <option>CRÉDITO</option>
            </select>
          </label>
          {method === "CRÉDITO" && (
            <p className="info-banner">
              La venta quedará pendiente de cobro. Registra sus abonos en Pagos
              y saldos.
            </p>
          )}
          {method === "EFECTIVO" && (
            <label className="field">
              <span>Monto recibido Q</span>
              <input
                type="number"
                min={total}
                step=".01"
                value={received}
                onChange={(e) => setReceived(e.target.value)}
              />
              <small>Cambio: {q(Math.max(0, Number(received) - total))}</small>
            </label>
          )}
          <Notice message={payError} />
          <div className="form-actions">
            <button className="btn tonal" onClick={() => setPay(false)}>
              Cancelar
            </button>
            <button
              className="btn"
              disabled={
                busy || (method === "EFECTIVO" && Number(received) < total)
              }
              onClick={checkout}
            >
              {busy ? "Registrando…" : "Confirmar venta"}
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}

export function Sales({ can }) {
  const { data, error, load } = useLoad("/ventas"),
    [search, setSearch] = useState(""),
    [cancel, setCancel] = useState(null);
  return (
    <>
      <Heading
        title="Ventas"
        description={
          can("ventas.todas")
            ? "Consulta operaciones, comprobantes y anulaciones."
            : "Historial de tus propias operaciones."
        }
      />
      <Notice message={error} />
      <section className="surface">
        <div className="table-toolbar">
          <SearchBox value={search} onChange={setSearch} />
        </div>
        <Table
          data={(data?.data || []).filter((v) =>
            (v.numero_ticket + " " + v.nombre_razon_social)
              .toLowerCase()
              .includes(search.toLowerCase()),
          )}
          columns={[
            ["numero_ticket", "Comprobante"],
            ["fecha_hora", "Fecha", fecha],
            ["nombre_razon_social", "Cliente"],
            moneyColumn("total", "Total"),
            statusColumn,
            [
              "actions",
              "Acciones",
              (_, r) => (
                <div className="row-actions">
                  <Link
                    to={"/ventas/" + r.id_venta}
                    className="btn-small tonal"
                  >
                    Ver ticket
                  </Link>
                  {can("ventas.anular") && r.estado === "COMPLETADA" && (
                    <button
                      className="btn-small tonal danger"
                      onClick={() => setCancel(r)}
                    >
                      Anular
                    </button>
                  )}
                </div>
              ),
            ],
          ]}
        />
      </section>
      {cancel && (
        <Modal
          title={"Anular " + cancel.numero_ticket}
          onClose={() => setCancel(null)}
        >
          <p>
            Se conservará el historial y se devolverán las existencias. El
            reembolso en efectivo requiere una caja administrativa abierta.
          </p>
          <RecordForm
            fields={[textField("motivo", "Motivo de anulación", true)]}
            onCancel={() => setCancel(null)}
            onSave={async (d) => {
              await api("/ventas/" + cancel.id_venta + "/anular", {
                method: "POST",
                body: d,
              });
              setCancel(null);
              load();
            }}
            submitLabel="Confirmar anulación"
          />
        </Modal>
      )}
    </>
  );
}
export function Ticket() {
  const { id } = useParams(),
    { data, error } = useLoad("/ventas/" + id);
  return (
    <>
      <Heading title="Comprobante de venta">
        <Link to="/ventas" className="btn tonal">
          <ArrowLeft size={17} /> Volver
        </Link>
        <button className="btn" onClick={() => window.print()}>
          <Printer size={17} /> Imprimir
        </button>
      </Heading>
      <Notice message={error} />
      {data && (
        <div className="ticket-paper">
          <h2>PUNTO COM</h2>
          <p>Comprobante de venta · {data.venta.numero_ticket}</p>
          <Badge value={data.venta.estado} />
          <p>
            {fecha(data.venta.fecha_hora)}
            <br />
            {data.venta.nombre_razon_social} · NIT {data.venta.nit_dpi || "CF"}
            <br />
            Atendió: {data.venta.cajero}
          </p>
          <Table
            data={data.detalle}
            columns={[
              ["nombre", "Producto"],
              ["cantidad", "Cant."],
              moneyColumn("precio_unitario", "Precio"),
              moneyColumn("descuento", "Desc."),
            ]}
          />
          <div className="cart-total">
            <span>Total</span>
            <strong>{q(data.venta.total)}</strong>
          </div>
          <p>{data.venta.metodo_pago} · ¡Gracias por tu compra!</p>
          {data.venta.metodo_pago === "CRÉDITO" && (
            <p>
              Documento a crédito. Consulta el saldo actualizado y sus recibos
              en Pagos y saldos.
            </p>
          )}
        </div>
      )}
    </>
  );
}

export function Cash() {
  const { data, error, load } = useLoad("/caja"),
    [form, setForm] = useState(null);
  return (
    <>
      <Heading
        title="Control de caja"
        description="Cada ingreso y egreso, en su lugar."
      >
        <Badge value={data?.turno ? "ABIERTO" : "Sin turno abierto"} />
      </Heading>
      <Notice message={error} />
      {data && (
        <>
          <div className="cash-grid">
            <section className="surface">
              <h2>
                {data.turno
                  ? "Turno #" + data.turno.id_turno
                  : "Comienza tu jornada"}
              </h2>
              <p className="muted">
                {data.turno
                  ? "Efectivo esperado en tu caja"
                  : "Abre una caja antes de registrar ventas."}
              </p>
              {data.turno && (
                <div className="payment-total">{q(data.saldo)}</div>
              )}
              <div className="button-stack">
                {data.turno ? (
                  <>
                    <button
                      className="btn"
                      onClick={() => setForm("movimiento")}
                    >
                      <Plus size={18} /> Registrar movimiento
                    </button>
                    <button
                      className="btn tonal danger"
                      onClick={() => setForm("cerrar")}
                    >
                      Cerrar turno
                    </button>
                  </>
                ) : (
                  <button className="btn" onClick={() => setForm("abrir")}>
                    Abrir caja
                  </button>
                )}
              </div>
            </section>
            <section className="surface">
              <h2>Movimientos del turno</h2>
              <Table
                data={data.movimientos}
                columns={[
                  ["fecha_hora", "Fecha", fecha],
                  ["tipo", "Tipo"],
                  ["concepto", "Concepto"],
                  moneyColumn("monto", "Importe"),
                ]}
              />
            </section>
          </div>
          <section className="surface section-space">
            <h2>Últimos turnos</h2>
            <Table
              data={data.ultimos}
              columns={[
                ["id_turno", "Turno"],
                ["usuario", "Responsable"],
                ["apertura", "Apertura", fecha],
                moneyColumn("fondo_inicial", "Fondo inicial"),
                statusColumn,
              ]}
            />
          </section>
        </>
      )}
      {form && (
        <Modal
          title={
            {
              abrir: "Abrir caja",
              cerrar: "Cerrar turno",
              movimiento: "Movimiento de efectivo",
            }[form]
          }
          onClose={() => setForm(null)}
        >
          <RecordForm
            fields={
              form === "abrir"
                ? [
                    {
                      name: "fondo_inicial",
                      label: "Fondo inicial Q",
                      type: "number",
                      min: 0,
                      step: ".01",
                      required: true,
                    },
                  ]
                : form === "cerrar"
                  ? [
                      {
                        name: "efectivo_contado",
                        label: "Efectivo contado Q",
                        type: "number",
                        min: 0,
                        step: ".01",
                        required: true,
                      },
                    ]
                  : [
                      {
                        name: "tipo",
                        label: "Tipo",
                        options: [
                          ["INGRESO", "Ingreso"],
                          ["EGRESO", "Egreso"],
                        ],
                        required: true,
                      },
                      textField("concepto", "Concepto", true),
                      {
                        name: "monto",
                        label: "Monto Q",
                        type: "number",
                        min: ".01",
                        step: ".01",
                        required: true,
                      },
                    ]
            }
            onCancel={() => setForm(null)}
            onSave={async (d) => {
              await api("/caja", {
                method: "POST",
                body: { ...d, accion: form },
              });
              setForm(null);
              load();
            }}
          />
        </Modal>
      )}
    </>
  );
}

export function Inventory({ can }) {
  const { data, error, load } = useLoad("/inventario"),
    [search, setSearch] = useState(""),
    [form, setForm] = useState(null),
    [actionError, setActionError] = useState("");
  const columns = [
    ["codigo", "Código"],
    ["nombre", "Producto"],
    ["categoria", "Categoría"],
    ["existencia_actual", "Existencia"],
    ["stock_minimo", "Mínimo"],
    [
      "stock",
      "Disponibilidad",
      (_, r) => (
        <Badge
          value={
            !r.estado
              ? "Inactivo"
              : r.existencia_actual === 0
                ? "Agotado"
                : r.existencia_actual <= r.stock_minimo
                  ? "Stock bajo"
                  : "Disponible"
          }
        />
      ),
    ],
  ];
  if (can("costos.ver")) columns.push(moneyColumn("costo", "Costo"));
  async function resolve(id, accion) {
    if (
      !window.confirm(
        "¿" + (accion === "aprobar" ? "Aprobar" : "Rechazar") + " este conteo?",
      )
    )
      return;
    try {
      await api(`/inventario/ajustes/${id}/${accion}`, {
        method: "POST",
        body: { motivo: "Revision de inventario" },
      });
      load();
    } catch (e) {
      setActionError(e.message);
    }
  }
  return (
    <>
      <Heading
        title="Inventario"
        description="Controla existencias, movimientos y conteos físicos."
      >
        <button
          className="btn tonal"
          onClick={() =>
            download("/inventario/excel", "Inventario.xlsx").catch((e) =>
              setActionError(e.message),
            )
          }
        >
          <Download size={17} /> Excel
        </button>
        {can("inventario.mover") && (
          <button className="btn" onClick={() => setForm("movimientos")}>
            <Plus size={18} /> Movimiento
          </button>
        )}
      </Heading>
      <Notice message={error || actionError} />
      <section className="surface">
        <div className="table-toolbar">
          <SearchBox value={search} onChange={setSearch} />
          {can("inventario.contar") && (
            <button
              className="btn-small tonal"
              onClick={() => setForm("conteos")}
            >
              Registrar conteo físico
            </button>
          )}
        </div>
        <Table
          data={(data?.data || []).filter((p) =>
            (p.codigo + " " + p.nombre)
              .toLowerCase()
              .includes(search.toLowerCase()),
          )}
          columns={columns}
        />
      </section>
      <section className="surface section-space">
        <div className="section-heading">
          <h2>Solicitudes de ajuste</h2>
          <span className="muted">Los conteos requieren aprobación</span>
        </div>
        <Table
          data={data?.solicitudes}
          columns={[
            ["codigo", "Producto"],
            ["solicitante", "Solicitante"],
            ["existencia_sistema", "Sistema"],
            ["cantidad_contada", "Conteo"],
            ["diferencia", "Diferencia"],
            statusColumn,
            ...(can("inventario.aprobar")
              ? [
                  [
                    "actions",
                    "Resolver",
                    (_, r) =>
                      r.estado === "PENDIENTE" && (
                        <div className="row-actions">
                          <button
                            className="icon-button"
                            aria-label={"Aprobar conteo " + r.id_solicitud}
                            onClick={() => resolve(r.id_solicitud, "aprobar")}
                          >
                            <Check size={18} />
                          </button>
                          <button
                            className="icon-button danger"
                            aria-label={"Rechazar conteo " + r.id_solicitud}
                            onClick={() => resolve(r.id_solicitud, "rechazar")}
                          >
                            <X size={18} />
                          </button>
                        </div>
                      ),
                  ],
                ]
              : []),
          ]}
        />
      </section>
      <section className="surface section-space">
        <h2>Últimos movimientos</h2>
        <Table
          data={data?.movimientos}
          columns={[
            ["fecha_hora", "Fecha", fecha],
            ["nombre", "Producto"],
            ["tipo", "Tipo"],
            ["cantidad", "Cantidad"],
            ["responsable", "Responsable"],
            ["motivo", "Motivo"],
          ]}
        />
      </section>
      {form && (
        <Modal
          title={
            form === "conteos"
              ? "Registrar conteo físico"
              : "Registrar movimiento"
          }
          onClose={() => setForm(null)}
        >
          <RecordForm
            fields={[
              {
                name: "id_producto",
                label: "Producto",
                options: (data?.data || [])
                  .filter((p) => p.estado)
                  .map((p) => [p.id_producto, p.codigo + " · " + p.nombre]),
                required: true,
              },
              ...(form === "movimientos"
                ? [
                    {
                      name: "tipo",
                      label: "Tipo",
                      options: [
                        ["ENTRADA", "Entrada"],
                        ["SALIDA", "Salida"],
                      ],
                      required: true,
                    },
                  ]
                : []),
              {
                name: form === "conteos" ? "cantidad_contada" : "cantidad",
                label: form === "conteos" ? "Cantidad contada" : "Cantidad",
                type: "number",
                min: form === "conteos" ? 0 : 1,
                step: 1,
                required: true,
              },
              textField("motivo", "Motivo (letras y espacios)", true),
            ]}
            onCancel={() => setForm(null)}
            onSave={async (d) => {
              await api("/inventario/" + form, { method: "POST", body: d });
              setForm(null);
              load();
            }}
          />
        </Modal>
      )}
    </>
  );
}

export function Purchases() {
  const { data, error, load } = useLoad("/compras"),
    [open, setOpen] = useState(false);
  return (
    <>
      <Heading
        title="Compras"
        description="Registra abastecimientos y actualiza tu inventario."
      >
        <button className="btn" onClick={() => setOpen(true)}>
          <Plus size={18} /> Nueva compra
        </button>
      </Heading>
      <Notice message={error} />
      <section className="surface">
        <Table
          data={data?.data}
          columns={[
            ["numero_factura", "Factura"],
            ["fecha", "Fecha", fecha],
            ["razon_social", "Proveedor"],
            ["metodo_pago", "Método"],
            moneyColumn("total", "Total"),
          ]}
        />
      </section>
      {open && (
        <Modal title="Registrar compra" onClose={() => setOpen(false)}>
          <RecordForm
            fields={[
              {
                name: "id_proveedor",
                label: "Proveedor",
                options: (data?.proveedores || []).map((p) => [
                  p.id_proveedor,
                  p.razon_social,
                ]),
                required: true,
              },
              {
                name: "id_producto",
                label: "Producto",
                options: (data?.productos || [])
                  .filter((p) => p.estado)
                  .map((p) => [p.id_producto, p.nombre]),
                required: true,
              },
              textField("numero_factura", "Número de factura"),
              {
                name: "cantidad",
                label: "Cantidad",
                type: "number",
                min: 1,
                step: 1,
                required: true,
              },
              {
                name: "costo_unitario",
                label: "Costo unitario Q",
                type: "number",
                min: 0,
                step: ".01",
                required: true,
              },
              {
                name: "metodo_pago",
                label: "Método de pago",
                options: [
                  "EFECTIVO",
                  "TARJETA",
                  "TRANSFERENCIA",
                  "CRÉDITO",
                ].map((m) => [m, m]),
                required: true,
              },
            ]}
            onCancel={() => setOpen(false)}
            onSave={async (d) => {
              await api("/compras", { method: "POST", body: d });
              setOpen(false);
              load();
            }}
          />
        </Modal>
      )}
    </>
  );
}

export function Reports({ can }) {
  const [filter, setFilter] = useState(""),
    { data, error } = useLoad("/reportes" + filter),
    [exportError, setExportError] = useState("");
  return (
    <>
      <Heading
        title="Reportes de ventas"
        description={
          can("ventas.todas")
            ? "Información para decidir con confianza."
            : "Consulta y exporta únicamente tus ventas."
        }
      >
        <button className="btn tonal" onClick={() => window.print()}>
          <Printer size={17} /> Imprimir
        </button>
        <button
          className="btn"
          onClick={() =>
            download("/reportes/excel" + filter, "Ventas.xlsx").catch((e) =>
              setExportError(e.message),
            )
          }
        >
          <Download size={17} /> Descargar Excel
        </button>
      </Heading>
      <Notice message={error || exportError} />
      <form
        className="surface filter-bar"
        onSubmit={(e) => {
          e.preventDefault();
          const f = new FormData(e.target);
          setFilter("?" + new URLSearchParams(f).toString());
        }}
      >
        <label className="field">
          <span>Desde</span>
          <input
            type="date"
            name="desde"
            required
            defaultValue={data?.desde}
            key={"a" + data?.desde}
          />
        </label>
        <label className="field">
          <span>Hasta</span>
          <input
            type="date"
            name="hasta"
            required
            defaultValue={data?.hasta}
            key={"b" + data?.hasta}
          />
        </label>
        <button className="btn tonal">Aplicar filtro</button>
      </form>
      {data && (
        <>
          <div className="metric-grid compact">
            <section className="metric">
              <span>Ventas en el período</span>
              <strong>{data.resumen.cantidad}</strong>
            </section>
            <section className="metric">
              <span>Total vendido</span>
              <strong>{q(data.resumen.total)}</strong>
            </section>
          </div>
          <div className="dashboard-grid">
            <ChartPanel data={data.dias} title="Ventas por día" />
            <section className="surface">
              <h2>Productos más vendidos</h2>
              <Table
                data={data.productos}
                columns={[
                  ["nombre", "Producto"],
                  ["cantidad", "Unidades"],
                  moneyColumn("total", "Importe"),
                ]}
              />
            </section>
          </div>
          <section className="surface section-space">
            <h2>Detalle de ventas</h2>
            <Table
              data={data.ventas}
              columns={[
                ["numero_ticket", "Ticket"],
                ["fecha_hora", "Fecha", fecha],
                ["cliente", "Cliente"],
                ["cajero", "Cajero"],
                moneyColumn("total", "Total"),
              ]}
            />
          </section>
        </>
      )}
    </>
  );
}
