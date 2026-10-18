export function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[char]));
}

export function icon(name) {
  const paths = {
    search: '<circle cx="11" cy="11" r="6.25" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M16.2 16.2L20.5 20.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>',
    back: '<path d="M14.5 5.5L8 12l6.5 6.5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
    trip: '<path d="M4 9.5h16v7.2a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V9.5Z" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M8 9.5V7.8A2.8 2.8 0 0 1 10.8 5h2.4A2.8 2.8 0 0 1 16 7.8v1.7" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M4 13h16" stroke="currentColor" stroke-width="1.6" stroke-dasharray="2 2"/>',
    guide: '<path d="M6 5.5h9.2A2.8 2.8 0 0 1 18 8.3V19H8.2A2.2 2.2 0 0 0 6 21.2V5.5Z" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M6 5.5A2.2 2.2 0 0 0 3.8 7.7V19" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M9 9.5h6M9 13h6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>',
    sos: '<circle cx="12" cy="12" r="7.2" fill="none" stroke="currentColor" stroke-width="1.6"/><circle cx="12" cy="12" r="2.2" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M12 4.8v2.2M12 17v2.2M4.8 12h2.2M17 12h2.2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>',
    profile: '<circle cx="12" cy="9" r="3" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M6.2 18.2c1.2-2.4 3.2-3.5 5.8-3.5s4.6 1.1 5.8 3.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>',
    check: '<path d="M5.5 12.2l4.1 4.1L18.5 8" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
  };
  return `<svg class="ico" viewBox="0 0 24 24" aria-hidden="true">${paths[name] || ""}</svg>`;
}

export function splitName(name) {
  const match = String(name || "").match(/^(.*?)(\s*[\u{1F1E6}-\u{1F1FF}]{2})\s*$/u);
  if (!match) return { title: name || "", flag: "" };
  return { title: match[1].trim(), flag: match[2].trim() };
}

const MONTHS = ["янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"];

export function formatDay(iso) {
  if (!iso || !/^\d{4}-\d{2}-\d{2}$/.test(iso)) return "";
  const [year, month, day] = iso.split("-").map(Number);
  return `${day} ${MONTHS[month - 1]} ${year}`;
}

export function nightsBetween(depart, ret) {
  if (!depart || !ret) return null;
  const ms = Date.parse(`${ret}T00:00:00`) - Date.parse(`${depart}T00:00:00`);
  if (!Number.isFinite(ms) || ms < 0) return null;
  return Math.round(ms / 86400000);
}

export function daysUntil(iso) {
  if (!iso) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const target = new Date(`${iso}T00:00:00`);
  return Math.round((target - today) / 86400000);
}

export function zoneName(zone, catalog) {
  const titles = (catalog && catalog.zone_titles) || {};
  return titles[zone] || "зона";
}

function volatilitySuffix(fact) {
  return fact.volatility_label ? ` · ${fact.volatility_label}` : "";
}

export function factMeta(fact) {
  if (fact.gap) return `не исследовано${volatilitySuffix(fact)}`;
  const estimate = fact.date_estimated ? " (дата ориентировочная)" : "";
  const volatility = volatilitySuffix(fact);
  if (fact.hidden) {
    return fact.date ? `Непроверено, проверено ${fact.date}${volatility}` : `Непроверено${volatility}`;
  }
  if (fact.date) return `Проверено: ${fact.date}${estimate}${volatility}`;
  return `Даты проверки нет${volatility}`;
}

export function countryBySlug(catalog, slug) {
  return (catalog.countries || []).find((country) => country.slug === slug) || null;
}

export function sectionOf(country, key) {
  if (!country) return null;
  return (country.sections || []).find((section) => section.key === key) || null;
}

export function visibleFacts(facts, showHidden) {
  return (facts || []).filter((fact) => showHidden || !fact.hidden);
}

export function factStamp(fact) {
  const value = String((fact && (fact.date_iso || fact.date)) || "");
  const iso = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (iso) return Date.parse(`${iso[1]}-${iso[2]}-${iso[3]}T00:00:00Z`) || 0;
  const ru = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(value);
  if (ru) return Date.parse(`${ru[3]}-${ru[2]}-${ru[1]}T00:00:00Z`) || 0;
  return 0;
}

