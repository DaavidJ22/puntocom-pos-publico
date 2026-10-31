// Reglas de edición y ayuda inmediata; la API vuelve a validar al guardar.
export function constraintsFor(name) {
  if (name === "telefono")
    return {
      type: "tel",
      inputMode: "numeric",
      minLength: 8,
      maxLength: 8,
      pattern: "[0-9]{8}",
      title: "Escribe 8 dígitos, sin letras, espacios ni guiones.",
      autoComplete: "tel-national",
    };
  if (name === "correo") return { maxLength: 150, autoComplete: "email" };
  if (name === "password")
    return { minLength: 12, autoComplete: "new-password" };
  return {};
}

export function acceptsEdit(name, value) {
  // Rechazar una entrada inválida completa, sin convertirla en otro teléfono.
  return name !== "telefono" || /^[0-9]{0,8}$/.test(value);
}
