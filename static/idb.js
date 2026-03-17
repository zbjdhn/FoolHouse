/* IndexedDB layer (local-first storage)
 * - DB name: FoolHouseDB
 * - Stores:
 *   - meta: key-value (deviceId, schemaVersion, bootstrap flags)
 *   - equityTrades: A-share trades
 *   - cryptoTrades: crypto trades
 *   - outbox: sync queue entries
 */
(() => {
  const DB_NAME = "FoolHouseDB";
  const DB_VERSION = 1;
  const STORE_META = "meta";
  const STORE_EQUITY = "equityTrades";
  const STORE_CRYPTO = "cryptoTrades";
  const STORE_OUTBOX = "outbox";

  function promisifyRequest(req) {
    return new Promise((resolve, reject) => {
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }

  function withDb() {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = (event) => {
      const db = req.result;
      const oldVersion = event.oldVersion || 0;

      if (oldVersion < 1) {
        const meta = db.createObjectStore(STORE_META);

        const equity = db.createObjectStore(STORE_EQUITY, { keyPath: "clientId" });
        equity.createIndex("by_owner_date", ["owner", "date"], { unique: false });
        equity.createIndex("by_owner_code", ["owner", "code"], { unique: false });
        equity.createIndex("by_owner_updatedAt", ["owner", "updatedAt"], { unique: false });
        equity.createIndex("by_owner_syncStatus", ["owner", "syncStatus"], { unique: false });

        const crypto = db.createObjectStore(STORE_CRYPTO, { keyPath: "clientId" });
        crypto.createIndex("by_owner_date", ["owner", "date"], { unique: false });
        crypto.createIndex("by_owner_code", ["owner", "code"], { unique: false });
        crypto.createIndex("by_owner_updatedAt", ["owner", "updatedAt"], { unique: false });
        crypto.createIndex("by_owner_syncStatus", ["owner", "syncStatus"], { unique: false });

        const outbox = db.createObjectStore(STORE_OUTBOX, { keyPath: "outboxId" });
        outbox.createIndex("by_owner_kind_status", ["owner", "kind", "status"], { unique: false });
        outbox.createIndex("by_owner_createdAt", ["owner", "createdAt"], { unique: false });
        outbox.createIndex("by_owner_clientId", ["owner", "clientId"], { unique: false });

        // Prevent unused var lint in some setups
        void meta;
      }
    };
    return promisifyRequest(req);
  }

  function tx(db, storeNames, mode = "readonly") {
    const t = db.transaction(storeNames, mode);
    return { t, stores: storeNames.map((n) => t.objectStore(n)) };
  }

  function nowIso() {
    return new Date().toISOString();
  }

  function uuid() {
    if (crypto && crypto.randomUUID) {
      return crypto.randomUUID();
    }
    // Fallback: RFC4122-ish
    const buf = new Uint8Array(16);
    (crypto || window.crypto).getRandomValues(buf);
    buf[6] = (buf[6] & 0x0f) | 0x40;
    buf[8] = (buf[8] & 0x3f) | 0x80;
    const hex = Array.from(buf, (b) => b.toString(16).padStart(2, "0")).join("");
    return (
      hex.slice(0, 8) +
      "-" +
      hex.slice(8, 12) +
      "-" +
      hex.slice(12, 16) +
      "-" +
      hex.slice(16, 20) +
      "-" +
      hex.slice(20)
    );
  }

  async function metaGet(key) {
    const db = await withDb();
    const { t, stores } = tx(db, [STORE_META], "readonly");
    const req = stores[0].get(key);
    const val = await promisifyRequest(req);
    await promisifyRequest(t.done || (() => t.complete)());
    db.close();
    return val;
  }

  async function metaSet(key, value) {
    const db = await withDb();
    const { t, stores } = tx(db, [STORE_META], "readwrite");
    stores[0].put(value, key);
    await new Promise((resolve, reject) => {
      t.oncomplete = () => resolve();
      t.onerror = () => reject(t.error);
      t.onabort = () => reject(t.error);
    });
    db.close();
  }

  async function getOrCreateDeviceId() {
    let deviceId = null;
    try {
      deviceId = localStorage.getItem("fh-device-id");
    } catch (e) {
      deviceId = null;
    }
    if (!deviceId) {
      deviceId = await metaGet("deviceId");
    }
    if (!deviceId) {
      deviceId = uuid();
    }
    try {
      localStorage.setItem("fh-device-id", deviceId);
    } catch (e) {
      // ignore
    }
    await metaSet("deviceId", deviceId);
    return deviceId;
  }

  function normalizeEquityTrade(input) {
    const t = { ...input };
    t.clientId = t.clientId || uuid();
    t.kind = "equity";
    t.owner = (t.owner || "").trim();
    t.date = (t.date || "").trim();
    t.code = (t.code || "").trim();
    t.name = (t.name || "").trim();
    t.side = (t.side || "").trim();
    t.price = (t.price ?? "").toString();
    t.quantity = (t.quantity ?? "").toString();
    t.amount = (t.amount ?? "").toString();
    t.amountAuto = (t.amountAuto ?? t.amount_auto ?? "0").toString();
    const ts = nowIso();
    t.createdAt = t.createdAt || ts;
    t.updatedAt = ts;
    t.deletedAt = t.deletedAt || null;
    t.syncStatus = t.syncStatus || "local"; // local|queued|synced|error
    return t;
  }

  function normalizeCryptoTrade(input) {
    const t = { ...input };
    t.clientId = t.clientId || uuid();
    t.kind = "crypto";
    t.owner = (t.owner || "").trim();
    t.date = (t.date || "").trim();
    t.code = (t.code || "").trim().toUpperCase();
    t.platform = (t.platform || "").trim();
    t.side = (t.side || "").trim();
    t.price = (t.price ?? "").toString();
    t.quantity = (t.quantity ?? "").toString();
    const ts = nowIso();
    t.createdAt = t.createdAt || ts;
    t.updatedAt = ts;
    t.deletedAt = t.deletedAt || null;
    t.syncStatus = t.syncStatus || "local";
    return t;
  }

  async function putTrade(kind, trade) {
    const storeName = kind === "crypto" ? STORE_CRYPTO : STORE_EQUITY;
    const normalized = kind === "crypto" ? normalizeCryptoTrade(trade) : normalizeEquityTrade(trade);

    const db = await withDb();
    const { t, stores } = tx(db, [storeName], "readwrite");
    stores[0].put(normalized);
    await new Promise((resolve, reject) => {
      t.oncomplete = () => resolve();
      t.onerror = () => reject(t.error);
      t.onabort = () => reject(t.error);
    });
    db.close();
    return normalized;
  }

  async function getTrade(kind, clientId) {
    const storeName = kind === "crypto" ? STORE_CRYPTO : STORE_EQUITY;
    const db = await withDb();
    const { t, stores } = tx(db, [storeName], "readonly");
    const val = await promisifyRequest(stores[0].get(clientId));
    await new Promise((resolve, reject) => {
      t.oncomplete = () => resolve();
      t.onerror = () => reject(t.error);
      t.onabort = () => reject(t.error);
    });
    db.close();
    return val || null;
  }

  async function listTrades(kind, owner) {
    const storeName = kind === "crypto" ? STORE_CRYPTO : STORE_EQUITY;
    const db = await withDb();
    const { t, stores } = tx(db, [storeName], "readonly");
    const idx = stores[0].index("by_owner_date");
    const range = IDBKeyRange.bound([owner, ""], [owner, "\uffff"]);
    const rows = await promisifyRequest(idx.getAll(range));
    await new Promise((resolve, reject) => {
      t.oncomplete = () => resolve();
      t.onerror = () => reject(t.error);
      t.onabort = () => reject(t.error);
    });
    db.close();
    const filtered = (rows || []).filter((r) => !r.deletedAt);
    filtered.sort((a, b) => (b.date || "").localeCompare(a.date || "") || (b.updatedAt || "").localeCompare(a.updatedAt || ""));
    return filtered;
  }

  async function softDeleteTrade(kind, clientId) {
    const existing = await getTrade(kind, clientId);
    if (!existing) return false;
    const updated = { ...existing, deletedAt: nowIso(), updatedAt: nowIso(), syncStatus: "local" };
    await putTrade(kind, updated);
    return true;
  }

  async function enqueueOutbox(entry) {
    const e = { ...entry };
    e.outboxId = e.outboxId || uuid();
    e.owner = (e.owner || "").trim();
    e.kind = e.kind || "equity"; // equity|crypto
    e.clientId = e.clientId || "";
    e.op = e.op || "upsert"; // upsert|delete|import
    e.status = e.status || "pending"; // pending|sending|done|error
    e.createdAt = e.createdAt || nowIso();
    e.lastError = e.lastError || null;

    const db = await withDb();
    const { t, stores } = tx(db, [STORE_OUTBOX], "readwrite");
    stores[0].put(e);
    await new Promise((resolve, reject) => {
      t.oncomplete = () => resolve();
      t.onerror = () => reject(t.error);
      t.onabort = () => reject(t.error);
    });
    db.close();
    return e;
  }

  async function outboxCount(owner) {
    const db = await withDb();
    const { t, stores } = tx(db, [STORE_OUTBOX], "readonly");
    const idx = stores[0].index("by_owner_kind_status");
    const range = IDBKeyRange.bound([owner, "", "pending"], [owner, "\uffff", "pending"]);
    // Note: IDB doesn't support prefix wildcards; we use broad range with kind between "" and \uffff.
    const all = await promisifyRequest(idx.getAll(range));
    await new Promise((resolve, reject) => {
      t.oncomplete = () => resolve();
      t.onerror = () => reject(t.error);
      t.onabort = () => reject(t.error);
    });
    db.close();
    return (all || []).length;
  }

  async function outboxGetBatch(owner, kind, limit = 50) {
    const db = await withDb();
    const { t, stores } = tx(db, [STORE_OUTBOX], "readonly");
    const idx = stores[0].index("by_owner_kind_status");
    const range = IDBKeyRange.only([owner, kind, "pending"]);
    const items = await promisifyRequest(idx.getAll(range, limit));
    await new Promise((resolve, reject) => {
      t.oncomplete = () => resolve();
      t.onerror = () => reject(t.error);
      t.onabort = () => reject(t.error);
    });
    db.close();
    return items || [];
  }

  async function outboxMarkDone(outboxIds) {
    const db = await withDb();
    const { t, stores } = tx(db, [STORE_OUTBOX], "readwrite");
    const store = stores[0];
    for (const id of outboxIds) {
      store.delete(id);
    }
    await new Promise((resolve, reject) => {
      t.oncomplete = () => resolve();
      t.onerror = () => reject(t.error);
      t.onabort = () => reject(t.error);
    });
    db.close();
  }

  async function markTradeSynced(kind, clientId) {
    const existing = await getTrade(kind, clientId);
    if (!existing) return;
    const updated = { ...existing, syncStatus: "synced", updatedAt: nowIso() };
    await putTrade(kind, updated);
  }

  async function markTradeQueued(kind, clientId) {
    const existing = await getTrade(kind, clientId);
    if (!existing) return;
    const updated = { ...existing, syncStatus: "queued", updatedAt: nowIso() };
    await putTrade(kind, updated);
  }

  function legacyStableId(kind, owner, rec) {
    // Deterministic ID for historical records without clientId.
    // Avoids duplicate bootstraps and enables cross-device de-dup.
    const s = [
      kind,
      owner,
      rec.date || "",
      rec.code || "",
      rec.platform || "",
      rec.side || "",
      rec.price || "",
      rec.quantity || "",
      rec.amount || "",
      rec.name || "",
    ].join("|");
    let h = 5381;
    for (let i = 0; i < s.length; i++) {
      h = ((h << 5) + h) ^ s.charCodeAt(i);
      h = h >>> 0;
    }
    return `legacy_${kind}_${h.toString(16)}`;
  }

  async function bootstrapOnce(owner, fetcher) {
    const key = `bootstrap:${owner}`;
    const done = await metaGet(key);
    if (done) return { bootstrapped: true, count: 0 };
    const data = await fetcher();
    const equity = Array.isArray(data.equity) ? data.equity : [];
    const crypto = Array.isArray(data.crypto) ? data.crypto : [];
    let count = 0;
    for (const r of equity) {
      const clientId = (r && r.clientId) ? String(r.clientId).trim() : "";
      await putTrade("equity", { ...r, clientId: clientId || legacyStableId("equity", owner, r || {}), owner, syncStatus: "synced" });
      count += 1;
    }
    for (const r of crypto) {
      const clientId = (r && r.clientId) ? String(r.clientId).trim() : "";
      await putTrade("crypto", { ...r, clientId: clientId || legacyStableId("crypto", owner, r || {}), owner, syncStatus: "synced" });
      count += 1;
    }
    await metaSet(key, true);
    return { bootstrapped: true, count };
  }

  window.FH_IDB = {
    DB_NAME,
    DB_VERSION,
    getOrCreateDeviceId,
    metaGet,
    metaSet,
    uuid,
    nowIso,
    putTrade,
    getTrade,
    listTrades,
    softDeleteTrade,
    enqueueOutbox,
    outboxCount,
    outboxGetBatch,
    outboxMarkDone,
    markTradeSynced,
    markTradeQueued,
    bootstrapOnce,
  };
})();

