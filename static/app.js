const currency = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
const state = { charts: {}, meta: null };

function formatCurrency(v) {
  return currency.format(v || 0);
}

async function fetchJSON(url, options) {
  const res = await fetch(url, options);
  return res.json();
}

function setActiveView(target) {
  document.querySelectorAll(".nav-item").forEach((b) => b.classList.remove("active"));
  document.querySelector(`.nav-item[data-target='${target}']`).classList.add("active");
  document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
  document.getElementById(`view-${target}`).classList.add("active");
  const titleMap = {
    dashboard: "Dashboard",
    add: "Add Expense",
    scan: "Scan Receipt",
    "voice-entry": "Voice Entry",
    assistant: "AI Voice Assistant",
    predictions: "Predictions",
    reports: "Reports",
    settings: "Settings",
  };
  document.getElementById("pageTitle").textContent = titleMap[target];
}

function buildTable(expenses) {
  const table = document.getElementById("recentTable");
  table.innerHTML = "";
  const header = document.createElement("div");
  header.className = "table-row header";
  header.innerHTML = `
    <div>Date</div>
    <div>Category</div>
    <div>Amount</div>
    <div class="note">Description</div>
    <div class="actions">Method</div>
  `;
  table.appendChild(header);
  expenses.forEach((exp) => {
    const row = document.createElement("div");
    row.className = "table-row";
    row.innerHTML = `
      <div>${exp.date}</div>
      <div>${exp.category}</div>
      <div>${formatCurrency(exp.amount)}</div>
      <div class="note">${exp.description || "-"}</div>
      <div class="actions">${exp.entry_method || "manual"}</div>
    `;
    table.appendChild(row);
  });
}

function updateInsights(insights) {
  const list = document.getElementById("insights");
  list.innerHTML = "";
  insights.forEach((text) => {
    const li = document.createElement("li");
    li.innerHTML = text;
    list.appendChild(li);
  });
  document.getElementById("quickInsight").textContent = insights[0] ? insights[0].replace(/<[^>]*>/g, "") : "";
}

function updateCards(data) {
  document.getElementById("totalAll").textContent = formatCurrency(data.total_all);
  document.getElementById("totalMonth").textContent = formatCurrency(data.total_range);
  document.getElementById("monthLabel").textContent = data.range_label;
  const max = Math.max(...data.category_totals);
  const idx = data.category_totals.findIndex((v) => v === max);
  document.getElementById("topCategory").textContent = max > 0 ? data.categories[idx] : "-";
}

function renderCharts(data) {
  const common = {
    plugins: { legend: { labels: { color: getComputedStyle(document.body).getPropertyValue("--text") } } },
    scales: {
      x: { ticks: { color: getComputedStyle(document.body).getPropertyValue("--muted") } },
      y: { ticks: { color: getComputedStyle(document.body).getPropertyValue("--muted") } },
    },
  };

  if (state.charts.pie) state.charts.pie.destroy();
  state.charts.pie = new Chart(document.getElementById("pieChart"), {
    type: "pie",
    data: {
      labels: data.categories,
      datasets: [
        { data: data.category_totals, backgroundColor: ["#0f766e", "#f97316", "#2563eb", "#64748b", "#ec4899", "#14b8a6", "#a855f7", "#f43f5e", "#22c55e"] },
      ],
    },
    options: { plugins: { legend: { position: "bottom" } } },
  });

  if (state.charts.bar) state.charts.bar.destroy();
  state.charts.bar = new Chart(document.getElementById("barChart"), {
    type: "bar",
    data: { labels: data.months, datasets: [{ label: "Monthly Spend", data: data.month_totals, backgroundColor: "rgba(15,118,110,0.6)" }] },
    options: common,
  });

  if (state.charts.line) state.charts.line.destroy();
  state.charts.line = new Chart(document.getElementById("lineChart"), {
    type: "line",
    data: { labels: data.trend_labels, datasets: [{ label: "Daily Spend", data: data.trend_values, borderColor: "#f97316", backgroundColor: "rgba(249,115,22,0.2)", fill: true, tension: 0.3 }] },
    options: common,
  });

  if (state.charts.compare) state.charts.compare.destroy();
  state.charts.compare = new Chart(document.getElementById("compareChart"), {
    type: "bar",
    data: {
      labels: data.categories,
      datasets: [
        { label: "This Month", data: data.comparison_current, backgroundColor: "rgba(14,116,144,0.7)" },
        { label: "Last Month", data: data.comparison_last, backgroundColor: "rgba(100,116,139,0.5)" },
      ],
    },
    options: common,
  });

  if (document.getElementById("reportPie")) {
    if (state.charts.reportPie) state.charts.reportPie.destroy();
    state.charts.reportPie = new Chart(document.getElementById("reportPie"), {
      type: "doughnut",
      data: { labels: data.categories, datasets: [{ data: data.category_totals, backgroundColor: ["#0f766e", "#f97316", "#2563eb", "#64748b", "#ec4899", "#14b8a6", "#a855f7", "#f43f5e", "#22c55e"] }] },
      options: { plugins: { legend: { position: "bottom" } } },
    });
  }

  if (document.getElementById("reportBar")) {
    if (state.charts.reportBar) state.charts.reportBar.destroy();
    state.charts.reportBar = new Chart(document.getElementById("reportBar"), {
      type: "bar",
      data: { labels: data.months, datasets: [{ label: "Monthly", data: data.month_totals, backgroundColor: "rgba(15,118,110,0.6)" }] },
      options: common,
    });
  }
}

