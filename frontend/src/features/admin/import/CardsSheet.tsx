import { useQuery } from "@tanstack/react-query";

import { api, type Schemas } from "@/shared/api/client";
import { t } from "@/shared/i18n";
import { AccessCards, type AccessCard } from "@/shared/ui";

type CardInfo = Schemas["AccessCardInfo"];

function useCardInfo() {
  return useQuery({
    queryKey: ["admin", "access-cards"],
    queryFn: () => api<CardInfo>("/admin/access-cards"),
    staleTime: 300_000,
  });
}

/** Cards for passwords that exist only in this page's memory (SPEC §8.2). */
export function CardsSheet({ cards }: { cards: AccessCard[] }) {
  const info = useCardInfo();
  if (!info.data) return null;
  return (
    <AccessCards
      cards={cards}
      centerName={info.data.center_name}
      siteUrl={info.data.site_url}
      qr={info.data.qr}
      labels={{
        login: t("cards.login"),
        password: t("cards.password"),
        site: t("cards.site"),
        note: t("cards.note"),
      }}
    />
  );
}