export function groupFacts(facts, catalog) {
  const presentation = catalog || {};
  const ordered = presentation.zone_groups || [];
  const gapZone = presentation.gap_zone;
  const missingZone = presentation.missing_zone;
  const buckets = new Map(ordered.map((group) => [group.name, []]));
  const extra = [];
  (facts || []).forEach((fact, index) => {
    const zone = fact.gap && gapZone ? gapZone : (fact.zone || missingZone);
    const item = { fact, index };
    if (zone && buckets.has(zone)) buckets.get(zone).push(item);
    else extra.push(item);
  });
  const sortNewest = (items) => items
    .slice()
    .sort((a, b) => factStamp(b.fact) - factStamp(a.fact) || a.index - b.index)
    .map((item) => item.fact);
  const groups = [];
  for (const group of ordered) {
    const items = sortNewest(buckets.get(group.name) || []);
    if (items.length) groups.push({ zone: group.name, title: group.title, facts: items });
  }
  const rest = sortNewest(extra);
  if (rest.length) {
    const fallback = ordered.find((group) => group.name === missingZone) || ordered[0] || { name: missingZone, title: "" };
    groups.push({ zone: fallback.name, title: fallback.title, facts: rest });
  }
  return groups;
}

export function hasHidden(facts) {
  return (facts || []).some((fact) => fact.hidden);
}

export function visibleSteps(instruction, showHidden) {
  return ((instruction && instruction.steps) || []).filter((step) => showHidden || !step.hidden);
}

export function stepPosition(steps, progress, cursor) {
  if (Number.isInteger(cursor) && cursor >= 0 && cursor < steps.length) return cursor;
  const incomplete = steps.findIndex((step) => !(progress[step.id] && progress[step.id].completed));
  if (incomplete < 0) return Math.max(steps.length - 1, 0);
  return incomplete;
}

