import test from "node:test";
import assert from "node:assert/strict";
import { createClientIdentity } from "../src/lib/client-identity.ts";

test("blocked storage retains an identity within a session but separates browser sessions", () => {
  const previous = globalThis.window;
  globalThis.window = { get localStorage() { throw new Error("Storage blocked"); } };
  try {
    const first = createClientIdentity(), second = createClientIdentity();
    const id = first();
    assert.equal(first(), id);
    assert.notEqual(second(), id);
    assert.notEqual(id, "anonymous-session");
  } finally { if (previous === undefined) delete globalThis.window; else globalThis.window = previous; }
});

test("stored identity survives reloads and legacy shared identity is replaced", () => {
  const previous = globalThis.window;
  let value = "anonymous-session";
  globalThis.window = { localStorage: { getItem: () => value, setItem: (_, id) => { value = id; } } };
  try {
    const id = createClientIdentity()();
    assert.notEqual(id, "anonymous-session");
    assert.equal(createClientIdentity()(), id);
    assert.equal(value, id);
  } finally { if (previous === undefined) delete globalThis.window; else globalThis.window = previous; }
});
