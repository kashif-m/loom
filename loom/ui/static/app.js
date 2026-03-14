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
let modelsCatalog = [];
let currentOrgId = 'default';
let taskEventSource = null;
let currentTheme = localStorage.getItem('loomTheme') || 'light';
let currentRuntime = null;
let topologyGraph = null;
let topologyDirty = false;
let designerDraft = null;
let designerGeneratedBundle = null;
let designerDirty = false;
let selectedDesignerRoleId = null;
let selectedDesignerWorkflowId = null;
let selectedDesignerStepId = null;

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

const showNotification = (message, type = 'info', duration = 5000) => {
  const container = document.getElementById('notifications');
  if (!container) return;
  
  const notification = document.createElement('div');
  notification.className = `notification ${type}`;
  notification.setAttribute('role', type === 'error' ? 'alert' : 'status');
  notification.innerHTML = `
    <span>${message}</span>
    <button class="notification-close" aria-label="Dismiss notification">&times;</button>
  `;
  
  container.appendChild(notification);
  
  const closeBtn = notification.querySelector('.notification-close');
  closeBtn.addEventListener('click', () => removeNotification(notification));
  
  if (duration > 0) {
    setTimeout(() => removeNotification(notification), duration);
  }
};

const removeNotification = (notification) => {
  notification.classList.add('removing');
  setTimeout(() => notification.remove(), 300);
};

function applyTheme(theme) {
  currentTheme = theme === 'dark' ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', currentTheme);
  localStorage.setItem('loomTheme', currentTheme);
  const btn = document.getElementById('themeToggle');
  if (btn) btn.textContent = currentTheme === 'dark' ? 'Light' : 'Dark';
}

function confirmDanger(msg) {
  return window.confirm(msg);
}

// View switching with batch DOM updates
let viewSwitchRAF = null;

function switchView(viewName) {
  // Cancel any pending view switch
  if (viewSwitchRAF) cancelAnimationFrame(viewSwitchRAF);
  
  currentView = viewName;
  
  // Batch DOM reads
  const navItems = document.querySelectorAll('.nav-item');
  const views = document.querySelectorAll('.view');
  const titles = {
    organization: 'Organization Settings',
    agents: 'Agents Management',
    workflows: 'Workflows Studio',
    designer: 'Designer Studio',
    tasks: 'Tasks Console'
  };
  const viewTitle = titles[viewName] || viewName;
  
  // Schedule DOM writes in next frame
  viewSwitchRAF = requestAnimationFrame(() => {
    navItems.forEach(item => {
      const isActive = item.dataset.view === viewName;
      item.classList.toggle('active', isActive);
      item.setAttribute('aria-selected', isActive ? 'true' : 'false');
    });
    
    views.forEach(view => {
      view.classList.toggle('active', view.id === `view-${viewName}`);
    });
    
    document.getElementById('viewTitle').textContent = viewTitle;
    document.title = `${viewTitle} | Loom`;
    
    // Lazy load data for non-visible views
    if (viewName === 'agents') loadAgentsData();
    if (viewName === 'workflows') loadWorkflowsData();
    if (viewName === 'designer') loadDesignerData();
    if (viewName === 'tasks') loadTasksData();
  });
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
  await loadOrganizations();
  await loadOrganization();
  await loadIntegrationStatus();
}

async function loadOrganizations() {
  try {
    const orgs = await call('/api/organizations');
    const select = document.getElementById('orgSelect');
    if (!select) return;

    if (!Array.isArray(orgs) || orgs.length === 0) {
      currentOrgId = 'default';
      select.innerHTML = '<option value="default">default</option>';
      select.value = 'default';
      return;
    }

    const orgIds = orgs.map(o => o.org_id);
    if (!orgIds.includes(currentOrgId)) {
      currentOrgId = orgIds[0];
    }

    select.innerHTML = orgs.map(org => `
      <option value="${org.org_id}">${org.org_id} - ${org.name || ''}</option>
    `).join('');
    select.value = currentOrgId;
  } catch (e) {
    // Silently handle load errors
    if (process.env.NODE_ENV === 'development') {
      console.error('Failed to load organizations:', e);
    }
  }
}

async function loadOrganization() {
  try {
    const org = await call(`/api/organization?org_id=${encodeURIComponent(currentOrgId)}`);
    currentOrgId = org.org_id || currentOrgId;
    const select = document.getElementById('orgSelect');
    if (select) select.value = currentOrgId;
    document.getElementById('orgName').value = org.name || '';
    document.getElementById('orgLiteLLMUrl').value = org.litellm_base_url || '';
    document.getElementById('orgLiteLLMApiKey').value = org.litellm_api_key || '';
    document.getElementById('orgLiteLLMModel').value = org.litellm_default_model || 'open-large';
    document.getElementById('orgLiteLLMStartCmd').value = org.litellm_start_cmd || '';
    document.getElementById('orgOpenAIApiKey').value = org.openai_api_key || '';
    document.getElementById('orgOpenAIModel').value = org.openai_model || 'gpt-4.1-mini';
    document.getElementById('orgOpenCodeEnabled').checked = org.opencode_enabled || false;
    document.getElementById('orgOpenCodeCmd').value = org.opencode_cmd || 'opencode';
    updateOpenCodeStatus();
    await refreshRuntime();
  } catch (e) {
    // Silently handle load errors
    if (process.env.NODE_ENV === 'development') {
      console.error('Failed to load organization:', e);
    }
  }
}

