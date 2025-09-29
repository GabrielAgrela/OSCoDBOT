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
    sequenceActionList: document.getElementById('sequence-action-list'),
    sequenceAdd: document.getElementById('sequence-add'),
    sequenceToggleJson: document.getElementById('sequence-toggle-json'),
    sequenceActionsJson: document.getElementById('sequence-actions-json'),
    diagram: document.getElementById('diagram-canvas'),
    stepList: document.getElementById('step-list'),
    stepEditor: document.getElementById('step-editor'),
    stepTitle: document.getElementById('step-title'),
    stepName: document.getElementById('step-name'),
    stepSuccess: document.getElementById('step-success'),
    stepFailure: document.getElementById('step-failure'),
    actionList: document.getElementById('action-list'),
    actionAdd: document.getElementById('action-add'),
    actionToggleJson: document.getElementById('action-toggle-json'),
    stepActionsJson: document.getElementById('step-actions-json'),
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
    dirty: false,
    stepDraftDirty: false
  };

  const actionEditors = {};

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

  function layoutStorageKey(key) {
    return `sm-layout:${key}`;
  }

  function saveLayoutToStorage(machine) {
    if (!machine || !machine.key || !Array.isArray(machine.steps)) return;
    const payload = {};
    machine.steps.forEach(step => {
      if (step && step.name && step.layout && typeof step.layout.x === 'number' && typeof step.layout.y === 'number') {
        payload[step.name] = { x: step.layout.x, y: step.layout.y };
      }
    });
    try {
      localStorage.setItem(layoutStorageKey(machine.key), JSON.stringify(payload));
    } catch (err) {
      console.warn('Failed to persist layout', err);
    }
  }

  function clearLayoutFromStorage(key) {
    try {
      localStorage.removeItem(layoutStorageKey(key));
    } catch (err) {
      console.warn('Failed to clear layout cache', err);
    }
  }

  function applyStoredLayout(machine) {
    if (!machine || !machine.key || !Array.isArray(machine.steps)) return;
    let cached = null;
    try {
      const raw = localStorage.getItem(layoutStorageKey(machine.key));
      if (raw) {
        cached = JSON.parse(raw);
      }
    } catch (err) {
      cached = null;
    }
    if (!cached) return;
    machine.steps.forEach(step => {
      const stored = cached[step.name];
      if (stored && typeof stored.x === 'number' && typeof stored.y === 'number') {
        step.layout = { x: stored.x, y: stored.y };
      }
    });
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
      applyStoredLayout(machine);
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
    machine.steps.forEach(step => {
      if (!Array.isArray(step.actions)) {
        step.actions = [];
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
    const startName = machine.start && byName.has(machine.start) ? machine.start : (machine.steps[0] ? machine.steps[0].name : null);
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
    let remaining = machine.steps.filter(step => !visited.has(step.name));
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

  function deepClone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  const BUILTIN_ACTION_TYPES = [
    'Screenshot',
    'Wait',
    'ClickPercent',
    'DragPercent',
    'SpiralCameraMoveStep',
    'ResetGemSpiral',
    'FindAndClick',
    'EndCycle',
    'CheckTemplate',
    'CheckTemplatesCountAtLeast',
    'CooldownGate',
    'SetCooldown',
    'SetCooldownRandom',
    'Retry',
    'ReadText'
  ];

  const ACTION_TEMPLATES = {
    Screenshot: { name: '' },
    Wait: { name: '', seconds: 1, randomize: false },
    ClickPercent: { name: '', x_pct: 0.5, y_pct: 0.5 },
    DragPercent: { name: '', x_pct: 0.5, y_pct: 0.5, to_x_pct: 0.6, to_y_pct: 0.6, duration_s: 0.5 },
    SpiralCameraMoveStep: { name: '', magnitude_x_pct: 0.2, magnitude_y_pct: 0.15, pause_after_drag_s: 0.5 },
    ResetGemSpiral: { name: '' },
    FindAndClick: { name: '', templates: [], region_pct: [0, 0, 1, 1], threshold: 0.8 },
    EndCycle: { name: '' },
    CheckTemplate: { name: '', template: '', region_pct: [0, 0, 1, 1], threshold: 0.85 },
    CheckTemplatesCountAtLeast: { name: '', templates: [], region_pct: [0, 0, 1, 1], threshold: 0.85, min_total: 1 },
    CooldownGate: { name: '', key: '' },
    SetCooldown: { name: '', key: '', seconds: 60 },
    SetCooldownRandom: { name: '', key: '', min_seconds: 30, max_seconds: 120 },
    Retry: { name: '', attempts: 3, actions: [] },
    ReadText: { name: '', region_pct: [0, 0, 1, 1], mode: 'ocr' }
  };

  function createDefaultAction(type, previous) {
    const template = ACTION_TEMPLATES[type];
    const action = Object.assign({ type }, template ? deepClone(template) : {});
    if (previous && typeof previous === 'object' && previous.name) {
      action.name = previous.name;
    }
    if (type === 'Retry' && !Array.isArray(action.actions)) {
      action.actions = [];
    }
    return action;
  }

  function collectActionTypes(actions, set = new Set()) {
    if (!Array.isArray(actions)) return set;
    actions.forEach(action => {
      if (action && typeof action.type === 'string') {
        set.add(action.type);
      }
      if (action && Array.isArray(action.actions)) {
        collectActionTypes(action.actions, set);
      }
    });
    return set;
  }

  function getTypeOptions(actions) {
    const set = new Set(BUILTIN_ACTION_TYPES);
    collectActionTypes(actions, set);
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  }

  function createActionEditor(config) {
    const { listEl, addButton, toggleButton, jsonTextarea, onDirty, onError } = config;
    let draft = [];
    let showJson = false;

    function markDirty() {
      if (typeof onDirty === 'function') {
        onDirty();
      }
    }

    function setDraft(actions) {
      draft = Array.isArray(actions) ? deepClone(actions) : [];
      render();
    }

    function getDraft() {
      if (showJson && jsonTextarea) {
        try {
          const parsed = JSON.parse(jsonTextarea.value || '[]');
          if (!Array.isArray(parsed)) {
            throw new Error('Actions must be an array');
          }
          draft = parsed;
        } catch (err) {
          throw err;
        }
      }
      return deepClone(draft);
    }

    function getAtPath(path) {
      return path.reduce((node, segment) => (node ? node[segment] : undefined), draft);
    }

    function getParent(path) {
      if (!path.length) return null;
      const parentPath = path.slice(0, -1);
      const key = path[path.length - 1];
      const container = parentPath.reduce((node, segment) => (node ? node[segment] : undefined), draft);
      if (!container) return null;
      return { container, key };
    }

    function replaceAction(path, newAction) {
      const parent = getParent(path);
      if (!parent) return;
      parent.container[parent.key] = newAction;
      markDirty();
      render();
    }

    function removeAction(path) {
      const parent = getParent(path);
      if (!parent) return;
      if (Array.isArray(parent.container)) {
        parent.container.splice(parent.key, 1);
      } else {
        delete parent.container[parent.key];
      }
      markDirty();
      render();
    }

    function moveAction(path, delta) {
      const parent = getParent(path);
      if (!parent || !Array.isArray(parent.container)) return;
      const index = parent.key;
      const target = index + delta;
      if (target < 0 || target >= parent.container.length) return;
      const tmp = parent.container[index];
      parent.container[index] = parent.container[target];
      parent.container[target] = tmp;
      markDirty();
      render();
    }

    function updateField(path, key, value) {
      const action = getAtPath(path);
      if (!action || typeof action !== 'object') return;
      action[key] = value;
      markDirty();
    }

    function removeField(path, key) {
      const action = getAtPath(path);
      if (!action || typeof action !== 'object') return;
      delete action[key];
      markDirty();
      render();
    }

    function addField(path, key, value) {
      const action = getAtPath(path);
      if (!action || typeof action !== 'object' || !key) return;
      if (key === 'type') return;
      action[key] = value;
      markDirty();
      render();
    }

    function ensureNested(path) {
      const action = getAtPath(path);
      if (!action || typeof action !== 'object') return [];
      if (!Array.isArray(action.actions)) {
        action.actions = [];
      }
      return action.actions;
    }

    function addNestedAction(path) {
      const actions = ensureNested(path);
      actions.push(createDefaultAction('Wait'));
      markDirty();
      render();
    }

    function render() {
      if (!listEl || !jsonTextarea || !toggleButton) return;
      if (showJson) {
        listEl.hidden = true;
        jsonTextarea.hidden = false;
        jsonTextarea.value = JSON.stringify(draft, null, 2);
        toggleButton.textContent = 'Hide JSON';
        return;
      }
      listEl.hidden = false;
      jsonTextarea.hidden = true;
      toggleButton.textContent = 'Show JSON';
      renderActionList(draft, listEl, [], {
        editor,
        typeOptions: getTypeOptions(draft),
        onError
      });
    }

    function toggleJson() {
      if (!showJson) {
        showJson = true;
        render();
        return;
      }
      if (!jsonTextarea) return;
      try {
        const parsed = JSON.parse(jsonTextarea.value || '[]');
        if (!Array.isArray(parsed)) {
          throw new Error('Actions must be an array');
        }
        draft = parsed;
        markDirty();
        showJson = false;
        render();
      } catch (err) {
        if (onError) onError(`Invalid JSON: ${err.message}`);
      }
    }

    if (addButton) {
      addButton.addEventListener('click', () => {
        draft.push(createDefaultAction('Wait'));
        markDirty();
        render();
      });
    }

    if (toggleButton) {
      toggleButton.addEventListener('click', toggleJson);
    }

    const editor = {
      setDraft,
      getDraft,
      render,
      changeType(path, type) {
        const action = getAtPath(path);
        const next = createDefaultAction(type, action);
        replaceAction(path, next);
      },
      deleteAction: removeAction,
      moveAction,
      updateField,
      removeField,
      addField,
      addNestedAction,
      isJsonMode() {
        return showJson;
      },
      markDirty
    };

    return editor;
  }

  function renderActionList(actions, container, path, ctx) {
    container.innerHTML = '';
    if (!Array.isArray(actions) || actions.length === 0) {
      const empty = document.createElement('div');
      empty.className = 'action-empty';
      empty.textContent = 'No actions yet.';
      container.appendChild(empty);
      return;
    }
    const typeOptions = Array.isArray(ctx.typeOptions) ? ctx.typeOptions : getTypeOptions(ctx.editor ? ctx.editor.getDraft ? ctx.editor.getDraft() : actions : actions);
    actions.forEach((action, index) => {
      const card = renderActionCard(action || {}, path.concat(index), Object.assign({}, ctx, { parentLength: actions.length }), index, typeOptions);
      container.appendChild(card);
    });
  }

  function renderActionCard(action, path, ctx, index, typeOptions) {
    const card = document.createElement('div');
    card.className = 'action-card';

    const header = document.createElement('div');
    header.className = 'action-card-header';

    const title = document.createElement('div');
    title.className = 'action-card-title';
    const pill = document.createElement('span');
    pill.className = 'action-pill';
    pill.textContent = action.type || 'Action';
    title.appendChild(pill);
    const subtitle = document.createElement('span');
    subtitle.className = 'action-card-subtitle';
    subtitle.textContent = `#${index + 1}`;
    title.appendChild(subtitle);
    header.appendChild(title);

    const controls = document.createElement('div');
    controls.className = 'action-card-controls';

    const typeSelect = document.createElement('select');
    typeSelect.className = 'action-type-select';
    const opts = new Set(typeOptions);
    if (action.type && !opts.has(action.type)) {
      opts.add(action.type);
    }
    Array.from(opts).sort((a, b) => a.localeCompare(b)).forEach(name => {
      const opt = document.createElement('option');
      opt.value = name;
      opt.textContent = name;
      if (name === action.type) {
        opt.selected = true;
      }
      typeSelect.appendChild(opt);
    });
    typeSelect.addEventListener('change', evt => {
      ctx.editor.changeType(path, evt.target.value);
    });
    controls.appendChild(typeSelect);

    const moveUp = createIconButton('▲', 'Move up', index === 0, () => ctx.editor.moveAction(path, -1));
    const moveDown = createIconButton('▼', 'Move down', index >= (ctx.parentLength || 1) - 1, () => ctx.editor.moveAction(path, 1));
    controls.appendChild(moveUp);
    controls.appendChild(moveDown);
    const deleteBtn = createIconButton('✕', 'Delete action', false, () => ctx.editor.deleteAction(path));
    deleteBtn.classList.add('danger');
    controls.appendChild(deleteBtn);

    header.appendChild(controls);
    card.appendChild(header);

    const body = document.createElement('div');
    body.className = 'action-card-body';
    const keys = Object.keys(action || {}).filter(key => key !== 'type' && key !== 'actions');
    keys.forEach(key => {
      const field = renderActionField(action, key, path, ctx);
      body.appendChild(field);
    });
    card.appendChild(body);

    if (Array.isArray(action.actions)) {
      const nestedWrapper = document.createElement('div');
      nestedWrapper.className = 'nested-actions';
      const nestedToolbar = document.createElement('div');
      nestedToolbar.className = 'actions-toolbar';
      const nestedLabel = document.createElement('span');
      nestedLabel.className = 'action-pill';
      nestedLabel.textContent = 'Nested Actions';
      nestedToolbar.appendChild(nestedLabel);
      const nestedAdd = document.createElement('button');
      nestedAdd.type = 'button';
      nestedAdd.className = 'btn secondary';
      nestedAdd.textContent = 'Add Action';
      nestedAdd.addEventListener('click', () => ctx.editor.addNestedAction(path.concat('actions')));
      nestedToolbar.appendChild(nestedAdd);
      nestedWrapper.appendChild(nestedToolbar);
      const nestedList = document.createElement('div');
      nestedList.className = 'action-list';
      nestedWrapper.appendChild(nestedList);
      renderActionList(action.actions, nestedList, path.concat('actions'), ctx);
      card.appendChild(nestedWrapper);
    }

    const footer = document.createElement('div');
    footer.className = 'action-card-footer';
    const addFieldBtn = document.createElement('button');
    addFieldBtn.type = 'button';
    addFieldBtn.className = 'btn secondary';
    addFieldBtn.textContent = 'Add Field';
    addFieldBtn.addEventListener('click', () => openAddFieldForm(footer, path, ctx));
    footer.appendChild(addFieldBtn);
    card.appendChild(footer);

    return card;
  }

  function createIconButton(symbol, title, disabled, handler) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'icon-button';
    btn.textContent = symbol;
    btn.title = title;
    if (disabled) {
      btn.disabled = true;
      btn.classList.add('disabled');
    } else {
      btn.addEventListener('click', handler);
    }
    return btn;
  }

  function determineValueKind(value) {
    if (Array.isArray(value)) {
      if (value.every(item => typeof item === 'string')) return 'string_list';
      if (value.every(item => typeof item === 'number')) return 'number_list';
      if (value.every(item => item && typeof item === 'object' && typeof item.type === 'string')) return 'actions';
      return 'json';
    }
    if (value && typeof value === 'object') {
      if (Object.prototype.hasOwnProperty.call(value, '$config')) return 'config';
      return 'json';
    }
    if (typeof value === 'number') return 'number';
    if (typeof value === 'boolean') return 'boolean';
    return 'string';
  }

  function renderActionField(action, key, path, ctx) {
    const field = document.createElement('div');
    field.className = 'action-field';
    const label = document.createElement('div');
    label.className = 'action-field-label';
    label.textContent = key;
    const removeBtn = createIconButton('✕', 'Remove field', false, () => ctx.editor.removeField(path, key));
    removeBtn.classList.add('danger');
    label.appendChild(removeBtn);
    field.appendChild(label);

    const kind = determineValueKind(action[key]);
    if (kind === 'actions') {
      const note = document.createElement('div');
      note.className = 'action-field-note';
      note.textContent = 'Use the nested editor below to manage actions.';
      field.appendChild(note);
      return field;
    }

    const input = createFieldInput(kind, action[key], value => ctx.editor.updateField(path, key, value), ctx.onError);
    field.appendChild(input);
    return field;
  }

  function createFieldInput(kind, value, onChange, onError) {
    const wrapper = document.createElement('div');
    wrapper.className = 'action-field-input';

    function notifyError(msg) {
      if (typeof onError === 'function') onError(msg);
    }

    if (kind === 'string') {
      const input = document.createElement('input');
      input.type = 'text';
      input.value = value != null ? value : '';
      input.addEventListener('input', () => onChange(input.value));
      wrapper.appendChild(input);
      return wrapper;
    }
    if (kind === 'number') {
      const input = document.createElement('input');
      input.type = 'number';
      input.step = 'any';
      input.value = value != null ? value : '';
      input.addEventListener('change', () => {
        const parsed = parseFloat(input.value);
        if (Number.isNaN(parsed)) {
          notifyError('Invalid number');
        } else {
          onChange(parsed);
        }
      });
      wrapper.appendChild(input);
      return wrapper;
    }
    if (kind === 'boolean') {
      const input = document.createElement('input');
      input.type = 'checkbox';
      input.checked = Boolean(value);
      input.addEventListener('change', () => onChange(Boolean(input.checked)));
      wrapper.appendChild(input);
      return wrapper;
    }
    if (kind === 'string_list' || kind === 'number_list') {
      const textarea = document.createElement('textarea');
      const items = Array.isArray(value) ? value : [];
      textarea.value = items.map(item => String(item)).join('\n');
      textarea.rows = 4;
      textarea.addEventListener('change', () => {
        const lines = textarea.value.split(/\r?\n/).map(line => line.trim()).filter(Boolean);
        if (kind === 'number_list') {
          const parsed = lines.map(line => Number(line)).filter(num => !Number.isNaN(num));
          onChange(parsed);
        } else {
          onChange(lines);
        }
      });
      wrapper.appendChild(textarea);
      return wrapper;
    }
    if (kind === 'config') {
      const attrInput = document.createElement('input');
      attrInput.type = 'text';
      attrInput.placeholder = 'config attribute';
      attrInput.value = value && value.$config ? value.$config : '';
      const defaultInput = document.createElement('textarea');
      defaultInput.rows = 2;
      defaultInput.placeholder = 'default (optional, JSON)';
      defaultInput.value = value && Object.prototype.hasOwnProperty.call(value, 'default') ? JSON.stringify(value.default) : '';
      attrInput.addEventListener('change', () => {
        const attr = attrInput.value.trim();
        if (!attr) {
          notifyError('Config attribute cannot be empty');
          return;
        }
        const updated = { $config: attr };
        const defText = defaultInput.value.trim();
        if (defText) {
          try {
            updated.default = JSON.parse(defText);
          } catch (err) {
            updated.default = defText;
          }
        }
        onChange(updated);
      });
      defaultInput.addEventListener('change', () => attrInput.dispatchEvent(new Event('change')));
      wrapper.appendChild(attrInput);
      wrapper.appendChild(defaultInput);
      return wrapper;
    }
    const textarea = document.createElement('textarea');
    textarea.rows = 4;
    textarea.value = value != null ? JSON.stringify(value, null, 2) : '';
    textarea.addEventListener('change', () => {
      const raw = textarea.value.trim();
      if (!raw) {
        onChange(null);
        return;
      }
      try {
        const parsed = JSON.parse(raw);
        onChange(parsed);
      } catch (err) {
        notifyError(`Invalid JSON: ${err.message}`);
      }
    });
    wrapper.appendChild(textarea);
    return wrapper;
  }

  function openAddFieldForm(container, path, ctx) {
    if (container.querySelector('.custom-field')) return;
    const form = document.createElement('div');
    form.className = 'action-field custom-field';
    const label = document.createElement('div');
    label.className = 'action-field-label';
    label.textContent = 'New Field';
    form.appendChild(label);

    const row = document.createElement('div');
    row.className = 'action-field-input';

    const nameInput = document.createElement('input');
    nameInput.type = 'text';
    nameInput.placeholder = 'name';
    row.appendChild(nameInput);

    const typeSelect = document.createElement('select');
    const fieldTypes = [
      { value: 'string', label: 'String' },
      { value: 'number', label: 'Number' },
      { value: 'boolean', label: 'Boolean' },
      { value: 'string_list', label: 'String List' },
      { value: 'number_list', label: 'Number List' },
      { value: 'json', label: 'JSON' },
      { value: 'config', label: 'Config Reference' }
    ];
    fieldTypes.forEach(item => {
      const opt = document.createElement('option');
      opt.value = item.value;
      opt.textContent = item.label;
      typeSelect.appendChild(opt);
    });
    row.appendChild(typeSelect);

    const valueWrapper = document.createElement('div');
    valueWrapper.className = 'custom-field-value';
    row.appendChild(valueWrapper);

    form.appendChild(row);

    const actions = document.createElement('div');
    actions.className = 'action-card-footer';
    const saveBtn = document.createElement('button');
    saveBtn.type = 'button';
    saveBtn.className = 'btn primary';
    saveBtn.textContent = 'Save';
    const cancelBtn = document.createElement('button');
    cancelBtn.type = 'button';
    cancelBtn.className = 'btn';
    cancelBtn.textContent = 'Cancel';
    actions.appendChild(saveBtn);
    actions.appendChild(cancelBtn);
    form.appendChild(actions);
    container.appendChild(form);

    let currentInput = null;

    function renderValueEditor(kind) {
      valueWrapper.innerHTML = '';
      if (currentInput && currentInput.destroy) {
        currentInput.destroy();
      }
      if (kind === 'boolean') {
        const select = document.createElement('select');
        ['true', 'false'].forEach(val => {
          const opt = document.createElement('option');
          opt.value = val;
          opt.textContent = val;
          select.appendChild(opt);
        });
        valueWrapper.appendChild(select);
        currentInput = {
          getValue() { return select.value === 'true'; }
        };
        return;
      }
      if (kind === 'string') {
        const input = document.createElement('input');
        input.type = 'text';
        valueWrapper.appendChild(input);
        currentInput = {
          getValue() { return input.value; }
        };
        return;
      }
      if (kind === 'number') {
        const input = document.createElement('input');
        input.type = 'number';
        input.step = 'any';
        valueWrapper.appendChild(input);
        currentInput = {
          getValue() {
            const parsed = parseFloat(input.value);
            if (Number.isNaN(parsed)) throw new Error('Enter a valid number');
            return parsed;
          }
        };
        return;
      }
      if (kind === 'string_list' || kind === 'number_list') {
        const textarea = document.createElement('textarea');
        textarea.rows = 3;
        textarea.placeholder = 'one per line';
        valueWrapper.appendChild(textarea);
        currentInput = {
          getValue() {
            const lines = textarea.value.split(/\r?\n/).map(line => line.trim()).filter(Boolean);
            if (kind === 'number_list') {
              const parsed = lines.map(line => Number(line)).filter(num => !Number.isNaN(num));
              return parsed;
            }
            return lines;
          }
        };
        return;
      }
      if (kind === 'config') {
        const attrInput = document.createElement('input');
        attrInput.type = 'text';
        attrInput.placeholder = 'config attribute';
        const defaultInput = document.createElement('textarea');
        defaultInput.rows = 2;
        defaultInput.placeholder = 'default (optional, JSON)';
        valueWrapper.appendChild(attrInput);
        valueWrapper.appendChild(defaultInput);
        currentInput = {
          getValue() {
            const attr = attrInput.value.trim();
            if (!attr) throw new Error('Config attribute is required');
            const result = { $config: attr };
            const def = defaultInput.value.trim();
            if (def) {
              try {
                result.default = JSON.parse(def);
              } catch (err) {
                result.default = def;
              }
            }
            return result;
          }
        };
        return;
      }
      const textarea = document.createElement('textarea');
      textarea.rows = 3;
      textarea.placeholder = 'JSON value';
      valueWrapper.appendChild(textarea);
      currentInput = {
        getValue() {
          const raw = textarea.value.trim();
          if (!raw) return null;
          return JSON.parse(raw);
        }
      };
    }

    renderValueEditor(typeSelect.value);
    typeSelect.addEventListener('change', () => renderValueEditor(typeSelect.value));

    cancelBtn.addEventListener('click', () => {
      form.remove();
    });

    saveBtn.addEventListener('click', () => {
      const name = nameInput.value.trim();
      if (!name) {
        if (ctx.onError) ctx.onError('Field name cannot be empty');
        return;
      }
      if (!currentInput || typeof currentInput.getValue !== 'function') return;
      try {
        const value = currentInput.getValue();
        ctx.editor.addField(path, name, value);
        form.remove();
      } catch (err) {
        if (ctx.onError) ctx.onError(err.message);
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
      if (actionEditors.sequence && actionEditors.sequence.setDraft) {
        actionEditors.sequence.setDraft([]);
      }
      if (actionEditors.step && actionEditors.step.setDraft) {
        actionEditors.step.setDraft([]);
      }
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
      if (actionEditors.step && actionEditors.step.setDraft) {
        actionEditors.step.setDraft([]);
      }
      state.stepDraftDirty = false;
      if (actionEditors.sequence && actionEditors.sequence.setDraft) {
        actionEditors.sequence.setDraft(machine.actions || []);
      }
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
    const steps = machine.steps.slice().sort((a, b) => {
      const ay = a.layout ? a.layout.y : 0;
      const by = b.layout ? b.layout.y : 0;
      if (ay !== by) return ay - by;
      const ax = a.layout ? a.layout.x : 0;
      const bx = b.layout ? b.layout.x : 0;
      return ax - bx;
    });
    steps.forEach(step => {
      const li = document.createElement('li');
      li.className = 'step-item';
      li.dataset.name = step.name;
      li.textContent = step.name;
      if (machine.start === step.name) {
        li.classList.add('start');
      }
      if (state.selectedStep && state.selectedStep.name === step.name) {
        li.classList.add('selected');
      }
      li.addEventListener('click', () => {
        if (state.stepDraftDirty) {
          const applied = applyStepChanges(true);
          if (!applied) {
            return;
          }
        }
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
      if (actionEditors.step && actionEditors.step.setDraft) {
        actionEditors.step.setDraft([]);
      }
      return;
    }
    const step = state.selectedStep;
    els.stepEditor.hidden = false;
    els.stepTitle.textContent = step.name;
    els.stepName.value = step.name;
    populateTransitionSelect(els.stepSuccess, step.on_success);
    populateTransitionSelect(els.stepFailure, step.on_failure);
    if (actionEditors.step && actionEditors.step.setDraft) {
      actionEditors.step.setDraft(step.actions || []);
    }
    state.stepDraftDirty = false;
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
      if (machine.start === step.name) {
        group.classList.add('start');
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
        if (state.current && state.current.type === 'graph') {
          saveLayoutToStorage(state.current);
        }
      }
    });
    group.addEventListener('pointerleave', evt => {
      if (state.dragging && state.dragging.step === step && evt.buttons === 0) {
        state.dragging = null;
        if (state.current && state.current.type === 'graph') {
          saveLayoutToStorage(state.current);
        }
      }
    });
  }

  function applyStepChanges(silent = false) {
    if (!state.current || state.current.type !== 'graph' || !state.selectedStep) return false;
    const step = state.selectedStep;
    const newName = els.stepName.value.trim();
    if (!newName) {
      if (!silent) showStatus('Step name cannot be empty.', 'err');
      return false;
    }
    const machine = state.current;
    if (newName !== step.name) {
      if (machine.steps.some(s => s !== step && s.name === newName)) {
        if (!silent) showStatus('Another step already has that name.', 'err');
        return false;
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
    if (actionEditors.step && typeof actionEditors.step.getDraft === 'function') {
      try {
        const actions = actionEditors.step.getDraft();
        step.actions = actions;
      } catch (err) {
        if (!silent) showStatus(`Invalid actions: ${err.message}`, 'err');
        return false;
      }
    }
    state.dirty = true;
    state.stepDraftDirty = false;
    renderStepList();
    renderDiagram();
    populateStartOptions();
    updateStepForm();
    if (!silent) showStatus('Step updated.', 'info');
    return true;
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
    saveLayoutToStorage(state.current);
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
    saveLayoutToStorage(state.current);
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
      if (actionEditors.sequence && typeof actionEditors.sequence.getDraft === 'function') {
        try {
          const actions = actionEditors.sequence.getDraft();
          state.current.actions = actions;
        } catch (err) {
          showStatus(`Invalid sequence actions: ${err.message}`, 'err');
        }
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
    const previousKey = state.current.key || '';
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
        saveLayoutToStorage(state.current);
        if (previousKey && previousKey !== key) {
          clearLayoutFromStorage(previousKey);
        }
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
        clearLayoutFromStorage(key);
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

  function initActionEditors() {
    if (els.actionList && els.stepActionsJson) {
      actionEditors.step = createActionEditor({
        listEl: els.actionList,
        addButton: els.actionAdd,
        toggleButton: els.actionToggleJson,
        jsonTextarea: els.stepActionsJson,
        onDirty: () => {
          state.stepDraftDirty = true;
        },
        onError: msg => showStatus(msg, 'err')
      });
    }
    if (els.sequenceActionList && els.sequenceActionsJson) {
      actionEditors.sequence = createActionEditor({
        listEl: els.sequenceActionList,
        addButton: els.sequenceAdd,
        toggleButton: els.sequenceToggleJson,
        jsonTextarea: els.sequenceActionsJson,
        onDirty: () => {
          state.dirty = true;
        },
        onError: msg => showStatus(msg, 'err')
      });
    }
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
    els.stepApply.addEventListener('click', applyStepChanges);
    els.stepDelete.addEventListener('click', deleteStep);
    els.stepAdd.addEventListener('click', addStep);
  }

  function init() {
    if (!els.list) return;
    initActionEditors();
    initEvents();
    loadList();
  }

  document.addEventListener('DOMContentLoaded', init);
})();
