import { test } from "node:test";
import assert from "node:assert/strict";
import { projectGrades, exampleMix } from "../src/lib/grade-planner.ts";
const rows = [6, 6, 6, 6, 6].map((c, i) => ({ id: String(i), name: "", credits: String(c), grade: "B1", include: true }));

test("weighted projection and required average use counted credits", () => {
  const r = projectGrades("3.1", "60", "3.3", rows);
  assert.ok(Math.abs(r.required - 3.7) < 1e-9);
  assert.ok(Math.abs(r.projected - 3.1333333333333333) < 1e-9);
  assert.equal(r.maximum, 3.4);
  assert.equal(r.possible, true);
});
test("example mix reaches target and respects unequal indivisible module credits", () => {
  for (const modules of [rows, rows.map((m, i) => ({ ...m, credits: String([3, 7.5, 4.5, 9, 6][i]) }))]) {
    const r = projectGrades("3.1", "60", "3.3", modules);
    const mix = exampleMix(modules, r.required);
    assert.ok(projectGrades("3.1", "60", "3.3", mix).reached);
    assert.ok(mix.every(m => ["A1", "A2"].includes(m.grade)));
  }
});
test("unreachable, exact maximum, zero-credit starting point and exclusions", () => {
  assert.equal(projectGrades("2", "120", "3.3", rows).possible, false);
  assert.equal(projectGrades("3.1", "60", "3.4", rows.map(m => ({ ...m, grade: "A1" }))).reached, true);
  assert.ok(Math.abs(projectGrades("0", "0", "3.2", rows).projected - 3.2) < 1e-9);
  const excluded = [...rows, { ...rows[0], id: "excluded", credits: "60", grade: "F", include: false }];
  assert.equal(projectGrades("3.1", "60", "3.3", excluded).remaining, 30);
  assert.equal(exampleMix(rows, 4.01), null);
});
test("invalid inputs do not silently become zero and failing outcomes are flagged", () => {
  for (const input of ["", "NaN", "Infinity", "-1", "4.1"])
    assert.ok(projectGrades(input, "60", "3.3", rows).error);
  assert.ok(projectGrades("3", "60", "3.3", [{ ...rows[0], credits: "1.3" }]).error);
  assert.ok(projectGrades("3", "60", "3.3", rows.map(m => ({ ...m, include: false }))).error);
  assert.equal(projectGrades("3", "60", "3.3", [{ ...rows[0], grade: "F" }]).deficient, true);
});

test("all A1 modules give 4.0 independently of the cumulative projection", () => {
  const allA1 = rows.map(m => ({ ...m, grade:"A1" }));
  assert.equal(projectGrades("0", "0", "3.3", allA1).projected, 4);
  const cumulative = projectGrades("3.1", "60", "3.3", allA1);
  assert.equal(cumulative.moduleQca, 4);
  assert.equal(cumulative.projected, 3.4);
  assert.equal(projectGrades("4", "60", "4", allA1).projected, 4);
});
