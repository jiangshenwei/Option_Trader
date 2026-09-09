const ETFS = {
  "510050": { name: "50ETF", spot: 2.505, chg: 0.82 },
  "510300": { name: "300ETF", spot: 3.892, chg: -0.35 },
  "510500": { name: "500ETF", spot: 7.689, chg: 1.12 },
};

let currentUnderlying = "510500";
let currentTQuoteMonthIdx = 0;
let tradeList = [];
let lastQuoteRefresh = null;
let homeRefreshTimer = null;

const SETTINGS_KEY = "etf-option-settings";
const DEFAULT_SETTINGS = {
  r: 0.02,
  q: 0,
  quoteRefreshSec: 8,
  homeRefreshSec: 30,
};

function loadSettings() {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (!raw) return { ...DEFAULT_SETTINGS };
    return { ...DEFAULT_SETTINGS, ...JSON.parse(raw) };
  } catch {
    return { ...DEFAULT_SETTINGS };
  }
}

let settings = loadSettings();

function saveSettings() {
  localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
  restartHomeRefreshTimer();
}

function formatTime(d) {
  return d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function quoteRefreshLabel() {
  return lastQuoteRefresh ? ` · 更新 ${formatTime(lastQuoteRefresh)}` : "";
}

/** 上交所 ETF 期权行权价间距（元） */
function strikeStep(spot) {
  if (spot <= 3) return 0.05;
  if (spot <= 5) return 0.1;
  if (spot <= 10) return 0.25;
  if (spot <= 20) return 0.5;
  if (spot <= 50) return 1;
  if (spot <= 100) return 2.5;
  return 5;
}

/** 仅展示现价 ±20% 范围内的行权价 */
function buildStrikes(spot) {
  const step = strikeStep(spot);
  const minK = spot * 0.8;
  const maxK = spot * 1.2;
  let k = Math.ceil(minK / step) * step;
  const all = [];
  while (k <= maxK + 1e-9) {
    all.push(Math.round(k * 10000) / 10000);
    k += step;
  }
  return {
    puts: all.filter((x) => x < spot),
    calls: all.filter((x) => x >= spot),
    step,
  };
}

/**
 * 上交所 ETF 期权挂牌月份：当月、下月、随后两个季月（3/6/9/12），共 4 个
 * 例：2026年9月 → 9月、10月、12月、次年3月
 */
function getSSEOptionMonths(refDate = new Date()) {
  const quarters = [3, 6, 9, 12];
  const y0 = refDate.getFullYear();
  const m0 = refDate.getMonth() + 1;

  const addMonth = (y, m, delta) => {
    const d = new Date(y, m - 1 + delta, 1);
    return { y: d.getFullYear(), m: d.getMonth() + 1 };
  };

  const cur = { y: y0, m: m0 };
  const nxt = addMonth(y0, m0, 1);

  const quarterSlots = [];
  for (let y = nxt.y; y <= nxt.y + 1; y++) {
    for (const q of quarters) {
      if (y === nxt.y && q <= nxt.m) continue;
      quarterSlots.push({ y, m: q });
    }
  }

  const raw = [cur, nxt, quarterSlots[0], quarterSlots[1]];
  const seen = new Set();
  const uniq = [];
  for (const item of raw) {
    if (!item) continue;
    const key = `${item.y}-${item.m}`;
    if (!seen.has(key)) {
      seen.add(key);
      uniq.push(item);
    }
  }

  return uniq.slice(0, 4).map((item) => ({
    ...item,
    label: item.m === m0 && item.y === y0 ? `${item.m}月(当月)` :
      item.m === nxt.m && item.y === nxt.y ? `${item.m}月(下月)` :
      `${item.y !== y0 ? item.y + "年" : ""}${item.m}月(季)`,
    shortLabel: `${item.m}月`,
  }));
}

function midIv(strike, monthIdx, isCall, spot) {
  const base = 18 + monthIdx * 1.5 + (isCall ? (strike - spot) * 2 : (spot - strike) * 2);
  const jitter = ((strike * 17 + monthIdx * 13) % 7) * 0.3;
  return Math.max(15, Math.min(35, base + jitter));
}

function midDelta(strike, spot, isCall) {
  if (isCall) return Math.max(0.05, Math.min(0.95, 0.5 + (spot - strike) * 0.8));
  return -Math.max(0.05, Math.min(0.95, 0.5 + (strike - spot) * 0.8));
}

function heatColor(iv, vmin = 18.2, vmax = 32.5) {
  const t = Math.max(0, Math.min(1, (iv - vmin) / (vmax - vmin)));
  const r = Math.round(254 - t * 154);
  const g = Math.round(242 - t * 192);
  const b = Math.round(242 - t * 192);
  return `rgb(${r},${g},${b})`;
}

function contractKey(strike, month, isCall) {
  return `${isCall ? "C" : "P"}_${strike}_${month}`;
}

function seedOhlc(seed) {
  const data = [];
  let price = seed;
  for (let i = 0; i < 60; i++) {
    const open = price;
    const change = (Math.sin(i / 5 + seed) + (Math.random() - 0.5) * 0.4) * 0.02;
    const close = Math.max(0.5, open + change);
    const high = Math.max(open, close) + Math.random() * 0.015;
    const low = Math.min(open, close) - Math.random() * 0.015;
    data.push({ open, high, low, close });
    price = close;
  }
  return data;
}

function drawCandles(canvas, ohlc) {
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  const pad = { l: 8, r: 8, t: 20, b: 16 };
  const plotW = w - pad.l - pad.r;
  const plotH = h - pad.t - pad.b;
  const visible = ohlc.slice(-40);
  const lows = visible.map((d) => d.low);
  const highs = visible.map((d) => d.high);
  const min = Math.min(...lows);
  const max = Math.max(...highs);
  const range = max - min || 0.01;

  const y = (v) => pad.t + plotH - ((v - min) / range) * plotH;
  const candleW = Math.max(4, plotW / visible.length - 2);

  ctx.fillStyle = "#64748b";
  ctx.font = "10px sans-serif";
  ctx.fillText("日K（蜡烛图）", pad.l, 12);

  visible.forEach((d, i) => {
    const x = pad.l + i * (plotW / visible.length) + candleW / 2;
    const up = d.close >= d.open;
    const color = up ? "#16a34a" : "#dc2626";

    ctx.strokeStyle = color;
    ctx.fillStyle = color;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x, y(d.high));
    ctx.lineTo(x, y(d.low));
    ctx.stroke();

    const top = y(Math.max(d.open, d.close));
    const bot = y(Math.min(d.open, d.close));
    const bodyH = Math.max(1, bot - top);
    ctx.fillRect(x - candleW / 2, top, candleW, bodyH);
  });
}

