const refs = {
  refreshBtn: document.getElementById("refreshBtn"),
  epochFilter: document.getElementById("epochFilter"),
  logSummary: document.getElementById("logSummary"),
  logList: document.getElementById("logList"),
  roundSummary: document.getElementById("roundSummary"),
  roundLogs: document.getElementById("roundLogs"),
  roundEpochCount: document.getElementById("roundEpochCount"),
  trainAgainBtn: document.getElementById("trainAgainBtn"),
};

const state = {
  entries: [],
  agent: null,
};

function safeJson(value) {
  return JSON.stringify(value ?? {}, null, 2);
}

function formatFloat(value, digits = 3) {
  const n = Number(value || 0);
  return Number.isNaN(n) ? "0.000" : n.toFixed(digits);
}

function renderSummary() {
  const entries = state.entries;
  const uniqueEpochs = new Set(entries.map((entry) => entry.epoch_run).filter((value) => value !== undefined && value !== null));
  const avgReward = entries.length === 0
    ? 0
    : entries.reduce((sum, entry) => sum + Number(entry.reward?.value || 0), 0) / entries.length;
  const cards = [
    ["Log Entries", String(entries.length)],
    ["Epochs Seen", String(uniqueEpochs.size || 0)],
    ["Average Reward", formatFloat(avgReward)],
    ["Policy Updates", String(state.agent?.updates ?? 0)],
    ["Recommended Model", String(state.agent?.recommended_model || "N/A")],
    ["Using Recommended", state.agent?.is_using_recommended_model ? "Yes" : "No"],
  ];

  refs.logSummary.innerHTML = "";
  cards.forEach(([label, value]) => {
    const card = document.createElement("div");
    card.className = "support-stat";
    const k = document.createElement("div");
    k.className = "k";
    k.textContent = label;
    const v = document.createElement("div");
    v.className = "v";
    v.textContent = value;
    card.appendChild(k);
    card.appendChild(v);
    refs.logSummary.appendChild(card);
  });
}

function makeField(label, value) {
  const wrap = document.createElement("div");
  wrap.className = "log-field";
  const k = document.createElement("div");
  k.className = "k";
  k.textContent = label;
  const v = document.createElement("div");
  v.className = "v";
  v.textContent = value;
  wrap.appendChild(k);
  wrap.appendChild(v);
  return wrap;
}

function makeBlock(label, text) {
  const wrap = document.createElement("div");
  wrap.className = "log-field log-block";
  const k = document.createElement("div");
  k.className = "k";
  k.textContent = label;
  const pre = document.createElement("pre");
  pre.className = "log-json";
  pre.textContent = text;
  wrap.appendChild(k);
  wrap.appendChild(pre);
  return wrap;
}

function renderLogs() {
  const filterValue = refs.epochFilter.value.trim();
  const epochFilter = filterValue === "" ? null : Number(filterValue);
  const entries = state.entries.filter((entry) => {
    if (epochFilter === null || Number.isNaN(epochFilter)) {
      return true;
    }
    return Number(entry.epoch_run || 0) === epochFilter;
  });

  refs.logList.innerHTML = "";

  if (entries.length === 0) {
    refs.logList.innerHTML = '<div class="search-empty">No learning records match the selected epoch.</div>';
    return;
  }

  entries.slice().reverse().forEach((entry, index) => {
    const card = document.createElement("article");
    card.className = "log-card";

    const head = document.createElement("div");
    head.className = "log-card-head";
    const title = document.createElement("h3");
    title.textContent = `Epoch ${entry.epoch_run ?? "N/A"} • Load ${entries.length - index}`;
    const meta = document.createElement("span");
    meta.className = "log-meta";
    meta.textContent = `${entry.timestamp || "unknown time"}`;
    head.appendChild(title);
    head.appendChild(meta);

    const grid = document.createElement("div");
    grid.className = "log-grid";
    grid.appendChild(makeField("Source", entry.source || "policy"));
    grid.appendChild(makeField("Confidence", formatFloat(entry.confidence, 2)));
    grid.appendChild(makeField("Step", String(entry.step_number ?? "N/A")));
    grid.appendChild(makeField("Recommended Model", entry.recommended_model || state.agent?.recommended_model || "N/A"));
    grid.appendChild(makeField("Model In Use", entry.model_in_use || state.agent?.model_in_use || "N/A"));
    grid.appendChild(makeField("Using Recommended", entry.is_using_recommended_model ? "Yes" : "No"));
    grid.appendChild(makeField("Examples Seen", String(entry.examples_seen ?? 0)));
    grid.appendChild(makeField("Updates", String(entry.updates ?? 0)));
    grid.appendChild(makeField("Action", entry.action?.action_type || "N/A"));
    grid.appendChild(makeField("Category", entry.action?.category || "N/A"));
    grid.appendChild(makeField("Priority", entry.action?.priority || "N/A"));
    grid.appendChild(makeField("Order ID", entry.action?.order_id || "N/A"));
    grid.appendChild(makeField("Reward", formatFloat(entry.reward?.value || 0)));
    grid.appendChild(makeField("Feedback", entry.reward?.feedback || "N/A"));

    card.appendChild(head);
    card.appendChild(grid);
    card.appendChild(makeBlock("Email", safeJson(entry.email || {})));
    card.appendChild(makeBlock("Context", safeJson(entry.context || {})));
    refs.logList.appendChild(card);
  });
}

