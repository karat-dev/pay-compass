/** Loyalty directory shown in the Mini App. Kept in step with database/data/loyalty_programs.json. */

export const LOYALTY_CHECKED = "2026-10-28";

export const LOYALTY_ALLIANCES = [
  { id: "star", name: "Star Alliance", members: ["Turkish", "Air China", "Thai"] },
  { id: "sky", name: "SkyTeam", members: ["China Eastern", "Aeroflot (приостановлен)"] },
  { id: "one", name: "oneworld", members: ["Qatar", "Cathay"] },
  { id: "out", name: "Без альянса", members: ["Pegasus", "AJet", "Emirates", "flydubai", "Etihad", "Air Arabia", "China Southern", "Hainan", "AirAsia"] },
];

export const LOYALTY_PROGRAMS = [
  { id: "turkish-airlines", airline: "Turkish Airlines", iata: "TK", allianceId: "star", program: "Miles&Smiles", zone: "yellow", tag: "", color: "#9B1B2E" },
  { id: "ajet", airline: "AJet", iata: "VF", allianceId: "out", program: "AJet — своя программа / Miles&Smiles: не проверено", zone: "yellow", tag: "не сверено", color: "#7A1F2B" },
  { id: "pegasus", airline: "Pegasus", iata: "PC", allianceId: "out", program: "Pegasus BolBol", zone: "yellow", tag: "", color: "#8A6E12" },
  { id: "emirates", airline: "Emirates", iata: "EK", allianceId: "out", program: "Emirates Skywards", zone: "green", tag: "", color: "#8A6A2A" },
  { id: "flydubai", airline: "flydubai", iata: "FZ", allianceId: "out", program: "Emirates Skywards (общая с Emirates)", zone: "green", tag: "", color: "#2C5F8A" },
  { id: "qatar-airways", airline: "Qatar Airways", iata: "QR", allianceId: "one", program: "Privilege Club", zone: "green", tag: "", color: "#5C0A2A" },
  { id: "etihad", airline: "Etihad", iata: "EY", allianceId: "out", program: "Etihad Guest", zone: "yellow", tag: "", color: "#A67C3A" },
  { id: "air-arabia", airline: "Air Arabia", iata: "G9", allianceId: "out", program: "Air Rewards", zone: "yellow", tag: "", color: "#E36B1A" },
  { id: "air-china", airline: "Air China", iata: "CA", allianceId: "star", program: "PhoenixMiles", zone: "yellow", tag: "", color: "#C0392B" },
  { id: "china-southern", airline: "China Southern", iata: "CZ", allianceId: "out", program: "Sky Pearl Club", zone: "yellow", tag: "вышла из SkyTeam 01.01.2020", color: "#1B4E8C" },
  { id: "china-eastern", airline: "China Eastern", iata: "MU", allianceId: "sky", program: "Eastern Miles", zone: "yellow", tag: "", color: "#1A4B8C" },
  { id: "hainan-airlines", airline: "Hainan Airlines", iata: "HU", allianceId: "out", program: "Fortune Wings Club", zone: "yellow", tag: "", color: "#C4392A" },
  { id: "aeroflot", airline: "Aeroflot", iata: "SU", allianceId: "sky", program: "Аэрофлот Бонус", zone: "yellow", tag: "членство приостановлено с 2022", color: "#E04E39" },
  { id: "thai-airways", airline: "Thai Airways", iata: "TG", allianceId: "star", program: "Royal Orchid Plus", zone: "yellow", tag: "", color: "#4B2E83" },
  { id: "airasia", airline: "AirAsia", iata: "AK/FD", allianceId: "out", program: "AirAsia Rewards (AirAsia points)", zone: "yellow", tag: "", color: "#D32011" },
  { id: "cathay-pacific", airline: "Cathay Pacific", iata: "CX", allianceId: "one", program: "Cathay (Asia Miles)", zone: "yellow", tag: "", color: "#1E6B4A" },
];

export function allianceIdFromSource(alliance) {
  const text = String(alliance || "").trim().toLowerCase();
  if (!text || text.startsWith("none") || text.includes("без альянса") || text.includes("вышла")) return "out";
  if (text.includes("star alliance")) return "star";
  if (text.includes("skyteam")) return "sky";
  if (text.includes("oneworld")) return "one";
  return "out";
}

export function trustZone(program) {
  return program && program.enrolment_url_verified === true ? "green" : "yellow";
}

export function programTag(program) {
  const alliance = String((program && program.alliance) || "");
  const name = String((program && program.program) || "");
  if (alliance.includes("приостановлен")) return "членство приостановлено с 2022";
  if (alliance.includes("вышла из SkyTeam")) return "вышла из SkyTeam 01.01.2020";
  if (name.includes("не проверено")) return "не сверено";
  return "";
}

export function allianceLabel(id) {
  if (id === "out") return "Вне альянсов";
  const found = LOYALTY_ALLIANCES.find((item) => item.id === id);
  return found ? found.name : "Вне альянсов";
}

export function allianceMembers(id) {
  const found = LOYALTY_ALLIANCES.find((item) => item.id === id);
  return found ? found.members.slice() : [];
}

export function programById(id) {
  return LOYALTY_PROGRAMS.find((item) => item.id === id) || null;
}

export function programInitials(iata) {
  return String(iata || "").split("/")[0].slice(0, 2).toUpperCase() || "??";
}

export function filterLoyalty(query, allianceId) {
  const needle = String(query || "").trim().toLowerCase();
  return LOYALTY_PROGRAMS.filter((item) => {
    if (allianceId && item.allianceId !== allianceId) return false;
    if (!needle) return true;
    const hay = [item.airline, item.program, item.iata, allianceLabel(item.allianceId), item.tag].join(" ").toLowerCase();
    return hay.includes(needle);
  });
}
