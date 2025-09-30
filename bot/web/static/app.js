let running = false;
let paused = false;
let lastLogId = 0;
let metricsInflight = false;

// Persist selected modes across visits
const LS_SELECTED_KEY = 'modes.selected.v1';
const LS_COUNTERS_KEY = 'counters.v1';
const LS_SESSION_KEY = 'counters.session.v1';
const LS_VIEW_MODE_KEY = 'dashboard.viewMode.v1';

function saveSelectionLS(arr) {
  try {
    localStorage.setItem(LS_SELECTED_KEY, JSON.stringify(arr || []));
  } catch (e) {
    // ignore storage errors
  }
}

function loadSelectionLS() {
  try {
    const raw = localStorage.getItem(LS_SELECTED_KEY);
    const arr = JSON.parse(raw || '[]');
    return Array.isArray(arr) ? arr : [];
  } catch (e) {
    return [];
  }
}

function saveCountersLS(obj) {
  try {
    localStorage.setItem(LS_COUNTERS_KEY, JSON.stringify(obj || {}));
  } catch (e) {
    // ignore storage errors
  }
}

function loadCountersLS() {
  try {
    const raw = localStorage.getItem(LS_COUNTERS_KEY);
    const obj = JSON.parse(raw || '{}');
    return (obj && typeof obj === 'object') ? obj : {};
  } catch (e) {
    return {};
  }
}

// Session baseline helpers (since last Start)
function saveSessionBaseline(obj) {
  try {
    const payload = {
      troops_trained: parseInt(obj.troops_trained || 0, 10) || 0,
      nodes_farmed: parseInt(obj.nodes_farmed || 0, 10) || 0,
      alliance_helps: parseInt(obj.alliance_helps || 0, 10) || 0,
      ts: Date.now(),
    };
    localStorage.setItem(LS_SESSION_KEY, JSON.stringify(payload));
  } catch (e) {
    // ignore
  }
}

function loadSessionBaseline() {
  try {
    const raw = localStorage.getItem(LS_SESSION_KEY);
    if (!raw) return null;
    const obj = JSON.parse(raw);
    if (!obj || typeof obj !== 'object') return null;
    return {
      troops_trained: parseInt(obj.troops_trained || 0, 10) || 0,
      nodes_farmed: parseInt(obj.nodes_farmed || 0, 10) || 0,
      alliance_helps: parseInt(obj.alliance_helps || 0, 10) || 0,
      ts: parseInt(obj.ts || 0, 10) || 0,
    };
  } catch (e) {
    return null;
  }
}

function clearSessionBaseline() {
  try { localStorage.removeItem(LS_SESSION_KEY); } catch (e) { /* ignore */ }
}

function saveViewMode(mode) {
  try {
    const value = mode === 'screenshot' ? 'screenshot' : 'preview';
    localStorage.setItem(LS_VIEW_MODE_KEY, value);
  } catch (e) {
    // ignore
  }
}

function loadViewMode() {
  try {
    const stored = localStorage.getItem(LS_VIEW_MODE_KEY);
    return stored === 'screenshot' ? 'screenshot' : 'preview';
  } catch (e) {
    return 'preview';
  }
}

function applyViewMode(mode, notify = true) {
  const targetMode = mode === 'screenshot' ? 'screenshot' : 'preview';
  const shot = document.getElementById('shot-panel');
  const viewer = document.getElementById('machine-viewer');
  const toggle = document.getElementById('view-toggle');
  const showPreview = targetMode !== 'screenshot';
  if (shot) shot.classList.toggle('is-hidden', showPreview);
  if (viewer) viewer.classList.toggle('is-hidden', !showPreview);
  if (toggle) {
    toggle.textContent = showPreview ? 'Show Screenshot' : 'Show Machine Preview';
    toggle.setAttribute('aria-pressed', showPreview ? 'true' : 'false');
  }
  if (notify) {
    try {
      document.dispatchEvent(new CustomEvent('bot-view-mode', { detail: { mode: targetMode } }));
    } catch (e) {
      // ignore broadcast issues
    }
  }
}

