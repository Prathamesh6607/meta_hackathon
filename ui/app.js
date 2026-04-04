const state = {
  taskId: "task_1",
  observation: null,
  done: false,
  totalReward: 0,
  lastReward: 0,
  steps: 0,
  timeline: [],
  lastPayload: null,
  lastAction: null,
};

const categoryOptions = [
  "Refund Request",
  "Shipping Delay",
  "Account Access",
  "Product Defect",
  "Billing Issue",
  "General Inquiry",
];

const priorityOptions = ["Low", "Normal", "Urgent"];

const refs = {
  taskSelect: document.getElementById("taskSelect"),
  actionType: document.getElementById("actionType"),
  actionFields: document.getElementById("actionFields"),
  resetBtn: document.getElementById("resetBtn"),
  autoBtn: document.getElementById("autoBtn"),
  runEpisodeBtn: document.getElementById("runEpisodeBtn"),
  apiKeyInput: document.getElementById("apiKeyInput"),
  modelInput: document.getElementById("modelInput"),
  useApiCheckbox: document.getElementById("useApiCheckbox"),
  supportSearchInput: document.getElementById("supportSearchInput"),
  supportSearchTopK: document.getElementById("supportSearchTopK"),
  supportSearchBtn: document.getElementById("supportSearchBtn"),
  supportSearchClearBtn: document.getElementById("supportSearchClearBtn"),
  supportSearchResults: document.getElementById("supportSearchResults"),
  supportStats: document.getElementById("supportStats"),
  submitActionBtn: document.getElementById("submitActionBtn"),
  statusText: document.getElementById("statusText"),
  observationView: document.getElementById("observationView"),
  outcomeView: document.getElementById("outcomeView"),
  metrics: document.getElementById("metrics"),
  timeline: document.getElementById("timeline"),
};

function setStatus(text) {
  refs.statusText.textContent = text;
}

function safeJson(value) {
  return JSON.stringify(value ?? {}, null, 2);
}

function asInt(value, fallback = 0) {
  const n = Number.parseInt(value, 10);
  return Number.isNaN(n) ? fallback : n;
}

