import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { useGroups } from "@/features/admin/groups/api";
import styles from "@/features/schedule/SchedulePage.module.css";
import { api } from "@/shared/api/client";
import { errorMessage, fieldError } from "@/shared/api/errors";
import { t } from "@/shared/i18n";
import { formatDateTime } from "@/shared/lib/time";
import {
  Button,
  Checkbox,
  Dialog,
  DialogActions,
  EmptyState,
  LinkifiedText,
  RuledSkeleton,
  SelectField,
  Table,
  TextField,
} from "@/shared/ui";

import { useAdminAnnouncements, type Announcement } from "./api";

type Audience = NonNullable<Announcement["audience"]>;

/** «2026-11-21T14:30» for datetime-local, in the browser's zone (the centre's for staff). */
function toLocalInput(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function state(item: Announcement): string {
  const now = Date.now();
  if (item.published_at && new Date(item.published_at).getTime() > now) {
    return t("announcements.scheduled");
  }
  if (item.expires_at && new Date(item.expires_at).getTime() <= now) {
    return t("announcements.expired");
  }
  return t("announcements.live");
}

function audienceText(item: Announcement): string {
  if (item.audience === "role") {
    return item.role === "teacher"
      ? t("announcements.roleTeacher")
      : t("announcements.roleStudent");
  }
  if (item.audience === "groups") return item.group_names.join(", ");
  return t("announcements.audienceAll");
}

function AnnouncementForm({ item, onClose }: { item?: Announcement; onClose: () => void }) {
  const groups = useGroups();
  const queryClient = useQueryClient();
  const [title, setTitle] = useState(item?.title ?? "");
  const [body, setBody] = useState(item?.body ?? "");
  const [audience, setAudience] = useState<Audience>(item?.audience ?? "all");
  const [role, setRole] = useState(item?.role || "student");
  const [picked, setPicked] = useState<string[]>(item?.groups ?? []);
  const [pinned, setPinned] = useState(item?.pinned ?? false);
  const [publishedAt, setPublishedAt] = useState(toLocalInput(item?.published_at));
  const [expiresAt, setExpiresAt] = useState(toLocalInput(item?.expires_at));
  const save = useMutation({
    mutationFn: () => {
      const payload = {
        title: title.trim(),
        body: body.trim(),
        audience,
        role: audience === "role" ? role : "",
        groups: audience === "groups" ? picked : [],
        pinned,
        published_at: publishedAt ? new Date(publishedAt).toISOString() : undefined,
        expires_at: expiresAt ? new Date(expiresAt).toISOString() : null,
      };
      return item
        ? api<Announcement>(`/admin/announcements/${item.id}`, { method: "PATCH", body: payload })
        : api<Announcement>("/admin/announcements", { method: "POST", body: payload });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["announcements"] });
      onClose();
    },
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    save.mutate();
  };
  const known = ["title", "body", "role", "groups", "expires_at", "published_at"];
  return (
    <Dialog
      open
      onOpenChange={(o) => !o && onClose()}
      title={item ? item.title : t("announcements.create")}
    >
      <form className={styles.form} onSubmit={submit} noValidate>
        <TextField
          label={t("announcements.titleField")}
          value={title}
          maxLength={200}
          onChange={(e) => setTitle(e.target.value)}
          error={fieldError(save.error, "title")}
        />
        <label className={styles.section}>
          <span className={styles.status}>{t("announcements.body")}</span>
          <textarea
            className={styles.textarea}
            rows={6}
            maxLength={5000}
            value={body}
            onChange={(e) => setBody(e.target.value)}
          />
          <span className={styles.status}>{t("announcements.bodyHint")}</span>
        </label>
        <SelectField
          label={t("announcements.audience")}
          value={audience}
          onChange={(e) => setAudience(e.target.value as Audience)}
          options={[
            { value: "all", label: t("announcements.audienceAll") },
            { value: "role", label: t("announcements.audienceRole") },
            { value: "groups", label: t("announcements.audienceGroups") },
          ]}
        />
        {audience === "role" && (
          <SelectField
            label={t("announcements.audienceRole")}
            value={role}
            onChange={(e) => setRole(e.target.value)}
            options={[
              { value: "student", label: t("announcements.roleStudent") },
              { value: "teacher", label: t("announcements.roleTeacher") },
            ]}
            error={fieldError(save.error, "role")}
          />
        )}
        {audience === "groups" && (
          <fieldset className={styles.section}>
            <legend className={styles.status}>{t("announcements.groups")}</legend>
            {(groups.data ?? []).map((g) => (
              <Checkbox
                key={g.id}
                label={g.name}
                checked={picked.includes(g.id)}
                onChange={(e) =>
                  setPicked(e.target.checked ? [...picked, g.id] : picked.filter((x) => x !== g.id))
                }
              />
            ))}
            {fieldError(save.error, "groups") && (
              <p className={styles.error}>{fieldError(save.error, "groups")}</p>
            )}
          </fieldset>
        )}
        <Checkbox
          label={t("announcements.pinned")}
          checked={pinned}
          onChange={(e) => setPinned(e.target.checked)}
        />
        <div className={styles.row}>
          <TextField
            label={t("announcements.publishedAt")}
            type="datetime-local"
            value={publishedAt}
            onChange={(e) => setPublishedAt(e.target.value)}
          />
          <TextField
            label={t("announcements.expiresAt")}
            type="datetime-local"
            hint={t("announcements.expiresHint")}
            value={expiresAt}
            onChange={(e) => setExpiresAt(e.target.value)}
            error={fieldError(save.error, "expires_at")}
          />
        </div>
        {save.error && !known.some((f) => fieldError(save.error, f)) && (
          <p className={styles.error} role="alert">
            {errorMessage(save.error)}
          </p>
        )}
        <DialogActions>
          <Button
            type="submit"
            variant="primary"
            disabled={save.isPending || !title.trim() || !body.trim()}
          >
            {t("announcements.save")}
          </Button>
          <Button onClick={onClose}>{t("common.cancel")}</Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}

/** «Объявления» of the administrator. */
export function AnnouncementsPage() {
  const list = useAdminAnnouncements();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<Announcement | "new" | null>(null);
  const [deleting, setDeleting] = useState<Announcement | null>(null);
  const remove = useMutation({
    mutationFn: (id: string) => api(`/admin/announcements/${id}`, { method: "DELETE" }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["announcements"] });
      setDeleting(null);
    },
  });
  const items = list.data?.results ?? [];
  return (
    <section className={styles.page}>
      <div className={styles.titleRow}>
        <h1>{t("announcements.title")}</h1>
        <Button variant="primary" onClick={() => setEditing("new")}>
          {t("announcements.create")}
        </Button>
      </div>
      {list.isPending ? (
        <RuledSkeleton rows={4} />
      ) : list.error ? (
        <p className={styles.error}>{errorMessage(list.error)}</p>
      ) : items.length === 0 ? (
        <EmptyState text={t("announcements.empty")} />
      ) : (
        <Table>
          <thead>
            <tr>
              <th scope="col">{t("announcements.titleField")}</th>
              <th scope="col">{t("announcements.audience")}</th>
              <th scope="col">{t("announcements.publishedAt")}</th>
              <th scope="col">{t("announcements.state")}</th>
              <th scope="col">
                <span className="visually-hidden">{t("common.actions")}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id}>
                <td>
                  <strong>{item.title}</strong>
                  {item.pinned && (
                    <span className={styles.status}> · {t("announcements.pinnedMark")}</span>
                  )}
                  <p className={styles.note}>
                    <LinkifiedText text={item.body.slice(0, 160)} />
                  </p>
                </td>
                <td>{audienceText(item)}</td>
                <td className="mono">
                  {item.published_at ? formatDateTime(item.published_at) : "—"}
                  {item.expires_at && (
                    <span className={styles.status}> → {formatDateTime(item.expires_at)}</span>
                  )}
                </td>
                <td>{state(item)}</td>
                <td>
                  <div className={styles.row}>
                    <Button onClick={() => setEditing(item)}>{t("announcements.edit")}</Button>
                    <Button onClick={() => setDeleting(item)}>{t("announcements.delete")}</Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
      {editing && (
        <AnnouncementForm
          item={editing === "new" ? undefined : editing}
          onClose={() => setEditing(null)}
        />
      )}
      <Dialog
        open={deleting !== null}
        onOpenChange={(o) => !o && setDeleting(null)}
        title={t("announcements.delete")}
        description={t("announcements.deleteConfirm", { title: deleting?.title ?? "" })}
      >
        {remove.error && <p className={styles.error}>{errorMessage(remove.error)}</p>}
        <DialogActions>
          <Button
            variant="primary"
            disabled={remove.isPending}
            onClick={() => deleting && remove.mutate(deleting.id)}
          >
            {t("announcements.delete")}
          </Button>
          <Button onClick={() => setDeleting(null)}>{t("common.cancel")}</Button>
        </DialogActions>
      </Dialog>
    </section>
  );
}
