const els = {
  toast: document.querySelector("#toast"),
  runStatus: document.querySelector("#runStatus"),
  statusDot: document.querySelector("#statusDot"),
  targetTime: document.querySelector("#targetTime"),
  preparedCount: document.querySelector("#preparedCount"),
  cacheStatus: document.querySelector("#cacheStatus"),
  reservationForm: document.querySelector("#reservationForm"),
  usernumber: document.querySelector("#usernumber"),
  password: document.querySelector("#password"),
  seatNumber: document.querySelector("#seatNumber"),
  startTime: document.querySelector("#startTime"),
  endTime: document.querySelector("#endTime"),
  reservationList: document.querySelector("#reservationList"),
  clearReservations: document.querySelector("#clearReservations"),
  preheatBtn: document.querySelector("#preheatBtn"),
  startBtn: document.querySelector("#startBtn"),
  stopBtn: document.querySelector("#stopBtn"),
  templateName: document.querySelector("#templateName"),
  templateSelect: document.querySelector("#templateSelect"),
  saveTemplate: document.querySelector("#saveTemplate"),
  loadTemplate: document.querySelector("#loadTemplate"),
  deleteTemplate: document.querySelector("#deleteTemplate"),
  refreshTemplates: document.querySelector("#refreshTemplates"),
  historySelect: document.querySelector("#historySelect"),
  loadHistory: document.querySelector("#loadHistory"),
  clearHistory: document.querySelector("#clearHistory"),
  recordForm: document.querySelector("#recordForm"),
  recordUsernumber: document.querySelector("#recordUsernumber"),
  recordPassword: document.querySelector("#recordPassword"),
  recordSelect: document.querySelector("#recordSelect"),
  cancelRecord: document.querySelector("#cancelRecord"),
  recordCards: document.querySelector("#recordCards"),
  toggleRecordCards: document.querySelector("#toggleRecordCards"),
  accountList: document.querySelector("#accountList"),
  accountSelect: document.querySelector("#accountSelect"),
  refreshAccounts: document.querySelector("#refreshAccounts"),
  deleteAccount: document.querySelector("#deleteAccount"),
  clearAccounts: document.querySelector("#clearAccounts"),
  refreshState: document.querySelector("#refreshState"),
  runLog: document.querySelector("#runLog"),
};

let state = null;
let pollTimer = null;
let lastRecords = [];
let recordsCollapsed = false;
let userEditing = false;
let userEditingTimer = null;
const renderCache = {
  accounts: "",
  history: "",
  log: "",
  reservations: "",
  templates: "",
  timeOptions: "",
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function showToast(message) {
  if (!message) return;
  els.toast.textContent = message;
  els.toast.hidden = false;
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    els.toast.hidden = true;
  }, 3600);
}

function stableSignature(value) {
  return JSON.stringify(value ?? null);
}

function isBusyStatus(status) {
  return status === "running" || status === "preheating";
}

function isEditableElement(element) {
  if (!element) return false;
  return ["INPUT", "SELECT", "TEXTAREA"].includes(element.tagName);
}

function markUserEditing() {
  userEditing = true;
  window.clearTimeout(userEditingTimer);
  userEditingTimer = window.setTimeout(() => {
    userEditing = isEditableElement(document.activeElement);
  }, 1200);
}

function focusedOnEditable() {
  return userEditing || isEditableElement(document.activeElement);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || data.message || "请求失败");
  }
  return data;
}

function reservationSignature(reservations) {
  return stableSignature(
    (reservations || []).map((item) => ({
      usernumber: item["学号"],
      seat: item["座位号"],
      regionId: item["区域编号"] || "",
      regionName: item["区域名称"] || "",
      startTime: item["开始时间"],
      endTime: item["结束时间"],
      passwordCached: Boolean(item.passwordCached),
      passwordProvided: Boolean(item.passwordProvided),
    }))
  );
}

