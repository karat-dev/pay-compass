/** Where to go on launch, after the intro, and how a missing date is labeled. */

export function bootTarget({ introSeen, deepLink, hash }) {
  if (!introSeen) return "/intro";
  const path = typeof hash === "string" && hash.startsWith("#/") ? hash.slice(1) : "";
  if (path) return path;
  return deepLink || "/trip";
}

export function introExit({ action, deepLink }) {
  if (action === "pick") return "/pick";
  if (action === "skip") return deepLink || "/guide";
  return deepLink || "/trip";
}

export function afterPick({ deepLink }) {
  return deepLink || "/trip";
}

export function tripWhen(depart) {
  if (!depart) return "Дата не выбрана";
  return "";
}

export function tripCountdown(until) {
  if (until === 0) return "Вылет сегодня";
  if (typeof until === "number" && until > 0) return `До вылета ${until} дн.`;
  if (typeof until === "number" && until < 0) return "Дата вылета уже прошла";
  return "";
}