async function saveOrganization() {
  const btn = document.getElementById('saveOrganization');
  btn.setAttribute('aria-busy', 'true');
  btn.disabled = true;
  
  try {
    const payload = {
      org_id: currentOrgId,
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
    showNotification('Organization settings saved', 'success');
    await loadOrganizations();
  } finally {
    btn.removeAttribute('aria-busy');
    btn.disabled = false;
  }
}

function renderRuntimeSummary(runtime) {
  const container = document.getElementById('runtimeSummary');
  if (!container) return;
  const services = Array.isArray(runtime?.services) ? runtime.services : [];
  if (services.length === 0) {
    container.innerHTML = '<p class="hint">No runtime services detected yet.</p>';
    return;
  }
  container.innerHTML = services.map((svc) => {
    const state = svc.state || 'unknown';
    const title = svc.service_id || 'service';
    const health = svc.healthy ? 'healthy' : 'unhealthy';
    const meta = [];
    if (svc.type === 'server' && svc.health_url) meta.push(svc.health_url);
    if (svc.type === 'command' && svc.command) meta.push(`cmd: ${svc.command}`);
    if (svc.required) meta.push('required');
    if (!svc.configured) meta.push('missing config');
    return `
      <div class="runtime-chip">
        <div class="runtime-title">
          <span>${title}</span>
          <span class="runtime-badge ${state}">${state}</span>
        </div>
        <div class="runtime-meta">${health}${meta.length ? ` | ${meta.join(' | ')}` : ''}</div>
      </div>
    `;
  }).join('');
}

async function refreshRuntime() {
  try {
    const runtime = await call(`/api/organization/runtime?org_id=${encodeURIComponent(currentOrgId)}`);
    currentRuntime = runtime;
    renderRuntimeSummary(runtime);
    setOut('runtimeOut', runtime);
  } catch (e) {
    // Silently handle load errors
    if (process.env.NODE_ENV === 'development') {
      console.error('Failed to load runtime status:', e);
    }
  }
}

async function runOrganizationRuntime() {
  const payload = { org_id: currentOrgId };
  const runtime = await call('/api/organization/runtime/run', 'POST', payload);
  currentRuntime = runtime;
  renderRuntimeSummary(runtime);
  setOut('runtimeOut', runtime);
  if (runtime.restart_required) {
    showNotification('Runtime needs restart to apply config changes', 'info');
  }
}

async function stopOrganizationRuntime() {
  if (!confirmDanger('Stop managed runtime services for this organization?')) return;
  const payload = { org_id: currentOrgId };
  const runtime = await call('/api/organization/runtime/stop', 'POST', payload);
  currentRuntime = runtime;
  renderRuntimeSummary(runtime);
  setOut('runtimeOut', runtime);
}

async function applyBundle() {
  const bundleYaml = document.getElementById('bundleYaml').value;
  const bundleOut = document.getElementById('bundleOut');
  if (!bundleYaml.trim()) {
    bundleOut.innerHTML = '<div class="validation-error" role="alert">Please paste bundle YAML</div>';
    return;
  }
  const btn = document.getElementById('applyBundle');
  btn.setAttribute('aria-busy', 'true');
  btn.disabled = true;
  try {
    const result = await call(
      `/api/bundle/apply?org_id=${encodeURIComponent(currentOrgId)}`,
      'POST',
      { bundle_yaml: bundleYaml }
    );
    setOut('bundleOut', result);
    bundleOut.insertAdjacentHTML('afterbegin', '<div class="validation-success" role="status">Bundle applied successfully!</div>');
    await refreshAll();
  } finally {
    btn.removeAttribute('aria-busy');
    btn.disabled = false;
  }
}

async function exportBundle() {
  const domainPack = document.getElementById('bundleExportDomain').value.trim();
  const q = new URLSearchParams({ org_id: currentOrgId });
  if (domainPack) q.set('domain_pack', domainPack);
  const res = await fetch(`/api/bundle/export?${q.toString()}`, { headers: authHeaders() });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Failed export (${res.status})`);
  }
  const yaml = await res.text();
  setOut('bundleOut', yaml);
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
    const status = await call(`/api/integrations/status?org_id=${encodeURIComponent(currentOrgId)}`);
    const health = await call('/api/integrations/health');
    availableConnectors = {
      commands: { ...(status.commands || {}), ...(health.commands || {}) },
      litellm: status.litellm || {},
      openai: status.openai || health.openai || {},
      graphiti: status.graphiti || health.graphiti || {},
      openclaw: status.openclaw || health.openclaw || {},
      opencode: status.opencode || {},
    };
    if (status.runtime) {
      currentRuntime = status.runtime;
      renderRuntimeSummary(status.runtime);
      setOut('runtimeOut', status.runtime);
    }
    setOut('integrationStatusOut', { status, health });
    updateOpenCodeStatus();
  } catch (e) {
    // Silently handle load errors
    if (process.env.NODE_ENV === 'development') {
      console.error('Failed to load integration status:', e);
    }
  }
}

async function loadAgentsData() {
  try {
    capabilities = await call('/api/capabilities');
    policies = await call('/api/policies');
    roles = await call('/api/roles');
    modelsCatalog = await call('/api/models');
    renderCapabilitiesSelector();
    renderPoliciesSelector();
    renderModelSelector();
    renderAgentsList();
  } catch (e) {
    // Silently handle load errors
    if (process.env.NODE_ENV === 'development') {
      console.error('Failed to load agents data:', e);
    }
  }
}

function renderModelSelector() {
  const select = document.getElementById('agentPreferredModel');
  if (!select) return;
  const options = ['<option value="">(use service/org default)</option>'];
  for (const model of modelsCatalog) {
    options.push(`<option value="${model.model_id}">${model.model_id} (${model.model_name})</option>`);
  }
  select.innerHTML = options.join('');
}

// Memoized render function with batch updates
let lastAgentsHash = '';

function renderAgentsList() {
  const container = document.getElementById('agentsList');
  if (!container) return;
  
  // Check if data actually changed
  const currentHash = JSON.stringify(roles.map(r => r.role_id));
  if (currentHash === lastAgentsHash) return;
  lastAgentsHash = currentHash;
  
  if (roles.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">&#128100;</div>
        <div class="empty-state-title">No agents yet</div>
        <div class="empty-state-description">Create your first agent to start orchestrating workflows.</div>
      </div>
    `;
    return;
  }
  
  // Build HTML string once (faster than multiple DOM manipulations)
  const html = roles.map(role => {
    const caps = role.capability_ids || [];
    const connectors = caps.map(capId => {
      const cap = capabilities.find(c => c.capability_id === capId);
      return cap?.connector_binding;
    }).filter(Boolean);
    const uniqueConnectors = [...new Set(connectors)];
    
    return `
      <div class="agent-card">
        <h4>
          ${escapeHtml(role.title || role.role_id)}
          <span class="status-badge ${escapeHtml(role.status)}">${escapeHtml(role.status)}</span>
        </h4>
        <div class="capabilities">
          ${caps.length > 0 ? caps.map(escapeHtml).join(', ') : 'No capabilities'}
        </div>
        <div class="capabilities">
          model: ${escapeHtml(role.preferred_model_id || '(default routing)')}
        </div>
        <div class="connector-badges">
          ${uniqueConnectors.map(c => `<span class="connector-badge ${escapeHtml(c)}">${escapeHtml(c)}</span>`).join('')}
        </div>
      </div>
    `;
  }).join('');
  
  // Single DOM write
  requestAnimationFrame(() => {
    container.innerHTML = html;
  });
}

// Utility to prevent XSS
function escapeHtml(text) {
  if (typeof text !== 'string') return text;
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function renderCapabilitiesSelector() {
  const container = document.getElementById('capabilitiesSelector');
  if (!container) return;
  
  container.innerHTML = capabilities.map(cap => `
    <label class="checkbox-item">
      <input type="checkbox" value="${cap.capability_id}" 
             ${selectedCapabilities.includes(cap.capability_id) ? 'checked' : ''}
             data-capability-id="${cap.capability_id}">
      <div class="cap-info">
        <div class="cap-id">${escapeHtml(cap.capability_id)}</div>
        <div class="cap-desc">${escapeHtml(cap.description || '')}</div>
      </div>
      ${cap.connector_binding ? `<span class="cap-connector">${escapeHtml(cap.connector_binding)}</span>` : ''}
    </label>
  `).join('');
  
  // Attach event listeners after DOM insertion (CSP compliant)
  container.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
    checkbox.addEventListener('change', (e) => {
      toggleCapability(e.target.dataset.capabilityId);
    });
  });
}