function extractOrderId(text) {
  const raw = String(text || "");
  const direct = raw.match(/\bORD[-_ ]?\d+\b/i);
  if (direct) {
    const normalized = direct[0].toUpperCase().replace(/[_ ]/g, "-");
    return normalized.startsWith("ORD-") ? normalized : normalized.replace("ORD", "ORD-");
  }
  const idMatch = raw.match(/\border[_\s-]*id[:#\s-]*([A-Za-z0-9-]{4,})\b/i);
  if (idMatch) {
    return String(idMatch[1]).toUpperCase().replace(/[_ ]/g, "-");
  }
  return null;
}

function latestToolTrace(traces, toolName) {
  if (!Array.isArray(traces)) {
    return null;
  }
  for (let i = traces.length - 1; i >= 0; i -= 1) {
    if (traces[i] && traces[i].tool_name === toolName) {
      return traces[i];
    }
  }
  return null;
}

function buildActionTypeOptions() {
  const actions = state.observation?.available_actions || [];
  refs.actionType.innerHTML = "";
  actions.forEach((name) => {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    refs.actionType.appendChild(opt);
  });
  renderActionFields();
}

function createField(labelText, key, type = "text", value = "") {
  const wrap = document.createElement("div");
  wrap.className = "control-row";
  const label = document.createElement("label");
  label.textContent = labelText;

  let input;
  if (type === "textarea") {
    input = document.createElement("textarea");
    input.value = value;
  } else if (Array.isArray(type)) {
    input = document.createElement("select");
    type.forEach((optionValue) => {
      const option = document.createElement("option");
      option.value = optionValue;
      option.textContent = optionValue;
      input.appendChild(option);
    });
    input.value = value || type[0] || "";
  } else {
    input = document.createElement("input");
    input.type = type;
    input.value = value;
  }

  input.dataset.key = key;
  wrap.appendChild(label);
  wrap.appendChild(input);
  return wrap;
}

function renderActionFields() {
  const actionType = refs.actionType.value;
  refs.actionFields.innerHTML = "";

  if (actionType === "classify_email") {
    refs.actionFields.appendChild(createField("Category", "category", categoryOptions, "General Inquiry"));
    refs.actionFields.appendChild(createField("Priority", "priority", priorityOptions, "Normal"));
    refs.actionFields.appendChild(createField("Order ID", "order_id", "text", ""));
  } else if (actionType === "query_policy") {
    refs.actionFields.appendChild(createField("Policy Question", "policy_question", "textarea", "Can a 40-day-old order be returned?"));
  } else if (actionType === "draft_response") {
    refs.actionFields.appendChild(createField("Response Text", "response_text", "textarea", ""));
  } else if (actionType === "query_order_db") {
    refs.actionFields.appendChild(createField("Order ID", "order_id", "text", ""));
  } else if (actionType === "query_inventory") {
    refs.actionFields.appendChild(createField("SKU", "sku", "text", ""));
  } else if (actionType === "ship_replacement" || actionType === "issue_refund") {
    refs.actionFields.appendChild(createField("Order ID", "order_id", "text", ""));
    refs.actionFields.appendChild(createField("Reason", "reason", "text", actionType === "ship_replacement" ? "defective_item" : "replacement_out_of_stock"));
  }
}

function collectActionFromForm() {
  const action = { action_type: refs.actionType.value };
  const fields = refs.actionFields.querySelectorAll("input, textarea, select");
  fields.forEach((el) => {
    const key = el.dataset.key;
    const raw = el.value;
    if (raw !== "") {
      action[key] = raw;
    }
  });
  return action;
}

function renderMetrics() {
  const o = state.observation;
  const context = o?.context || {};
  const data = [
    ["Task", state.taskId],
    ["Step", String(o?.step_number ?? 0)],
    ["Done", String(state.done)],
    ["Step Reward", Number(state.lastReward || 0).toFixed(3)],
    ["Total Reward", Number(state.totalReward || 0).toFixed(3)],
    ["Allowed", String((o?.available_actions || []).length)],
    ["Tool Traces", String((o?.tool_traces || []).length)],
    ["Steps Left", String(context.steps_remaining ?? "-")],
  ];

  refs.metrics.innerHTML = "";
  data.forEach(([k, v]) => {
    const card = document.createElement("div");
    card.className = "metric";
    card.innerHTML = `<div class="k">${k}</div><div class="v">${v}</div>`;
    refs.metrics.appendChild(card);
  });
}

function renderObservation() {
  refs.observationView.textContent = buildObservationText();
}

function formatContextLines(context) {
  const entries = Object.entries(context || {});
  if (entries.length === 0) {
    return "- none";
  }
  return entries
    .map(([k, v]) => `- ${k}: ${typeof v === "object" ? safeJson(v) : String(v)}`)
    .join("\n");
}

function buildObservationText() {
  const o = state.observation;
  if (!o) {
    return "No observation yet. Click Reset to start.";
  }

  const lines = [
    `Task: ${o.task_id || state.taskId}`,
    `Step: ${o.step_number ?? 0}`,
    `Allowed Actions: ${(o.available_actions || []).join(", ") || "none"}`,
  ];

  if (o.last_action_error) {
    lines.push(`Last Error: ${o.last_action_error}`);
  }

  if (o.current_email) {
    const e = o.current_email;
    lines.push("", "Current Email:");
    lines.push(`- id: ${e.id || "N/A"}`);
    lines.push(`- sender: ${e.sender || "N/A"}`);
    lines.push(`- subject: ${e.subject || "N/A"}`);
    lines.push(`- body: ${e.body || "N/A"}`);
  }

  if (o.ticket) {
    const t = o.ticket;
    lines.push("", "Ticket:");
    lines.push(`- id: ${t.id || "N/A"}`);
    lines.push(`- customer_email: ${t.customer_email || "N/A"}`);
    lines.push(`- message: ${t.message || "N/A"}`);
    if (t.reported_order_id) {
      lines.push(`- reported_order_id: ${t.reported_order_id}`);
    }
  }

  lines.push("", "Context:");
  lines.push(formatContextLines(o.context));

  const traces = o.tool_traces || [];
  lines.push("", `Tool Traces (${traces.length}):`);
  if (traces.length === 0) {
    lines.push("- none");
  } else {
    traces.forEach((trace, idx) => {
      lines.push(`- ${idx + 1}. ${trace.tool_name || "unknown_tool"}`);
      if (trace.request) {
        lines.push(`  request: ${safeJson(trace.request)}`);
      }
      if (trace.result) {
        lines.push(`  result: ${safeJson(trace.result)}`);
      }
    });
  }

  return lines.join("\n");
}

function buildTimelineText(action, payload) {
  const reward = payload?.reward || {};
  const info = payload?.info || {};
  const parts = [
    `Action: ${action?.action_type || "N/A"}`,
    `Reward: ${Number(reward.value || 0).toFixed(3)}`,
    `Done: ${Boolean(payload?.done)}`,
    `Feedback: ${reward.feedback || "No feedback"}`,
  ];

  if (action?.order_id) {
    parts.push(`Order ID: ${action.order_id}`);
  }
  if (action?.category) {
    parts.push(`Category: ${action.category}`);
  }
  if (action?.priority) {
    parts.push(`Priority: ${action.priority}`);
  }
  if (action?.response_text) {
    parts.push(`Response: ${action.response_text}`);
  }
  if (action?.reason) {
    parts.push(`Reason: ${action.reason}`);
  }

  const breakdown = Object.entries(reward.breakdown || {})
    .map(([k, v]) => `${k}=${Number(v || 0).toFixed(3)}`)
    .join(", ");
  if (breakdown) {
    parts.push(`Breakdown: ${breakdown}`);
  }

  if (Object.keys(info).length > 0) {
    parts.push(`Info: ${safeJson(info)}`);
  }

  return parts.join("\n");
}

function renderTimeline() {
  refs.timeline.innerHTML = "";
  state.timeline.forEach((entry) => {
    const item = document.createElement("div");
    item.className = `timeline-item ${entry.error ? "error" : ""}`;
    item.innerHTML = `<div class="head">Step ${entry.step} • ${entry.action}</div><div class="desc">${entry.desc}</div>`;
    refs.timeline.appendChild(item);
  });
}

function formatBreakdownLines(breakdown) {
  const entries = Object.entries(breakdown || {});
  if (entries.length === 0) {
    return "- No breakdown available";
  }
  return entries
    .map(([k, v]) => `- ${k}: ${Number(v || 0).toFixed(3)}`)
    .join("\n");
}

function buildFinalOutcomeText() {
  if (!state.done || !state.lastPayload) {
    return [
      "Status: In progress",
      `Task: ${state.taskId}`,
      "Message: Complete the episode to see the final response.",
    ].join("\n");
  }

  const payload = state.lastPayload;
  const action = state.lastAction || {};
  const reward = payload.reward || {};
  const traces = state.observation?.tool_traces || [];
  const context = state.observation?.context || {};
  const recommendation = payload.support_recommendation || {};

  const lines = [
    "Status: Done",
    `Task: ${state.taskId}`,
    `Steps: ${state.steps}`,
    `Total Reward: ${Number(state.totalReward).toFixed(3)}`,
    `Final Step Reward: ${Number(reward.value || 0).toFixed(3)}`,
    "",
    "Reward Breakdown:",
    formatBreakdownLines(reward.breakdown),
    "",
    `Grader Feedback: ${reward.feedback || "No feedback available."}`,
    "",
    "Final Action Sent:",
    `- action_type: ${action.action_type || "N/A"}`,
  ];

  if (action.order_id) {
    lines.push(`- order_id: ${action.order_id}`);
  }
  if (action.category) {
    lines.push(`- category: ${action.category}`);
  }
  if (action.priority) {
    lines.push(`- priority: ${action.priority}`);
  }
  if (action.response_text) {
    lines.push(`- response_text: ${action.response_text}`);
  }
  if (action.reason) {
    lines.push(`- reason: ${action.reason}`);
  }

  lines.push("", "Task-specific Outcome:");
  if (state.taskId === "task_1") {
    lines.push(`- processed_emails: ${context.emails_processed ?? "N/A"}`);
    lines.push(`- average_email_score: ${context.avg_email_score ?? "N/A"}`);
    lines.push(`- last_order_id: ${action.order_id || "N/A"}`);
  } else if (state.taskId === "task_2") {
    lines.push(`- policy_queried: ${Boolean(context.queried_policy)}`);
    lines.push(`- final_response_text: ${action.response_text || "N/A"}`);
  } else {
    const finalTrace = traces.length > 0 ? traces[traces.length - 1] : null;
    const resultText = finalTrace?.result ? safeJson(finalTrace.result) : "N/A";
    lines.push(`- action_executed: ${action.action_type || "N/A"}`);
    lines.push(`- system_result: ${resultText}`);
  }

  if (Object.keys(recommendation).length > 0) {
    lines.push("", "Support Recommendation:");
    lines.push(`- suggested_response: ${recommendation.suggested_response || "N/A"}`);
    lines.push(`- pitch_note: ${recommendation.pitch_note || "N/A"}`);
    const matches = recommendation.matched_cases || [];
    if (matches.length > 0) {
      lines.push(`- matched_cases: ${matches.map((match) => `${match.record_id} (${match.label})`).join(', ')}`);
    }
    if (recommendation.index_stats) {
      lines.push(`- index_stats: ${safeJson(recommendation.index_stats)}`);
    }
  }

  return lines.join("\n");
}

function renderOutcome() {
  refs.outcomeView.textContent = buildFinalOutcomeText();
}

function renderSupportSearchResults(matches, query) {
  refs.supportSearchResults.innerHTML = "";

  if (!query) {
    refs.supportSearchResults.innerHTML = '<div class="search-empty">Enter a query to search the support corpus.</div>';
    return;
  }

  if (!Array.isArray(matches) || matches.length === 0) {
    refs.supportSearchResults.innerHTML = '<div class="search-empty">No matches found for that query.</div>';
    return;
  }

  matches.forEach((match, index) => {
    const card = document.createElement("article");
    card.className = "search-card";

    const head = document.createElement("div");
    head.className = "search-card-head";
    const left = document.createElement("span");
    left.textContent = `#${index + 1} ${match.record_id || "unknown"}`;
    const right = document.createElement("span");
    right.textContent = `${match.label || "unknown"} • score ${Number(match.score || 0).toFixed(3)}`;
    head.appendChild(left);
    head.appendChild(right);

    const meta = document.createElement("div");
    meta.className = "search-card-meta";
    meta.textContent = `source: ${match.source || "N/A"}`;

    const snippet = document.createElement("div");
    snippet.className = "search-card-snippet";
    snippet.textContent = match.snippet || "";

    const metadata = document.createElement("div");
    metadata.className = "search-card-metadata";
    metadata.textContent = match.metadata ? safeJson(match.metadata) : "{}";

    card.appendChild(head);
    card.appendChild(meta);
    card.appendChild(snippet);
    card.appendChild(metadata);
    refs.supportSearchResults.appendChild(card);
  });
}

function renderSupportStats(stats) {
  refs.supportStats.innerHTML = "";
  if (!stats) {
    refs.supportStats.innerHTML = '<div class="search-empty">Corpus stats unavailable.</div>';
    return;
  }

  const cards = [
    ["Records", String(stats.records ?? 0)],
    ["Unique Tokens", String(stats.unique_tokens ?? 0)],
    ["Top Labels", (stats.top_labels || []).slice(0, 3).map((item) => `${item.label}:${item.count}`).join(" | ") || "N/A"],
  ];

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
    refs.supportStats.appendChild(card);
  });
}

