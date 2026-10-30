# Punto Com POS

Sistema académico de punto de venta en español para Guatemala. Frontend React y Materialize; API Flask separada; PostgreSQL. Incluye permisos, JWT con refresh rotatorio, 2FA TOTP, auditoría, compras, ventas, inventario, caja, cuentas a crédito y cinco informes en PDF y Excel.

Esta copia pública se instala con una base propia. No contiene contraseñas, usuarios de la demostración publicada, copias de bases ni archivos privados. Los datos iniciales son ficticios. Clonar el código no concede acceso a la base del autor.

## Requisitos

- Python 3.11 o posterior.
- Node.js 22 y pnpm 10.20.0 (instalar desde los distribuidores oficiales).
- PostgreSQL 14 o posterior y la herramienta psql, o pgAdmin para ejecutar los scripts.
- Internet para instalar dependencias y consultar los tres proveedores externos.

## Instalación local en Windows

Clona este repositorio y abre su carpeta en Visual Studio Code:

```powershell
git clone https://github.com/DaavidJ22/puntocom-pos-publico.git
cd puntocom-pos-publico
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

En `.env`, configura DB_HOST, DB_PORT, DB_NAME, DB_USER y DB_PASSWORD para tu PostgreSQL. La plantilla usa el puerto 5432 y la base puntocom_pos. Deja DATABASE_URL vacía para usar esos valores. Define SECRET_KEY con una clave privada estable, generada con:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
```

Copia ese resultado únicamente a tu `.env`. Nunca lo subas al repositorio. Puedes generar otra clave para JWT_SECRET_KEY; si la dejas vacía se utiliza SECRET_KEY.

### Crear la base y sus tablas

Crea una base **nueva y vacía** llamada puntocom_pos desde pgAdmin o con `createdb -U postgres puntocom_pos`. Ejecuta los nueve scripts de `sql/` en orden numérico. No ejecutes el esquema inicial sobre una base que ya utilizas. En PowerShell, con psql disponible y la base creada:

```powershell
Get-ChildItem sql/*.sql | Sort-Object Name | ForEach-Object {
    psql -X -h localhost -p 5432 -U postgres -d puntocom_pos -v ON_ERROR_STOP=1 -f $_.FullName
    if ($LASTEXITCODE -ne 0) { throw "La instalación se detuvo; revisa el último script." }
}
```

Ajusta host, puerto, usuario y base para que coincidan con `.env`. psql solicita tu contraseña de PostgreSQL. Los scripts crean tablas, relaciones, catálogos y dos productos ficticios con existencias iniciales. No incluyen cuentas con contraseña compartida.

Crea tu administrador; el comando solicita nombre, correo y una contraseña de al menos 12 caracteres:

```powershell
.\.venv\Scripts\python.exe -m flask --app app crear-admin
```

### Iniciar backend y frontend

Terminal 1, desde la raíz del proyecto:

```powershell
.\.venv\Scripts\python.exe -m backend.app
```

Terminal 2:

```powershell
cd frontend
pnpm install --frozen-lockfile
pnpm dev
```

Abre **http://127.0.0.1:5173** e ingresa con el administrador que creaste. La API escucha en 5001; Vite redirige `/api` a ese puerto. Mantén ambas terminales abiertas. Para iniciar una instalación propia no necesitas el PostgreSQL portable ni los archivos `.local` de otra computadora; utiliza los comandos anteriores.

En Linux/macOS, usa `python3 -m venv .venv` y `.venv/bin/python` en lugar del ejecutable de Windows. Los scripts SQL y los comandos del frontend son los mismos.

## Primer recorrido

1. Ingresa y revisa productos, existencias y proveedores.
2. Abre un turno de caja y realiza una venta de prueba con los productos ficticios.
3. Consulta ticket, movimientos y reportes.
4. Crea un proveedor y registra una compra para verificar la entrada de inventario.
5. Crea usuarios propios con los perfiles Cajero y Bodeguero para comprobar los permisos.

## APIs externas

En **Planificación** se integran Frankfurter (USD/GTQ), Nager.Date (feriados de Guatemala) y Google Public DNS (registros MX del dominio de un contacto). Son consultas auxiliares; no procesan pagos ni verifican la existencia de un buzón. Si un proveedor falla, se muestra el estado y la operación principal puede continuar. Consulta [APIs externas](docs/APIS_EXTERNAS.md).

## Pruebas

Las pruebas aisladas se ejecutan sin conectar la base de la demostración:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

Las suites de `tests/postgres/` y `tests/api/` requieren un PostgreSQL de pruebas independiente y su configuración; no deben apuntarse a una base con datos reales. Para compilar la interfaz ejecuta `pnpm build` desde frontend.

## Publicación propia

El uso local no requiere Render, Vercel ni una cuenta de Neon. Para desplegar, utiliza tu propia base y configura secretos en el proveedor. `render.yaml` contiene la plantilla del backend. Antes de publicar el frontend, genera su configuración con `scripts/preparar_frontend_nube.py` y la URL de tu propia API; el archivo `frontend/vercel.json` contiene una dirección de ejemplo. No utiliza la API publicada del autor.

## Estructura

- `frontend/`: React, Materialize y navegación.
- `backend/`: API, autenticación, informes y proveedores externos.
- `sql/`: esquema, datos ficticios y migraciones ordenadas.
- `tests/`: comprobaciones aisladas, PostgreSQL y API.
- `docs/`: documentación funcional seleccionada.
- Archivos Python de la raíz: servicios de negocio compartidos y aplicación con plantillas.

La versión de presentación utiliza React en el puerto 5173. `app.py` y `templates/` conservan la aplicación con plantillas, que utiliza otro flujo de inicio; no confundas sus sesiones con los tokens de la API.
