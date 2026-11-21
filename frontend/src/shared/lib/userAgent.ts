/** «Chrome · Android» from a User-Agent string; rough on purpose, for the sessions list. */
export function describeUserAgent(ua: string): string {
  if (!ua) return "";
  const browser =
    (/Edg\//.test(ua) && "Edge") ||
    (/OPR\//.test(ua) && "Opera") ||
    (/YaBrowser\//.test(ua) && "Яндекс Браузер") ||
    (/Firefox\//.test(ua) && "Firefox") ||
    (/Chrome\//.test(ua) && "Chrome") ||
    (/Safari\//.test(ua) && "Safari") ||
    "";
  const os =
    (/Android/.test(ua) && "Android") ||
    (/iPhone|iPad|iPod/.test(ua) && "iOS") ||
    (/Windows/.test(ua) && "Windows") ||
    (/Mac OS X/.test(ua) && "macOS") ||
    (/Linux/.test(ua) && "Linux") ||
    "";
  return [browser, os].filter(Boolean).join(" · ") || ua.slice(0, 40);
}