function renderPoliciesSelector() {
  const container = document.getElementById('policiesSelector');
  if (!container) return;
  
  container.innerHTML = policies.map(pol => `
    <label class="checkbox-item">
      <input type="checkbox" value="${pol.policy_id}"
             ${selectedPolicies.includes(pol.policy_id) ? 'checked' : ''}
             data-policy-id="${pol.policy_id}">
      <div class="cap-info">
        <div class="cap-id">${escapeHtml(pol.policy_id)}</div>
        <div class="cap-desc">${escapeHtml(pol.description || '')}</div>
      </div>
    </label>
  `).join('');
  
  // Attach event listeners after DOM insertion (CSP compliant)
  container.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
    checkbox.addEventListener('change', (e) => {
      togglePolicy(e.target.dataset.policyId);
    });
  });
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
    showNotification('Please enter a capability ID', 'error');
    return;
  }
  
  const btn = document.getElementById('addCapability');
  btn.setAttribute('aria-busy', 'true');
  btn.disabled = true;
  
  const payload = {
    capability_id: capId,
    description: desc || capId,
    connector_binding: connector,
    status: 'active'
  };
  
  try {
    await call('/api/capabilities', 'POST', payload);
    document.getElementById('newCapId').value = '';
    document.getElementById('newCapDesc').value = '';
    
    capabilities = await call('/api/capabilities');
    renderCapabilitiesSelector();
    selectedCapabilities.push(capId);
    renderCapabilitiesSelector();
    showNotification('Capability added', 'success');
  } finally {
    btn.removeAttribute('aria-busy');
    btn.disabled = false;
  }
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
    preferred_model_id: document.getElementById('agentPreferredModel').value || null,
    capability_ids: selectedCapabilities,
    policy_ids: selectedPolicies,
    status: 'active'
  };
  setOut('agentReview', review);
}

