let csrfToken = null;

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

async function call(path, method='GET', body=null, expectsJson=true) {
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
  document.getElementById(id).textContent = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
};

function confirmDanger(msg) {
  return window.confirm(msg);
}

async function refreshAuth() {
  const me = await call('/api/auth/me');
  setOut('integrationOut', { auth: me });
  const csrf = await call('/api/auth/csrf');
  csrfToken = csrf.csrf;
}

async function refreshAll() {
  setOut('workflowsOut', await call('/api/workflows'));
  setOut('rolesOut', await call('/api/roles'));
  setOut('capsOut', await call('/api/capabilities'));
  setOut('policiesOut', await call('/api/policies'));
  setOut('promptsOut', await call('/api/prompts'));
  const providers = await call('/api/model-providers');
  const models = await call('/api/models');
  const serviceModels = await call('/api/service-models');
  setOut('modelsOut', { providers, models, service_models: serviceModels });
  setOut('schedulesOut', await call('/api/schedules'));
  setOut('tasksOut', await call('/api/tasks'));
}

function bind(id, fn) {
  document.getElementById(id).addEventListener('click', async () => {
    try { await fn(); } catch (e) { alert(e.message); }
  });
}

bind('refreshAll', async () => { await refreshAuth(); await refreshAll(); });
bind('whoAmI', async () => setOut('integrationOut', await call('/api/auth/me')));
bind('loadDocsPack', async () => {
  if (!confirmDanger('Load Docs Pack into current DB?')) return;
  setOut('integrationOut', await call('/api/bootstrap/docs-pack', 'POST'));
  await refreshAll();
});
bind('integrationStatus', async () => {
  const status = await call('/api/integrations/status');
  const health = await call('/api/integrations/health');
  const bindings = await call('/api/integrations/bindings');
  setOut('integrationOut', { status, health, bindings });
});

bind('validateWorkflow', async () => {
  const payload = {
    workflow_id: document.getElementById('wfId').value,
    version: Number(document.getElementById('wfVersion').value || 1),
    markdown: document.getElementById('workflowMarkdown').value,
  };
  setOut('workflowsOut', await call('/api/workflows/validate', 'POST', payload));
});

bind('publishWorkflow', async () => {
  const payload = {
    workflow_id: document.getElementById('wfId').value,
    version: Number(document.getElementById('wfVersion').value || 1),
    title: document.getElementById('wfTitle').value,
    domain_pack: document.getElementById('wfDomain').value,
    intent_group: document.getElementById('wfIntent').value,
    markdown: document.getElementById('workflowMarkdown').value,
    activate: document.getElementById('wfActivate').checked,
  };
  setOut('workflowsOut', await call('/api/workflows/publish', 'POST', payload));
  await refreshAll();
});

const workflowAction = (name) => async () => {
  const wf = document.getElementById('wfVersionActionId').value;
  const ver = Number(document.getElementById('wfVersionAction').value);
  if (!wf || !ver) throw new Error('workflow_id and version required');
  if (['archive','rollback'].includes(name) && !confirmDanger(`${name} workflow version?`)) return;
  setOut('workflowsOut', await call(`/api/workflows/${encodeURIComponent(wf)}/${ver}/${name}`, 'POST'));
  await refreshAll();
};

bind('activateWorkflow', workflowAction('activate'));
bind('deprecateWorkflow', workflowAction('deprecate'));
bind('archiveWorkflow', workflowAction('archive'));
bind('rollbackWorkflow', workflowAction('rollback'));

bind('loadDiff', async () => {
  const wf = document.getElementById('diffWorkflowId').value;
  const fromV = Number(document.getElementById('diffFrom').value);
  const toV = Number(document.getElementById('diffTo').value);
  setOut('workflowsOut', await call(`/api/workflows/${encodeURIComponent(wf)}/diff/${fromV}/${toV}`));
});

bind('buildAgent', async () => {
  const payload = JSON.parse(document.getElementById('agentBuilderJson').value);
  setOut('rolesOut', await call('/api/agents/builder', 'POST', payload));
  await refreshAll();
});

bind('checkCompat', async () => {
  const roleId = document.getElementById('compatRoleId').value;
  setOut('rolesOut', await call(`/api/agents/compat/${encodeURIComponent(roleId)}`));
});

bind('upsertRole', async () => {
  const payload = JSON.parse(document.getElementById('roleJson').value);
  setOut('rolesOut', await call('/api/roles', 'POST', payload));
  await refreshAll();
});

bind('deleteRole', async () => {
  const rid = document.getElementById('deleteRoleId').value;
  if (!confirmDanger(`Retire role ${rid}?`)) return;
  setOut('rolesOut', await call(`/api/roles/${encodeURIComponent(rid)}`, 'DELETE'));
  await refreshAll();
});

bind('upsertCap', async () => {
  const payload = JSON.parse(document.getElementById('capJson').value);
  setOut('capsOut', await call('/api/capabilities', 'POST', payload));
  await refreshAll();
});

bind('upsertPolicy', async () => {
  const payload = JSON.parse(document.getElementById('policyJson').value);
  setOut('policiesOut', await call('/api/policies', 'POST', payload));
  await refreshAll();
});

bind('upsertPrompt', async () => {
  const payload = JSON.parse(document.getElementById('promptJson').value);
  setOut('promptsOut', await call('/api/prompts', 'POST', payload));
  await refreshAll();
});

bind('upsertModelProvider', async () => {
  const payload = JSON.parse(document.getElementById('modelProviderJson').value);
  setOut('modelsOut', await call('/api/model-providers', 'POST', payload));
  await refreshAll();
});