function setSelectOptions(select, options, placeholder = "暂无可选项") {
  const signature = stableSignature({ options, placeholder });
  if (select.dataset.signature === signature) {
    return;
  }
  const previousValue = select.value;
  select.innerHTML = "";
  if (!options.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = placeholder;
    select.append(option);
    select.dataset.signature = signature;
    return;
  }
  options.forEach((item) => {
    const option = document.createElement("option");
    if (typeof item === "string") {
      option.value = item;
      option.textContent = item;
    } else {
      option.value = item.value;
      option.textContent = item.label;
    }
    select.append(option);
  });
  if ([...select.options].some((option) => option.value === previousValue)) {
    select.value = previousValue;
  }
  select.dataset.signature = signature;
}

function fillTimeOptions(timeOptions) {
  const signature = stableSignature(timeOptions);
  if (renderCache.timeOptions === signature) {
    return;
  }
  const previousStart = els.startTime.value || "08:00:00";
  const previousEnd = els.endTime.value || "22:00:00";
  setSelectOptions(els.startTime, timeOptions);
  setSelectOptions(els.endTime, timeOptions);
  els.startTime.value = timeOptions.includes(previousStart) ? previousStart : timeOptions[0];
  els.endTime.value = timeOptions.includes(previousEnd) ? previousEnd : timeOptions[timeOptions.length - 1];
  renderCache.timeOptions = signature;
}

function renderReservations(reservations) {
  const signature = reservationSignature(reservations);
  if (renderCache.reservations === signature) {
    return;
  }
  renderCache.reservations = signature;
  if (!reservations.length) {
    els.reservationList.className = "reservation-list empty";
    els.reservationList.textContent = "暂无预约信息";
    return;
  }
  els.reservationList.className = "reservation-list";
  els.reservationList.innerHTML = reservations
    .map((item, index) => {
      const passwordText = item.passwordProvided
        ? "本次已填写密码"
        : item.passwordCached
          ? "本地已缓存密码"
          : "缺少密码";
      return `
        <article class="reservation-card">
          <div class="reservation-main">
            <div>
              <div class="reservation-title">${index + 1}. ${escapeHtml(item["学号"])} · ${escapeHtml(item["座位号"])}</div>
              <div class="meta-line">${escapeHtml(item["开始时间"])} - ${escapeHtml(item["结束时间"])} · ${escapeHtml(item["区域名称"])}</div>
            </div>
            <span class="tag">${escapeHtml(passwordText)}</span>
          </div>
          <div class="tag-row">
            <span class="tag">区域编号 ${escapeHtml(item["区域编号"] || "F6")}</span>
            <span class="tag">独立账号上下文</span>
          </div>
        </article>
      `;
    })
    .join("");
}

function renderRecords(records) {
  lastRecords = records || [];
  setSelectOptions(
    els.recordSelect,
    lastRecords.map((record) => ({
      label: `${record.seatNum || ""} | ${record.startTime || ""} | ${record.statusName || ""}`,
      value: String(record.id || ""),
    })),
    "暂无记录"
  );

  if (!lastRecords.length) {
    els.recordCards.className = "record-cards empty";
    els.recordCards.textContent = "暂无当前预约记录";
    els.toggleRecordCards.hidden = true;
    return;
  }
  els.toggleRecordCards.hidden = false;
  els.toggleRecordCards.textContent = recordsCollapsed ? "展开记录" : "收起记录";
  els.toggleRecordCards.setAttribute("aria-expanded", String(!recordsCollapsed));
  if (recordsCollapsed) {
    els.recordCards.className = "record-cards collapsed-summary";
    els.recordCards.textContent = `已收起 ${lastRecords.length} 条预约记录，可继续通过上方下拉框选择并取消。`;
    return;
  }
  els.recordCards.className = "record-cards";
  els.recordCards.innerHTML = lastRecords
    .map(
      (record) => `
        <article class="record-card">
          <div class="record-main">
            <div>
              <div class="record-title">座位 ${escapeHtml(record.seatNum)}</div>
              <div class="meta-line">${escapeHtml(record.startTime)} - ${escapeHtml(record.endTime)}</div>
            </div>
            <span class="tag">${escapeHtml(record.statusName)}</span>
          </div>
          <div class="tag-row">
            <span class="tag">记录 ID ${escapeHtml(record.id)}</span>
          </div>
        </article>
      `
    )
    .join("");
}

