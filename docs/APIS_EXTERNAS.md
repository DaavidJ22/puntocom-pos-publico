# Tres APIs externas de planificación

La sección Planificación integra tres proveedores por HTTPS desde Flask, con JWT para los tres perfiles:

| Proveedor | Función | Uso en Punto Com |
| --- | --- | --- |
| Frankfurter v2 | Cambio USD/GTQ | Estimar importes de compras cotizadas en dólares |
| Nager.Date | Feriados de Guatemala | Planificar atención y pedidos |
| Google Public DNS | Registros MX de un dominio | Detectar posibles errores en dominios de contactos de clientes/proveedores |

No requieren cuentas nuevas, claves ni planes de pago para esta demostración. No se transmiten contraseñas, tokens, ventas ni nombres de contactos a los proveedores. Google recibe únicamente el dominio escrito por el usuario, nunca su correo completo. La pantalla informa esto antes de consultar; no envía correos ni comprueba la existencia de un buzón.

## Límites y significado

El cambio es orientativo, no es tasa oficial de Banguat ni oferta bancaria, y no modifica precios, cobros ni compras. Los feriados son la referencia del proveedor, sin garantía de cubrir todos los asuetos locales ni decidir horarios del negocio. El resultado DNS distingue dominio inexistente, MX configurado, Null MX (declara no recibir correo), ausencia de MX explícito y consulta fallida. No interpreta ausencia de MX como prueba absoluta de que el dominio no recibe correo: existe recepción implícita. Ningún resultado acredita identidad, propiedad de una cuenta o entrega de mensajes.

El pronóstico de Open-Meteo se probó localmente pero se descartó de la implementación final porque su API rechazó la conexión compartida de Render con HTTP 429. No se evade ese límite ni se cuenta como una cuarta integración. La función de dominios fue elegida como alternativa aplicable al registro de contactos.

## Seguridad, caché y fallos

Las URL de proveedores son constantes. Solo se aceptan el año actual/anterior/siguiente y dominios validados e internacionalizados con IDNA; no direcciones IP, correos completos ni URL. El dominio se utiliza como parámetro DNS codificado, nunca como host de una conexión. Se rechazan redirecciones, cuerpos superiores a 512 KiB, JSON inválido y contratos incoherentes. Tiempo de espera de red: cinco segundos por petición.

La caché del proceso está limitada a ocho entradas: cambio y dominios una hora, calendario un día. Ante fallo se puede mostrar cambio anterior hasta 24 horas o calendario anterior hasta siete días, con aviso y fecha explícitos. No se reutiliza una consulta DNS vencida si falla su actualización. Reiniciar pierde la caché. No se inventan tasas, feriados ni registros DNS. Un fallo de integración devuelve estado no disponible y no modifica ni bloquea las rutas del negocio. Las tarjetas se consultan de forma independiente y muestran fuente, fecha y estado. Los mensajes privados de proveedores nunca se devuelven; solo una categoría mínima de fallo.

## Verificación

Validación del 28 de octubre de 2026: 108 pruebas aisladas, 62 pruebas API y compilación del frontend correctas. Las 13 comprobaciones públicas verifican los tres proveedores con administrador, cajero y bodega, además de rechazo anónimo y años inválidos; se cierran las sesiones de prueba y no se modifican datos comerciales.

Las pruebas aisladas cubren caché, caducidad, error de red, datos numéricos inválidos, países/años incorrectos, dominio inválido, MX, Null MX, NXDOMAIN y fallos DNS. La suite API prueba JWT, los tres roles, entradas inválidas y continuidad del catálogo durante una caída simulada. Las comprobaciones reales se guardan sin credenciales en resultado_apis_externas.json y resultado_externos_nube.json. El cumplimiento técnico no sustituye validación con usuarios ni evaluación académica de utilidad.

Fuentes primarias: [Frankfurter](https://frankfurter.dev/), [Nager.Date](https://github.com/nager/Nager.Date), [Google Public DNS JSON API](https://developers.google.com/speed/public-dns/docs/doh/json) y [privacidad de DNS sobre HTTPS](https://developers.google.com/speed/public-dns/docs/doh).
