import rules from "../data/qca-rules.json" with { type: "json" };

export { rules as gradeRules };
export type PlannedModule = { id: string; name: string; credits: string; grade: string; include: boolean };
export const gradePoints = Object.fromEntries(rules.grades.map(g => [g.grade, g.qpv]));
const EPS = 1e-9;

export function numberInput(value: string): number {
  return value.trim() === "" ? NaN : Number(value);
}

export function projectGrades(current: string, completed: string, target: string, modules: PlannedModule[]) {
  const qca = numberInput(current), counted = numberInput(completed), goal = numberInput(target);
  if (![qca, counted, goal].every(Number.isFinite) || qca < 0 || qca > 4 || counted < 0 || counted > 600 || goal < 0 || goal > 4)
    return { error: "Enter a QCA and target from 0 to 4, and counted credits from 0 to 600." } as const;
  if (!modules.length || modules.length > 40) return { error: "Add between 1 and 40 remaining modules." } as const;
  const included = modules.filter(m => m.include);
  if (!included.length) return { error: "Include at least one remaining module." } as const;
  if (included.some(m => !Number.isFinite(numberInput(m.credits)) || Number(m.credits) < 0.5 || Number(m.credits) > 60 || !Number.isInteger(Number(m.credits) * 2) || !(m.grade in gradePoints)))
    return { error: "Each included module needs a grade and 0.5–60 credits, in steps of 0.5." } as const;
  const remaining = included.reduce((s, m) => s + Number(m.credits), 0);
  const plannedPoints = included.reduce((s, m) => s + Number(m.credits) * gradePoints[m.grade], 0);
  const total = counted + remaining;
  const required = (goal * total - qca * counted) / remaining;
  const projected = (qca * counted + plannedPoints) / total;
  const maximum = (qca * counted + 4 * remaining) / total;
  return { qca, counted, goal, remaining, required, projected, maximum,
    gap: Math.max(0, goal * total - qca * counted - plannedPoints),
    reached: projected + EPS >= goal, possible: required <= 4 + EPS,
    deficient: included.some(m => ["D1", "F", "NG"].includes(m.grade)),
    band: rules.classifications.find(c => projected + EPS >= c.min_qca)?.label ?? "Below the listed honours bands" } as const;
}

/** Find a sufficient mix of two adjacent passing QPVs using minimum upgrade credits.
 * Dynamic programming handles unequal module credits without exponential search.
 */
export function exampleMix(modules: PlannedModule[], required: number): PlannedModule[] | null {
  if (!Number.isFinite(required) || required > 4 + EPS) return null;
  const passing = rules.grades.filter(g => g.qpv >= 2).sort((a, b) => a.qpv - b.qpv);
  const upper = passing.find(g => g.qpv + EPS >= required) ?? passing[passing.length - 1];
  const lower = passing.filter(g => g.qpv < upper.qpv).at(-1) ?? upper;
  const included = modules.filter(m => m.include);
  if (included.some(m => !Number.isFinite(numberInput(m.credits)) || Number(m.credits) < 0.5 || Number(m.credits) > 60 || !Number.isInteger(Number(m.credits) * 2))) return null;
  const total = included.reduce((s, m) => s + Number(m.credits), 0);
  const need = upper.qpv === lower.qpv ? 0 : Math.max(0, (required - lower.qpv) * total / (upper.qpv - lower.qpv));
  const subsets = new Map<number, string[]>([[0, []]]);
  for (const m of included) {
    for (const [units, ids] of [...subsets]) {
      const next = units + Number(m.credits) * 2;
      if (!subsets.has(next)) subsets.set(next, [...ids, m.id]);
    }
  }
  const units = [...subsets.keys()].sort((a, b) => a - b).find(u => u / 2 + EPS >= need);
  if (units === undefined) return null;
  const upgrades = new Set(subsets.get(units));
  return modules.map(m => m.include ? { ...m, grade: upgrades.has(m.id) ? upper.grade : lower.grade } : m);
}
