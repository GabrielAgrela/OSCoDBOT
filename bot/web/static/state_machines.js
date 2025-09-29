(() => {
  const svgNS = 'http://www.w3.org/2000/svg';

  const els = {
    list: document.getElementById('sm-list'),
    refresh: document.getElementById('sm-refresh'),
    create: document.getElementById('sm-new'),
    title: document.getElementById('sm-title'),
    status: document.getElementById('sm-status'),
    save: document.getElementById('sm-save'),
    del: document.getElementById('sm-delete'),
    form: document.getElementById('sm-meta'),
    key: document.getElementById('sm-key'),
    label: document.getElementById('sm-label'),
    type: document.getElementById('sm-type'),
    context: document.getElementById('sm-context'),
    loop: document.getElementById('sm-loop'),
    start: document.getElementById('sm-start'),
    category: document.getElementById('sm-category'),
    badge: document.getElementById('sm-badge'),
    description: document.getElementById('sm-description'),
    tags: document.getElementById('sm-tags'),
    graphEditor: document.getElementById('sm-graph-editor'),
    seqEditor: document.getElementById('sm-sequence-editor'),
    sequenceActions: document.getElementById('sequence-actions'),
    diagram: document.getElementById('diagram-canvas'),
    stepList: document.getElementById('step-list'),
    stepEditor: document.getElementById('step-editor'),
    stepTitle: document.getElementById('step-title'),
    stepName: document.getElementById('step-name'),
    stepSuccess: document.getElementById('step-success'),
    stepFailure: document.getElementById('step-failure'),
    stepActions: document.getElementById('step-actions'),
    stepApply: document.getElementById('step-apply'),
    stepDelete: document.getElementById('step-delete'),
    stepAdd: document.getElementById('step-add')
  };

  const state = {
    machines: [],
    current: null,
    currentKey: null,
    isNew: false,
    selectedStep: null,
    dragging: null,
    dirty: false
  };

  function fetchJSON(url, options = {}) {
    return fetch(url, Object.assign({
      headers: { 'Content-Type': 'application/json' }
    }, options)).then(res => {
      if (!res.ok) {
        return res.json().catch(() => ({})).then(data => {
          const err = new Error(data.error || res.statusText);
          err.status = res.status;
          throw err;
        });
      }
      const ct = res.headers.get('content-type') || '';
      if (ct.includes('application/json')) {
        return res.json();
      }
      return res.text();
    });
  }

  function showStatus(msg, type = 'info') {
    if (!els.status) return;
    els.status.textContent = msg || '';
    els.status.className = `status ${type}`;
    if (msg) {
      setTimeout(() => {
        if (els.status.textContent === msg) {
          els.status.textContent = '';
          els.status.className = 'status';
        }
      }, 4000);
    }
  }

  function loadList() {
    fetchJSON('/api/state-machines')
      .then(data => {
        state.machines = Array.isArray(data.items) ? data.items : [];
        renderList();
      })
      .catch(err => showStatus(`Failed to load list: ${err.message}`, 'err'));
  }

  function renderList() {
    els.list.innerHTML = '';
    if (state.machines.length === 0) {
      const li = document.createElement('li');
      li.textContent = 'No state machines yet.';
      li.className = 'empty';
      els.list.appendChild(li);
      return;
    }
    state.machines.forEach(item => {
      const li = document.createElement('li');
      li.className = 'sm-item';
      li.dataset.key = item.key;
      li.innerHTML = `
        <div class="sm-item-title">${escapeHtml(item.label || item.key)}</div>
        <div class="sm-item-meta">${escapeHtml(item.type || '')}${item.steps != null ? ` • ${item.steps} steps` : ''}</div>
      `;
      if (state.current && state.currentKey === item.key && !state.isNew) {
        li.classList.add('selected');
      }
      li.addEventListener('click', () => selectMachine(item.key));
      els.list.appendChild(li);
    });
  }

  function escapeHtml(str) {
    return String(str || '').replace(/[&<>"]/g, s => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[s]));
  }

  function selectMachine(key) {
    fetchJSON(`/api/state-machines/${encodeURIComponent(key)}`)
      .then(data => {
        state.current = normalizeMachine(data);
        state.currentKey = state.current.key;
        state.isNew = false;
        state.dirty = false;
        state.selectedStep = state.current.type === 'graph' && state.current.steps.length ? state.current.steps[0] : null;
        renderEditor();
        highlightSelection();
      })
      .catch(err => showStatus(`Failed to load state machine: ${err.message}`, 'err'));
  }

  function normalizeMachine(data) {
    const machine = Object.assign({
      key: '',
      label: '',
      type: 'graph',
      context: 'default',
      loop_sleep_s: 0.05,
      start: '',
      steps: [],
      actions: [],
      metadata: {}
    }, data || {});
    if (!machine.metadata || typeof machine.metadata !== 'object') {
      machine.metadata = {};
    }
    if (machine.type === 'graph') {
      if (!Array.isArray(machine.steps)) {
        machine.steps = [];
      }
      ensureLayouts(machine);
      if (!machine.start && machine.steps.length) {
        machine.start = machine.steps[0].name || '';
      }
    } else {
      if (!Array.isArray(machine.actions)) {
        machine.actions = [];
      }
    }
    return machine;
  }

  function ensureLayouts(machine) {
    const spacingX = 180;
    const spacingY = 120;
    machine.steps.forEach((step, idx) => {
      if (!step.layout || typeof step.layout.x !== 'number' || typeof step.layout.y !== 'number') {
        step.layout = { x: 80 + (idx % 4) * spacingX, y: 80 + Math.floor(idx / 4) * spacingY };
      }
      if (!Array.isArray(step.actions)) {
        step.actions = [];
      }
    });
  }

  function createNewMachine() {
    const template = normalizeMachine({
      key: '',
      label: 'New State Machine',
      type: 'graph',
      context: 'default',
      start: 'Step1',
      loop_sleep_s: 0.05,
      steps: [
        {
          name: 'Step1',
          actions: [],
          on_success: null,
          on_failure: null,
          layout: { x: 100, y: 120 }
        }
      ],
      metadata: {
        category: 'Custom',
        badge: '',
        description: '',
        tags: []
      }
    });
    state.current = template;
    state.currentKey = '';
    state.isNew = true;
    state.dirty = true;
    state.selectedStep = template.steps[0];
    renderEditor();
    highlightSelection();
    showStatus('New state machine created. Remember to set a unique key.', 'info');
  }

  function highlightSelection() {
    const items = els.list.querySelectorAll('.sm-item');
    items.forEach(li => {
      li.classList.toggle('selected', !state.isNew && state.current && li.dataset.key === state.current.key);
    });
  }

  function renderEditor() {
    const machine = state.current;
    if (!machine) {
      els.title.textContent = 'Select a state machine';
      els.save.disabled = true;
      els.del.disabled = true;
      els.form.reset();
      els.graphEditor.hidden = true;
      els.seqEditor.hidden = true;
      els.stepEditor.hidden = true;
      els.stepList.innerHTML = '';
      els.diagram.innerHTML = '<defs><marker id="arrow" markerWidth="10" markerHeight="6" refX="10" refY="3" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L10,3 L0,6 Z" class="diagram-arrow"></path></marker></defs>';
      return;
    }
    els.title.textContent = machine.label || machine.key || 'State Machine';
    els.save.disabled = false;
    els.del.disabled = state.isNew;
    els.key.value = machine.key || '';
    els.key.disabled = !state.isNew;
    els.label.value = machine.label || '';
    els.type.value = machine.type || 'graph';
    els.context.value = typeof machine.context === 'string' ? machine.context : JSON.stringify(machine.context);
    els.loop.value = typeof machine.loop_sleep_s === 'number' ? machine.loop_sleep_s : 0.05;

    const meta = machine.metadata || {};
    els.category.value = meta.category || '';
    els.badge.value = meta.badge || '';
    els.description.value = meta.description || '';
    const tags = Array.isArray(meta.tags) ? meta.tags.join(', ') : '';
    els.tags.value = tags;

    if (machine.type === 'graph') {
      populateStartOptions();
      toggleStartVisibility(true);
      els.graphEditor.hidden = false;
      els.seqEditor.hidden = true;
      renderStepList();
      renderDiagram();
      updateStepForm();
    } else {
      toggleStartVisibility(false);
      els.graphEditor.hidden = true;
      els.seqEditor.hidden = false;
      els.sequenceActions.value = JSON.stringify(machine.actions || [], null, 2);
    }
  }

  function toggleStartVisibility(show) {
    if (!els.start) return;
    const wrapper = els.start.closest('label');
    if (wrapper) {
      wrapper.style.display = show ? '' : 'none';
    }
  }

  function populateStartOptions() {
    const machine = state.current;
    if (!machine || machine.type !== 'graph') return;
    els.start.innerHTML = '';
    machine.steps.forEach(step => {
      const opt = document.createElement('option');
      opt.value = step.name || '';
      opt.textContent = step.name || '';
      els.start.appendChild(opt);
    });
    els.start.value = machine.start || (machine.steps[0] ? machine.steps[0].name : '');
  }

  function renderStepList() {
    const machine = state.current;
    els.stepList.innerHTML = '';
    if (!machine || machine.type !== 'graph') return;
    machine.steps.forEach(step => {
      const li = document.createElement('li');
      li.className = 'step-item';
      li.dataset.name = step.name;
      li.textContent = step.name;
      if (state.selectedStep && state.selectedStep.name === step.name) {
        li.classList.add('selected');
      }
      li.addEventListener('click', () => {
        state.selectedStep = step;
        updateStepForm();
        renderStepList();
      });
      els.stepList.appendChild(li);
    });
  }

  function updateStepForm() {
    const machine = state.current;
    if (!machine || machine.type !== 'graph' || !state.selectedStep) {
      els.stepEditor.hidden = true;
      return;
    }
    const step = state.selectedStep;
    els.stepEditor.hidden = false;
    els.stepTitle.textContent = step.name;
    els.stepName.value = step.name;
    populateTransitionSelect(els.stepSuccess, step.on_success);
    populateTransitionSelect(els.stepFailure, step.on_failure);
    els.stepActions.value = JSON.stringify(step.actions || [], null, 2);
  }

  function populateTransitionSelect(select, value) {
    const machine = state.current;
    select.innerHTML = '';
    const empty = document.createElement('option');
    empty.value = '';
    empty.textContent = '—';
    select.appendChild(empty);
    if (!machine || machine.type !== 'graph') return;
    machine.steps.forEach(step => {
      const opt = document.createElement('option');
      opt.value = step.name;
      opt.textContent = step.name;
      if (step.name === value) {
        opt.selected = true;
      }
      select.appendChild(opt);
    });
    if (!Array.from(select.options).some(opt => opt.value === (value || ''))) {
      select.value = '';
    }
  }

  function renderDiagram() {
    const machine = state.current;
    if (!machine || machine.type !== 'graph') return;
    const defs = els.diagram.querySelector('defs');
    els.diagram.innerHTML = '';
    if (defs) {
      els.diagram.appendChild(defs);
    } else {
      const d = document.createElementNS(svgNS, 'defs');
      const marker = document.createElementNS(svgNS, 'marker');
      marker.setAttribute('id', 'arrow');
      marker.setAttribute('markerWidth', '10');
      marker.setAttribute('markerHeight', '6');
      marker.setAttribute('refX', '10');
      marker.setAttribute('refY', '3');
      marker.setAttribute('orient', 'auto');
      marker.setAttribute('markerUnits', 'strokeWidth');
      const path = document.createElementNS(svgNS, 'path');
      path.setAttribute('d', 'M0,0 L10,3 L0,6 Z');
      path.setAttribute('class', 'diagram-arrow');
      marker.appendChild(path);
      d.appendChild(marker);
      els.diagram.appendChild(d);
    }

    machine.steps.forEach(step => {
      const group = document.createElementNS(svgNS, 'g');
      group.classList.add('diagram-node');
      group.dataset.name = step.name;
      if (state.selectedStep && state.selectedStep.name === step.name) {
        group.classList.add('selected');
      }
      const rect = document.createElementNS(svgNS, 'rect');
      rect.setAttribute('x', step.layout.x);
      rect.setAttribute('y', step.layout.y);
      rect.setAttribute('width', 140);
      rect.setAttribute('height', 60);
      const text = document.createElementNS(svgNS, 'text');
      text.setAttribute('x', step.layout.x + 70);
      text.setAttribute('y', step.layout.y + 35);
      text.setAttribute('text-anchor', 'middle');
      text.setAttribute('dominant-baseline', 'middle');
      text.textContent = step.name;
      group.appendChild(rect);
      group.appendChild(text);
      els.diagram.appendChild(group);
      attachDragHandlers(group, step);
      group.addEventListener('click', evt => {
        evt.preventDefault();
        evt.stopPropagation();
        state.selectedStep = step;
        updateStepForm();
        renderStepList();
        renderDiagram();
      });
    });
    renderConnections();
  }

  function renderConnections() {
    const machine = state.current;
    if (!machine || machine.type !== 'graph') return;
    machine.steps.forEach(step => {
      if (step.on_success) {
        drawLink(step, step.on_success, 'success');
      }
      if (step.on_failure) {
        drawLink(step, step.on_failure, 'failure');
      }
    });
  }

  function refreshConnections() {
    const links = Array.from(els.diagram.querySelectorAll('.diagram-link'));
    links.forEach(link => link.remove());
    renderConnections();
  }

  function findStep(name) {
    const machine = state.current;
    if (!machine || machine.type !== 'graph') return null;
    return machine.steps.find(step => step.name === name) || null;
  }

  function drawLink(fromStep, toName, kind) {
    const target = findStep(toName);
    if (!target) return;
    const group = document.createElementNS(svgNS, 'path');
    group.setAttribute('class', `diagram-link ${kind}`);
    const startX = fromStep.layout.x + 140 / 2;
    const startY = fromStep.layout.y + 60 / 2;
    const endX = target.layout.x + 140 / 2;
    const endY = target.layout.y + 60 / 2;
    const dx = endX - startX;
    const dy = endY - startY;
    const midX = startX + dx / 2;
    const midY = startY + dy / 2 - 40;
    const d = `M ${startX} ${startY} Q ${midX} ${midY} ${endX} ${endY}`;
    group.setAttribute('d', d);
    group.setAttribute('marker-end', 'url(#arrow)');
    els.diagram.appendChild(group);
  }

  function attachDragHandlers(group, step) {
    const rect = group.querySelector('rect');
    if (!rect) return;
    rect.style.cursor = 'move';
    group.addEventListener('pointerdown', evt => {
      evt.preventDefault();
      const svgRect = els.diagram.getBoundingClientRect();
      const offsetX = evt.clientX - svgRect.left - step.layout.x;
      const offsetY = evt.clientY - svgRect.top - step.layout.y;
      state.dragging = { step, offsetX, offsetY };
      group.setPointerCapture(evt.pointerId);
    });
    group.addEventListener('pointermove', evt => {
      if (!state.dragging || state.dragging.step !== step) return;
      const svgRect = els.diagram.getBoundingClientRect();
      const newX = evt.clientX - svgRect.left - state.dragging.offsetX;
      const newY = evt.clientY - svgRect.top - state.dragging.offsetY;
      step.layout.x = Math.max(10, Math.min(900, newX));
      step.layout.y = Math.max(10, Math.min(560, newY));
      rect.setAttribute('x', step.layout.x);
      rect.setAttribute('y', step.layout.y);
      const text = group.querySelector('text');
      if (text) {
        text.setAttribute('x', step.layout.x + 70);
        text.setAttribute('y', step.layout.y + 35);
      }
      state.dirty = true;
      refreshConnections();
    });
    group.addEventListener('pointerup', evt => {
      if (state.dragging && state.dragging.step === step) {
        state.dragging = null;
        group.releasePointerCapture(evt.pointerId);
      }
    });
    group.addEventListener('pointerleave', evt => {
      if (state.dragging && state.dragging.step === step && evt.buttons === 0) {
        state.dragging = null;
      }
    });
  }

  function applyStepChanges() {
    if (!state.current || state.current.type !== 'graph' || !state.selectedStep) return;
    const step = state.selectedStep;
    const newName = els.stepName.value.trim();
    if (!newName) {
      showStatus('Step name cannot be empty.', 'err');
      return;
    }
    const machine = state.current;
    if (newName !== step.name) {
      if (machine.steps.some(s => s !== step && s.name === newName)) {
        showStatus('Another step already has that name.', 'err');
        return;
      }
      // Update references
      machine.steps.forEach(s => {
        if (s.on_success === step.name) s.on_success = newName;
        if (s.on_failure === step.name) s.on_failure = newName;
      });
      if (machine.start === step.name) {
        machine.start = newName;
      }
      step.name = newName;
    }
    step.on_success = els.stepSuccess.value || null;
    step.on_failure = els.stepFailure.value || null;
    try {
      const parsed = JSON.parse(els.stepActions.value || '[]');
      if (!Array.isArray(parsed)) throw new Error('Actions must be an array');
      step.actions = parsed;
    } catch (err) {
      showStatus(`Invalid actions JSON: ${err.message}`, 'err');
      return;
    }
    state.dirty = true;
    renderStepList();
    renderDiagram();
    populateStartOptions();
    updateStepForm();
    showStatus('Step updated.', 'info');
  }

  function addStep() {
    if (!state.current || state.current.type !== 'graph') return;
    const base = 'Step';
    let idx = state.current.steps.length + 1;
    let name = `${base}${idx}`;
    while (state.current.steps.some(s => s.name === name)) {
      idx += 1;
      name = `${base}${idx}`;
    }
    const step = {
      name,
      actions: [],
      on_success: null,
      on_failure: null,
      layout: { x: 120, y: 120 }
    };
    state.current.steps.push(step);
    state.selectedStep = step;
    ensureLayouts(state.current);
    state.dirty = true;
    renderEditor();
    showStatus('Step added.', 'info');
  }

  function deleteStep() {
    if (!state.current || state.current.type !== 'graph' || !state.selectedStep) return;
    if (state.current.steps.length <= 1) {
      showStatus('A graph must have at least one step.', 'err');
      return;
    }
    const name = state.selectedStep.name;
    state.current.steps = state.current.steps.filter(s => s !== state.selectedStep);
    state.current.steps.forEach(s => {
      if (s.on_success === name) s.on_success = null;
      if (s.on_failure === name) s.on_failure = null;
    });
    if (state.current.start === name) {
      state.current.start = state.current.steps[0] ? state.current.steps[0].name : '';
    }
    state.selectedStep = state.current.steps[0] || null;
    state.dirty = true;
    renderEditor();
    showStatus('Step deleted.', 'info');
  }

  function updateMetaFromForm() {
    if (!state.current) return;
    const meta = state.current.metadata || {};
    meta.category = els.category.value.trim();
    meta.badge = els.badge.value.trim();
    meta.description = els.description.value.trim();
    meta.tags = els.tags.value.split(',').map(t => t.trim()).filter(Boolean);
    state.current.metadata = meta;
    state.current.label = els.label.value.trim();
    state.current.context = els.context.value.trim() || 'default';
    state.current.loop_sleep_s = parseFloat(els.loop.value) || 0.0;
    if (state.current.type === 'graph') {
      state.current.start = els.start.value || (state.current.steps[0] ? state.current.steps[0].name : '');
    } else {
      try {
        const parsed = JSON.parse(els.sequenceActions.value || '[]');
        if (Array.isArray(parsed)) {
          state.current.actions = parsed;
        }
      } catch (err) {
        showStatus(`Invalid sequence JSON: ${err.message}`, 'err');
      }
    }
  }

  function saveCurrent() {
    if (!state.current) return;
    const key = (els.key.value || '').trim();
    if (!key) {
      showStatus('Key is required.', 'err');
      els.key.focus();
      return;
    }
    updateMetaFromForm();
    state.current.key = key;
    const payload = JSON.parse(JSON.stringify(state.current));
    const method = state.isNew ? 'POST' : 'PUT';
    const url = state.isNew ? '/api/state-machines' : `/api/state-machines/${encodeURIComponent(key)}`;
    fetchJSON(url, {
      method,
      body: JSON.stringify(payload)
    })
      .then(() => {
        showStatus('State machine saved.', 'info');
        state.isNew = false;
        state.dirty = false;
        state.currentKey = key;
        loadList();
      })
      .catch(err => showStatus(`Save failed: ${err.message}`, 'err'));
  }

  function deleteCurrent() {
    if (!state.current || state.isNew) return;
    const key = state.current.key;
    if (!confirm(`Delete state machine "${key}"?`)) return;
    fetchJSON(`/api/state-machines/${encodeURIComponent(key)}`, { method: 'DELETE' })
      .then(() => {
        showStatus('State machine deleted.', 'info');
        state.current = null;
        state.currentKey = null;
        state.selectedStep = null;
        renderEditor();
        loadList();
      })
      .catch(err => showStatus(`Delete failed: ${err.message}`, 'err'));
  }

  function handleMetaChange() {
    if (!state.current) return;
    state.dirty = true;
    updateMetaFromForm();
    if (state.current.type === 'graph') {
      renderDiagram();
      renderStepList();
    }
  }

  function handleTypeChange() {
    if (!state.current) return;
    const newType = els.type.value;
    if (state.current.type === newType) return;
    state.current.type = newType;
    if (newType === 'graph') {
      state.current.steps = state.current.steps && state.current.steps.length ? state.current.steps : [
        { name: 'Step1', actions: [], on_success: null, on_failure: null, layout: { x: 100, y: 120 } }
      ];
      ensureLayouts(state.current);
      state.current.start = state.current.steps[0].name;
    } else {
      state.current.actions = state.current.actions || [];
    }
    state.selectedStep = newType === 'graph' ? state.current.steps[0] : null;
    state.dirty = true;
    renderEditor();
  }

  function initEvents() {
    els.refresh.addEventListener('click', () => {
      loadList();
      showStatus('Refreshed state list.', 'info');
    });
    els.create.addEventListener('click', createNewMachine);
    els.save.addEventListener('click', saveCurrent);
    els.del.addEventListener('click', deleteCurrent);
    els.form.addEventListener('input', handleMetaChange);
    els.form.addEventListener('change', handleMetaChange);
    els.type.addEventListener('change', handleTypeChange);
    els.start.addEventListener('change', handleMetaChange);
    els.sequenceActions.addEventListener('change', handleMetaChange);
    els.stepApply.addEventListener('click', applyStepChanges);
    els.stepDelete.addEventListener('click', deleteStep);
    els.stepAdd.addEventListener('click', addStep);
  }

  function init() {
    if (!els.list) return;
    initEvents();
    loadList();
  }

  document.addEventListener('DOMContentLoaded', init);
})();
