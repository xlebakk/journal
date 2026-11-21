import { Fragment } from "react";

import { formatHumanDate } from "@/shared/lib/time";

import styles from "./Notices.module.css";

export type Notice = {
  id: string;
  title: string;
  body: string;
  pinned: boolean;
  published_at: string;
  author_name: string;
};

const LINK = /(https:\/\/[^\s<>"«»]+[^\s<>"«».,;:!?)])/g;

/** Plain text with https:// addresses turned into links (SPEC §11): no HTML is parsed. */
export function LinkifiedText({ text }: { text: string }) {
  const parts = text.split(LINK);
  return (
    <>
      {parts.map((part, i) =>
        i % 2 === 1 ? (
          <a key={i} href={part} target="_blank" rel="noopener noreferrer">
            {part}
          </a>
        ) : (
          <Fragment key={i}>{part}</Fragment>
        ),
      )}
    </>
  );
}

/** Announcements as notes on a board: pinned ones first, marked in words, not colour only. */
export function Notices({ items, pinnedLabel }: { items: Notice[]; pinnedLabel: string }) {
  return (
    <ul className={styles.list}>
      {items.map((item) => (
        <li key={item.id} className={item.pinned ? `${styles.item} ${styles.pinned}` : styles.item}>
          <h3 className={styles.title}>{item.title}</h3>
          <p className={styles.meta}>
            {item.pinned && <span className={styles.pin}>{pinnedLabel} · </span>}
            {formatHumanDate(new Date(item.published_at))} · {item.author_name}
          </p>
          <p className={styles.body}>
            <LinkifiedText text={item.body} />
          </p>
        </li>
      ))}
    </ul>
  );
}
