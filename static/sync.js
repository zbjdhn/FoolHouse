(() => {
  if (!window.FH_IDB) return;

  function qs(sel, root = document) {
    return root.querySelector(sel);
  }

  function getOwner() {
    const el = document.body;
    return (el && el.getAttribute("data-fh-owner")) || "";
  }

  function setText(el, text) {
    if (el) el.textContent = text;
  }

  function showFlash(kind, msg) {
    const host = qs("[data-fh-flash-host]");
    if (!host) return;
    host.innerHTML = `<div class="alert alert-${kind}" role="alert"><div>${msg}</div></div>`;
  }

  async function refreshSyncBadge() {
    const owner = getOwner();
    if (!owner) return;
    const count = await FH_IDB.outboxCount(owner);
    const badge = qs("[data-fh-sync-badge]");
    if (!badge) return;
    badge.style.display = count > 0 ? "inline-block" : "none";
    setText(badge, String(count));
  }

  async function syncKind(kind) {
    const owner = getOwner();
    if (!owner) return { accepted: 0, errors: 0 };
    const deviceId = await FH_IDB.getOrCreateDeviceId();

    let acceptedTotal = 0;
    let errorsTotal = 0;

    // Drain in batches
    while (true) {
      const batch = await FH_IDB.outboxGetBatch(owner, kind, 50);
      if (!batch.length) break;

      const records = batch.map((x) => ({
        clientId: x.clientId,
        op: x.op,
        payload: x.payload || x.payload === 0 ? x.payload : x.payload, // keep as-is
      }));

      const resp = await fetch(kind === "crypto" ? "/api/sync/crypto" : "/api/sync/equity", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ deviceId, records }),
      });

      if (!resp.ok) {
        const txt = await resp.text();
        throw new Error(`sync failed (${kind}): ${resp.status} ${txt}`);
      }
      const data = await resp.json();
      const accepted = Array.isArray(data.accepted) ? data.accepted : [];
      const errs = Array.isArray(data.errors) ? data.errors : [];

      // Mark accepted: remove outbox items that match accepted clientIds.
      const acceptedSet = new Set(accepted);
      const doneIds = batch.filter((x) => acceptedSet.has(x.clientId)).map((x) => x.outboxId);
      await FH_IDB.outboxMarkDone(doneIds);
      for (const cid of accepted) {
        await FH_IDB.markTradeSynced(kind, cid);
      }

      acceptedTotal += accepted.length;
      errorsTotal += errs.length;

      if (accepted.length === 0) {
        // Avoid infinite loop if server rejects everything but still ok.
        break;
      }
    }

    await FH_IDB.metaSet(`lastSync:${owner}`, new Date().toISOString());
    return { accepted: acceptedTotal, errors: errorsTotal };
  }

  async function runSync() {
    const owner = getOwner();
    if (!owner) return;
    const btn = qs("[data-fh-sync-btn]");
    if (btn) btn.disabled = true;
    try {
      showFlash("info", "正在同步本地记录到云端…");
      const eq = await syncKind("equity");
      const cr = await syncKind("crypto");
      await refreshSyncBadge();
      showFlash("success", `同步完成：A股 ${eq.accepted} 条，Crypto ${cr.accepted} 条。${eq.errors || cr.errors ? "（部分记录有错误，可稍后重试）" : ""}`);
    } catch (e) {
      await refreshSyncBadge();
      showFlash("danger", `同步失败：${e && e.message ? e.message : String(e)}`);
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  function bind() {
    const btn = qs("[data-fh-sync-btn]");
    if (!btn) return;
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      runSync();
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    bind();
    refreshSyncBadge().catch(() => {});
  });
})();