function initViewToggle() {
  const btn = document.getElementById('view-toggle');
  if (!btn) return;
  let currentMode = loadViewMode();
  btn.addEventListener('click', () => {
    currentMode = currentMode === 'screenshot' ? 'preview' : 'screenshot';
    saveViewMode(currentMode);
    applyViewMode(currentMode);
  });
  // Ensure persisted state is applied on load
  applyViewMode(currentMode);
}

function broadcastSelection(selection) {
  try {
    const detail = { selection: Array.isArray(selection) ? selection.slice() : [] };
    document.dispatchEvent(new CustomEvent('bot-selection', { detail }));
  } catch (e) {
    // ignore broadcast failures
  }
}

function applySavedSelection() {
  const saved = new Set(loadSelectionLS());
  document.querySelectorAll('.mode-check').forEach(el => {
    el.checked = saved.has(el.value);
  });
  refreshModeCardStates();
  broadcastSelection(getSelection());
}

function applySavedCounters() {
  try {
    const ctr = document.getElementById('counters');
    if (!ctr) return;
    const c = loadCountersLS();
    const trained = parseInt(c.troops_trained || 0, 10) || 0;
    const farmed = parseInt(c.nodes_farmed || 0, 10) || 0;
    const helps = parseInt(c.alliance_helps || 0, 10) || 0;
    ctr.textContent = `Troops trained: ${trained} • Nodes farmed: ${farmed} • Helps: ${helps}`;
  } catch (e) {
    // ignore
  }
}

function refreshModeCardStates() {
  document.querySelectorAll('.mode-pill').forEach(pill => {
    const input = pill.querySelector('.mode-check');
    const active = !!(input && input.checked);
    pill.classList.toggle('selected', active);
    pill.setAttribute('aria-checked', active ? 'true' : 'false');
  });
}

function clearAllModes() {
  document.querySelectorAll('.mode-check').forEach(el => { el.checked = false; });
  onSelectionChange();
  refreshModeCardStates();
}

function initModeInteractions() {
  document.querySelectorAll('.mode-check').forEach(el => {
    el.addEventListener('change', () => {
      onSelectionChange();
      refreshModeCardStates();
    });
  });
  document.querySelectorAll('.mode-pill').forEach(pill => {
    pill.addEventListener('keydown', evt => {
      if (evt.key === 'Enter' || evt.key === ' ') {
        evt.preventDefault();
        const input = pill.querySelector('.mode-check');
        if (input) {
          input.checked = !input.checked;
          input.dispatchEvent(new Event('change', { bubbles: true }));
        }
      }
    });
  });
  const clearBtn = document.getElementById('mode-clear');
  if (clearBtn) clearBtn.addEventListener('click', clearAllModes);
}

function getSelection() {
  const checks = Array.from(document.querySelectorAll('.mode-check'));
  return checks.filter(c => c.checked).map(c => c.value);
}

function updateControls() {
  const startBtn = document.getElementById('start');
  const pauseBtn = document.getElementById('pause');
  const sel = getSelection();
  // Disable only when not running and nothing selected (can't start)
  startBtn.disabled = !running && sel.length === 0;
  const label = document.getElementById('start-label');
  label.textContent = running ? 'Stop' : 'Start';
  // Pause button only enabled when running
  pauseBtn.disabled = !running;
  const plabel = document.getElementById('pause-label');
  plabel.textContent = paused ? 'Resume' : 'Pause';
}

function onSelectionChange() {
  // Save selections whenever user toggles a mode
  const selection = getSelection();
  saveSelectionLS(selection);
  updateControls();
  broadcastSelection(selection);
}

