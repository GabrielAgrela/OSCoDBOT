async function status() {
  const res = await fetch('/api/status');
  const data = await res.json();
  const el = document.getElementById('status');
  if (!data.running) { el.textContent = 'Idle'; return; }
  if (data.kind === 'combo') {
    el.textContent = `Alternating: ${data.modes.join(' -> ')}`;
  } else {
    el.textContent = `${data.modes[0]} running...`;
  }
}

async function start() {
  const checks = Array.from(document.querySelectorAll('.mode-check'));
  const selection = checks.filter(c => c.checked).map(c => c.value);
  const res = await fetch('/api/start', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ selection })
  });
  if (!res.ok) { alert('Failed to start'); return; }
  await status();
}

async function stop() {
  await fetch('/api/stop', { method: 'POST' });
  await status();
}

window.addEventListener('DOMContentLoaded', () => {
  document.getElementById('start').addEventListener('click', start);
  document.getElementById('stop').addEventListener('click', stop);
  status();
  setInterval(status, 1500);
});