async function createAgent() {
  const btn = document.getElementById('wizardCreate');
  btn.setAttribute('aria-busy', 'true');
  btn.disabled = true;
  
  try {
    const payload = {
      role: {
        role_id: document.getElementById('agentId').value,
        title: document.getElementById('agentTitle').value,
        domain_pack: document.getElementById('agentDomainPack').value,
        preferred_model_id: document.getElementById('agentPreferredModel').value || null,
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
    showNotification('Agent created successfully', 'success');
    
    selectedCapabilities = [];
    selectedPolicies = [];
    const modelSelect = document.getElementById('agentPreferredModel');
    if (modelSelect) modelSelect.value = '';
    wizardStep = 1;
    switchWizardStep(1);
    switchTab('view-agents', 'agents-list');
    await loadAgentsData();
  } finally {
    btn.removeAttribute('aria-busy');
    btn.disabled = false;
  }
}

async function loadWorkflowsData() {
  try {
    workflows = await call('/api/workflows');
    renderWorkflowsList();
  } catch (e) {
    showNotification('Failed to load workflows', 'error');
  }
}

let lastWorkflowsHash = '';

function renderWorkflowsList() {
  const container = document.getElementById('workflowsList');
  if (!container) return;
  
  // Check if data actually changed
  const currentHash = JSON.stringify(workflows.map(w => w.workflow_id + w.version));
  if (currentHash === lastWorkflowsHash) return;
  lastWorkflowsHash = currentHash;
  
  if (workflows.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">&#128260;</div>
        <div class="empty-state-title">No workflows yet</div>
        <div class="empty-state-description">Create your first workflow to orchestrate agent tasks.</div>
      </div>
    `;
    return;
  }
  
  // Build HTML string once
  const html = workflows.map(wf => {
    const ir = wf.compiled_ir || {};
    const steps = ir.steps || [];
    const title = escapeHtml(wf.metadata?.title || wf.workflow_id);
    const status = escapeHtml(wf.status);
    
    return `
      <div class="card workflow-card">
        <h4>${title} <span class="status-badge ${status}">${status}</span></h4>
        <div class="workflow-meta">
          Version: ${wf.version} | Steps: ${steps.length}
        </div>
        ${steps.length > 0 ? `
          <div class="workflow-steps">
            ${steps.slice(0, 3).map(s => `
              <div class="step-preview">
                <div class="step-title">${escapeHtml(s.step_id)}</div>
                <div class="step-owner">owned by: <span class="owner-badge">${escapeHtml(s.owned_by)}</span></div>
              </div>
            `).join('')}
            ${steps.length > 3 ? `<div class="more-steps">+${steps.length - 3} more steps</div>` : ''}
          </div>
        ` : ''}
      </div>
    `;
  }).join('');
  
  // Single DOM write
  requestAnimationFrame(() => {
    container.innerHTML = html;
  });
}

// Debounced workflow preview update
let previewRAF = null;
let previewTimeout = null;

function updateWorkflowPreview() {
  // Cancel any pending update
  if (previewRAF) cancelAnimationFrame(previewRAF);
  if (previewTimeout) clearTimeout(previewTimeout);
  
  // Debounce to prevent excessive updates on fast typing
  previewTimeout = setTimeout(() => {
    previewRAF = requestAnimationFrame(() => {
      const markdown = document.getElementById('workflowMarkdown').value;
      const preview = document.getElementById('workflowPreview');
      const validation = document.getElementById('workflowValidation');
      
      if (!markdown.trim()) {
        preview.innerHTML = '<p class="hint">Start typing workflow markdown to see a preview...</p>';
        validation.innerHTML = '';
        return;
      }
      
      // Use DocumentFragment for better performance
      const steps = [];
      let currentStep = null;
      
      // Single pass through lines
      const lines = markdown.split('\n');
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        if (line.startsWith('### Step')) {
          if (currentStep) steps.push(currentStep);
          currentStep = { title: line.replace('### ', '').trim(), owned_by: '', participants: [] };
        } else if (currentStep && line.includes('owned_by:')) {
          currentStep.owned_by = line.split('owned_by:')[1]?.trim() || '';
        } else if (currentStep && line.includes('participants:')) {
          const parts = line.split('participants:')[1]?.trim().replace(/[\[\]]/g, '') || '';
          currentStep.participants = parts ? parts.split(',').map(s => s.trim()).filter(Boolean) : [];
        }
      }
      if (currentStep) steps.push(currentStep);
      
      if (steps.length === 0) {
        preview.innerHTML = '<p class="hint">Add steps using "### Step N: Title" format to see agent assignments.</p>';
      } else {
        // Build HTML string once
        const html = steps.map(s => `
          <div class="step-preview">
            <div class="step-title">${escapeHtml(s.title)}</div>
            <div class="step-owner">
              owned by: <span class="owner-badge">${escapeHtml(s.owned_by || 'unassigned')}</span>
              ${s.participants.length > 0 ? `| participants: ${s.participants.map(escapeHtml).join(', ')}` : ''}
            </div>
          </div>
        `).join('');
        preview.innerHTML = html;
      }
    });
  }, 100); // 100ms debounce
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
    showNotification('Please enter a workflow ID', 'error');
    return;
  }
  
  const btn = document.getElementById('publishWorkflow');
  btn.setAttribute('aria-busy', 'true');
  btn.disabled = true;
  
  try {
    await call('/api/workflows/publish', 'POST', payload);
    showNotification('Workflow published successfully', 'success');
    await loadWorkflowsData();
  } finally {
    btn.removeAttribute('aria-busy');
    btn.disabled = false;
  }
}

async function workflowAction(name) {
  const wf = document.getElementById('wfVersionActionId').value;
  const ver = Number(document.getElementById('wfVersionAction').value);
  if (!wf || !ver) {
    showNotification('workflow_id and version required', 'error');
    return;
  }
  if (['archive', 'rollback'].includes(name) && !confirmDanger(`${name} workflow version?`)) return;
  
  await call(`/api/workflows/${encodeURIComponent(wf)}/${ver}/${name}`, 'POST');
  showNotification(`Workflow ${name} successful`, 'success');
  await loadWorkflowsData();
}

async function loadWorkflowDiff() {
  const workflowId = document.getElementById('wfDiffId').value.trim();
  const fromVersion = Number(document.getElementById('wfDiffFrom').value);
  const toVersion = Number(document.getElementById('wfDiffTo').value);
  if (!workflowId || !fromVersion || !toVersion) {
    showNotification('workflow_id, from_version, and to_version are required', 'error');
    return;
  }
  const result = await call(
    `/api/workflows/${encodeURIComponent(workflowId)}/diff/${fromVersion}/${toVersion}`
  );
  setOut('workflowDiffOut', result);
}

async function loadTasksData() {
  try {
    tasks = await call(`/api/tasks?organization_id=${encodeURIComponent(currentOrgId)}`);
    renderAllTasksList();
  } catch (e) {
    // Silently handle load errors
    if (process.env.NODE_ENV === 'development') {
      console.error('Failed to load tasks:', e);
    }
  }
}

let lastTasksHash = '';

function renderAllTasksList() {
  const container = document.getElementById('allTasksList');
  if (!container) return;
  
  // Check if data actually changed
  const currentHash = JSON.stringify(tasks.map(t => t.task_id + t.current_status));
  if (currentHash === lastTasksHash) return;
  lastTasksHash = currentHash;
  
  if (tasks.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">&#9654;</div>
        <div class="empty-state-title">No tasks yet</div>
        <div class="empty-state-description">Use the Console tab to create and run your first task.</div>
      </div>
    `;
    return;
  }
  
  // Build HTML string once with XSS protection
  const html = tasks.map(task => {
    const taskId = escapeHtml(task.task_id);
    const status = escapeHtml(task.current_status);
    const request = escapeHtml(task.raw_request?.substring(0, 100) || '');
    const truncated = task.raw_request?.length > 100 ? '...' : '';
    
    return `
      <div class="task-item">
        <div class="task-info">
          <div class="task-id">${taskId}</div>
          <div class="task-request">${request}${truncated}</div>
        </div>
        <span class="task-status ${status}">${status}</span>
      </div>
    `;
  }).join('');
  
  // Single DOM write
  requestAnimationFrame(() => {
    container.innerHTML = html;
  });
}

async function intakeTask() {
  const workflowId = document.getElementById('taskWorkflowId').value.trim();
  const workflowVersionRaw = document.getElementById('taskWorkflowVersion').value.trim();
  const payload = {
    request: document.getElementById('taskRequest').value,
    domain_pack: document.getElementById('taskDomain').value || 'custom',
    organization_id: currentOrgId,
    async_run: document.getElementById('taskAsync').checked,
    workflow_id: workflowId || null,
    workflow_version: workflowVersionRaw ? Number(workflowVersionRaw) : null,
    fanout: document.getElementById('taskFanout').checked,
  };
  
  if (!payload.request) {
    showNotification('Please enter a request', 'error');
    return;
  }
  
  const result = await call('/api/tasks/intake', 'POST', payload);
  setOut('tasksOut', result);
  if (result.task?.task_id) {
    document.getElementById('taskId').value = result.task.task_id;
  } else if (result.tasks?.length > 0) {
    document.getElementById('taskId').value = result.tasks[0].task_id;
  }
  await loadTasksData();
}

async function runTask() {
  const taskId = document.getElementById('taskId').value;
  if (!taskId) {
    showNotification('Please enter a task ID', 'error');
    return;
  }
  const result = await call(`/api/tasks/${encodeURIComponent(taskId)}/run`, 'POST');
  setOut('tasksOut', result);
  await loadTasksData();
}

async function retryTask() {
  const taskId = document.getElementById('taskId').value;
  if (!taskId) {
    showNotification('Please enter a task ID', 'error');
    return;
  }
  const result = await call(`/api/tasks/${encodeURIComponent(taskId)}/retry`, 'POST');
  setOut('tasksOut', result);
  await loadTasksData();
}

async function traceTask() {
  const taskId = document.getElementById('taskId').value;
  if (!taskId) {
    showNotification('Please enter a task ID', 'error');
    return;
  }
  const result = await call(`/api/tasks/${encodeURIComponent(taskId)}/trace`);
  setOut('tasksOut', result);
}

function stopTaskStream() {
  if (taskEventSource) {
    taskEventSource.close();
    taskEventSource = null;
    statusBar('Task stream stopped');
  }
}

async function streamTaskEvents() {
  const taskId = document.getElementById('taskId').value;
  if (!taskId) {
    showNotification('Please enter a task ID', 'error');
    return;
  }
  if (document.getElementById('authMode').value === 'token') {
    showNotification('EventSource stream currently supports auth mode "none/header". Use trace/events API for token mode.', 'error');
    return;
  }
  stopTaskStream();
  const out = document.getElementById('taskStreamOut');
  if (out) out.textContent = '';

  taskEventSource = new EventSource(`/api/tasks/${encodeURIComponent(taskId)}/events/stream`);
  taskEventSource.addEventListener('task_event', (evt) => {
    try {
      const payload = JSON.parse(evt.data);
      const line = `${payload.created_at || ''} ${payload.event_type}: ${JSON.stringify(payload.payload || {})}`;
      if (out) out.textContent += `${line}\n`;
    } catch {
      if (out) out.textContent += `${evt.data}\n`;
    }
  });
  taskEventSource.onerror = () => {
    statusBar('Task event stream closed');
    stopTaskStream();
  };
  statusBar(`Streaming events for ${taskId}`);
}

async function queryMemory() {
  const workflowId = document.getElementById('memoryWorkflowId').value.trim();
  const workflowVersion = Number(document.getElementById('memoryWorkflowVersion').value);
  const domainPack = document.getElementById('memoryDomainPack').value.trim();
  if (!domainPack || !workflowId || !workflowVersion) {
    showNotification('Memory query needs domain_pack, workflow_id and workflow_version', 'error');
    return;
  }
  const payload = {
    organization_id: currentOrgId,
    domain_pack: domainPack,
    workflow_id: workflowId,
    workflow_version: workflowVersion,
    role: document.getElementById('memoryRole').value.trim() || 'any',
    memory_type: document.getElementById('memoryType').value,
    active_only: document.getElementById('memoryActiveOnly').checked,
  };
  const result = await call('/api/memory/query', 'POST', payload);
  setOut('memoryOut', result);
}

async function invalidateMemory() {
  const workflowId = document.getElementById('memoryWorkflowId').value.trim();
  const workflowVersion = Number(document.getElementById('memoryWorkflowVersion').value);
  const domainPack = document.getElementById('memoryDomainPack').value.trim();
  if (!domainPack || !workflowId || !workflowVersion) {
    showNotification('Memory invalidation needs domain_pack, workflow_id and workflow_version', 'error');
    return;
  }
  const payload = {
    organization_id: currentOrgId,
    domain_pack: domainPack,
    workflow_id: workflowId,
    workflow_version: workflowVersion,
    role: document.getElementById('memoryRole').value.trim() || 'any',
    hard: document.getElementById('memoryHardInvalidate').checked,
  };
  const result = await call('/api/memory/invalidate', 'POST', payload);
  setOut('memoryOut', result);
}

async function markTask(status) {
  const taskId = document.getElementById('taskId').value;
  const reason = document.getElementById('markReason').value;
  if (!taskId) {
    showNotification('Please enter a task ID', 'error');
    return;
  }
  const result = await call(`/api/tasks/${encodeURIComponent(taskId)}/mark/${status}?reason=${encodeURIComponent(reason)}`, 'POST');
  setOut('tasksOut', result);
  await loadTasksData();
}

function setDesignerDirty(flag = true) {
  designerDirty = flag;
}

function getDesignerRole(roleId) {
  if (!designerDraft) return null;
  return (designerDraft.roles || []).find((role) => role.role_id === roleId) || null;
}

function getDesignerWorkflow(workflowId) {
  if (!designerDraft) return null;
  return (designerDraft.workflows || []).find((workflow) => workflow.workflow_id === workflowId) || null;
}

function renderTopologyTable(targetId, items, onDelete) {
  const target = document.getElementById(targetId);
  if (!target) return;
  if (!items || items.length === 0) {
    target.innerHTML = '<p class="hint">No entries yet.</p>';
    return;
  }
  target.innerHTML = items.map((item) => {
    const id = item.group_id || item.membership_id || item.edge_id || `${item.role_id || ''}`;
    return `
      <div class="topology-row">
        <pre>${escapeHtml(JSON.stringify(item, null, 2))}</pre>
        <button class="danger topology-delete-btn" data-id="${escapeHtml(id)}">Delete</button>
      </div>
    `;
  }).join('');
  target.querySelectorAll('.topology-delete-btn').forEach((btn) => {
    btn.addEventListener('click', () => onDelete(btn.dataset.id));
  });
}

function renderTopologyGraph() {
  const container = document.getElementById('topologyGraphCanvas');
  if (!container) return;
  if (!topologyGraph || !Array.isArray(topologyGraph.nodes)) {
    container.innerHTML = '<p class="hint">No topology loaded.</p>';
    return;
  }
  const filter = (document.getElementById('topologyFilter')?.value || '').toLowerCase().trim();
  const visibleNodes = topologyGraph.nodes.filter((node) => {
    if (!filter) return true;
    return `${node.id} ${node.label}`.toLowerCase().includes(filter);
  });
  const visibleIds = new Set(visibleNodes.map((node) => node.id));
  const visibleEdges = (topologyGraph.edges || []).filter((edge) => visibleIds.has(edge.from) && visibleIds.has(edge.to));

  const positions = new Map();
  const roleNodes = visibleNodes.filter((node) => node.kind === 'role');
  const groupNodes = visibleNodes.filter((node) => node.kind === 'group');
  roleNodes.forEach((node, idx) => {
    positions.set(node.id, { x: 120 + (idx % 3) * 280, y: 100 + Math.floor(idx / 3) * 140 });
  });
  groupNodes.forEach((node, idx) => {
    positions.set(node.id, { x: 220 + (idx % 3) * 280, y: 70 + Math.floor(idx / 3) * 140 });
  });

  const width = 980;
  const height = Math.max(360, 180 + Math.ceil(Math.max(roleNodes.length, groupNodes.length) / 3) * 170);
  const lines = visibleEdges.map((edge) => {
    const from = positions.get(edge.from);
    const to = positions.get(edge.to);
    if (!from || !to) return '';
    const stroke = edge.kind === 'membership' ? '#2185d0' : '#16a34a';
    return `<line x1="${from.x}" y1="${from.y}" x2="${to.x}" y2="${to.y}" stroke="${stroke}" stroke-width="2" />`;
  }).join('\n');
  const nodesSvg = visibleNodes.map((node) => {
    const pos = positions.get(node.id);
    if (!pos) return '';
    const isRole = node.kind === 'role';
    const fill = isRole ? '#1f2937' : '#7c2d12';
    const stroke = isRole ? '#60a5fa' : '#fb923c';
    return `
      <g>
        <rect x="${pos.x - 90}" y="${pos.y - 24}" width="180" height="48" rx="10" fill="${fill}" stroke="${stroke}" />
        <text x="${pos.x}" y="${pos.y - 6}" text-anchor="middle" fill="#f8fafc" font-size="12" font-weight="700">${escapeHtml(node.label || node.id)}</text>
        <text x="${pos.x}" y="${pos.y + 12}" text-anchor="middle" fill="#cbd5e1" font-size="11">${escapeHtml(node.kind)}</text>
      </g>
    `;
  }).join('\n');

  container.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Memory topology graph">
      ${lines}
      ${nodesSvg}
    </svg>
  `;
  setOut('topologyValidationOut', topologyGraph.validation || {});
}

async function refreshTopologyGraph() {
  topologyGraph = await call(`/api/memory/topology/graph?org_id=${encodeURIComponent(currentOrgId)}`);
  renderTopologyGraph();
}

async function loadTopologyLists() {
  const [groups, memberships, edges] = await Promise.all([
    call(`/api/memory/groups?org_id=${encodeURIComponent(currentOrgId)}`),
    call(`/api/memory/memberships?org_id=${encodeURIComponent(currentOrgId)}`),
    call(`/api/memory/edges?org_id=${encodeURIComponent(currentOrgId)}`),
  ]);
  renderTopologyTable('topologyGroupsList', groups, async (groupId) => {
    await call(`/api/memory/groups/${encodeURIComponent(groupId)}?org_id=${encodeURIComponent(currentOrgId)}`, 'DELETE');
    await loadTopologyLists();
    await refreshTopologyGraph();
  });
  renderTopologyTable('topologyMembershipsList', memberships, async (membershipId) => {
    await call(`/api/memory/memberships/${encodeURIComponent(membershipId)}`, 'DELETE');
    await loadTopologyLists();
    await refreshTopologyGraph();
  });
  renderTopologyTable('topologyEdgesList', edges, async (edgeId) => {
    await call(`/api/memory/edges/${encodeURIComponent(edgeId)}`, 'DELETE');
    await loadTopologyLists();
    await refreshTopologyGraph();
  });
}

async function saveTopologyGroup() {
  const groupId = document.getElementById('topologyGroupId').value.trim();
  if (!groupId) {
    showNotification('group_id is required', 'error');
    return;
  }
  const payload = {
    group_id: groupId,
    organization_id: currentOrgId,
    title: document.getElementById('topologyGroupTitle').value.trim() || groupId,
    description: '',
    visibility: 'shared',
    owner_role_id: document.getElementById('topologyGroupOwner').value.trim() || null,
    status: 'active',
  };
  await call('/api/memory/groups', 'POST', payload);
  document.getElementById('topologyGroupId').value = '';
  await loadTopologyLists();
  await refreshTopologyGraph();
}

async function saveTopologyMembership() {
  const groupId = document.getElementById('topologyMembershipGroup').value.trim();
  const roleId = document.getElementById('topologyMembershipRole').value.trim();
  if (!groupId || !roleId) {
    showNotification('group_id and role_id are required', 'error');
    return;
  }
  const payload = {
    organization_id: currentOrgId,
    group_id: groupId,
    role_id: roleId,
    access: document.getElementById('topologyMembershipAccess').value,
    status: 'active',
  };
  await call('/api/memory/memberships', 'POST', payload);
  await loadTopologyLists();
  await refreshTopologyGraph();
}

async function saveTopologyEdge() {
  const parentRoleId = document.getElementById('topologyParentRole').value.trim();
  const childRoleId = document.getElementById('topologyChildRole').value.trim();
  if (!parentRoleId || !childRoleId) {
    showNotification('parent_role_id and child_role_id are required', 'error');
    return;
  }
  const payload = {
    organization_id: currentOrgId,
    parent_role_id: parentRoleId,
    child_role_id: childRoleId,
    shared_group_id: document.getElementById('topologySharedGroup').value.trim() || null,
    status: 'active',
  };
  await call('/api/memory/edges', 'POST', payload);
  await loadTopologyLists();
  await refreshTopologyGraph();
}

function renderDesignerRoleInspector() {
  const role = getDesignerRole(selectedDesignerRoleId);
  const id = document.getElementById('designerSelectedRoleId');
  const title = document.getElementById('designerSelectedRoleTitle');
  const domain = document.getElementById('designerSelectedRoleDomain');
  const capabilitiesInput = document.getElementById('designerSelectedRoleCapabilities');
  if (!id || !title || !domain || !capabilitiesInput) return;
  if (!role) {
    id.value = '';
    title.value = '';
    domain.value = '';
    capabilitiesInput.value = '';
    return;
  }
  id.value = role.role_id;
  title.value = role.title || role.role_id;
  domain.value = role.domain_pack || 'custom';
  capabilitiesInput.value = (role.capability_ids || []).join(', ');
}

function renderDesignerWorkflowOptions() {
  const select = document.getElementById('designerWorkflowSelect');
  if (!select || !designerDraft) return;
  const workflowsList = designerDraft.workflows || [];
  if (workflowsList.length === 0) {
    select.innerHTML = '<option value="">(no workflows)</option>';
    selectedDesignerWorkflowId = null;
    return;
  }
  if (!selectedDesignerWorkflowId || !workflowsList.some((wf) => wf.workflow_id === selectedDesignerWorkflowId)) {
    selectedDesignerWorkflowId = workflowsList[0].workflow_id;
  }
  select.innerHTML = workflowsList.map((wf) => `<option value="${escapeHtml(wf.workflow_id)}">${escapeHtml(wf.workflow_id)}</option>`).join('');
  select.value = selectedDesignerWorkflowId;
}

function renderDesignerSteps() {
  const container = document.getElementById('designerStepsList');
  if (!container) return;
  const workflow = getDesignerWorkflow(selectedDesignerWorkflowId);
  if (!workflow) {
    container.innerHTML = '<p class="hint">Select or create a workflow to manage steps.</p>';
    return;
  }
  const steps = workflow.steps || [];
  if (!selectedDesignerStepId || !steps.some((step) => step.step_id === selectedDesignerStepId)) {
    selectedDesignerStepId = steps[0]?.step_id || null;
  }
  container.innerHTML = steps.map((step) => `
    <div class="designer-step-card ${step.step_id === selectedDesignerStepId ? 'selected' : ''}" data-step-id="${escapeHtml(step.step_id)}">
      <div class="row">
        <strong>${escapeHtml(step.step_id)}</strong>
        <button class="danger designer-step-delete" data-step-id="${escapeHtml(step.step_id)}">Delete</button>
      </div>
      <input data-field="title" value="${escapeHtml(step.title || step.step_id)}" placeholder="title" />
      <input data-field="owned_by" value="${escapeHtml(step.owned_by || '')}" placeholder="owned_by" />
      <input data-field="required_capabilities" value="${escapeHtml((step.required_capabilities || []).join(', '))}" placeholder="required_capabilities csv" />
      <input data-field="on_success" value="${escapeHtml(step.on_success || 'completed')}" placeholder="on_success" />
    </div>
  `).join('');

  container.querySelectorAll('.designer-step-card').forEach((card) => {
    card.addEventListener('click', () => {
      selectedDesignerStepId = card.dataset.stepId;
      renderDesignerSteps();
    });
    const stepId = card.dataset.stepId;
    card.querySelectorAll('input').forEach((input) => {
      input.addEventListener('input', () => {
        const targetStep = steps.find((s) => s.step_id === stepId);
        if (!targetStep) return;
        if (input.dataset.field === 'required_capabilities') {
          targetStep.required_capabilities = input.value.split(',').map((s) => s.trim()).filter(Boolean);
        } else {
          targetStep[input.dataset.field] = input.value.trim();
        }
        setDesignerDirty(true);
      });
    });
  });
  container.querySelectorAll('.designer-step-delete').forEach((btn) => {
    btn.addEventListener('click', (evt) => {
      evt.stopPropagation();
      const stepId = btn.dataset.stepId;
      workflow.steps = steps.filter((step) => step.step_id !== stepId);
      setDesignerDirty(true);
      renderDesignerSteps();
    });
  });
}

function renderDesignerCanvas() {
  const canvas = document.getElementById('designerCanvas');
  if (!canvas) return;
  if (!designerDraft || !Array.isArray(designerDraft.roles) || designerDraft.roles.length === 0) {
    canvas.innerHTML = '<p class="hint">No roles yet. Add a role to start designing.</p>';
    return;
  }
  canvas.innerHTML = designerDraft.roles.map((role) => `
    <div class="designer-role-node ${role.role_id === selectedDesignerRoleId ? 'selected' : ''}" data-role-id="${escapeHtml(role.role_id)}"
      style="left:${Number(role.x || 40)}px; top:${Number(role.y || 40)}px;">
      <div class="designer-role-title">${escapeHtml(role.title || role.role_id)}</div>
      <div class="designer-role-meta">${escapeHtml(role.domain_pack || 'custom')}</div>
    </div>
  `).join('');

  canvas.querySelectorAll('.designer-role-node').forEach((node) => {
    const roleId = node.dataset.roleId;
    let dragging = false;
    let startX = 0;
    let startY = 0;
    let offsetX = 0;
    let offsetY = 0;

    node.addEventListener('click', () => {
      selectedDesignerRoleId = roleId;
      renderDesignerRoleInspector();
      renderDesignerCanvas();
    });

    node.addEventListener('mousedown', (evt) => {
      dragging = true;
      startX = evt.clientX;
      startY = evt.clientY;
      const role = getDesignerRole(roleId);
      offsetX = Number(role?.x || 0);
      offsetY = Number(role?.y || 0);
      evt.preventDefault();
    });

    window.addEventListener('mousemove', (evt) => {
      if (!dragging) return;
      const dx = evt.clientX - startX;
      const dy = evt.clientY - startY;
      const role = getDesignerRole(roleId);
      if (!role) return;
      role.x = Math.max(10, offsetX + dx);
      role.y = Math.max(10, offsetY + dy);
      node.style.left = `${role.x}px`;
      node.style.top = `${role.y}px`;
      setDesignerDirty(true);
    });

    window.addEventListener('mouseup', () => {
      dragging = false;
    });
  });
}

async function loadDesignerDraft() {
  const record = await call(`/api/designer/draft?org_id=${encodeURIComponent(currentOrgId)}`);
  designerDraft = record.draft || { roles: [], workflows: [], memory_topology: {} };
  setDesignerDirty(false);
  selectedDesignerRoleId = designerDraft.roles?.[0]?.role_id || null;
  selectedDesignerWorkflowId = designerDraft.workflows?.[0]?.workflow_id || null;
  renderDesignerRoleInspector();
  renderDesignerCanvas();
  renderDesignerWorkflowOptions();
  renderDesignerSteps();
}

async function saveDesignerDraft() {
  if (!designerDraft) return;
  const result = await call(`/api/designer/draft?org_id=${encodeURIComponent(currentOrgId)}`, 'PUT', { draft: designerDraft });
  setDesignerDirty(false);
  setOut('designerValidationOut', result.validation || {});
  showNotification(`Draft saved (version ${result.version})`, 'success');
}

async function validateDesignerDraft() {
  if (!designerDraft) return;
  const result = await call(`/api/designer/validate?org_id=${encodeURIComponent(currentOrgId)}`, 'POST', { draft: designerDraft });
  setOut('designerValidationOut', result);
  if (result.ok) showNotification('Designer draft is valid', 'success');
  else showNotification('Designer draft has validation errors', 'error');
}

async function generateDesignerBundle() {
  if (!designerDraft) return;
  const result = await call(`/api/designer/bundle/generate?org_id=${encodeURIComponent(currentOrgId)}`, 'POST', { draft: designerDraft });
  designerGeneratedBundle = result;
  setOut('designerBundleOut', result.bundle_yaml || result);
  setOut('designerValidationOut', result.validation || {});
  if (!result.ok) {
    showNotification('Bundle generated with validation issues', 'error');
  } else {
    showNotification('Bundle generated', 'success');
  }
}

async function applyDesignerBundle() {
  if (!designerDraft) return;
  const result = await call(`/api/designer/bundle/apply?org_id=${encodeURIComponent(currentOrgId)}`, 'POST', { draft: designerDraft });
  setOut('designerBundleOut', result.bundle_yaml || result);
  setOut('designerValidationOut', result);
  showNotification('Designer bundle applied', 'success');
  await refreshAll();
}

function exportDesignerBundle() {
  if (!designerGeneratedBundle?.bundle_yaml) {
    showNotification('Generate bundle first', 'error');
    return;
  }
  const blob = new Blob([designerGeneratedBundle.bundle_yaml], { type: 'application/x-yaml' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${currentOrgId}.designer.bundle.yaml`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function showDesignerDrift() {
  if (!designerGeneratedBundle?.drift) {
    showNotification('Generate bundle first', 'error');
    return;
  }
  setOut('designerBundleOut', designerGeneratedBundle.drift);
}

function addDesignerRole() {
  if (!designerDraft) return;
  const roleId = document.getElementById('designerNewRoleId').value.trim();
  if (!roleId) {
    showNotification('Role ID is required', 'error');
    return;
  }
  if ((designerDraft.roles || []).some((role) => role.role_id === roleId)) {
    showNotification('Role already exists in draft', 'error');
    return;
  }
  const role = {
    role_id: roleId,
    title: document.getElementById('designerNewRoleTitle').value.trim() || roleId,
    domain_pack: document.getElementById('designerNewRoleDomain').value.trim() || 'custom',
    capability_ids: [],
    policy_ids: [],
    memory_visibility: [],
    x: 40,
    y: 40,
  };
  designerDraft.roles = [...(designerDraft.roles || []), role];
  selectedDesignerRoleId = roleId;
  setDesignerDirty(true);
  renderDesignerRoleInspector();
  renderDesignerCanvas();
}

function updateSelectedDesignerRole() {
  const role = getDesignerRole(selectedDesignerRoleId);
  if (!role) {
    showNotification('Select a role first', 'error');
    return;
  }
  role.title = document.getElementById('designerSelectedRoleTitle').value.trim() || role.role_id;
  role.domain_pack = document.getElementById('designerSelectedRoleDomain').value.trim() || 'custom';
  role.capability_ids = document.getElementById('designerSelectedRoleCapabilities').value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
  setDesignerDirty(true);
  renderDesignerCanvas();
}

function addDesignerWorkflow() {
  if (!designerDraft) return;
  const workflowId = window.prompt('Enter workflow_id');
  if (!workflowId) return;
  if ((designerDraft.workflows || []).some((wf) => wf.workflow_id === workflowId)) {
    showNotification('Workflow already exists', 'error');
    return;
  }
  const domain = designerDraft.roles?.[0]?.domain_pack || 'custom';
  const workflow = {
    workflow_id: workflowId,
    version: 1,
    title: workflowId,
    domain_pack: domain,
    intent_group: 'custom_local',
    activate: true,
    purpose: 'Generated workflow purpose.',
    required_inputs: ['request'],
    completion_criteria: 'workflow completed',
    blocked_conditions: 'blocked by validation or runtime preflight',
    failure_conditions: 'runtime execution failure',
    rules: ['Follow workflow rules.'],
    steps: [],
  };
  designerDraft.workflows = [...(designerDraft.workflows || []), workflow];
  selectedDesignerWorkflowId = workflowId;
  setDesignerDirty(true);
  renderDesignerWorkflowOptions();
  renderDesignerSteps();
}

function addDesignerStep() {
  const workflow = getDesignerWorkflow(selectedDesignerWorkflowId);
  if (!workflow) {
    showNotification('Create a workflow first', 'error');
    return;
  }
  const stepId = window.prompt('Enter step_id');
  if (!stepId) return;
  if ((workflow.steps || []).some((step) => step.step_id === stepId)) {
    showNotification('Step already exists', 'error');
    return;
  }
  const defaultOwner = designerDraft.roles?.[0]?.role_id || '';
  const steps = workflow.steps || [];
  steps.push({
    step_id: stepId,
    title: stepId,
    owned_by: defaultOwner,
    participants: [],
    required_capabilities: [],
    on_success: 'completed',
    on_blocked: 'blocked',
    on_failure: 'failed',
    state_partition: null,
  });
  workflow.steps = steps;
  selectedDesignerStepId = stepId;
  setDesignerDirty(true);
  renderDesignerSteps();
}

async function loadDesignerData() {
  await Promise.all([loadTopologyLists(), refreshTopologyGraph(), loadDesignerDraft()]);
}

function bindNavItems() {
  document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', () => switchView(item.dataset.view));
    item.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        switchView(item.dataset.view);
      }
    });
  });
  
  // Mobile menu toggle
  const mobileToggle = document.querySelector('.mobile-menu-toggle');
  const sidebar = document.querySelector('.sidebar');
  if (mobileToggle && sidebar) {
    mobileToggle.addEventListener('click', () => {
      const isOpen = sidebar.classList.toggle('is-open');
      mobileToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
      mobileToggle.innerHTML = isOpen ? '<span aria-hidden="true">&#10005;</span>' : '<span aria-hidden="true">&#9776;</span>';
    });
    
    // Close mobile menu when clicking outside
    document.addEventListener('click', (e) => {
      if (sidebar.classList.contains('is-open') && 
          !sidebar.contains(e.target) && 
          !mobileToggle.contains(e.target)) {
        sidebar.classList.remove('is-open');
        mobileToggle.setAttribute('aria-expanded', 'false');
        mobileToggle.innerHTML = '<span aria-hidden="true">&#9776;</span>';
      }
    });
  }
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