async function status() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    try {
      document.dispatchEvent(new CustomEvent('bot-status', { detail: data }));
    } catch (err) {
      // ignore broadcast issues
    }
    const el = document.getElementById('status');
    const cdEl = document.getElementById('cooldown');
    const startBtn = document.getElementById('start');
    startBtn.classList.remove('loading');
    running = !!data.running;
    paused = !!data.paused;
    if (!running) {
      el.textContent = 'Idle';
      if (cdEl) cdEl.textContent = 'Cooldown: n/a';
      try { const sctr = document.getElementById('session-counters'); if (sctr) sctr.style.display = 'none'; } catch (e) {}
      updateControls();
      return;
    }
    if (paused) { el.textContent = 'Paused'; /* still show cooldown below if any */ }
    // Show cooldowns below window size
    const cds = data.cooldowns || {};
    const ents = Object.entries(cds).filter(([k,v]) => (v||0) > 0);
    if (cdEl) {
      const fmt = (sec) => {
        sec = Math.max(0, parseInt(sec, 10) || 0);
        const h = Math.floor(sec / 3600);
        const m = Math.floor((sec % 3600) / 60);
        const s = sec % 60;
        if (h > 0) return `${h}h ${m}m ${s}s`;
        if (m > 0) return `${m}m ${s}s`;
        return `${s}s`;
      };
      if (ents.length === 0) {
        cdEl.textContent = 'Cooldown: none';
      } else if (ents.length === 1) {
        const [k, v] = ents[0];
        cdEl.textContent = `Cooldown: ${k} ${fmt(v)} remaining`;
      } else {
        const parts = ents.map(([k, v]) => `${k} ${fmt(v)}`);
        cdEl.textContent = `Cooldowns: ${parts.join(', ')} remaining`;
      }
    }
    if (paused) { updateControls(); return; }
    if (data.kind !== 'single') {
      el.textContent = `Alternating: ${data.modes.join(' -> ')}`;
    } else {
      el.textContent = `${data.modes[0]} running...`;
    }
    updateControls();
  } catch (e) {
    // ignore
  }
}

function renderLogs(items) {
  if (!items || !items.length) return;
  const box = document.getElementById('log');
  const atBottom = Math.abs(box.scrollHeight - box.scrollTop - box.clientHeight) < 4;
  const frag = document.createDocumentFragment();
  for (const it of items) {
    const div = document.createElement('div');
    div.className = 'log-line ' + (it.level || 'info');
    const t = new Date((it.ts || 0) * 1000);
    const hh = String(t.getHours()).padStart(2,'0');
    const mm = String(t.getMinutes()).padStart(2,'0');
    const ss = String(t.getSeconds()).padStart(2,'0');
    div.textContent = `[${hh}:${mm}:${ss}] ${it.text}`;
    frag.appendChild(div);
    if (it.id && it.id > lastLogId) lastLogId = it.id;
  }
  box.appendChild(frag);
  // Trim overly long logs in DOM
  const maxLines = 300;
  while (box.childElementCount > maxLines) {
    box.removeChild(box.firstElementChild);
  }
  if (atBottom) box.scrollTop = box.scrollHeight;
}

async function fetchLogs() {
  try {
    const res = await fetch(`/api/logs?since=${lastLogId}`);
    if (!res.ok) return;
    const data = await res.json();
    renderLogs(data.logs || []);
  } catch (e) {
    // ignore
  }
}

async function start() {
  const startBtn = document.getElementById('start');
  const selection = getSelection();
  startBtn.classList.add('loading');
  try {
    if (running) {
      // Toggle to stop
      await fetch('/api/stop', { method: 'POST' });
    } else {
      // Capture a session baseline before starting
      try {
        const c = loadCountersLS();
        saveSessionBaseline({
          troops_trained: c.troops_trained || 0,
          nodes_farmed: c.nodes_farmed || 0,
          alliance_helps: c.alliance_helps || 0,
        });
        const sctr = document.getElementById('session-counters');
        if (sctr) { sctr.textContent = 'Since start: Troops +0 | Nodes +0 | Helps +0'; sctr.style.display = ''; }
      } catch (e) { /* ignore */ }
      // Start with current selection
      const res = await fetch('/api/start', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ selection })
      });
      if (!res.ok) { alert('Failed to start'); }
    }
  } catch (e) {
    // Show a generic error depending on current toggle attempt
    alert(running ? 'Failed to stop' : 'Failed to start');
  } finally {
    await status();
    await metrics();
  }
}

