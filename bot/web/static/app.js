function getSelection() {
  const checks = Array.from(document.querySelectorAll('.mode-check'));
  return checks.filter(c => c.checked).map(c => c.value);
}

function updateControls() {
  const startBtn = document.getElementById('start');
  const sel = getSelection();
  startBtn.disabled = sel.length === 0;
}

async function status() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    const el = document.getElementById('status');
    const startBtn = document.getElementById('start');
    startBtn.classList.remove('loading');
    if (!data.running) { el.textContent = 'Idle'; return; }
    if (data.kind !== 'single') {
      el.textContent = `Alternating: ${data.modes.join(' -> ')}`;
    } else {
      el.textContent = `${data.modes[0]} running...`;
    }
  } catch (e) {
    // ignore
  }
}

async function start() {
  const startBtn = document.getElementById('start');
  const selection = getSelection();
  startBtn.classList.add('loading');
  try {
    const res = await fetch('/api/start', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ selection })
    });
    if (!res.ok) { alert('Failed to start'); }
  } catch (e) {
    alert('Failed to start');
  } finally {
    await status();
  }
}

async function stop() {
  try { await fetch('/api/stop', { method: 'POST' }); } catch (e) {}
  await status();
}

window.addEventListener('DOMContentLoaded', () => {
  document.getElementById('start').addEventListener('click', start);
  document.getElementById('stop').addEventListener('click', stop);
  document.querySelectorAll('.mode-check').forEach(el => el.addEventListener('change', updateControls));
  updateControls();
  status();
  setInterval(status, 1500);
});
