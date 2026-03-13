let csrfToken = null;
let currentView = 'organization';
let wizardStep = 1;
let availableConnectors = {};
let selectedCapabilities = [];
let selectedPolicies = [];
let capabilities = [];
let policies = [];
let roles = [];
let workflows = [];
let tasks = [];

const statusBar = (msg) => {
  document.getElementById('statusBar').textContent = msg;
};

const authHeaders = () => {
  const h = { 'content-type': 'application/json' };
  const mode = document.getElementById('authMode').value;
  if (mode === 'token') {
    const token = document.getElementById('bearerToken').value.trim();
    if (token) h['authorization'] = `Bearer ${token}`;
  } else {
    h['x-loom-role'] = document.getElementById('roleHeader').value;
  }
  if (csrfToken) h['x-csrf-token'] = csrfToken;
  return h;
};

async function call(path, method = 'GET', body = null, expectsJson = true) {
  statusBar(`${method} ${path} ...`);
  const res = await fetch(path, { method, headers: authHeaders(), body: body ? JSON.stringify(body) : null });
  if (!expectsJson) return res;
  const text = await res.text();
  let data;
  try { data = JSON.parse(text); } catch { data = text; }
  if (!res.ok) {
    statusBar(`Error ${res.status}`);
    throw new Error(typeof data === 'string' ? data : JSON.stringify(data, null, 2));
  }
  statusBar('Ready');
  return data;
}

const setOut = (id, data) => {
  const el = document.getElementById(id);
  if (el) el.textContent = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
};

function confirmDanger(msg) {
  return window.confirm(msg);
}

function switchView(viewName) {
  currentView = viewName;
  document.querySelectorAll('.nav-item').forEach(item => {
    item.classList.toggle('active', item.dataset.view === viewName);
  });
  document.querySelectorAll('.view').forEach(view => {
    view.classList.toggle('active', view.id === `view-${viewName}`);
  });
  const titles = {
    organization: 'Organization Settings',
    agents: 'Agents Management',
    workflows: 'Workflows Studio',
    tasks: 'Tasks Console'
  };
  document.getElementById('viewTitle').textContent = titles[viewName] || viewName;
  
  if (viewName === 'agents') loadAgentsData();
  if (viewName === 'workflows') loadWorkflowsData();
  if (viewName === 'tasks') loadTasksData();
}

function switchTab(containerId, tabName) {
  const container = document.getElementById(containerId);
  if (!container) return;
  container.querySelectorAll('.tab-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.tab === tabName);
  });
  container.querySelectorAll('.tab-content').forEach(content => {
    content.classList.toggle('active', content.id === `tab-${tabName}`);
  });
}

function switchWizardStep(step) {
  wizardStep = step;
  document.querySelectorAll('.wizard-step').forEach(s => {
    s.classList.toggle('active', parseInt(s.dataset.step) === step);
    s.classList.toggle('completed', parseInt(s.dataset.step) < step);
  });
  document.querySelectorAll('.wizard-panel').forEach(p => {
    p.classList.toggle('active', p.id === `wizard-step-${step}`);
  });
  
  document.getElementById('wizardPrev').disabled = step === 1;
  document.getElementById('wizardNext').classList.toggle('hidden', step === 5);
  document.getElementById('wizardCreate').classList.toggle('hidden', step !== 5);
  
  if (step === 3) loadConnectors();
  if (step === 5) updateAgentReview();
}

async function refreshAuth() {
  const me = await call('/api/auth/me');
  const csrf = await call('/api/auth/csrf');
  csrfToken = csrf.csrf;
}

async function refreshAll() {
  await loadOrganization();
  await loadIntegrationStatus();
}

