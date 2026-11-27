/** Personal data stays on the user side: Telegram CloudStorage, then localStorage. */

export const PERSONAL_SECTIONS = ["trips", "settings", "passport", "loyalty", "payments"];

const PREFIX = "ut.personal.";

export function storageKey(section) {
  if (!PERSONAL_SECTIONS.includes(section)) {
    throw new Error("Неизвестный раздел личных данных.");
  }
  return PREFIX + section;
}

export function createMemoryBackend(seed) {
  const box = new Map();
  if (seed) {
    for (const [key, value] of Object.entries(seed)) box.set(key, String(value));
  }
  return {
    kind: "memory",
    async getItem(key) {
      return box.has(key) ? box.get(key) : null;
    },
    async setItem(key, value) {
      box.set(key, String(value));
    },
    async removeItem(key) {
      box.delete(key);
    },
  };
}

export function createLocalBackend(storage) {
  return {
    kind: "local",
    async getItem(key) {
      try {
        const value = storage.getItem(key);
        return value == null ? null : String(value);
      } catch {
        return null;
      }
    },
    async setItem(key, value) {
      storage.setItem(key, String(value));
    },
    async removeItem(key) {
      storage.removeItem(key);
    },
  };
}

function defaultLocal() {
  try {
    if (typeof localStorage !== "undefined" && localStorage && typeof localStorage.getItem === "function") {
      return createLocalBackend(localStorage);
    }
  } catch {
    /* private mode falls through */
  }
  return createMemoryBackend();
}

export function detectCloud() {
  const tg = globalThis.Telegram && globalThis.Telegram.WebApp;
  if (!tg || !tg.initData) return null;
  const cloud = tg.CloudStorage;
  if (!cloud || typeof cloud.getItem !== "function") return null;
  return cloud;
}

function callCloud(cloud, method, key, value) {
  return new Promise((resolve, reject) => {
    let settled = false;
    const timer = setTimeout(() => {
      if (settled) return;
      settled = true;
      reject(new Error("cloud timeout"));
    }, 2500);
    const done = (error, result) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (error) reject(error instanceof Error ? error : new Error(String(error)));
      else resolve(result == null ? null : result);
    };
    try {
      const fn = cloud && cloud[method];
      if (typeof fn !== "function") throw new Error("cloud missing");
      if (method === "setItem") fn.call(cloud, key, value, done);
      else fn.call(cloud, key, done);
    } catch (error) {
      if (!settled) {
        settled = true;
        clearTimeout(timer);
        reject(error);
      }
    }
  });
}

function createCloudBackend(cloud) {
  return {
    kind: "cloud",
    getItem(key) {
      return callCloud(cloud, "getItem", key);
    },
    setItem(key, value) {
      return callCloud(cloud, "setItem", key, value);
    },
    removeItem(key) {
      return callCloud(cloud, "removeItem", key);
    },
  };
}

function parseJson(value) {
  if (value == null || value === "") return null;
  try {
    return JSON.parse(String(value));
  } catch {
    return null;
  }
}

export function createPersonalStore(options = {}) {
  const local = options.local || defaultLocal();
  const cloud = Object.prototype.hasOwnProperty.call(options, "cloud") ? options.cloud : detectCloud();
  const cloudBackend = cloud && typeof cloud.getItem === "function" ? createCloudBackend(cloud) : null;

  async function mirror(key, raw) {
    try {
      await local.setItem(key, raw);
    } catch {
      /* the device cache is optional when CloudStorage succeeded */
    }
  }

  return {
    kind: cloudBackend ? "cloud" : (local.kind || "local"),
    async read(section) {
      const key = storageKey(section);
      if (cloudBackend) {
        try {
          const value = await cloudBackend.getItem(key);
          if (value != null && value !== "") {
            await mirror(key, String(value));
            return parseJson(value);
          }
        } catch {
          /* CloudStorage missed; read the on-device copy */
        }
      }
      return parseJson(await local.getItem(key));
    },
    async write(section, data) {
      const key = storageKey(section);
      const raw = JSON.stringify(data);
      if (cloudBackend) {
        try {
          await cloudBackend.setItem(key, raw);
          await mirror(key, raw);
          return;
        } catch {
          /* fall through to localStorage */
        }
      }
      await local.setItem(key, raw);
    },
    async remove(section) {
      const key = storageKey(section);
      if (cloudBackend) {
        try {
          await cloudBackend.removeItem(key);
        } catch {
          /* still drop the on-device copy */
        }
      }
      await local.removeItem(key);
    },
  };
}
