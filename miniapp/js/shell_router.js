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

const TRIP_INNER = {
  "flight-add": "flight-add",
  edit: "trip-edit",
  pay: "trip-pay",
  transport: "trip-transport",
  checklist: "trip-checklist",
};

export function parseShellRoute(hash) {
  let path = String(hash || "").replace(/^#/, "");
  const query = path.indexOf("?");
  if (query >= 0) path = path.slice(0, query);
  if (path.startsWith("/")) path = path.slice(1);
  const parts = path.split("/").filter(Boolean);
  const head = parts[0] || "home";
  if (head === "guide" && parts[1] === "airlines") {
    return { name: "loyalty-ref", tab: "guide", inner: true, slug: "" };
  }
  if (head === "guide" && parts[1] && parts[2] === "pay") {
    return { name: "country-pay", tab: "guide", inner: true, slug: parts[1] };
  }
  if (head === "guide" && parts[1]) {
    return { name: "country", tab: "guide", inner: true, slug: parts[1] };
  }
  if (head === "guide") return { name: "guide", tab: "guide", inner: false, slug: "" };
  if (head === "loyalty" && parts[1] === "add") {
    return { name: "loyalty-add", tab: "profile", inner: true, slug: "" };
  }
  if (head === "pay" && parts[1] === "add") {
    return { name: "pay-add", tab: "profile", inner: true, slug: "" };
  }
  if (head === "pay" && parts[1] === "experience") {
    return { name: "pay-experience", tab: "profile", inner: true, slug: "" };
  }
  if (PROFILE_INNER.has(head)) return { name: head, tab: "profile", inner: true, slug: "" };
  if (head === "trip") {
    const sub = parts[1] || "";
    if (Object.prototype.hasOwnProperty.call(TRIP_INNER, sub)) {
      return { name: TRIP_INNER[sub], tab: "trip", inner: true, slug: "" };
    }
    return { name: "trip", tab: "trip", inner: false, slug: "" };
  }
  if (head === "profile") return { name: "profile", tab: "profile", inner: false, slug: "" };
  return { name: "home", tab: "home", inner: false, slug: "" };
}

export function backTarget(route) {
  if (!route) return "";
  if (route.name === "country" || route.name === "loyalty-ref") return "/guide";
  if (route.name === "country-pay") return `/guide/${route.slug || ""}`;
  if (route.name === "loyalty-add") return "/loyalty";
  if (route.name === "pay-add" || route.name === "pay-experience") return "/pay";
  if (route.inner && route.tab === "profile") return "/profile";
  if (route.inner && route.tab === "trip") return "/trip";
  return "";
}

export function readTripForm(fields) {
  const origin = String((fields && fields.origin) || "").trim();
  const destination = String((fields && fields.destination) || "").trim();
  const country = String((fields && fields.country) || "").trim();
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
      country: country.slice(0, 40),
      depart,
      ret,
      stepsDone: 0,
      stepsTotal: 6,
      checks: [],
      flights: [],
    },
  };
}

export function readTripEdit(fields, current) {
  const parsed = readTripForm(fields);
  if (parsed.error) return parsed;
  const base = current && typeof current === "object" ? current : {};
  return {
    trip: {
      ...base,
      id: base.id || parsed.trip.id,
      origin: parsed.trip.origin,
      destination: parsed.trip.destination,
      country: parsed.trip.country,
      depart: parsed.trip.depart,
      ret: parsed.trip.ret,
      stepsDone: Number(base.stepsDone) || 0,
      stepsTotal: Number(base.stepsTotal) || 6,
      checks: Array.isArray(base.checks) ? base.checks : [],
      flights: Array.isArray(base.flights) ? base.flights : [],
    },
  };
}