async function loadOrganization() {
  try {
    const org = await call('/api/organization');
    document.getElementById('orgName').value = org.name || '';
    document.getElementById('orgLiteLLMUrl').value = org.litellm_base_url || '';
    document.getElementById('orgLiteLLMApiKey').value = org.litellm_api_key || '';
    document.getElementById('orgLiteLLMModel').value = org.litellm_default_model || 'open-large';
    document.getElementById('orgOpenAIApiKey').value = org.openai_api_key || '';
    document.getElementById('orgOpenAIModel').value = org.openai_model || 'gpt-4.1-mini';
    document.getElementById('orgOpenCodeEnabled').checked = org.opencode_enabled || false;
    document.getElementById('orgOpenCodeCmd').value = org.opencode_cmd || 'opencode';
    updateOpenCodeStatus();
  } catch (e) {
    console.error('Failed to load organization:', e);
  }
}

async function saveOrganization() {
  const payload = {
    name: document.getElementById('orgName').value,
    litellm_base_url: document.getElementById('orgLiteLLMUrl').value || null,
    litellm_api_key: document.getElementById('orgLiteLLMApiKey').value || null,
    litellm_default_model: document.getElementById('orgLiteLLMModel').value || 'open-large',
    openai_api_key: document.getElementById('orgOpenAIApiKey').value || null,
    openai_model: document.getElementById('orgOpenAIModel').value || 'gpt-4.1-mini',
    opencode_enabled: document.getElementById('orgOpenCodeEnabled').checked,
    opencode_cmd: document.getElementById('orgOpenCodeCmd').value || 'opencode',
  };
  await call('/api/organization', 'POST', payload);
  alert('Organization settings saved!');
}

function updateOpenCodeStatus() {
  const statusEl = document.getElementById('opencodeStatus');
  if (!statusEl) return;
  
  const health = availableConnectors.commands || {};
  const opencodeCmd = document.getElementById('orgOpenCodeCmd')?.value || 'opencode';
  const isAvailable = health[opencodeCmd];
  
  statusEl.innerHTML = `
    <span class="connector-status ${isAvailable ? 'available' : 'unavailable'}">
      ${isAvailable ? '✓ OpenCode CLI is available' : '✗ OpenCode CLI not found in PATH'}
    </span>
  `;
}

async function loadIntegrationStatus() {
  try {
    const status = await call('/api/integrations/status');
    const health = await call('/api/integrations/health');
    availableConnectors = { ...status.commands, ...health };
    setOut('integrationStatusOut', { status, health });
    updateOpenCodeStatus();
  } catch (e) {
    console.error('Failed to load integration status:', e);
  }
}

async function loadAgentsData() {
  try {
    capabilities = await call('/api/capabilities');
    policies = await call('/api/policies');
    roles = await call('/api/roles');
    renderCapabilitiesSelector();
    renderPoliciesSelector();
    renderAgentsList();
  } catch (e) {
    console.error('Failed to load agents data:', e);
  }
}

function renderAgentsList() {
  const container = document.getElementById('agentsList');
  if (!container) return;
  
  if (roles.length === 0) {
    container.innerHTML = '<p class="hint">No agents created yet. Use the Create Agent tab to add one.</p>';
    return;
  }
  
  container.innerHTML = roles.map(role => {
    const caps = role.capability_ids || [];
    const connectors = caps.map(capId => {
      const cap = capabilities.find(c => c.capability_id === capId);
      return cap?.connector_binding;
    }).filter(Boolean);
    const uniqueConnectors = [...new Set(connectors)];
    
    return `
      <div class="agent-card">
        <h4>
          ${role.title || role.role_id}
          <span class="status-badge ${role.status}">${role.status}</span>
        </h4>
        <div class="capabilities">
          ${caps.length > 0 ? caps.join(', ') : 'No capabilities'}
        </div>
        <div class="connector-badges">
          ${uniqueConnectors.map(c => `<span class="connector-badge ${c}">${c}</span>`).join('')}
        </div>
      </div>
    `;
  }).join('');
}

