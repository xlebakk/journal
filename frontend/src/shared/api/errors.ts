import { t, tMaybe } from "@/shared/i18n";

import { ApiError } from "./client";

/** Human text for an API error code; field errors are handled by forms. */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    const code = error.code;
    if (code) {
      const minutes = error.field<number>("retry_after_minutes") ?? "";
      return tMaybe(`errors.${code}`, { minutes }) ?? t("common.unknownError");
    }
    return t("common.unknownError");
  }
  if (error instanceof TypeError) return t("common.networkError");
  return t("common.unknownError");
}

/** First translated message for a form field, if the server rejected it. */
export function fieldError(error: unknown, field: string): string | undefined {
  if (!(error instanceof ApiError)) return undefined;
  const codes = error.fields[field];
  if (!codes?.length) return undefined;
  return codes.map((code) => tMaybe(`errors.${code}`) ?? code).join(" ");
}
