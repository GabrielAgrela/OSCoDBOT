let running = false;
let paused = false;
let lastLogId = 0;

// Persist selected modes across visits
const LS_SELECTED_KEY = 'modes.selected.v1';
const LS_COUNTERS_KEY = 'counters.v1';

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

function applySavedSelection() {
  const saved = new Set(loadSelectionLS());
  document.querySelectorAll('.mode-check').forEach(el => {
    el.checked = saved.has(el.value);
  });
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
  saveSelectionLS(getSelection());
  updateControls();
}

async function status() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    const el = document.getElementById('status');
    const cdEl = document.getElementById('cooldown');
    const startBtn = document.getElementById('start');
    startBtn.classList.remove('loading');
    running = !!data.running;
    paused = !!data.paused;
    if (!running) { el.textContent = 'Idle'; if (cdEl) cdEl.textContent = 'Cooldown: n/a'; updateControls(); return; }
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
  }
}

window.addEventListener('DOMContentLoaded', () => {
  document.getElementById('start').addEventListener('click', start);
  document.getElementById('pause').addEventListener('click', togglePause);
  const quitBtn = document.getElementById('quit');
  if (quitBtn) quitBtn.addEventListener('click', quitApp);
  // Restore saved selection and wire up change handler to persist
  applySavedSelection();
  // Show saved counters immediately before first metrics fetch
  applySavedCounters();
  document.querySelectorAll('.mode-check').forEach(el => el.addEventListener('change', onSelectionChange));
  updateControls();
  status();
  setInterval(status, 1500);
  // Periodically fetch metrics to show window dimensions
  metrics();
  setInterval(metrics, 1500);
  fetchLogs();
  setInterval(fetchLogs, 1000);
  // Refresh debug screenshot
  refreshShot();
  setInterval(refreshShot, 500);
});

async function metrics() {
  try {
    const res = await fetch('/api/metrics');
    if (!res.ok) return;
    const data = await res.json();
    const el = document.getElementById('window-dims');
    const ctr = document.getElementById('counters');
    if (!el) return;
    if (!data.running) { el.textContent = 'Window: n/a'; return; }
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
      }
    } catch (e) {
      // ignore UI update errors
    }
  } catch (e) {
    // ignore
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