function renderCapabilitiesSelector() {
  const container = document.getElementById('capabilitiesSelector');
  if (!container) return;
  
  container.innerHTML = capabilities.map(cap => `
    <label class="checkbox-item">
      <input type="checkbox" value="${cap.capability_id}" 
             ${selectedCapabilities.includes(cap.capability_id) ? 'checked' : ''}
             onchange="toggleCapability('${cap.capability_id}')">
      <div class="cap-info">
        <div class="cap-id">${cap.capability_id}</div>
        <div class="cap-desc">${cap.description || ''}</div>
      </div>
      ${cap.connector_binding ? `<span class="cap-connector">${cap.connector_binding}</span>` : ''}
    </label>
  `).join('');
}

function renderPoliciesSelector() {
  const container = document.getElementById('policiesSelector');
  if (!container) return;
  
  container.innerHTML = policies.map(pol => `
    <label class="checkbox-item">
      <input type="checkbox" value="${pol.policy_id}"
             ${selectedPolicies.includes(pol.policy_id) ? 'checked' : ''}
             onchange="togglePolicy('${pol.policy_id}')">
      <div class="cap-info">
        <div class="cap-id">${pol.policy_id}</div>
        <div class="cap-desc">${pol.description || ''}</div>
      </div>
    </label>
  `).join('');
}

function toggleCapability(capId) {
  if (selectedCapabilities.includes(capId)) {
    selectedCapabilities = selectedCapabilities.filter(c => c !== capId);
  } else {
    selectedCapabilities.push(capId);
  }
}

function togglePolicy(polId) {
  if (selectedPolicies.includes(polId)) {
    selectedPolicies = selectedPolicies.filter(p => p !== polId);
  } else {
    selectedPolicies.push(polId);
  }
}

async function addNewCapability() {
  const capId = document.getElementById('newCapId').value.trim();
  const desc = document.getElementById('newCapDesc').value.trim();
  const connector = document.getElementById('newCapConnector').value;
  
  if (!capId) {
    alert('Please enter a capability ID');
    return;
  }
  
  const payload = {
    capability_id: capId,
    description: desc || capId,
    connector_binding: connector,
    status: 'active'
  };
  
  await call('/api/capabilities', 'POST', payload);
  document.getElementById('newCapId').value = '';
  document.getElementById('newCapDesc').value = '';
  
  capabilities = await call('/api/capabilities');
  renderCapabilitiesSelector();
  selectedCapabilities.push(capId);
  renderCapabilitiesSelector();
}

function loadConnectors() {
  const container = document.getElementById('connectorsList');
  if (!container) return;
  
  const connectorList = [
    { name: 'opencode', label: 'OpenCode CLI', check: availableConnectors.commands?.opencode },
    { name: 'litellm', label: 'LiteLLM', check: availableConnectors.litellm?.enabled },
    { name: 'git', label: 'Git', check: availableConnectors.commands?.git },
    { name: 'gh', label: 'GitHub CLI', check: availableConnectors.commands?.gh },
    { name: 'openai', label: 'OpenAI', check: availableConnectors.openai?.enabled },
    { name: 'graphiti', label: 'Graphiti', check: availableConnectors.graphiti?.enabled },
  ];
  
  container.innerHTML = connectorList.map(conn => `
    <div class="connector-item">
      <span class="connector-name">${conn.label}</span>
      <span class="connector-status ${conn.check ? 'available' : 'unavailable'}">
        ${conn.check ? 'Available' : 'Not Available'}
      </span>
    </div>
  `).join('');
}

function updateAgentReview() {
  const review = {
    role_id: document.getElementById('agentId').value || 'unnamed_agent',
    title: document.getElementById('agentTitle').value || 'Untitled Agent',
    domain_pack: document.getElementById('agentDomainPack').value || 'custom',
    capability_ids: selectedCapabilities,
    policy_ids: selectedPolicies,
    status: 'active'
  };
  setOut('agentReview', review);
}