export function parseRoute(hash) {
  const clean = String(hash || "").replace(/^#/, "").replace(/^\//, "");
  const [path, query = ""] = clean.split("?");
  const parts = path.split("/").filter(Boolean);
  const params = new URLSearchParams(query);
  if (!parts.length || parts[0] === "trip") {
    return { name: parts[1] === "edit" ? "trip-edit" : "trip", tab: "trip", parts, params };
  }
  if (parts[0] === "intro") return { name: "intro", tab: "", parts, params };
  if (parts[0] === "pick" || parts[0] === "onboarding") return { name: "pick", tab: "", parts, params };
  if (parts[0] === "guide") {
    if (parts.length === 1) return { name: "guide", tab: "guide", parts, params };
    if (parts[2] === "i" && parts[3]) {
      return { name: "instruction", tab: "guide", slug: parts[1], instructionId: parts[3], parts, params };
    }
    if (parts[2]) return { name: "section", tab: "guide", slug: parts[1], sectionKey: parts[2], parts, params };
    return { name: "country", tab: "guide", slug: parts[1], parts, params };
  }
  if (parts[0] === "sos") return { name: "sos", tab: "sos", parts, params };
  if (parts[0] === "profile") return { name: "profile", tab: "profile", parts, params };
  if (parts[0] === "search") return { name: "search", tab: "", parts, params };
  return { name: "trip", tab: "trip", parts, params };
}

export function mapStart(catalog, value) {
  if (!value) return "";
  if (["trip", "guide", "sos", "profile", "search"].includes(value)) return `/${value}`;
  if (value.startsWith("guide_")) return `/guide/${value.slice("guide_".length)}`;
  if (value.startsWith("instruction_")) {
    const id = value.slice("instruction_".length);
    const instruction = catalog.instructions && catalog.instructions[id];
    if (!instruction) return "/guide";
    const slug = (instruction.countries && instruction.countries[0]) || "china";
    return `/guide/${slug}/i/${id}`;
  }
  if (value.startsWith("section_")) {
    const rest = value.slice("section_".length);
    const slugs = (catalog.countries || []).map((country) => country.slug).sort((a, b) => b.length - a.length);
    for (const slug of slugs) {
      if (rest.startsWith(`${slug}_`)) return `/guide/${slug}/${rest.slice(slug.length + 1)}`;
    }
  }
  return "/trip";
}

export function searchRows(catalog) {
  const rows = [];
  for (const country of catalog.countries || []) {
    const place = splitName(country.name);
    for (const section of country.sections || []) {
      rows.push({
        kind: "section",
        title: section.short_title,
        note: place.title,
        haystack: `${section.short_title} ${section.title} ${place.title}`,
        hash: `/guide/${country.slug}/${section.key}`,
      });
      const buckets = [{ title: "", facts: section.facts || [] }].concat(
        (section.subsections || []).map((sub) => ({ title: sub.title, facts: sub.facts || [] })),
      );
      for (const bucket of buckets) {
        for (const fact of bucket.facts) {
          rows.push({
            kind: "fact",
            title: fact.text,
            note: `${place.title} · ${section.short_title}`,
            haystack: `${fact.text} ${section.short_title} ${section.title} ${bucket.title} ${place.title}`,
            hash: `/guide/${country.slug}/${section.key}?fact=${encodeURIComponent(fact.id)}`,
            hidden: fact.hidden,
            slug: country.slug,
            sectionKey: section.key,
          });
        }
      }
    }
  }
  for (const instruction of Object.values(catalog.instructions || {})) {
    for (const step of instruction.steps || []) {
      const slug = step.country_slug || (instruction.countries && instruction.countries[0]) || "china";
      rows.push({
        kind: "step",
        title: step.text,
        note: instruction.service,
        haystack: `${step.text} ${instruction.service} ${step.stage || ""}`,
        hash: `/guide/${slug}/i/${instruction.id}?fact=${encodeURIComponent(step.id)}`,
        hidden: step.hidden,
        slug,
        instructionId: instruction.id,
      });
    }
  }
  return rows;
}

function fillTicketDate(url, depart) {
  if (!url || !url.includes("{DDMM}")) return url || "";
  if (depart && /^\d{4}-\d{2}-\d{2}$/.test(depart)) {
    const [, month, day] = depart.split("-");
    return url.replace("{DDMM}", `${day}${month}`);
  }
  return url.replace("{DDMM}", "");
}

export function ticketLinks(route, depart) {
  const links = route.ticket_links && route.ticket_links.length
    ? route.ticket_links
    : (route.tickets_url ? [{ label: "Найти билеты", url: route.tickets_url }] : []);
  return links.map((link) => ({ label: link.label, url: fillTicketDate(link.url, depart) }));
}

export function ticketsUrl(route, depart) {
  const links = ticketLinks(route, depart);
  return links.length ? links[0].url : "";
}

export function applyTheme() {
  const params = new URLSearchParams(location.search);
  const tg = window.Telegram && window.Telegram.WebApp;
  const scheme = params.get("theme") || (tg && tg.colorScheme) || "light";
  document.documentElement.dataset.theme = scheme === "dark" ? "dark" : "light";
  const theme = (tg && tg.themeParams) || {};
  const root = document.documentElement.style;
  const map = {
    "--bg": theme.bg_color,
    "--elev": theme.section_bg_color || theme.secondary_bg_color,
    "--text": theme.text_color,
    "--hint": theme.hint_color,
    "--accent": theme.button_color,
    "--accent-text": theme.button_text_color,
    "--link": theme.link_color,
    "--header": theme.header_bg_color || theme.bg_color,
    "--nav": theme.bottom_bar_bg_color || theme.secondary_bg_color || theme.bg_color,
    "--chip": theme.secondary_bg_color,
  };
  Object.entries(map).forEach(([key, value]) => {
    if (value) root.setProperty(key, value);
    else root.removeProperty(key);
  });
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta && (theme.header_bg_color || theme.bg_color)) {
    meta.setAttribute("content", theme.header_bg_color || theme.bg_color);
  }
  if (tg && theme.bg_color && tg.setBackgroundColor) {
    try { tg.setBackgroundColor(theme.bg_color); } catch (error) { /* desktop preview */ }
  }
  if (tg && theme.header_bg_color && tg.setHeaderColor) {
    try { tg.setHeaderColor(theme.header_bg_color); } catch (error) { /* desktop preview */ }
  }
}

export function isLocalHost() {
  return location.hostname === "localhost" || location.hostname === "127.0.0.1";
}

export function ruCount(count, one, few, many) {
  const n10 = count % 10;
  const n100 = count % 100;
  const word = n10 === 1 && n100 !== 11 ? one : n10 >= 2 && n10 <= 4 && (n100 < 12 || n100 > 14) ? few : many;
  return `${count} ${word}`;
}
