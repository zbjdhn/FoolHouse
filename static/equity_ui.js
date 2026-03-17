(() => {
  if (!window.FH_IDB) return;

  function qs(sel, root = document) {
    return root.querySelector(sel);
  }
  function qsa(sel, root = document) {
    return Array.from(root.querySelectorAll(sel));
  }

  function getOwner() {
    const el = qs("[data-fh-owner]");
    return el ? (el.getAttribute("data-fh-owner") || "") : "";
  }

  function getPage() {
    const el = document.body;
    return (el && el.getAttribute("data-fh-page")) || "";
  }

  function fmt2(v) {
    const n = Number(v);
    if (!isFinite(n)) return "";
    return n.toFixed(2);
  }

  function parseDateValue(dateText) {
    const s = (dateText || "").trim();
    if (/^\d{8}$/.test(s)) return parseInt(s, 10);
    if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return parseInt(s.replace(/-/g, ""), 10);
    return 0;
  }

  function computeFee(trade) {
    if ((trade.side || "") === "红股入账") return "-";
    const amt = Math.abs(Number(trade.amount || 0));
    const qty = Number(trade.quantity || 0);
    const pr = Number(trade.price || 0);
    if (!isFinite(amt) || !isFinite(qty) || !isFinite(pr)) return "";
    return fmt2(Math.abs(amt - pr * qty));
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

  async function renderTradesTable() {
    const owner = getOwner();
    if (!owner) return;

    const tbody = qs("#trades-tbody");
    const emptyWrap = qs("[data-fh-empty-state]");
    const tableWrap = qs("[data-fh-table-state]");
    if (!tbody) return;

    const trades = await FH_IDB.listTrades("equity", owner);
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
      tr.setAttribute("data-code", trade.code || "");

      const amountAuto = (trade.amountAuto || trade.amount_auto || "0").toString();
      const autoBadge =
        amountAuto === "1"
          ? `<span class="badge bg-warning text-dark ms-1 align-middle" title="该发生金额由成交价格×成交数量自动计算，未含手续费" aria-label="自动计算提示">!</span>`
          : "";

      const priceCell = (trade.side || "") === "红股入账" ? "-" : (trade.price || "");
      const amountCell = (trade.side || "") === "红股入账" ? "-" : `${trade.amount || ""}${autoBadge}`;

      tr.innerHTML = `
        <td>${trade.date || ""}</td>
        <td><a href="#" class="code-filter-link text-decoration-none" data-code="${trade.code || ""}">${trade.code || ""}</a></td>
        <td class="stock-name-cell" data-code="${trade.code || ""}">
          <span class="stock-name-placeholder">${trade.name ? trade.name : '<span class="text-muted">-</span>'}</span>
        </td>
        <td>${trade.side || ""}</td>
        <td class="text-end">${priceCell}</td>
        <td class="text-end">${trade.quantity || ""}</td>
        <td class="text-end">${amountCell}</td>
        <td class="text-end">${computeFee(trade)}</td>
        <td class="text-center">
          <a href="/edit/0?clientId=${encodeURIComponent(trade.clientId)}" class="btn btn-sm btn-outline-primary me-1">编辑</a>
          <button type="button" class="btn btn-sm btn-outline-danger" data-fh-delete>删除</button>
        </td>
      `;
      tbody.appendChild(tr);
    }

    // tooltips (if bootstrap present)
    if (window.bootstrap && bootstrap.Tooltip) {
      qsa('[title]').forEach((el) => {
        if (el.getAttribute("data-bs-toggle") === "tooltip") return;
        el.setAttribute("data-bs-toggle", "tooltip");
        new bootstrap.Tooltip(el);
      });
    }
  }

  async function bindTradesListInteractions() {
    const tbody = qs("#trades-tbody");
    const searchInput = qs("#search-input");
    const clearBtn = qs("#clear-search");
    const resultCount = qs("#search-result-count");
    const noResults = qs("#no-results");
    const sortAscBtn = qs("#sort-date-asc");
    const sortDescBtn = qs("#sort-date-desc");
    if (!tbody) return;

    let allRows = () => Array.from(tbody.querySelectorAll("tr"));

    function performSearch() {
      const term = (searchInput && searchInput.value ? searchInput.value : "").trim().toLowerCase();
      const rows = allRows();
      if (!term) {
        rows.forEach((r) => (r.style.display = ""));
        if (clearBtn) clearBtn.style.display = "none";
        if (resultCount) resultCount.textContent = "";
        if (noResults) noResults.style.display = "none";
        return;
      }
      let visible = 0;
      rows.forEach((row) => {
        const code = (row.getAttribute("data-code") || "").toLowerCase();
        const nameCell = row.querySelector(".stock-name-cell");
        const nameText = nameCell ? (nameCell.textContent || "").toLowerCase() : "";
        const ok = code.includes(term) || nameText.includes(term);
        row.style.display = ok ? "" : "none";
        if (ok) visible += 1;
      });
      if (clearBtn) clearBtn.style.display = "inline-block";
      if (resultCount) resultCount.textContent = `找到 ${visible} 条记录`;
      if (noResults) noResults.style.display = visible === 0 ? "block" : "none";
    }

    function sortRows(asc) {
      const rows = allRows();
      rows.sort((a, b) => {
        const da = parseDateValue(a.cells[0].textContent);
        const db = parseDateValue(b.cells[0].textContent);
        return asc ? da - db : db - da;
      });
      rows.forEach((r) => tbody.appendChild(r));
    }

    tbody.addEventListener("click", async (e) => {
      const target = e.target;
      if (!(target instanceof Element)) return;
      if (target.classList.contains("code-filter-link")) {
        e.preventDefault();
        const code = target.getAttribute("data-code") || "";
        if (searchInput) searchInput.value = code;
        performSearch();
        return;
      }
      if (target.hasAttribute("data-fh-delete")) {
        const row = target.closest("tr");
        const clientId = row ? row.getAttribute("data-client-id") : null;
        if (!clientId) return;
        if (!confirm("确定要删除这条交易记录吗？")) return;
        const owner = getOwner();
        await FH_IDB.softDeleteTrade("equity", clientId);
        await FH_IDB.enqueueOutbox({
          owner,
          kind: "equity",
          clientId,
          op: "delete",
          payload: { clientId },
        });
        await FH_IDB.markTradeQueued("equity", clientId);
        await renderTradesTable();
        performSearch();
      }
    });

    if (searchInput) searchInput.addEventListener("input", performSearch);
    if (clearBtn) clearBtn.addEventListener("click", () => {
      if (searchInput) searchInput.value = "";
      performSearch();
    });
    if (sortAscBtn) sortAscBtn.addEventListener("click", () => {
      sortRows(true);
      performSearch();
    });
    if (sortDescBtn) sortDescBtn.addEventListener("click", () => {
      sortRows(false);
      performSearch();
    });
  }

  async function bindEquityForm(mode) {
    const owner = getOwner();
    if (!owner) return;

    const form = qs("form[data-fh-trade-form]");
    if (!form) return;

    const codeInput = qs("#code");
    const nameHidden = qs("#name");
    const dateInput = qs("#date");
    const sideSelect = qs("#side");
    const priceInput = qs("#price");
    const quantityInput = qs("#quantity");
    const amountInput = qs("#amount");

    const clientIdParam = new URLSearchParams(location.search).get("clientId");
    let editing = null;
    if (mode === "edit" && clientIdParam) {
      editing = await FH_IDB.getTrade("equity", clientIdParam);
      if (editing) {
        if (codeInput) codeInput.value = editing.code || "";
        if (nameHidden) nameHidden.value = editing.name || "";
        if (dateInput) dateInput.value = editing.date || "";
        if (sideSelect) sideSelect.value = editing.side || "";
        if (priceInput) priceInput.value = editing.price || "";
        if (quantityInput) quantityInput.value = editing.quantity || "";
        if (amountInput) amountInput.value = editing.amount || "";
      }
    }

    function updateFieldsForSide() {
      const isBonus = sideSelect && sideSelect.value === "红股入账";
      if (priceInput && amountInput) {
        priceInput.required = !isBonus;
        amountInput.required = !isBonus;
        priceInput.disabled = isBonus;
        amountInput.disabled = isBonus;
        if (isBonus) {
          priceInput.value = "0";
          amountInput.value = "0";
          amountInput.dataset.manual = "0";
        }
      }
    }

    function updateAmount() {
      if ((sideSelect && sideSelect.value === "红股入账") || (amountInput && amountInput.dataset.manual === "1")) {
        return;
      }
      const price = Number(priceInput && priceInput.value ? priceInput.value : "");
      const qty = Number(quantityInput && quantityInput.value ? quantityInput.value : "");
      if (isFinite(price) && isFinite(qty) && price > 0 && qty > 0 && amountInput) {
        amountInput.value = (price * qty).toFixed(2);
        amountInput.dataset.manual = "0";
      }
    }

    if (sideSelect) {
      sideSelect.addEventListener("change", updateFieldsForSide);
      updateFieldsForSide();
    }
    if (priceInput) priceInput.addEventListener("input", updateAmount);
    if (quantityInput) quantityInput.addEventListener("input", updateAmount);
    if (amountInput) amountInput.addEventListener("input", () => (amountInput.dataset.manual = "1"));

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const t = {
        clientId: editing ? editing.clientId : undefined,
        owner,
        date: dateInput ? dateInput.value : "",
        code: codeInput ? codeInput.value : "",
        name: nameHidden ? nameHidden.value : "",
        side: sideSelect ? sideSelect.value : "",
        price: priceInput ? priceInput.value : "",
        quantity: quantityInput ? quantityInput.value : "",
        amount: amountInput ? amountInput.value : "",
        amountAuto: amountInput && amountInput.dataset.manual === "1" ? "0" : "1",
      };
      const saved = await FH_IDB.putTrade("equity", t);
      await FH_IDB.enqueueOutbox({
        owner,
        kind: "equity",
        clientId: saved.clientId,
        op: "upsert",
        payload: saved,
      });
      await FH_IDB.markTradeQueued("equity", saved.clientId);
      location.href = "/trades";
    });
  }

  async function main() {
    const page = getPage();
    if (!page) return;
    await ensureBootstrap();
    if (page === "equity_list") {
      await renderTradesTable();
      await bindTradesListInteractions();
    }
    if (page === "equity_add") {
      await bindEquityForm("add");
    }
    if (page === "equity_edit") {
      await bindEquityForm("edit");
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    main().catch(() => {});
  });
})();

