import { QueryCache, QueryClient } from "@tanstack/react-query";

import { ME_KEY } from "@/features/auth/api";
import { isApiError } from "@/shared/api/client";

export function createQueryClient(): QueryClient {
  const client: QueryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: (count, error) => !isApiError(error) && count < 1,
        refetchOnWindowFocus: false,
        // Stage 19: a screen opened again shows its data at once; within a minute it is not
        // asked for again, later it is refreshed quietly behind the shown data. Memory only.
        staleTime: 60_000,
        gcTime: 30 * 60_000,
      },
    },
    queryCache: new QueryCache({
      onError: (error) => {
        // Session ended elsewhere (timeout, revoked): the gate sends the user to /login.
        if (isApiError(error, 401)) client.setQueryData(ME_KEY, null);
        if (
          isApiError(error, 403) &&
          ["password_change_required", "totp_setup_required"].includes(error.code ?? "")
        ) {
          void client.invalidateQueries({ queryKey: ME_KEY });
        }
      },
    }),
  });
  return client;
}