bind('deleteModelProvider', async () => {
  const providerId = document.getElementById('deleteModelProviderId').value;
  if (!confirmDanger(`Delete model provider ${providerId}?`)) return;
  setOut('modelsOut', await call(`/api/model-providers/${encodeURIComponent(providerId)}`, 'DELETE'));
  await refreshAll();
});

bind('upsertModel', async () => {
  const payload = JSON.parse(document.getElementById('modelJson').value);
  setOut('modelsOut', await call('/api/models', 'POST', payload));
  await refreshAll();
});

bind('deleteModel', async () => {
  const modelId = document.getElementById('deleteModelId').value;
  if (!confirmDanger(`Delete model ${modelId}?`)) return;
  setOut('modelsOut', await call(`/api/models/${encodeURIComponent(modelId)}`, 'DELETE'));
  await refreshAll();
});

bind('upsertServiceModel', async () => {
  const payload = JSON.parse(document.getElementById('serviceModelJson').value);
  setOut('modelsOut', await call('/api/service-models', 'POST', payload));
  await refreshAll();
});

bind('deleteServiceModel', async () => {
  const serviceId = document.getElementById('deleteServiceModelId').value;
  if (!confirmDanger(`Delete binding for ${serviceId}?`)) return;
  setOut('modelsOut', await call(`/api/service-models/${encodeURIComponent(serviceId)}`, 'DELETE'));
  await refreshAll();
});

bind('resolveServiceModel', async () => {
  const serviceId = document.getElementById('resolveServiceId').value;
  setOut('modelsOut', await call(`/api/service-models/resolve/${encodeURIComponent(serviceId)}`));
});

bind('intakeTask', async () => {
  const payload = {
    request: document.getElementById('taskRequest').value,
    domain_pack: document.getElementById('taskDomain').value,
    async_run: document.getElementById('taskAsync').checked,
  };
  const out = await call('/api/tasks/intake', 'POST', payload);
  setOut('tasksOut', out);
  if (out.task?.task_id) document.getElementById('taskId').value = out.task.task_id;
  await refreshAll();
});

bind('runTask', async () => {
  const taskId = document.getElementById('taskId').value;
  setOut('tasksOut', await call(`/api/tasks/${encodeURIComponent(taskId)}/run`, 'POST'));
  await refreshAll();
});

bind('retryTask', async () => {
  const taskId = document.getElementById('taskId').value;
  setOut('tasksOut', await call(`/api/tasks/${encodeURIComponent(taskId)}/retry`, 'POST'));
  await refreshAll();
});

bind('traceTask', async () => {
  const taskId = document.getElementById('taskId').value;
  setOut('tasksOut', await call(`/api/tasks/${encodeURIComponent(taskId)}/trace`));
});

bind('streamTask', async () => {
  const taskId = document.getElementById('taskId').value;
  const res = await call(`/api/tasks/${encodeURIComponent(taskId)}/events/stream`, 'GET', null, false);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let text = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    text += decoder.decode(value, { stream: true });
    setOut('tasksOut', text);
  }
});

bind('markBlocked', async () => {
  const taskId = document.getElementById('taskId').value;
  const reason = document.getElementById('markReason').value;
  setOut('tasksOut', await call(`/api/tasks/${encodeURIComponent(taskId)}/mark/blocked?reason=${encodeURIComponent(reason)}`, 'POST'));
  await refreshAll();
});

bind('markFailed', async () => {
  const taskId = document.getElementById('taskId').value;
  const reason = document.getElementById('markReason').value;
  setOut('tasksOut', await call(`/api/tasks/${encodeURIComponent(taskId)}/mark/failed?reason=${encodeURIComponent(reason)}`, 'POST'));
  await refreshAll();
});

bind('queryMemory', async () => {
  const payload = JSON.parse(document.getElementById('memoryQueryJson').value);
  setOut('integrationOut', await call('/api/memory/query', 'POST', payload));
});

bind('invalidateMemory', async () => {
  if (!confirmDanger('Invalidate memory for supplied scope?')) return;
  const payload = JSON.parse(document.getElementById('memoryQueryJson').value);
  payload.hard = false;
  setOut('integrationOut', await call('/api/memory/invalidate', 'POST', payload));
});

bind('loadAudit', async () => {
  const taskId = document.getElementById('auditTaskId').value;
  const eventType = document.getElementById('auditEventType').value;
  const qs = new URLSearchParams();
  if (taskId) qs.set('task_id', taskId);
  if (eventType) qs.set('event_type', eventType);
  setOut('integrationOut', await call(`/api/audit/events?${qs.toString()}`));
});

bind('createIncident', async () => {
  const payload = JSON.parse(document.getElementById('incidentJson').value);
  setOut('integrationOut', await call('/api/incidents', 'POST', payload));
});

bind('listIncidents', async () => setOut('integrationOut', await call('/api/incidents')));
bind('exportIncidents', async () => setOut('integrationOut', await call('/api/incidents/export')));
bind('loadTopology', async () => setOut('integrationOut', await call('/api/topology')));

bind('upsertSchedule', async () => {
  const payload = JSON.parse(document.getElementById('scheduleJson').value);
  setOut('schedulesOut', await call('/api/schedules', 'POST', payload));
  await refreshAll();
});

bind('deleteSchedule', async () => {
  const sid = document.getElementById('deleteScheduleId').value;
  if (!confirmDanger(`Delete schedule ${sid}?`)) return;
  setOut('schedulesOut', await call(`/api/schedules/${encodeURIComponent(sid)}`, 'DELETE'));
  await refreshAll();
});

(async () => {
  try {
    await refreshAuth();
    await refreshAll();
  } catch (e) {
    statusBar(e.message);
  }
})();
