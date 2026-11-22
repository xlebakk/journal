import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type Schemas } from "@/shared/api/client";
import { t } from "@/shared/i18n";

export type GroupFees = Schemas["GroupFees"];
export type StudentList = Schemas["StudentList"];
export type AdminLedger = Schemas["AdminLedger"];
export type Ledger = Schemas["Ledger"];
export type PaymentMethod = Schemas["PaymentWriteRequest"]["method"];

export const METHODS: PaymentMethod[] = ["cash", "card", "transfer"];

/** «1 250 000 сум» — whole soʻm, grouped like the rest of the numbers. */
export function money(amount: number): string {
  return `${amount.toLocaleString("ru-RU")} ${t("payments.currency")}`;
}

export type StudentQuery = { q?: string; group?: string; debtors?: boolean };

export function useGroupFees() {
  return useQuery({
    queryKey: ["payments", "groups"],
    queryFn: () => api<GroupFees>("/admin/payments/groups"),
  });
}

export function usePaymentStudents(query: StudentQuery) {
  return useQuery({
    queryKey: ["payments", "students", query],
    queryFn: () =>
      api<StudentList>("/admin/payments/students", {
        query: {
          q: query.q || undefined,
          group: query.group || undefined,
          debtors: query.debtors ? "1" : undefined,
        },
      }),
    placeholderData: keepPreviousData,
  });
}

export function useLedger(id: string) {
  return useQuery({
    queryKey: ["payments", "ledger", id],
    queryFn: () => api<AdminLedger>(`/admin/payments/students/${id}`),
  });
}

export function useMyPayments(enabled = true) {
  return useQuery({
    queryKey: ["payments", "mine"],
    queryFn: () => api<Ledger>("/student/payments"),
    enabled,
  });
}

/** Any change of money refreshes every payments screen. */
export function usePaymentsMutation<T, R>(fn: (value: T) => Promise<R>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["payments"] }),
  });
}
