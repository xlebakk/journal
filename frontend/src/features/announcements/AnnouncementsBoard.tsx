import { t } from "@/shared/i18n";
import { Notices } from "@/shared/ui";

import { useFeed } from "./api";

/** Live announcements for the active role: pinned first, at most five (SPEC §6.1, §7.1). */
export function AnnouncementsBoard({ className }: { className?: string }) {
  const feed = useFeed();
  const items = (feed.data ?? []).slice(0, 5);
  if (items.length === 0) return null;
  return (
    <section className={className} aria-labelledby="announcements-board">
      <h2 id="announcements-board">{t("announcements.board")}</h2>
      <Notices items={items} pinnedLabel={t("announcements.pinnedMark")} />
    </section>
  );
}
