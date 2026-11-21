import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useSearchParams } from "react-router";

import { api, type Schemas } from "@/shared/api/client";
import { t, type MessageKey } from "@/shared/i18n";
import { SelectField } from "@/shared/ui";

import { CatalogSection, type CatalogConfig, type Row } from "./CatalogSection";
import styles from "./Catalogs.module.css";

type Year = Schemas["AcademicYear"];
type WorkType = Schemas["WorkType"];

const TABS: { key: string; label: MessageKey }[] = [
  { key: "years", label: "catalogs.years" },
  { key: "subjects", label: "catalogs.subjects" },
  { key: "rooms", label: "catalogs.rooms" },
  { key: "lesson-types", label: "catalogs.lessonTypes" },
  { key: "work-types", label: "catalogs.workTypes" },
  { key: "holidays", label: "catalogs.holidays" },
];

const SCALES = [
  { value: "100", label: "0–100" },
  { value: "5", label: "2–5" },
  { value: "10", label: "1–10" },
];

const byName = (row: Row) => String(row.name ?? "");

function useYears() {
  return useQuery({
    queryKey: ["admin", "catalog", "/admin/years", {}],
    queryFn: () => api<Year[]>("/admin/years"),
  });
}

function YearsTab() {
  const years = useYears();
  const [selected, setSelected] = useState("");
  const yearId = selected || years.data?.find((y) => y.is_current)?.id || years.data?.[0]?.id || "";
  const yearOptions = (years.data ?? []).map((y) => ({ value: y.id, label: y.name }));
  return (
    <>
      <CatalogSection
        config={{
          endpoint: "/admin/years",
          title: "catalogs.years",
          name: byName,
          fields: [
            { name: "name", label: "catalogs.name", kind: "text", required: true },
            { name: "starts_on", label: "catalogs.startsOn", kind: "date", required: true },
            { name: "ends_on", label: "catalogs.endsOn", kind: "date", required: true },
            { name: "is_current", label: "catalogs.isCurrent", kind: "checkbox" },
            { name: "grade_scale", label: "catalogs.gradeScale", kind: "select", options: SCALES },
          ],
          defaults: { grade_scale: "100" },
        }}
      />
      {yearId && (
        <>
          <div className={styles.filter}>
            <SelectField
              label={t("groups.year")}
              value={yearId}
              onChange={(e) => setSelected(e.target.value)}
              options={yearOptions}
            />
          </div>
          <CatalogSection
            key={yearId}
            config={{
              endpoint: "/admin/terms",
              title: "catalogs.terms",
              name: byName,
              query: { year: yearId },
              defaults: { year: yearId },
              fields: [
                { name: "year", label: "groups.year", kind: "select", options: yearOptions },
                { name: "name", label: "catalogs.name", kind: "text", required: true },
                { name: "starts_on", label: "catalogs.startsOn", kind: "date", required: true },
                { name: "ends_on", label: "catalogs.endsOn", kind: "date", required: true },
              ],
            }}
          />
        </>
      )}
    </>
  );
}

function LessonTypesTab() {
  const workTypes = useQuery({
    queryKey: ["admin", "catalog", "/admin/work-types", {}],
    queryFn: () => api<WorkType[]>("/admin/work-types"),
  });
  const options = (workTypes.data ?? []).map((w) => ({ value: w.id, label: w.name }));
  return (
    <CatalogSection
      config={{
        endpoint: "/admin/lesson-types",
        title: "catalogs.lessonTypes",
        name: byName,
        defaults: { counts_attendance: true, sort_order: "0" },
        fields: [
          { name: "name", label: "catalogs.name", kind: "text", required: true },
          { name: "short", label: "catalogs.short", kind: "text", required: true },
          { name: "default_work_type", label: "catalogs.defaultWorkType", kind: "select", options },
          { name: "counts_attendance", label: "catalogs.countsAttendance", kind: "checkbox" },
          { name: "sort_order", label: "catalogs.sortOrder", kind: "number" },
          { name: "is_archived", label: "catalogs.archived", kind: "checkbox" },
        ],
      }}
    />
  );
}

const SIMPLE: Record<string, CatalogConfig> = {
  subjects: {
    endpoint: "/admin/subjects",
    title: "catalogs.subjects",
    name: byName,
    fields: [
      { name: "name", label: "catalogs.name", kind: "text", required: true },
      { name: "short_name", label: "catalogs.shortName", kind: "text", required: true },
      { name: "is_archived", label: "catalogs.archived", kind: "checkbox" },
    ],
  },
  rooms: {
    endpoint: "/admin/rooms",
    title: "catalogs.rooms",
    name: byName,
    fields: [
      { name: "name", label: "catalogs.name", kind: "text", required: true },
      { name: "capacity", label: "catalogs.capacity", kind: "number", required: true },
      { name: "is_archived", label: "catalogs.archived", kind: "checkbox" },
    ],
  },
  "work-types": {
    endpoint: "/admin/work-types",
    title: "catalogs.workTypes",
    name: byName,
    defaults: { weight: "1" },
    fields: [
      { name: "name", label: "catalogs.name", kind: "text", required: true },
      { name: "weight", label: "catalogs.weight", kind: "decimal", required: true },
      { name: "is_archived", label: "catalogs.archived", kind: "checkbox" },
    ],
  },
  holidays: {
    endpoint: "/admin/holidays",
    title: "catalogs.holidays",
    name: (row) => `${String(row.date)} ${String(row.name)}`,
    fields: [
      { name: "date", label: "catalogs.date", kind: "date", required: true },
      { name: "name", label: "catalogs.name", kind: "text", required: true },
    ],
  },
};

/** «Справочники» (SPEC §8.4). The tab lives in the URL. */
export function CatalogsPage() {
  const [params, setParams] = useSearchParams();
  const tab = TABS.some((x) => x.key === params.get("tab")) ? params.get("tab")! : "years";
  return (
    <section className={styles.page}>
      <h1>{t("catalogs.title")}</h1>
      <div className={styles.tabs} role="tablist" aria-label={t("catalogs.title")}>
        {TABS.map((x) => (
          <button
            key={x.key}
            type="button"
            role="tab"
            aria-selected={tab === x.key}
            className={styles.tab}
            onClick={() => setParams({ tab: x.key }, { replace: true })}
          >
            {t(x.label)}
          </button>
        ))}
      </div>
      <div role="tabpanel">
        {tab === "years" ? (
          <YearsTab />
        ) : tab === "lesson-types" ? (
          <LessonTypesTab />
        ) : (
          <CatalogSection key={tab} config={SIMPLE[tab]!} />
        )}
      </div>
    </section>
  );
}