async function loadSupportStats() {
  const resp = await fetch("/support/stats");
  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status}`);
  }
  const payload = await resp.json();
  renderSupportStats(payload);
}

async function runSupportSearch() {
  const query = refs.supportSearchInput.value.trim();
  const topK = asInt(refs.supportSearchTopK.value, 3);

  if (!query) {
    renderSupportSearchResults([], query);
    setStatus("Enter a search query first.");
    return;
  }

  const resp = await fetch("/support/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, top_k: topK }),
  });

  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try {
      const payload = await resp.json();
      if (payload?.detail) {
        detail = payload.detail;
      }
    } catch (_e) {
      // Ignore malformed error bodies.
    }
    throw new Error(detail);
  }

  const payload = await resp.json();
  renderSupportSearchResults(payload.matches || [], payload.query || query);
  setStatus(`Search complete for "${query}".`);
}

function renderAll() {
  buildActionTypeOptions();
  renderMetrics();
  renderObservation();
  renderTimeline();
  renderOutcome();
}

function inferTask1Action(observation) {
  const current = observation?.current_email || {};
  const subject = String(current.subject || "").toLowerCase();
  const body = String(current.body || "").toLowerCase();
  const text = `${subject} ${body}`;

  let category = "General Inquiry";
  if (/(defective|damaged|cracked|broke|faulty|not working|stopped working)/.test(text)) {
    category = "Product Defect";
  } else if (/(tracking|where is my package|shipping|shipment|delayed|not updated|late|lost)/.test(text)) {
    category = "Shipping Delay";
  } else if (/(login|log in|password|account|two-factor|2fa|authentication)/.test(text)) {
    category = "Account Access";
  } else if (/(charged|billing|invoice|payment|card|double charge|overcharged)/.test(text)) {
    category = "Billing Issue";
  } else if (/refund/.test(text)) {
    category = "Refund Request";
  }

  let priority = "Normal";
  if (/(urgent|asap|immediately|today|lawsuit|legal|angry|threat)/.test(text)) {
    priority = "Urgent";
  } else if (/(no rush|whenever|fyi)/.test(text)) {
    priority = "Low";
  }

  const orderId = extractOrderId(`${subject} ${body}`);
  return { action_type: "classify_email", category, priority, order_id: orderId };
}

function inferTask2Action(observation) {
  const traces = observation?.tool_traces || [];
  const policyTrace = latestToolTrace(traces, "query_policy");
  const ticket = observation?.ticket || {};
  if (!policyTrace) {
    return {
      action_type: "query_policy",
      policy_question: ticket.message || "What is the return window policy?",
    };
  }

  const result = policyTrace.result || {};
  const windowDays = asInt(result.window_days ?? result.return_window_days, 30);
  let days = asInt(observation?.context?.days_since_delivery, -1);
  if (days < 0) {
    const match = String(ticket.message || "").match(/(\d+)\s*day/i);
    days = match ? asInt(match[1], windowDays + 1) : windowDays + 1;
  }

  const responseText = days <= windowDays
    ? `Your return is approved because it is within ${windowDays} days of delivery. Please share your preferred return method so we can proceed.`
    : `Your return is declined because it is outside ${windowDays} days from delivery. We can still help with troubleshooting or warranty options.`;
  return { action_type: "draft_response", response_text: responseText };
}

function inferTask3Action(observation) {
  const ticket = observation?.ticket || {};
  const traces = observation?.tool_traces || [];
  const orderId = ticket.reported_order_id;
  const orderTrace = latestToolTrace(traces, "query_order_db");

  if (!orderTrace) {
    return { action_type: "query_order_db", order_id: orderId };
  }

  const orderResult = orderTrace.result || {};
  const orderExists = Boolean(orderResult.order_exists ?? orderResult.exists ?? orderResult.found ?? orderResult.valid);
  const sku = orderResult.sku;

  if (!orderExists) {
    return { action_type: "issue_refund", order_id: orderId, reason: "order_not_found_defective_claim" };
  }

  const invTrace = latestToolTrace(traces, "query_inventory");
  if (!invTrace) {
    if (sku) {
      return { action_type: "query_inventory", sku };
    }
    return { action_type: "issue_refund", order_id: orderId, reason: "missing_sku_for_replacement" };
  }

  const invResult = invTrace.result || {};
  const inStock = asInt(invResult.in_stock ?? invResult.stock ?? invResult.available_qty ?? invResult.qty, 0);
  if (inStock > 0) {
    return { action_type: "ship_replacement", order_id: orderId, reason: "defective_item" };
  }
  return { action_type: "issue_refund", order_id: orderId, reason: "replacement_out_of_stock" };
}

function coerceAllowed(action, availableActions) {
  if (!Array.isArray(availableActions) || availableActions.length === 0) {
    return action;
  }
  if (availableActions.includes(action.action_type)) {
    return action;
  }
  return { action_type: availableActions[0] };
}

function inferAutoAction() {
  const o = state.observation;
  if (!o) {
    return null;
  }
  if (state.taskId === "task_1") {
    return coerceAllowed(inferTask1Action(o), o.available_actions || []);
  }
  if (state.taskId === "task_2") {
    return coerceAllowed(inferTask2Action(o), o.available_actions || []);
  }
  return coerceAllowed(inferTask3Action(o), o.available_actions || []);
}

async function apiReset() {
  const resp = await fetch(`/reset/${state.taskId}`, { method: "POST" });
  if (!resp.ok) {
    throw new Error(`Reset failed: ${resp.status}`);
  }
  state.observation = await resp.json();
  state.done = false;
  state.totalReward = 0;
  state.lastReward = 0;
  state.steps = 0;
  state.timeline = [];
  state.lastPayload = null;
  state.lastAction = null;
  setStatus(`Reset complete for ${state.taskId}.`);
  renderAll();
}

async function apiStep(action) {
  const resp = await fetch(`/step/${state.taskId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(action),
  });
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try {
      const payload = await resp.json();
      if (payload?.detail) {
        detail = payload.detail;
      }
    } catch (_e) {
      // Ignore malformed error bodies.
    }
    throw new Error(detail);
  }

  const payload = await resp.json();
  state.observation = payload.observation;
  state.lastReward = Number(payload.reward?.value || 0);
  state.totalReward += state.lastReward;
  state.done = Boolean(payload.done);
  state.steps += 1;
  state.lastPayload = payload;
  state.lastAction = action;

  state.timeline.unshift({
    step: state.steps,
    action: action.action_type,
    desc: buildTimelineText(action, payload),
    error: Boolean(state.observation?.last_action_error),
  });

  setStatus(`Step ${state.steps} complete. Reward ${state.lastReward.toFixed(3)}.`);
  renderAll();
}

