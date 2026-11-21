/** 0..4. Length matters most; a phrase of several words is fine without symbols. */
export function passwordStrength(password: string, personal: string[] = []): number {
  if (password.length < 10) return password.length ? 1 : 0;
  const lower = password.toLowerCase();
  if (personal.some((part) => part.length >= 3 && lower.includes(part.toLowerCase()))) return 1;
  let score = 2;
  if (password.length >= 14) score += 1;
  const kinds = [/[a-zа-яё]/i, /\d/, /\s/, /[^\p{L}\d\s]/u].filter((re) => re.test(password));
  if (kinds.length >= 2 || password.length >= 20) score += 1;
  if (/^(.)\1+$/.test(password) || /^(?:0123|1234|qwer|йцук)/i.test(password)) score = 1;
  return Math.min(score, 4);
}
