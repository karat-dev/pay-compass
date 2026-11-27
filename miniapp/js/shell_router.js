/** Hash routes for the Mini App shell. Tabs stay in the glass bar; the rest are inner screens. */

const PROFILE_INNER = new Set([
  "pay",
  "settings",
  "passport",
  "chat",
  "trips",
  "loyalty",
  "achievements",
]);

export function parseShellRoute(hash) {
  let path = String(hash || "").replace(/^#/, "");
  const query = path.indexOf("?");
  if (query >= 0) path = path.slice(0, query);
  if (path.startsWith("/")) path = path.slice(1);
  const parts = path.split("/").filter(Boolean);
  const head = parts[0] || "home";
  if (head === "guide" && parts[1]) {
    return { name: "country", tab: "guide", inner: true, slug: parts[1] };
  }
  if (head === "guide") return { name: "guide", tab: "guide", inner: false, slug: "" };
  if (PROFILE_INNER.has(head)) return { name: head, tab: "profile", inner: true, slug: "" };
  if (head === "trip") return { name: "trip", tab: "trip", inner: false, slug: "" };
  if (head === "profile") return { name: "profile", tab: "profile", inner: false, slug: "" };
  return { name: "home", tab: "home", inner: false, slug: "" };
}

export function backTarget(route) {
  if (!route) return "";
  if (route.name === "country") return "/guide";
  if (route.inner && route.tab === "profile") return "/profile";
  return "";
}

export function readTripForm(fields) {
  const origin = String((fields && fields.origin) || "").trim();
  const destination = String((fields && fields.destination) || "").trim();
  const depart = String((fields && fields.depart) || "");
  const ret = String((fields && fields.ret) || "");
  if (!destination || !depart || !ret) return { error: "Укажите направление и обе даты." };
  if (!/^\d{4}-\d{2}-\d{2}$/.test(depart) || !/^\d{4}-\d{2}-\d{2}$/.test(ret)) {
    return { error: "Укажите даты в формате с годом." };
  }
  if (ret < depart) return { error: "Дата возвращения раньше даты вылета." };
  return {
    trip: {
      id: `local-${depart}-${ret}`,
      origin: (origin || "Москва").slice(0, 40),
      destination: destination.slice(0, 40),
      depart,
      ret,
      stepsDone: 0,
      stepsTotal: 6,
    },
  };
}