function renderHome() {
  const grid = document.getElementById("home-grid");
  grid.innerHTML = "";
  Object.entries(ETFS).forEach(([code, etf]) => {
    const card = document.createElement("div");
    card.className = "etf-card";
    const chgCls = etf.chg >= 0 ? "up" : "down";
    const chgSign = etf.chg >= 0 ? "+" : "";
    card.innerHTML = `
      <div class="etf-head">
        <div>
          <strong>${code} ${etf.name}</strong>
          <div class="muted">HV20 ${(20 + etf.spot).toFixed(1)}%</div>
        </div>
        <div>
          <div class="etf-price">${etf.spot.toFixed(3)}</div>
          <div class="${chgCls}">${chgSign}${etf.chg.toFixed(2)}%</div>
        </div>
      </div>
      <canvas class="candle-chart" width="340" height="160"></canvas>
      <button class="btn btn-primary" style="margin-top:12px;width:100%" data-code="${code}">进入分析 →</button>
    `;
    grid.appendChild(card);
    const canvas = card.querySelector("canvas");
    drawCandles(canvas, seedOhlc(etf.spot));
    card.querySelector("button").addEventListener("click", () => {
      currentUnderlying = code;
      document.getElementById("underlying-select").value = code;
      showPage("heatmap");
    });
  });
}

function getCellState(key) {
  const item = tradeList.find((t) => t.key === key);
  return item ? item.direction : null;
}

function toggleCell(key, meta) {
  const idx = tradeList.findIndex((t) => t.key === key);
  if (idx === -1) {
    tradeList.push({ ...meta, key, direction: "long", quoteType: "mid", qty: 1 });
  } else if (tradeList[idx].direction === "long") {
    tradeList[idx].direction = "short";
  } else {
    tradeList.splice(idx, 1);
  }
  renderTradeTables();
  renderHeatmap();
  renderTQuote();
}

