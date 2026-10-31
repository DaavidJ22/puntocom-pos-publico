import test from "node:test";
import assert from "node:assert/strict";
import { acceptsEdit, constraintsFor } from "../src/validation.js";

test("teléfono permite completar, corregir y borrar sin perder ceros iniciales", () => {
  for (const value of ["", "0", "01234567", "55551234"])
    assert.equal(acceptsEdit("telefono", value), true);
});
test("teléfono rechaza letras, formatos mixtos, números extra y dígitos Unicode", () => {
  for (const value of [
    "abcdefgh",
    "5555abcd",
    "5555-1234",
    "+50255551234",
    "555512345",
    "5555 1234",
    "１２３４５６７８",
    "١٢٣٤٥٦٧٨",
    "55551234\n",
  ])
    assert.equal(acceptsEdit("telefono", value), false, JSON.stringify(value));
});
test("la restricción final exige ocho dígitos aunque la edición admita parciales", () => {
  const rules = constraintsFor("telefono");
  assert.equal(rules.type, "tel");
  assert.equal(rules.maxLength, 8);
  const pattern = new RegExp("^(?:" + rules.pattern + ")$");
  assert.equal(pattern.test("01234567"), true);
  assert.equal(pattern.test("1234567"), false);
});
test("otros campos conservan signos legítimos y sus límites", () => {
  assert.equal(acceptsEdit("razon_social", "Distribuidora 123, S.A."), true);
  assert.equal(acceptsEdit("correo", "ana+compras@example.com"), true);
  assert.equal(constraintsFor("correo").maxLength, 150);
  assert.equal(constraintsFor("password").minLength, 12);
});
