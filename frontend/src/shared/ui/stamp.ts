export const STAMP_INKS = 6;

/** First letter of the first name + first letter of the last name: Фарход Алиев → «ФА». */
export function initialsOf(firstName: string, lastName: string): string {
  const first = firstName.trim().charAt(0);
  const last = lastName.trim().charAt(0);
  return (first + last).toLocaleUpperCase("ru-RU");
}

/** Stable ink 1..6 from the user id (FNV-1a). */
export function stampInk(userId: string): number {
  let hash = 0x811c9dc5;
  for (let i = 0; i < userId.length; i += 1) {
    hash ^= userId.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193);
  }
  return ((hash >>> 0) % STAMP_INKS) + 1;
}
