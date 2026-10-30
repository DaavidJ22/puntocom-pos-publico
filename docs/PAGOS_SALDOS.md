# Pagos y saldos a crédito

La pantalla `/pagos` permite consultar las cuentas a crédito, su total, abonos y saldo. La selección muestra cuentas por cobrar a clientes y, solo al administrador, por pagar a proveedores. Lista 50 documentos por página; el resumen incluye todas las cuentas autorizadas, no solo la página visible. Se mantienen visibles las cuentas ya liquidadas y su historial.

## Flujo

1. Registrar una venta con método CRÉDITO en Punto de venta, o una compra CRÉDITO en Compras. No representa efectivo recibido o entregado en ese momento. La venta conserva el requisito de caja abierta y descuenta existencias; una compra incorpora inventario una sola vez.
2. Abrir Pagos y saldos y elegir la cuenta. Se muestra el historial y el saldo actualizado.
3. Registrar el importe exacto del abono, método y referencia opcional (sin datos privados de tarjeta). No se admite sobrepago ni se calcula cambio.
4. Un cobro en efectivo crea un ingreso en la caja abierta del responsable. Un pago a proveedor crea un egreso y requiere efectivo disponible. Tarjeta/transferencia no mueven efectivo ni requieren caja abierta. Registrar un abono no vuelve a mover inventario.
5. La cuenta se liquida al alcanzar saldo cero; se conserva el historial con recibo numérico, fecha, responsable y referencia. Estos registros son comprobantes internos, no facturas fiscales.

Los métodos tarjeta/transferencia registran una operación ya realizada por el negocio; no ejecutan transferencias ni cargos bancarios ni reciben números de tarjeta. Este módulo es de control de crédito, no una pasarela de pagos.

## Permisos y consistencia

Administrador: todas las cuentas y pagos a proveedores. Cajero: solo sus propias ventas y cobros. Bodeguero: sin acceso a cuentas, incluso por petición directa. El servidor vuelve a verificar el rol vigente dentro de la transacción.

Cada formulario conserva un UUID para reintentar exactamente la misma solicitud sin duplicar el abono. Reutilizarlo con datos diferentes se rechaza. Abrir otro formulario genera otra operación; antes de repetir manualmente un pago hay que revisar su historial. El documento se bloquea en PostgreSQL antes de calcular saldo y escribir; dos abonos simultáneos no pueden exceder el saldo. El abono, movimiento de caja y bitácora se confirman o revierten juntos. La FK única `movimiento_caja.id_abono` vincula y evita repetir el movimiento. Los importes usan Decimal/NUMERIC(12,2).

La base también rechaza abonos a documentos de contado, anulados o por encima del saldo, y prohíbe editar/eliminar abonos confirmados. La aplicación impide anular una venta con abonos: el proceso de devoluciones/contrapartidas aún no está implementado. Una venta a crédito sin abonos puede anularse con los permisos habituales y restituye inventario sin reembolso de efectivo.

## Migración y alcance histórico

`sql/09_abonos_credito.sql` añade `abono` y su relación con caja, y permite CRÉDITO en ventas. Es repetible, conserva identificadores y no crea abonos ficticios para documentos previos. Las compras a crédito históricas sin abonos registrados aparecen pendientes por su total; cualquier pago anterior debe revisarse con el negocio antes de registrarlo. Los documentos de contado se consideran liquidados para este módulo y conservan su funcionamiento anterior; no se reconstruyen movimientos históricos de caja.

La base local tiene 21 tablas y 32 claves foráneas. Antes de migrarla se creó y verificó un respaldo privado en `.local/respaldos`. El diccionario actualizado se genera con `scripts/auditar_bd.py`. La preparación de Render incorpora la migración 09.

## Verificación

Las pruebas API sobre una base desechable cubren abonos parciales y liquidación, cobros/egresos de caja, insuficiencia de efectivo, exceso de saldo, métodos/importes inválidos, permisos de los tres roles, aislamiento entre cajeros, idempotencia, rollback con bitácora, integridad SQL, migración repetida y dos abonos simultáneos. No se crean documentos comerciales de prueba en la base publicada. Los resultados se guardan en `resultado_api.json`; las verificaciones públicas son de lectura y permisos.

Los informes de ventas/compras muestran el importe del documento, independientemente de cuánto se haya abonado. El informe de caja solo representa efectivo. El saldo a crédito actualizado se consulta en Pagos y saldos; no se deben sumar los abonos como si fueran nuevas ventas.

Validación del 28 de octubre de 2026: 108 pruebas aisladas, 70 pruebas API y 123 pruebas PostgreSQL correctas; compilación de React correcta y siete verificaciones públicas de lectura/permisos aprobadas. Evidencia: `resultado_pagos_nube.json`. La pantalla pública se verificó con el administrador de demostración; actualmente no contiene cuentas a crédito de prueba.
