import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  Routes,
  Route,
  NavLink,
  Navigate,
  useLocation,
  useNavigate,
} from "react-router-dom";
import * as M from "@materializecss/materialize";
import {
  LayoutDashboard,
  ShoppingCart,
  Package,
  Warehouse,
  Tags,
  Users,
  Truck,
  ShoppingBag,
  Receipt,
  Wallet,
  BarChart3,
  ShieldCheck,
  Menu,
  LogOut,
  X,
  ArrowRight,
  Eye,
  EyeOff,
  CheckCircle2,
  History,
} from "lucide-react";
import { api, refreshSession, signIn, signOut, verifySecondFactor } from "./api";
import Auditoria from "./Auditoria";
import Seguridad from "./Seguridad";
import Informes from "./Informes";
import Herramientas from "./Herramientas";
import Pagos from "./Pagos";
import { Notice } from "./components";
import {
  Dashboard,
  Resource,
  POS,
  Sales,
  Ticket,
  Cash,
  Inventory,
  Purchases,
  Reports,
} from "./pages";

const navigation = [
  ["/", "Panel principal", LayoutDashboard, "configuracion.gestionar"],
  ["/pos", "Punto de venta", ShoppingCart, "ventas.registrar"],
  ["/productos", "Productos", Package, "productos.ver"],
  ["/inventario", "Inventario", Warehouse, "inventario.ver"],
  ["/categorias", "Categorías", Tags, "productos.gestionar"],
  ["/clientes", "Clientes", Users, "clientes.ver"],
  ["/proveedores", "Proveedores", Truck, "proveedores.ver"],
  ["/compras", "Compras", ShoppingBag, "proveedores.gestionar"],
  ["/ventas", "Ventas", Receipt, "ventas.ver"],
  ["/caja", "Caja", Wallet, "ventas.registrar"],
  ["/pagos", "Pagos y saldos", Wallet, "pagos.cobrar"],
  ["/reportes", "Reportes", BarChart3, "reportes.consultar"],
  ["/usuarios", "Usuarios y permisos", ShieldCheck, "usuarios.gestionar"],
  ["/auditoria", "Bitácora de auditoría", History, "auditoria.ver"],
  ["/seguridad", "Mi seguridad", ShieldCheck, "seguridad.propia"],
  ["/herramientas", "Planificación", BarChart3, "herramientas.ver"],
];
const home = (user) =>
  user.rol === "Administrador"
    ? "/"
    : user.rol === "Cajero"
      ? "/pos"
      : "/inventario";