function renderMonthTabs() {
  const tabsEl = document.getElementById("month-tabs");
  const chipEl = document.getElementById("month-chip");
  const months = getSSEOptionMonths();

  if (chipEl) {
    chipEl.textContent = `挂牌: ${months.map((m) => m.shortLabel).join(" / ")}`;
  }

  if (!tabsEl) return;
  tabsEl.innerHTML = months.map((m, i) =>
    `<button class="month-tab ${i === currentTQuoteMonthIdx ? "active" : ""}" data-idx="${i}" title="${m.label}">${m.shortLabel}</button>`
  ).join("");

  tabsEl.querySelectorAll(".month-tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      currentTQuoteMonthIdx = +btn.dataset.idx;
      renderMonthTabs();
      renderTQuote();
    });
  });
}

function refreshHomeData() {
  renderHome();
}

function refreshQuoteData() {
  lastQuoteRefresh = new Date();
  renderHeatmap();
  renderMonthTabs();
  renderTQuote();
}

function restartHomeRefreshTimer() {
  if (homeRefreshTimer) clearInterval(homeRefreshTimer);
  const sec = Math.max(5, settings.homeRefreshSec || DEFAULT_SETTINGS.homeRefreshSec);
  homeRefreshTimer = setInterval(() => {
    if (document.getElementById("page-home")?.classList.contains("active")) {
      refreshHomeData();
    }
  }, sec * 1000);
}

function renderHeatmap() {
  const spot = ETFS[currentUnderlying].spot;
  const { puts, calls, step } = buildStrikes(spot);
  const months = getSSEOptionMonths();

  document.getElementById("heatmap-subtitle").textContent =
    `${currentUnderlying} · 现价 ${spot.toFixed(3)} · 行权价±20% · 间距 ${step}${quoteRefreshLabel()} · IV色阶: 10年20日HV 20%(18.2%)→80%(32.5%)`;

  const monthChip = document.getElementById("month-chip");
  if (monthChip) {
    const months = getSSEOptionMonths();
    monthChip.textContent = `挂牌: ${months.map((m) => m.shortLabel).join(" / ")}`;
  }

  renderMonthTabs();

  const thead = document.getElementById("heatmap-head");
  const tbody = document.getElementById("heatmap-body");
  thead.innerHTML = "";
  tbody.innerHTML = "";

  const headRow = document.createElement("tr");
  const monthHead = document.createElement("th");
  monthHead.className = "col-month";
  headRow.appendChild(monthHead);

  puts.forEach((strike) => {
    const th = document.createElement("th");
    th.className = "col-strike strike-put";
    th.textContent = `${strike.toFixed(2)}沽`;
    headRow.appendChild(th);
  });

  const spotHead = document.createElement("th");
  spotHead.className = "col-spot spot-col";
  spotHead.innerHTML = '<span class="spot-head">现价</span>';
  headRow.appendChild(spotHead);

  calls.forEach((strike) => {
    const th = document.createElement("th");
    th.className = "col-strike strike-call";
    th.textContent = `${strike.toFixed(2)}购`;
    headRow.appendChild(th);
  });
  thead.appendChild(headRow);

  const midRow = Math.floor(months.length / 2);

  months.forEach((month, mi) => {
    const tr = document.createElement("tr");

    const monthTh = document.createElement("th");
    monthTh.className = "col-month";
    monthTh.textContent = month.shortLabel;
    monthTh.title = month.label;
    tr.appendChild(monthTh);

    puts.forEach((strike) => {
      tr.appendChild(buildHeatCell(strike, month, mi, spot, false));
    });

    const spotTd = document.createElement("td");
    spotTd.className = "col-spot spot-col";
    spotTd.innerHTML = `<div class="spot-line"></div>${mi === midRow ? `<div class="spot-label">${spot.toFixed(3)}</div>` : ""}`;
    tr.appendChild(spotTd);

    calls.forEach((strike) => {
      tr.appendChild(buildHeatCell(strike, month, mi, spot, true));
    });

    tbody.appendChild(tr);
  });
}

