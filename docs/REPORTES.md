# Cinco reportes

El menú Reportes permite seleccionar ventas completadas, productos más vendidos, inventario actual, compras y movimientos de caja. Cada uno tiene consulta y exportación PDF/Excel sobre la misma función de datos. Se mantienen las rutas anteriores para compatibilidad.

Administrador consulta los cinco; Cajero consulta solo sus ventas, sus productos vendidos y sus movimientos de caja; Bodeguero consulta inventario sin costos. Los permisos se comprueban también en las rutas de descarga.

Los rangos admiten hasta 366 días y se rechazan fechas invertidas. Inventario es una fotografía actual, no una reconstrucción histórica. Ventas/productos excluyen anulaciones; compras conserva los registros de compra. El neto de movimientos de caja no incluye fondos iniciales y no equivale al arqueo. Máximo 5000 filas; un exceso se rechaza explícitamente sin entregar datos truncados.

PDF: A4 horizontal, encabezados repetidos, texto escapado, filas partidas entre páginas, numeración y fecha/hora Guatemala. Excel: números y fechas tipados, texto literal contra fórmulas inyectadas, filtros y encabezado inmovilizado. Sin datos se genera un documento válido con aviso.

Verificación: 61 pruebas API aprobadas, incluidas consultas/exportaciones reales de los cinco reportes, permisos por ruta y alcance propio del cajero. Se renderizó una muestra de PDF con datos ficticios para revisar legibilidad y paginación. Las operaciones de prueba solo se crean en bases desechables. La aceptación académica y la validación con usuarios siguen siendo pasos distintos.

Publicación comprobada: 45 verificaciones HTTPS de consultas, PDF, Excel y permisos con las tres cuentas de demostración. Evidencia sin credenciales en resultado_reportes_nube.json. No se modificaron datos del negocio.