function getRangeParams() {
  const rangeSelect = document.getElementById("rangeSelect");
  const startEl = document.getElementById("rangeStart");
  const endEl = document.getElementById("rangeEnd");
  const duration = rangeSelect.value;
  if (duration === "custom") {
    return { start: startEl.value, end: endEl.value, duration: "custom" };
  }
  return { duration };
}

async function loadMeta() {
  state.meta = await fetchJSON("/api/meta");
  const catSelect = document.getElementById("categorySelect");
  const paySelect = document.getElementById("paymentSelect");
  const filterCategory = document.getElementById("filterCategory");

  catSelect.innerHTML = state.meta.categories.map((c) => `<option>${c}</option>`).join("");
  paySelect.innerHTML = state.meta.payment_methods.map((p) => `<option>${p}</option>`).join("");
  filterCategory.innerHTML = ["All", ...state.meta.categories].map((c) => `<option>${c}</option>`).join("");
}

async function loadAnalytics() {
  const params = new URLSearchParams(getRangeParams());
  const data = await fetchJSON(`/api/analytics?${params.toString()}`);
  updateCards(data);
  updateInsights(data.insights);
  renderCharts(data);
  return data;
}

async function loadExpenses() {
  const range = getRangeParams();
  const filterCategory = document.getElementById("filterCategory").value;
  const sort = document.getElementById("filterSort").value;
  const order = document.getElementById("filterOrder").value;
  const limit = document.getElementById("filterLimit").value;

  const params = new URLSearchParams();
  if (range.duration && range.duration !== "custom") params.set("duration", range.duration);
  if (range.start) params.set("start", range.start);
  if (range.end) params.set("end", range.end);
  if (filterCategory) params.set("category", filterCategory);
  if (sort) params.set("sort", sort);
  if (order) params.set("order", order);
  if (limit) params.set("limit", limit);

  const data = await fetchJSON(`/api/expenses?${params.toString()}`);
  buildTable(data);
  return data;
}

async function addExpense(payload) {
  await fetchJSON("/api/expenses", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

function initTheme() {
  const toggle = document.getElementById("themeToggle");
  toggle.addEventListener("change", () => {
    document.body.setAttribute("data-theme", toggle.checked ? "dark" : "light");
    loadAnalytics();
  });
}

function initNavigation() {
  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.addEventListener("click", () => setActiveView(btn.dataset.target));
  });
}

function initAddExpense() {
  const form = document.getElementById("expenseForm");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(form).entries());
    data.amount = parseFloat(data.amount);
    data.entry_method = "manual";
    await addExpense(data);
    form.reset();
    await refreshAll();
    setActiveView("dashboard");
  });
}

function parseVoiceExpense(text) {
  const t = text.toLowerCase();
  const amountMatch = t.match(/(\d+\.?\d*)/);
  const amount = amountMatch ? parseFloat(amountMatch[1]) : null;
  const categoryMap = {
    food: "Food & Dining",
    dining: "Food & Dining",
    restaurant: "Food & Dining",
    travel: "Travel",
    transport: "Transportation",
    shopping: "Shopping",
    entertainment: "Entertainment",
    bills: "Bills & Utilities",
    utilities: "Bills & Utilities",
    healthcare: "Healthcare",
    education: "Education",
  };
  let category = null;
  Object.keys(categoryMap).forEach((k) => {
    if (t.includes(k)) category = categoryMap[k];
  });
  const paymentMap = {
    cash: "Cash",
    debit: "Debit Card",
    credit: "Credit Card",
    wallet: "Digital Wallet",
    bank: "Bank Transfer",
  };
  let payment_method = "Cash";
  Object.keys(paymentMap).forEach((k) => {
    if (t.includes(k)) payment_method = paymentMap[k];
  });
  return { amount, category, payment_method, description: text };
}