function buildHeatCell(strike, month, monthIdx, spot, isCall) {
  const td = document.createElement("td");
  td.className = "col-strike";
  const key = contractKey(strike, month.shortLabel, isCall);
  const state = getCellState(key);
  const iv = midIv(strike, monthIdx, isCall, spot);
  const delta = midDelta(strike, spot, isCall);

  const cell = document.createElement("div");
  cell.className = `heat-cell ${state || ""}`;
  cell.style.background = heatColor(iv);
  cell.innerHTML = `<div><strong>IV (${iv.toFixed(1)}%)</strong></div><div>Δ ${delta.toFixed(3)}</div>`;
  cell.addEventListener("click", () =>
    toggleCell(key, {
      code: `${currentUnderlying}${isCall ? "购" : "沽"}${month.shortLabel}${String(strike).replace(".", "")}`,
      strike,
      month: month.shortLabel,
      isCall,
      iv,
      delta,
      gamma: isCall ? 0.04 : 0.06,
      theta: isCall ? -6.1 : -8.2,
      vega: isCall ? 1.2 : 1.4,
    })
  );
  td.appendChild(cell);
  return td;
}

function orderPrice(item) {
  const bid = 0.08, ask = 0.085;
  if (item.quoteType === "opponent") return item.direction === "long" ? ask : bid;
  if (item.quoteType === "limit") return item.direction === "long" ? bid : ask;
  return (bid + ask) / 2;
}

function renderTradeTables() {
  const bodies = [
    document.getElementById("trade-body-drawer"),
    document.getElementById("trade-body-drawer-tquote"),
    document.getElementById("trade-body-page"),
  ];
  let sumD = 0, sumG = 0, sumT = 0, sumV = 0, sumPrem = 0;

  const rows = tradeList.map((item, i) => {
    const price = orderPrice(item);
    const sign = item.direction === "long" ? 1 : -1;
    const dContrib = item.delta * sign * item.qty;
    sumD += dContrib;
    sumG += item.gamma * sign * item.qty;
    sumT += item.theta * sign * item.qty;
    sumV += item.vega * sign * item.qty;
    sumPrem += price * item.qty * 10000 * (item.direction === "long" ? -1 : 1);

    const dirLabel = item.direction === "long" ? "做多" : "做空";
    const dirCls = item.direction === "long" ? "up" : "down";
    return `<tr data-idx="${i}">
      <td>${item.code}</td>
      <td class="${dirCls}"><strong>${dirLabel}</strong></td>
      <td><select data-field="quoteType">
        <option value="mid" ${item.quoteType==="mid"?"selected":""}>中间价</option>
        <option value="opponent" ${item.quoteType==="opponent"?"selected":""}>对手价</option>
        <option value="limit" ${item.quoteType==="limit"?"selected":""}>挂单价</option>
      </select></td>
      <td><input type="number" min="1" value="${item.qty}" data-field="qty" style="width:60px"></td>
      <td>${price.toFixed(4)}</td>
      <td>${item.iv.toFixed(1)}%</td>
      <td>${item.delta.toFixed(3)}</td>
      <td>${item.gamma.toFixed(2)}</td>
      <td>${item.theta.toFixed(1)}</td>
      <td>${item.vega.toFixed(1)}</td>
      <td>¥${(price * item.qty * 10000).toLocaleString()}</td>
      <td><button class="btn" data-remove="${i}">删除</button></td>
    </tr>`;
  }).join("");

  const emptyRow = `<tr><td colspan="12" class="muted">点击热力图或 T 型报价格子添加合约（做多→做空→移除）</td></tr>`;

  bodies.forEach((body) => {
    if (!body) return;
    body.innerHTML = rows || emptyRow;
    body.querySelectorAll("select, input").forEach((el) => {
      el.addEventListener("change", (e) => {
        const tr = e.target.closest("tr");
        const idx = +tr.dataset.idx;
        const field = e.target.dataset.field;
        tradeList[idx][field] = field === "qty" ? +e.target.value : e.target.value;
        renderTradeTables();
      });
    });
    body.querySelectorAll("[data-remove]").forEach((btn) => {
      btn.addEventListener("click", () => {
        tradeList.splice(+btn.dataset.remove, 1);
        renderTradeTables();
        renderHeatmap();
        renderTQuote();
      });
    });
  });

  const summary = `交易列表 (${tradeList.length}) · ΣΔ ${sumD.toFixed(2)} · ΣΓ ${sumG.toFixed(2)} · ΣΘ ${sumT.toFixed(1)} · ΣV ${sumV.toFixed(1)} · 预估权利金 ¥${Math.abs(sumPrem).toLocaleString()}`;
  const summaryEls = [
    document.getElementById("trade-summary-drawer"),
    document.getElementById("trade-summary-drawer-tquote"),
    document.getElementById("trade-summary-page"),
  ];
  summaryEls.forEach((el) => { if (el) el.textContent = summary; });
}