async function togglePause() {
  const pauseBtn = document.getElementById('pause');
  if (!running) return;
  try {
    const url = paused ? '/api/resume' : '/api/pause';
    const res = await fetch(url, { method: 'POST' });
    if (!res.ok) {
      alert(paused ? 'Failed to resume' : 'Failed to pause');
    }
  } catch (e) {
    alert(paused ? 'Failed to resume' : 'Failed to pause');
  } finally {
    await status();
    await metrics();
  }
}

window.addEventListener('DOMContentLoaded', () => {
  document.getElementById('start').addEventListener('click', start);
  document.getElementById('pause').addEventListener('click', togglePause);
  const stopCloseBtn = document.getElementById('stop-close');
  if (stopCloseBtn) stopCloseBtn.addEventListener('click', stopAndCloseGame);
  const quitBtn = document.getElementById('quit');
  if (quitBtn) quitBtn.addEventListener('click', quitApp);
  const settingsBtn = document.getElementById('settings-toggle');
  if (settingsBtn) settingsBtn.addEventListener('click', toggleSettings);
  const saveBtn = document.getElementById('save-settings');
  if (saveBtn) saveBtn.addEventListener('click', saveSettings);
  initModeInteractions();
  initViewToggle();
  applySavedSelection();
  // Show saved counters immediately before first metrics fetch
  applySavedCounters();
  updateControls();
  status();
  setInterval(status, 1500);
  // Periodically fetch metrics to show window dimensions
  metrics();
  setInterval(metrics, 500);
  fetchLogs();
  setInterval(fetchLogs, 1000);
  // Refresh debug screenshot
  refreshShot();
  setInterval(refreshShot, 500);
  // Load settings
  loadSettings();
});

async function metrics() {
  if (metricsInflight) return;
  metricsInflight = true;
  try {
    const res = await fetch('/api/metrics');
    if (!res.ok) return;
    const data = await res.json();
    try {
      document.dispatchEvent(new CustomEvent('bot-metrics', { detail: data }));
    } catch (err) {
      // ignore broadcast issues
    }
    const el = document.getElementById('window-dims');
    const ctr = document.getElementById('counters');
    if (!el) return;
    if (!data.running) { el.textContent = 'Window: n/a'; try { const sctr = document.getElementById('session-counters'); if (sctr) sctr.style.display = 'none'; } catch (e) {} return; }
    const win = data.metrics && data.metrics.window;
    if (win && win.width > 0 && win.height > 0) {
      el.textContent = `Window: ${win.width}x${win.height}`;
    } else {
      el.textContent = 'Window: n/a';
    }
    // Update counters
    try {
      const c = (data.metrics && data.metrics.counters) || {};
      if (ctr) {
        const trained = parseInt(c.troops_trained || 0, 10) || 0;
        const farmed = parseInt(c.nodes_farmed || 0, 10) || 0;
        const helps = parseInt(c.alliance_helps || 0, 10) || 0;
        ctr.textContent = `Troops trained: ${trained} • Nodes farmed: ${farmed} • Helps: ${helps}`;
        // Persist to localStorage so values survive reruns and refreshes
        saveCountersLS({ troops_trained: trained, nodes_farmed: farmed, alliance_helps: helps });
        // Update session delta since start, if baseline exists
        try {
          const sctr = document.getElementById('session-counters');
          const base = loadSessionBaseline();
          if (sctr && base) {
            const dt = Math.max(0, trained - (base.troops_trained || 0));
            const df = Math.max(0, farmed - (base.nodes_farmed || 0));
            const dh = Math.max(0, helps - (base.alliance_helps || 0));
            sctr.textContent = `Since start: Troops +${dt} | Nodes +${df} | Helps +${dh}`;
            sctr.style.display = '';
          } else if (sctr) {
            sctr.style.display = 'none';
          }
        } catch (e) { /* ignore */ }
      }
    } catch (e) {
      // ignore UI update errors
    }
  } catch (e) {
    // ignore
  } finally {
    metricsInflight = false;
  }
}

