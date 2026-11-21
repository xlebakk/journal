import { tMaybe } from "@/shared/i18n";

/** «journal.grade_create» → «журнал: оценка»; unknown actions stay as they are. */
export function actionText(action: string): string {
  const [entity = "", verb = ""] = action.split(".", 2);
  const what = tMaybe(`auditActions.${entity}`);
  const how = tMaybe(`auditVerbs.${verb}`);
  if (!what || !how) return action;
  return `${what}: ${how}`;
}

/** Changed keys of before/after, for the «было → стало» view. */
export function changes(
  before: unknown,
  after: unknown,
): { field: string; before: string; after: string }[] {
  const a = (before && typeof before === "object" ? before : {}) as Record<string, unknown>;
  const b = (after && typeof after === "object" ? after : {}) as Record<string, unknown>;
  const show = (v: unknown) =>
    v === undefined ? "" : v === null ? "—" : typeof v === "string" ? v : JSON.stringify(v);
  return [...new Set([...Object.keys(a), ...Object.keys(b)])]
    .filter((key) => JSON.stringify(a[key]) !== JSON.stringify(b[key]))
    .map((key) => ({ field: key, before: show(a[key]), after: show(b[key]) }));
}
