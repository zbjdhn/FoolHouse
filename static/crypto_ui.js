(() => {
  if (!window.FH_IDB) return;

  function qs(sel, root = document) {
    return root.querySelector(sel);
  }

  function getOwner() {
    const el = qs("[data-fh-owner]");
    return el ? (el.getAttribute("data-fh-owner") || "") : "";
  }

  function getPage() {
    const el = document.body;
    return (el && el.getAttribute("data-fh-page")) || "";
  }

  async function ensureBootstrap() {
    const owner = getOwner();
    if (!owner) return;
    await FH_IDB.bootstrapOnce(owner, async () => {
      const resp = await fetch("/api/bootstrap", { credentials: "same-origin" });
      if (!resp.ok) return { equity: [], crypto: [] };
      return await resp.json();
    });
  }

  async function renderCryptoTable() {
    const owner = getOwner();
    if (!owner) return;
    const tbody = qs("#crypto-trades-tbody");
    const emptyWrap = qs("[data-fh-empty-state]");
    const tableWrap = qs("[data-fh-table-state]");
    if (!tbody) return;
    const trades = await FH_IDB.listTrades("crypto", owner);
    if (!trades.length) {
      if (tableWrap) tableWrap.style.display = "none";
      if (emptyWrap) emptyWrap.style.display = "block";
      return;
    }
    if (emptyWrap) emptyWrap.style.display = "none";
    if (tableWrap) tableWrap.style.display = "block";

    tbody.innerHTML = "";
    for (const trade of trades) {
      const tr = document.createElement("tr");
      tr.setAttribute("data-client-id", trade.clientId);
      tr.innerHTML = `
        <td>${trade.date || ""}</td>
        <td>${trade.code || ""}</td>
        <td>${trade.platform || ""}</td>
        <td>${trade.side || ""}</td>
        <td class="text-end">${trade.price || ""}</td>
        <td class="text-end">${trade.quantity || ""}</td>
        <td class="text-center">
          <a href="/crypto/edit/0?clientId=${encodeURIComponent(trade.clientId)}" class="btn btn-sm btn-outline-primary me-1">编辑</a>
          <button type="button" class="btn btn-sm btn-outline-danger" data-fh-delete>删除</button>
        </td>
      `;
      tbody.appendChild(tr);
    }
  }

  async function bindCryptoListInteractions() {
    const tbody = qs("#crypto-trades-tbody");
    if (!tbody) return;
    tbody.addEventListener("click", async (e) => {
      const target = e.target;
      if (!(target instanceof Element)) return;
      if (!target.hasAttribute("data-fh-delete")) return;
      const row = target.closest("tr");
      const clientId = row ? row.getAttribute("data-client-id") : null;
      if (!clientId) return;
      if (!confirm("确定要删除这条交易记录吗？")) return;
      const owner = getOwner();
      await FH_IDB.softDeleteTrade("crypto", clientId);
      await FH_IDB.enqueueOutbox({
        owner,
        kind: "crypto",
        clientId,
        op: "delete",
        payload: { clientId },
      });
      await FH_IDB.markTradeQueued("crypto", clientId);
      await renderCryptoTable();
    });
  }

  async function bindCryptoForm(mode) {
    const owner = getOwner();
    if (!owner) return;
    const form = qs("form[data-fh-trade-form]");
    if (!form) return;
    const dateInput = qs("#date");
    const codeInput = qs("#code");
    const platformInput = qs("#platform");
    const sideInput = qs("#side");
    const priceInput = qs("#price");
    const quantityInput = qs("#quantity");

    const clientIdParam = new URLSearchParams(location.search).get("clientId");
    let editing = null;
    if (mode === "edit" && clientIdParam) {
      editing = await FH_IDB.getTrade("crypto", clientIdParam);
      if (editing) {
        if (dateInput) dateInput.value = editing.date || "";
        if (codeInput) codeInput.value = editing.code || "";
        if (platformInput) platformInput.value = editing.platform || "";
        if (sideInput) sideInput.value = editing.side || "";
        if (priceInput) priceInput.value = editing.price || "";
        if (quantityInput) quantityInput.value = editing.quantity || "";
      }
    }

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const t = {
        clientId: editing ? editing.clientId : undefined,
        owner,
        date: dateInput ? dateInput.value : "",
        code: codeInput ? codeInput.value : "",
        platform: platformInput ? platformInput.value : "",
        side: sideInput ? sideInput.value : "",
        price: priceInput ? priceInput.value : "",
        quantity: quantityInput ? quantityInput.value : "",
      };
      const saved = await FH_IDB.putTrade("crypto", t);
      await FH_IDB.enqueueOutbox({
        owner,
        kind: "crypto",
        clientId: saved.clientId,
        op: "upsert",
        payload: saved,
      });
      await FH_IDB.markTradeQueued("crypto", saved.clientId);
      location.href = "/crypto/trades";
    });
  }

  async function main() {
    const page = getPage();
    if (!page) return;
    await ensureBootstrap();
    if (page === "crypto_list") {
      await renderCryptoTable();
      await bindCryptoListInteractions();
    }
    if (page === "crypto_add") {
      await bindCryptoForm("add");
    }
    if (page === "crypto_edit") {
      await bindCryptoForm("edit");
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    main().catch(() => {});
  });
})();