async function stopAndCloseGame() {
  let proceed = true;
  try {
    proceed = confirm('Stop the bot and close Call of Dragons?');
  } catch (e) {
    proceed = true;
  }
  if (!proceed) return;
  const btn = document.getElementById('stop-close');
  if (btn) btn.disabled = true;
  try {
    const res = await fetch('/api/close-game', { method: 'POST' });
    let body = null;
    try { body = await res.json(); } catch (err) { body = null; }
    if (!res.ok) {
      alert('Failed to stop and close the game');
    } else if (!body || body.ok !== true) {
      const msg = body && body.error ? String(body.error) : 'Failed to stop and close the game';
      alert(msg);
    } else {
      if (body.forced) {
        console.warn('Force-terminated Call of Dragons process.');
      }
      if (body.missing) {
        console.info('Call of Dragons window was not found; nothing to close.');
      }
    }
  } catch (err) {
    alert('Failed to stop and close the game');
  } finally {
    if (btn) btn.disabled = false;
    try { await status(); } catch (err) { /* ignore */ }
    try { await metrics(); } catch (err) { /* ignore */ }
  }
}


async function quitApp() {
  try {
    // Optional confirmation to avoid accidental closes
    const ok = confirm('Close the bot?');
    if (!ok) return;
  } catch (e) {
    // ignore if confirm not available
  }
  try {
    await fetch('/api/quit', { method: 'POST' });
  } catch (e) {
    // ignore; process will terminate shortly anyway
  }
}

