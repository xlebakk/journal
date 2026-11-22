import styles from "./AccessCards.module.css";

export type AccessCard = {
  id: string;
  full_name: string;
  login: string;
  temporary_password: string;
  group_name?: string;
};

type Labels = { login: string; password: string; site: string; note: string };

/**
 * A4 sheets with 8 cards each: name, login, temporary password, the site and its
 * QR. The passwords live only in memory of this page; after closing it — only a reset.
 */
export function AccessCards({
  cards,
  centerName,
  siteUrl,
  qr,
  labels,
}: {
  cards: AccessCard[];
  centerName: string;
  siteUrl: string;
  qr: string;
  labels: Labels;
}) {
  const pages: AccessCard[][] = [];
  for (let i = 0; i < cards.length; i += 8) pages.push(cards.slice(i, i + 8));
  return (
    <div className={styles.sheets}>
      {pages.map((page, n) => (
        <div key={n} className={styles.sheet}>
          {page.map((card) => (
            <article key={card.id} className={styles.card}>
              <header className={styles.center}>{centerName}</header>
              <p className={styles.name}>{card.full_name}</p>
              {card.group_name && <p className={styles.group}>{card.group_name}</p>}
              <dl className={styles.facts}>
                <dt>{labels.login}</dt>
                <dd className="mono">{card.login}</dd>
                <dt>{labels.password}</dt>
                <dd className="mono">{card.temporary_password}</dd>
                <dt>{labels.site}</dt>
                <dd className="mono">{siteUrl}</dd>
              </dl>
              <img className={styles.qr} src={qr} alt="" width={72} height={72} />
              <p className={styles.note}>{labels.note}</p>
            </article>
          ))}
        </div>
      ))}
    </div>
  );
}