function getAutoStepOptions() {
  return {
    api_key: refs.apiKeyInput.value.trim() || null,
    model_name: refs.modelInput.value.trim() || null,
    use_api: Boolean(refs.useApiCheckbox.checked),
  };
}

async function apiAutoStep() {
  const resp = await fetch(`/auto-step/${state.taskId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(getAutoStepOptions()),
  });
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try {
      const payload = await resp.json();
      if (payload?.detail) {
        detail = payload.detail;
      }
    } catch (_e) {
      // Ignore malformed error bodies.
    }
    throw new Error(detail);
  }

  const payload = await resp.json();
  const action = payload.action_used || { action_type: "unknown" };
  state.observation = payload.observation;
  state.lastReward = Number(payload.reward?.value || 0);
  state.totalReward += state.lastReward;
  state.done = Boolean(payload.done);
  state.steps += 1;
  state.lastPayload = payload;
  state.lastAction = action;

  state.timeline.unshift({
    step: state.steps,
    action: action.action_type,
    desc: buildTimelineText(action, payload),
    error: Boolean(state.observation?.last_action_error),
  });

  setStatus(`Step ${state.steps} complete. Reward ${state.lastReward.toFixed(3)}.`);
  renderAll();
}

async function runEpisode() {
  if (!state.observation || state.done) {
    await apiReset();
  }

  const maxLoops = 20;
  for (let i = 0; i < maxLoops; i += 1) {
    if (state.done) {
      break;
    }
    await apiAutoStep();
    await new Promise((resolve) => setTimeout(resolve, 240));
  }

  setStatus(`Episode finished. Total reward ${state.totalReward.toFixed(3)}.`);
}

async function submitManualAction() {
  if (!state.observation) {
    await apiReset();
  }
  const action = collectActionFromForm();
  await apiStep(action);
}

refs.taskSelect.addEventListener("change", async (e) => {
  state.taskId = e.target.value;
  await apiReset();
});

refs.actionType.addEventListener("change", renderActionFields);

refs.resetBtn.addEventListener("click", async () => {
  try {
    await apiReset();
  } catch (err) {
    setStatus(`Error: ${err.message}`);
  }
});

refs.submitActionBtn.addEventListener("click", async () => {
  try {
    await submitManualAction();
  } catch (err) {
    setStatus(`Error: ${err.message}`);
  }
});

refs.autoBtn.addEventListener("click", async () => {
  try {
    if (!state.observation) {
      await apiReset();
    }
    await apiAutoStep();
  } catch (err) {
    setStatus(`Error: ${err.message}`);
  }
});

refs.runEpisodeBtn.addEventListener("click", async () => {
  try {
    await runEpisode();
  } catch (err) {
    setStatus(`Error: ${err.message}`);
  }
});

refs.supportSearchBtn.addEventListener("click", async () => {
  try {
    await runSupportSearch();
  } catch (err) {
    setStatus(`Search error: ${err.message}`);
  }
});

refs.supportSearchClearBtn.addEventListener("click", () => {
  refs.supportSearchInput.value = "";
  refs.supportSearchResults.innerHTML = '<div class="search-empty">Enter a query to search the support corpus.</div>';
  setStatus("Search cleared.");
});

(async function init() {
  refs.taskSelect.value = state.taskId;
  refs.supportSearchResults.innerHTML = '<div class="search-empty">Enter a query to search the support corpus.</div>';
  try {
    await loadSupportStats();
    await apiReset();
  } catch (err) {
    setStatus(`Boot failed: ${err.message}`);
  }
})();