function buildTQuoteMeta(strike, month, monthIdx, spot, isCall) {
  const iv = midIv(strike, monthIdx, isCall, spot);
  const delta = midDelta(strike, spot, isCall);
  const key = contractKey(strike, month.shortLabel, isCall);
  return {
    key,
    code: `${currentUnderlying}${isCall ? "购" : "沽"}${month.shortLabel}${String(strike).replace(".", "")}`,
    strike,
    month: month.shortLabel,
    isCall,
    iv,
    delta,
    gamma: isCall ? 0.04 : 0.06,
    theta: isCall ? -6.1 : -8.2,
    vega: isCall ? 1.2 : 1.4,
  };
}

function renderTQuote() {
  const spot = ETFS[currentUnderlying].spot;
  const { puts, calls } = buildStrikes(spot);
  const strikes = [...puts, ...calls].sort((a, b) => a - b);
  const months = getSSEOptionMonths();
  const month = months[currentTQuoteMonthIdx] || months[0];
  const monthIdx = currentTQuoteMonthIdx;
  const body = document.getElementById("tquote-body");
  const intro = document.querySelector("#page-tquote .split-intro");
  if (intro) {
    intro.textContent = `T 型报价 — ${month.label} · 点击购/沽侧三态点选${quoteRefreshLabel()}`;
  }

  body.innerHTML = strikes.map((k) => {
    const callMeta = buildTQuoteMeta(k, month, monthIdx, spot, true);
    const putMeta = buildTQuoteMeta(k, month, monthIdx, spot, false);
    const callState = getCellState(callMeta.key);
    const putState = getCellState(putMeta.key);
    const callCls = `tquote-clickable${callState ? ` tquote-${callState}` : ""}`;
    const putCls = `tquote-clickable${putState ? ` tquote-${putState}` : ""}`;
    const civ = callMeta.iv.toFixed(1);
    const piv = putMeta.iv.toFixed(1);
    const cd = callMeta.delta.toFixed(3);
    const pd = putMeta.delta.toFixed(3);
    return `<tr data-strike="${k}">
      <td class="${callCls}" data-side="call">${(0.078).toFixed(3)}</td>
      <td class="${callCls}" data-side="call">${(0.081).toFixed(3)}</td>
      <td class="${callCls}" data-side="call">${civ}</td>
      <td class="${callCls}" data-side="call">${cd}</td>
      <td class="${callCls}" data-side="call">0.06</td>
      <td class="${callCls}" data-side="call">-8.1</td>
      <td class="${callCls}" data-side="call">1.3</td>
      <td><strong>${k.toFixed(2)}</strong></td>
      <td class="${putCls}" data-side="put">${(0.079).toFixed(3)}</td>
      <td class="${putCls}" data-side="put">${(0.082).toFixed(3)}</td>
      <td class="${putCls}" data-side="put">${piv}</td>
      <td class="${putCls}" data-side="put">${pd}</td>
      <td class="${putCls}" data-side="put">0.06</td>
      <td class="${putCls}" data-side="put">-7.8</td>
      <td class="${putCls}" data-side="put">1.4</td>
    </tr>`;
  }).join("");

  body.querySelectorAll("td[data-side]").forEach((td) => {
    td.addEventListener("click", () => {
      const tr = td.closest("tr");
      const strike = +tr.dataset.strike;
      const isCall = td.dataset.side === "call";
      const meta = buildTQuoteMeta(strike, month, monthIdx, spot, isCall);
      toggleCell(meta.key, meta);
    });
  });
}

