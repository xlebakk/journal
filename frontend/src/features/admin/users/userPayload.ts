import { z } from "@/shared/lib/zod";

import { t } from "@/shared/i18n";

import type { UserDetail, UserWrite } from "./api";

export const ROLES = ["admin", "teacher", "parent", "student"] as const;
export const SECTIONS = [
  "users",
  "structure",
  "schedule",
  "journal",
  "exams",
  "reports",
  "payments",
  "announcements",
  "audit",
  "settings",
] as const;
const LOGIN_RE = /^$|^[a-z0-9][a-z0-9._-]{1,62}[a-z0-9]$/i;

export const schema = z.object({
  last_name: z.string().trim().min(1, t("common.required")),
  first_name: z.string().trim().min(1, t("common.required")),
  middle_name: z.string().trim(),
  login: z.string().trim().regex(LOGIN_RE, t("errors.invalid_login")),
  roles: z
    .array(z.enum(ROLES))
    .min(1, t("userForm.rolesRequired"))
    .refine((roles) => !(roles.includes("student") && roles.length > 1), {
      message: t("userForm.studentRoleExclusive"),
    }),
  student: z.object({
    phone: z.string().trim(),
    school: z.string().trim(),
    school_grade: z.string(),
    target: z.string().trim(),
    target_score: z.string().regex(/^\d{0,3}$/),
    parent_name: z.string().trim(),
    parent_phone: z.string().trim(),
    admin_note: z.string(),
  }),
  teacher: z.object({ phone: z.string().trim(), subjects: z.array(z.string()) }),
  // Create only: the administrator types the first password (stage 16).
  password: z.string(),
  must_change_password: z.boolean(),
  is_superadmin: z.boolean(),
  admin_sections: z.array(z.enum(SECTIONS)),
  position: z.string().max(80),
});
export type UserFormValues = z.infer<typeof schema>;

export function defaults(user?: UserDetail): UserFormValues {
  const s = user?.student_profile;
  return {
    last_name: user?.last_name ?? "",
    first_name: user?.first_name ?? "",
    middle_name: user?.middle_name ?? "",
    login: user?.login ?? "",
    roles: (user?.roles.filter((r): r is (typeof ROLES)[number] =>
      (ROLES as readonly string[]).includes(r),
    ) ?? []) as UserFormValues["roles"],
    student: {
      phone: s?.phone ?? "",
      school: s?.school ?? "",
      school_grade: s?.school_grade ? String(s.school_grade) : "",
      target: s?.target ?? "",
      target_score: s?.target_score != null ? String(s.target_score) : "",
      parent_name: s?.parent_name ?? "",
      parent_phone: s?.parent_phone ?? "",
      admin_note: s?.admin_note ?? "",
    },
    teacher: {
      phone: user?.teacher_profile?.phone ?? "",
      subjects: user?.teacher_profile?.subjects ?? [],
    },
    password: "",
    must_change_password: false,
    is_superadmin: user?.is_superadmin ?? false,
    admin_sections: (user?.admin_sections ?? []) as UserFormValues["admin_sections"],
    position: user?.position ?? "",
  };
}

export function toPayload(values: UserFormValues, superadmin = false): UserWrite {
  const payload: UserWrite = {
    last_name: values.last_name,
    first_name: values.first_name,
    middle_name: values.middle_name,
    roles: values.roles,
    must_change_password: values.must_change_password,
  };
  if (values.password) payload.password = values.password;
  if (values.login) payload.login = values.login.toLowerCase();
  if (values.roles.includes("student")) {
    const s = values.student;
    payload.student_profile = {
      phone: s.phone,
      school: s.school,
      school_grade: s.school_grade ? (Number(s.school_grade) as 9 | 10 | 11) : null,
      target: s.target,
      target_score: s.target_score ? Number(s.target_score) : null,
      parent_name: s.parent_name,
      parent_phone: s.parent_phone,
      admin_note: s.admin_note,
    };
  }
  if (values.roles.includes("teacher")) {
    payload.teacher_profile = { phone: values.teacher.phone, subjects: values.teacher.subjects };
  }
  // Rights of an administrator: only the super administrator sends them.
  if (superadmin && values.roles.includes("admin")) {
    payload.is_superadmin = values.is_superadmin;
    payload.admin_sections = values.is_superadmin ? [] : values.admin_sections;
    payload.position = values.position.trim();
  }
  return payload;
}