async function createAgent() {
  const payload = {
    role: {
      role_id: document.getElementById('agentId').value,
      title: document.getElementById('agentTitle').value,
      domain_pack: document.getElementById('agentDomainPack').value,
      capability_ids: selectedCapabilities,
      policy_ids: selectedPolicies,
      status: 'active'
    },
    capabilities: selectedCapabilities.map(capId => {
      const cap = capabilities.find(c => c.capability_id === capId);
      return cap || { capability_id: capId, description: capId, status: 'active' };
    }),
    policies: selectedPolicies.map(polId => {
      const pol = policies.find(p => p.policy_id === polId);
      return pol || { policy_id: polId, description: polId, status: 'active' };
    }),
    prompt_profile: {
      profile_id: `${document.getElementById('agentId').value}_prompt`,
      version: 1,
      domain_pack: document.getElementById('agentDomainPack').value,
      system_prompt: `You are ${document.getElementById('agentTitle').value}.`,
      status: 'active'
    }
  };
  
  await call('/api/agents/builder', 'POST', payload);
  alert('Agent created successfully!');
  
  selectedCapabilities = [];
  selectedPolicies = [];
  wizardStep = 1;
  switchWizardStep(1);
  switchTab('view-agents', 'agents-list');
  await loadAgentsData();
}

async function loadWorkflowsData() {
  try {
    workflows = await call('/api/workflows');
    renderWorkflowsList();
  } catch (e) {
    console.error('Failed to load workflows:', e);
  }
}

function renderWorkflowsList() {
  const container = document.getElementById('workflowsList');
  if (!container) return;
  
  if (workflows.length === 0) {
    container.innerHTML = '<p class="hint">No workflows created yet. Use the Create Workflow tab to add one.</p>';
    return;
  }
  
  container.innerHTML = workflows.map(wf => {
    const ir = wf.compiled_ir || {};
    const steps = ir.steps || [];
    return `
      <div class="card" style="margin-bottom: 8px;">
        <h4>${wf.metadata?.title || wf.workflow_id} <span class="status-badge ${wf.status}">${wf.status}</span></h4>
        <div style="font-size: 0.85rem; color: var(--muted);">
          Version: ${wf.version} | Steps: ${steps.length}
        </div>
        ${steps.length > 0 ? `
          <div style="margin-top: 8px;">
            ${steps.slice(0, 3).map(s => `
              <div class="step-preview">
                <div class="step-title">${s.step_id}</div>
                <div class="step-owner">owned by: <span class="owner-badge">${s.owned_by}</span></div>
              </div>
            `).join('')}
            ${steps.length > 3 ? `<div style="font-size: 0.8rem; color: var(--muted);">+${steps.length - 3} more steps</div>` : ''}
          </div>
        ` : ''}
      </div>
    `;
  }).join('');
}

function updateWorkflowPreview() {
  const markdown = document.getElementById('workflowMarkdown').value;
  const preview = document.getElementById('workflowPreview');
  const validation = document.getElementById('workflowValidation');
  
  if (!markdown.trim()) {
    preview.innerHTML = '<p class="hint">Start typing workflow markdown to see a preview...</p>';
    validation.innerHTML = '';
    return;
  }
  
  const lines = markdown.split('\n');
  const steps = [];
  let currentStep = null;
  
  for (const line of lines) {
    if (line.startsWith('### Step')) {
      if (currentStep) steps.push(currentStep);
      currentStep = { title: line.replace('### ', '').replace('Step ', '').trim(), owned_by: '', participants: [] };
    } else if (currentStep && line.includes('owned_by:')) {
      currentStep.owned_by = line.split('owned_by:')[1].trim();
    } else if (currentStep && line.includes('participants:')) {
      currentStep.participants = line.split('participants:')[1].trim().replace(/[\[\]]/g, '').split(',').map(s => s.trim()).filter(Boolean);
    }
  }
  if (currentStep) steps.push(currentStep);
  
  if (steps.length === 0) {
    preview.innerHTML = '<p class="hint">Add steps using "### Step N: Title" format to see agent assignments.</p>';
  } else {
    preview.innerHTML = steps.map(s => `
      <div class="step-preview">
        <div class="step-title">${s.title}</div>
        <div class="step-owner">
          owned by: <span class="owner-badge">${s.owned_by || 'unassigned'}</span>
          ${s.participants.length > 0 ? `| participants: ${s.participants.join(', ')}` : ''}
        </div>
      </div>
    `).join('');
  }
}