function bindKeyboardShortcuts() {
  document.addEventListener('keydown', async (evt) => {
    const target = evt.target;
    const tag = target && target.tagName ? target.tagName.toLowerCase() : '';
    const isTyping = tag === 'input' || tag === 'textarea' || target?.isContentEditable;

    if (evt.ctrlKey && !evt.shiftKey && ['1', '2', '3', '4', '5'].includes(evt.key)) {
      evt.preventDefault();
      const mapping = { '1': 'organization', '2': 'agents', '3': 'workflows', '4': 'designer', '5': 'tasks' };
      switchView(mapping[evt.key]);
      return;
    }

    if (evt.ctrlKey && evt.shiftKey && evt.key.toLowerCase() === 'r') {
      evt.preventDefault();
      await refreshAuth();
      await refreshAll();
      return;
    }

    if (evt.ctrlKey && evt.key === 'Enter' && currentView === 'tasks') {
      evt.preventDefault();
      await intakeTask();
      return;
    }

    if (!evt.ctrlKey && !evt.metaKey && !evt.altKey && evt.key === '?' && !isTyping) {
      evt.preventDefault();
      showNotification(
        'Keyboard Shortcuts: Ctrl+1/2/3/4/5 = switch views, Ctrl+Enter = intake task, Ctrl+Shift+R = refresh',
        'info',
        8000
      );
    }
  });
}