function initVoiceEntry() {
  const btn = document.getElementById("voiceEntryBtn");
  const log = document.getElementById("voiceEntryLog");
  if (!("webkitSpeechRecognition" in window)) {
    log.textContent = "Speech recognition is not supported in this browser.";
    return;
  }
  const recognition = new webkitSpeechRecognition();
  recognition.lang = "en-IN";
  recognition.interimResults = false;

  btn.addEventListener("click", () => {
    log.textContent = "Listening...";
    recognition.start();
  });

  recognition.onresult = async (event) => {
    const transcript = event.results[0][0].transcript;
    log.textContent = `You said: ${transcript}`;
    const parsed = parseVoiceExpense(transcript);
    if (!parsed.amount || !parsed.category) {
      log.textContent = "Could not detect amount or category. Try saying: 'Spent 12 on food via cash'.";
      return;
    }
    const payload = {
      date: new Date().toISOString().slice(0, 10),
      category: parsed.category,
      amount: parsed.amount,
      payment_method: parsed.payment_method,
      description: parsed.description,
      entry_method: "voice",
    };
    await addExpense(payload);
    await refreshAll();
    log.textContent = "Expense added via voice.";
  };
}

function initOCR() {
  const scanBtn = document.getElementById("scanBtn");
  const fileInput = document.getElementById("receiptFile");
  const result = document.getElementById("scanResult");

  scanBtn.addEventListener("click", async () => {
    const file = fileInput.files[0];
    if (!file) {
      result.textContent = "Please select an image.";
      return;
    }
    const form = new FormData();
    form.append("file", file);
    result.textContent = "Scanning...";
    const res = await fetchJSON("/api/ocr", { method: "POST", body: form });
    if (res.error) {
      result.textContent = res.error;
      return;
    }
    result.textContent = `Detected: ${res.parsed.merchant || ""} | Amount: ${res.parsed.amount || ""} | Category: ${res.parsed.category || ""}`;
  });
}

function pickPreferredVoice(voices) {
  const indian = voices.filter((v) => /-IN/i.test(v.lang));
  const femaleHints = /(female|zira|sangeeta|priya|heera|kanya|lekha|tessa|veena|samantha|kathy|deepti|sarita|shreya|aisha|ananya|rani)/i;
  const candidates = indian.length ? indian : voices;
  let preferred = candidates.find((v) => femaleHints.test(v.name));
  if (!preferred && indian.length) preferred = indian[0];
  if (!preferred && voices.length) preferred = voices[0];
  return preferred;
}

function initAssistant() {
  const micBtn = document.getElementById("assistantMic");
  const stopBtn = document.getElementById("assistantStop");
  const log = document.getElementById("assistantLog");
  const text = document.getElementById("assistantText");
  const askBtn = document.getElementById("assistantAsk");
  const voiceSelect = document.getElementById("assistantVoice");

  let recognition = null;
  if ("webkitSpeechRecognition" in window) {
    recognition = new webkitSpeechRecognition();
    recognition.lang = "en-IN";
    recognition.interimResults = false;
    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      text.value = transcript;
      askQuestion(transcript);
    };
  }

  function populateVoices() {
    if (!voiceSelect || !("speechSynthesis" in window)) return;
    const voices = speechSynthesis.getVoices();
    voiceSelect.innerHTML = "";
    voices.forEach((v) => {
      const opt = document.createElement("option");
      opt.value = v.name;
      opt.textContent = `${v.name} (${v.lang})`;
      voiceSelect.appendChild(opt);
    });
    const saved = localStorage.getItem("assistantVoice");
    if (saved) {
      voiceSelect.value = saved;
    } else {
      const preferred = pickPreferredVoice(voices);
      if (preferred) {
        voiceSelect.value = preferred.name;
        localStorage.setItem("assistantVoice", preferred.name);
      }
    }
  }

  if ("speechSynthesis" in window) {
    populateVoices();
    speechSynthesis.onvoiceschanged = populateVoices;
    voiceSelect.addEventListener("change", () => {
      localStorage.setItem("assistantVoice", voiceSelect.value);
    });
  }

  function speak(answer) {
    if (!("speechSynthesis" in window)) return;
    const utter = new SpeechSynthesisUtterance(answer);
    const voices = speechSynthesis.getVoices();
    const selected = voiceSelect ? voiceSelect.value : null;
    if (selected) {
      const voice = voices.find((v) => v.name === selected);
      if (voice) utter.voice = voice;
    }
    utter.rate = 0.95;
    utter.pitch = 1.05;
    speechSynthesis.speak(utter);
  }

  async function askQuestion(query) {
    if (!query) {
      log.textContent = "Please ask a question first.";
      return;
    }
    log.textContent = `You asked: ${query}`;
    const res = await fetchJSON("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
    log.textContent = `Assistant: ${res.answer}`;
    speak(res.answer);
  }

  micBtn.onclick = () => {
    if (!recognition) {
      log.textContent = "Speech recognition is not supported in this browser.";
      return;
    }
    log.textContent = "Listening...";
    recognition.start();
  };
  stopBtn.onclick = () => recognition && recognition.stop();
  askBtn.onclick = () => askQuestion(text.value.trim());
}