function renderRoundSummary(payload) {
  const summary = payload?.summary || {};
  const cards = [
    ["Epoch Logs", String(summary.epochs ?? 0)],
    ["Latest Epoch", String(summary.latest_epoch ?? "-")],
    ["Best Avg Score", formatFloat(summary.best_average_score || 0)],
  ];

  refs.roundSummary.innerHTML = "";
  cards.forEach(([label, value]) => {
    const card = document.createElement("div");
    card.className = "support-stat";
    const k = document.createElement("div");
    k.className = "k";
    k.textContent = label;
    const v = document.createElement("div");
    v.className = "v";
    v.textContent = value;
    card.appendChild(k);
    card.appendChild(v);
    refs.roundSummary.appendChild(card);
  });
}

function renderRoundLogs(entries) {
  refs.roundLogs.innerHTML = "";
  if (!Array.isArray(entries) || entries.length === 0) {
    refs.roundLogs.innerHTML = '<div class="search-empty">No round epoch logs yet.</div>';
    return;
  }

  entries.slice().reverse().slice(0, 20).forEach((entry) => {
    const t1 = formatFloat(entry?.tasks?.task_1?.score || 0);
    const t2 = formatFloat(entry?.tasks?.task_2?.score || 0);
    const t3 = formatFloat(entry?.tasks?.task_3?.score || 0);
    const avg = formatFloat(entry?.average_score || 0);

    const card = document.createElement("article");
    card.className = "epoch-log-item";
    card.innerHTML = [
      `<div class="head">Epoch ${entry.epoch} • Avg ${avg}</div>`,
      `<div class="desc">task_1=${t1} | task_2=${t2} | task_3=${t3}</div>`,
      `<div class="desc">use_api=${Boolean(entry.use_api)} • ${entry.timestamp || "unknown time"}</div>`,
    ].join("");
    refs.roundLogs.appendChild(card);
  });
}

async function loadRoundLogs() {
  const resp = await fetch("/training/logs?limit=200");
  if (!resp.ok) {
    throw new Error(`Round logs HTTP ${resp.status}`);
  }
  const payload = await resp.json();
  renderRoundSummary(payload);
  renderRoundLogs(payload.entries || []);
}

async function trainAgain() {
  const epochs = Math.max(1, Math.min(200, Number.parseInt(refs.roundEpochCount.value || "1", 10) || 1));
  refs.roundEpochCount.value = String(epochs);

  const resp = await fetch("/training/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ epochs, use_api: false }),
  });
  if (!resp.ok) {
    throw new Error(`Training HTTP ${resp.status}`);
  }
  const payload = await resp.json();
  renderRoundSummary({
    summary: {
      epochs: Array.isArray(payload?.entries) ? payload.entries.length : 0,
      latest_epoch: payload?.latest?.epoch ?? "-",
      best_average_score: Array.isArray(payload?.entries)
        ? payload.entries.reduce((max, item) => Math.max(max, Number(item?.average_score || 0)), 0)
        : 0,
    },
  });
  renderRoundLogs(Array.isArray(payload?.entries) ? payload.entries : []);
  await loadLogs();
  await loadRoundLogs();
}

async function loadLogs() {
  const [agentResp, logsResp] = await Promise.all([
    fetch("/agent/task_1"),
    fetch("/agent/task_1/logs?limit=200"),
  ]);

  if (!agentResp.ok) {
    throw new Error(`Agent status HTTP ${agentResp.status}`);
  }
  if (!logsResp.ok) {
    throw new Error(`Logs HTTP ${logsResp.status}`);
  }

  state.agent = await agentResp.json();
  const payload = await logsResp.json();
  state.entries = Array.isArray(payload.entries) ? payload.entries : [];
  renderSummary();
  renderLogs();
}

refs.refreshBtn.addEventListener("click", async () => {
  try {
    await loadLogs();
  } catch (err) {
    refs.logList.innerHTML = `<div class="search-empty">Failed to load logs: ${err.message}</div>`;
  }
});

refs.trainAgainBtn.addEventListener("click", async () => {
  try {
    refs.trainAgainBtn.disabled = true;
    refs.trainAgainBtn.textContent = "Training...";
    await trainAgain();
  } catch (err) {
    refs.roundLogs.innerHTML = `<div class="search-empty">Training failed: ${err.message}</div>`;
  } finally {
    refs.trainAgainBtn.disabled = false;
    refs.trainAgainBtn.textContent = "Train Again";
  }
});

refs.epochFilter.addEventListener("input", renderLogs);

(async function init() {
  try {
    await loadLogs();
    await loadRoundLogs();
  } catch (err) {
    refs.logSummary.innerHTML = '<div class="search-empty">Log summary unavailable.</div>';
    refs.logList.innerHTML = `<div class="search-empty">Failed to load logs: ${err.message}</div>`;
    refs.roundSummary.innerHTML = '<div class="search-empty">Round summary unavailable.</div>';
    refs.roundLogs.innerHTML = `<div class="search-empty">Failed to load round logs: ${err.message}</div>`;
  }
})();