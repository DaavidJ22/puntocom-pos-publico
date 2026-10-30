# Autenticación de dos factores (2FA)

Implementación publicada en [Mi seguridad](https://puntocom-demo-analisis2.vercel.app/seguridad). Pasaron 103 pruebas generales, 123 de PostgreSQL y 58 de API (19 escenarios de 2FA), más 41 comprobaciones públicas de sesiones, permisos, auditoría y consulta del estado 2FA. Se revisó la pantalla en 1280 px y 390 px. No se activaron factores en las cuentas reales/de demostración. Evidencias: `resultado_2fa.json`, `resultado_api.json` y `resultado_nube.json`.

Cada usuario tiene **Mi seguridad** en el menú. La función está disponible para Administrador, Cajero y Bodeguero y solo modifica la cuenta autenticada. Instalar o desplegar no activa ninguna cuenta automáticamente.

## Activación personal

1. Ingresar con la cuenta que se desea proteger y abrir **Mi seguridad**.
2. Escribir la contraseña actual y pulsar **Preparar vinculación**.
3. En una aplicación autenticadora compatible con TOTP, añadir una cuenta mediante el QR. Si se trabaja desde el mismo celular, utilizar la clave manual. El QR se genera dentro del servidor, sin enviar la semilla a servicios externos.
4. Confirmar la contraseña y un código de 6 dígitos del autenticador. La vinculación dura 10 minutos y pertenece a la sesión que la inició. Solo entonces se activa 2FA.
5. Guardar los 10 códigos de respaldo en un lugar privado separado del celular. Solo se muestran una vez; el servidor conserva sus huellas SHA-256. Cada código exige también la contraseña y se consume una sola vez.

Después de activar, esperar a que cambie el código antes de usarlo en otro ingreso: no se acepta reutilización. Mantener automática la fecha/hora del celular. La configuración mantiene una sesión nueva para el usuario y revoca sus sesiones anteriores.

La vinculación del autenticador y la confirmación deben realizarlas personalmente los integrantes. No compartir capturas del QR, la clave manual, los códigos ni contraseñas en el chat o repositorio.

## Ingreso y recuperación

Sin 2FA activo, el ingreso mantiene su comportamiento anterior. Con 2FA, una contraseña correcta entrega únicamente un reto opaco de cinco minutos: no entrega access token ni refresh cookie. El segundo paso verifica el autenticador o un respaldo antes de emitir una sesión completa.

Si se pierde el celular: ingresar con contraseña y un respaldo sin usar. Desde **Mi seguridad**, se puede desactivar 2FA usando la contraseña y otro respaldo, para después vincular un nuevo autenticador. Renovar respaldos también exige contraseña y un segundo factor y deja inutilizables los anteriores. No existe un botón administrativo que omita estas verificaciones. Si se pierden autenticador y todos los respaldos, se requiere un procedimiento manual de recuperación de identidad; no se añadió un bypass ni un restablecimiento automático por correo.

## Controles implementados

- TOTP estándar de seis dígitos/30 segundos con ventana de un paso anterior/posterior; se conserva el último paso aceptado para rechazar reutilizaciones.
- Retos de un solo uso con cinco intentos, vinculados a la versión de MFA y a la credencial que autorizó el primer paso. Caducan al cambiar contraseña/configuración o al desactivar la cuenta.
- Límites persistentes en PostgreSQL: veinte contraseñas fallidas por correo/15 minutos; diez verificaciones de segundo factor por usuario/5 minutos, incluso al generar retos nuevos; diez intentos de configuración/5 minutos. El éxito limpia su contador. Se aplica protección por cuenta, sin inferir IPs desde cabeceras de proxy no confiables.
- Bloqueo del usuario durante los cambios; códigos de respaldo y TOTP se consumen dentro de la misma transacción que crea la sesión. Dos solicitudes concurrentes no pueden consumir el mismo respaldo.
- Activar, desactivar o renovar respaldos revoca las sesiones y retos anteriores. La interfaz antigua rechaza el ingreso y sus cookies existentes para usuarios que activen 2FA; no permite omitirlo.
- Secretos TOTP cifrados con Fernet y una clave derivada mediante HKDF-SHA256. Se utiliza `MFA_ENCRYPTION_KEY` si está configurada; de lo contrario se deriva del `SECRET_KEY` estable del servidor, con separación de propósito. Nunca se deriva de un dato público ni de la clave JWT.
- Bitácora con preparación, activación, solicitudes, verificaciones, rechazos, respaldos utilizados/renovados y desactivación. Las tablas privadas de MFA no tienen disparadores que copien sus filas a la bitácora.
- No se almacenan códigos TOTP, semillas en claro ni respaldos utilizables en auditoría. Las respuestas de API siguen usando `no-store`, HTTPS/cookies seguras en producción y control de origen.

## Datos y claves

La migración 08 añade `usuario_mfa`, `reto_mfa`, `codigo_respaldo` y `limite_auth`: veinte tablas y veintisiete relaciones en total. No altera ventas, stock, contraseñas ni el estado 2FA de cuentas existentes. Es repetible y la preparación de Render la incluye.

Para local, iniciar PostgreSQL, instalar `requirements.txt`, respaldar y ejecutar:

```text
.venv/Scripts/python.exe scripts/respaldo_bd.py
.venv/Scripts/python.exe scripts/migrar_mfa.py
```

Reiniciar la API. Mantener estable la clave de cifrado: cambiar `SECRET_KEY` sin una clave dedicada también cambia el cifrado de las semillas. Respaldar la clave privada por separado de la base, fuera del repositorio. Un respaldo todavía puede servir para recuperar acceso si falta la clave de cifrado; la semilla anterior no puede recuperarse sin su clave. No modificar claves de producción como parte de un despliegue rutinario.

## Verificación

Las pruebas locales usan cuentas y bases UUID desechables: vectores TOTP conocidos, cifrado, límites, caducidad, actor, recuperación, concurrencia, sesiones revocadas y bloqueo del acceso anterior. No activan 2FA en las cuentas personales/de presentación.

`scripts/verificar_nube.py --url https://puntocom-demo-analisis2.vercel.app --auditoria --seguridad` comprueba sesiones, permisos, auditoría y consulta privada del estado 2FA en el despliegue. **No activa MFA ni verifica un código personal en producción**. Si una cuenta ya está protegida, la prueba avisa que su ingreso requiere una comprobación manual.

Fuentes: [PyOTP](https://pyauth.github.io/pyotp/), [OWASP MFA](https://cheatsheetseries.owasp.org/cheatsheets/Multifactor_Authentication_Cheat_Sheet.html) y [Fernet](https://cryptography.io/en/latest/fernet/).