function Login({ onLogin }) {
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [show, setShow] = useState(false),
    [challenge, setChallenge] = useState(null),
    [backup, setBackup] = useState(false),
    [remaining, setRemaining] = useState(300);
  useEffect(() => {
    if (!challenge) return;
    const update = () => setRemaining(Math.max(0, Math.ceil((challenge.expires - Date.now()) / 1000)));
    update();
    const timer = setInterval(update, 1000);
    return () => clearInterval(timer);
  }, [challenge]);
  async function submit(e) {
    e.preventDefault();
    const data = new FormData(e.target);
    setBusy(true);
    setError("");
    try {
      if (challenge) {
        onLogin(await verifySecondFactor(challenge.reto, data.get("codigo")));
      } else {
        const result = await signIn(data.get("correo"), data.get("password"));
        if (result.requiere_2fa) {
          setChallenge({ reto: result.reto, correo: data.get("correo"), expires: Date.now() + result.expira_en * 1000 });
          setShow(false);
        } else onLogin(result);
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="login-layout">
      <section className="login-story">
        <a className="brand" href="/">
          <span className="brand-mark">
            pc<span>•</span>
          </span>
          <strong>PUNTO COM</strong>
        </a>
        <div className="story-content">
          <span className="story-label">GESTIÓN COMERCIAL</span>
          <h1>
            Más control.
            <br />
            Más tiempo para
            <br />
            <span>tu negocio.</span>
          </h1>
          <p>Ventas, inventario y clientes conectados en un mismo lugar.</p>
          <div className="story-points">
            <span>
              <CheckCircle2 size={18} /> Operaciones organizadas
            </span>
            <span>
              <CheckCircle2 size={18} /> Información siempre a mano
            </span>
            <span>
              <CheckCircle2 size={18} /> Acceso según tu perfil
            </span>
          </div>
        </div>
        <small>Servicios Informáticos Punto Com · Chiquimula</small>
      </section>
      <main className="login-main">
        <form className="login-form" onSubmit={submit} key={challenge ? "factor" : "password"}>
          <div className="login-mobile-brand">
            <span className="brand-mark">
              pc<span>•</span>
            </span>
            <strong>PUNTO COM</strong>
          </div>
          <span className="eyebrow">BIENVENIDO DE NUEVO</span>
          <h2>{challenge ? "Verifica tu identidad" : "Inicia tu jornada"}</h2>
          <p className="muted">{challenge ? "Completa el ingreso de " + challenge.correo + "." : "Ingresa con tu cuenta para continuar."}</p>
          <Notice message={error} />
          {!challenge ? <><label className="field">
            <span>Correo electrónico</span>
            <input
              type="email"
              name="correo"
              autoComplete="username"
              placeholder="tu.correo@ejemplo.com"
              required
              autoFocus
            />
          </label>
          <label className="field">
            <span>Contraseña</span>
            <div className="password-field">
              <input
                type={show ? "text" : "password"}
                name="password"
                autoComplete="current-password"
                placeholder="Ingresa tu contraseña"
                required
              />
              <button
                className="icon-button"
                type="button"
                aria-label={show ? "Ocultar contraseña" : "Mostrar contraseña"}
                onClick={() => setShow(!show)}
              >
                {show ? <EyeOff size={20} /> : <Eye size={20} />}
              </button>
            </div>
          </label>
          </> : <>
            <p>{backup ? "Escribe uno de tus códigos de respaldo sin utilizar." : "Escribe los 6 dígitos que aparecen en tu aplicación autenticadora."}</p>
            <label className="field"><span>{backup ? "Código de respaldo" : "Código del autenticador"}</span>
              <input key={backup ? "backup" : "totp"} name="codigo" type="text" inputMode={backup ? "text" : "numeric"}
                pattern={backup ? "[0-9a-fA-F \\-]{20,30}" : "[0-9]{6}"} maxLength={backup ? 30 : 6}
                autoComplete="one-time-code" autoFocus required className="otp-input" /></label>
            <p className="muted" role="status">{remaining ? `Este paso vence en ${Math.floor(remaining / 60)}:${String(remaining % 60).padStart(2, "0")}.` : "Este paso expiró. Vuelve a ingresar tu contraseña."}</p>
            <button className="btn-flat security-text-button" type="button" disabled={busy} onClick={() => { setBackup(!backup); setError(""); }}>
              {backup ? "Usar aplicación autenticadora" : "Usar un código de respaldo"}</button>
          </>}
          <button
            className="btn waves-effect full-width login-submit"
            disabled={busy || (challenge && !remaining)}
          >
            {busy ? "Verificando…" : challenge ? "Verificar e ingresar" : "Iniciar sesión"}
            <ArrowRight size={18} />
          </button>
          {challenge && <button className="btn-flat full-width" type="button" disabled={busy} onClick={() => { setChallenge(null); setBackup(false); setError(""); }}>Volver al ingreso</button>}
          <p className="login-help">
            ¿Necesitas ayuda para ingresar?
            <br />
            Comunícate con el administrador del sistema.
          </p>
          <div className="login-security">
            <ShieldCheck size={16} /> Tu información, protegida.
          </div>
        </form>
        <small className="login-footer">
          Punto Com · Gestión de ventas e inventario
        </small>
      </main>
    </div>
  );
}

function Shell({ user, setUser }) {
  const [drawerOpen, setDrawerOpen] = useState(false),
    [logoutError, setLogoutError] = useState(""),
    [loggingOut, setLoggingOut] = useState(false);
  const menuRef = useRef(null),
    instance = useRef(null),
    mainRef = useRef(null),
    triggerRef = useRef(null);
  const location = useLocation(),
    navigate = useNavigate();
  const can = useCallback((p) => user.permisos.includes(p), [user]);
  const title =
    navigation.find(
      (n) =>
        n[0] ===
        (location.pathname.startsWith("/ventas/")
          ? "/ventas"
          : location.pathname),
    )?.[1] || "Punto Com";
  useEffect(() => {
    const syncAccessibility = () => {
      const visible = window.innerWidth > 992 || instance.current?.isOpen;
      menuRef.current.setAttribute("aria-hidden", String(!visible));
      menuRef.current.querySelectorAll("a[href]").forEach((link) => {
        link.tabIndex = visible ? 0 : -1;
      });
    };
    instance.current = M.Sidenav.init(menuRef.current, {
      draggable: true,
      onOpenStart: () => {
        if (window.innerWidth <= 992) setDrawerOpen(true);
      },
      onOpenEnd: () => {
        syncAccessibility();
        if (window.innerWidth <= 992)
          menuRef.current.querySelector(".drawer-close")?.focus();
      },
      onCloseEnd: () => {
        syncAccessibility();
        setDrawerOpen(false);
        if (window.innerWidth <= 992) triggerRef.current?.focus();
      },
    });
    const resize = () => {
      if (window.innerWidth > 992) {
        setDrawerOpen(false);
      }
      requestAnimationFrame(syncAccessibility);
    };
    syncAccessibility();
    window.addEventListener("resize", resize);
    return () => {
      instance.current?.destroy();
      window.removeEventListener("resize", resize);
    };
  }, []);
  useEffect(() => {
    if (window.innerWidth <= 992) instance.current?.close();
  }, [location.pathname]);
  useEffect(() => {
    if (mainRef.current) mainRef.current.inert = drawerOpen;
    function trap(e) {
      if (!drawerOpen) return;
      if (e.key === "Escape") {
        instance.current?.close();
        return;
      }
      if (e.key === "Tab") {
        const nodes = [
          ...menuRef.current.querySelectorAll("a[href],button:not([disabled])"),
        ].filter((el) => el.getClientRects().length);
        const first = nodes[0],
          last = nodes.at(-1);
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }
    }
    document.addEventListener("keydown", trap);
    return () => document.removeEventListener("keydown", trap);
  }, [drawerOpen]);
  async function logout() {
    setLoggingOut(true);
    try {
      await signOut();
      setUser(null);
      navigate("/login");
    } catch (e) {
      setLogoutError(e.message);
    } finally {
      setLoggingOut(false);
    }
  }
  async function refreshUser() {
    const updated = await api("/auth/me");
    setUser(updated);
  }
  const protect = (permission, view) =>
    can(permission) ? (
      view
    ) : (
      <section className="surface">
        <h1>Acceso restringido</h1>
        <p>Tu perfil no tiene permiso para esta sección.</p>
        <NavLink to={home(user)} className="btn">
          Volver a mi inicio
        </NavLink>
      </section>
    );
  return (
    <>
      <a className="skip-link" href="#main-content">
        Ir al contenido
      </a>
      <ul
        id="app-navigation"
        ref={menuRef}
        className="sidenav sidenav-fixed app-navigation"
        role="navigation"
        aria-label="Menú principal"
      >
        <li className="brand-row">
          <NavLink to={home(user)} className="brand">
            <span className="brand-mark">
              pc<span>•</span>
            </span>
            <span>
              <strong>PUNTO COM</strong>
              <small>Gestión comercial</small>
            </span>
          </NavLink>
          <button
            className="icon-button drawer-close"
            aria-label="Cerrar menú"
            onClick={() => instance.current?.close()}
          >
            <X size={21} />
          </button>
        </li>
        <li className="nav-section-label">ESPACIO DE TRABAJO</li>
        {navigation
          .filter((n) => can(n[3]))
          .map(([path, label, Icon]) => (
            <li key={path}>
              <NavLink
                to={path}
                end={path === "/"}
                className={({ isActive }) =>
                  "waves-effect nav-item " + (isActive ? "active" : "")
                }
              >
                <Icon size={20} aria-hidden="true" />
                <span>{label}</span>
              </NavLink>
            </li>
          ))}
        <li className="sidebar-foot">
          <span className="online-dot" /> Conectado a tu negocio
        </li>
      </ul>
      <div className="app-main" ref={mainRef}>
        <header className="app-topbar">
          <div className="topbar-left">
            <button
              className="icon-button menu-button"
              ref={triggerRef}
              aria-label="Abrir menú"
              aria-controls="app-navigation"
              aria-expanded={drawerOpen}
              onClick={() => instance.current?.open()}
            >
              <Menu size={24} />
            </button>
            <span className="breadcrumb-brand">
              Punto Com <span>/</span>
            </span>
            <strong>{title}</strong>
          </div>
          <div className="topbar-right">
            <span className="today">
              {new Intl.DateTimeFormat("es-GT", {
                day: "numeric",
                month: "short",
                timeZone: "America/Guatemala",
              }).format(new Date())}
            </span>
            <span className="user-avatar" title={user.nombre}>
              {user.nombre[0]}
            </span>
            <div className="user-caption">
              <strong>{user.nombre}</strong>
              <small>{user.rol}</small>
            </div>
            <button
              className="icon-button"
              disabled={loggingOut}
              onClick={logout}
              aria-label="Cerrar sesión"
              title="Cerrar sesión"
            >
              <LogOut size={20} />
            </button>
          </div>
        </header>
        <main className="app-content" id="main-content" tabIndex="-1">
          <Notice message={logoutError} />
          <Notice message={user.aviso_seguridad} />
          <Routes>
            <Route
              path="/"
              element={
                can("configuracion.gestionar") ? (
                  <Dashboard />
                ) : (
                  <Navigate to={home(user)} replace />
                )
              }
            />
            <Route
              path="/pos"
              element={protect("ventas.registrar", <POS can={can} />)}
            />
            {[
              "productos",
              "categorias",
              "clientes",
              "proveedores",
              "usuarios",
            ].map((module) => (
              <Route
                key={module}
                path={"/" + module}
                element={protect(
                  navigation.find((n) => n[0] === "/" + module)[3],
                  <Resource
                    key={module}
                    module={module}
                    can={can}
                    refreshUser={refreshUser}
                  />,
                )}
              />
            ))}
            <Route
              path="/inventario"
              element={protect("inventario.ver", <Inventory can={can} />)}
            />
            <Route
              path="/compras"
              element={protect("proveedores.gestionar", <Purchases />)}
            />
            <Route
              path="/ventas"
              element={protect("ventas.ver", <Sales can={can} />)}
            />
            <Route
              path="/ventas/:id"
              element={protect("ventas.ver", <Ticket />)}
            />
            <Route
              path="/caja"
              element={protect("ventas.registrar", <Cash />)}
            />
            <Route
              path="/reportes"
              element={protect("reportes.consultar", <Informes can={can} />)}
            />
            <Route path="/auditoria" element={protect("auditoria.ver", <Auditoria />)} />
            <Route path="/seguridad" element={protect("seguridad.propia", <Seguridad user={user} />)} />
            <Route path="/pagos" element={protect("pagos.cobrar", <Pagos can={can} />)} />
            <Route path="/herramientas" element={protect("herramientas.ver", <Herramientas />)} />
            <Route path="*" element={<Navigate to={home(user)} replace />} />
          </Routes>
        </main>
        <footer className="app-footer">
          Punto Com <span>Hecho para acompañar tu jornada.</span>
        </footer>
      </div>
    </>
  );
}

function App() {
  const [user, setUser] = useState(null),
    [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    refreshSession()
      .then(() => api("/auth/me"))
      .then((u) => {
        if (active) setUser(u);
      })
      .catch(() => {})
      .finally(() => {
        if (active) setLoading(false);
      });
    const ended = () => setUser(null);
    window.addEventListener("session-ended", ended);
    return () => {
      active = false;
      window.removeEventListener("session-ended", ended);
    };
  }, []);
  if (loading)
    return (
      <div className="loading-screen">
        <span className="brand-mark">
          pc<span>•</span>
        </span>
        <p>Preparando tu espacio de trabajo…</p>
      </div>
    );
  return user ? (
    <Shell user={user} setUser={setUser} />
  ) : (
    <Login onLogin={setUser} />
  );
}
export default App;
