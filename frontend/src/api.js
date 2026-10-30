// El access token vive solo en memoria; la cookie refresh es HttpOnly.
let accessToken = null;
let refreshFlight = null;
const csrf = () =>
  document.cookie
    .split("; ")
    .find((c) => c.startsWith("csrf_refresh_token="))
    ?.split("=")[1] || "";

export async function refreshSession() {
  if (!refreshFlight) {
    const rotate = async () => {
      const res = await fetch("/api/auth/refresh", {
        method: "POST",
        credentials: "same-origin",
        headers: { "X-CSRF-TOKEN": csrf() },
      });
      const data = await res.json();
      if (!res.ok) {
        accessToken = null;
        throw new Error(data.error || "Inicia sesión nuevamente.");
      }
      accessToken = data.access_token;
    };
    // Las pestañas comparten la cookie: serializar la rotación entre ellas.
    refreshFlight = (
      navigator.locks
        ? navigator.locks.request("puntocom-refresh", rotate)
        : rotate()
    ).finally(() => {
      refreshFlight = null;
    });
  }
  return refreshFlight;
}

export async function api(path, options = {}, retry = true) {
  const headers = {
    ...(options.body ? { "Content-Type": "application/json" } : {}),
    ...options.headers,
  };
  if (accessToken) headers.Authorization = "Bearer " + accessToken;
  const res = await fetch("/api" + path, {
    ...options,
    headers,
    credentials: "same-origin",
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  if (res.status === 401 && retry && !path.startsWith("/auth/login")) {
    try {
      await refreshSession();
    } catch (error) {
      window.dispatchEvent(new Event("session-ended"));
      throw error;
    }
    return api(path, options, false);
  }
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.error || "No se pudo completar la operación.");
  }
  if (options.download) return res.blob();
  return res.json();
}

export async function signIn(correo, password) {
  accessToken = null;
  const data = await api("/auth/login", {
    method: "POST",
    body: { correo, password },
  });
  if (data.requiere_2fa) return data;
  return completeSignIn(data);
}
async function completeSignIn(data) {
  accessToken = data.access_token;
  const usuario = await api("/auth/me");
  if (data.uso_respaldo) usuario.aviso_seguridad = "Ingresaste con un código de respaldo. Ya no se puede volver a usar; revisa los restantes en Mi seguridad.";
  return usuario;
}
export async function verifySecondFactor(reto, codigo) {
  const data = await api("/auth/login/segundo-factor", { method: "POST", body: { reto, codigo } }, false);
  return completeSignIn(data);
}
export async function changeSecurity(accion, body) {
  const data = await api("/auth/mfa/" + accion, { method: "POST", body });
  if (data.access_token) accessToken = data.access_token;
  return data;
}
export async function signOut() {
  const res = await fetch("/api/auth/logout", {
    method: "POST",
    credentials: "same-origin",
    headers: { "X-CSRF-TOKEN": csrf() },
  });
  if (!res.ok && res.status !== 401)
    throw new Error("No se pudo cerrar la sesión. Intenta nuevamente.");
  accessToken = null;
}
export async function download(path, name) {
  const blob = await api(path, { download: true });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}