function copyOrderInfo() {
  if (!tradeList.length) {
    alert("交易列表为空，请先点选合约");
    return;
  }
  const lines = tradeList.map((t) => {
    const action = t.direction === "long" ? "买入" : "卖出";
    const price = orderPrice(t).toFixed(4);
    return `${action} ${t.code} 数量${t.qty}张 委托价${price}`;
  });
  const text = lines.join("\n");
  if (navigator.clipboard?.writeText) {
    navigator.clipboard.writeText(text).then(() => alert("已复制下单信息到剪贴板"));
  } else {
    prompt("复制以下内容：", text);
  }
}

function exportTradeCsv() {
  if (!tradeList.length) {
    alert("交易列表为空");
    return;
  }
  const header = "合约,方向,报价方式,数量,委托价,IV,Delta,Gamma,Theta,Vega,权利金";
  const rows = tradeList.map((t) => {
    const price = orderPrice(t);
    const dir = t.direction === "long" ? "做多" : "做空";
    const prem = price * t.qty * 10000;
    return [t.code, dir, t.quoteType, t.qty, price.toFixed(4), t.iv, t.delta, t.gamma, t.theta, t.vega, prem].join(",");
  });
  const blob = new Blob([header + "\n" + rows.join("\n")], { type: "text/csv;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `trade-list-${currentUnderlying}.csv`;
  a.click();
}

function initSettingsForm() {
  const rEl = document.getElementById("setting-r");
  const qEl = document.getElementById("setting-q");
  const quoteEl = document.getElementById("setting-quote-refresh");
  const homeEl = document.getElementById("setting-home-refresh");
  if (!rEl) return;

  rEl.value = settings.r;
  qEl.value = settings.q;
  quoteEl.value = settings.quoteRefreshSec;
  homeEl.value = settings.homeRefreshSec;

  const onChange = () => {
    settings.r = +rEl.value;
    settings.q = +qEl.value;
    settings.quoteRefreshSec = +quoteEl.value;
    settings.homeRefreshSec = +homeEl.value;
    saveSettings();
  };

  [rEl, qEl, quoteEl, homeEl].forEach((el) => {
    el.addEventListener("change", onChange);
    el.addEventListener("input", onChange);
  });
}

function showPage(id) {
  document.querySelectorAll(".page").forEach((p) => p.classList.remove("active"));
  document.getElementById(`page-${id}`).classList.add("active");
  document.querySelectorAll(".nav-item").forEach((n) => n.classList.toggle("active", n.dataset.page === id));
  const title = { home: "首页", heatmap: "IV 热力图", tquote: "T 型报价", tradelist: "交易列表", settings: "设置" };
  document.getElementById("page-title").textContent = title[id] || "";
  const showToolbar = id !== "home" && id !== "settings";
  document.getElementById("analysis-toolbar").style.display = showToolbar ? "flex" : "none";
  document.getElementById("month-chip").style.display = id === "tquote" ? "none" : (showToolbar ? "inline" : "none");
  document.getElementById("month-tabs").style.display = id === "tquote" ? "flex" : "none";

  if (id === "home") refreshHomeData();
  if (id === "heatmap") refreshQuoteData();
  if (id === "tquote") {
    renderMonthTabs();
    refreshQuoteData();
  }
  if (id === "tradelist") renderTradeTables();
}

document.querySelectorAll(".nav-item").forEach((btn) => {
  btn.addEventListener("click", () => showPage(btn.dataset.page));
});

document.getElementById("underlying-select").addEventListener("change", (e) => {
  currentUnderlying = e.target.value;
  refreshQuoteData();
});

document.getElementById("btn-refresh").addEventListener("click", () => {
  const active = document.querySelector(".page.active")?.id;
  if (active === "page-home") refreshHomeData();
  else if (active === "page-heatmap" || active === "page-tquote") refreshQuoteData();
});

["btn-copy-heatmap", "btn-copy-tquote", "btn-copy-page"].forEach((id) => {
  document.getElementById(id)?.addEventListener("click", copyOrderInfo);
});
["btn-export-heatmap", "btn-export-tquote", "btn-export-page"].forEach((id) => {
  document.getElementById(id)?.addEventListener("click", exportTradeCsv);
});
["btn-goto-tradelist-heatmap", "btn-goto-tradelist-tquote"].forEach((id) => {
  document.getElementById(id)?.addEventListener("click", () => showPage("tradelist"));
});

// init
initSettingsForm();
renderHome();
renderTradeTables();
restartHomeRefreshTimer();
showPage("home");