async function initPredictions() {
  const btn = document.getElementById("predictBtn");
  const daysInput = document.getElementById("predictDays");
  const summary = document.getElementById("predictSummary");

  btn.addEventListener("click", async () => {
    const days = parseInt(daysInput.value || "30", 10);
    const res = await fetchJSON("/api/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ days_ahead: days }),
    });
    if (res.error) {
      summary.textContent = res.error;
      return;
    }
    summary.textContent = res.message;
    if (state.charts.predict) state.charts.predict.destroy();
    state.charts.predict = new Chart(document.getElementById("predictChart"), {
      type: "line",
      data: { labels: res.dates, datasets: [{ label: "Predicted", data: res.values, borderColor: "#f97316", backgroundColor: "rgba(249,115,22,0.2)", fill: true }] },
      options: { scales: { x: { ticks: { color: getComputedStyle(document.body).getPropertyValue("--muted") } }, y: { ticks: { color: getComputedStyle(document.body).getPropertyValue("--muted") } } } },
    });
  });
}

async function initReports() {
  const report = await fetchJSON("/api/report");
  document.getElementById("reportContent").textContent = report.report;
  document.getElementById("downloadReport").addEventListener("click", () => {
    const blob = new Blob([report.report], { type: "text/markdown" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `expense_report_${new Date().toISOString().slice(0, 10)}.md`;
    link.click();
  });

  const analytics = await fetchJSON("/api/analytics");
  document.getElementById("reportSummary").innerHTML = `
    <h3>Summary</h3>
    <p><strong>Total:</strong> ${formatCurrency(analytics.total_all)}</p>
    <p><strong>Selected Range:</strong> ${formatCurrency(analytics.total_range)}</p>
    <p><strong>Top Category:</strong> ${analytics.categories[analytics.category_totals.indexOf(Math.max(...analytics.category_totals))] || "-"}</p>
  `;
  renderCharts(analytics);
}

async function initSettings() {
  const budgetList = document.getElementById("budgetList");
  const budgets = await fetchJSON("/api/budgets");
  budgetList.innerHTML = "";
  state.meta.categories.forEach((cat) => {
    const row = document.createElement("div");
    row.className = "budget-row";
    row.innerHTML = `
      <div>${cat}</div>
      <input type="number" step="0.01" value="${budgets[cat] || 0}" />
      <button class="btn ghost">Save</button>
    `;
    const input = row.querySelector("input");
    const btn = row.querySelector("button");
    btn.addEventListener("click", async () => {
      await fetchJSON("/api/budgets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category: cat, amount: parseFloat(input.value || "0") }),
      });
    });
    budgetList.appendChild(row);
  });
}

function initFilters() {
  const rangeSelect = document.getElementById("rangeSelect");
  const startEl = document.getElementById("rangeStart");
  const endEl = document.getElementById("rangeEnd");
  const dateFields = document.querySelectorAll(".date-field");
  const applyBtn = document.getElementById("applyFilters");

  function updateDateFields() {
    const isCustom = rangeSelect.value === "custom";
    dateFields.forEach((el) => el.classList.toggle("hidden", !isCustom));
  }
  rangeSelect.addEventListener("change", updateDateFields);
  updateDateFields();

  applyBtn.addEventListener("click", refreshAll);
  document.getElementById("filterCategory").addEventListener("change", refreshAll);
  document.getElementById("filterSort").addEventListener("change", refreshAll);
  document.getElementById("filterOrder").addEventListener("change", refreshAll);
}

async function initSeed() {
  const btn = document.getElementById("seedBtn");
  btn.addEventListener("click", async () => {
    await fetchJSON("/api/seed", { method: "POST" });
    await refreshAll();
  });
}

async function refreshAll() {
  await loadMeta();
  await Promise.all([loadAnalytics(), loadExpenses()]);
}

window.addEventListener("DOMContentLoaded", async () => {
  initTheme();
  initNavigation();
  initAddExpense();
  initVoiceEntry();
  initOCR();
  initAssistant();
  initPredictions();
  initSeed();
  initFilters();

  await refreshAll();
  await initReports();
  await initSettings();

  document.getElementById("refreshBtn").addEventListener("click", refreshAll);
});
