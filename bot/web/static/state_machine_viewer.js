(() => {
  const svgNS = 'http://www.w3.org/2000/svg';
  const root = document.getElementById('machine-viewer');
  if (!root) return;

  const els = {
    title: document.getElementById('machine-viewer-title'),
    status: document.getElementById('machine-viewer-status'),
    canvas: document.getElementById('machine-viewer-canvas'),
    empty: document.getElementById('machine-viewer-empty'),
  };

  const state = {
    selection: [],
    running: false,
    runningKind: 'single',
    runningModes: [],
    machineKey: null,
    machineLabel: '',
    machine: null,
    previewReason: 'none',
    loading: false,
    error: '',
    activeStep: '',
  };

  const NODE_WIDTH = 140;
  const NODE_HEIGHT = 60;
  const VIEW_PADDING = 120;

  function titleFromKey(key) {
    if (!key) return 'State Machine Preview';
    return key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  }

  function layoutStorageKey(key) {
    return `sm-layout:${key}`;
  }

  function applyStoredLayout(machine) {
    if (!machine || !machine.key) return;
    let payload = null;
    try {
      const raw = localStorage.getItem(layoutStorageKey(machine.key));
      if (raw) {
        payload = JSON.parse(raw);
      }
    } catch (err) {
      payload = null;
    }
    if (!payload) return;
    machine.steps.forEach(step => {
      const coords = payload[step.name];
      if (!coords) return;
      if (typeof coords.x === 'number' && typeof coords.y === 'number') {
        step.layout = { x: coords.x, y: coords.y };
      }
    });
  }

  function computeAutoLayout(machine) {
    const spacingX = 220;
    const spacingY = 140;
    const marginX = 80;
    const marginY = 80;
    const byName = new Map();
    machine.steps.forEach(step => {
      if (step && step.name) {
        byName.set(step.name, step);
      }
    });
    const levels = new Map();
    const queue = [];
    const visited = new Set();
    const startName = machine.start && byName.has(machine.start)
      ? machine.start
      : (machine.steps[0] ? machine.steps[0].name : null);
    if (startName) {
      queue.push({ name: startName, depth: 0 });
      visited.add(startName);
    }
    while (queue.length) {
      const current = queue.shift();
      const step = byName.get(current.name);
      if (!step) continue;
      if (!levels.has(current.depth)) {
        levels.set(current.depth, []);
      }
      levels.get(current.depth).push(step.name);
      [step.on_success, step.on_failure].forEach(target => {
        if (target && byName.has(target) && !visited.has(target)) {
          visited.add(target);
          queue.push({ name: target, depth: current.depth + 1 });
        }
      });
    }
    const remaining = machine.steps.filter(step => !visited.has(step.name));
    if (remaining.length) {
      let depth = levels.size;
      remaining.forEach(step => {
        levels.set(depth, [step.name]);
        depth += 1;
      });
    }
    const layout = new Map();
    Array.from(levels.keys()).sort((a, b) => a - b).forEach(level => {
      const items = levels.get(level) || [];
      items.forEach((name, idx) => {
        const x = marginX + idx * spacingX;
        const y = marginY + level * spacingY;
        layout.set(name, { x, y });
      });
    });
    return layout;
  }

  function ensureLayouts(machine) {
    if (!machine || machine.type !== 'graph' || !Array.isArray(machine.steps)) return;
    const invalid = machine.steps.some(step => !step.layout || typeof step.layout.x !== 'number' || typeof step.layout.y !== 'number');
    if (invalid) {
      const computed = computeAutoLayout(machine);
      machine.steps.forEach(step => {
        const coords = computed.get(step.name);
        if (coords) {
          step.layout = { x: coords.x, y: coords.y };
        } else if (!step.layout) {
          step.layout = { x: 100, y: 100 };
        }
      });
    } else {
      machine.steps.forEach(step => {
        if (!step.layout) {
          step.layout = { x: 100, y: 100 };
        }
      });
    }
  }

  function normalizeMachine(data, keyHint) {
    const machine = Object.assign({
      key: keyHint || '',
      label: '',
      type: 'graph',
      context: 'default',
      loop_sleep_s: 0.05,
      start: '',
      steps: [],
    }, data || {});
    if (!machine.key) {
      machine.key = keyHint || machine.key || '';
    }
    if (machine.type === 'graph') {
      if (!Array.isArray(machine.steps)) {
        machine.steps = [];
      }
      ensureLayouts(machine);
      applyStoredLayout(machine);
      if (!machine.start && machine.steps.length) {
        machine.start = machine.steps[0].name || '';
      }
    }
    return machine;
  }

  function computeDiagramBounds(machine) {
    if (!machine || machine.type !== 'graph' || !Array.isArray(machine.steps) || machine.steps.length === 0) {
      return null;
    }
    let minX = Number.POSITIVE_INFINITY;
    let minY = Number.POSITIVE_INFINITY;
    let maxX = Number.NEGATIVE_INFINITY;
    let maxY = Number.NEGATIVE_INFINITY;
    machine.steps.forEach(step => {
      if (!step || !step.layout) return;
      const x = typeof step.layout.x === 'number' ? step.layout.x : 0;
      const y = typeof step.layout.y === 'number' ? step.layout.y : 0;
      minX = Math.min(minX, x);
      minY = Math.min(minY, y);
      maxX = Math.max(maxX, x + NODE_WIDTH);
      maxY = Math.max(maxY, y + NODE_HEIGHT);
    });
    if (!Number.isFinite(minX) || !Number.isFinite(minY) || !Number.isFinite(maxX) || !Number.isFinite(maxY)) {
      return null;
    }
    return { minX, minY, maxX, maxY };
  }

  function computeViewBox(machine) {
    const bounds = computeDiagramBounds(machine);
    if (!bounds) {
      return { x: 0, y: 0, width: 960, height: 640 };
    }
    const rect = els.canvas ? els.canvas.getBoundingClientRect() : { width: 960, height: 640 };
    const width = Math.max(bounds.maxX - bounds.minX, 10);
    const height = Math.max(bounds.maxY - bounds.minY, 10);
    const paddedWidth = width + VIEW_PADDING * 2;
    const paddedHeight = height + VIEW_PADDING * 2;
    let viewWidth = paddedWidth;
    let viewHeight = paddedHeight;
    if (rect.width > 0 && rect.height > 0) {
      const aspect = rect.width / rect.height;
      const boundsAspect = paddedWidth / paddedHeight;
      if (boundsAspect < aspect) {
        viewWidth = paddedHeight * aspect;
        viewHeight = paddedHeight;
      } else {
        viewHeight = paddedWidth / aspect;
        viewWidth = paddedWidth;
      }
    }
    const centerX = (bounds.minX + bounds.maxX) / 2;
    const centerY = (bounds.minY + bounds.maxY) / 2;
    return {
      x: centerX - viewWidth / 2,
      y: centerY - viewHeight / 2,
      width: viewWidth,
      height: viewHeight,
    };
  }

  function createLayers(svg) {
    const links = document.createElementNS(svgNS, 'g');
    links.setAttribute('class', 'diagram-links');
    const nodes = document.createElementNS(svgNS, 'g');
    nodes.setAttribute('class', 'diagram-nodes');
    svg.appendChild(links);
    svg.appendChild(nodes);
    return { links, nodes };
  }

  function drawConnections(layer, machine) {
    if (!layer || !machine || machine.type !== 'graph') return;
    const buckets = new Map();
    const findStep = name => machine.steps.find(step => step.name === name) || null;
    const enqueue = (fromStep, toName, kind) => {
      const target = findStep(toName);
      if (!target) return;
      const key = `${fromStep.name}->${target.name}`;
      if (!buckets.has(key)) {
        buckets.set(key, []);
      }
      buckets.get(key).push({ fromStep, target, kind });
    };

    machine.steps.forEach(step => {
      if (step.on_success) {
        enqueue(step, step.on_success, 'success');
      }
      if (step.on_failure) {
        enqueue(step, step.on_failure, 'failure');
      }
    });

    buckets.forEach(entries => {
      const total = entries.length;
      entries.forEach((entry, index) => {
        drawLink(layer, entry.fromStep, entry.target, entry.kind, index, total);
      });
    });
  }

  function drawLink(layer, fromStep, target, kind, index = 0, total = 1) {
    if (!layer || !fromStep || !target) return;

    const line = document.createElementNS(svgNS, 'path');
    line.setAttribute('class', `diagram-link ${kind}`);

    const halfWidth = NODE_WIDTH / 2;
    const halfHeight = NODE_HEIGHT / 2;

    const fromCenter = {
      x: fromStep.layout.x + halfWidth,
      y: fromStep.layout.y + halfHeight,
    };
    const toCenter = {
      x: target.layout.x + halfWidth,
      y: target.layout.y + halfHeight,
    };

    const projectEdgePoint = (center, toward) => {
      const dx = toward.x - center.x;
      const dy = toward.y - center.y;
      if (Math.abs(dx) < 1e-6 && Math.abs(dy) < 1e-6) {
        return { x: center.x, y: center.y };
      }
      if (Math.abs(dx) < 1e-6) {
        return { x: center.x, y: center.y + (dy > 0 ? halfHeight : -halfHeight) };
      }
      if (Math.abs(dy) < 1e-6) {
        return { x: center.x + (dx > 0 ? halfWidth : -halfWidth), y: center.y };
      }
      const scale = Math.min(halfWidth / Math.abs(dx), halfHeight / Math.abs(dy));
      return {
        x: center.x + dx * scale,
        y: center.y + dy * scale,
      };
    };

    const baseStart = projectEdgePoint(fromCenter, toCenter);
    const baseEnd = projectEdgePoint(toCenter, fromCenter);

    const dx = baseEnd.x - baseStart.x;
    const dy = baseEnd.y - baseStart.y;
    const length = Math.hypot(dx, dy) || 1;
    const nx = dx / length;
    const ny = dy / length;
    const perpX = -ny;
    const perpY = nx;

    const offsetIndex = index - (total - 1) / 2;
    const offsetDistance = offsetIndex * 18;

    const startPoint = {
      x: baseStart.x + perpX * offsetDistance,
      y: baseStart.y + perpY * offsetDistance,
    };
    const endPoint = {
      x: baseEnd.x + perpX * offsetDistance,
      y: baseEnd.y + perpY * offsetDistance,
    };

    const curveMagnitude = Math.max(40, Math.min(140, length * 0.35)) + Math.abs(offsetDistance) * 0.4;
    const controlPoint = {
      x: (startPoint.x + endPoint.x) / 2 + perpX * curveMagnitude,
      y: (startPoint.y + endPoint.y) / 2 + perpY * curveMagnitude,
    };

    const d = `M ${startPoint.x} ${startPoint.y} Q ${controlPoint.x} ${controlPoint.y} ${endPoint.x} ${endPoint.y}`;
    line.setAttribute('d', d);

    const arrow = document.createElementNS(svgNS, 'path');
    arrow.setAttribute('class', `diagram-arrow ${kind}`);
    arrow.setAttribute('d', 'M 0 0 L -24 10 L -24 -10 Z');
    const angle = Math.atan2(ny, nx) * (180 / Math.PI);
    const arrowOffset = 2;
    const arrowX = endPoint.x + nx * arrowOffset;
    const arrowY = endPoint.y + ny * arrowOffset;
    arrow.setAttribute('transform', `translate(${arrowX} ${arrowY}) rotate(${angle})`);

    layer.appendChild(line);
    layer.appendChild(arrow);
  }

  function drawNodes(layer, machine) {
    if (!layer || !machine || machine.type !== 'graph') return;
    machine.steps.forEach(step => {
      const group = document.createElementNS(svgNS, 'g');
      group.setAttribute('class', 'diagram-node');
      group.dataset.name = step.name;
      if (machine.start === step.name) {
        group.classList.add('start');
      }
      if (state.activeStep && state.activeStep === step.name) {
        group.classList.add('active');
      }
      const rect = document.createElementNS(svgNS, 'rect');
      rect.setAttribute('x', step.layout.x);
      rect.setAttribute('y', step.layout.y);
      rect.setAttribute('width', NODE_WIDTH);
      rect.setAttribute('height', NODE_HEIGHT);
      const text = document.createElementNS(svgNS, 'text');
      text.setAttribute('x', step.layout.x + NODE_WIDTH / 2);
      text.setAttribute('y', step.layout.y + NODE_HEIGHT / 2);
      text.setAttribute('text-anchor', 'middle');
      text.setAttribute('dominant-baseline', 'middle');
      text.textContent = step.name;
      group.appendChild(rect);
      group.appendChild(text);
      layer.appendChild(group);
    });
  }

  function updateEmptyOverlay(hasGraph) {
    if (!els.empty) return;
    let message = '';
    if (state.loading) {
      message = 'Loading…';
    } else if (state.error) {
      message = state.error;
    } else if (!state.machineKey) {
      message = 'Select a mode to preview its flow.';
    } else if (!state.machine) {
      message = 'State machine not available.';
    } else if (state.machine.type !== 'graph') {
      message = 'Preview is only available for graph state machines.';
    } else if (!hasGraph) {
      message = 'State machine has no steps yet.';
    }
    els.empty.textContent = message;
    if (message) {
      els.empty.style.display = 'flex';
      root.classList.remove('has-graph');
    } else {
      els.empty.style.display = 'none';
      root.classList.add('has-graph');
    }
  }

  function render() {
    if (!els.canvas) return;
    while (els.canvas.firstChild) {
      els.canvas.removeChild(els.canvas.firstChild);
    }
    const hasGraph = !!(state.machine && state.machine.type === 'graph' && Array.isArray(state.machine.steps) && state.machine.steps.length);
    updateEmptyOverlay(hasGraph);
    if (!hasGraph || state.loading || state.error) {
      return;
    }
    const viewBox = computeViewBox(state.machine);
    els.canvas.setAttribute('viewBox', `${viewBox.x} ${viewBox.y} ${viewBox.width} ${viewBox.height}`);
    const layers = createLayers(els.canvas);
    drawConnections(layers.links, state.machine);
    drawNodes(layers.nodes, state.machine);
  }

  function updateHeader() {
    if (els.title) {
      const fallback = state.machineKey ? titleFromKey(state.machineKey) : 'State Machine Preview';
      const label = state.machineLabel && state.machineLabel.trim() ? state.machineLabel : fallback;
      els.title.textContent = label;
    }
    if (els.status) {
      let text = '';
      if (state.loading) {
        text = 'Loading…';
      } else if (state.error) {
        text = state.error;
      } else if (!state.machineKey) {
        text = 'Select a mode to preview its flow.';
      } else if (state.previewReason === 'running') {
        text = state.activeStep ? `Running — Active step: ${state.activeStep}` : 'Running…';
      } else if (state.previewReason === 'selection') {
        text = 'Previewing selected mode.';
      } else if (state.previewReason === 'fallback') {
        text = 'Multi-mode run — showing first mode.';
      } else {
        text = 'Preview unavailable.';
      }
      els.status.textContent = text;
    }
  }

  async function loadMachine(key) {
    state.loading = true;
    state.error = '';
    state.machine = null;
    state.machineLabel = titleFromKey(key);
    render();
    updateHeader();
    try {
      const res = await fetch(`/api/state-machines/${encodeURIComponent(key)}`);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.error || `Failed to load ${key}`);
      }
      const data = await res.json();
      const machine = normalizeMachine(data, key);
      state.machine = machine;
      state.machineLabel = machine.label && machine.label.trim() ? machine.label : titleFromKey(key);
      state.loading = false;
      state.error = '';
      render();
      updateHeader();
    } catch (err) {
      state.loading = false;
      state.machine = null;
      state.error = err && err.message ? err.message : 'Failed to load state machine.';
      render();
      updateHeader();
    }
  }

  function determinePreview() {
    if (state.running && state.runningKind === 'single' && state.runningModes.length === 1) {
      return { key: state.runningModes[0], reason: 'running' };
    }
    if (state.selection.length > 0) {
      return { key: state.selection[0], reason: 'selection' };
    }
    if (state.running && state.runningModes.length > 0) {
      return { key: state.runningModes[0], reason: 'fallback' };
    }
    return { key: null, reason: 'none' };
  }

  function updatePreviewTarget() {
    const { key, reason } = determinePreview();
    const changedKey = key !== state.machineKey;
    const changedReason = reason !== state.previewReason;
    state.machineKey = key;
    state.previewReason = reason;
    if (reason !== 'running') {
      setActiveStep('');
    }
    if (!key) {
      state.machine = null;
      state.machineLabel = '';
      state.loading = false;
      state.error = '';
      render();
      updateHeader();
      return;
    }
    if (changedKey) {
      loadMachine(key);
    } else {
      if (changedReason) {
        updateHeader();
      }
    }
  }

  function setActiveStep(name) {
    const normalized = typeof name === 'string' ? name.trim() : '';
    if (state.activeStep === normalized) return;
    state.activeStep = normalized;
    render();
    updateHeader();
  }

  function handleSelection(evt) {
    const detail = evt && evt.detail ? evt.detail : {};
    const selection = Array.isArray(detail.selection) ? detail.selection.filter(item => typeof item === 'string') : [];
    state.selection = selection;
    updatePreviewTarget();
  }

  function handleStatus(evt) {
    const detail = evt && evt.detail ? evt.detail : {};
    state.running = !!detail.running;
    state.runningKind = detail.kind || 'single';
    state.runningModes = Array.isArray(detail.modes) ? detail.modes.filter(item => typeof item === 'string') : [];
    if (!state.running || state.runningKind !== 'single') {
      setActiveStep('');
    }
    updatePreviewTarget();
  }

  function handleMetrics(evt) {
    const detail = evt && evt.detail ? evt.detail : {};
    if (!detail.running || !state.running || state.runningKind !== 'single') {
      setActiveStep('');
      return;
    }
    const metrics = detail.metrics || {};
    const step = (typeof metrics.current_step === 'string' && metrics.current_step)
      ? metrics.current_step
      : (typeof metrics.current_state === 'string' ? metrics.current_state : '');
    if (!step) {
      setActiveStep('');
      return;
    }
    if (state.previewReason !== 'running') {
      return;
    }
    setActiveStep(step);
  }

  document.addEventListener('bot-selection', handleSelection);
  document.addEventListener('bot-status', handleStatus);
  document.addEventListener('bot-metrics', handleMetrics);

  render();
  updateHeader();
})();
