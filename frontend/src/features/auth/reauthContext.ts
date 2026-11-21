import { createContext, useContext } from "react";

export type WithReauth = <T>(action: () => Promise<T>) => Promise<T>;

export const ReauthContext = createContext<WithReauth | null>(null);

export function useReauth(): WithReauth {
  const value = useContext(ReauthContext);
  if (!value) throw new Error("useReauth outside ReauthProvider");
  return value;
}
