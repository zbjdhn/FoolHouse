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
    return (document.body && document.body.getAttribute("data-fh-page")) || "";
  }

  function normStr(v) {
    if (v === null || v === undefined) return "";
    return String(v).trim();
  }

  function toDateStr(v) {
    // Accept: Date, YYYYMMDD, YYYY-MM-DD, Excel serial
    if (v instanceof Date && !isNaN(v.getTime())) {
      const yyyy = v.getFullYear();
      const mm = String(v.getMonth() + 1).padStart(2, "0");
      const dd = String(v.getDate()).padStart(2, "0");
      return `${yyyy}-${mm}-${dd}`;
    }
    const s = normStr(v);
    if (/^\d{8}$/.test(s)) {
      return `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}`;
    }
    if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s;
    // Excel serial date (days since 1899-12-30)
    const n = Number(v);
    if (isFinite(n) && n > 20000 && n < 90000) {
      const epoch = new Date(Date.UTC(1899, 11, 30));
      const d = new Date(epoch.getTime() + n * 86400 * 1000);
      if (!isNaN(d.getTime())) {
        const yyyy = d.getUTCFullYear();
        const mm = String(d.getUTCMonth() + 1).padStart(2, "0");
        const dd = String(d.getUTCDate()).padStart(2, "0");
        return `${yyyy}-${mm}-${dd}`;
      }
    }
    return "";
  }

  function findColumn(headers, candidates) {
    const normHeaders = headers.map((h) => normStr(h));
    for (let i = 0; i < normHeaders.length; i++) {
      const h = normHeaders[i];
      for (const c of candidates) {
        if (h === c || h.toLowerCase() === c.toLowerCase()) return i;
      }
    }
    return -1;
  }

  const EQUITY_COLS = {
    date: ["成交日期", "日期", "date", "Date", "DATE", "交易日期", "成交日"],
    code: ["证券代码", "代码", "code", "Code", "CODE", "股票代码", "证券"],
    side: ["买卖标志", "买卖方向", "方向", "side", "Side", "SIDE", "交易方向", "类型"],
    price: ["成交价格", "价格", "price", "Price", "PRICE", "单价"],
    quantity: ["成交数量", "数量", "quantity", "Quantity", "QUANTITY", "股数", "数量(股)"],
    amount: ["发生金额", "金额", "amount", "Amount", "AMOUNT", "总金额", "金额(元)"],
    name: ["证券名称", "名称", "证券简称", "股票名称", "name", "Name", "NAME"],
  };

  const CRYPTO_COLS = {
    date: ["成交日期", "日期", "date", "Date", "DATE", "交易日期", "成交日"],
    code: ["代币代码", "代码", "币种", "code", "symbol", "Symbol", "SYMBOL"],
    side: ["买卖标志", "买卖方向", "方向", "side", "类型", "Side", "SIDE"],
    price: ["成交价格", "价格", "price", "Price", "PRICE", "单价"],
    quantity: ["成交数量", "数量", "quantity", "Quantity", "QUANTITY", "数量(币)"],
    platform: ["平台", "platform", "Platform", "PLATFORM", "交易所", "Exchange"],
  };

  function mapEquitySide(raw) {
    const s = normStr(raw);
    const variants = {
      "证券买入": ["证券买入", "买入", "BUY", "Buy", "buy", "B"],
      "证券卖出": ["证券卖出", "卖出", "SELL", "Sell", "sell", "S"],
      "配售申购": ["配售申购", "申购", "SUB", "Subscription"],
      "红股入账": ["红股入账", "红股", "分红送股", "DIV", "Dividend"],
    };
    for (const k of Object.keys(variants)) {
      if (variants[k].includes(s)) return k;
    }
    return s;
  }

  function mapCryptoSide(raw) {
    const s = normStr(raw);
    if (!s) return s;
    if (["买入", "BUY", "Buy", "buy"].includes(s)) return "买入";
    if (["卖出", "SELL", "Sell", "sell"].includes(s)) return "卖出";
    return s;
  }

  async function parseAndImportEquity(file) {
    if (!window.XLSX) throw new Error("XLSX 未加载");
    const owner = getOwner();
    const buf = await file.arrayBuffer();
    const wb = XLSX.read(buf, { type: "array" });
    const sheetName = wb.SheetNames[0];
    const ws = wb.Sheets[sheetName];
    const rows = XLSX.utils.sheet_to_json(ws, { header: 1, raw: true, defval: "" });
    if (!rows.length) return { ok: true, count: 0, errors: [] };

    const header = rows[0];
    const idx = {
      date: findColumn(header, EQUITY_COLS.date),
      code: findColumn(header, EQUITY_COLS.code),
      side: findColumn(header, EQUITY_COLS.side),
      price: findColumn(header, EQUITY_COLS.price),
      quantity: findColumn(header, EQUITY_COLS.quantity),
      amount: findColumn(header, EQUITY_COLS.amount),
      name: findColumn(header, EQUITY_COLS.name),
    };
    const required = ["date", "code", "side", "price", "quantity", "amount"];
    for (const k of required) {
      if (idx[k] < 0) {
        throw new Error(`未找到必需的列：${EQUITY_COLS[k][0]}`);
      }
    }

    let count = 0;
    const errors = [];
    for (let r = 1; r < rows.length; r++) {
      const row = rows[r];
      if (!row || row.every((c) => normStr(c) === "")) continue;
      const rowNum = r + 1;
      const date = toDateStr(row[idx.date]);
      const code = normStr(row[idx.code]);
      const side = mapEquitySide(row[idx.side]);
      const price = normStr(row[idx.price]);
      const quantity = normStr(row[idx.quantity]);
      let amount = normStr(row[idx.amount]);
      const name = idx.name >= 0 ? normStr(row[idx.name]) : "";

      if (!date || !code || !side || !price || !quantity) {
        errors.push(`第${rowNum}行：字段缺失（date/code/side/price/quantity）`);
        continue;
      }
      // amount auto-calc if empty
      let amountAuto = "0";
      if (!amount) {
        const p = Number(price);
        const q = Number(quantity);
        if (isFinite(p) && isFinite(q)) {
          amount = (p * q).toFixed(2);
          amountAuto = "1";
        } else {
          errors.push(`第${rowNum}行：发生金额为空且无法自动计算`);
          continue;
        }
      }

      const saved = await FH_IDB.putTrade("equity", {
        owner,
        date,
        code,
        name,
        side,
        price,
        quantity,
        amount,
        amountAuto,
      });
      await FH_IDB.enqueueOutbox({ owner, kind: "equity", clientId: saved.clientId, op: "upsert", payload: saved });
      await FH_IDB.markTradeQueued("equity", saved.clientId);
      count += 1;
    }
    return { ok: errors.length === 0, count, errors };
  }

  async function parseAndImportCrypto(file) {
    if (!window.XLSX) throw new Error("XLSX 未加载");
    const owner = getOwner();
    const buf = await file.arrayBuffer();
    const wb = XLSX.read(buf, { type: "array" });
    const sheetName = wb.SheetNames[0];
    const ws = wb.Sheets[sheetName];
    const rows = XLSX.utils.sheet_to_json(ws, { header: 1, raw: true, defval: "" });
    if (!rows.length) return { ok: true, count: 0, errors: [] };

    const header = rows[0];
    const idx = {
      date: findColumn(header, CRYPTO_COLS.date),
      code: findColumn(header, CRYPTO_COLS.code),
      side: findColumn(header, CRYPTO_COLS.side),
      price: findColumn(header, CRYPTO_COLS.price),
      quantity: findColumn(header, CRYPTO_COLS.quantity),
      platform: findColumn(header, CRYPTO_COLS.platform),
    };
    const required = ["date", "code", "side", "price", "quantity"];
    for (const k of required) {
      if (idx[k] < 0) {
        throw new Error(`未找到必需的列：${CRYPTO_COLS[k][0]}`);
      }
    }

    let count = 0;
    const errors = [];
    for (let r = 1; r < rows.length; r++) {
      const row = rows[r];
      if (!row || row.every((c) => normStr(c) === "")) continue;
      const rowNum = r + 1;
      const date = toDateStr(row[idx.date]);
      const code = normStr(row[idx.code]).toUpperCase();
      const side = mapCryptoSide(row[idx.side]);
      const price = normStr(row[idx.price]);
      const quantity = normStr(row[idx.quantity]);
      const platform = idx.platform >= 0 ? normStr(row[idx.platform]) : "";

      if (!date || !code || !side || !price || !quantity) {
        errors.push(`第${rowNum}行：字段缺失（date/code/side/price/quantity）`);
        continue;
      }

      const saved = await FH_IDB.putTrade("crypto", { owner, date, code, side, price, quantity, platform });
      await FH_IDB.enqueueOutbox({ owner, kind: "crypto", clientId: saved.clientId, op: "upsert", payload: saved });
      await FH_IDB.markTradeQueued("crypto", saved.clientId);
      count += 1;
    }
    return { ok: errors.length === 0, count, errors };
  }

  function renderResult(container, result) {
    if (!container) return;
    if (!result) {
      container.innerHTML = "";
      return;
    }
    const errHtml = (result.errors || [])
      .slice(0, 200)
      .map((e) => `<li>${String(e)}</li>`)
      .join("");
    const errBlock =
      result.errors && result.errors.length
        ? `<div class="alert alert-danger mt-3"><h6 class="alert-heading">错误详情：</h6><ul class="mb-0" style="max-height: 300px; overflow-y: auto;">${errHtml}</ul></div>`
        : "";
    container.innerHTML = `
      <div class="alert alert-${result.errors && result.errors.length ? "warning" : "success"} mt-3">
        <strong>导入完成</strong>：成功 ${result.count || 0} 条${result.errors && result.errors.length ? `，错误 ${result.errors.length} 条` : ""}
      </div>
      ${errBlock}
    `;
  }

  async function main() {
    const page = getPage();
    if (page !== "equity_import" && page !== "crypto_import") return;

    const form = qs("form[data-fh-import-form]");
    const fileInput = qs("input[type=file][name=file]");
    const resultWrap = qs("[data-fh-import-result]");
    if (!form || !fileInput) return;

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const file = fileInput.files && fileInput.files[0] ? fileInput.files[0] : null;
      if (!file) return;
      try {
        const result = page === "equity_import" ? await parseAndImportEquity(file) : await parseAndImportCrypto(file);
        renderResult(resultWrap, result);
      } catch (err) {
        renderResult(resultWrap, { ok: false, count: 0, errors: [err && err.message ? err.message : String(err)] });
      }
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    main().catch(() => {});
  });
})();