function renderAccounts(accounts) {
  const signature = stableSignature(accounts);
  if (renderCache.accounts === signature) {
    return;
  }
  renderCache.accounts = signature;
  setSelectOptions(
    els.accountSelect,
    accounts.map((usernumber) => ({ label: usernumber, value: usernumber })),
    "暂无已缓存账号"
  );
  if (!accounts.length) {
    els.accountList.className = "account-list empty";
    els.accountList.textContent = "暂无已缓存账号";
    return;
  }
  els.accountList.className = "account-list";
  els.accountList.innerHTML = accounts.map((usernumber) => `<div class="account-chip">${escapeHtml(usernumber)}</div>`).join("");
}

function renderLog(runLog) {
  const signature = stableSignature(runLog);
  if (renderCache.log === signature) {
    return;
  }
  renderCache.log = signature;
  if (!runLog.length) {
    els.runLog.textContent = "暂无运行日志";
    return;
  }
  els.runLog.textContent = runLog.join("\n");
  els.runLog.scrollTop = els.runLog.scrollHeight;
}

function renderTemplateOptions(templates) {
  const options = (templates || []).map((template) => ({
    label: `${template.name} · ${template.count} 条`,
    value: template.name,
  }));
  const signature = stableSignature(options);
  if (renderCache.templates === signature) {
    return;
  }
  renderCache.templates = signature;
  setSelectOptions(els.templateSelect, options, "暂无模板");
}

function renderHistoryOptions(history) {
  const options = (history || []).map((record) => ({ label: record.label, value: record.label }));
  const signature = stableSignature(options);
  if (renderCache.history === signature) {
    return;
  }
  renderCache.history = signature;
  setSelectOptions(els.historySelect, options, "暂无历史记录");
}

function renderState(nextState) {
  const previousStatus = state?.runStatus || "idle";
  state = nextState;

  if (!focusedOnEditable() && state.timeOptions?.length) {
    fillTimeOptions(state.timeOptions);
  }
  els.targetTime.textContent = state.targetTime || "12:00:17";
  els.preparedCount.textContent = String(state.preparedCount || 0);
  els.runStatus.textContent = state.runStatus || "idle";
  els.statusDot.className = `status-dot ${state.runStatus || "idle"}`;

  renderReservations(state.reservations || []);
  renderLog(state.runLog || []);

  const statusBecameIdle = isBusyStatus(previousStatus) && !isBusyStatus(state.runStatus);
  if (!focusedOnEditable() || statusBecameIdle) {
    renderAccounts(state.accounts || []);
    renderTemplateOptions(state.templates || []);
    renderHistoryOptions(state.history || []);
  }

  if (state.message) showToast(state.message);
  scheduleNextPoll();
}

async function refreshState() {
  renderState(await api("/api/state"));
}

async function mutate(path, body = null, method = "POST") {
  const options = { method };
  if (body !== null) options.body = JSON.stringify(body);
  renderState(await api(path, options));
}

async function checkAccountStatus() {
  const usernumber = els.usernumber.value.trim();
  if (!usernumber) {
    els.cacheStatus.textContent = "输入学号后检查缓存";
    return;
  }
  const data = await api(`/api/account/status?usernumber=${encodeURIComponent(usernumber)}`);
  els.cacheStatus.textContent = data.status || "";
  if (data.status === "无需输入") {
    els.password.value = "";
  }
}

function withErrorHandling(fn) {
  return async (event) => {
    event?.preventDefault();
    try {
      await fn(event);
    } catch (error) {
      showToast(error.message);
    }
  };
}

els.reservationForm.addEventListener(
  "submit",
  withErrorHandling(async () => {
    await mutate("/api/reservations", {
      usernumber: els.usernumber.value.trim(),
      password: els.password.value,
      seat_number: els.seatNumber.value.trim(),
      start_time: els.startTime.value,
      end_time: els.endTime.value,
    });
    els.seatNumber.value = "";
    els.password.value = "";
    await checkAccountStatus();
  })
);

els.usernumber.addEventListener(
  "input",
  withErrorHandling(async () => {
    els.password.value = "";
    await checkAccountStatus();
  })
);