async function refreshShot() {
  try {
    const img = document.getElementById('shot-img');
    const empty = document.getElementById('shot-empty');
    if (!img || !empty) return;
    const res = await fetch('/shots/latest', { cache: 'no-store' });
    if (!res.ok) {
      if (img.dataset.url) {
        try { URL.revokeObjectURL(img.dataset.url); } catch (e) { /* ignore */ }
        delete img.dataset.url;
      }
      img.style.display = 'none';
      empty.style.display = 'block';
      return;
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    if (img.dataset.url) {
      try { URL.revokeObjectURL(img.dataset.url); } catch (e) { /* ignore */ }
    }
    img.src = url;
    img.dataset.url = url;
    img.style.display = 'block';
    empty.style.display = 'none';
  } catch (e) {
    // ignore
  }
}

function toggleSettings() {
  try {
    const pnl = document.getElementById('settings-panel');
    if (!pnl) return;
    pnl.style.display = (pnl.style.display === 'none' || !pnl.style.display) ? 'block' : 'none';
  } catch (e) {}
}

async function loadSettings() {
  try {
    const res = await fetch('/api/settings');
    if (!res.ok) return;
    const data = await res.json();
    const items = Array.isArray(data.settings) ? data.settings : [];
    renderSettings(items);
  } catch (e) { /* ignore */ }
}

function renderSettings(items) {
  const form = document.getElementById('settings-form');
  if (!form) return;
  form.innerHTML = '';
  if (!Array.isArray(items) || items.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'settings-empty';
    empty.textContent = 'No configurable settings available.';
    form.appendChild(empty);
    return;
  }
  const groups = [];
  const seen = new Map();
  for (const item of items) {
    const category = String(item.category || 'General');
    if (!seen.has(category)) {
      const arr = [];
      groups.push({ category, items: arr });
      seen.set(category, arr);
    }
    seen.get(category).push(item);
  }
  for (const group of groups) {
    const groupEl = document.createElement('div');
    groupEl.className = 'settings-group';
    const title = document.createElement('div');
    title.className = 'settings-group-title';
    title.textContent = group.category;
    groupEl.appendChild(title);
    for (const entry of group.items) {
      const key = String(entry.key || '').trim();
      if (!key) continue;
      const type = String(entry.type || 'string').toLowerCase();
      const labelText = entry.label ? String(entry.label) : key;
      const description = entry.description ? String(entry.description) : '';
      const inputId = `setting_${key}`;
      const itemEl = document.createElement('div');
      itemEl.className = 'settings-item';

      if (type === 'bool') {
        const checkboxWrap = document.createElement('label');
        checkboxWrap.className = 'settings-item-checkbox';
        checkboxWrap.setAttribute('for', inputId);
        const input = document.createElement('input');
        input.type = 'checkbox';
        input.id = inputId;
        input.dataset.settingKey = key;
        input.dataset.settingType = 'bool';
        input.checked = !!entry.value;
        checkboxWrap.appendChild(input);
        const text = document.createElement('span');
        text.textContent = labelText;
        checkboxWrap.appendChild(text);
        itemEl.appendChild(checkboxWrap);
        if (description) {
          const desc = document.createElement('div');
          desc.className = 'settings-item-desc';
          desc.textContent = description;
          itemEl.appendChild(desc);
        }
      } else {
        const label = document.createElement('label');
        label.className = 'settings-item-label';
        label.setAttribute('for', inputId);
        label.textContent = labelText;
        itemEl.appendChild(label);
        const input = document.createElement('input');
        input.id = inputId;
        input.className = 'settings-input';
        input.dataset.settingKey = key;
        input.dataset.settingType = type;
        input.autocomplete = 'off';
        input.spellcheck = false;
        let inputType = 'text';
        if (type === 'int' || type === 'float' || type === 'number') {
          inputType = 'number';
          if (type === 'int' && !input.hasAttribute('step')) {
            input.step = entry.step !== undefined ? String(entry.step) : '1';
          } else if (entry.step !== undefined) {
            input.step = String(entry.step);
          }
          if (entry.min !== undefined) input.min = String(entry.min);
          if (entry.max !== undefined) input.max = String(entry.max);
        }
        input.type = inputType;
        if (entry.placeholder) {
          input.placeholder = String(entry.placeholder);
        } else if (entry.default !== undefined && entry.default !== null) {
          input.placeholder = String(entry.default);
        }
        const value = entry.value;
        if (value !== undefined && value !== null) {
          input.value = String(value);
        } else {
          input.value = '';
        }
        if (description) {
          input.title = description;
        }
        itemEl.appendChild(input);
        if (description) {
          const desc = document.createElement('div');
          desc.className = 'settings-item-desc';
          desc.textContent = description;
          itemEl.appendChild(desc);
        }
      }
      groupEl.appendChild(itemEl);
    }
    form.appendChild(groupEl);
  }
}

async function saveSettings() {
  try {
    const form = document.getElementById('settings-form');
    if (!form) return;
    const payload = {};
    for (const el of form.querySelectorAll('[data-setting-key]')) {
      const key = el.dataset.settingKey;
      if (!key) continue;
      const type = (el.dataset.settingType || '').toLowerCase();
      if (type === 'bool') {
        payload[key] = !!el.checked;
      } else {
        payload[key] = el.value;
      }
    }
    const res = await fetch('/api/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    if (!res.ok) { alert('Failed to save settings'); return; }
    const j = await res.json();
    if (!j.ok) { alert('Failed to save settings'); return; }
    try { await status(); } catch (e) {}
    if (j.reloaded) {
      alert('Saved and applied.');
    } else {
      alert('Saved.');
    }
    try { await loadSettings(); } catch (e) {}
  } catch (e) { alert('Failed to save settings'); }
}

