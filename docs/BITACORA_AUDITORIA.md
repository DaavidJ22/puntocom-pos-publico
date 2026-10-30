# Bitácora de auditoría

Implementada en local y publicada. Validación: 98 pruebas generales, 123 de PostgreSQL y 39 de API; las bases temporales fueron eliminadas. Además pasaron 38 comprobaciones HTTPS contra el enlace público, incluidos los permisos de bitácora de los tres roles y la persistencia de accesos en Neon. Evidencia: `resultado_auditoria.json`, `resultado_api.json` y `resultado_nube.json` en esta carpeta.

El administrador accede desde **Bitácora de auditoría** en el menú. Puede filtrar por fechas, responsable, módulo, acción y número de registro, recorrer páginas y abrir el detalle de valores anteriores/nuevos. La fecha se muestra en America/Guatemala, aunque el dispositivo use otra zona horaria. Cajero y Bodeguero no pueden consultar el historial, ni siquiera llamando directamente a la API.

## Alcance

- Ventas, detalles y anulaciones; compras y sus detalles.
- Apertura/cierre de caja y movimientos de efectivo.
- Movimientos de inventario, conteos y aprobación/rechazo de ajustes.
- Altas, cambios, activaciones, desactivaciones y eliminaciones de productos, categorías, clientes, proveedores, usuarios y roles.
- En la API: inicio de sesión, credenciales rechazadas, renovación, cierre y detección de reutilización de refresh token. Un ingreso rechazado no se atribuye a la persona cuyo correo fue escrito.

La tabla `bitacora_auditoria` guarda fecha con zona horaria, identidad y nombre/rol del responsable en ese momento, módulo, entidad, referencia, acción, operación, valores anteriores/nuevos, transacción e identificador de petición. Una venta genera varias filas relacionadas por la misma petición: encabezado, detalle, stock y caja. No se presenta cada fila como una venta independiente.

## Consistencia y protección

La migración `sql/07_bitacora_auditoria.sql` instala disparadores sobre 14 tablas del negocio. El evento se guarda en la misma transacción que el cambio. Si falla la operación o su auditoría, ambas se revierten; una compra incompleta no queda registrada como exitosa.

El servidor establece el responsable con `set_config(..., true)` después de autenticarlo; el contexto termina con la transacción y no se conserva al reutilizar una conexión. No acepta nombres ni identificadores de responsables desde el formulario. La aplicación anterior también establece contexto para las modificaciones autenticadas. El SQL directo se identifica como `base_datos`, sin atribuirlo artificialmente a un usuario de la aplicación.

Los campos copiados se definen mediante listas positivas por tabla. No se almacenan contraseñas, hashes, JWT, cookies, conexión de base de datos ni cuerpos completos de solicitudes. Un cambio de contraseña solo deja una indicación de que fue modificada. Los datos comerciales permitidos (incluidos datos de contacto) solo son visibles al administrador.

El historial no tiene botones ni endpoints para editar o borrar. Un disparador rechaza UPDATE, DELETE y TRUNCATE de la bitácora. No hay FK al responsable para conservar su identificación histórica aunque su cuenta pueda eliminarse legítimamente. Estas medidas protegen el uso ordinario; el propietario de PostgreSQL todavía puede alterar el esquema o deshabilitar disparadores. No equivale a una bitácora externa con firma criptográfica.

## Instalación y comprobación

Local, con PostgreSQL iniciado y respaldo previo:

```text
.venv/Scripts/python.exe scripts/respaldo_bd.py
.venv/Scripts/python.exe scripts/migrar_auditoria.py
```

Reiniciar la API tras instalar. En Render, `backend.preparar_nube` aplica la migración al desplegar. Es aditiva y repetible: no elimina datos, no restablece claves y no inventa historial previo.

Las pruebas de API y PostgreSQL crean operaciones solo en una base UUID desechable, verifican valores, permisos, rollback, ausencia de secretos, conservación del autor, aislamiento entre solicitudes y rechazo a modificar el historial. El restablecimiento de fixtures desactiva temporalmente la protección solo en esa base identificada; esa excepción no existe en la aplicación ni en la migración.

Para demostrarla: ingresar como administrador, abrir la bitácora, filtrar por Accesos y consultar un inicio de sesión. Para cambios comerciales, efectuar una operación autorizada y revisar su referencia y detalle. Los hechos previos a la instalación no se reconstruyen. La auditoría de operaciones no sustituye respaldos ni validación con usuarios.

Fundamento: [disparadores de PostgreSQL 17](https://www.postgresql.org/docs/17/plpgsql-trigger.html) y [configuración local a la transacción](https://www.postgresql.org/docs/17/functions-admin.html#FUNCTIONS-ADMIN-SET).
