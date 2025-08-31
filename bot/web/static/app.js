let running = false;
let lastLogId = 0;

function getSelection() {
  const checks = Array.from(document.querySelectorAll('.mode-check'));
  return checks.filter(c => c.checked).map(c => c.value);
}

function updateControls() {
  const startBtn = document.getElementById('start');
  const sel = getSelection();
  // Disable only when not running and nothing selected (can't start)
  startBtn.disabled = !running && sel.length === 0;
  const label = document.getElementById('start-label');
  label.textContent = running ? 'Stop' : 'Start';
}

async function status() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    const el = document.getElementById('status');
    const startBtn = document.getElementById('start');
    startBtn.classList.remove('loading');
    running = !!data.running;
    if (!running) { el.textContent = 'Idle'; updateControls(); return; }
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

window.addEventListener('DOMContentLoaded', () => {
  document.getElementById('start').addEventListener('click', start);
  document.querySelectorAll('.mode-check').forEach(el => el.addEventListener('change', updateControls));
  updateControls();
  status();
  setInterval(status, 1500);
  fetchLogs();
  setInterval(fetchLogs, 1000);
});
