export type Course = {
  id: string; title: string; url: string; checkedAt: string; level: string;
  subjects: string[]; summary: string; code: string | null; duration: string | null;
  attendance: string | null; delivery: string | null; nfq: string | null;
  euFee?: string | null; nonEuFee?: string | null;
  award: string | null; start: string | null; points: string | null; pointsYear: string | null;
  links: Record<string, string | undefined>; requirements: string | null; requirementsCheckedAt: string | null;
};

export function courseMatches(course: Course, query: string) {
  const haystack = [course.title, course.code, course.summary, ...course.subjects].join(" ").toLowerCase();
  return query.toLowerCase().trim().split(/\s+/).every(word => haystack.includes(word));
}

export function sourceDate(value: string | null | undefined) {
  if (!value) return "Date unavailable";
  const date = new Date(value.includes("T") ? value : value.replace(" ", "T") + "Z");
  return Number.isNaN(date.getTime()) ? "Date unavailable" : date.toLocaleDateString("en-IE", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
}

export function validCourseIds(values: unknown, courses: Course[], limit = 200): string[] {
  if (!Array.isArray(values)) return [];
  const known = new Set(courses.map(course => course.id));
  return [...new Set(values.filter((id): id is string => typeof id === "string" && known.has(id)))].slice(0, limit);
}

export function comparisonCsv(courses: Course[]) {
  const rows = [
    ["Field", ...courses.map(c => c.title)],
    ["Course code", ...courses.map(c => c.code || "Not specified")],
    ["Study level", ...courses.map(c => c.level)],
    ["Duration", ...courses.map(c => c.duration || "Not specified")],
    ["Attendance", ...courses.map(c => c.attendance || "Not specified")],
    ["Delivery", ...courses.map(c => c.delivery || "Not specified")],
    ["NFQ", ...courses.map(c => c.nfq || "Not specified")],
    ["Historical CAO points", ...courses.map(c => c.points ? `${c.points} (${c.pointsYear})` : "Not specified")],
    ["EU published annual fee (academic year not stated)", ...courses.map(c => c.euFee || "See official guidance")],
    ["Non-EU published annual fee (academic year not stated)", ...courses.map(c => c.nonEuFee || "See official guidance")],
    ["Entry guidance extract", ...courses.map(c => c.requirements || "See official entry page")],
    ["Entry source", ...courses.map(c => c.links["entry requirements"] || c.url)],
    ["Fees guidance", ...courses.map(c => c.links["fees and funding"] || "https://www.ul.ie/fees")],
    ["Course source", ...courses.map(c => c.url)],
    ["Source collected", ...courses.map(c => c.checkedAt)],
  ];
  return "\uFEFF" + rows.map(row => row.map(cell => `"${(/^[=+@-]/.test(cell) ? "'" + cell : cell).replaceAll('"', '""')}"`).join(",")).join("\r\n");
}
