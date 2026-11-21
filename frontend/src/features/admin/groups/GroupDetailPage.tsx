import { useMutation, useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router";

import { NotFoundPage } from "@/app/NotFoundPage";
import styles from "@/features/schedule/SchedulePage.module.css";
import { api, isApiError, type Schemas } from "@/shared/api/client";
import { errorMessage, fieldError } from "@/shared/api/errors";
import { t } from "@/shared/i18n";
import { centerToday, formatDate } from "@/shared/lib/week";
import {
  Button,
  Checkbox,
  Dialog,
  DialogActions,
  EmptyState,
  RuledSkeleton,
  SelectField,
  Table,
  TextField,
} from "@/shared/ui";

import {
  useCourses,
  useGroup,
  useGroups,
  useInvalidateAdmin,
  useMembers,
  useSubjects,
  useTeachers,
  type Course,
  type Group,
  type Membership,
} from "./api";

type UserList = Schemas["PaginatedAdminUserListList"];

function ErrorLine({ error }: { error: unknown }) {
  if (!error) return null;
  const text =
    fieldError(error, "non_field_errors") ??
    fieldError(error, "student") ??
    fieldError(error, "date") ??
    fieldError(error, "left_on") ??
    fieldError(error, "group") ??
    fieldError(error, "assistants") ??
    errorMessage(error);
  return (
    <p className={styles.error} role="alert">
      {text}
    </p>
  );
}

function AddMember({ group, onClose }: { group: Group; onClose: () => void }) {
  const invalidate = useInvalidateAdmin();
  const [q, setQ] = useState("");
  const [student, setStudent] = useState("");
  const [joined, setJoined] = useState(centerToday());
  const found = useQuery({
    queryKey: ["admin", "users", "pick", q],
    queryFn: () =>
      api<UserList>("/admin/users", { query: { role: "student", status: "active", q } }),
    enabled: q.trim().length >= 2,
  });
  const add = useMutation({
    mutationFn: () =>
      api(`/admin/groups/${group.id}/members`, {
        method: "POST",
        body: { student, joined_on: joined },
      }),
    onSuccess: async () => {
      await invalidate();
      onClose();
    },
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    add.mutate();
  };
  return (
    <form className={styles.form} onSubmit={submit} noValidate>
      <TextField
        label={t("groups.searchStudent")}
        type="search"
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />
      <SelectField
        label={t("schedule.student")}
        value={student}
        onChange={(e) => setStudent(e.target.value)}
        options={[
          { value: "", label: "—" },
          ...(found.data?.results ?? []).map((u) => ({
            value: u.id,
            label: `${u.full_name} (${u.login})`,
          })),
        ]}
      />
      <TextField
        label={t("groups.joinedOn")}
        type="date"
        value={joined}
        onChange={(e) => setJoined(e.target.value)}
      />
      <ErrorLine error={add.error} />
      <DialogActions>
        <Button type="submit" variant="primary" disabled={!student || add.isPending}>
          {t("groups.addMember")}
        </Button>
        <Button onClick={onClose}>{t("common.cancel")}</Button>
      </DialogActions>
    </form>
  );
}

function MemberAction({
  membership,
  kind,
  onClose,
}: {
  membership: Membership;
  kind: "transfer" | "leave";
  onClose: () => void;
}) {
  const invalidate = useInvalidateAdmin();
  const groups = useGroups();
  const [date, setDate] = useState(centerToday());
  const [target, setTarget] = useState("");
  const run = useMutation({
    mutationFn: () =>
      kind === "transfer"
        ? api(`/admin/memberships/${membership.id}/transfer`, {
            method: "POST",
            body: { group: target, date },
          })
        : api(`/admin/memberships/${membership.id}/leave`, {
            method: "POST",
            body: { left_on: date },
          }),
    onSuccess: async () => {
      await invalidate();
      onClose();
    },
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    run.mutate();
  };
  const others = (groups.data ?? []).filter((g) => g.id !== membership.group);
  return (
    <form className={styles.form} onSubmit={submit} noValidate>
      <p className={styles.note}>{membership.student.full_name}</p>
      {kind === "transfer" && (
        <SelectField
          label={t("groups.transferTo")}
          value={target}
          onChange={(e) => setTarget(e.target.value)}
          options={[
            { value: "", label: "—" },
            ...others.map((g) => ({ value: g.id, label: g.name })),
          ]}
        />
      )}
      <TextField
        label={t(kind === "transfer" ? "groups.transferDate" : "groups.leaveDate")}
        type="date"
        value={date}
        onChange={(e) => setDate(e.target.value)}
      />
      <ErrorLine error={run.error} />
      <DialogActions>
        <Button
          type="submit"
          variant="primary"
          disabled={run.isPending || (kind === "transfer" && !target)}
        >
          {t(kind === "transfer" ? "groups.transfer" : "groups.leave")}
        </Button>
        <Button onClick={onClose}>{t("common.cancel")}</Button>
      </DialogActions>
    </form>
  );
}

function Composition({ group }: { group: Group }) {
  const members = useMembers(group.id);
  const [history, setHistory] = useState(false);
  const [dialog, setDialog] = useState<
    { kind: "add" } | { kind: "transfer" | "leave"; membership: Membership } | null
  >(null);
  const rows = (members.data ?? []).filter(
    (m) => history || m.is_active || m.joined_on > centerToday(),
  );
  return (
    <section className={styles.section} aria-labelledby="composition">
      <div className={styles.titleRow}>
        <h2 id="composition">{t("groups.composition")}</h2>
        <Button onClick={() => setDialog({ kind: "add" })} disabled={group.is_archived}>
          {t("groups.addMember")}
        </Button>
      </div>
      <Checkbox
        label={t("groups.history")}
        checked={history}
        onChange={(e) => setHistory(e.target.checked)}
      />
      {members.isPending ? (
        <RuledSkeleton rows={4} />
      ) : rows.length === 0 ? (
        <EmptyState text={t("groups.noMembers")} />
      ) : (
        <Table>
          <thead>
            <tr>
              <th scope="col">{t("users.name")}</th>
              <th scope="col">{t("groups.joinedOn")}</th>
              <th scope="col">{t("groups.leftOn")}</th>
              <th scope="col">
                <span className="visually-hidden">{t("userActions.title")}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((m) => (
              <tr key={m.id}>
                <td>
                  <Link to={`/admin/users/${m.student.id}`}>{m.student.full_name}</Link>
                </td>
                <td className="mono">{formatDate(m.joined_on)}</td>
                <td className="mono">{m.left_on ? formatDate(m.left_on) : "—"}</td>
                <td>
                  {m.is_active && (
                    <span className={styles.row}>
                      <Button onClick={() => setDialog({ kind: "transfer", membership: m })}>
                        {t("groups.transfer")}
                      </Button>
                      <Button
                        variant="danger"
                        onClick={() => setDialog({ kind: "leave", membership: m })}
                      >
                        {t("groups.leave")}
                      </Button>
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
      <Dialog
        open={dialog !== null}
        onOpenChange={(o) => !o && setDialog(null)}
        title={
          dialog?.kind === "add"
            ? t("groups.addMember")
            : dialog?.kind === "transfer"
              ? t("groups.transfer")
              : t("groups.leave")
        }
      >
        {dialog?.kind === "add" && <AddMember group={group} onClose={() => setDialog(null)} />}
        {dialog && dialog.kind !== "add" && (
          <MemberAction
            membership={dialog.membership}
            kind={dialog.kind}
            onClose={() => setDialog(null)}
          />
        )}
      </Dialog>
    </section>
  );
}

function CourseForm({
  group,
  course,
  onClose,
}: {
  group: Group;
  course?: Course;
  onClose: () => void;
}) {
  const subjects = useSubjects();
  const teachers = useTeachers();
  const invalidate = useInvalidateAdmin();
  const [subject, setSubject] = useState(course?.subject ?? "");
  const [teacher, setTeacher] = useState(course?.teacher ?? "");
  const [assistants, setAssistants] = useState<string[]>(course?.assistants ?? []);
  const save = useMutation({
    mutationFn: () =>
      course
        ? api(`/admin/courses/${course.id}`, { method: "PATCH", body: { teacher, assistants } })
        : api("/admin/courses", {
            method: "POST",
            body: { group: group.id, subject, teacher, assistants },
          }),
    onSuccess: async () => {
      await invalidate();
      onClose();
    },
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    save.mutate();
  };
  const teacherOptions = (teachers.data ?? []).map((p) => ({ value: p.id, label: p.full_name }));
  return (
    <form className={styles.form} onSubmit={submit} noValidate>
      {!course && (
        <SelectField
          label={t("groups.subject")}
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          options={[
            { value: "", label: "—" },
            ...(subjects.data ?? [])
              .filter((s) => !s.is_archived)
              .map((s) => ({ value: s.id, label: s.name })),
          ]}
        />
      )}
      <SelectField
        label={t("groups.teacher")}
        value={teacher}
        onChange={(e) => setTeacher(e.target.value)}
        options={[{ value: "", label: "—" }, ...teacherOptions]}
      />
      <fieldset className={styles.section}>
        <legend className={styles.note}>{t("groups.assistants")}</legend>
        {teacherOptions
          .filter((o) => o.value !== teacher)
          .map((o) => (
            <Checkbox
              key={o.value}
              label={o.label}
              checked={assistants.includes(o.value)}
              onChange={(e) =>
                setAssistants((list) =>
                  e.target.checked ? [...list, o.value] : list.filter((id) => id !== o.value),
                )
              }
            />
          ))}
      </fieldset>
      <ErrorLine error={save.error} />
      <DialogActions>
        <Button
          type="submit"
          variant="primary"
          disabled={save.isPending || !teacher || (!course && !subject)}
        >
          {t("common.save")}
        </Button>
        <Button onClick={onClose}>{t("common.cancel")}</Button>
      </DialogActions>
    </form>
  );
}

function Courses({ group }: { group: Group }) {
  const courses = useCourses({ group: group.id });
  const invalidate = useInvalidateAdmin();
  const [editing, setEditing] = useState<Course | "new" | null>(null);
  const remove = useMutation({
    mutationFn: (course: Course) => api(`/admin/courses/${course.id}`, { method: "DELETE" }),
    onSuccess: () => invalidate(),
  });
  return (
    <section className={styles.section} aria-labelledby="courses">
      <div className={styles.titleRow}>
        <h2 id="courses">{t("groups.courses")}</h2>
        <Button onClick={() => setEditing("new")} disabled={group.is_archived}>
          {t("groups.addCourse")}
        </Button>
      </div>
      {courses.isPending ? (
        <RuledSkeleton rows={3} />
      ) : (courses.data ?? []).length === 0 ? (
        <EmptyState text={t("groups.noCourses")} />
      ) : (
        <Table>
          <thead>
            <tr>
              <th scope="col">{t("groups.subject")}</th>
              <th scope="col">{t("groups.teacher")}</th>
              <th scope="col">{t("groups.assistants")}</th>
              <th scope="col">
                <span className="visually-hidden">{t("catalogs.edit")}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {(courses.data ?? []).map((c) => (
              <tr key={c.id}>
                <td>{c.subject_name}</td>
                <td>{c.teacher_info.full_name}</td>
                <td>{c.assistants_info.map((a) => a.short_name).join(", ") || "—"}</td>
                <td>
                  <span className={styles.row}>
                    <Button onClick={() => setEditing(c)}>{t("catalogs.edit")}</Button>
                    <Button
                      variant="danger"
                      onClick={() => remove.mutate(c)}
                      disabled={remove.isPending}
                    >
                      {t("groups.removeCourse")}
                    </Button>
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
      <ErrorLine error={remove.error} />
      <Dialog
        open={editing !== null}
        onOpenChange={(o) => !o && setEditing(null)}
        title={editing === "new" ? t("groups.addCourse") : t("groups.courses")}
      >
        {editing && (
          <CourseForm
            group={group}
            course={editing === "new" ? undefined : editing}
            onClose={() => setEditing(null)}
          />
        )}
      </Dialog>
    </section>
  );
}

function Settings({ group }: { group: Group }) {
  const invalidate = useInvalidateAdmin();
  const [name, setName] = useState(group.name);
  const [level, setLevel] = useState(group.level ?? "");
  const save = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api(`/admin/groups/${group.id}`, { method: "PATCH", body }),
    onSuccess: () => invalidate(),
  });
  return (
    <section className={styles.section} aria-labelledby="group-settings">
      <h2 id="group-settings">{t("groups.settings")}</h2>
      <div className={styles.grid}>
        <TextField
          label={t("groups.name")}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <TextField
          label={t("groups.level")}
          value={level}
          onChange={(e) => setLevel(e.target.value)}
        />
      </div>
      <div className={styles.row}>
        <Button
          onClick={() => save.mutate({ name: name.trim(), level: level.trim() })}
          disabled={save.isPending}
        >
          {t("common.save")}
        </Button>
        <Link to={`/admin/schedule?group=${group.id}`}>{t("nav.schedule")}</Link>
        <Button
          variant={group.is_archived ? "secondary" : "danger"}
          onClick={() => save.mutate({ is_archived: !group.is_archived })}
          disabled={save.isPending}
        >
          {t(group.is_archived ? "groups.unarchive" : "groups.archive")}
        </Button>
      </div>
      <ErrorLine error={save.error} />
    </section>
  );
}

export function GroupDetailPage() {
  const { id = "" } = useParams();
  const group = useGroup(id);
  if (group.isPending) return <RuledSkeleton rows={6} />;
  if (isApiError(group.error, 404)) return <NotFoundPage />;
  if (group.error) return <p className={styles.error}>{errorMessage(group.error)}</p>;
  const data = group.data;
  return (
    <div className={styles.page}>
      <div className={styles.titleRow}>
        <h1>{data.name}</h1>
        <span className={styles.status}>
          {data.year_name}
          {data.level && <> · {data.level}</>} · {t("groups.members")}: {data.members_count}
          {data.is_archived && <> · {t("groups.archived")}</>}
        </span>
      </div>
      <Composition group={data} />
      <Courses group={data} />
      <Settings key={data.id + data.name} group={data} />
    </div>
  );
}
