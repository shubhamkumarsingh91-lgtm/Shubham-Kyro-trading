const STATUS_MAP = {
  "Buy": { cls: "good", icon: "▲" },
  "Overweight": { cls: "good", icon: "▲" },
  "Hold": { cls: "warning", icon: "●" },
  "Underweight": { cls: "serious", icon: "▼" },
  "Sell": { cls: "critical", icon: "▼" },
};

function statusFor(decision) {
  return STATUS_MAP[decision] || { cls: "muted", icon: "–" };
}

function fmtPrice(n) {
  return n == null ? "—" : `$${n.toFixed(2)}`;
}

function fmtPct(n) {
  return n == null ? "—" : `${n > 0 ? "+" : ""}${n.toFixed(2)}%`;
}

async function fetchJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url} -> ${res.status}`);
  return res.json();
}

const state = {
  watchlist: [],
  latestDecisions: {},
  history: {},
  activeTicker: null,
};

async function init() {
  const grid = document.getElementById("grid");
  const emptyNote = document.getElementById("empty-note");
  try {
    const [{ watchlist }, { latest }] = await Promise.all([
      fetchJSON("/api/watchlist"),
      fetchJSON("/api/decisions"),
    ]);
    state.watchlist = watchlist;
    state.latestDecisions = latest;

    if (Object.keys(latest).length === 0) {
      emptyNote.style.display = "block";
    }

    grid.innerHTML = "";
    for (const ticker of watchlist) {
      grid.appendChild(await renderCard(ticker));
    }

    if (watchlist.length > 0) {
      selectTicker(watchlist[0]);
    }
  } catch (err) {
    grid.innerHTML = `<div class="error">Failed to load dashboard data: ${err.message}</div>`;
  }
}

async function renderCard(ticker) {
  const card = document.createElement("button");
  card.className = "card";
  card.id = `card-${ticker}`;
  card.setAttribute("aria-pressed", "false");

  const decision = state.latestDecisions[ticker];
  const st = statusFor(decision?.decision);
  const kf = decision?.kronos_forecast;
  const kronosOk = kf && !kf.error;

  let lastPrice = null;
  try {
    const ph = await fetchJSON(`/api/price-history/${ticker}?period=5d`);
    lastPrice = ph.close[ph.close.length - 1];
  } catch (_) { /* leave null, chart section will surface errors */ }

  card.innerHTML = `
    <div class="ticker">${ticker}</div>
    <div class="price">${fmtPrice(lastPrice)}</div>
    <div class="row">
      <span class="badge ${st.cls}">${st.icon} ${decision ? decision.decision : "No proposal yet"}</span>
    </div>
    <div class="row">
      ${kronosOk
        ? `<span>Kronos:</span> <span class="kronos-delta ${kf.direction}">${kf.direction === "up" ? "▲" : kf.direction === "down" ? "▼" : "–"} ${fmtPct(kf.pct_change)}</span>`
        : `<span class="kronos-delta flat">Kronos: —</span>`}
    </div>
  `;
  card.addEventListener("click", () => selectTicker(ticker));
  return card;
}

async function selectTicker(ticker) {
  state.activeTicker = ticker;
  document.querySelectorAll(".card").forEach((c) => {
    const active = c.id === `card-${ticker}`;
    c.classList.toggle("active", active);
    c.setAttribute("aria-pressed", String(active));
  });

  const detail = document.getElementById("detail");
  detail.style.display = "block";
  document.getElementById("detail-ticker").textContent = ticker;

  const decision = state.latestDecisions[ticker];
  const sub = document.getElementById("detail-sub");
  sub.textContent = decision
    ? `Last proposal: ${decision.decision} on ${decision.trade_date} (logged ${new Date(decision.logged_at).toLocaleString()})`
    : "No proposal logged yet for this ticker.";

  renderReports(decision);

  try {
    const [priceHistory, decisionsHistory] = await Promise.all([
      fetchJSON(`/api/price-history/${ticker}?period=6mo`),
      fetchJSON(`/api/decisions/${ticker}`).catch(() => ({ history: [] })),
    ]);
    state.history[ticker] = priceHistory;
    drawChart(priceHistory, decisionsHistory.history || []);
  } catch (err) {
    document.getElementById("chart-error").textContent = `Could not load price history: ${err.message}`;
  }
}

function renderReports(decision) {
  const container = document.getElementById("reports");
  if (!decision) {
    container.innerHTML = `<div class="report-card wide"><div class="body">Run <code>python run_watchlist.py</code> (or <code>propose.py TICKER</code>) in trading-agents/ to generate a proposal for this ticker.</div></div>`;
    return;
  }
  const sections = [
    ["Market analyst (incl. Kronos)", decision.market_report],
    ["Sentiment analyst", decision.sentiment_report],
    ["News analyst", decision.news_report],
    ["Fundamentals analyst", decision.fundamentals_report],
    ["Final trader reasoning", decision.final_trade_decision],
    ["Risk management judge", decision.risk_judge_decision],
  ];
  container.innerHTML = sections
    .map(
      ([title, body]) => `
      <div class="report-card${title.startsWith("Final") || title.startsWith("Risk") ? " wide" : ""}">
        <h3>${title}</h3>
        <div class="body"></div>
      </div>`
    )
    .join("");
  // textContent, not innerHTML, for untrusted LLM-generated report bodies
  container.querySelectorAll(".report-card").forEach((el, i) => {
    el.querySelector(".body").textContent = sections[i][1] || "—";
  });
}

function drawChart(priceHistory, decisions) {
  document.getElementById("chart-error").textContent = "";
  const canvas = document.getElementById("chart");
  const tooltip = document.getElementById("tooltip");
  const dpr = window.devicePixelRatio || 1;
  const cssWidth = canvas.parentElement.clientWidth;
  const cssHeight = 280;
  canvas.width = cssWidth * dpr;
  canvas.height = cssHeight * dpr;
  canvas.style.height = `${cssHeight}px`;
  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, cssWidth, cssHeight);

  const css = getComputedStyle(document.documentElement);
  const col = (name) => css.getPropertyValue(name).trim();

  const dates = priceHistory.dates;
  const closes = priceHistory.close;
  const padL = 46, padR = 12, padT = 16, padB = 24;
  const w = cssWidth - padL - padR;
  const h = cssHeight - padT - padB;

  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const yPad = (max - min) * 0.08 || 1;
  const yMin = min - yPad, yMax = max + yPad;

  const x = (i) => padL + (i / (dates.length - 1)) * w;
  const y = (v) => padT + h - ((v - yMin) / (yMax - yMin)) * h;

  // gridlines
  ctx.strokeStyle = col("--gridline");
  ctx.lineWidth = 1;
  const ticks = 4;
  ctx.fillStyle = col("--text-muted");
  ctx.font = "11px system-ui, sans-serif";
  ctx.textBaseline = "middle";
  for (let t = 0; t <= ticks; t++) {
    const v = yMin + (t / ticks) * (yMax - yMin);
    const yy = y(v);
    ctx.beginPath();
    ctx.moveTo(padL, yy);
    ctx.lineTo(padL + w, yy);
    ctx.stroke();
    ctx.fillText(`$${v.toFixed(0)}`, 4, yy);
  }

  // price line
  ctx.strokeStyle = col("--series-price");
  ctx.lineWidth = 2;
  ctx.lineJoin = "round";
  ctx.lineCap = "round";
  ctx.beginPath();
  closes.forEach((c, i) => {
    const px = x(i), py = y(c);
    if (i === 0) ctx.moveTo(px, py);
    else ctx.lineTo(px, py);
  });
  ctx.stroke();

  // decision markers
  const dateIndex = new Map(dates.map((d, i) => [d, i]));
  const markers = decisions
    .map((d) => ({ ...d, idx: dateIndex.get(d.trade_date) }))
    .filter((d) => d.idx !== undefined);

  markers.forEach((d) => {
    const st = statusFor(d.decision);
    const px = x(d.idx), py = y(closes[d.idx]);
    ctx.beginPath();
    ctx.arc(px, py, 6, 0, Math.PI * 2);
    ctx.fillStyle = col(`--${st.cls}`);
    ctx.strokeStyle = col("--surface-1");
    ctx.lineWidth = 2;
    ctx.fill();
    ctx.stroke();
  });

  // crosshair + tooltip
  canvas.onmousemove = (evt) => {
    const rect = canvas.getBoundingClientRect();
    const mx = evt.clientX - rect.left;
    const relX = Math.min(Math.max((mx - padL) / w, 0), 1);
    const idx = Math.round(relX * (dates.length - 1));

    drawChart(priceHistory, decisions); // redraw base
    const px = x(idx), py = y(closes[idx]);
    ctx.strokeStyle = col("--baseline");
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(px, padT);
    ctx.lineTo(px, padT + h);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(px, py, 4, 0, Math.PI * 2);
    ctx.fillStyle = col("--series-price");
    ctx.fill();

    const marker = markers.find((d) => d.idx === idx);
    tooltip.style.opacity = "1";
    tooltip.style.left = `${Math.min(px + padL + 8, cssWidth - 170)}px`;
    tooltip.style.top = `${py - 12}px`;
    tooltip.innerHTML = "";
    const dateEl = document.createElement("div");
    dateEl.textContent = dates[idx];
    const priceEl = document.createElement("div");
    priceEl.innerHTML = `Close: <strong></strong>`;
    priceEl.querySelector("strong").textContent = fmtPrice(closes[idx]);
    tooltip.appendChild(dateEl);
    tooltip.appendChild(priceEl);
    if (marker) {
      const decEl = document.createElement("div");
      const st = statusFor(marker.decision);
      decEl.textContent = `Proposal: ${marker.decision}`;
      decEl.style.color = col(`--${st.cls}`);
      tooltip.appendChild(decEl);
    }
  };
  canvas.onmouseleave = () => {
    tooltip.style.opacity = "0";
  };
}

window.addEventListener("resize", () => {
  const t = state.activeTicker;
  if (t && state.history[t]) {
    const decision = state.latestDecisions[t];
    fetchJSON(`/api/decisions/${t}`)
      .then((d) => drawChart(state.history[t], d.history || []))
      .catch(() => drawChart(state.history[t], []));
  }
});

init();
