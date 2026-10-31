# Validación de formularios

Clientes y proveedores usan un teléfono local opcional de ocho dígitos ASCII. El formulario admite completar, corregir y borrar el valor; rechaza letras, signos, espacios, números adicionales y dígitos de otros alfabetos, sin transformar una entrada mixta en un número distinto. El teclado móvil es numérico y el campo conserva ceros iniciales. La API mantiene la comprobación de ocho dígitos antes de guardar.

Los campos compartidos ahora transmiten restricciones HTML de longitud mínima/máxima, patrón y modo de entrada. El correo se limita a 150 caracteres; la contraseña de alta requiere 12 como mínimo. Nombres de cliente y usuario, contacto y categorías reflejan la regla de letras y espacios del servidor. La razón social de proveedor conserva números y signos. Los identificadores fiscales siguen sujetos a comprobación en la API; validar formato no certifica identidad ni existencia del contacto.

Comprobaciones locales: 109 pruebas Python aprobadas, cuatro pruebas del frontend aprobadas y compilación Vite correcta. Ejecutar `pnpm test` en frontend y `python -m unittest discover -s tests -p "test_*.py"` en la raíz.
