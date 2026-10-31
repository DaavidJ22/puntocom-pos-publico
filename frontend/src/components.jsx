import React, { useEffect, useRef, useState } from "react";
import {
  X,
  Search,
  ArrowUpRight,
  PackageOpen,
  AlertCircle,
} from "lucide-react";
import Chart from "chart.js/auto";
import { constraintsFor, acceptsEdit } from "./validation";

export const q = (n) =>
  "Q " +
  Number(n || 0).toLocaleString("es-GT", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
export const fecha = (d) =>
  d
    ? new Date(d).toLocaleString("es-GT", {
        dateStyle: "short",
        timeStyle: "short",
      })
    : "—";
export function Heading({ title, description, children }) {
  return (
    <div className="page-heading">
      <div>
        <p className="eyebrow">TU NEGOCIO, EN ORDEN</p>
        <h1>{title}</h1>
        {description && <p className="page-description">{description}</p>}
      </div>
      <div className="heading-actions">{children}</div>
    </div>
  );
}
export function Empty({ text = "Todavía no hay registros." }) {
  return (
    <div className="empty">
      <PackageOpen size={32} />
      <p>{text}</p>
    </div>
  );
}
export function Notice({ message }) {
  return message ? (
    <div className="notice" role="alert">
      <AlertCircle size={18} />
      <span>{message}</span>
    </div>
  ) : null;
}
export function Badge({ value }) {
  const good = [
    true,
    "COMPLETADA",
    "APROBADA",
    "Disponible",
    "ABIERTO",
  ].includes(value);
  const bad = ["ANULADA", "RECHAZADA", "Agotado"].includes(value);
  return (
    <span className={"status " + (good ? "good" : bad ? "bad" : "neutral")}>
      {typeof value === "boolean" ? (value ? "Activo" : "Inactivo") : value}
    </span>
  );
}
export function Table({ columns, data = [], empty }) {
  return (
    <div
      className="table-scroll"
      tabIndex="0"
      role="region"
      aria-label="Tabla de registros; desliza horizontalmente para ver más columnas"
    >
      <table
        className="highlight"
        style={{ minWidth: Math.min(1000, columns.length * 110) }}
      >
        <thead>
          <tr>
            {columns.map(([key, label]) => (
              <th key={key}>{label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr
              key={
                row.id_evento ||
                row.campo ||
                row.id_venta ||
                row.id_producto ||
                row.id_usuario ||
                i
              }
            >
              {columns.map(([key, label, render]) => (
                <td
                  key={key}
                  className={
                    /total|precio|costo|monto|fondo/.test(key) ? "numeric" : ""
                  }
                >
                  {render ? render(row[key], row) : String(row[key] ?? "—")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {!data.length && <Empty text={empty} />}
    </div>
  );
}
export function SearchBox({
  value,
  onChange,
  placeholder = "Buscar registros…",
}) {
  return (
    <div className="search-field">
      <Search size={18} />
      <input
        aria-label={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
      />
    </div>
  );
}
export function ChartPanel({
  data = [],
  title = "Ventas",
  description = "Importes en quetzales",
}) {
  const ref = useRef(null);
  useEffect(() => {
    const chart = new Chart(ref.current, {
      type: "bar",
      data: {
        labels: data.map((d) => String(d.fecha).slice(5)),
        datasets: [
          {
            label: title,
            data: data.map((d) => Number(d.total)),
            backgroundColor: "#3a72dd",
            borderRadius: 5,
            maxBarThickness: 34,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false } },
          y: {
            beginAtZero: true,
            ticks: { callback: (v) => "Q " + v },
            grid: { color: "#edf1f6" },
          },
        },
      },
    });
    return () => chart.destroy();
  }, [data, title]);
  return (
    <section className="surface">
      <div className="section-heading">
        <div>
          <h2>{title}</h2>
          <p>{description}</p>
        </div>
        <ArrowUpRight size={19} />
      </div>
      <div className="chart">
        <canvas
          ref={ref}
          role="img"
          aria-label={
            title +
            "; " +
            data.map((d) => `${d.fecha}: ${q(d.total)}`).join(", ")
          }
        />
      </div>
    </section>
  );
}
export function Modal({ title, onClose, children }) {
  const ref = useRef(null),
    close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    const dialog = ref.current;
    dialog.showModal();
    return () => {
      if (dialog.open) dialog.close();
    };
  }, []);
  return (
    <dialog
      className="modal app-modal"
      aria-label={title}
      ref={ref}
      onClose={() => close.current()}
      onClick={(e) => {
        if (e.target === ref.current) {
          const r = ref.current.getBoundingClientRect();
          if (
            e.clientX < r.left ||
            e.clientX > r.right ||
            e.clientY < r.top ||
            e.clientY > r.bottom
          )
            ref.current.close();
        }
      }}
    >
      <div className="modal-content">
        <div className="section-heading">
          <h2>{title}</h2>
          <button
            type="button"
            className="icon-button"
            aria-label="Cerrar diálogo"
            onClick={() => ref.current.close()}
          >
            <X size={22} />
          </button>
        </div>
        {children}
      </div>
    </dialog>
  );
}
export function Field({
  name,
  label,
  type = "text",
  options,
  required = false,
  value,
  onChange,
  min,
  max,
  step,
  minLength,
  maxLength,
  pattern,
  inputMode,
  title,
  autoComplete,
}) {
  const rules = constraintsFor(name);
  return (
    <label className="field">
      <span>
        {label}
        {required ? " *" : ""}
      </span>
      {options ? (
        <select
          className="browser-default"
          name={name}
          value={value ?? ""}
          onChange={onChange}
          required={required}
        >
          <option value="">Selecciona una opción</option>
          {options.map(([v, l]) => (
            <option value={v} key={v}>
              {l}
            </option>
          ))}
        </select>
      ) : (
        <input
          name={name}
          type={rules.type ?? type}
          required={required}
          value={value ?? ""}
          onChange={(e) => {
            if (acceptsEdit(name, e.target.value)) onChange(e);
          }}
          min={min}
          max={max}
          step={step}
          minLength={minLength ?? rules.minLength}
          maxLength={maxLength ?? rules.maxLength}
          pattern={pattern ?? rules.pattern}
          inputMode={inputMode ?? rules.inputMode}
          title={title ?? rules.title}
          autoComplete={autoComplete ?? rules.autoComplete}
        />
      )}
      {name === "telefono" && (
        <small>Opcional: 8 dígitos, sin espacios ni guiones.</small>
      )}
    </label>
  );
}
export function RecordForm({
  fields,
  initial = {},
  onSave,
  onCancel,
  submitLabel = "Guardar cambios",
}) {
  const [form, setForm] = useState(initial),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await onSave(form);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit}>
      <div className="form-grid">
        {fields.map((f) => (
          <Field
            {...f}
            key={f.name}
            value={form[f.name]}
            onChange={(e) => setForm({ ...form, [f.name]: e.target.value })}
          />
        ))}
      </div>
      <Notice message={error} />
      <div className="form-actions">
        <button type="button" className="btn tonal" onClick={onCancel}>
          Cancelar
        </button>
        <button className="btn waves-effect" disabled={busy}>
          {busy ? "Guardando…" : submitLabel}
        </button>
      </div>
    </form>
  );
}