async function init() {
  applyTheme(currentTheme);
  bindNavItems();
  bindTabs();
  bindWizardSteps();
  bindKeyboardShortcuts();
  
  document.getElementById('refreshAll').addEventListener('click', async () => {
    await refreshAuth();
    await refreshAll();
  });
  document.getElementById('themeToggle').addEventListener('click', () => {
    applyTheme(currentTheme === 'dark' ? 'light' : 'dark');
  });
  document.getElementById('loadIntegrationStatus').addEventListener('click', loadIntegrationStatus);
  document.getElementById('runOrganization').addEventListener('click', runOrganizationRuntime);
  document.getElementById('refreshRuntime').addEventListener('click', refreshRuntime);
  document.getElementById('stopOrganization').addEventListener('click', stopOrganizationRuntime);
  document.getElementById('saveOrganization').addEventListener('click', saveOrganization);
  const orgSelect = document.getElementById('orgSelect');
  if (orgSelect) {
    orgSelect.addEventListener('change', async () => {
      currentOrgId = orgSelect.value || 'default';
      await loadOrganization();
      await loadIntegrationStatus();
      await loadTasksData();
      if (currentView === 'designer') await loadDesignerData();
    });
  }
  document.getElementById('orgLoad').addEventListener('click', async () => {
    const select = document.getElementById('orgSelect');
    currentOrgId = (select && select.value) ? select.value : currentOrgId;
    await loadOrganization();
    await loadIntegrationStatus();
    await loadTasksData();
    if (currentView === 'designer') await loadDesignerData();
  });
  document.getElementById('orgCreate').addEventListener('click', async () => {
    const orgId = document.getElementById('newOrgId').value.trim();
    if (!orgId) {
      showNotification('Please enter a new org ID', 'error');
      return;
    }
    await call('/api/organization', 'POST', { org_id: orgId, name: orgId });
    currentOrgId = orgId;
    document.getElementById('newOrgId').value = '';
    await loadOrganizations();
    await loadOrganization();
    await loadIntegrationStatus();
    await loadTasksData();
    if (currentView === 'designer') await loadDesignerData();
  });
  document.getElementById('applyBundle').addEventListener('click', applyBundle);
  document.getElementById('exportBundle').addEventListener('click', async () => {
    try {
      await exportBundle();
    } catch (e) {
      showNotification(e.message, 'error');
    }
  });
  
  document.getElementById('wizardPrev').addEventListener('click', () => {
    if (wizardStep > 1) switchWizardStep(wizardStep - 1);
  });
  document.getElementById('wizardNext').addEventListener('click', () => {
    if (wizardStep < 5) switchWizardStep(wizardStep + 1);
  });
  document.getElementById('wizardCreate').addEventListener('click', createAgent);
  document.getElementById('addCapability').addEventListener('click', addNewCapability);
  ['agentId', 'agentTitle', 'agentDomainPack', 'agentPreferredModel'].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('input', updateAgentReview);
    if (el && el.tagName.toLowerCase() === 'select') {
      el.addEventListener('change', updateAgentReview);
    }
  });
  
  document.getElementById('workflowMarkdown').addEventListener('input', updateWorkflowPreview);
  document.getElementById('validateWorkflow').addEventListener('click', validateWorkflow);
  document.getElementById('publishWorkflow').addEventListener('click', publishWorkflow);
  document.getElementById('activateWorkflow').addEventListener('click', () => workflowAction('activate'));
  document.getElementById('deprecateWorkflow').addEventListener('click', () => workflowAction('deprecate'));
  document.getElementById('archiveWorkflow').addEventListener('click', () => workflowAction('archive'));
  document.getElementById('rollbackWorkflow').addEventListener('click', () => workflowAction('rollback'));
  document.getElementById('loadWorkflowDiff').addEventListener('click', loadWorkflowDiff);
  
  document.getElementById('intakeTask').addEventListener('click', intakeTask);
  document.getElementById('runTask').addEventListener('click', runTask);
  document.getElementById('retryTask').addEventListener('click', retryTask);
  document.getElementById('traceTask').addEventListener('click', traceTask);
  document.getElementById('streamTask').addEventListener('click', streamTaskEvents);
  document.getElementById('stopStreamTask').addEventListener('click', stopTaskStream);
  document.getElementById('markBlocked').addEventListener('click', () => markTask('blocked'));
  document.getElementById('markFailed').addEventListener('click', () => markTask('failed'));
  document.getElementById('queryMemory').addEventListener('click', queryMemory);
  document.getElementById('invalidateMemory').addEventListener('click', invalidateMemory);

  document.getElementById('topologyAddGroup').addEventListener('click', saveTopologyGroup);
  document.getElementById('topologyAddMembership').addEventListener('click', saveTopologyMembership);
  document.getElementById('topologyAddEdge').addEventListener('click', saveTopologyEdge);
  document.getElementById('topologyRefreshGraph').addEventListener('click', refreshTopologyGraph);
  document.getElementById('topologyFilter').addEventListener('input', renderTopologyGraph);

  document.getElementById('designerLoadDraft').addEventListener('click', loadDesignerDraft);
  document.getElementById('designerSaveDraft').addEventListener('click', saveDesignerDraft);
  document.getElementById('designerValidateDraft').addEventListener('click', validateDesignerDraft);
  document.getElementById('designerGenerateBundle').addEventListener('click', generateDesignerBundle);
  document.getElementById('designerApplyBundle').addEventListener('click', applyDesignerBundle);
  document.getElementById('designerExportBundle').addEventListener('click', exportDesignerBundle);
  document.getElementById('designerDriftCheck').addEventListener('click', showDesignerDrift);
  document.getElementById('designerAddRole').addEventListener('click', addDesignerRole);
  document.getElementById('designerUpdateSelectedRole').addEventListener('click', updateSelectedDesignerRole);
  document.getElementById('designerAddWorkflow').addEventListener('click', addDesignerWorkflow);
  document.getElementById('designerAddStep').addEventListener('click', addDesignerStep);
  document.getElementById('designerWorkflowSelect').addEventListener('change', (evt) => {
    selectedDesignerWorkflowId = evt.target.value || null;
    renderDesignerSteps();
  });

  window.addEventListener('beforeunload', (evt) => {
    if (!designerDirty) return;
    evt.preventDefault();
    evt.returnValue = '';
  });
  
  try {
    await refreshAuth();
    await refreshAll();
  } catch (e) {
    statusBar(e.message);
  }
}

init();