async function validateWorkflow() {
  const payload = {
    workflow_id: document.getElementById('wfId').value || 'untitled',
    version: Number(document.getElementById('wfVersion').value || 1),
    markdown: document.getElementById('workflowMarkdown').value,
  };
  
  try {
    const result = await call('/api/workflows/validate', 'POST', payload);
    const validation = document.getElementById('workflowValidation');
    
    if (result.ok) {
      validation.innerHTML = '<div class="validation-success">Workflow is valid!</div>';
    } else {
      validation.innerHTML = `<div class="validation-error">Errors:\n${result.errors.join('\n')}</div>`;
    }
  } catch (e) {
    document.getElementById('workflowValidation').innerHTML = `<div class="validation-error">${e.message}</div>`;
  }
}

async function publishWorkflow() {
  const payload = {
    workflow_id: document.getElementById('wfId').value,
    version: Number(document.getElementById('wfVersion').value || 1),
    title: document.getElementById('wfTitle').value || 'Untitled Workflow',
    domain_pack: document.getElementById('wfDomain').value || 'custom',
    intent_group: document.getElementById('wfIntent').value || 'general',
    markdown: document.getElementById('workflowMarkdown').value,
    activate: document.getElementById('wfActivate').checked,
  };
  
  if (!payload.workflow_id) {
    alert('Please enter a workflow ID');
    return;
  }
  
  await call('/api/workflows/publish', 'POST', payload);
  alert('Workflow published successfully!');
  await loadWorkflowsData();
}

async function workflowAction(name) {
  const wf = document.getElementById('wfVersionActionId').value;
  const ver = Number(document.getElementById('wfVersionAction').value);
  if (!wf || !ver) {
    alert('workflow_id and version required');
    return;
  }
  if (['archive', 'rollback'].includes(name) && !confirmDanger(`${name} workflow version?`)) return;
  
  await call(`/api/workflows/${encodeURIComponent(wf)}/${ver}/${name}`, 'POST');
  alert(`Workflow ${name} successful!`);
  await loadWorkflowsData();
}

async function loadTasksData() {
  try {
    tasks = await call('/api/tasks');
    renderAllTasksList();
  } catch (e) {
    console.error('Failed to load tasks:', e);
  }
}

function renderAllTasksList() {
  const container = document.getElementById('allTasksList');
  if (!container) return;
  
  if (tasks.length === 0) {
    container.innerHTML = '<p class="hint">No tasks yet. Use the Console tab to create and run tasks.</p>';
    return;
  }
  
  container.innerHTML = tasks.map(task => `
    <div class="task-item">
      <div class="task-info">
        <div class="task-id">${task.task_id}</div>
        <div class="task-request">${task.raw_request?.substring(0, 100)}${task.raw_request?.length > 100 ? '...' : ''}</div>
      </div>
      <span class="task-status ${task.current_status}">${task.current_status}</span>
    </div>
  `).join('');
}

async function intakeTask() {
  const payload = {
    request: document.getElementById('taskRequest').value,
    domain_pack: document.getElementById('taskDomain').value || 'custom',
    async_run: document.getElementById('taskAsync').checked,
  };
  
  if (!payload.request) {
    alert('Please enter a request');
    return;
  }
  
  const result = await call('/api/tasks/intake', 'POST', payload);
  setOut('tasksOut', result);
  if (result.task?.task_id) {
    document.getElementById('taskId').value = result.task.task_id;
  }
  await loadTasksData();
}