els.clearReservations.addEventListener("click", withErrorHandling(() => mutate("/api/reservations", null, "DELETE")));
els.preheatBtn.addEventListener("click", withErrorHandling(() => mutate("/api/preheat")));
els.startBtn.addEventListener("click", withErrorHandling(() => mutate("/api/start")));
els.stopBtn.addEventListener("click", withErrorHandling(() => mutate("/api/stop")));
els.refreshState.addEventListener("click", withErrorHandling(refreshState));
els.refreshTemplates.addEventListener("click", withErrorHandling(refreshState));
els.refreshAccounts.addEventListener("click", withErrorHandling(refreshState));

els.saveTemplate.addEventListener(
  "click",
  withErrorHandling(() => mutate("/api/templates", { name: els.templateName.value.trim() }))
);
els.loadTemplate.addEventListener(
  "click",
  withErrorHandling(() => mutate("/api/templates/load", { name: els.templateSelect.value }))
);
els.deleteTemplate.addEventListener(
  "click",
  withErrorHandling(() => mutate("/api/templates/delete", { name: els.templateSelect.value }))
);

els.loadHistory.addEventListener(
  "click",
  withErrorHandling(() => mutate("/api/history/load", { label: els.historySelect.value }))
);
els.clearHistory.addEventListener("click", withErrorHandling(() => mutate("/api/history", null, "DELETE")));

els.recordForm.addEventListener(
  "submit",
  withErrorHandling(async () => {
    const data = await api("/api/records/query", {
      method: "POST",
      body: JSON.stringify({
        usernumber: els.recordUsernumber.value.trim(),
        password: els.recordPassword.value,
      }),
    });
    renderState(data);
    recordsCollapsed = false;
    renderRecords(data.records || []);
  })
);

els.cancelRecord.addEventListener(
  "click",
  withErrorHandling(async () => {
    const data = await api("/api/records/cancel", {
      method: "POST",
      body: JSON.stringify({
        usernumber: els.recordUsernumber.value.trim(),
        password: els.recordPassword.value,
        record_id: els.recordSelect.value,
      }),
    });
    renderState(data);
    recordsCollapsed = false;
    renderRecords(data.records || []);
  })
);

els.toggleRecordCards.addEventListener("click", () => {
  recordsCollapsed = !recordsCollapsed;
  renderRecords(lastRecords);
});

els.deleteAccount.addEventListener(
  "click",
  withErrorHandling(() => mutate("/api/accounts/delete", { usernumber: els.accountSelect.value }))
);
els.clearAccounts.addEventListener("click", withErrorHandling(() => mutate("/api/accounts", null, "DELETE")));

document.querySelectorAll(".nav a").forEach((link) => {
  link.addEventListener("click", () => {
    document.querySelectorAll(".nav a").forEach((item) => item.classList.remove("active"));
    link.classList.add("active");
  });
});

function ensurePolling() {
  window.clearTimeout(pollTimer);
  scheduleNextPoll();
}

function scheduleNextPoll(delay = null) {
  window.clearTimeout(pollTimer);
  const status = state?.runStatus || "idle";
  const nextDelay = delay ?? (isBusyStatus(status) ? 1200 : 8000);
  pollTimer = window.setTimeout(async () => {
    if (focusedOnEditable() && !isBusyStatus(state?.runStatus || "idle")) {
      scheduleNextPoll(1500);
      return;
    }
    try {
      await refreshState();
    } catch {
      scheduleNextPoll(5000);
    }
  }, nextDelay);
}

document.addEventListener("focusin", (event) => {
  if (isEditableElement(event.target)) {
    markUserEditing();
  }
});

document.addEventListener("input", (event) => {
  if (isEditableElement(event.target)) {
    markUserEditing();
  }
});

document.addEventListener("focusout", () => {
  window.clearTimeout(userEditingTimer);
  userEditingTimer = window.setTimeout(() => {
    userEditing = false;
    scheduleNextPoll(400);
  }, 250);
});

refreshState()
  .then(() => {
    renderRecords([]);
    ensurePolling();
  })
  .catch((error) => showToast(error.message));
