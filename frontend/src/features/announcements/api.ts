import { useQuery } from "@tanstack/react-query";

import { api, type Schemas } from "@/shared/api/client";

export type Announcement = Schemas["Announcement"];
export type FeedItem = Schemas["FeedItem"];

export function useFeed() {
  return useQuery({
    queryKey: ["announcements", "feed"],
    queryFn: () => api<FeedItem[]>("/announcements"),
    staleTime: 60_000,
  });
}

export function useAdminAnnouncements() {
  return useQuery({
    queryKey: ["announcements", "admin"],
    queryFn: () =>
      api<Schemas["PaginatedAnnouncementList"]>("/admin/announcements", {
        query: { page_size: "200" },
      }),
  });
}