async function runTask() {
  const taskId = document.getElementById('taskId').value;
  if (!taskId) {
    alert('Please enter a task ID');
    return;
  }
  const result = await call(`/api/tasks/${encodeURIComponent(taskId)}/run`, 'POST');
  setOut('tasksOut', result);
  await loadTasksData();
}

async function retryTask() {
  const taskId = document.getElementById('taskId').value;
  if (!taskId) {
    alert('Please enter a task ID');
    return;
  }
  const result = await call(`/api/tasks/${encodeURIComponent(taskId)}/retry`, 'POST');
  setOut('tasksOut', result);
  await loadTasksData();
}

async function traceTask() {
  const taskId = document.getElementById('taskId').value;
  if (!taskId) {
    alert('Please enter a task ID');
    return;
  }
  const result = await call(`/api/tasks/${encodeURIComponent(taskId)}/trace`);
  setOut('tasksOut', result);
}

async function markTask(status) {
  const taskId = document.getElementById('taskId').value;
  const reason = document.getElementById('markReason').value;
  if (!taskId) {
    alert('Please enter a task ID');
    return;
  }
  const result = await call(`/api/tasks/${encodeURIComponent(taskId)}/mark/${status}?reason=${encodeURIComponent(reason)}`, 'POST');
  setOut('tasksOut', result);
  await loadTasksData();
}

function bindNavItems() {
  document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', () => switchView(item.dataset.view));
  });
}

function bindTabs() {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const view = btn.closest('.view');
      if (view) switchTab(view.id, btn.dataset.tab);
    });
  });
}

function bindWizardSteps() {
  document.querySelectorAll('.wizard-step').forEach(step => {
    step.addEventListener('click', () => switchWizardStep(parseInt(step.dataset.step)));
  });
}

async function init() {
  bindNavItems();
  bindTabs();
  bindWizardSteps();
  
  document.getElementById('refreshAll').addEventListener('click', async () => {
    await refreshAuth();
    await refreshAll();
  });
  document.getElementById('loadIntegrationStatus').addEventListener('click', loadIntegrationStatus);
  document.getElementById('saveOrganization').addEventListener('click', saveOrganization);
  
  document.getElementById('wizardPrev').addEventListener('click', () => {
    if (wizardStep > 1) switchWizardStep(wizardStep - 1);
  });
  document.getElementById('wizardNext').addEventListener('click', () => {
    if (wizardStep < 5) switchWizardStep(wizardStep + 1);
  });
  document.getElementById('wizardCreate').addEventListener('click', createAgent);
  document.getElementById('addCapability').addEventListener('click', addNewCapability);
  
  document.getElementById('workflowMarkdown').addEventListener('input', updateWorkflowPreview);
  document.getElementById('validateWorkflow').addEventListener('click', validateWorkflow);
  document.getElementById('publishWorkflow').addEventListener('click', publishWorkflow);
  document.getElementById('activateWorkflow').addEventListener('click', () => workflowAction('activate'));
  document.getElementById('deprecateWorkflow').addEventListener('click', () => workflowAction('deprecate'));
  document.getElementById('archiveWorkflow').addEventListener('click', () => workflowAction('archive'));
  document.getElementById('rollbackWorkflow').addEventListener('click', () => workflowAction('rollback'));
  
  document.getElementById('intakeTask').addEventListener('click', intakeTask);
  document.getElementById('runTask').addEventListener('click', runTask);
  document.getElementById('retryTask').addEventListener('click', retryTask);
  document.getElementById('traceTask').addEventListener('click', traceTask);
  document.getElementById('markBlocked').addEventListener('click', () => markTask('blocked'));
  document.getElementById('markFailed').addEventListener('click', () => markTask('failed'));
  
  try {
    await refreshAuth();
    await refreshAll();
  } catch (e) {
    statusBar(e.message);
  }
}

init();
