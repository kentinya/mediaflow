# ruff: noqa: E501,I001
from __future__ import annotations


INDEX_HTML = b"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>MediaFlow Operator</title>
  <link rel="stylesheet" href="/ui/style.css">
</head>
<body>
  <header><div><span class="eyebrow">MEDIAFLOW</span><h1>Operator console</h1></div>
    <div class="auth"><label for="token">API token</label><input id="token" type="password"
      autocomplete="off" spellcheck="false"><button id="connect">Connect</button>
      <button id="disconnect" class="secondary">Disconnect</button></div></header>
  <nav aria-label="Operator views">
    <button data-view="dashboard" class="active">Dashboard</button>
    <button data-view="tasks">Tasks</button>
    <button data-view="files">Files</button>
    <button data-view="file-index">FileIndex</button>
    <button data-view="jobs">Jobs</button>
    <button data-view="schedules">Schedules</button>
    <button data-view="automation">Automation</button>
    <button data-view="notifications">Notifications</button>
    <button data-view="logs">Logs</button>
    <button data-view="confirmations">Conflicts</button>
    <button data-view="recognition-reviews">Recognition</button>
    <button data-view="metadata-reviews">Metadata</button>
    <button data-view="metadata-corrections">Metadata correction</button>
    <button data-view="classification-reviews">Classification</button>
    <button data-view="configuration">Configuration</button>
    <button data-view="system">System</button>
    <button data-view="workers">Workers</button>
  </nav>
  <main>
    <div id="notice" role="status" aria-live="polite">Enter an API token to connect.</div>
    <section id="content" aria-live="polite"></section>
    <aside id="detail" hidden><button id="close-detail" class="secondary">Close</button>
      <div id="detail-content"></div></aside>
  </main>
  <script src="/ui/app.js" defer></script>
</body>
</html>
"""


STYLE_CSS = b""":root{color-scheme:dark;--bg:#101512;--panel:#19211c;--line:#34443a;--ink:#edf5ef;
--muted:#9db0a2;--accent:#b7f26c;--warn:#ffd166;--bad:#ff7b72;font:15px system-ui,sans-serif}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink)}header{padding:28px 4vw;
display:flex;align-items:end;justify-content:space-between;gap:24px;border-bottom:1px solid var(--line)}
h1{margin:.2rem 0;font-size:clamp(1.6rem,4vw,3rem)}.eyebrow{letter-spacing:.25em;color:var(--accent)}
.auth{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.auth label{color:var(--muted)}input,button,
select{border:1px solid var(--line);border-radius:6px;background:#202b24;color:var(--ink);padding:9px 12px}
button{cursor:pointer}button:hover,button:focus,.active{border-color:var(--accent)}.secondary{background:transparent}
nav{display:flex;gap:8px;padding:16px 4vw;overflow:auto}main{padding:0 4vw 48px}#notice{min-height:2.5em;
color:var(--muted)}.error{color:var(--bad)!important}.cards{display:grid;grid-template-columns:repeat(auto-fit,
minmax(150px,1fr));gap:12px}.card,table,aside{background:var(--panel);border:1px solid var(--line);
border-radius:8px}.card{padding:16px}.card strong{display:block;font-size:1.8rem;color:var(--accent)}table{
width:100%;border-collapse:collapse;overflow:hidden}th,td{padding:11px;text-align:left;border-bottom:1px solid var(--line)}
th{color:var(--muted)}tr:last-child td{border:0}aside{margin-top:18px;padding:18px}dl{display:grid;
grid-template-columns:minmax(130px,1fr) 3fr;gap:8px 16px}dt{color:var(--muted)}dd{margin:0;overflow-wrap:anywhere}
.choices{display:grid;gap:8px;margin:16px 0}.choice{display:flex;justify-content:space-between;gap:12px;
align-items:center;border:1px solid var(--line);padding:12px;border-radius:6px}.warning{color:var(--warn)}
textarea{width:100%;min-height:16rem;font:13px ui-monospace,monospace;resize:vertical}
@media(max-width:720px){header{align-items:start;flex-direction:column}.auth{width:100%}.auth input{flex:1}
table{display:block;overflow:auto}dl{grid-template-columns:1fr}}
"""


APP_JS = b"""(() => {
  'use strict';
  let token = '';
  let view = 'dashboard';
  let canManageConfiguration = false;
  let canActivateConfiguration = false;
  const content = document.getElementById('content');
  const notice = document.getElementById('notice');
  const detail = document.getElementById('detail');
  const detailContent = document.getElementById('detail-content');
  const tokenInput = document.getElementById('token');

  const text = (tag, value, className) => {
    const node = document.createElement(tag);
    node.textContent = value === null || value === undefined ? '-' : String(value);
    if (className) node.className = className;
    return node;
  };
  const clear = node => { while (node.firstChild) node.removeChild(node.firstChild); };
  const message = (value, failed = false) => {
    notice.textContent = value;
    notice.className = failed ? 'error' : '';
  };
  const errorText = error => {
    const details = error && error.details;
    const fragments = [error && error.message ? error.message : String(error)];
    if (details && details.currentRevisionId) {
      fragments.push(`Current Active: ${details.currentRevisionId} ` +
        `(${details.currentDigest || '-'})`);
    } else if (details && details.revisionId) {
      fragments.push(`Revision: ${details.revisionId} (${details.digest || '-'})`);
    }
    if (details && details.continuationId) {
      fragments.push(`Continuation: ${details.continuationId} ` +
        `(Job ${details.jobId || '-'}; status ${details.status || '-'})`);
    }
    if (details && details.durableState) fragments.push(`State: ${details.durableState}`);
    if (details && details.sideEffects) fragments.push(`Side effects: ${details.sideEffects}`);
    if (details && details.stage) fragments.push(`Stage: ${details.stage}`);
    if (details && details.category) fragments.push(`Category: ${details.category}`);
    if (details && details.path !== undefined) fragments.push(`Path: ${details.path || '<root>'}`);
    if (details && details.retrySafe !== undefined) {
      fragments.push(`Retry safe: ${details.retrySafe ? 'YES' : 'NO'}`);
    }
    if (details && details.referenceCount !== undefined) {
      fragments.push(`References: ${details.referenceCount}`);
      if (details.referencesTruncated) fragments.push('Reference labels truncated; update references first.');
      const structured = details.referenceEvidence && Array.isArray(details.referenceEvidence.items) ?
        details.referenceEvidence.items : (Array.isArray(details.referenceItems) ? details.referenceItems : []);
      if (structured.length) {
        const labels = structured.map(reference => reference.label ||
          `${reference.section || 'configuration'}:${reference.id || '-'}.${reference.field || '-'}`);
        fragments.push(`Referrers: ${labels.join(', ')}`);
      } else if (Array.isArray(details.references) && details.references.length) {
        fragments.push(`Referrers: ${details.references.join(', ')}`);
      }
    }
    if (details && details.nextAction) fragments.push(`Next action: ${details.nextAction}`);
    return fragments.join(' ');
  };
  async function api(path, options = {}) {
    if (!token) throw new Error('API token is required');
    const headers = {'Authorization': `Bearer ${token}`};
    if (options.body) headers['Content-Type'] = 'application/json';
    const response = await fetch(path, {...options, headers});
    const document = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = new Error((document.error && document.error.message) ||
        `Request failed (${response.status})`);
      error.details = document.error && document.error.details;
      throw error;
    }
    return document;
  }
  const field = (list, label, value) => {
    list.append(text('dt', label)); list.append(text('dd', value));
  };
  function cards(values) {
    const grid = text('div', '', 'cards');
    values.forEach(([label, value]) => {
      const card = text('article', '', 'card');
      card.append(text('span', label), text('strong', value)); grid.append(card);
    });
    return grid;
  }
  function renderDashboard(data) {
    clear(content);
    content.append(text('h2', 'Dashboard'));
    content.append(cards([
      ['Resource libraries', data.resource_libraries], ['Media libraries', data.media_libraries],
      ['Files', data.files && data.files.total], ['Tasks', data.tasks && data.tasks.total],
      ['Jobs', data.jobs && data.jobs.total], ['Pending conflicts', data.pending_confirmations],
      ['Metadata reviews', data.pending_metadata_reviews],
      ['Classification reviews', data.pending_classification_reviews],
      ['Dead-letter notifications', data.dead_letter_notifications]
    ]));
    const failures = (data.recent_failures || []).map(item => [item.kind, item.status,
      item.category, item.occurred_at]);
    content.append(text('h3', 'Recent failures'), table(['Kind', 'Status', 'Category', 'Time'], failures));
  }
  async function renderSystem() {
    const data = await api('/api/v1/system/status');
    clear(content); content.append(text('h2', 'System status'));
    content.append(text('p', 'Paths, templates, endpoints, environment variables, and secrets are intentionally hidden.',
      'warning'));
    const system = data.system || {};
    content.append(cards([
      ['Application', system.application_version], ['Python', system.python_version],
      ['Python supported', system.python_supported], ['Runtime schema', system.runtime_schema_version],
      ['Platform', system.platform], ['Configuration valid', system.configuration_valid]
      , ['Maximum active jobs', system.maximum_active_jobs]
      , ['Stale job age (seconds)', system.stale_job_age_seconds]
    ]));
    content.append(actionButton('Refresh system status', renderSystem));
    const sections = [
      ['Storages', 'storages', ['id', 'type', 'read_only']],
      ['Resource libraries', 'resource_libraries', ['id', 'storage_id', 'enabled', 'scan_mode']],
      ['Media libraries', 'media_libraries', ['id', 'storage_id', 'enabled']],
      ['Recognition mappings', 'recognition_type_policies', ['recognition_type_id',
        'metadata_policy_id', 'naming_policy_id', 'classification_policy_id', 'organize_policy_id']],
      ['Metadata policies', 'metadata_policies', ['id', 'provider_id', 'query_type', 'enabled']],
      ['Naming policies', 'naming_policies', ['id', 'media_type_mode', 'enabled']],
      ['Classification policies', 'classification_policies', ['id', 'rule_count', 'enabled']],
      ['Organize policies', 'organize_policies', ['id', 'operation', 'conflict_strategy']]
    ];
    sections.forEach(([label, key, fields]) => {
      const section = data[key] || {items: [], total: 0, truncated: false};
      content.append(text('h3', `${label} (${section.total || 0})`));
      if (section.truncated) content.append(text('p', 'This section is truncated.', 'warning'));
      const items = section.items || [];
      content.append(table(fields, items.map(item => fields.map(fieldName => item[fieldName]))));
    });
  }
  async function renderWorkers() {
    const [readiness, list] = await Promise.all([
      api('/api/v1/workers/readiness'),
      api('/api/v1/workers?limit=50')
    ]);
    clear(content); content.append(text('h2', 'Processing workers'));
    content.append(text('p', 'Read-only projection of registered Processing Workers. The Operator UI never supervises, starts, or stops a Worker.', 'hint'));
    content.append(cards([
      ['Ready', readiness.ready],
      ['Condition', readiness.condition],
      ['Active workers', readiness.activeWorkersCount],
      ['Side effects', readiness.sideEffects],
      ['Retry safe', readiness.retrySafe],
      ['Next action', readiness.nextAction],
      ['Durable state', readiness.durableState]
    ]));
    const items = (list && list.workers) || [];
    content.append(text('h3', `Registered workers (${list ? list.count : 0})`));
    if (items.length === 0) {
      content.append(text('p', 'No workers are registered. Start a resident worker with the active configuration to enable processing.', 'warning'));
      return;
    }
    content.append(table(
      ['worker_id', 'label', 'status', 'supported_commands', 'registered_at', 'last_heartbeat_at', 'configuration_snapshot_id', 'runtime_schema_version'],
      items.map(w => [
        w.worker_id, w.label, w.status, (w.supported_commands || []).join(', ') || '-',
        w.registered_at, w.last_heartbeat_at, w.configuration_snapshot_id, w.runtime_schema_version
      ])
    ));
  }

  async function renderConfiguration() {
    const data = await api('/api/v1/configuration');
    canManageConfiguration = data.canManageConfiguration !== false;
    canActivateConfiguration = data.canActivateConfiguration !== false;
    clear(content); content.append(text('h2', 'Configuration lifecycle'));
    const active = data.active || {};
    content.append(cards([
      ['Authority', data.authority], ['Active status', active.status || '-'],
      ['Active version', active.version || '-'], ['Revision sequence', active.revisionSequence || '-'],
      ['Active digest', active.digest || '-'], ['Health', data.health || '-'],
      ['Management ready', data.managementReady === undefined ? '-' : data.managementReady],
      ['Setup required', data.setupRequired === undefined ? '-' : data.setupRequired],
      ['Runtime configured', data.runtimeConfigured === undefined ? '-' : data.runtimeConfigured],
      ['Workflow available', data.workflowAvailable === undefined ? '-' : data.workflowAvailable]
    ]));
    if (data.unavailableReason) content.append(text('p',
      `${data.unavailableReason}. ${data.lastKnownActive ?
        `Last known Active: ${data.lastKnownActive.revisionId} / sequence ` +
        `${data.lastKnownActive.revisionSequence || data.lastKnownActive.version || '-'} / ` +
        `${data.lastKnownActive.digest}` :
        'Stage an explicit replacement JSON Draft.'} ` +
      'No media side effect occurred; inspect the status, then validate and activate a replacement.',
      'error'));
    content.append(text('p', 'Activation is explicit and does not scan or mutate Storage.', 'warning'));
    if (data.setupRequired === true) {
      content.append(text('h3', 'Setup required'));
      content.append(text('p',
        'MediaFlow is alive and management is ready, but no business runtime or Active revision exists. ' +
        'Creating this Draft does not validate, test Storage, contact a Provider, queue work, or touch media.',
        'warning'));
      if (data.setupDraft) {
        const setup = data.setupDraft;
        content.append(text('p', `A setup Draft already exists: ${setup.revisionId} / ${setup.digest}.`));
        content.append(actionButton('Resume setup Draft', () => showConfigurationRevision(setup)));
      } else if (data.canManageConfiguration !== false) {
        content.append(actionButton('Create first Draft', async () => {
          try {
            await api('/api/v1/configuration/drafts/first',
              {method: 'POST', body: '{}'});
            message('First setup Draft created. Resume it to complete guided setup before validation and activation.');
            await renderConfiguration();
          } catch (error) { message(errorText(error), true); await renderConfiguration(); }
        }));
      } else {
        content.append(text('p',
          'This principal is read-only. Ask a configuration administrator to create the first Draft.',
          'warning'));
      }
      if (data.nextAction) content.append(text('p', `Next action: ${data.nextAction}`, 'warning'));
    } else {
      content.append(text('h3', 'Stage a whole-document JSON Draft'));
      const editor = document.createElement('textarea');
      editor.setAttribute('aria-label', 'Configuration JSON draft');
      editor.placeholder = 'Paste a complete configuration document here. Secrets must remain environment references.';
      content.append(editor);
      content.append(actionButton('Import pasted JSON as Draft', async () => {
        try {
          const parsed = JSON.parse(editor.value);
          await api('/api/v1/configuration/drafts',
            {method: 'POST', body: JSON.stringify({document: parsed})});
          message('Draft imported. Open the revision, correct any validation errors, then validate.');
          await renderConfiguration();
        } catch (error) { message(errorText(error), true); }
      }));
      content.append(actionButton('Import current JSON as Draft', async () => {
        try { await api('/api/v1/configuration/drafts',
          {method: 'POST', body: JSON.stringify({source: 'current'})});
          message('Draft imported. Validate it before activation.'); await renderConfiguration();
        } catch (error) { message(errorText(error), true); }
      }));
    }
    const revisions = data.revisions || [];
    content.append(text('h3', `Revisions (${revisions.length})`));
    content.append(table(['Revision', 'Status', 'Version', 'Digest', 'Updated'],
      revisions.map(item => [item.revisionId, item.status, item.version,
        item.digest, item.updatedAt]), index => showConfigurationRevision(revisions[index])));
  }
  function guidedInput(label, value, type = 'text') {
    const wrapper = text('label', label);
    const input = document.createElement('input'); input.type = type;
    input.value = value === null || value === undefined ? '' : String(value);
    input.setAttribute('aria-label', label); wrapper.append(input);
    return {wrapper, input};
  }
  function guidedSelect(label, value, choices) {
    const wrapper = text('label', label);
    const input = document.createElement('select');
    input.setAttribute('aria-label', label);
    choices.forEach(([choice, choiceLabel]) => {
      const option = document.createElement('option'); option.value = choice;
      option.textContent = choiceLabel; input.append(option);
    });
    input.value = value || choices[0][0]; wrapper.append(input);
    return {wrapper, input};
  }
  const storageKinds = [
    ['local', 'Local'], ['smb', 'SMB'], ['openlist', 'OpenList'], ['s3', 'AWS S3'],
    ['r2', 'Cloudflare R2'], ['s3-compatible', 'S3-compatible']
  ];
  const storageNumericOptions = new Set([
    'port', 'connectTimeout', 'requestTimeout', 'operationTimeout', 'maxConcurrency',
    'maxRetries', 'pageSize', 'multipartThreshold', 'multipartPartSize'
  ]);
  function storageOptionDefinitions(type) {
    if (type === 'smb') return [
      ['usernameEnv', 'Username environment variable', 'text'],
      ['passwordEnv', 'Password environment variable', 'text'],
      ['host', 'SMB host', 'text'], ['share', 'SMB share', 'text'],
      ['domain', 'SMB domain (optional)', 'text'], ['port', 'Port', 'number', 445],
      ['connectTimeout', 'Connect timeout (seconds)', 'number', 30],
      ['operationTimeout', 'Operation timeout (seconds)', 'number', 60],
      ['maxConcurrency', 'Maximum concurrency', 'number', 4]
    ];
    if (type === 'openlist') return [
      ['tokenEnv', 'Token environment variable', 'text'], ['baseUrl', 'OpenList base URL', 'text'],
      ['connectTimeout', 'Connect timeout (seconds)', 'number', 10],
      ['requestTimeout', 'Request timeout (seconds)', 'number', 60],
      ['maxConcurrency', 'Maximum concurrency', 'number', 4],
      ['maxRetries', 'Maximum retries', 'number', 2], ['pageSize', 'Page size', 'number', 100]
    ];
    if (type === 's3' || type === 'r2' || type === 's3-compatible') return [
      ['accessKeyEnv', 'Access key environment variable', 'text'],
      ['secretKeyEnv', 'Secret key environment variable', 'text'],
      ['sessionTokenEnv', 'Session token environment variable (optional)', 'text'],
      ['bucket', 'Bucket', 'text'], ['endpoint', 'Endpoint (optional for AWS S3)', 'text'],
      ['region', 'Region (optional)', 'text'], ['forcePathStyle', 'Force path style', 'checkbox'],
      ['connectTimeout', 'Connect timeout (seconds)', 'number', 10],
      ['requestTimeout', 'Request timeout (seconds)', 'number', 60],
      ['maxConcurrency', 'Maximum concurrency', 'number', 4],
      ['maxRetries', 'Maximum retries', 'number', 2], ['pageSize', 'Page size', 'number', 1000],
      ['multipartThreshold', 'Multipart threshold (bytes)', 'number', 67108864],
      ['multipartPartSize', 'Multipart part size (bytes)', 'number', 16777216]
    ];
    return [];
  }
  function renderStorageOptions(type, item, inputs, container) {
    clear(container); Object.keys(inputs).forEach(key => delete inputs[key]);
    const options = item && item.options && typeof item.options === 'object' ? item.options : {};
    storageOptionDefinitions(type).forEach(([key, label, inputType, fallback]) => {
      const initial = options[key] === undefined ? fallback : options[key];
      const control = guidedInput(label, initial, inputType);
      if (inputType === 'checkbox') control.input.checked = initial === true;
      control.wrapper.dataset.guidedField = key; inputs[key] = control.input;
      container.append(control.wrapper);
    });
  }
  function guidedObjectFields(kind, item = {}) {
    if (kind === 'storages') {
      const typeControl = guidedSelect('Storage kind', item.type, storageKinds);
      const optionsContainer = text('div', '', 'choices');
      const optionInputs = {};
      renderStorageOptions(typeControl.input.value, item, optionInputs, optionsContainer);
      typeControl.input.addEventListener('change', () =>
        renderStorageOptions(typeControl.input.value, {}, optionInputs, optionsContainer));
      const result = {};
      [['id', 'ID'], ['name', 'Name'], ['rootPath', 'Storage root path']].forEach(([key, label]) => {
        const control = guidedInput(label, item[key]);
        result[key] = control.input; control.wrapper.dataset.guidedField = key;
      });
      result.type = typeControl.input;
      result._storageOptionInputs = optionInputs;
      result._storageOptionContainer = optionsContainer;
      [['readOnly', 'Read-only', false], ['enabled', 'Enabled', true]].forEach(([key, label, fallback]) => {
        const control = guidedInput(label, item[key] === undefined ? fallback : item[key], 'checkbox');
        control.input.checked = item[key] === undefined ? fallback : Boolean(item[key]);
        result[key] = control.input; control.wrapper.dataset.guidedField = key;
      });
      return result;
    }
    const fields = {
      resourceLibraries: [['id', 'ID'], ['name', 'Name'], ['storageId', 'Storage ID'],
        ['storagePath', 'Storage-relative source path'], ['displayRootPath', 'Display root path'],
        ['extensions', 'Extensions (comma separated)'], ['maxDepth', 'Maximum depth']],
      mediaLibraries: [['id', 'ID'], ['name', 'Name'], ['storageId', 'Storage ID'],
        ['rootPath', 'Storage-relative destination root']]
    }[kind];
    const result = {};
    (fields || []).forEach(([key, label]) => {
      const initial = key === 'extensions' && Array.isArray(item[key]) ? item[key].join(',') : item[key];
      const control = guidedInput(label, initial, key === 'maxDepth' ? 'number' : 'text');
      result[key] = control.input;
      control.wrapper.dataset.guidedField = key;
    });
    const booleans = kind === 'storages' ? [['readOnly', 'Read-only']] : [['enabled', 'Enabled']];
    booleans.forEach(([key, label]) => {
      const control = guidedInput(label, item[key] === undefined ? true : item[key], 'checkbox');
      control.input.checked = item[key] === undefined ? true : Boolean(item[key]);
      result[key] = control.input;
      control.wrapper.dataset.guidedField = key;
    });
    return result;
  }
  function guidedObjectPayload(kind, fields) {
    const value = {};
    Object.entries(fields).forEach(([key, input]) => {
      if (key.startsWith('_')) return;
      if (input.type === 'checkbox') value[key] = input.checked;
      else if (key === 'extensions') value[key] = input.value.split(',').map(item => item.trim()).filter(Boolean);
      else if (key === 'maxDepth') value[key] = input.value === '' ? null : Number(input.value);
      else value[key] = input.value;
    });
    if (kind === 'storages') {
      value.options = {};
      Object.entries(fields._storageOptionInputs || {}).forEach(([key, input]) => {
        if (input.type === 'checkbox') value.options[key] = input.checked;
        else if (input.value !== '') value.options[key] = storageNumericOptions.has(key) ? Number(input.value) : input.value;
      });
    }
    if (kind === 'resourceLibraries') {
      if (!value.displayRootPath) delete value.displayRootPath;
      if (!value.extensions || value.extensions.length === 0) delete value.extensions;
      if (value.maxDepth === null) delete value.maxDepth;
    }
    return value;
  }
  async function mutateGuidedObject(revision, kind, objectId, value, method) {
    const suffix = objectId ? `/${encodeURIComponent(objectId)}` : '';
    await api(`/api/v1/configuration/revisions/${encodeURIComponent(revision.revisionId)}/objects/${kind}${suffix}`,
      {method, body: JSON.stringify(objectId && method === 'DELETE' ?
        {expectedVersion: revision.version} : {object: value, expectedVersion: revision.version})});
    message('Guided configuration change saved. Validate the Draft again before activation.');
    detail.hidden = true; await renderConfiguration();
  }
  async function mutateStorageAction(revision, item, action) {
    await api(`/api/v1/configuration/revisions/${encodeURIComponent(revision.revisionId)}/objects/storages/${encodeURIComponent(item.id)}/${action}`,
      {method: 'POST', body: JSON.stringify({expectedVersion: revision.version})});
    message(`Storage ${action} saved. Validate the Draft again before activation.`);
    detail.hidden = true; await renderConfiguration();
  }
  async function runStorageCheck(revision, item) {
    try {
      const result = await api(`/api/v1/configuration/revisions/${encodeURIComponent(revision.revisionId)}/storage-check`,
        {method: 'POST', body: JSON.stringify({storageId: item.id,
          expectedVersion: revision.version, expectedDigest: revision.digest})});
      message(result.status === 'passed' ?
        'Storage read-only root check passed. Review the declared capabilities and continue setup.' :
        `${result.message || 'Storage read-only root check failed.'} ${result.nextAction || ''} ` +
        `Side effects: ${result.sideEffects || 'unknown'}. Retry safe: ${result.retrySafe === true ? 'yes' : 'no'}.`,
        result.status !== 'passed');
      await showConfigurationRevision(revision);
    } catch (error) { message(errorText(error), true); }
  }
  function storageCheckEvidenceFor(guided, storageId) {
    const values = guided && Array.isArray(guided.storageChecks) ? guided.storageChecks : [];
    return values.find(item => item && item.storageId === storageId) || null;
  }
  function renderStorageCheckEvidence(revision, evidence) {
    const list = document.createElement('dl');
    const current = Boolean(evidence && evidence.current === true && evidence.stale === false);
    const capabilities = evidence && evidence.capabilities && typeof evidence.capabilities === 'object' ? evidence.capabilities : {};
    const operations = Array.isArray(evidence && evidence.completedReadOperations) ? evidence.completedReadOperations :
      (Array.isArray(evidence && evidence.operations) ? evidence.operations : []);
    const attempted = Array.isArray(evidence && evidence.attemptedOperations) ? evidence.attemptedOperations : [];
    const readiness = Array.isArray(evidence && evidence.secretReadiness) ? evidence.secretReadiness.map(item =>
      `${item.field || '-'}: ${item.state || '-'}`).join(', ') : '-';
    field(list, 'Storage check state', current ? 'current' : 'stale');
    field(list, 'Status', boundedSetupText(evidence && evidence.status));
    field(list, 'Check revision', `${boundedSetupText(evidence && evidence.revisionId)} / v${Number.isInteger(evidence && evidence.revisionVersion) ? evidence.revisionVersion : '-'}`);
    field(list, 'Check digest', boundedSetupText(evidence && evidence.revisionDigest));
    field(list, 'Storage', `${boundedSetupText(evidence && evidence.storageId)} (${boundedSetupText(evidence && evidence.storageType)})`);
    field(list, 'Completed read operations', operations.length ? operations.join(', ') : '-');
    field(list, 'Attempted read operations', attempted.length ? attempted.join(', ') : '-');
    field(list, 'Declared capabilities', Object.entries(capabilities).map(([key, value]) => `${key}: ${value === true ? 'yes' : 'no'}`).join(', ') || '-');
    field(list, 'Capability source', boundedSetupText(evidence && evidence.capabilitySource));
    field(list, 'Capability probe', boundedSetupText(evidence && evidence.capabilityProbe));
    field(list, 'Credential readiness', readiness);
    field(list, 'Failure category', boundedSetupText(evidence && evidence.failureCategory));
    field(list, 'Message', boundedSetupText(evidence && evidence.message));
    field(list, 'Side effects', boundedSetupText(evidence && evidence.sideEffects, 'unknown'));
    field(list, 'Retry safe', evidence && evidence.retrySafe === true ? 'YES' : 'NO');
    field(list, 'Next action', boundedSetupText(evidence && evidence.nextAction));
    if (evidence && evidence.staleReason) field(list, 'Stale reason', boundedSetupText(evidence.staleReason));
    return list;
  }
  function configurationRevisionEditable(revision) {
    return canManageConfiguration && (revision.status === 'draft' || revision.status === 'validated');
  }
  function renderGuidedObjectList(revision, guided, kind, label) {
    const values = guided.objects && guided.objects[kind] || [];
    const referenceKind = {storages: 'storage', resourceLibraries: 'resource_library',
      mediaLibraries: 'media_library', recognitionTypes: 'recognition_type',
      recognitionRules: 'recognition_rule', recognitionTypePolicies: 'recognition_type_policy',
      metadataPolicies: 'metadata_policy', namingPolicies: 'naming_policy',
      classificationPolicies: 'classification_policy', organizePolicies: 'organize_policy',
      automationTaskDefinitions: 'schedule'}[kind] || kind;
    detailContent.append(text('h3', `${label} (${values.length})`));
    values.forEach(item => {
      const row = text('div', '', 'choice');
      const namingSummary = kind === 'namingPolicies' ?
        ` - ${item.mediaTypeMode || 'auto'} - ${item.missingVariableStrategy || 'omit_token'} - ` +
        `${item.enabled === false ? 'disabled' : 'enabled'}` : '';
      row.append(text('span', `${item.id || '-'} - ${item.name || '-'} - ${item.type || ''}${namingSummary}`));
      if (kind === 'namingPolicies') row.append(text('span',
        `Movie: ${item.directoryTemplate || '-'} / ${item.filenameTemplate || '-'}; ` +
        `TV: ${item.seriesDirectoryTemplate || '-'} / ${item.seasonDirectoryTemplate || '-'} / ` +
        `${item.episodeFilenameTemplate || '-'} / ${item.multiEpisodeFileTemplate || '-'}`));
      if (kind === 'classificationPolicies') {
        const allRules = Array.isArray(item.rules) ? item.rules : [];
        const rules = allRules.slice(0, 32);
        row.append(text('span', `Priority: ${Number.isInteger(item.priority) ? item.priority : 0}; ` +
          `${item.enabled === false ? 'disabled' : 'enabled'}; Rules: ${allRules.length}`));
        rules.forEach(rule => { const result = rule.result && typeof rule.result === 'object' ? rule.result : {};
          const path = Array.isArray(result.path) ? result.path.join('/') : result.path || '-';
          row.append(text('span', `${rule.id || '-'} - ${Number.isInteger(rule.priority) ? rule.priority : 0} - ` +
            `${result.mediaLibraryId || '-'} - ${path}`)); });
        if (allRules.length > rules.length) row.append(text('span',
          `Rule summary truncated; showing ${rules.length} of ${allRules.length}.`, 'warning'));
      }
      if (kind === 'organizePolicies') {
        const duplicate = item.duplicateDetection && typeof item.duplicateDetection === 'object' ? item.duplicateDetection : {};
        const cleanup = item.sourceDirectoryCleanup && typeof item.sourceDirectoryCleanup === 'object' ? item.sourceDirectoryCleanup : {};
        const attachments = item.attachments && typeof item.attachments === 'object' ? item.attachments : {};
        row.append(text('span', `Operation: ${item.operation || '-'}; Conflict: ${item.conflictStrategy || 'manual'}; ` +
          `Attachments: ${attachments.enabled === true ? 'enabled' : 'disabled'}; ` +
          `Duplicates: ${duplicate.mode || 'none'}; Source cleanup: ${cleanup.mode || 'none'}`));
        if (item.conflictStrategy === 'overwrite' || (cleanup.mode && cleanup.mode !== 'none'))
          row.append(text('span', 'DESTRUCTIVE AUTHORITY: overwrite or source cleanup is enabled.', 'warning'));
      }
      if (kind === 'automationTaskDefinitions') {
        const timing = item.intervalSeconds !== undefined ?
          `every ${item.intervalSeconds}s` : `${item.cron || '-'} (${item.timezone || '-'})`;
        row.append(text('span', `${item.resourceLibraryId || '-'} / ${item.sourceScope || '<root>'}; ` +
          `${item.mode || item.runMode || '-'}; ${timing}; limit ${item.itemLimit || item.limit || '-'}; ` +
          `${item.enabled === true ? 'enabled' : 'disabled'}`));
      }
      const referenceEvidence = guided.references && guided.references[`${referenceKind}:${item.id}`] ||
        {total: 0, items: [], truncated: false};
      const references = Array.isArray(referenceEvidence) ? referenceEvidence :
        (Array.isArray(referenceEvidence.items) ? referenceEvidence.items : []);
      const referenceTotal = Array.isArray(referenceEvidence) ? references.length :
        Number.isInteger(referenceEvidence.total) ? referenceEvidence.total : references.length;
      if (referenceTotal) {
        const labels = references.map(reference =>
          `${reference.section || 'configuration'}:${reference.id || '-'}.${reference.field || '-'}`);
        const suffix = !Array.isArray(referenceEvidence) && referenceEvidence.truncated ?
          `; showing ${references.length} (truncated)` : '';
        row.append(text('span', `References (${referenceTotal}${suffix}): ${labels.join(', ')}`, 'warning'));
      }
      if (kind === 'storages') {
        const readiness = Array.isArray(item.secretReadiness) ? item.secretReadiness : [];
        const readinessText = readiness.length ? readiness.map(entry =>
          `${entry.field}: ${entry.state}`).join(', ') : 'No secret reference';
        row.append(text('span', `Credential readiness: ${readinessText}`));
        const storageEvidence = storageCheckEvidenceFor(guided, item.id);
        row.append(text('span', storageEvidence ?
          `Read-only root check: ${storageEvidence.current === true && storageEvidence.stale === false ? 'current' : 'stale'} / ${storageEvidence.status || 'unknown'}` :
          'Read-only root check: not run', storageEvidence && storageEvidence.status === 'failed' ? 'warning' : ''));
        if (storageEvidence) row.append(renderStorageCheckEvidence(revision, storageEvidence));
        if (configurationRevisionEditable(revision)) row.append(actionButton(
          storageEvidence ? 'Rerun read-only Storage check' : 'Run read-only Storage check',
          () => runStorageCheck(revision, item)));
      }
      if (kind === 'storages') row.append(actionButton(
        'Open Storage browser', () => renderStandaloneStorageBrowser(revision, item, guided)));
      if (configurationRevisionEditable(revision)) {
        row.append(actionButton('Edit', () => renderGuidedObjectForm(revision, kind, item, false, guided)));
        if (kind === 'storages' || kind === 'namingPolicies' || kind === 'classificationPolicies' || kind === 'organizePolicies') row.append(actionButton('Copy', async () => {
          if (kind === 'storages') {
            const confirmation = text('span', '', 'choices');
            confirmation.append(text('span', `Copy Storage ${item.id}? The copy starts disabled.`),
              actionButton('Confirm copy', async () => {
                try { await mutateStorageAction(revision, item, 'copy'); }
                catch (error) { message(errorText(error), true); }
              }), actionButton('Cancel copy', () => confirmation.remove()));
            row.append(confirmation);
            return;
          }
          const copied = {...item, id: `${item.id}-copy`, name: `${item.name || item.id} copy`};
          renderGuidedObjectForm(revision, kind, copied, true, guided);
        }));
        if (kind === 'storages') row.append(actionButton(item.enabled === true ? 'Disable' : 'Enable', async () => {
          const action = item.enabled === true ? 'disable' : 'enable';
          const confirmation = text('span', '', 'choices');
          confirmation.append(text(`${action === 'enable' ? 'Enable' : 'Disable'} Storage ${item.id}? This changes only the Draft.`),
            actionButton(`Confirm ${action}`, async () => {
              try { await mutateStorageAction(revision, item, action); }
              catch (error) { message(errorText(error), true); }
            }), actionButton('Cancel', () => confirmation.remove()));
          row.append(confirmation);
        }));
        if (kind === 'automationTaskDefinitions') {
          row.append(actionButton('Copy', async () => {
            const confirmation = text('span', '', 'choices');
            confirmation.append(text('span', `Copy Automation Task Definition ${item.id}? The copy starts disabled.`),
              actionButton('Confirm copy', async () => {
                try {
                  await api(`/api/v1/configuration/revisions/${encodeURIComponent(revision.revisionId)}/objects/automationTaskDefinitions/${encodeURIComponent(item.id)}/copy`,
                    {method: 'POST', body: JSON.stringify({expectedVersion: revision.version})});
                  confirmation.remove(); detail.hidden = true; await renderConfiguration();
                } catch (error) { message(errorText(error), true); }
              }), actionButton('Cancel copy', () => confirmation.remove()));
            row.append(confirmation);
          }));
          row.append(actionButton(item.enabled === true ? 'Disable' : 'Enable', async () => {
            const action = item.enabled === true ? 'disable' : 'enable';
            const confirmation = text('span', '', 'choices');
            confirmation.append(text('span', `${action === 'enable' ? 'Enable' : 'Disable'} ${item.id}? This changes only the Draft.`),
              actionButton(`Confirm ${action}`, async () => {
                try {
                  await api(`/api/v1/configuration/revisions/${encodeURIComponent(revision.revisionId)}/objects/automationTaskDefinitions/${encodeURIComponent(item.id)}/${action}`,
                    {method: 'POST', body: JSON.stringify({expectedVersion: revision.version})});
                  confirmation.remove(); detail.hidden = true; await renderConfiguration();
                } catch (error) { message(errorText(error), true); }
              }), actionButton('Cancel', () => confirmation.remove()));
            row.append(confirmation);
          }));
        }
        if (kind !== 'automationTaskDefinitions') row.append(actionButton('Delete', () => {
          const confirmation = text('span', '', 'choices');
          confirmation.append(text('span', `Delete ${label} ${item.id}? References block deletion.`),
            actionButton('Confirm delete', async () => {
              try { await mutateGuidedObject(revision, kind, item.id, null, 'DELETE'); }
              catch (error) { message(errorText(error), true); }
            }), actionButton('Cancel delete', () => confirmation.remove()));
          row.append(confirmation);
        }));
      }
      detailContent.append(row);
    });
    if (configurationRevisionEditable(revision)) {
      const singular = {storages: 'Storage', resourceLibraries: 'ResourceLibrary',
        mediaLibraries: 'MediaLibrary', recognitionTypes: 'RecognitionType',
        recognitionRules: 'RecognitionRule', recognitionTypePolicies: 'RecognitionTypePolicy',
        metadataPolicies: 'MetadataPolicy', namingPolicies: 'NamingPolicy',
        organizePolicies: 'OrganizePolicy', automationTaskDefinitions: 'AutomationTaskDefinition'}[kind] || kind;
      const classificationPolicy = kind === 'classificationPolicies';
      const organizePolicy = kind === 'organizePolicies';
      const guidedJson = kind === 'storages' || kind.startsWith('recognition') ||
        kind === 'metadataPolicies' || kind === 'namingPolicies' || classificationPolicy || organizePolicy ||
        kind === 'automationTaskDefinitions';
      const objectLabel = classificationPolicy ? 'ClassificationPolicy' : organizePolicy ? 'OrganizePolicy' : singular;
      detailContent.append(actionButton(`${guidedJson ? 'Add' : 'Add Local'} ${objectLabel}`,
        () => renderGuidedObjectForm(revision, kind, null, false, guided)));
    }
  }
  function renderStandaloneStorageBrowser(revision, item, guided) {
    clear(detailContent);
    detailContent.append(text('h2', `Storage browser: ${item.name || item.id || '-'}`));
    detailContent.append(text('p',
      'This setup-only browser is read-only and scoped to the selected configured Storage. ' +
      'It does not inspect FileIndex entries or provide arbitrary host filesystem access.', 'warning'));
    const fields = {
      storageId: {value: item.id},
      browserPath: {value: ''}
    };
    renderStorageBrowserPicker(revision, 'storageBrowser', fields, null, guided, false, true);
  }
  function renderStorageBrowserPicker(revision, kind, fields, item, guided, copyMode = false, standalone = false) {
    const storages = guided && guided.objects && Array.isArray(guided.objects.storages) ?
      guided.objects.storages.filter(storage => storage.enabled !== false) : [];
    if (!storages.length || !fields.storageId) return;
    const pathField = fields.storagePath || fields.rootPath || fields.browserPath;
    const target = kind === 'resourceLibraries' ? 'resourceLibrary' : 'mediaLibrary';
    const selectedField = kind === 'resourceLibraries' ? 'storagePath' : 'rootPath';
    const panel = text('div', '', 'choices');
    panel.append(text('h3', 'Storage directory browser'));
    panel.append(text('p',
      'This bounded setup browser reads the configured Storage directly; it is not the File Catalog. ' +
      'Directories can be selected after the read-only listing succeeds. Files and symbolic links are not selectable.',
      'warning'));
    const storageChoices = storages.map(storage => [storage.id, `${storage.id} - ${storage.name || storage.id}`]);
    const storage = guidedSelect('Browser Storage', fields.storageId.value, storageChoices);
    const path = guidedInput('Storage-relative browser path', pathField.value || '');
    const limit = guidedInput('Browser page size (1-100)', 50, 'number');
    const controls = text('div', '', 'choices');
    const results = text('div', '', 'choices');
    const state = {path: path.input.value || '', cursor: null, requestCursor: null};
    const renderError = error => {
      clear(results);
      results.append(text('p', `Storage browser could not continue. ${errorText(error)}`, 'error'));
      results.append(text('p',
        'No Storage mutation occurred. Retry the same bounded read, or reload the revision to restart after a stale cursor.',
        'warning'));
    };
    const renderPage = data => {
      clear(results);
      state.path = typeof data.path === 'string' ? data.path : '';
      state.cursor = data.nextCursor || null;
      path.input.value = state.path;
      results.append(text('p', `Storage-relative path: ${state.path || '<root>'}`));
      const breadcrumbs = text('div', '', 'choices');
      (Array.isArray(data.breadcrumbs) ? data.breadcrumbs : []).forEach(breadcrumb => {
        breadcrumbs.append(actionButton(breadcrumb.name || 'Storage root', () => {
          state.path = breadcrumb.path || ''; state.cursor = null; path.input.value = state.path;
          browse();
        }));
      });
      results.append(breadcrumbs);
      const entries = Array.isArray(data.entries) ? data.entries : [];
      if (!entries.length) results.append(text('p', 'This directory has no entries on this page.'));
      entries.forEach(entry => {
        const row = text('div', '', 'choice');
        const label = `${entry.name || '-'} (${entry.type || 'unknown'})`;
        if (entry.traversable === true && entry.selectable === true) {
          row.append(actionButton(label, () => {
            state.path = entry.path; state.cursor = null; path.input.value = state.path; browse();
          }));
        } else {
          row.append(text('span', label));
          row.append(text('span', entry.isSymlink ? 'not traversable/selectable' : 'not a directory', 'warning'));
        }
        row.append(text('span', `size ${Number.isInteger(entry.size) ? entry.size : '-'}; ` +
          `${entry.modifiedAt || '-'}`));
        results.append(row);
      });
      const actions = text('div', '', 'choices');
      actions.append(actionButton(standalone ? 'Keep browsing this directory' :
        `Select ${state.path || 'Storage root'} for ${target}`, async () => {
        if (standalone) {
          actions.append(text('p',
            `Current directory: ${state.path || '<root>'}. ` +
            'Use a ResourceLibrary or MediaLibrary picker to select a directory for a Draft.',
            'warning'));
          return;
        }
        if (item && item.id && !copyMode) {
          try {
            const result = await api(`/api/v1/configuration/revisions/${encodeURIComponent(revision.revisionId)}/storage-browser/select`, {
              method: 'POST', body: JSON.stringify({storageId: storage.input.value, path: state.path,
                target, libraryId: item.id, field: selectedField, expectedVersion: revision.version,
                expectedDigest: revision.digest})});
            message(`Selected ${result.selected.path || '<root>'}. Draft saved; validate it again before activation.`);
            detail.hidden = true; await renderConfiguration();
          } catch (error) { renderError(error); }
          return;
        }
        fields.storageId.value = storage.input.value;
        pathField.value = state.path;
        const selected = text('p', `Selected ${storage.input.value}:${state.path || '<root>'}. Save the guided object to persist this Storage-relative path.`, 'warning');
        actions.append(selected);
      }));
      if (data.hasNext && data.nextCursor) actions.append(actionButton('Next page', () => browse(data.nextCursor)));
      actions.append(actionButton('Retry page', () => browse(state.requestCursor)));
      results.append(actions);
    };
    const browse = async nextCursor => {
      const query = new URLSearchParams();
      query.set('storageId', storage.input.value);
      query.set('path', state.path);
      query.set('limit', String(Math.max(1, Math.min(100, Number(limit.input.value) || 50))));
      query.set('expectedVersion', String(revision.version));
      query.set('expectedDigest', revision.digest);
      const cursor = nextCursor === undefined ? state.cursor : nextCursor;
      state.requestCursor = cursor || null;
      if (cursor) query.set('cursor', cursor);
      try {
        const data = await api(`/api/v1/configuration/revisions/${encodeURIComponent(revision.revisionId)}/storage-browser?${query.toString()}`);
        renderPage(data);
      } catch (error) { renderError(error); }
    };
    storage.input.addEventListener('change', () => { state.path = ''; path.input.value = ''; state.cursor = null; browse(null); });
    controls.append(storage.wrapper, path.wrapper, limit.wrapper,
      actionButton('Browse path', () => { state.path = path.input.value || ''; state.cursor = null; browse(null); }));
    panel.append(controls, results);
    detailContent.append(panel);
    browse(null);
  }
  function renderGuidedObjectForm(revision, kind, item, copyMode = false, guided = null) {
    if (kind.startsWith('recognition') || kind === 'metadataPolicies' || kind === 'namingPolicies' || kind === 'classificationPolicies' || kind === 'organizePolicies' || kind === 'automationTaskDefinitions') {
      const metadataPolicy = kind === 'metadataPolicies';
      const namingPolicy = kind === 'namingPolicies';
      const classificationPolicy = kind === 'classificationPolicies';
      const organizePolicy = kind === 'organizePolicies';
      const automationTaskDefinition = kind === 'automationTaskDefinitions';
      clear(detailContent);
      detailContent.append(text('h2', `${item && !copyMode ? 'Edit' : 'Add'} ${metadataPolicy ? 'MetadataPolicy' : namingPolicy ? 'NamingPolicy' : classificationPolicy ? 'ClassificationPolicy' : organizePolicy ? 'OrganizePolicy' : automationTaskDefinition ? 'Automation Task Definition' : 'recognition object'}`));
      detailContent.append(text('p', automationTaskDefinition ?
        'Edit one bounded Automation Task Definition. It references one enabled ResourceLibrary and owns only source scope, schedule, run mode and item limit; policy and destination choices stay in configuration.' : organizePolicy ?
        'Edit one bounded OrganizePolicy JSON object. Overwrite and source cleanup grant destructive authority and are never implicit.' : classificationPolicy ?
        'Edit one bounded ClassificationPolicy JSON object. Rules use the configured conditions and safe relative result paths.' : namingPolicy ?
        'Edit one bounded NamingPolicy JSON object. Templates use the restricted naming variables; separators, traversal, unknown variables and unsupported formats are rejected.' : metadataPolicy ?
        'Edit one bounded MetadataPolicy JSON object. Provider/query/locale/threshold/request settings are validated; credentials and unknown fields are rejected.' :
        'Edit one bounded JSON object. References and rule priority are checked when the Draft is validated; unsafe regex is rejected when saved.', 'warning'));
      const editor = document.createElement('textarea');
      editor.setAttribute('aria-label', metadataPolicy ? 'MetadataPolicy JSON' : namingPolicy ? 'NamingPolicy JSON' : classificationPolicy ? 'ClassificationPolicy JSON' : organizePolicy ? 'OrganizePolicy JSON' : automationTaskDefinition ? 'Automation Task Definition JSON' : 'Recognition object JSON');
      editor.value = JSON.stringify(item || {}, null, 2); detailContent.append(editor);
      detailContent.append(actionButton(metadataPolicy ? 'Save MetadataPolicy' : namingPolicy ? 'Save NamingPolicy' : classificationPolicy ? 'Save ClassificationPolicy' : organizePolicy ? 'Save OrganizePolicy' : automationTaskDefinition ? 'Save Automation Task Definition' : 'Save recognition object', async () => {
        try { await mutateGuidedObject(revision, kind, item && !copyMode && item.id, JSON.parse(editor.value), item && !copyMode ? 'PUT' : 'POST'); }
        catch (error) { message(errorText(error), true); }
      }), actionButton('Back to revision', () => showConfigurationRevision(revision)));
      return;
    }
    if (kind === 'storages') {
      clear(detailContent);
      detailContent.append(text('h2', `${item ? 'Edit' : 'Add'} Storage`));
      detailContent.append(text('p', 'Choose exactly one supported Storage kind. Credentials are environment-variable references; only SET/UNSET readiness is shown.', 'warning'));
      detailContent.append(text('p',
        'Local Storage rootPath is a host-absolute directory visible inside the MediaFlow execution environment, not an arbitrary host path. In Docker, bind-mount the directory explicitly with the intended read-only/read-write permission and ensure the container user has ownership or access. Host /, the Docker socket, unmapped host paths and arbitrary host filesystem access are unsupported. Remote Storage roots follow the provider contract and are not tested or contacted while editing.',
        'warning'));
      const form = text('div', '', 'choices'); const fields = guidedObjectFields(kind, item || {});
      Object.entries(fields).forEach(([key, input]) => {
        if (key === '_storageOptionContainer') form.append(input);
        else if (!key.startsWith('_')) form.append(input.parentElement);
      });
      form.append(text('h4', 'Provider options'));
      form.append(fields._storageOptionContainer); detailContent.append(form);
      detailContent.append(actionButton('Save guided object', async () => {
        try { await mutateGuidedObject(revision, kind, item && item.id && !copyMode ? item.id : null,
          guidedObjectPayload(kind, fields), item && !copyMode ? 'PUT' : 'POST'); }
        catch (error) { message(errorText(error), true); }
      }), actionButton('Back to revision', () => showConfigurationRevision(revision)));
      return;
    }
    clear(detailContent);
      detailContent.append(text('h2', `${item ? 'Edit' : 'Add'} ${kind === 'resourceLibraries' ? 'ResourceLibrary' : 'MediaLibrary'}`));
    detailContent.append(text('p',
      'ResourceLibrary storagePath and MediaLibrary rootPath are Storage-relative paths. ' +
      'Use Storage-relative paths for this object; absolute paths, backslashes and traversal are rejected. ' +
      'Use the displayed Storage-relative breadcrumb to return to a parent; the setup browser uses the same configured Storage and remains read-only.', 'warning'));
    const form = text('div', '', 'choices'); const fields = guidedObjectFields(kind, item || {});
    Object.values(fields).forEach(input => form.append(input.parentElement)); detailContent.append(form);
    if (guided) renderStorageBrowserPicker(revision, kind, fields, item, guided, copyMode);
    detailContent.append(actionButton('Save guided object', async () => {
      try { await mutateGuidedObject(revision, kind, item && item.id, guidedObjectPayload(kind, fields), item ? 'PUT' : 'POST'); }
      catch (error) { message(errorText(error), true); }
    }), actionButton('Back to revision', () => showConfigurationRevision(revision)));
  }
  function boundedSetupText(value, fallback = '-') {
    return typeof value === 'string' && value.length > 0 && value.length <= 4096 ? value : fallback;
  }
  function determinationText(value) {
    if (value === true) return 'YES';
    if (value === false) return 'NO';
    return 'NOT DETERMINED';
  }
  function namingEvidenceIsCurrent(revision, evidence) {
    return Boolean(evidence && evidence.stale === false &&
      evidence.revisionId === revision.revisionId &&
      evidence.revisionVersion === revision.version && evidence.revisionDigest === revision.digest);
  }
  function renderNamingPreview(revision, guided) {
    const evidence = guided.namingPreview;
    detailContent.append(text('h3', 'Offline naming preview'));
    if (!evidence) detailContent.append(text('p',
      'Status: not run. Preview one bounded sample with zero Storage or Provider access.', 'warning'));
    else {
      const current = namingEvidenceIsCurrent(revision, evidence);
      const result = evidence.result && typeof evidence.result === 'object' ? evidence.result : {};
      const list = document.createElement('dl');
      field(list, 'Evidence state', current ? 'current' : 'stale');
      field(list, 'Status', boundedSetupText(evidence.status));
      field(list, 'Revision ID', boundedSetupText(evidence.revisionId));
      field(list, 'Revision version', Number.isInteger(evidence.revisionVersion) ? evidence.revisionVersion : '-');
      field(list, 'Revision digest', boundedSetupText(evidence.revisionDigest));
      field(list, 'Applied policy', boundedSetupText(result.appliedPolicyId || evidence.policyId));
      field(list, 'RecognitionType', boundedSetupText(result.recognitionType));
      field(list, 'Rendered directory', boundedSetupText(result.directory));
      field(list, 'Rendered filename', boundedSetupText(result.filename));
      field(list, 'Sanitization', Array.isArray(result.sanitizationChanges) && result.sanitizationChanges.length ?
        result.sanitizationChanges.slice(0, 32).join(', ') : 'none');
      field(list, 'Missing-variable strategy', boundedSetupText(result.missingVariableStrategy));
      field(list, 'Warnings', Array.isArray(result.warnings) && result.warnings.length ?
        result.warnings.slice(0, 32).join(', ') : 'none');
      field(list, 'Failure category', boundedSetupText(evidence.failureCategory));
      field(list, 'Message', boundedSetupText(evidence.message));
      field(list, 'Side effects', boundedSetupText(evidence.sideEffects, 'unknown'));
      field(list, 'Retry safe', evidence.retrySafe === true ? 'YES' : 'NO');
      field(list, 'Next action', boundedSetupText(evidence.nextAction));
      detailContent.append(list);
      if (Array.isArray(result.missingVariableDecisions) && result.missingVariableDecisions.length) {
        detailContent.append(table(['Missing variable', 'Decision'],
          result.missingVariableDecisions.slice(0, 32).map(item => [item.variable, item.decision])));
      }
      if (!current) detailContent.append(text('p',
        'This preview is stale because the Draft changed. Rerun against the current revision.', 'warning'));
    }
    if (!configurationRevisionEditable(revision)) return;
    const policies = guided.objects && guided.objects.namingPolicies || [];
    if (!policies.length) return;
    const controls = text('div', '', 'choices');
    const policy = document.createElement('select'); policy.setAttribute('aria-label', 'NamingPolicy preview policy');
    policies.forEach(item => { const option = document.createElement('option'); option.value = item.id;
      option.textContent = `${item.id} - ${item.name || item.id}`; policy.append(option); });
    const editor = document.createElement('textarea'); editor.setAttribute('aria-label', 'Naming preview sample JSON');
    editor.value = JSON.stringify({title: 'The Matrix', mediaType: 'movie', recognitionType: 'C',
      provider: 'tmdb', providerId: '603', year: 1999, extension: 'mkv'}, null, 2);
    controls.append(policy, editor, actionButton('Run offline naming preview', async () => {
      try {
        const result = await api(`/api/v1/configuration/revisions/${encodeURIComponent(revision.revisionId)}/naming-preview`,
          {method: 'POST', body: JSON.stringify({expectedVersion: revision.version,
            expectedDigest: revision.digest, policyId: policy.value, sample: JSON.parse(editor.value)})});
        message(result.status === 'completed' ?
          'Naming preview completed. Review the rendered directory, filename and explanation.' :
          `${result.message || 'Naming preview failed.'} ${result.nextAction || ''}`,
          result.status !== 'completed');
        await showConfigurationRevision(revision);
      } catch (error) { message(errorText(error), true); }
    }));
    detailContent.append(controls);
  }
  function classificationEvidenceIsCurrent(revision, evidence) {
    return Boolean(evidence && evidence.stale === false &&
      evidence.revisionId === revision.revisionId &&
      evidence.revisionVersion === revision.version && evidence.revisionDigest === revision.digest);
  }
  function renderClassificationPreview(revision, guided) {
    const evidence = guided.classificationPreview;
    detailContent.append(text('h3', 'Offline classification preview'));
    if (!evidence) detailContent.append(text('p',
      'Status: not run. Preview one bounded sample with zero Storage or Provider access.', 'warning'));
    else {
      const current = classificationEvidenceIsCurrent(revision, evidence);
      const result = evidence.result && typeof evidence.result === 'object' ? evidence.result : {};
      const list = document.createElement('dl');
      field(list, 'Evidence state', current ? 'current' : 'stale');
      field(list, 'Status', boundedSetupText(result.status || evidence.status));
      field(list, 'Revision ID', boundedSetupText(evidence.revisionId));
      field(list, 'Revision version', Number.isInteger(evidence.revisionVersion) ? evidence.revisionVersion : '-');
      field(list, 'Revision digest', boundedSetupText(evidence.revisionDigest));
      field(list, 'Applied policy', boundedSetupText(result.appliedPolicyId || evidence.policyId));
      field(list, 'RecognitionType', boundedSetupText(result.recognitionType));
      field(list, 'Matched rule', boundedSetupText(result.matchedRuleId));
      field(list, 'Matched rule name', boundedSetupText(result.matchedRuleName));
      field(list, 'MediaLibrary', boundedSetupText(result.mediaLibraryId));
      field(list, 'MediaLibrary resolved', result.mediaLibraryResolved === true ? 'YES' : 'NO');
      field(list, 'Relative path', boundedSetupText(result.relativePath));
      field(list, 'Reason', boundedSetupText(result.reason));
      field(list, 'Match evidence', Array.isArray(result.matchEvidence) && result.matchEvidence.length ?
        result.matchEvidence.slice(0, 32).join(', ') : 'none');
      field(list, 'Warnings', Array.isArray(result.warnings) && result.warnings.length ?
        result.warnings.slice(0, 32).join(', ') : 'none');
      field(list, 'Failure category', boundedSetupText(evidence.failureCategory));
      field(list, 'Message', boundedSetupText(evidence.message));
      field(list, 'Side effects', boundedSetupText(evidence.sideEffects, 'unknown'));
      field(list, 'Retry safe', evidence.retrySafe === true ? 'YES' : 'NO');
      field(list, 'Next action', boundedSetupText(evidence.nextAction));
      detailContent.append(list);
      if (!current) detailContent.append(text('p',
        'This classification preview is stale because the Draft changed. Reload and rerun it.', 'warning'));
    }
    if (!configurationRevisionEditable(revision)) return;
    const policies = guided.objects && guided.objects.classificationPolicies || [];
    if (!policies.length) return;
    const controls = text('div', '', 'choices');
    const policy = document.createElement('select');
    policy.setAttribute('aria-label', 'ClassificationPolicy preview policy');
    policies.forEach(item => { const option = document.createElement('option'); option.value = item.id;
      option.textContent = `${item.id} - ${item.name || item.id}`; policy.append(option); });
    const editor = document.createElement('textarea');
    editor.setAttribute('aria-label', 'Classification preview sample JSON');
    editor.value = JSON.stringify({title: 'The Matrix', mediaType: 'movie', recognitionType: 'C',
      year: 1999, genres: ['Action'], countries: ['US'], languages: ['en'], keywords: []}, null, 2);
    controls.append(policy, editor, actionButton('Run offline classification preview', async () => {
      try {
        const result = await api(`/api/v1/configuration/revisions/${encodeURIComponent(revision.revisionId)}/classification-preview`,
          {method: 'POST', body: JSON.stringify({expectedVersion: revision.version,
            expectedDigest: revision.digest, policyId: policy.value, sample: JSON.parse(editor.value)})});
        message(result.status === 'completed' ?
          'Classification preview completed. Review the chosen MediaLibrary, path and explanation.' :
          `${result.message || 'Classification preview failed.'} ${result.nextAction || ''}`,
          result.status !== 'completed');
        await showConfigurationRevision(revision);
      } catch (error) { message(errorText(error), true); }
    }));
    detailContent.append(controls);
  }
  function organizeAuthorityIsCurrent(revision, evidence) {
    return Boolean(evidence && evidence.stale === false &&
      evidence.revisionId === revision.revisionId &&
      evidence.revisionVersion === revision.version && evidence.revisionDigest === revision.digest);
  }
  function renderOrganizeAuthority(revision, guided) {
    const evidence = guided.organizeAuthority;
    detailContent.append(text('h3', 'Offline organize authority explanation'));
    if (!evidence) detailContent.append(text('p',
      'Status: not run. Explain declared authority without Storage, planning, or execution.', 'warning'));
    else {
      const current = organizeAuthorityIsCurrent(revision, evidence);
      const result = evidence.result && typeof evidence.result === 'object' ? evidence.result : {};
      const list = document.createElement('dl');
      field(list, 'Evidence state', current ? 'current' : 'stale');
      field(list, 'Status', boundedSetupText(evidence.status));
      field(list, 'Revision ID', boundedSetupText(evidence.revisionId));
      field(list, 'Revision version', Number.isInteger(evidence.revisionVersion) ? evidence.revisionVersion : '-');
      field(list, 'Revision digest', boundedSetupText(evidence.revisionDigest));
      field(list, 'RecognitionType', boundedSetupText(result.recognitionType || evidence.recognitionType));
      field(list, 'RecognitionTypePolicy', boundedSetupText(result.recognitionTypePolicyId));
      field(list, 'OrganizePolicy', boundedSetupText(result.organizePolicyId));
      field(list, 'Operation', boundedSetupText(result.operation));
      field(list, 'Conflict strategy', boundedSetupText(result.conflictStrategy));
      field(list, 'Overwrite authorized', result.overwriteAuthorized === true ? 'YES' : 'NO');
      field(list, 'Delete authorized', result.deleteAuthorized === true ? 'YES' : 'NO');
      field(list, 'Attachments', boundedSetupText(JSON.stringify(result.attachments || {})));
      field(list, 'Duplicate detection', boundedSetupText(JSON.stringify(result.duplicateDetection || {})));
      field(list, 'Rollback', boundedSetupText(JSON.stringify(result.rollback || {})));
      field(list, 'Source cleanup', boundedSetupText(JSON.stringify(result.sourceDirectoryCleanup || {})));
      field(list, 'Required Storage capabilities', Array.isArray(result.requiredStorageCapabilities) ?
        result.requiredStorageCapabilities.slice(0, 8).join(', ') : 'none');
      field(list, 'Fallback', boundedSetupText(result.fallback));
      field(list, 'Destructive warnings', Array.isArray(result.warnings) && result.warnings.length ?
        result.warnings.slice(0, 16).join('; ') : 'none');
      field(list, 'Failure category', boundedSetupText(evidence.failureCategory));
      field(list, 'Message', boundedSetupText(evidence.message));
      field(list, 'Side effects', boundedSetupText(evidence.sideEffects, 'unknown'));
      field(list, 'Retry safe', evidence.retrySafe === true ? 'YES' : 'NO');
      field(list, 'Next action', boundedSetupText(evidence.nextAction));
      detailContent.append(list);
      if (!current) detailContent.append(text('p',
        'This organize authority explanation is stale. Reload and rerun it.', 'warning'));
    }
    if (!configurationRevisionEditable(revision)) return;
    const controls = text('div', '', 'choices');
    const recognitionType = document.createElement('input');
    recognitionType.setAttribute('aria-label', 'Organize authority RecognitionType');
    recognitionType.value = 'C';
    controls.append(recognitionType, actionButton('Explain offline organize authority', async () => {
      try {
        const result = await api(`/api/v1/configuration/revisions/${encodeURIComponent(revision.revisionId)}/organize-authority`,
          {method: 'POST', body: JSON.stringify({expectedVersion: revision.version,
            expectedDigest: revision.digest, recognitionType: recognitionType.value})});
        message(result.status === 'completed' ?
          'Organize authority explained. Review destructive warnings and required capabilities.' :
          `${result.message || 'Organize authority failed.'} ${result.nextAction || ''}`,
          result.status !== 'completed');
        await showConfigurationRevision(revision);
      } catch (error) { message(errorText(error), true); }
    }));
    detailContent.append(controls);
  }
  function destinationPreviewIsCurrent(revision, evidence) {
    return Boolean(evidence && evidence.stale === false &&
      evidence.revisionId === revision.revisionId &&
      evidence.revisionVersion === revision.version && evidence.revisionDigest === revision.digest);
  }
  function renderDestinationPreview(revision, guided) {
    const evidence = guided.destinationPreview;
    detailContent.append(text('h3', 'Offline composed destination preview'));
    if (!evidence) detailContent.append(text('p',
      'Status: not run. This computes a Storage-relative path without reading Storage.', 'warning'));
    else {
      const current = destinationPreviewIsCurrent(revision, evidence);
      const result = evidence.result && typeof evidence.result === 'object' ? evidence.result : {};
      const list = document.createElement('dl');
      field(list, 'Evidence state', current ? 'current' : 'stale');
      field(list, 'Status', boundedSetupText(evidence.status));
      field(list, 'Path scope', boundedSetupText(evidence.pathScope));
      field(list, 'RecognitionType', boundedSetupText(result.recognitionType || evidence.recognitionType));
      field(list, 'RecognitionTypePolicy', boundedSetupText(result.recognitionTypePolicyId));
      field(list, 'MediaLibrary contribution', `${boundedSetupText(result.mediaLibraryId)}: ${boundedSetupText(result.mediaLibraryRootPath)}`);
      field(list, 'ClassificationPolicy contribution', `${boundedSetupText(result.classificationPolicyId)}: ${boundedSetupText(result.classificationRelativePath)}`);
      field(list, 'NamingPolicy directory contribution', `${boundedSetupText(result.namingPolicyId)}: ${Array.isArray(result.namingDirectorySegments) ? result.namingDirectorySegments.join('/') : '-'}`);
      field(list, 'NamingPolicy filename contribution', `${boundedSetupText(result.namingPolicyId)}: ${boundedSetupText(result.namingFilename)}`);
      field(list, 'Root-relative destination', boundedSetupText(result.rootRelativeDestination));
      field(list, 'Composed Storage-relative destination', boundedSetupText(result.composedStorageRelativeDestination));
      field(list, 'Failure category', boundedSetupText(evidence.failureCategory));
      field(list, 'Message', boundedSetupText(evidence.message));
      field(list, 'Side effects', boundedSetupText(evidence.sideEffects, 'unknown'));
      field(list, 'Retry safe', evidence.retrySafe === true ? 'YES' : 'NO');
      field(list, 'Next action', boundedSetupText(evidence.nextAction));
      detailContent.append(list);
      if (!current) detailContent.append(text('p',
        'This destination preview is stale. Reload and rerun it.', 'warning'));
      if (evidence.status !== 'completed' || !result.composedStorageRelativeDestination)
        detailContent.append(text('p', 'No valid destination was produced. Follow the recovery action.', 'error'));
    }
    if (!configurationRevisionEditable(revision)) return;
    const controls = text('div', '', 'choices');
    const recognitionType = document.createElement('input');
    recognitionType.setAttribute('aria-label', 'Destination preview RecognitionType');
    recognitionType.value = 'C';
    const sample = document.createElement('textarea');
    sample.setAttribute('aria-label', 'Destination preview sample JSON');
    sample.value = JSON.stringify({title: 'The Matrix', mediaType: 'movie', year: 1999,
      genres: ['Action'], extension: 'mkv'}, null, 2);
    controls.append(recognitionType, sample, actionButton('Run offline destination preview', async () => {
      try {
        const result = await api(`/api/v1/configuration/revisions/${encodeURIComponent(revision.revisionId)}/destination-preview`,
          {method: 'POST', body: JSON.stringify({expectedVersion: revision.version,
            expectedDigest: revision.digest, recognitionType: recognitionType.value,
            sample: JSON.parse(sample.value)})});
        message(result.status === 'completed' ?
          'Destination preview completed. Review the Storage-relative composition.' :
          `${result.message || 'Destination preview failed.'} ${result.nextAction || ''}`,
          result.status !== 'completed');
        await showConfigurationRevision(revision);
      } catch (error) { message(errorText(error), true); }
    }));
    detailContent.append(controls);
  }
  function destinationPrecheckIsCurrent(revision, evidence) {
    return Boolean(evidence && evidence.stale === false &&
      evidence.revisionId === revision.revisionId &&
      evidence.revisionVersion === revision.version && evidence.revisionDigest === revision.digest);
  }
  function destinationPrecheckActivationRequirement(revision, guided) {
    const evidence = guided && guided.destinationPrecheck;
    const objects = guided && guided.objects && typeof guided.objects === 'object' ? guided.objects : {};
    const mediaLibraries = Array.isArray(objects.mediaLibraries) ? objects.mediaLibraries : [];
    const applicable = mediaLibraries.length > 0;
    const current = destinationPrecheckIsCurrent(revision, evidence);
    const completed = Boolean(evidence && evidence.status === 'completed');
    const capabilityGap = Boolean(evidence && evidence.result &&
      typeof evidence.result === 'object' && evidence.result.verdict === 'capability_gap');
    const satisfied = !applicable || Boolean(current && completed && !capabilityGap);
    let nextAction = null;
    let message = null;
    let style = 'warning';
    if (applicable && !evidence) {
      nextAction = 'run the read-only destination precheck on this revision, then activate checked';
      message = `Checked activation blocked: ${nextAction}.`;
    } else if (applicable && !current) {
      nextAction = 'reload this revision and rerun the destination precheck on its current version and digest';
      message = `Checked activation blocked: ${nextAction}.`;
    } else if (applicable && !completed) {
      nextAction = boundedSetupText(evidence.nextAction,
        'correct the destination configuration, then rerun the precheck');
      message = `Checked activation blocked: destination precheck failed (${boundedSetupText(evidence.failureCategory)}); ${nextAction}.`;
      style = 'error';
    } else if (applicable && capabilityGap) {
      nextAction = 'change the configured operation or destination Storage, then rerun the precheck';
      message = `Checked activation blocked: ${nextAction}.`;
      style = 'error';
    }
    return {applicable, evidence, current, completed, capabilityGap, satisfied, nextAction, message, style};
  }
  function renderDestinationPrecheck(revision, guided) {
    const activation = destinationPrecheckActivationRequirement(revision, guided);
    const evidence = activation.evidence;
    detailContent.append(text('h3', 'Read-only destination precheck'));
    if (!activation.applicable) detailContent.append(text('p',
      'Checked activation requirement: not applicable because this Draft has no MediaLibrary destination.'));
    else if (!activation.satisfied) detailContent.append(text('p', activation.message, activation.style));
    else detailContent.append(text('p',
      'Checked activation requirement: satisfied by current destination precheck evidence.'));
    if (!evidence) detailContent.append(text('p',
      'Status: not run. This observes one destination without changing it.', 'warning'));
    else {
      const current = activation.current;
      const result = evidence.result && typeof evidence.result === 'object' ? evidence.result : {};
      const conflict = result.conflictProjection && typeof result.conflictProjection === 'object' ?
        result.conflictProjection : {};
      const sampleCount = Number.isFinite(result.sampleCount) ? result.sampleCount : 1;
      if (sampleCount > 1) {
        const runList = document.createElement('dl');
        field(runList, 'Evidence state', current ? 'current' : 'stale');
        field(runList, 'Sample count', String(sampleCount));
        field(runList, 'Status', boundedSetupText(evidence.status));
        field(runList, 'Run verdict (most severe sample)', boundedSetupText(result.verdict || evidence.failureCategory));
        field(runList, 'Destination Storage', `${boundedSetupText(result.destinationStorageId)} (${boundedSetupText(result.destinationStorageType)})`);
        field(runList, 'Storage support', boundedSetupText(result.storageSupport));
        field(runList, 'MediaLibrary and Storage-relative root', `${boundedSetupText(result.mediaLibraryId)}: ${boundedSetupText(result.mediaLibraryRootPath)}`);
        field(runList, 'Destination root exists / directory', `${determinationText(result.destinationRootExists)} / ${determinationText(result.destinationRootIsDirectory)}`);
        field(runList, 'Required capabilities', Array.isArray(result.requiredStorageCapabilities) ? result.requiredStorageCapabilities.join(', ') : '-');
        field(runList, 'Declared destination capabilities', Array.isArray(result.destinationStorageCapabilities) ? result.destinationStorageCapabilities.join(', ') : '-');
        field(runList, 'Missing capabilities', Array.isArray(result.missingStorageCapabilities) ? result.missingStorageCapabilities.join(', ') : '-');
        field(runList, 'Fallback', boundedSetupText(result.fallback));
        field(runList, 'Authority granted', boundedSetupText(result.authorityGranted));
        field(runList, 'Path scope', boundedSetupText(evidence.pathScope));
        field(runList, 'Side effects', boundedSetupText(evidence.sideEffects));
        field(runList, 'Retry safe', evidence.retrySafe === true ? 'YES' : 'NO');
        field(runList, 'Message', boundedSetupText(evidence.message));
        field(runList, 'Next action', boundedSetupText(evidence.nextAction));
        detailContent.append(runList);
        detailContent.append(text('h4', 'First sample destination'));
        const firstList = document.createElement('dl');
        field(firstList, 'Deepest existing ancestor', boundedSetupText(result.deepestExistingAncestor));
        field(firstList, 'Directories that would be created', Array.isArray(result.directoriesToCreate) ? result.directoriesToCreate.join(', ') : '-');
        field(firstList, 'Destination path', boundedSetupText(result.destinationPath));
        field(firstList, 'Target exists', determinationText(result.targetExists));
        field(firstList, 'Configured conflict strategy', boundedSetupText(conflict.configuredStrategy));
        field(firstList, 'Projected conflict outcome', boundedSetupText(conflict.projectedOutcome));
        field(firstList, 'Proposed relative destination', boundedSetupText(conflict.proposedRelativeDestination));
        field(firstList, 'Read operations', Array.isArray(result.probeOperations) ? result.probeOperations.join(', ') : '-');
        detailContent.append(firstList);
      } else {
        const list = document.createElement('dl');
        field(list, 'Evidence state', current ? 'current' : 'stale');
        field(list, 'Sample count', String(sampleCount));
        field(list, 'Status', boundedSetupText(evidence.status));
        field(list, 'Verdict', boundedSetupText(result.verdict || evidence.failureCategory));
        field(list, 'Destination Storage', `${boundedSetupText(result.destinationStorageId)} (${boundedSetupText(result.destinationStorageType)})`);
        field(list, 'Storage support', boundedSetupText(result.storageSupport));
        field(list, 'MediaLibrary and Storage-relative root', `${boundedSetupText(result.mediaLibraryId)}: ${boundedSetupText(result.mediaLibraryRootPath)}`);
        field(list, 'Destination root exists / directory', `${determinationText(result.destinationRootExists)} / ${determinationText(result.destinationRootIsDirectory)}`);
        field(list, 'Deepest existing ancestor', boundedSetupText(result.deepestExistingAncestor));
        field(list, 'Directories that would be created', Array.isArray(result.directoriesToCreate) ? result.directoriesToCreate.join(', ') : '-');
        field(list, 'Destination path', boundedSetupText(result.destinationPath));
        field(list, 'Target exists', determinationText(result.targetExists));
        field(list, 'Configured conflict strategy', boundedSetupText(conflict.configuredStrategy));
        field(list, 'Projected conflict outcome', boundedSetupText(conflict.projectedOutcome));
        field(list, 'Proposed relative destination', boundedSetupText(conflict.proposedRelativeDestination));
        field(list, 'Required capabilities', Array.isArray(result.requiredStorageCapabilities) ? result.requiredStorageCapabilities.join(', ') : '-');
        field(list, 'Declared destination capabilities', Array.isArray(result.destinationStorageCapabilities) ? result.destinationStorageCapabilities.join(', ') : '-');
        field(list, 'Missing capabilities', Array.isArray(result.missingStorageCapabilities) ? result.missingStorageCapabilities.join(', ') : '-');
        field(list, 'Fallback', boundedSetupText(result.fallback));
        field(list, 'Read operations', Array.isArray(result.probeOperations) ? result.probeOperations.join(', ') : '-');
        field(list, 'Authority granted', boundedSetupText(result.authorityGranted));
        field(list, 'Path scope', boundedSetupText(evidence.pathScope));
        field(list, 'Side effects', boundedSetupText(evidence.sideEffects));
        field(list, 'Retry safe', evidence.retrySafe === true ? 'YES' : 'NO');
        field(list, 'Message', boundedSetupText(evidence.message));
        field(list, 'Next action', boundedSetupText(evidence.nextAction));
        detailContent.append(list);
      }
      if (Array.isArray(result.items)) {
        detailContent.append(text('h4', 'Per-sample destination rows'));
        detailContent.append(table(['Sample', 'Destination', 'Projected outcome', 'Failure category', 'Message', 'Next action'],
          result.items.map(item => [
            Number.isFinite(item.index) ? String(item.index) : '-',
            boundedSetupText(item.destinationPath),
            boundedSetupText(item.projectedOutcome),
            boundedSetupText(item.failureCategory),
            boundedSetupText(item.message),
            boundedSetupText(item.nextAction)
          ])));
      }
      if (Array.isArray(result.collisions)) {
        detailContent.append(text('h4', 'Cross-item destination collisions'));
        if (result.collisions.length) detailContent.append(table(['Destination', 'Colliding samples'],
          result.collisions.map(item => [
            boundedSetupText(item.destinationPath),
            Array.isArray(item.itemIndexes) ? item.itemIndexes.join(', ') : '-'
          ])));
        else detailContent.append(text('p', 'No cross-item destination collision detected.'));
      }
      if (!current) detailContent.append(text('p',
        'This destination precheck is stale. Reload and rerun it.', 'warning'));
      if (evidence.status !== 'completed' || result.verdict === 'capability_gap' ||
          !result.destinationRootExists || !result.destinationPath)
        detailContent.append(text('p',
          'Destination is not ready. Follow the recovery action; no authority was granted.', 'error'));
      detailContent.append(text('p',
        'This precheck grants no overwrite, delete or execute authority. Unsupported capabilities fail with no fallback to Copy or Move.',
        'warning'));
    }
    if (!configurationRevisionEditable(revision)) return;
    const controls = text('div', '', 'choices');
    const recognitionType = document.createElement('input');
    recognitionType.setAttribute('aria-label', 'Destination precheck RecognitionType');
    recognitionType.value = 'C';
    const sample = document.createElement('textarea');
    sample.setAttribute('aria-label', 'Destination precheck sample JSON (one object, or an array of 1-8 samples)');
    sample.value = JSON.stringify({title: 'The Matrix', mediaType: 'movie', year: 1999,
      genres: ['Action'], extension: 'mkv'}, null, 2);
    controls.append(text('p', 'An array of samples detects cross-item destination collisions before activation.'));
    controls.append(recognitionType, sample, actionButton('Run read-only destination precheck', async () => {
      try {
        const parsed = JSON.parse(sample.value);
        const body = {expectedVersion: revision.version,
          expectedDigest: revision.digest, recognitionType: recognitionType.value};
        if (Array.isArray(parsed)) body.samples = parsed; else body.sample = parsed;
        const result = await api(`/api/v1/configuration/revisions/${encodeURIComponent(revision.revisionId)}/destination-precheck`,
          {method: 'POST', body: JSON.stringify(body)});
        message(result.status === 'completed' ?
          'Destination precheck completed. Review the read-only verdict.' :
          `${result.message || 'Destination precheck failed.'} ${result.nextAction || ''}`,
          result.status !== 'completed');
        await showConfigurationRevision(revision);
      } catch (error) { message(errorText(error), true); }
    }));
    detailContent.append(controls);
  }
  function setupEvidenceIsCurrent(revision, evidence) {
    return Boolean(evidence && evidence.stale === false &&
      evidence.revisionId === revision.revisionId &&
      evidence.revisionVersion === revision.version &&
      evidence.revisionDigest === revision.digest);
  }
  function renderLocalSetupEvidence(revision, guided) {
    const evidence = guided.localSetupCheck;
    detailContent.append(text('h3', 'Local setup check evidence'));
    if (!evidence || typeof evidence !== 'object') {
      detailContent.append(text('p', 'Status: not run. No setup-check evidence exists for this revision.', 'warning'));
      return;
    }
    const current = setupEvidenceIsCurrent(revision, evidence);
    const status = evidence.status === 'passed' || evidence.status === 'failed' ? evidence.status : 'unknown';
    const operations = Array.isArray(evidence.operations) ? evidence.operations.slice(0, 32)
      .filter(value => typeof value === 'string' && value.length > 0 && value.length <= 128) : [];
    const list = document.createElement('dl');
    field(list, 'Evidence state', current ? 'current' : 'stale');
    field(list, 'Status', status);
    field(list, 'Evidence revision ID', boundedSetupText(evidence.revisionId));
    field(list, 'Evidence version', Number.isInteger(evidence.revisionVersion) ? evidence.revisionVersion : '-');
    field(list, 'Evidence digest', boundedSetupText(evidence.revisionDigest));
    field(list, 'Current version', revision.version);
    field(list, 'Current digest', boundedSetupText(revision.digest));
    field(list, 'Failure category', boundedSetupText(evidence.failureCategory));
    field(list, 'Message', boundedSetupText(evidence.message));
    field(list, 'Source root', boundedSetupText(evidence.sourcePath));
    field(list, 'Destination root', boundedSetupText(evidence.destinationPath));
    field(list, 'Completed operations', operations.length ? operations.join(', ') : '-');
    field(list, 'Duration', Number.isInteger(evidence.durationMs) && evidence.durationMs >= 0 ?
      `${evidence.durationMs} ms` : '-');
    field(list, 'Side effects', boundedSetupText(evidence.sideEffects, 'unknown'));
    field(list, 'Retry safe', typeof evidence.retrySafe === 'boolean' ?
      (evidence.retrySafe ? 'YES' : 'NO') : 'unknown');
    field(list, 'Next action', boundedSetupText(evidence.nextAction));
    detailContent.append(list);
    if (!current) detailContent.append(text('p', revision.status === 'draft' ?
      'This evidence is stale. Finish correcting this Draft, then Validate before rerunning the check.' :
      'This evidence is stale. Run Local setup check again before checked activation.', 'warning'));
  }
  function localSetupSelection(guided) {
    const objects = guided.objects || {};
    const localBackendIds = new Set((objects.storages || [])
      .filter(item => item.type === 'local').map(item => item.id));
    const resources = (objects.resourceLibraries || [])
      .filter(item => item.enabled !== false && localBackendIds.has(item.storageId));
    const media = (objects.mediaLibraries || [])
      .filter(item => item.enabled !== false && localBackendIds.has(item.storageId));
    return {resource: resources[0] || null, media: media[0] || null};
  }
  function renderLocalSetupActions(revision, guided) {
    const evidence = guided.localSetupCheck;
    const selection = localSetupSelection(guided);
    if (revision.status === 'draft') {
      detailContent.append(text('p', 'Validate this Draft before running Local setup check.', 'warning'));
      return;
    }
    if (revision.status !== 'validated') return;
    if (!selection.resource || !selection.media) {
      detailContent.append(text('p',
        'Configure and enable one Local-backed ResourceLibrary and MediaLibrary, then Validate before running Local setup check.',
        'warning'));
      return;
    }
    const action = text('div', '', 'choices');
    action.append(text('p', evidence ? 'Explicitly rerun this bounded read-only check when needed.' :
      'Run a bounded read-only Local setup check before checked activation.', 'warning'));
    action.append(actionButton('Run Local setup check', async () => {
      try {
        const result = await api(`/api/v1/configuration/revisions/${encodeURIComponent(revision.revisionId)}/local-setup-check`,
          {method: 'POST', body: JSON.stringify({expectedVersion: revision.version, expectedDigest: revision.digest,
            resourceLibraryId: selection.resource.id, mediaLibraryId: selection.media.id})});
        message(result.status === 'passed' ? 'Local setup check passed. Review the diff, then activate.' :
          `${result.message || 'Local setup check failed.'} ${result.nextAction || ''} ` +
          `Side effects: ${result.sideEffects || 'unknown'}. Retry safe: ${result.retrySafe === true ? 'yes' : 'no'}.`,
          result.status !== 'passed');
        await showConfigurationRevision(revision);
      } catch (error) { message(errorText(error), true); }
    }));
    detailContent.append(action);
  }
  function strategyEvidenceIsCurrent(revision, evidence) {
    return Boolean(evidence && evidence.stale === false &&
      evidence.revisionId === revision.revisionId &&
      evidence.revisionVersion === revision.version && evidence.revisionDigest === revision.digest);
  }
  function firstStorageCheckBlocker(guided) {
    const objects = guided && guided.objects && typeof guided.objects === 'object' ? guided.objects : {};
    const storages = Array.isArray(objects.storages) ? objects.storages : [];
    const resourceLibraries = Array.isArray(objects.resourceLibraries) ? objects.resourceLibraries : [];
    const mediaLibraries = Array.isArray(objects.mediaLibraries) ? objects.mediaLibraries : [];
    const libraries = resourceLibraries.concat(mediaLibraries);
    for (const library of libraries) {
      const storageId = String(library.storageId || '');
      if (!storageId) return 'correct the library Storage reference';
      const storage = storages.find(item => String(item.id) === storageId);
      if (!storage) return `add the referenced Storage ${storageId}`;
      if (storage.enabled === false) continue;
      const evidence = storageCheckEvidenceFor(guided, storageId);
      if (!evidence) return `run the read-only Storage check for ${storageId}`;
      if (evidence.current !== true || evidence.stale !== false) {
        return `reload this revision and rerun the read-only Storage check for ${storageId}`;
      }
      if (evidence.status !== 'passed') {
        return `correct Storage ${storageId}, rerun its read-only check, then activate checked`;
      }
    }
    return null;
  }
  function referencedStorageChecksSatisfied(guided) {
    return firstStorageCheckBlocker(guided) === null;
  }
  function setupAndStrategyEvidenceIsCurrent(revision, guided) {
    const strategy = guided && guided.recognitionStrategyTest;
    return Boolean(referencedStorageChecksSatisfied(guided) &&
      strategy && strategy.status === 'completed' && strategyEvidenceIsCurrent(revision, strategy));
  }
  function checkedActivationEvidenceIsCurrent(revision, guided) {
    return Boolean(setupAndStrategyEvidenceIsCurrent(revision, guided) &&
      destinationPrecheckActivationRequirement(revision, guided).satisfied);
  }
  function destinationPrecheckBlocksCheckedActivation(revision, guided) {
    const requirement = destinationPrecheckActivationRequirement(revision, guided);
    if (!requirement.message || !setupAndStrategyEvidenceIsCurrent(revision, guided)) return null;
    return requirement;
  }
  function renderStrategyEvidenceRows(label, values) {
    const source = Array.isArray(values) ? values : [];
    const bounded = source.slice(0, 32).filter(item => item && typeof item === 'object');
    detailContent.append(text('h4', `${label} (${bounded.length}; display limit 32)`));
    if (!bounded.length) {
      detailContent.append(text('p', 'None recorded.'));
      return;
    }
    detailContent.append(table(['Rule ID', 'RecognitionType', 'Priority', 'Score'],
      bounded.map(item => [boundedSetupText(item.ruleId), boundedSetupText(item.recognitionType),
        Number.isFinite(item.priority) ? item.priority : '-', Number.isFinite(item.score) ? item.score : '-'])));
    if (source.length >= 32) detailContent.append(text('p',
      'Evidence display limit reached at 32 entries; additional matches may be omitted.', 'warning'));
  }
  function renderMetadataTestEvidence(value, confirmCandidate) {
    if (!value || typeof value !== 'object') return;
    detailContent.append(text('h4', 'Live Metadata Result'));
    const identity = value.identity && typeof value.identity === 'object' ? value.identity : {};
    const match = value.match && typeof value.match === 'object' ? value.match : {};
    const summary = document.createElement('dl');
    field(summary, 'Metadata status', boundedSetupText(value.status));
    field(summary, 'Query', boundedSetupText(value.query));
    field(summary, 'Cache', boundedSetupText(value.cacheStatus, 'not reported'));
    field(summary, 'Selected Provider', boundedSetupText(identity.provider));
    field(summary, 'Selected Provider ID', boundedSetupText(identity.providerId));
    field(summary, 'Selected title', boundedSetupText(identity.title));
    field(summary, 'Canonical / regional year',
      `${Number.isInteger(identity.canonicalYear) ? identity.canonicalYear : '-'} / ${Number.isInteger(identity.regionalYear) ? identity.regionalYear : '-'}`);
    field(summary, 'Confidence', Number.isFinite(identity.confidence) ? identity.confidence : '-');
    field(summary, 'Candidate outcome', boundedSetupText(match.status));
    field(summary, 'Winning score', Number.isFinite(match.score) ? match.score : '-');
    field(summary, 'Candidates projected / total',
      `${Number.isInteger(match.candidateProjected) ? match.candidateProjected : '-'} / ${Number.isInteger(match.candidateTotal) ? match.candidateTotal : '-'}`);
    field(summary, 'Evidence truncated', value.truncated === true || match.truncated === true ? 'YES' : 'NO');
    const selection = value.candidateSelection && typeof value.candidateSelection === 'object' ? value.candidateSelection : null;
    const correction = value.correction && typeof value.correction === 'object' ? value.correction : null;
    field(summary, 'Confirmed candidate rank', selection && Number.isInteger(selection.rank) ? selection.rank : '-');
    field(summary, 'Confirmed Provider / ID', selection ?
      `${boundedSetupText(selection.provider)} / ${boundedSetupText(selection.providerId)}` : '-');
    field(summary, 'Identity match method', boundedSetupText(identity.matchedBy));
    field(summary, 'Correction mode', correction ? boundedSetupText(correction.mode) : '-');
    field(summary, 'Correction query / year', correction && correction.mode === 'query' ?
      `${boundedSetupText(correction.query)} / ${Number.isInteger(correction.year) ? correction.year : '-'}` : '-');
    field(summary, 'Correction Provider ID', correction && correction.mode === 'direct_provider_id' ?
      boundedSetupText(correction.providerId) : '-');
    field(summary, 'Correction media type', correction ? boundedSetupText(correction.mediaType) : '-');
    detailContent.append(summary);
    if (value.truncated === true || match.truncated === true) detailContent.append(text('p',
      'Candidate evidence was reduced to the persisted byte budget; the outcome and highest-ranked evidence are preserved.', 'warning'));
    const reasons = Array.isArray(match.reasons) ? match.reasons.slice(0, 8) : [];
    reasons.forEach(reason => detailContent.append(text('p', `Match reason: ${boundedSetupText(reason)}`)));
    const warnings = Array.isArray(match.warnings) ? match.warnings.slice(0, 8) : [];
    warnings.forEach(warning => detailContent.append(text('p', `Match warning: ${boundedSetupText(warning)}`, 'warning')));
    const candidates = Array.isArray(match.candidates) ? match.candidates.slice(0, 5) : [];
    detailContent.append(text('h4', `Candidate explanation (${candidates.length}; display limit 5)`));
    if (!candidates.length) {
      detailContent.append(text('p', 'No scored candidates were recorded.'));
      return;
    }
    detailContent.append(table(
      ['Provider ID', 'Title', 'Canonical year', 'Score', 'Matched title', 'Title source'],
      candidates.map(candidate => [boundedSetupText(candidate.providerId), boundedSetupText(candidate.title),
        Number.isInteger(candidate.canonicalYear) ? candidate.canonicalYear : '-',
        Number.isFinite(candidate.totalScore) ? candidate.totalScore : '-',
        boundedSetupText(candidate.matchedProviderTitle), boundedSetupText(candidate.matchedTitleSource)])));
    candidates.forEach((candidate, index) => {
      const components = Array.isArray(candidate.components) ? candidate.components.slice(0, 6) : [];
      detailContent.append(text('p', `Candidate ${boundedSetupText(candidate.providerId)} score components:`));
      components.forEach(component => detailContent.append(text('p',
        `${boundedSetupText(component.name)}: ${Number.isFinite(component.score) ? component.score : '-'} - ${boundedSetupText(component.reason)}`)));
      if (typeof confirmCandidate === 'function') detailContent.append(actionButton(
        `Confirm candidate ${index + 1}: ${boundedSetupText(candidate.title)}`,
        () => confirmCandidate(index + 1)));
    });
  }
  function renderRecognitionStrategyTest(revision, guided) {
    const evidence = guided.recognitionStrategyTest;
    detailContent.append(text('h3', 'Recognition Strategy Test'));
    if (!evidence) detailContent.append(text('p', 'Status: not run. Test a synthetic path after validation.', 'warning'));
    else {
      const current = strategyEvidenceIsCurrent(revision, evidence);
      const list = document.createElement('dl');
      field(list, 'Evidence state', current ? 'current' : 'stale');
      field(list, 'Status', boundedSetupText(evidence.status));
      field(list, 'Test mode', boundedSetupText(evidence.result && evidence.result.mode, 'offline'));
      field(list, 'Synthetic path', boundedSetupText(evidence.syntheticPath));
      field(list, 'ResourceLibrary', boundedSetupText(evidence.resourceLibraryId));
      field(list, 'Evidence version', Number.isInteger(evidence.revisionVersion) ? evidence.revisionVersion : '-');
      field(list, 'Evidence digest', boundedSetupText(evidence.revisionDigest));
      const recognition = evidence.result && evidence.result.recognition || {};
      const policy = evidence.result && evidence.result.policy || {};
      const metadataPolicy = evidence.result && evidence.result.effectiveMetadataPolicy || null;
      field(list, 'Recognition outcome', boundedSetupText(recognition.status));
      field(list, 'RecognitionType', boundedSetupText(recognition.recognitionType));
      field(list, 'Matched rule', boundedSetupText(recognition.ruleId));
      field(list, 'Aggregate score', Number.isFinite(recognition.score) ? recognition.score : '-');
      field(list, 'Confidence', Number.isFinite(recognition.confidence) ? recognition.confidence : '-');
      field(list, 'Type policy', boundedSetupText(policy.typePolicyId));
      field(list, 'Metadata / Naming / Classification / Organize',
        [policy.metadataPolicy, policy.namingPolicy, policy.classificationPolicy, policy.organizePolicy]
          .map(value => boundedSetupText(value)).join(' / '));
      field(list, 'RecognitionType preserved', evidence.result && typeof evidence.result.recognitionTypePreserved === 'boolean' ?
        (evidence.result.recognitionTypePreserved ? 'YES' : 'NO') : '-');
      field(list, 'Failure category', boundedSetupText(evidence.failureCategory));
      field(list, 'Message', boundedSetupText(evidence.message));
      field(list, 'Side effects', boundedSetupText(evidence.sideEffects, 'unknown'));
      field(list, 'Retry safe', evidence.retrySafe === true ? 'YES' : 'NO');
      field(list, 'Next action', boundedSetupText(evidence.nextAction));
      detailContent.append(list);
      detailContent.append(text('h4', 'Effective MetadataPolicy'));
      if (metadataPolicy && typeof metadataPolicy === 'object') {
        const metadata = document.createElement('dl');
        field(metadata, 'Policy ID', boundedSetupText(metadataPolicy.id));
        field(metadata, 'Provider ID', boundedSetupText(metadataPolicy.providerId));
        field(metadata, 'Media query type', boundedSetupText(metadataPolicy.mediaQueryType));
        field(metadata, 'Language', boundedSetupText(metadataPolicy.language));
        field(metadata, 'Region', boundedSetupText(metadataPolicy.region));
        field(metadata, 'Automatic / confirmation threshold',
          `${Number.isFinite(metadataPolicy.automaticThreshold) ? metadataPolicy.automaticThreshold : '-'} / ${Number.isFinite(metadataPolicy.confirmationThreshold) ? metadataPolicy.confirmationThreshold : '-'}`);
        field(metadata, 'Minimum score gap', Number.isFinite(metadataPolicy.minimumScoreGap) ? metadataPolicy.minimumScoreGap : '-');
        field(metadata, 'Timeout seconds', Number.isFinite(metadataPolicy.timeout) ? metadataPolicy.timeout : '-');
        field(metadata, 'Retry count', metadataPolicy.retry && Number.isInteger(metadataPolicy.retry.count) ? metadataPolicy.retry.count : '-');
        field(metadata, 'Candidate / page limits',
          `${Number.isInteger(metadataPolicy.maxCandidates) ? metadataPolicy.maxCandidates : '-'} / ${Number.isInteger(metadataPolicy.maxSearchPages) ? metadataPolicy.maxSearchPages : '-'}`);
        field(metadata, 'Provider request / enrichment limits',
          `${Number.isInteger(metadataPolicy.maxProviderRequests) ? metadataPolicy.maxProviderRequests : '-'} / ${Number.isInteger(metadataPolicy.maxCandidateEnrichments) ? metadataPolicy.maxCandidateEnrichments : '-'}`);
        field(metadata, 'Enabled', metadataPolicy.enabled === true ? 'YES' : 'NO');
        detailContent.append(metadata);
      } else {
        detailContent.append(text('p', 'No MetadataPolicy resolved for this outcome. Correct Recognition configuration before retrying.', 'warning'));
      }
      const metadataResult = evidence.result && evidence.result.metadata || null;
      const metadataMatch = metadataResult && metadataResult.match || null;
      const canConfirmCandidate = current && revision.status === 'validated' &&
        evidence.status === 'completed' && evidence.result && evidence.result.mode === 'live' &&
        metadataMatch && (metadataMatch.status === 'need_confirm' || metadataMatch.status === 'ambiguous');
      async function confirmMetadataCandidate(rank) {
        try {
          const result = await api(`/api/v1/configuration/revisions/${encodeURIComponent(revision.revisionId)}/recognition-strategy-test/candidate-selection`,
            {method: 'POST', body: JSON.stringify({expectedVersion: revision.version,
              expectedDigest: revision.digest, expectedTestedAt: evidence.testedAt, candidateRank: rank})});
          message(result.status === 'completed' ?
            `Candidate confirmed. ${boundedSetupText(result.nextAction, 'Review the persisted identity.')}` :
            `${result.message || 'Candidate confirmation failed.'} ${result.nextAction || ''}`,
            result.status !== 'completed');
          await showConfigurationRevision(revision);
        } catch (error) { message(errorText(error), true); }
      }
      renderMetadataTestEvidence(metadataResult,
        canConfirmCandidate ? confirmMetadataCandidate : null);
      const correctionSource = metadataResult && metadataResult.correction &&
        typeof metadataResult.correction === 'object' ? metadataResult.correction.sourceOutcome : null;
      const correctableMetadataOutcomes = ['not_found', 'need_confirm', 'ambiguous'];
      const correctionFailure = metadataResult &&
        ['provider_error', 'configuration_error'].includes(metadataResult.status) &&
        correctableMetadataOutcomes.includes(correctionSource);
      const canCorrectMetadata = current && revision.status === 'validated' && evidence.result &&
        evidence.result.mode === 'live' && metadataResult &&
        (correctableMetadataOutcomes.includes(metadataResult.status) || correctionFailure);
      if (canCorrectMetadata) {
        const correctionControls = text('div', '', 'choices');
        correctionControls.append(text('h4', 'Run Metadata correction test'));
        const correctionMode = document.createElement('select');
        correctionMode.setAttribute('aria-label', 'Metadata correction mode');
        [['query', 'Corrected query'], ['direct_provider_id', 'Direct Provider ID']].forEach(([value, label]) => {
          const option = document.createElement('option'); option.value = value; option.textContent = label;
          correctionMode.append(option);
        });
        const correctionQuery = guidedInput('Corrected query', metadataResult.query || '');
        const correctionYear = guidedInput('Corrected year (optional)', '');
        correctionYear.input.type = 'number'; correctionYear.input.min = '1870'; correctionYear.input.max = '2100';
        const correctionProviderId = guidedInput('Direct Provider ID', '');
        const correctionMediaType = document.createElement('select');
        correctionMediaType.setAttribute('aria-label', 'Corrected media type');
        [['movie', 'Movie'], ['tv', 'TV']].forEach(([value, label]) => {
          const option = document.createElement('option'); option.value = value; option.textContent = label;
          correctionMediaType.append(option);
        });
        function updateCorrectionMode() {
          const direct = correctionMode.value === 'direct_provider_id';
          correctionQuery.input.disabled = direct; correctionYear.input.disabled = direct;
          correctionProviderId.input.disabled = !direct;
        }
        correctionMode.addEventListener('change', updateCorrectionMode); updateCorrectionMode();
        correctionControls.append(correctionMode, correctionQuery.wrapper, correctionYear.wrapper,
          correctionProviderId.wrapper, correctionMediaType);
        correctionControls.append(actionButton('Run Metadata correction test', async () => {
          try {
            const direct = correctionMode.value === 'direct_provider_id';
            const payload = {expectedVersion: revision.version, expectedDigest: revision.digest,
              expectedTestedAt: evidence.testedAt, mediaType: correctionMediaType.value};
            if (direct) payload.providerId = correctionProviderId.input.value;
            else {
              payload.query = correctionQuery.input.value;
              if (correctionYear.input.value !== '') payload.year = Number(correctionYear.input.value);
            }
            const result = await api(`/api/v1/configuration/revisions/${encodeURIComponent(revision.revisionId)}/recognition-strategy-test/metadata-correction`,
              {method: 'POST', body: JSON.stringify(payload)});
            message(result.status === 'completed' ?
              `Metadata correction test completed. ${boundedSetupText(result.nextAction, 'Review persisted evidence.')}` :
              `${result.message || 'Metadata correction test failed.'} ${result.nextAction || ''}`,
              result.status !== 'completed');
            await showConfigurationRevision(revision);
          } catch (error) { message(errorText(error), true); }
        }));
        detailContent.append(correctionControls);
      }
      renderStrategyEvidenceRows('Matched rules', recognition.matchedRules);
      renderStrategyEvidenceRows('Alternatives', recognition.alternatives);
      const reasons = Array.isArray(recognition.reasons) ? recognition.reasons.slice(0, 32) : [];
      reasons.forEach(reason => detailContent.append(text('p',
        `${boundedSetupText(reason.code)}: ${boundedSetupText(reason.message)}`)));
      const warnings = Array.isArray(recognition.warnings) ? recognition.warnings.slice(0, 32) : [];
      warnings.forEach(warning => detailContent.append(text('p',
        `Warning: ${boundedSetupText(warning)}`, 'warning')));
      if (!current) detailContent.append(text('p', 'Evidence is stale. Validate the current Draft and explicitly rerun Strategy Test.', 'warning'));
    }
    if (revision.status === 'draft') {
      detailContent.append(text('p', 'Validate this Draft before running Strategy Test.', 'warning'));
      return;
    }
    if (revision.status !== 'validated') return;
    const resources = (guided.objects && guided.objects.resourceLibraries || [])
      .filter(item => item.enabled !== false);
    if (!resources.length) {
      detailContent.append(text('p', 'Configure and enable a ResourceLibrary, then Validate before testing.', 'warning'));
      return;
    }
    const controls = text('div', '', 'choices');
    const pathControl = guidedInput('Synthetic media path', evidence && evidence.syntheticPath || 'Example.Movie.2024.1080p.mkv');
    const library = document.createElement('select'); library.setAttribute('aria-label', 'Strategy Test ResourceLibrary');
    resources.forEach(item => { const option = document.createElement('option'); option.value = item.id; option.textContent = `${item.id} - ${item.name || item.id}`; library.append(option); });
    controls.append(pathControl.wrapper, library);
    async function runStrategyTest(liveMetadata) {
      try {
        const result = await api(`/api/v1/configuration/revisions/${encodeURIComponent(revision.revisionId)}/recognition-strategy-test`,
          {method: 'POST', body: JSON.stringify({expectedVersion: revision.version, expectedDigest: revision.digest,
            resourceLibraryId: library.value, syntheticPath: pathControl.input.value, liveMetadata})});
        const outcome = result.result && result.result.recognition && result.result.recognition.status;
        message(result.status === 'completed' ?
          (liveMetadata ? `Live Metadata Test completed (${boundedSetupText(outcome, 'unknown')}). ` :
            `Strategy Test completed (${boundedSetupText(outcome, 'unknown')}). `) +
            boundedSetupText(result.nextAction, 'Review the persisted evidence.') :
          `${result.message || 'Strategy Test failed.'} ${result.nextAction || ''}`, result.status !== 'completed');
        await showConfigurationRevision(revision);
      } catch (error) { message(errorText(error), true); }
    }
    controls.append(actionButton('Run Recognition Strategy Test (offline)', () => runStrategyTest(false)));
    controls.append(actionButton('Run live Metadata test', () => runStrategyTest(true)));
    if (checkedActivationEvidenceIsCurrent(revision, guided)) {
      controls.append(actionButton('Activate checked Draft', () => activateConfigurationRevision(revision, true)));
    } else {
      const destination = destinationPrecheckBlocksCheckedActivation(revision, guided);
      if (destination) detailContent.append(text('p', destination.message, destination.style));
    }
    detailContent.append(controls);
  }
  async function activateConfigurationRevision(data, checked) {
    try {
      await api(`/api/v1/configuration/revisions/${encodeURIComponent(data.revisionId)}/activate`,
        {method: 'POST', body: JSON.stringify({expectedVersion: data.version, ...(checked ? {checked: true} : {})})});
      detail.hidden = true; message('Configuration activated. New work will pin this snapshot.');
      await renderConfiguration();
    } catch (error) { message(errorText(error), true); }
  }
  function configurationIdentity(value) {
    if (!value || typeof value !== 'object' || typeof value.revisionId !== 'string' ||
        !value.revisionId || !Number.isInteger(value.version) || typeof value.digest !== 'string' ||
        !value.digest) return null;
    return {revisionId: value.revisionId, version: value.version, digest: value.digest};
  }
  function configurationIdentityMatches(raw, guided) {
    const rawIdentity = configurationIdentity(raw);
    const guidedIdentity = configurationIdentity(guided);
    return Boolean(rawIdentity && guidedIdentity &&
      rawIdentity.revisionId === guidedIdentity.revisionId &&
      rawIdentity.version === guidedIdentity.version && rawIdentity.digest === guidedIdentity.digest);
  }
  function renderConfigurationIdentityMismatch(revision, raw, guided) {
    const rawIdentity = configurationIdentity(raw);
    const guidedIdentity = configurationIdentity(guided);
    detailContent.append(text('h2', 'Configuration changed while loading'));
    detailContent.append(text('p', 'Draft changed while loading; guided actions are withheld until the revision is reloaded.', 'error'));
    const list = document.createElement('dl');
    [['Raw revision', rawIdentity], ['Guided revision', guidedIdentity]].forEach(([label, identity]) => {
      field(list, `${label} ID`, identity && identity.revisionId || '-');
      field(list, `${label} version`, identity && identity.version === 0 ? 0 : identity && identity.version || '-');
      field(list, `${label} digest`, identity && identity.digest || '-');
    });
    detailContent.append(list);
    detailContent.append(text('p', 'Side effects: none. Reload to review one complete revision before editing, checking, validating, or activating.', 'warning'));
    detailContent.append(actionButton('Reload this revision', () => showConfigurationRevision(revision)));
  }
  async function showConfigurationRevision(revision) {
    try {
      const data = await api(`/api/v1/configuration/revisions/${encodeURIComponent(revision.revisionId)}`);
      let guided = null;
      try { guided = await api(`/api/v1/configuration/revisions/${encodeURIComponent(revision.revisionId)}/objects`); }
      catch (error) { message(`Guided configuration is unavailable: ${errorText(error)}`, true); }
      clear(detailContent);
      if (guided && !configurationIdentityMatches(data, guided)) {
        renderConfigurationIdentityMismatch(revision, data, guided);
        detail.hidden = false;
        return;
      }
      detailContent.append(text('h2', 'Configuration revision detail'));
      const list = document.createElement('dl');
      Object.entries(data).filter(([, value]) => !Array.isArray(value) && typeof value !== 'object')
        .forEach(([key, value]) => field(list, key, value)); detailContent.append(list);
      if (data.diff) detailContent.append(text('p', `Changed sections: ${(data.diff.changedSections || []).join(', ') || 'none'}`));
      if (Array.isArray(data.validationErrors) && data.validationErrors.length) {
        detailContent.append(text('h3', 'Validation errors'));
        data.validationErrors.forEach(error => detailContent.append(text('p', error, 'error')));
      }
      if (guided) {
        detailContent.append(text('h3', 'Guided Local setup'));
        detailContent.append(text('p', 'Draft edits are version-checked and audited. Activation uses the exact validated revision.', 'warning'));
        renderGuidedObjectList(data, guided, 'storages', 'Storages');
        renderGuidedObjectList(data, guided, 'resourceLibraries', 'ResourceLibraries');
        renderGuidedObjectList(data, guided, 'mediaLibraries', 'MediaLibraries');
        renderGuidedObjectList(data, guided, 'recognitionTypes', 'RecognitionTypes');
        renderGuidedObjectList(data, guided, 'recognitionRules', 'RecognitionRules');
        renderGuidedObjectList(data, guided, 'recognitionTypePolicies', 'RecognitionTypePolicies');
        renderGuidedObjectList(data, guided, 'metadataPolicies', 'MetadataPolicies');
        renderGuidedObjectList(data, guided, 'namingPolicies', 'NamingPolicies');
        renderGuidedObjectList(data, guided, 'classificationPolicies', 'ClassificationPolicies');
        renderGuidedObjectList(data, guided, 'organizePolicies', 'OrganizePolicies');
        renderGuidedObjectList(data, guided, 'automationTaskDefinitions', 'Automation Task Definitions');
        renderLocalSetupEvidence(data, guided);
        renderLocalSetupActions(data, guided);
        renderRecognitionStrategyTest(data, guided);
        renderNamingPreview(data, guided);
        renderClassificationPreview(data, guided);
        renderOrganizeAuthority(data, guided);
        renderDestinationPreview(data, guided);
        renderDestinationPrecheck(data, guided);
      }
      const actions = text('div', '', 'choices');
      if (data.status === 'draft' && canManageConfiguration) actions.append(actionButton('Validate Draft', async () => {
        try { await api(`/api/v1/configuration/revisions/${encodeURIComponent(data.revisionId)}/validate`,
          {method: 'POST', body: '{}'}); detail.hidden = true; await renderConfiguration();
        } catch (error) { message(errorText(error), true); }
      }));
      if (configurationRevisionEditable(data)) {
        const editor = document.createElement('textarea');
        editor.setAttribute('aria-label', 'Editable configuration JSON');
        editor.value = JSON.stringify(data.document || {}, null, 2);
        detailContent.append(text('h3', 'Edit Draft JSON')); detailContent.append(editor);
        actions.append(actionButton('Save Draft', async () => {
          try {
            const parsed = JSON.parse(editor.value);
            await api(`/api/v1/configuration/revisions/${encodeURIComponent(data.revisionId)}`,
              {method: 'PUT', body: JSON.stringify({document: parsed, expectedVersion: data.version})});
            message('Draft saved and returned to Draft state. Validate it again.');
            detail.hidden = true; await renderConfiguration();
          } catch (error) { message(errorText(error), true); }
        }));
      }
      if (data.status === 'validated') {
        if (canActivateConfiguration) {
          const checked = guided && checkedActivationEvidenceIsCurrent(data, guided);
          actions.append(actionButton(checked ? 'Activate checked revision' :
            (guided ? 'Activate unchecked compatibility revision' : 'Activate revision'),
            () => activateConfigurationRevision(data, Boolean(checked))));
          if (!checked && guided) {
            const destination = destinationPrecheckBlocksCheckedActivation(data, guided);
            const storageBlocker = firstStorageCheckBlocker(guided);
            const warning = destination ?
              `Activation is available for compatibility, but checked activation is blocked by the destination precheck; ${destination.nextAction}.` :
              storageBlocker ?
              `Activation is available for compatibility, but checked activation is blocked: ${storageBlocker}.` :
              'Activation is available for compatibility, but the guided safe path requires current passed read-only Storage checks for every referenced enabled Storage and a current completed Recognition Strategy Test.';
            actions.append(text('p', warning, 'warning'));
          }
        }
      }
      if (data.status === 'active') actions.append(actionButton('Queue first DryRun Preview', async () => {
        try { const job = await api('/api/v1/jobs', {method: 'POST', body: JSON.stringify({command: 'preview'})});
          message(`DryRun Preview queued: ${job.job_id || job.jobId || '-'}`); }
        catch (error) { message(errorText(error), true); }
      }));
      detailContent.append(actions); detail.hidden = false;
    } catch (error) { message(errorText(error), true); }
  }
  function table(headers, rows, onRow) {
    const tableNode = document.createElement('table');
    const head = document.createElement('thead'); const headerRow = document.createElement('tr');
    headers.forEach(value => headerRow.append(text('th', value))); head.append(headerRow);
    const body = document.createElement('tbody');
    rows.forEach((values, index) => {
      const row = document.createElement('tr');
      values.forEach(value => row.append(value && value.nodeType ? value : text('td', value)));
      if (onRow) { row.tabIndex = 0; row.addEventListener('click', () => onRow(index));
        row.addEventListener('keydown', event => { if (event.key === 'Enter') onRow(index); }); }
      body.append(row);
    }); tableNode.append(head, body); return tableNode;
  }
  function itemId(kind, item) {
    if (kind === 'confirmations') return item.confirmationId || item.confirmation_id;
    if (kind === 'metadata-reviews' || kind === 'recognition-reviews' ||
      kind === 'metadata-corrections') return item.review_id || item.reviewId;
    if (kind === 'files') return item.fileId || item.file_id;
    return item.review_id;
  }
  async function renderQueue(kind) {
    const query = kind === 'confirmations' ? '?status=pending&limit=100' : '?limit=100';
    const data = await api(`/api/v1/${kind}${query}`); const items = data.items || [];
    clear(content); content.append(text('h2', {
      confirmations: 'Conflict confirmations', 'recognition-reviews': 'Recognition reviews',
      'metadata-reviews': 'Metadata reviews', 'metadata-corrections': 'Metadata corrections',
      'classification-reviews': 'Classification reviews'}[kind]));
    const rows = items.map(item => [itemId(kind, item), item.status,
      item.recognition_type || item.conflictType || '-', item.updated_at || item.createdAt || '-']);
    content.append(table(['ID', 'Status', 'Type', 'Updated'], rows,
      index => showDetail(kind, itemId(kind, items[index]))));
  }
  function pageNavigation(target, noun, previousCursor, nextCursor, previous, next) {
    if (!previousCursor && !nextCursor) return;
    target.append(text('p', `Showing one page of ${noun}. Reselect the tab to refresh from first.`,
      'warning'));
    if (previousCursor) target.append(actionButton(`Previous ${noun}`, previous));
    if (nextCursor) target.append(actionButton(`Next ${noun}`, next));
  }
  function renderFileReMatchForm(id) {
    const query = document.createElement('input'); query.setAttribute('aria-label', 'Corrected query');
    const media = document.createElement('select'); media.setAttribute('aria-label', 'Media type');
    ['movie', 'tv'].forEach(value => { const option = text('option', value); option.value = value;
      media.append(option); });
    const year = document.createElement('input'); year.type = 'number'; year.min = '1870';
    year.max = '2100'; year.setAttribute('aria-label', 'Corrected year');
    const providerId = document.createElement('input');
    providerId.setAttribute('aria-label', 'Direct provider ID');
    const controls = text('div', '', 'choices'); controls.append(query, media, year, providerId,
      actionButton('Request re-match', async () => {
        const payload = {mediaType: media.value};
        if (query.value.trim()) payload.query = query.value.trim();
        if (year.value) payload.year = Number(year.value);
        if (providerId.value.trim()) payload.providerId = providerId.value.trim();
        try {
          await api(`/api/v1/files/${encodeURIComponent(id)}/re-match`,
            {method: 'POST', body: JSON.stringify(payload)});
          detail.hidden = true; message('Metadata re-match requested. Task was not resumed.');
          await load();
        } catch (error) { message(errorText(error), true); }
      }));
    detailContent.append(text('h3', 'Metadata re-match'), controls);
  }
  function renderMetadataContinuation(id, review) {
    const current = review.continuation;
    const section = text('div', '', 'choices');
    section.append(text('h3', 'Metadata correction DryRun continuation'));
    section.append(cards([
      ['Source Task', review.taskId], ['Source item', review.itemId || '-'],
      ['Correction', review.reviewId], ['Correction identity', review.correctionVersion],
      ['Configuration snapshot', review.configurationSnapshotId || '-'],
      ['Configuration digest', review.configurationSnapshotDigest || '-'],
      ['Items selected', '1'], ['Authority', 'DRY_RUN_ONLY'], ['Storage mutation', 'NONE']
    ]));
    if (current) {
      section.append(text('p', `Continuation status: ${current.status}. ` +
        `Job: ${current.jobId}. Task: ${current.taskId || '-'}. ` +
        `Result: ${current.resultId || '-'}.`, current.status === 'failed' ? 'error' : 'warning'));
      if (current.failureCategory) {
        section.append(text('p', `Failure category: ${current.failureCategory}.` +
          ' Restore the pinned snapshot before retrying.', 'error'));
      }
      if (current.error) section.append(text('p', `Failure: ${current.error}`, 'error'));
      if (current.recovery) section.append(text('p', `Recovery: ${current.recovery}`));
      if (current.nextAction) section.append(text('p', `Next action: ${current.nextAction}`));
      const links = text('div', '', 'choices');
      links.append(actionButton('Open continuation job', () => showJob(current.jobId)));
      if (current.taskId) {
        links.append(actionButton('Open linked Task/Result', () => showTask(current.taskId)));
      }
      if ((current.status === 'failed' || current.status === 'cancelled') && review.canContinue) {
        links.append(actionButton('Retry this correction as DryRun', () =>
          confirmMetadataContinuation(id, review)));
      }
      if (current.status === 'stale') {
        links.append(actionButton('Requeue stale continuation', () =>
          confirmStaleMetadataContinuation(id, current.jobId)));
      }
      section.append(links);
      detailContent.append(section);
      return;
    }
    section.append(text('p',
      'Only this TaskItem will be analyzed. Source media is not modified and no execute authority is inherited.',
      'warning'));
    section.append(actionButton('Continue as DryRun', () =>
      confirmMetadataContinuation(id, review)));
    detailContent.append(section);
  }
  function confirmMetadataContinuation(id, review) {
    const confirmation = text('div', '', 'choices');
    confirmation.append(text('p',
      `Continue only Metadata correction ${review.reviewId} as a new DryRun? ` +
      `The pinned configuration is ${review.configurationSnapshotId || 'unavailable'}. ` +
      'No media mutation or execute authority is inherited.'));
    confirmation.append(actionButton('Confirm Continue as DryRun', async () => {
      try {
        await api(`/api/v1/files/${encodeURIComponent(id)}/continue-dry-run`, {
          method: 'POST',
          body: JSON.stringify({
            reviewId: review.reviewId,
            expectedCorrectionVersion: review.correctionVersion
          })
        });
        detail.hidden = true;
        message('One-item DryRun continuation queued. Source Task and siblings are unchanged.');
        await load();
      } catch (error) { message(errorText(error), true); }
    }), actionButton('Keep source unchanged', () => confirmation.remove()));
    detailContent.append(confirmation);
  }
  function confirmStaleMetadataContinuation(id, jobId) {
    const confirmation = text('div', '', 'choices');
    confirmation.append(text('p',
      'Stale is an age observation, not proof that the Worker stopped. Inspect the Job, then explicitly requeue it? ' +
      'The continuation remains DryRun-only and the source stays unchanged.'));
    confirmation.append(actionButton('Confirm requeue stale Job', async () => {
      try {
        await api(`/api/v1/jobs/${encodeURIComponent(jobId)}/requeue-stale`, {method: 'POST'});
        detail.hidden = true;
        message('Stale continuation requeued. Reloading the File state.');
        await load();
      } catch (error) { message(errorText(error), true); }
    }), actionButton('Keep stale Job', () => confirmation.remove()));
    detailContent.append(confirmation);
  }
  async function renderFiles() {
    let status;
    try {
      status = await api('/api/v1/system/status');
    } catch (error) {
      clear(content); content.append(text('h2', 'Files'));
      content.append(text('p', errorText(error), 'error'));
      content.append(actionButton('Retry Files', renderFiles));
      return;
    }
    const storageSection = status && status.storages;
    const storages = storageSection && Array.isArray(storageSection.items) ?
      storageSection.items : [];
    const librarySection = status && status.resource_libraries;
    const resourceLibraries = librarySection && Array.isArray(librarySection.items) ?
      librarySection.items : [];
    clear(content); content.append(text('h2', 'Files'));
    content.append(text('p',
      'Browse immediate entries from the configured Active Storage. This is read-only and separate from FileIndex.',
      'warning'));
    if (!storages.length) {
      content.append(text('p', 'No configured Storage is available in the current Active runtime.', 'warning'),
        actionButton('Retry Files', renderFiles));
      return;
    }
    let selectedStorage = storages[0].id;
    let currentPath = '';
    const storageSelect = document.createElement('select');
    storageSelect.setAttribute('aria-label', 'Configured Storage');
    storages.forEach(storage => {
      const option = document.createElement('option'); option.value = storage.id;
      option.textContent = `${storage.id} (${storage.type || 'Storage'})`;
      storageSelect.append(option);
    });
    const controls = text('div', '', 'choices');
    const loadPage = async (cursor = null) => {
      const query = new URLSearchParams();
      query.set('storageId', selectedStorage); query.set('limit', '50');
      if (currentPath) query.set('path', currentPath);
      if (cursor) query.set('cursor', cursor);
      let data;
      try {
        data = await api(`/api/v1/storage/files?${query.toString()}`);
      } catch (error) {
        clear(content); content.append(text('h2', 'Files'));
        content.append(text('p', errorText(error), 'error'));
        content.append(actionButton('Retry page', () => loadPage(cursor)));
        return;
      }
      clear(content); content.append(text('h2', 'Files'));
      content.append(text('p',
        `Active runtime ${data.configuration && data.configuration.revisionId || '-'}; ` +
        'Storage browsing is read-only. Use FileIndex for indexed discovery state.', 'warning'));
      clear(controls);
      const storageLabel = text('label', 'Storage '); storageLabel.append(storageSelect);
      controls.append(storageLabel, actionButton('Refresh Files', () => loadPage(null)));
      controls.append(manualScanLibraryControls(resourceLibraries, selectedStorage));
      const breadcrumbs = text('div', '', 'choices');
      (Array.isArray(data.breadcrumbs) ? data.breadcrumbs : []).forEach(crumb => {
        breadcrumbs.append(actionButton(crumb.path ? crumb.name : 'Storage root', () => {
          currentPath = crumb.path || ''; loadPage(null);
        }));
      });
      content.append(controls, breadcrumbs);
      const items = Array.isArray(data.entries) ? data.entries : [];
      if (!items.length) content.append(text('p', 'This configured directory is empty.', 'warning'));
      const rows = items.map(item => {
        const membership = item.indexMembership || {};
        const membershipText = !membership.available ? 'FileIndex unavailable' :
          membership.indexed ? `Indexed (${membership.total || 0})` : 'Not indexed';
        const scanPayload = item.isDirectory ? null : manualScanPayloadFromMembership(membership);
        const scanAction = scanPayload ? actionButton('Scan file', () =>
          confirmManualScan(scanPayload, `Scan current FileIndex item ${scanPayload.fileId}`)) :
          text('span', item.isDirectory ? '-' : 'Scan unavailable until a verified current item exists');
        const previewPayload = item.isDirectory ? null : manualPreviewPayloadFromMembership(membership);
        const previewAction = previewPayload ? actionButton('Preview file', () =>
          confirmCurrentPreview(previewPayload, `Preview current FileIndex item ${previewPayload.fileId}`)) :
          text('span', item.isDirectory ? '-' : 'Preview unavailable until a verified current item exists');
        return [item.isDirectory ? actionButton(`Open ${item.name}`, () => {
          currentPath = item.path; loadPage(null);
        }) : item.name, item.type, item.size, item.modifiedAt, membershipText, scanAction,
          previewAction];
      });
      if (items.length) content.append(table(
        ['Name', 'Type', 'Size', 'Modified', 'FileIndex', 'Manual Scan', 'Preview'], rows));
      if (data.nextCursor) content.append(actionButton('Next page', () => loadPage(data.nextCursor)));
    };
    storageSelect.addEventListener('change', () => {
      selectedStorage = storageSelect.value; currentPath = ''; loadPage(null);
    });
    await loadPage();
  }
  async function renderFileIndex() {
    clear(content); content.append(text('h2', 'FileIndex'));
    content.append(text('p',
      'FileIndex separates Storage discovery/stability from current-source processing disposition. ' +
      'FileIndex is not a configured Storage browser.',
      'warning'));
    const selectedFileIds = new Set();
    const filters = [
      ['resourceLibrary', 'Resource library'], ['storage', 'Storage'],
      ['query', 'Path/filename'], ['recognitionType', 'Recognition type'],
      ['provider', 'Provider'], ['providerId', 'Provider ID'], ['title', 'Title'],
      ['taskId', 'Task ID'], ['year', 'Year']
    ].map(([name, label]) => {
      const labelNode = text('label', label); const input = document.createElement('input');
      input.setAttribute('aria-label', label); input.name = name; labelNode.append(input);
      return labelNode;
    });
    const status = document.createElement('select'); status.setAttribute('aria-label', 'Scan status');
    ['', 'discovered', 'unstable', 'ready', 'ignored', 'missing', 'error'].forEach(value => {
      const option = text('option', value || 'All scan statuses'); option.value = value;
      status.append(option);
    });
    const form = text('div', '', 'choices'); filters.forEach(item => form.append(item));
    form.append(status);
    const loadFiles = async () => {
      const parts = ['limit=100'];
      filters.forEach(node => {
        const input = node.querySelector('input');
        if (input && input.value.trim()) parts.push(`${input.name}=${encodeURIComponent(input.value.trim())}`);
      });
      if (status.value) parts.push(`scanStatus=${encodeURIComponent(status.value)}`);
      // The server keeps /api/v1/files? as a compatibility alias for this FileIndex request.
      const data = await api(`/api/v1/file-index?${parts.join('&')}`);
      const items = data.items || [];
      clear(content); content.append(text('h2', 'FileIndex'));
      content.append(text('p',
        'These are indexed discovery records; use Files to browse the configured Storage directly.',
        'warning'));
      const rows = items.map(item => {
        const fileId = item.fileId || item.file_id;
        const checkbox = document.createElement('input'); checkbox.type = 'checkbox';
        checkbox.checked = selectedFileIds.has(fileId); checkbox.value = fileId;
        checkbox.setAttribute('aria-label', `Select file ${fileId}`);
        checkbox.addEventListener('click', event => event.stopPropagation());
        checkbox.addEventListener('change', () => {
          if (checkbox.checked) selectedFileIds.add(fileId); else selectedFileIds.delete(fileId);
          message(`${selectedFileIds.size} file(s) selected; selection is bounded to 100 items.`);
        });
        const cell = text('span', ''); cell.append(checkbox, text('span', ` ${fileId}`));
        const occurrence = item.currentOccurrence || {};
        const scanPayload = manualScanPayloadFromFile(item);
        const scanAction = scanPayload ? actionButton('Scan', () =>
          confirmManualScan(scanPayload, `Scan current FileIndex item ${fileId}`)) :
          text('span', 'Scan unavailable until source is ready');
        const previewPayload = manualPreviewPayloadFromFile(item);
        const previewAction = previewPayload ? actionButton('Preview', () =>
          confirmCurrentPreview(previewPayload, `Preview current FileIndex item ${fileId}`)) :
          text('span', 'Preview unavailable until source is verified');
        return [cell, item.path, item.scanStatus || item.scan_status,
          item.processingDisposition || '-', occurrence.occurrenceId || 'unverified',
          item.updatedAt || item.updated_at, scanAction, previewAction];
      });
      content.append(table(['ID', 'Path', 'Scan / discovery', 'Processing disposition',
        'Current occurrence', 'Updated', 'Manual Scan', 'Preview'], rows,
        index => showDetail('files', items[index].fileId || items[index].file_id)));
      content.append(actionButton('Start manual organize for selected files', () =>
        confirmManualIntent(Array.from(selectedFileIds))));
      content.append(actionButton('Scan selected FileIndex item', () => {
        if (selectedFileIds.size !== 1) {
          message('Select exactly one current FileIndex item for a bounded manual Scan.', true);
          return;
        }
        const selected = items.find(item => (item.fileId || item.file_id) ===
          Array.from(selectedFileIds)[0]);
        const payload = manualScanPayloadFromFile(selected);
        if (!payload) {
          message('The selected item has no verified current source identity; refresh FileIndex.', true);
          return;
        }
        confirmManualScan(payload, `Scan current FileIndex item ${payload.fileId}`);
      }));
      content.append(actionButton('Refresh FileIndex', loadFiles));
    };
      content.append(form, actionButton('Search files', loadFiles));
  }
  function confirmManualScan(payload, label, onQueued = null) {
    clear(detailContent);
    const confirmation = text('div', '', 'choices');
    confirmation.append(text('h2', 'Confirm manual Scan'), text('p',
      `${label || 'Start this bounded discovery Scan'}? ` +
      'The request is pinned to the current Active runtime and performs FileIndex discovery only. ' +
      'It does not call a Provider, create a Preview, grant execution authority, organize media, ' +
      'or mutate Storage.', 'warning'));
    confirmation.append(actionButton('Confirm manual Scan', async () => {
      try {
        const result = await api('/api/v1/scans', {
          method: 'POST', body: JSON.stringify(payload)
        });
        confirmation.remove();
        if (typeof onQueued === 'function') await onQueued(result);
        await showTask(result.taskId || result.task_id);
        message(`Manual Scan Task ${result.taskId || result.task_id} admitted. ` +
          'Inspect its durable progress and per-item discovery outcomes.');
      } catch (error) { message(errorText(error), true); }
    }), actionButton('Keep source unchanged', () => confirmation.remove()));
    detailContent.append(confirmation); detail.hidden = false;
  }
  function manualScanPayloadFromMembership(membership) {
    const item = membership && Array.isArray(membership.memberships) &&
      membership.memberships.length === 1 ? membership.memberships[0] : null;
    if (!item || item.scanStatus !== 'ready' || item.fingerprintState !== 'verified' ||
        !item.fileId || !item.resourceLibraryId || !item.occurrenceId || !item.fingerprint) {
      return null;
    }
    return {
      scopeKind: 'file', mode: 'incremental', fileId: item.fileId,
      resourceLibraryId: item.resourceLibraryId, occurrenceId: item.occurrenceId,
      fingerprint: item.fingerprint
    };
  }
  function manualScanPayloadFromFile(item) {
    const occurrence = item && (item.currentOccurrence || {});
    if (!item || item.scanStatus !== 'ready' || occurrence.state !== 'verified' ||
        !item.fileId || !item.resourceLibraryId || !occurrence.occurrenceId ||
        !occurrence.fingerprint) return null;
    return {
      scopeKind: 'file', mode: 'incremental', fileId: item.fileId,
      resourceLibraryId: item.resourceLibraryId, occurrenceId: occurrence.occurrenceId,
      fingerprint: occurrence.fingerprint
    };
  }
  function manualPreviewPayloadFromFile(item) {
    const scan = manualScanPayloadFromFile(item);
    if (!scan) return null;
    return {scopeKind: 'file', resourceLibraryId: scan.resourceLibraryId,
      occurrenceId: scan.occurrenceId, fingerprint: scan.fingerprint,
      fileId: scan.fileId};
  }
  function manualPreviewPayloadFromMembership(membership) {
    const item = membership && Array.isArray(membership.memberships) &&
      membership.memberships.length === 1 ? membership.memberships[0] : null;
    if (!item || item.scanStatus !== 'ready' || item.fingerprintState !== 'verified' ||
        !item.fileId || !item.resourceLibraryId || !item.occurrenceId || !item.fingerprint) {
      return null;
    }
    return {scopeKind: 'file', fileId: item.fileId,
      resourceLibraryId: item.resourceLibraryId, occurrenceId: item.occurrenceId,
      fingerprint: item.fingerprint};
  }
  function confirmCurrentPreview(payload, label, onDone = null) {
    if (!payload || !payload.scopeKind || !payload.resourceLibraryId ||
        (payload.scopeKind === 'file' &&
          (!payload.fileId || !payload.occurrenceId || !payload.fingerprint))) {
      message('Preview is unavailable until a verified current FileIndex occurrence is selected.', true);
      return;
    }
    clear(detailContent);
    const confirmation = text('div', '', 'choices');
    confirmation.append(text('h2', 'Confirm current-source Preview'), text('p',
      `${label || 'Run this bounded Preview'}? The current FileIndex occurrence and immutable ` +
      'Active snapshot will be checked. The complete analysis is persisted for inspection; ' +
      'no Task, review backlog, execution authority or Storage mutation is created.', 'warning'));
    confirmation.append(actionButton('Confirm Preview', async () => {
      try {
        const result = await api('/api/v1/manual-previews', {
          method: 'POST', body: JSON.stringify(payload)
        });
        confirmation.remove();
        if (typeof onDone === 'function') await onDone(result);
        await showManualPreview(result.previewId);
        message('Current-source Preview persisted. Storage was not changed and no execution authority was created.');
      } catch (error) { message(errorText(error), true); }
    }), actionButton('Keep source unchanged', () => confirmation.remove()));
    detailContent.append(confirmation); detail.hidden = false;
  }
  function manualScanLibraryControls(libraries, storageId) {
    const available = (Array.isArray(libraries) ? libraries : []).filter(item =>
      item.storage_id === storageId && item.enabled !== false);
    const section = text('div', '', 'choices');
    if (!available.length) return section;
    section.append(text('span', 'Manual ResourceLibrary Scan: '));
    const mode = document.createElement('select'); mode.setAttribute('aria-label', 'Manual Scan mode');
    ['full', 'incremental'].forEach(value => {
      const option = text('option', value); option.value = value; mode.append(option);
    });
    section.append(mode);
    available.forEach(item => {
      section.append(actionButton(`Scan ${item.id}`, () =>
        confirmManualScan({scopeKind: 'resource_library', resourceLibraryId: item.id, mode: mode.value},
          `Scan ResourceLibrary ${item.id} (${mode.value})`)));
      section.append(actionButton(`Preview ${item.id}`, () =>
        confirmCurrentPreview({scopeKind: 'resource_library', resourceLibraryId: item.id},
          `Preview ResourceLibrary ${item.id}`)));
    });
    return section;
  }
  function confirmFileReprocess(id, data) {
    const occurrence = data && data.currentOccurrence || {};
    const required = data && data.reprocess && data.reprocess.required || occurrence;
    const occurrenceId = required.occurrenceId || occurrence.occurrenceId;
    const fingerprint = required.fingerprint || occurrence.fingerprint;
    if (!occurrenceId || !fingerprint) {
      message('Reprocess is unavailable because current source evidence is not verified.', true);
      return;
    }
    const confirmation = text('div', '', 'choices');
    confirmation.append(text('p',
      `Request bounded Reprocess for occurrence ${occurrenceId} with fingerprint ${fingerprint}? ` +
      'This admits an auditable request only. It creates no Task, calls no Provider, and performs no Storage mutation.',
      'warning'));
    confirmation.append(actionButton('Confirm Reprocess admission', async () => {
      try {
        const result = await api(`/api/v1/files/${encodeURIComponent(id)}/reprocess`, {
          method: 'POST', body: JSON.stringify({occurrenceId, fingerprint})
        });
        confirmation.remove();
        message(`Reprocess admitted for ${result.occurrenceId}. No Task or media side effect occurred. ` +
          `${result.nextAction || 'Run the later explicit Scan or Preview admission.'}`);
        await showDetail('files', id);
      } catch (error) { message(errorText(error), true); }
    }), actionButton('Keep current occurrence unchanged', () => confirmation.remove()));
    detailContent.append(confirmation);
  }
  function confirmManualIntent(fileIds) {
    const values = Array.from(new Set(fileIds || []));
    if (!values.length || values.length > 100) {
      message('Select between 1 and 100 current indexed files before starting manual organize.', true);
      return;
    }
    clear(detailContent);
    detailContent.append(text('h2', 'Confirm manual-organize intent'),
      text('p', `Create one durable intent for ${values.length} indexed file(s)? ` +
        'The exact FileIndex identities and current Managed Active snapshot will be pinned. ' +
        'No Preview, Provider request, Task, authorization or media mutation occurs now.', 'warning'),
      actionButton('Confirm create intent', async () => {
        try {
          const intent = await api('/api/v1/manual-intents', {
            method: 'POST', body: JSON.stringify({fileIds: values})
          });
          message('Manual intent created. Review the pinned snapshot and choices below.');
          await showManualIntent(intent.intentId);
        } catch (error) { message(errorText(error), true); }
      }), actionButton('Keep files unchanged', () => { detail.hidden = true; }));
    detail.hidden = false;
  }
  function manualOption(options, id) {
    return (Array.isArray(options) ? options : []).find(item => item.id === id) || null;
  }
  function manualSelect(label, values, selected) {
    const select = document.createElement('select');
    select.setAttribute('aria-label', label);
    (Array.isArray(values) ? values : []).forEach(item => {
      const option = document.createElement('option'); option.value = item.id;
      option.textContent = `${item.id} - ${item.name || item.id}`;
      option.selected = item.id === selected; select.append(option);
    });
    return select;
  }
  async function showManualIntent(intentId) {
    try {
      const data = await api(`/api/v1/manual-intents/${encodeURIComponent(intentId)}`);
      clear(detailContent); detailContent.append(text('h2', 'Manual-organize intent'));
      const snapshot = document.createElement('dl');
      field(snapshot, 'Intent', data.intentId); field(snapshot, 'Status', data.status);
      field(snapshot, 'Intent version', data.version);
      field(snapshot, 'Actor', data.actor);
      field(snapshot, 'Pinned Active snapshot', data.configurationSnapshotId);
      field(snapshot, 'Pinned digest', data.configurationSnapshotDigest);
      field(snapshot, 'Side effects', data.sideEffects || 'none');
      field(snapshot, 'Next action', data.nextAction || '-');
      detailContent.append(snapshot);
      const options = data.options || {};
      const items = Array.isArray(data.items) ? data.items : [];
      const previewSelections = new Set(items.map(item => item.itemId));
      detailContent.append(text('h3', `Selected items (${items.length})`));
      items.forEach(item => {
        const source = item.source || {}; const choice = item.choice || {};
        const section = text('div', '', 'choices');
        section.append(text('h4', `${item.itemId} - ${source.filename || source.fileId || '-'}`));
        if (data.status === 'open') {
          const include = document.createElement('input'); include.type = 'checkbox';
          include.checked = true; include.setAttribute('aria-label', `Include ${item.itemId} in Preview`);
          include.addEventListener('change', () => {
            if (include.checked) previewSelections.add(item.itemId);
            else previewSelections.delete(item.itemId);
          });
          const includeLabel = text('label', 'Include this item in Preview');
          includeLabel.append(include); section.append(includeLabel);
        }
        section.append(text('p', `${source.storageId || '-'} / ${source.resourceLibraryId || '-'} / ${source.path || '-'}`));
        section.append(text('p', `Status: ${item.status}; version: ${item.version}; ` +
          `${item.error || item.nextAction || ''}`, item.status === 'invalid' || item.status === 'stale' ? 'error' : ''));
        const type = manualSelect('RecognitionType', options.recognitionTypes, choice.recognitionTypeId);
        const naming = manualSelect('NamingPolicy', options.namingPolicies, choice.namingPolicyId);
        const classification = manualSelect('ClassificationPolicy', options.classificationPolicies, choice.classificationPolicyId);
        const organize = manualSelect('OrganizePolicy', options.organizePolicies, choice.organizePolicyId);
        const controls = text('div', '', 'choices'); controls.append(type, naming, classification, organize);
        const metadataPolicy = manualOption(options.metadataPolicies,
          (manualOption(options.recognitionTypes, choice.recognitionTypeId) || {}).metadataPolicyId);
        const metadataBox = text('div', '', 'choices');
        metadataBox.append(text('span', `Metadata policy: ${metadataPolicy ? metadataPolicy.id : '-'}; ` +
          `Provider: ${metadataPolicy ? metadataPolicy.providerId || '-' : '-'}`));
        const providerId = document.createElement('input'); providerId.type = 'text';
        providerId.value = choice.metadata && choice.metadata.providerId || '';
        providerId.placeholder = 'Normalized provider ID (optional)';
        providerId.setAttribute('aria-label', 'Metadata provider ID'); metadataBox.append(providerId);
        const mediaType = document.createElement('select'); mediaType.setAttribute('aria-label', 'Metadata media type');
        ['', 'movie', 'tv'].forEach(value => { const option = document.createElement('option');
          option.value = value; option.textContent = value || 'Use configured media type';
          option.selected = value === ((choice.metadata && choice.metadata.mediaType) || ''); mediaType.append(option); });
        metadataBox.append(mediaType);
        const title = document.createElement('input'); title.type = 'text';
        title.value = choice.metadata && choice.metadata.title || '';
        title.placeholder = 'Bounded title hint (optional)'; title.setAttribute('aria-label', 'Metadata title');
        metadataBox.append(title);
        const year = document.createElement('input'); year.type = 'number';
        year.value = choice.metadata && choice.metadata.year || '';
        year.placeholder = 'Year (optional)'; year.setAttribute('aria-label', 'Metadata year');
        metadataBox.append(year);
        metadataBox.append(text('small', 'Only a normalized provider identity is sent; raw Provider payloads are not accepted.'));
        controls.append(metadataBox);
        controls.append(actionButton('Review and save this item choice', () => confirmManualChoice(data, item,
          {recognitionTypeId: type.value, namingPolicyId: naming.value,
            classificationPolicyId: classification.value, organizePolicyId: organize.value,
            metadata: providerId.value.trim() ? {provider: metadataPolicy && metadataPolicy.providerId,
              providerId: providerId.value.trim(), mediaType: mediaType.value ||
                metadataPolicy && metadataPolicy.mediaType, title: title.value.trim() || undefined,
              year: year.value === '' ? undefined : Number(year.value)} : undefined})));
        section.append(controls);
        if (data.status === 'open') section.append(actionButton('Preview this item',
          () => confirmManualPreview(data, [item])));
        detailContent.append(section);
      });
      if (data.status === 'open' && items.length) {
        detailContent.append(actionButton('Preview all intent items', () =>
          confirmManualPreview(data, items.filter(item => previewSelections.has(item.itemId)))));
        detailContent.append(text('p',
          'Preview is an explicit analysis operation. It persists exact destinations and ' +
          'per-item blockers, performs no Storage mutation, and creates no Task, Job or ' +
          'execution authorization.', 'warning'));
      }
      if (data.status === 'open') detailContent.append(actionButton('Cancel intent', () =>
        confirmCancelManualIntent(data)));
      renderManualExecutionDiscovery(data.manualExecutionDiscovery);
      if (Array.isArray(data.audit) && data.audit.length) {
        detailContent.append(text('h3', `Audit (${data.audit.length})`), table(
          ['Audit', 'Action', 'Actor', 'Item', 'Occurred'],
          data.audit.map(item => [item.auditId, item.action, item.actor, item.itemId || '-', item.occurredAt])));
      }
      detail.hidden = false;
    } catch (error) { message(errorText(error), true); }
  }
  function confirmManualPreview(intent, selectedItems) {
    const items = Array.isArray(selectedItems) ? selectedItems : [];
    const values = items.map(item => typeof item === 'string' ? {itemId: item} : item)
      .filter(item => item && item.itemId);
    if (!values.length || values.length > 100) {
      message('Select between 1 and 100 current intent items before requesting Preview.', true);
      return;
    }
    const expectedItemVersions = {};
    values.forEach(item => {
      if (item.version !== undefined) expectedItemVersions[item.itemId] = item.version;
    });
    const confirmation = text('div', '', 'choices');
    confirmation.append(text('p',
      'Request a zero-mutation Preview for ' + values.length + ' item(s) at intent version ' +
      intent.version + '? The pinned snapshot and exact FileIndex source identities will be ' +
      'checked. No file is renamed, moved, copied, deleted or overwritten.', 'warning'));
    confirmation.append(actionButton('Confirm Preview', async () => {
      try {
        const body = {expectedVersion: intent.version,
          itemIds: values.map(item => item.itemId),
          expectedItemVersions: expectedItemVersions,
          snapshotId: intent.configurationSnapshotId,
          snapshotDigest: intent.configurationSnapshotDigest};
        const preview = await api('/api/v1/manual-intents/' + encodeURIComponent(intent.intentId) + '/preview', {
          method: 'POST', body: JSON.stringify(body)
        });
        await showManualPreview(preview.previewId);
        message('Preview persisted. No Storage mutation or execution authority was created.');
      } catch (error) { message(errorText(error), true); }
    }), actionButton('Keep intent unchanged', () => confirmation.remove()));
    detailContent.append(confirmation);
    detail.hidden = false;
  }
  function previewReviewPath(value) {
    if (!value || typeof value !== 'object') return null;
    const id = value.reviewId || value.confirmationId;
    const kind = {
      recognition: 'recognition-reviews', metadata: 'metadata-reviews',
      metadata_correction: 'metadata-corrections', classification: 'classification-reviews',
      conflict: 'confirmations'
    }[value.kind];
    return id && kind ? `/api/v1/${kind}/${encodeURIComponent(id)}` : null;
  }
  function renderManualExecutionDiscovery(discovery) {
    if (!discovery || typeof discovery !== 'object') return;
    const authorizations = Array.isArray(discovery.authorizations) ? discovery.authorizations : [];
    const executions = Array.isArray(discovery.executions) ? discovery.executions : [];
    if (!authorizations.length && !executions.length && !discovery.truncated) return;
    detailContent.append(text('h3', 'Durable manual execution state'));
    if (authorizations.length) {
      detailContent.append(text('h4', 'Authorizations'));
      authorizations.forEach(authority => {
        const section = text('div', '', 'choices');
        section.append(text('p', `${authority.authorizationId} - ${authority.status} ` +
          `(scope: ${(authority.scopeItemIds || []).join(', ') || 'none'})`));
        if (authority.executionId) section.append(text('p', `Execution: ${authority.executionId}`));
        const controls = text('div', '', 'choices');
        controls.append(actionButton('Open authorization', () =>
          showManualAuthorization(authority.authorizationId)));
        if (authority.executionId) controls.append(actionButton('Open durable execution', () =>
          showManualExecution(authority.executionId)));
        section.append(controls); detailContent.append(section);
      });
    }
    if (executions.length) {
      detailContent.append(text('h4', 'Executions'));
      executions.forEach(execution => {
        const section = text('div', '', 'choices');
        section.append(text('p', `${execution.executionId} - ${execution.status}; ` +
          `selected: ${(execution.selectedItemIds || []).length}; ` +
          `unselected: ${(execution.unselectedItemIds || []).length}`));
        const controls = text('div', '', 'choices');
        controls.append(actionButton('Open durable execution', () =>
          showManualExecution(execution.executionId)));
        if (execution.taskId) controls.append(actionButton('Open Task', () =>
          showTask(execution.taskId)));
        section.append(controls); detailContent.append(section);
      });
    }
    if (discovery.truncated) detailContent.append(text('p',
      'Manual execution history is bounded; reload from the linked Intent or Preview to inspect the current page.',
      'warning'));
    if (discovery.nextAction) detailContent.append(text('p', discovery.nextAction, 'warning'));
  }
  async function showManualPreview(previewId) {
    try {
      const data = await api('/api/v1/manual-previews/' + encodeURIComponent(previewId));
      clear(detailContent); detailContent.append(text('h2', 'Manual-organize Preview'));
      const summary = document.createElement('dl');
      field(summary, 'Preview', data.previewId);
      field(summary, 'Intent', data.intentId);
      field(summary, 'Status', data.status);
      field(summary, 'Current', data.current ? 'YES' : 'NO - historical/stale evidence');
      field(summary, 'Intent version', data.intentVersion);
      field(summary, 'Pinned snapshot', data.configurationSnapshotId);
      field(summary, 'Pinned digest', data.configurationSnapshotDigest);
      const scope = data.scope || {};
      field(summary, 'Preview scope', scope.kind ?
        `${scope.kind}:${scope.id} (${scope.itemCount || 0} item(s))` : 'intent selection');
      field(summary, 'Storage mutation', data.zeroMutation ? 'NONE' : 'INVALID');
      field(summary, 'Execution state', data.executionState || 'not available in this Task');
      field(summary, 'Next action', data.nextAction || '-');
      detailContent.append(summary);
      const items = Array.isArray(data.items) ? data.items : [];
      items.forEach(item => {
        const source = item.source || {}; const plan = item.plan || {};
        const destination = plan.destination || {};
        const capabilities = plan.capabilities || {};
        const policies = plan.policies || {};
        const identity = plan.mediaIdentity || {};
        const analysis = plan.analysis || {};
        const section = text('div', '', 'choices');
        section.append(text('h3', item.itemId + ' - ' + item.status + ' (' +
          (item.stage || 'analysis') + ')'));
        section.append(text('p', (source.storageId || '-') + ' / ' + (source.path || '-')));
        section.append(text('p',
          'Current occurrence: ' + (source.occurrenceId || '-') +
          '; fingerprint: ' + (source.fingerprint || '-') +
          '; state: ' + (source.occurrenceState || 'unverified')));
        section.append(text('p',
          'Media identity: ' + (identity.title || '-') +
          (identity.year ? ' (' + identity.year + ')' : '') +
          '; Provider: ' + (identity.provider || '-') + '/' + (identity.providerId || '-') +
          '; Plan fingerprint: ' + (item.planFingerprint || '-')));
        section.append(text('p',
          'RecognitionType: ' + (plan.recognitionType ||
            item.choice && item.choice.recognitionTypeId || '-') +
          '; NamingPolicy: ' + (policies.namingPolicyId || '-') +
          '; ClassificationPolicy: ' + (policies.classificationPolicyId || '-') +
          '; OrganizePolicy: ' + (policies.organizePolicyId || '-')));
        section.append(text('p',
          'Target: ' + (destination.storageId || '-') + ' / ' + (destination.path || '-') +
          '; Operation: ' + (plan.operation || '-') +
          '; Required capabilities: ' + ((capabilities.required || []).join(', ') || 'none') +
          '; Missing: ' + ((capabilities.missing || []).join(', ') || 'none')));
        const recognitionReasons = analysis.recognition && analysis.recognition.reasons || [];
        section.append(text('p',
          'Attachments: ' + (Array.isArray(plan.attachments) ? plan.attachments.length : 0) +
          '; Recognition explanation: ' +
          (recognitionReasons.map(value => value.message || value.code || value).join('; ') || '-')));
        section.append(text('p',
          'Zero mutation: ' + (item.zeroMutation ? 'YES' : 'INVALID') +
          '; Execution: ' + (item.executionState || 'not available in this Task')));
        if (item.error) section.append(text('p', 'Blocker/failure: ' + item.error, 'error'));
        if (item.nextAction) section.append(text('p', 'Recovery: ' + item.nextAction, 'warning'));
        if (Array.isArray(plan.conflicts) && plan.conflicts.length) {
          section.append(text('p',
            'Conflicts: ' + plan.conflicts.map(value => value.type || value).join(', '), 'error'));
          section.append(actionButton('Open conflict resolution queue',
            () => renderQueue('confirmations')));
        }
        if (Array.isArray(plan.warnings) && plan.warnings.length) {
          section.append(text('p', 'Warnings: ' + plan.warnings.join('; '), 'warning'));
        }
        const linked = text('div', '', 'choices');
        [...(item.reviewVersions || []), ...(item.conflictVersions || [])].forEach(value => {
          const path = previewReviewPath(value);
          if (path) linked.append(actionButton('Open linked ' + value.kind, () => showCheckpointBlocker(path)));
        });
        if (linked.childNodes.length) {
          section.append(text('small', 'Linked review/conflict resolution:'), linked);
        }
        if (item.status === 'stale' || data.status === 'stale' || data.current === false) {
          section.append(actionButton('Request fresh Preview',
            () => showManualIntent(data.intentId)));
        }
        if (item.status === 'previewed' && item.current && plan.executionPlan) {
          section.append(actionButton('Authorize this exact item',
            () => confirmManualAuthorization(data, [item])));
        }
        detailContent.append(section);
      });
      const unselected = data.selection && Array.isArray(data.selection.unselectedItemIds) ?
        data.selection.unselectedItemIds : [];
      if (unselected.length) {
        detailContent.append(text('h3', 'Intent items not included in this Preview'), table(
          ['Item', 'State'], unselected.map(itemId => [itemId, 'unselected - no Preview analysis'])));
        detailContent.append(text('p',
          'These intent items remain independently visible and were not analyzed or authorized by this Preview.',
          'warning'));
      }
      const selectedIds = data.selection && Array.isArray(data.selection.selectedItemIds) ?
        new Set(data.selection.selectedItemIds) : new Set();
      const executable = items.filter(item => item.status === 'previewed' && item.current &&
        item.plan && item.plan.executionPlan && (!selectedIds.size || selectedIds.has(item.itemId)));
      if (executable.length) {
        detailContent.append(actionButton(`Authorize ${executable.length} exact item(s)`,
          () => confirmManualAuthorization(data, executable)));
      }
      renderManualExecutionDiscovery(data.manualExecutionDiscovery);
      detailContent.append(actionButton('Reload Preview', () => showManualPreview(data.previewId)),
        actionButton('Open manual intent', () => showManualIntent(data.intentId)));
      detail.hidden = false;
    } catch (error) { message(errorText(error), true); }
  }
  function confirmManualAuthorization(preview, selectedItems) {
    const values = (Array.isArray(selectedItems) ? selectedItems : [])
      .filter(item => item && item.itemId && item.plan && item.plan.executionPlan &&
        item.status === 'previewed' && item.current);
    if (!values.length || values.length > 100) {
      message('Select between 1 and 100 current Preview items with complete plans.', true);
      return;
    }
    const needsOverwrite = values.some(item =>
      item.plan.executionPlan.overwriteAuthorized === true);
    const needsCleanup = values.some(item => {
      const cleanup = item.plan.executionPlan.sourceDirectoryCleanup || {};
      return cleanup.mode && cleanup.mode !== 'none';
    });
    const controls = text('div', '', 'choices');
    const overwrite = document.createElement('input'); overwrite.type = 'checkbox';
    overwrite.checked = false; overwrite.disabled = !needsOverwrite;
    overwrite.setAttribute('aria-label', 'Authorize reviewed overwrite');
    const overwriteLabel = text('label', 'Authorize the reviewed overwrite operation');
    overwriteLabel.append(overwrite); controls.append(overwriteLabel);
    const cleanup = document.createElement('input'); cleanup.type = 'checkbox';
    cleanup.checked = false; cleanup.disabled = !needsCleanup;
    cleanup.setAttribute('aria-label', 'Authorize reviewed source cleanup');
    const cleanupLabel = text('label', 'Authorize the reviewed source-directory cleanup');
    cleanupLabel.append(cleanup); controls.append(cleanupLabel);
    const confirmation = text('div', '', 'choices');
    confirmation.append(text('p',
      `Create one one-shot authorization for ${values.length} exact Preview item(s)? ` +
      'The pinned snapshot, source identities, choices, plan fingerprints and destinations will be checked again. ' +
      'This action does not mutate Storage.', 'warning'), controls);
    confirmation.append(actionButton('Create exact execution authorization', async () => {
      if ((needsOverwrite && !overwrite.checked) || (needsCleanup && !cleanup.checked)) {
        message('Explicitly authorize each destructive operation shown above.', true);
        return;
      }
      try {
        const expectedItemVersions = {};
        values.forEach(item => { expectedItemVersions[item.itemId] = item.itemVersion; });
        const authority = await api(`/api/v1/manual-previews/${encodeURIComponent(preview.previewId)}/authorize`, {
          method: 'POST', body: JSON.stringify({
            expectedVersion: preview.intentVersion,
            expectedItemVersions,
            itemIds: values.map(item => item.itemId),
            snapshotId: preview.configurationSnapshotId,
            snapshotDigest: preview.configurationSnapshotDigest,
            confirmation: true,
            allowOverwrite: overwrite.checked,
            allowSourceCleanup: cleanup.checked
          })
        });
        await showManualAuthorization(authority);
        message('One-shot authorization persisted. Storage was not changed; execute it explicitly below.');
      } catch (error) { message(errorText(error), true); }
    }), actionButton('Keep Preview unchanged', () => confirmation.remove()));
    detailContent.append(confirmation); detail.hidden = false;
  }
  async function showManualAuthorization(authority) {
    const data = authority && authority.authorizationId ? authority :
      await api(`/api/v1/manual-execution-authorizations/${encodeURIComponent(authority)}`);
    clear(detailContent); detailContent.append(text('h2', 'Exact execution authorization'));
    const summary = document.createElement('dl');
    field(summary, 'Authorization', data.authorizationId);
    field(summary, 'Preview', data.previewId);
    field(summary, 'Actor', data.actor);
    field(summary, 'Status', data.status);
    field(summary, 'Pinned snapshot', data.configurationSnapshotId);
    field(summary, 'Expires', data.expiresAt);
    field(summary, 'Scope', data.scope && data.scope.length);
    field(summary, 'Storage mutation', 'NONE until explicit Execute');
    field(summary, 'Next action', data.nextAction || '-');
    detailContent.append(summary);
    if (data.destructiveAuthority) detailContent.append(text('p',
      'Destructive authority: overwrite=' + (data.destructiveAuthority.allowOverwrite ? 'YES' : 'NO') +
      ', source cleanup=' + (data.destructiveAuthority.allowSourceCleanup ? 'YES' : 'NO'), 'warning'));
    if (data.audit && data.audit.length) detailContent.append(text('h3', 'Authorization audit'), table(
      ['Action', 'Actor', 'Time', 'Execution'],
      data.audit.map(item => [item.action, item.actor || '-', item.occurredAt, item.executionId || '-'])));
    if (data.status === 'active') detailContent.append(actionButton('Execute this exact authorization',
      () => confirmManualExecution(data)));
    if (data.executionId) detailContent.append(actionButton('Open durable execution',
      () => showManualExecution(data.executionId)));
    detailContent.append(actionButton('Reload authorization',
      () => showManualAuthorization(data.authorizationId)),
      actionButton('Open Preview', () => showManualPreview(data.previewId)));
    detail.hidden = false;
  }
  function confirmManualExecution(authority) {
    const confirmation = text('div', '', 'choices');
    confirmation.append(text('p',
      `Execute authorization ${authority.authorizationId} exactly once? ` +
      'The current source, destination, capability and conflict state will be revalidated. ' +
      'Results and effects will be saved per item; uncertain mutation will not be replayed.', 'warning'));
    confirmation.append(actionButton('Confirm exact execution', async () => {
      try {
        const execution = await api(`/api/v1/manual-execution-authorizations/${encodeURIComponent(authority.authorizationId)}/execute`, {
          method: 'POST', body: JSON.stringify({confirmation: true})
        });
        await showManualExecution(execution.executionId);
        message('Exact execution completed or recorded per item. Review each Result and checkpoint.');
      } catch (error) { message(errorText(error), true); }
    }), actionButton('Do not execute', () => confirmation.remove()));
    detailContent.append(confirmation);
  }
  async function showManualExecution(executionId) {
    try {
      const data = await api(`/api/v1/manual-executions/${encodeURIComponent(executionId)}`);
      clear(detailContent); detailContent.append(text('h2', 'Manual execution result'));
      const summary = document.createElement('dl');
      field(summary, 'Execution', data.executionId);
      field(summary, 'Task', data.taskId);
      field(summary, 'Status', data.status);
      field(summary, 'Selection', data.selection && data.selection.selectedItemIds &&
        data.selection.selectedItemIds.length);
      field(summary, 'Next action', data.nextAction || '-');
      detailContent.append(summary);
      const items = Array.isArray(data.items) ? data.items : [];
      const interrupted = ['admitted', 'running'].includes(data.status) || items.some(item =>
        ['admitted', 'running'].includes(item.status));
      if (interrupted) {
        detailContent.append(text('p',
          'This exact execution has no durable terminal outcome. Reconciliation records the ' +
          'safe state, releases its execution fence, and never replays Storage mutation.', 'warning'),
          actionButton('Reconcile interrupted execution',
            () => confirmManualReconciliation(data)));
      }
      items.forEach(item => {
        const section = text('div', '', 'choices');
        section.append(text('h3', `${item.itemId} - ${item.status}`));
        section.append(text('p', `Stage: ${item.stage}; Result: ${item.resultId || '-'}; ` +
          `Effect certainty: ${item.effectCertainty || 'unknown'}`));
        section.append(text('p', `Completed operations: ${(item.completedOperations || []).join(', ') || 'none'}`));
        if (item.error) section.append(text('p', `Failure: ${item.error}`, 'error'));
        if (item.nextAction) section.append(text('p', `Recovery: ${item.nextAction}`, 'warning'));
        const effects = Array.isArray(item.effects) ? item.effects : [];
        if (effects.length) section.append(text('h4', 'Operation effects'), table(
          ['Action', 'Source', 'Destination', 'Verified', 'Certainty'],
          effects.map(effect => [effect.action,
            `${effect.sourceStorageId || '-'} / ${effect.sourcePath || '-'}`,
            `${effect.destinationStorageId || '-'} / ${effect.destinationPath || '-'}`,
            effect.verified ? 'YES' : 'NO', effect.certainty || '-'])));
        if (item.checkpoint) {
          section.append(text('p', `Checkpoint: ${item.checkpoint.status}; ` +
            `stage: ${item.checkpoint.stage || '-'}; ` +
            `retry safety: ${item.checkpoint.retry_safety || '-'}; ` +
            `permitted actions: ${(item.checkpoint.permitted_action_ids || []).join(', ') || 'none'}`));
          const blockers = Array.isArray(item.checkpoint.blockers) && item.checkpoint.blockers.length ?
            item.checkpoint.blockers :
            (item.checkpoint.blocker ? [item.checkpoint.blocker] : []);
          if (blockers.length) {
            section.append(text('h4', 'Review / conflict blockers'));
            blockers.forEach(blocker => {
              const blockerControls = text('div', '', 'choices');
              blockerControls.append(text('p',
                `${blocker.kind}: ${blocker.blocker_id || blocker.id} (${blocker.status})`));
              if (blocker.resolution_path) {
                blockerControls.append(actionButton('Open blocker resolution',
                  () => showCheckpointBlocker(blocker.resolution_path)));
              }
              section.append(blockerControls);
            });
          }
        }
        section.append(actionButton('Open Processing Checkpoint',
          () => showTaskItem(data.taskId, item.taskItemId)));
        detailContent.append(section);
      });
      const unselected = data.selection && Array.isArray(data.selection.unselectedItemIds) ?
        data.selection.unselectedItemIds : [];
      if (unselected.length) {
        detailContent.append(text('h3', 'Intent/Preview items not executed'), table(
          ['Item', 'State'], unselected.map(itemId => [itemId, 'unselected - untouched'])));
        detailContent.append(text('p',
          'Unselected items have no TaskItem, Result, execution effect or Storage mutation in this execution.',
          'warning'));
      }
      detailContent.append(actionButton('Reload execution', () => showManualExecution(data.executionId)),
        actionButton('Open Task', () => showTask(data.taskId)));
      detail.hidden = false;
    } catch (error) { message(errorText(error), true); }
  }
  function confirmManualReconciliation(execution) {
    const confirmation = text('div', '', 'choices');
    confirmation.append(text('p',
      `Reconcile interrupted execution ${execution.executionId}? ` +
      'This publishes investigation evidence and releases the durable fence. It does not invoke ' +
      'OrganizerExecutor or replay any mutation.', 'warning'));
    confirmation.append(actionButton('Confirm reconciliation', async () => {
      try {
        const result = await api(`/api/v1/manual-executions/${encodeURIComponent(execution.executionId)}/reconcile`, {
          method: 'POST', body: JSON.stringify({confirmation: true})
        });
        await showManualExecution(result.executionId);
        message('Interrupted execution reconciled. Review each Result and checkpoint; no mutation was replayed.');
      } catch (error) { message(errorText(error), true); }
    }), actionButton('Keep execution unchanged', () => confirmation.remove()));
    detailContent.append(confirmation);
  }
  function confirmManualChoice(intent, item, patch) {
    const confirmation = text('div', '', 'choices');
    confirmation.append(text('p', `Save the normalized choice for ${item.itemId}? ` +
      'The intent version is checked and the pinned snapshot cannot be changed.', 'warning'),
      actionButton('Confirm save choice', async () => {
        try {
          await api(`/api/v1/manual-intents/${encodeURIComponent(intent.intentId)}/items/${encodeURIComponent(item.itemId)}/choice`, {
            method: 'PUT', body: JSON.stringify({expectedVersion: intent.version,
              expectedItemVersion: item.version, ...patch})
          });
          await showManualIntent(intent.intentId); message('Choice saved and audited.');
        } catch (error) { message(errorText(error), true); }
      }), actionButton('Keep prior choice', () => confirmation.remove()));
    detailContent.append(confirmation);
  }
  function confirmCancelManualIntent(intent) {
    const confirmation = text('div', '', 'choices');
    confirmation.append(text('p', 'Cancel this manual intent? Its durable choices remain auditable and no media is changed.'),
      actionButton('Confirm cancel intent', async () => {
        try {
          await api(`/api/v1/manual-intents/${encodeURIComponent(intent.intentId)}/cancel`, {
            method: 'POST', body: JSON.stringify({expectedVersion: intent.version})
          });
          await showManualIntent(intent.intentId); message('Manual intent cancelled.');
        } catch (error) { message(errorText(error), true); }
      }), actionButton('Keep intent open', () => confirmation.remove()));
    detailContent.append(confirmation);
  }
  async function renderObservability(kind, cursor = null) {
    const suffix = cursor ? `&cursor=${encodeURIComponent(cursor)}` : '';
    const data = await api(`/api/v1/${kind}?limit=100${suffix}`); const items = data.items || [];
    clear(content); content.append(text('h2', kind === 'tasks' ? 'Tasks' : 'Automation jobs'));
    if (kind === 'jobs') {
      content.append(actionButton('Queue DryRun job', showDryRunJobForm));
      content.append(actionButton('Show stale running jobs', renderStaleJobs));
    }
    if (kind === 'tasks') {
      const rows = items.map(item => [item.task_id, item.command, item.status,
        item.execute_authorized ? 'MUTATION_AUTHORIZED' : 'DRY_RUN', item.completed_items,
        item.failed_items, item.updated_at]);
      content.append(table(['ID', 'Command', 'Status', 'Authority', 'Done', 'Failed', 'Updated'], rows,
        index => showTask(items[index].task_id)));
      pageNavigation(content, 'tasks', data.previous_cursor, data.next_cursor,
        () => renderObservability(kind, data.previous_cursor),
        () => renderObservability(kind, data.next_cursor));
    } else {
      const rows = items.map(item => [item.job_id, item.command, item.status,
        item.execute_authorized ? 'MUTATION_AUTHORIZED' : 'DRY_RUN', item.task_id || '-',
        item.updated_at]);
      content.append(table(['ID', 'Command', 'Status', 'Authority', 'Task', 'Updated'], rows,
        index => showJob(items[index].job_id)));
      pageNavigation(content, 'jobs', data.previous_cursor, data.next_cursor,
        () => renderObservability(kind, data.previous_cursor),
        () => renderObservability(kind, data.next_cursor));
    }
  }
  async function renderStaleJobs() {
    const data = await api('/api/v1/jobs/stale?limit=100'); const items = data.items || [];
    clear(content); content.append(text('h2', 'Stale running automation jobs'));
    content.append(text('p', `Running jobs not updated for ${data.threshold_seconds} seconds. ` +
      'Age is an observation, not proof that a worker died. Inspect locally before recovery; ' +
      'automatic requeue is intentionally unavailable.', 'warning'));
    const rows = items.map(item => [item.job_id, item.command, item.status,
      item.execute_authorized ? 'MUTATION_AUTHORIZED \\u2014 MANUAL RECOVERY ONLY' : 'DRY_RUN',
      item.task_id || '-', item.ownerStatus || '-',
      (item.operationalCondition && item.operationalCondition.nextAction) || '-',
      item.updated_at]);
    content.append(table(['ID', 'Command', 'Status', 'Authority', 'Task', 'Owner', 'Next action', 'Updated'], rows,
      index => showJob(items[index].job_id)));
    content.append(actionButton('Back to automation jobs', () => renderObservability('jobs')));
  }
  function showDryRunJobForm() {
    clear(detailContent); detailContent.append(text('h2', 'Queue DryRun automation job'));
    const command = document.createElement('select'); command.setAttribute('aria-label', 'DryRun command');
    ['scan', 'preview'].forEach(value => { const option = text('option', value); option.value = value;
      command.append(option); });
    const limit = document.createElement('input'); limit.type = 'number'; limit.min = '1';
    limit.max = '10000'; limit.step = '1'; limit.placeholder = 'Optional limit';
    limit.setAttribute('aria-label', 'Optional item limit');
    const controls = text('div', '', 'choices'); controls.append(command, limit,
      actionButton('Review DryRun job', () => {
        if (limit.value && !limit.reportValidity()) return;
        reviewDryRunJob(command.value, limit.value ? Number(limit.value) : null);
      }), actionButton('Keep jobs unchanged', () => { detail.hidden = true; }));
    detailContent.append(text('p', 'This queues scan or preview only. It grants no execution authority.'),
      controls); detail.hidden = false;
  }
  function reviewDryRunJob(command, limit) {
    const payload = Object.freeze(limit === null ? {command} : {command, limit});
    clear(detailContent); detailContent.append(text('h2', 'Review DryRun job'), cards([
      ['Command', payload.command], ['Limit', payload.limit || 'No explicit limit'],
      ['Authority', 'DRY_RUN'], ['Storage mutation', 'NONE']
    ]), text('p', 'A Worker may read configured Storage and metadata providers. No organization is executed.',
      'warning'), actionButton('Confirm queueing', () => submitDryRunJob(payload)),
      actionButton('Back without queueing', showDryRunJobForm)); detail.hidden = false;
  }
  async function submitDryRunJob(payload) {
    try {
      const created = await api('/api/v1/jobs', {method: 'POST', body: JSON.stringify(payload)});
      await renderObservability('jobs'); await showJob(created.job_id); message('DryRun job queued.');
          } catch (error) { message(errorText(error), true); }
  }
  async function renderSchedules() {
    const data = await api('/api/v1/schedules'); const items = data.items || [];
    clear(content); content.append(text('h2', 'Schedules'));
    const rows = items.map(item => [item.schedule_id, item.command,
      item.expression || `${item.interval_seconds}s`, item.timezone || '-',
      item.enabled, item.state && item.state.next_run_at || '-',
      item.state && item.state.last_job_id || '-']);
    content.append(table(['ID', 'Command', 'Timing', 'Timezone', 'Enabled', 'Next run', 'Last job'],
      rows, index => showScheduleAudit(items[index].schedule_id)));
  }
  async function showScheduleAudit(id, cursor = null) {
    try {
      const suffix = cursor ? `&cursor=${encodeURIComponent(cursor)}` : '';
      const data = await api(`/api/v1/schedules/${encodeURIComponent(id)}/audit?limit=100${suffix}`);
      clear(detailContent); detailContent.append(text('h2', 'Schedule occurrence audit'));
      const rows = (data.items || []).map(item => [item.audit_id, item.occurrence_at,
        item.emitted_at, item.command, item.job_id, item.next_run_at]);
      detailContent.append(table(['Audit ID', 'Occurrence', 'Emitted', 'Command', 'Job', 'Next run'],
        rows));
      pageNavigation(detailContent, 'schedule records', data.previous_cursor, data.next_cursor,
        () => showScheduleAudit(id, data.previous_cursor),
        () => showScheduleAudit(id, data.next_cursor));
      detail.hidden = false;
        } catch (error) { message(errorText(error), true); }
  }
  async function renderAutomation() {
    const data = await api('/api/v1/automation/task-definitions');
    const configuration = data.configuration || {};
    const items = data.items || [];
    clear(content); content.append(text('h2', 'Automation Task Definitions'));
    content.append(text('p', 'Managed definitions are edited inside a Draft and become effective only after Validate and explicit Activate.', 'warning'));
    content.append(cards([
      ['Active configuration', configuration.revisionId || 'none'],
      ['Configuration version', configuration.version || '-'],
      ['Configuration digest', configuration.digest || '-'],
      ['Definitions', data.total || 0]
    ]));
    content.append(actionButton('Open managed Configuration', renderConfiguration));
    const rows = items.map(item => [item.id, item.name, item.enabled === true ? 'enabled' : 'disabled',
      item.resourceLibraryId, item.sourceScope || '<root>', item.mode || item.runMode || '-',
      item.intervalSeconds !== undefined ? `${item.intervalSeconds}s` : `${item.cron || '-'} (${item.timezone || '-'})`,
      item.itemLimit || item.limit || '-', item.nextRunAt || '-', item.lastOutcome || '-']);
    content.append(table(['ID', 'Name', 'State', 'ResourceLibrary', 'Scope', 'Mode', 'Schedule', 'Limit', 'Next run', 'Last outcome'], rows,
      index => showAutomationDetail(items[index], configuration)));
  }
  async function showAutomationDetail(item, configuration) {
    try {
      clear(detailContent); detailContent.append(text('h2', 'Automation Task Definition detail'));
      const occurrenceState = item.occurrenceState || item.occurrence || {};
      const list = document.createElement('dl');
      [['ID', item.id], ['Name', item.name], ['State', item.enabled === true ? 'enabled' : 'disabled'],
        ['ResourceLibrary', item.resourceLibraryId], ['Source scope', item.sourceScope || '<root>'],
        ['Run mode', item.mode || item.runMode], ['Interval seconds', item.intervalSeconds],
        ['Cron', item.cron], ['Timezone', item.timezone], ['Item limit', item.itemLimit || item.limit],
        ['Definition fingerprint', item.definitionFingerprint || '-'],
        ['Active configuration', (item.activeConfiguration || configuration).revisionId || '-'],
        ['Active configuration version', (item.activeConfiguration || configuration).version || '-'],
        ['Active configuration sequence', (item.activeConfiguration || configuration).revisionSequence || '-'],
        ['Active configuration digest', (item.activeConfiguration || configuration).digest || '-'],
        ['Next run', occurrenceState.nextRunAt || '-'],
        ['Last occurrence', occurrenceState.lastOccurrenceAt || '-'],
        ['Last Job', occurrenceState.lastJobId || '-'],
        ['Last Task', occurrenceState.lastTaskId || '-'],
        ['Last outcome', occurrenceState.lastOutcome || '-'],
        ['Failure category', occurrenceState.lastFailureCategory || '-'],
        ['Failure reason', occurrenceState.lastReason || '-'],
        ['Next action', occurrenceState.nextAction || '-']].forEach(([label, value]) => field(list, label, value));
      const grantState = await api(`/api/v1/automation/task-definitions/${encodeURIComponent(item.id)}/grant-state`);
      const grant = grantState.grant || grantState.unattendedExecutionGrant ||
        {status: 'none', active: false};
      const grantEligibility = grantState.grantEligibility || grantState.previewEligibility ||
        {eligible: false, nextAction: 'reload the current grant eligibility projection'};
      const previewData = await api(`/api/v1/automation/task-definitions/${encodeURIComponent(item.id)}/previews?limit=1`);
      const latestPreview = (previewData.items || [])[0] || null;
      [['Unattended grant', grant.status || 'none'],
        ['Grant exact scope', grant.sourceScope || '<root>'],
        ['Grant allowed run mode', grant.allowedRunMode || grant.runMode || '-'],
        ['Grant workload bound', grant.maxItemsPerRun || '-'],
        ['Granting principal', grant.grantingPrincipal || '-'],
        ['Granted at', grant.grantedAt || '-'],
        ['Revoked at', grant.revokedAt || '-'],
        ['Definition changed since grant', grant.definitionChangedSinceGrant === true ? 'YES' : 'NO'],
        ['Grant next action', grant.nextAction || '-'],
        ['Exact Preview linked to grant', grant.previewId || '-'],
        ['Latest Preview', latestPreview && latestPreview.previewId || '-'],
        ['Grant eligibility', grantEligibility.eligible === true ? 'eligible' : 'ineligible'],
        ['Eligibility explanation', grantEligibility.explanation ||
          (grantEligibility.error && grantEligibility.error.message) || '-'],
        ['Eligibility next action', grantEligibility.nextAction || '-'],
        ['Current permission', grant.currentPermission && grant.currentPermission.status || 'not granted']].forEach(([label, value]) => field(list, label, value));
      detailContent.append(list);
      if (occurrenceState.lastTaskId) {
        detailContent.append(actionButton('Open last Task', () => showTask(occurrenceState.lastTaskId)));
      }
      detailContent.append(actionButton('Run Preview / DryRun', () => confirmAutomationPreview(item)));
      if ((item.mode || item.runMode) === 'automatic-organization') {
        if (grant.active === true || grant.status === 'active') {
          detailContent.append(actionButton('Revoke unattended execution', () =>
            confirmAutomationGrantRevoke(item, grant, configuration)));
        } else if (grantEligibility.eligible === true) {
          detailContent.append(actionButton('Grant unattended execution', () =>
            confirmAutomationGrant(item, configuration, grantEligibility.previewId)));
        } else {
          detailContent.append(text('p', grantEligibility.nextAction ||
            'Unattended grant is unavailable until the shared eligibility projection permits it.', 'warning'));
        }
      }
      detailContent.append(actionButton('Open managed Configuration', () => renderConfiguration()));
      const occurrenceData = await api(`/api/v1/automation/task-definitions/${encodeURIComponent(item.id)}/occurrences?limit=10`);
      detailContent.append(text('h3', 'Scheduled occurrences'));
      const latestOccurrence = (occurrenceData.items || [])[0] || null;
      const outcomeSummary = latestOccurrence &&
        (latestOccurrence.outcomeSummary || latestOccurrence.itemOutcomeSummary) ||
        item.outcomeSummary || item.itemOutcomeSummary || null;
      detailContent.append(text('h3', 'Per-item outcome summary'));
      if (outcomeSummary && typeof outcomeSummary === 'object') {
        const counts = outcomeSummary.statusCounts || outcomeSummary.counts || {};
        detailContent.append(cards(Object.entries(counts).map(([key, value]) => [key, value])));
        const bound = outcomeSummary.bound && typeof outcomeSummary.bound === 'object' ?
          outcomeSummary.bound : {};
        detailContent.append(text('p', bound.statement ||
          'Bound state was not published for this occurrence.', 'warning'));
        const attention = Array.isArray(outcomeSummary.attention) ? outcomeSummary.attention : [];
        detailContent.append(text('h4', `Items needing attention (${attention.length}; display limit ${outcomeSummary.attentionLimit || 32})`));
        if (attention.length) {
          detailContent.append(table(
            ['Task item', 'Status', 'Stage', 'Blocker', 'Effect certainty', 'Retry safety', 'Failure category', 'Next action'],
            attention.map(value => [value.itemId, value.status, value.stage || '-',
              value.blockerKind ? `${value.blockerKind}:${value.blockerId || '-'}` : '-',
              value.effectCertainty || 'unknown', value.retrySafety || 'unknown',
              value.failureExplanation && value.failureExplanation.category || '-', value.nextAction || '-']),
            index => showTaskItem(attention[index].taskId, attention[index].itemId)));
        } else {
          detailContent.append(text('p', 'No item currently needs an operator decision.'));
        }
        if (outcomeSummary.moreAttention === true || outcomeSummary.attentionTruncated === true) {
          detailContent.append(text('p',
            `The attention list is capped at ${outcomeSummary.attentionLimit || 32}; more items need review in the linked Task.`,
            'warning'));
        }
      } else {
        detailContent.append(text('p', 'No per-item outcome summary has been published yet.', 'warning'));
      }
      const occurrenceRows = (occurrenceData.items || []).map(value => [value.occurrenceId,
        value.occurrenceAt, value.emittedAt, value.jobId, value.taskId || '-', value.configurationRevisionId,
        value.configurationRevisionVersion, value.configurationRevisionDigest,
        value.runMode, value.outcome, value.failureCategory || '-', value.reason || '-', value.nextAction || '-']);
      detailContent.append(table(['Occurrence', 'Due', 'Emitted', 'Job', 'Task', 'Configuration', 'Version', 'Digest', 'Run mode', 'Outcome', 'Failure category', 'Reason', 'Next action'], occurrenceRows,
        index => {
          const taskId = (occurrenceData.items || [])[index].taskId;
          if (taskId) showTask(taskId);
        }));
      if (!(occurrenceData.items || []).length) {
        detailContent.append(text('p', 'No scheduled occurrence has been emitted for this definition yet.'));
      }
      detailContent.append(text('h3', 'Previews'));
      const data = await api(`/api/v1/automation/task-definitions/${encodeURIComponent(item.id)}/previews?limit=10`);
      const rows = (data.items || []).map(value => [value.previewId, value.status,
        value.configurationRevisionId, value.createdAt,
        value.current === true ? 'current' : 'stale', value.nextAction || '-']);
      detailContent.append(table(['Preview', 'Status', 'Configuration', 'Created', 'State', 'Next action'],
        rows, index => showAutomationPreview(item.id, (data.items || [])[index].previewId)));
      if (!(data.items || []).length) {
        detailContent.append(text('p', 'No Preview has been run for this definition yet.'));
      }
      detailContent.append(text('p', 'Opening or refreshing this view is read-only. Preview runs only when you explicitly confirm it.', 'warning'));
      detail.hidden = false;
    } catch (error) { message(errorText(error), true); }
  }
  function confirmAutomationGrant(item, configuration, previewId) {
    const scope = item.sourceScope || '<root>';
    const mode = item.mode || item.runMode || '-';
    const limit = item.itemLimit || item.limit || '-';
    const confirmation = text('div', '', 'choices');
    confirmation.append(text('p', `Grant persistent unattended execution for ${item.id}? ` +
      `This explicitly authorizes only ${mode} over ResourceLibrary ${item.resourceLibraryId}, ` +
      `scope ${scope}, with at most ${limit} item(s) per run. Exact Preview ${previewId || '-'}. It does not authorize overwrite, ` +
      'delete, fallback operations, or any path outside that scope.'));
    confirmation.append(actionButton('Confirm unattended grant', async () => {
      try {
        const result = await api(`/api/v1/automation/task-definitions/${encodeURIComponent(item.id)}/grant`,
          {method: 'POST', body: JSON.stringify({
            revisionId: configuration.revisionId,
            expectedVersion: configuration.version,
            maxItemsPerRun: limit,
            confirmation: true,
            previewId: previewId
          })});
        message(`Unattended execution grant ${result.grant.grantId || '-'} is active.`);
        await showAutomationDetail({...item, unattendedExecutionGrant: result.grant}, configuration);
      } catch (error) { message(errorText(error), true); }
    }));
    confirmation.append(actionButton('Cancel', () => { clear(confirmation); }));
    detailContent.append(confirmation);
  }
  function confirmAutomationGrantRevoke(item, grant, configuration) {
    const confirmation = text('div', '', 'choices');
    confirmation.append(text('p', `Revoke unattended execution for ${item.id}? ` +
      'Future eligible mutations will stop at a safe item boundary; completed history is preserved.'));
    confirmation.append(actionButton('Confirm revoke', async () => {
      try {
        const result = await api(`/api/v1/automation/task-definitions/${encodeURIComponent(item.id)}/grant/revoke`,
          {method: 'POST', body: JSON.stringify({grantId: grant.grantId, reason: 'operator revoked unattended execution'})});
        message(`Unattended execution grant ${result.grant.grantId || '-'} is revoked.`);
        await showAutomationDetail({...item, unattendedExecutionGrant: result.unattendedExecutionGrant}, configuration);
      } catch (error) { message(errorText(error), true); }
    }));
    confirmation.append(actionButton('Cancel', () => { clear(confirmation); }));
    detailContent.append(confirmation);
  }
  function confirmAutomationPreview(item) {
    const confirmation = text('div', '', 'choices');
    confirmation.append(text('p', `Run an exact-definition, zero-mutation Preview for ${item.id}? It creates no Job, Task, grant, or configuration revision.`));
    confirmation.append(actionButton('Confirm Preview', async () => {
      try {
        const result = await api(`/api/v1/automation/task-definitions/${encodeURIComponent(item.id)}/preview`,
          {method: 'POST', body: JSON.stringify({})});
        message(`Preview ${result.previewId} completed with status ${result.status}. ${result.nextAction || ''}`);
        await showAutomationPreview(item.id, result.previewId);
      } catch (error) { message(errorText(error), true); }
    }));
    confirmation.append(actionButton('Cancel', () => { clear(confirmation); }));
    detailContent.append(confirmation);
  }
  async function showAutomationPreview(definitionId, previewId) {
    try {
      const data = await api(`/api/v1/automation/task-definitions/${encodeURIComponent(definitionId)}/previews/${encodeURIComponent(previewId)}`);
      clear(detailContent); detailContent.append(text('h2', 'Automation Preview'));
      if (data.current !== true || data.staleReason) {
        detailContent.append(text('p', `Stale evidence: ${data.staleReason || 'this Preview is no longer current'}. This is not execution authority.`, 'warning'));
      }
      const list = document.createElement('dl');
      [['Preview', data.previewId], ['Definition', data.definitionId], ['Status', data.status],
        ['Definition fingerprint', data.definitionFingerprint],
        ['Configuration revision', data.configurationRevisionId],
        ['Configuration version', data.configurationRevisionVersion],
        ['Configuration digest', data.configurationRevisionDigest],
        ['ResourceLibrary', data.resourceLibraryId], ['Storage', data.storageId],
        ['Source scope', data.sourceScope || '<root>'], ['Run mode', data.runMode],
        ['Effective item limit', data.effectiveItemLimit],
        ['Discovered', data.counts.discovered], ['Selected', data.counts.selected],
        ['Permitted', data.counts.permitted], ['Excluded/ignored', data.counts.excludedIgnored],
        ['Unstable', data.counts.unstable], ['Truncated by limit', data.counts.truncatedByLimit],
        ['Next action', data.nextAction], ['Error', data.error || '-']].forEach(([label, value]) => field(list, label, value));
      detailContent.append(list);
      detailContent.append(actionButton('Run a fresh Preview', () => confirmAutomationPreview({id: data.definitionId})));
      const rows = (data.items || []).map(item => [item.source.path, item.status,
        item.recognition.recognitionTypeId || '-', item.recognitionTypePolicy.recognitionTypePolicyId || '-',
        item.naming.directory || '-', item.destination.path || '-', item.operation || '-',
        item.blocker || item.nextAction || '-']);
      detailContent.append(text('h3', 'Per-item evidence'), table(
        ['Source', 'Status', 'RecognitionType', 'TypePolicy', 'Naming directory', 'Target', 'Operation', 'Blocker / next action'],
        rows));
      if (data.itemsTruncated) {
        detailContent.append(text('p', `${data.itemTotal} item records exist; the first 100 are shown here.`, 'warning'));
      }
      detail.hidden = false;
    } catch (error) { message(errorText(error), true); }
  }
  async function renderNotifications(status = 'all', cursor = null) {
    const selector = document.createElement('select'); selector.setAttribute('aria-label',
      'Notification status');
    ['all', 'pending', 'delivering', 'retry', 'delivered', 'dead-letter'].forEach(value => {
      const option = text('option', value); option.value = value; option.selected = value === status;
      selector.append(option);
    });
    const refresh = actionButton('Refresh notifications', () => renderNotifications(selector.value));
    const suffix = cursor ? `&cursor=${encodeURIComponent(cursor)}` : '';
    const data = await api(`/api/v1/notifications?limit=100&status=${encodeURIComponent(status)}` +
      suffix);
    clear(content); content.append(text('h2', 'Notification deliveries'), selector, refresh);
    const rows = (data.items || []).map(item => [item.deliveryId, item.webhookId, item.eventType,
      item.status, item.attempts, item.nextAttemptAt, item.updatedAt, item.failureCategory || '-',
      item.responseStatus || '-']);
    content.append(table(['Delivery', 'Webhook', 'Event', 'Status', 'Attempts', 'Next attempt',
      'Updated', 'Failure category', 'HTTP status'], rows));
    pageNavigation(content, 'notifications', data.previous_cursor, data.next_cursor,
      () => renderNotifications(status, data.previous_cursor),
      () => renderNotifications(status, data.next_cursor));
  }
  async function renderLogs(level = 'all', cursor = null) {
    const selector = document.createElement('select'); selector.setAttribute('aria-label', 'Log level');
    ['all', 'TRACE', 'DEBUG', 'INFO', 'WARN', 'ERROR'].forEach(value => {
      const option = text('option', value); option.value = value; option.selected = value === level;
      selector.append(option);
    });
    const refresh = actionButton('Refresh logs', () => renderLogs(selector.value));
    const suffix = cursor ? `&cursor=${encodeURIComponent(cursor)}` : '';
    const data = await api(`/api/v1/logs?limit=100&level=${encodeURIComponent(level)}${suffix}`);
    clear(content); content.append(text('h2', 'Operational logs'), selector, refresh);
    const rows = (data.items || []).map(item => [item.occurred_at, item.level, item.component,
      item.event, item.task_id || '-', item.job_id || '-', item.plan_id || '-', item.status || '-']);
    content.append(table(['Time', 'Level', 'Component', 'Event', 'Task', 'Job', 'Plan', 'Status'], rows));
    pageNavigation(content, 'logs', data.previous_cursor, data.next_cursor,
      () => renderLogs(level, data.previous_cursor),
      () => renderLogs(level, data.next_cursor));
  }
  function scalarDetails(data, excluded = []) {
    const list = document.createElement('dl');
    Object.entries(data).filter(([key, value]) => !excluded.includes(key) &&
      !Array.isArray(value) && typeof value !== 'object')
      .forEach(([key, value]) => field(list, key, value));
    return list;
  }
  async function showTask(id, itemCursor = null, resultCursor = null) {
    try {
      const itemSuffix = itemCursor ? `&itemCursor=${encodeURIComponent(itemCursor)}` : '';
      const resultSuffix = resultCursor ? `&resultCursor=${encodeURIComponent(resultCursor)}` : '';
      const data = await api(`/api/v1/tasks/${encodeURIComponent(id)}` +
        `?itemLimit=100&resultLimit=100${itemSuffix}${resultSuffix}`);
      clear(detailContent); detailContent.append(text('h2', 'Task detail'),
        scalarDetails(data, ['items_truncated', 'results_truncated']));
      renderManualExecutionDiscovery(data.manualExecutionDiscovery);
      const manualScan = data.manualScan;
      if (manualScan && typeof manualScan === 'object') {
        const scanList = document.createElement('dl');
        [['Scan scope', `${manualScan.scopeKind || '-'}:${manualScan.scopeId || '-'}`],
          ['Scan mode', manualScan.mode], ['Cancellation requested', manualScan.cancellationRequested ? 'yes' : 'no'],
          ['Reconciliation complete', manualScan.reconciliationComplete ? 'yes' : 'no'],
          ['Failure stage', manualScan.failureStage || '-'],
          ['Known effects', manualScan.knownEffects || 'none'],
          ['Retry safe', manualScan.retrySafe ? 'yes' : 'no'],
          ['Next action', manualScan.nextAction || '-']].forEach(([label, value]) => field(scanList, label, value));
        detailContent.append(text('h3', 'Manual Scan state'), scanList);
        const progress = manualScan.progress && typeof manualScan.progress === 'object' ? manualScan.progress : {};
        detailContent.append(text('p', `Progress: directories ${progress.directoriesVisited || 0}, ` +
          `files ${progress.filesVisited || 0}, candidates ${progress.mediaCandidates || 0}, ` +
          `unstable ${progress.unstable || 0}, errors ${progress.errors || 0}.`));
        if (['pending', 'running'].includes(manualScan.status) && !manualScan.cancellationRequested) {
          detailContent.append(text('p',
            'Cancellation is cooperative and never rolls back FileIndex discovery already persisted.',
            'warning'), actionButton('Request Scan cancellation', () =>
              confirmManualScanCancellation(manualScan.taskId)));
        }
        const scanItems = Array.isArray(manualScan.items) ? manualScan.items : [];
        if (scanItems.length) {
          detailContent.append(text('h4', 'Per-item discovery outcomes'), table(
            ['Item', 'Status', 'Change', 'Source', 'Occurrence', 'Stage', 'Next action'],
            scanItems.map(item => [item.itemId, item.status, item.change || '-', item.sourcePath,
              item.sourceOccurrenceId || '-', item.stage, item.nextAction || '-'])));
        }
        const scanErrors = Array.isArray(manualScan.errors) ? manualScan.errors : [];
        if (scanErrors.length) {
          detailContent.append(text('h4', 'Scan errors'), table(
            ['Code', 'Path', 'Operation'], scanErrors.map(item => [item.code, item.path || '-', item.operation || '-'])));
        }
      }
      const items = (data.items || []).map(item => {
        const checkpoint = item.checkpoint && typeof item.checkpoint === 'object' ? item.checkpoint : {};
        return [item.item_id, item.status, checkpoint.stage || item.stage,
          checkpoint.blocker_kind ? `${checkpoint.blocker_kind}:${checkpoint.blocker_id || '-'}` : '-',
          checkpoint.effect_certainty || 'unknown', checkpoint.retry_safety || 'unknown',
          checkpoint.recovery_request ?
            `${checkpoint.recovery_request.action_id}:${checkpoint.recovery_request.request_id}` : '-',
          item.storage_id, item.source_display, item.destination_storage_id || '-',
          item.destination_path || '-'];
      });
      detailContent.append(text('h3', 'Items'), table(
        ['ID', 'Status', 'Stage', 'Blocker', 'Effect certainty', 'Retry safety', 'Recovery request',
          'Source storage', 'Source', 'Target storage', 'Target'], items,
        index => showTaskItem(id, (data.items || [])[index] && (data.items || [])[index].item_id)));
      const eligible = (data.items || []).filter(item => {
        const checkpoint = item.checkpoint && typeof item.checkpoint === 'object' ? item.checkpoint : {};
        return Array.isArray(checkpoint.permitted_action_ids) &&
          (checkpoint.permitted_action_ids.includes('continue') ||
            checkpoint.permitted_action_ids.includes('retry'));
      });
      if (eligible.length) {
        const controls = text('div', '', 'choices');
        controls.append(text('h3', 'Batch recovery'));
        const selection = text('div', 'Select eligible items for one analysis-only continuation batch.');
        eligible.forEach(item => {
          const checkpoint = item.checkpoint;
          const label = document.createElement('label');
          const input = document.createElement('input');
          input.type = 'checkbox'; input.value = item.item_id; input.checked = true;
          input.dataset.checkpointVersion = checkpoint.checkpoint_version;
          label.append(input, text('span', ` ${item.item_id}`)); selection.append(label);
        });
        controls.append(selection, actionButton('Continue selected items (DryRun)', () => {
          const values = Array.from(selection.querySelectorAll('input[type="checkbox"]:checked'))
            .map(input => ({itemId: input.value, expectedCheckpointVersion: input.dataset.checkpointVersion}));
          confirmBatchRecovery(id, values, controls);
        }));
        detailContent.append(controls);
      }
      const batches = Array.isArray(data.recovery_batches) ? data.recovery_batches : [];
      if (batches.length) {
        detailContent.append(text('h3', 'Recovery batches'), table(
          ['Batch', 'Status', 'Selected', 'Queued', 'Running', 'Completed', 'Failed',
            'Ignored', 'Unchanged', 'Next action'],
          batches.map(batch => [batch.batch_id, batch.status, batch.selected_count,
            batch.counts && batch.counts.queued, batch.counts && batch.counts.running,
            batch.counts && batch.counts.completed, batch.counts && batch.counts.failed,
            batch.counts && batch.counts.ignored, batch.counts && batch.counts.unchanged,
            batch.next_action]),
          index => showRecoveryBatch(batches[index].batch_id)));
      }
      if (data.items_truncated) detailContent.append(text('p',
        `Items truncated at ${data.item_limit}.`, 'warning'));
      pageNavigation(detailContent, 'items', data.previous_item_cursor, data.next_item_cursor,
        () => showTask(id, data.previous_item_cursor, resultCursor),
        () => showTask(id, data.next_item_cursor, resultCursor));
      const results = (data.results || []).map(item => {
        const sourceItem = (data.items || []).find(value => value.item_id === item.item_id) || {};
        return [item.result_id, item.status, item.recognition_type || '-', item.title || '-',
          item.operation || '-', item.destination_path || '-', item.created_at,
          actionButton('Open file', () => openFileFromSource(item.source_storage_id ||
            sourceItem.storage_id, sourceItem.resource_library_id, item.source_path ||
            sourceItem.source_path))];
      });
      detailContent.append(text('h3', 'Results'), table(
        ['ID', 'Status', 'Type', 'Title', 'Operation', 'Destination', 'Created', 'File'],
        results));
      if (data.results_truncated) detailContent.append(text('p',
        `Results truncated at ${data.result_limit}.`, 'warning'));
      pageNavigation(detailContent, 'results', data.previous_result_cursor,
        data.next_result_cursor,
        () => showTask(id, itemCursor, data.previous_result_cursor),
        () => showTask(id, itemCursor, data.next_result_cursor));
      detail.hidden = false;
        } catch (error) { message(errorText(error), true); }
  }
  function confirmBatchRecovery(taskId, items, container) {
    if (!items.length) { message('Select at least one eligible item.', true); return; }
    const confirmation = text('div', '', 'choices');
    confirmation.append(text('p',
      `Confirm analysis-only recovery for ${items.length} selected item(s)? ` +
      'Each item keeps independent checkpoint, Job, Task and Result evidence. ' +
      'No media mutation or execution authority is granted.'));
    confirmation.append(actionButton('Confirm batch recovery', async () => {
      try {
        const batch = await api(`/api/v1/tasks/${encodeURIComponent(taskId)}/recovery/continue-batch`,
          {method: 'POST', body: JSON.stringify({items})});
        message(`Recovery batch ${batch.batch_id} admitted.`);
        confirmation.remove(); container.remove(); await showTask(taskId);
      } catch (error) { message(errorText(error), true); }
    }), actionButton('Keep items unchanged', () => confirmation.remove()));
    container.append(confirmation);
  }
  async function showRecoveryBatch(batchId) {
    try {
      const data = await api(`/api/v1/recovery-batches/${encodeURIComponent(batchId)}`);
      clear(detailContent); detailContent.append(text('h2', 'Recovery batch detail'),
        scalarDetails(data, ['items', 'counts']));
      detailContent.append(cards(Object.entries(data.counts || {}).map(([key, value]) => [key, value])));
      const batchItems = data.items || [];
      detailContent.append(table(
        ['Item', 'Status', 'Checkpoint version', 'Request', 'Continuation', 'Job',
          'New Task', 'New Result', 'Reason', 'Error', 'Next action'],
        batchItems.map(item => [item.source_item_id, item.status,
          item.checkpoint_version || '-', item.request_id || '-',
          item.continuation_id || '-', item.job_id || '-', item.new_task_id || '-',
          item.new_result_id || '-', item.reason || '-', item.error || '-',
          item.next_action || '-']),
        index => showTaskItem(batchItems[index].source_task_id,
          batchItems[index].source_item_id)));
      const linked = batchItems.filter(item => item.new_task_id);
      if (linked.length) {
        const links = text('div', '', 'choices');
        linked.forEach(item => {
          links.append(actionButton(
            `Open linked Task/Result for ${item.source_item_id}`,
            () => showTask(item.new_task_id)));
          if (item.job_id) {
            links.append(actionButton(
              `Open linked Job for ${item.source_item_id}`,
              () => showJob(item.job_id)));
          }
        });
        detailContent.append(text('h3', 'Linked DryRun Tasks/Results'), links);
      }
      const stranded = (data.items || []).some(item => item.status === 'selected');
      if (stranded) {
        const controls = text('div', '', 'choices');
        controls.append(text('p',
          'Some selected items never reached a durable outcome. Resume re-drives only those ' +
          'stranded items under the same analysis-only guarantees; no media mutation or ' +
          'execution authority is granted.'));
        controls.append(actionButton('Resume stranded items (DryRun)', () => {
          const confirmation = text('div', '', 'choices');
          confirmation.append(text('p', 'Confirm resume of stranded analysis-only items?'));
          confirmation.append(actionButton('Confirm resume', async () => {
            try {
              const updated = await api(
                `/api/v1/recovery-batches/${encodeURIComponent(batchId)}/resume`,
                {method: 'POST', body: ''});
              message(`Recovery batch ${updated.batch_id} resumed.`);
              confirmation.remove(); controls.remove(); await showRecoveryBatch(batchId);
            } catch (error) { message(errorText(error), true); }
          }), actionButton('Keep unchanged', () => confirmation.remove()));
          controls.append(confirmation);
        }));
        detailContent.append(controls);
      }
      detail.hidden = false;
    } catch (error) { message(errorText(error), true); }
  }
  async function showTaskItem(taskId, itemId) {
    if (!itemId) { message('Task item identity is unavailable.', true); return; }
    try {
      const data = await api(`/api/v1/tasks/${encodeURIComponent(taskId)}/items/` +
        `${encodeURIComponent(itemId)}`);
      clear(detailContent); detailContent.append(text('h2', 'Task item checkpoint'));
      detailContent.append(cards([
        ['Status', data.status], ['Durable stage', data.stage],
        ['Effect certainty', data.effects && data.effects.certainty],
        ['Retry safety', data.retry_safety], ['Checkpoint version', data.checkpoint_version]
      ]));
      const list = document.createElement('dl');
      field(list, 'Raw stage', data.raw_stage);
      field(list, 'Attempts', data.attempts);
      field(list, 'Source storage', data.source_storage_id);
      field(list, 'ResourceLibrary', data.resource_library_id);
      field(list, 'Storage-relative source', data.source_path);
      field(list, 'Plan', data.plan_id);
      field(list, 'Destination storage', data.destination_storage_id);
      field(list, 'Destination', data.destination_path);
      const configuration = data.configuration && typeof data.configuration === 'object' ?
        data.configuration : {};
      field(list, 'Pinned configuration', configuration.snapshot_id || '-');
      field(list, 'Configuration digest', configuration.snapshot_digest || '-');
      field(list, 'Configuration resolvable', configuration.resolvable === true ? 'YES' :
        configuration.resolvable === false ? `NO (${configuration.reason || 'unavailable'})` :
        'NOT DETERMINED');
      field(list, 'Error category', data.error_category);
      const failure = data.failureExplanation && typeof data.failureExplanation === 'object' ?
        data.failureExplanation : null;
      if (failure) {
        field(list, 'Failure explanation', failure.message || '-');
        field(list, 'Durable state', failure.durableState || '-');
        field(list, 'Failure side effects', failure.sideEffects || '-');
        field(list, 'Failure retry safe', failure.retrySafe === true ? 'YES' : 'NO');
        field(list, 'Failure next action', failure.nextAction || '-');
      }
      const effects = data.effects && typeof data.effects === 'object' ? data.effects : {};
      field(list, 'Completed effects', Array.isArray(effects.completed_operations) &&
        effects.completed_operations.length ? effects.completed_operations.join(', ') : 'none');
      field(list, 'Uncertain effects', Array.isArray(effects.uncertain_effects) &&
        effects.uncertain_effects.length ? effects.uncertain_effects.join(', ') : 'none');
      field(list, 'Refusal reason', data.refusal_reason || 'none');
      detailContent.append(list);
      renderManualExecutionDiscovery(data.manualExecutionDiscovery);
      detailContent.append(actionButton('Open File/Media detail',
        () => openFileFromSource(data.source_storage_id, data.resource_library_id,
          data.source_path)));
      const blocker = data.blocker && typeof data.blocker === 'object' ? data.blocker : null;
      if (blocker) {
        const blockerSection = text('div', '', 'choices');
        blockerSection.append(text('h3', 'Blocking review / conflict'));
        blockerSection.append(text('p', `${blocker.kind}: ${blocker.id} (${blocker.status})`));
        blockerSection.append(actionButton('Open blocker', () => showCheckpointBlocker(
          blocker.resolution_path)));
        detailContent.append(blockerSection);
      }
      const actions = Array.isArray(data.actions) ? data.actions : [];
      detailContent.append(text('h3', 'Permitted actions'));
      if (actions.length) {
        detailContent.append(table(['Action', 'Confirmation', 'Authority', 'Resolution surface'],
          actions.map(action => [action.label || action.action_id,
            action.confirmation_required ? 'required' : 'not required',
            action.required_authority || '-', action.resolution_surface || '-'])));
        const admissible = actions.filter(action => action.admissible === true);
        if (admissible.length && !data.recovery_request) {
          const controls = text('div', '', 'choices');
          admissible.forEach(action => controls.append(actionButton(
            `Request ${action.label || action.action_id}`,
            () => confirmTaskRecovery(taskId, itemId, data.checkpoint_version, action))));
          detailContent.append(text('p',
            'These are the only actions admitted by the current API checkpoint. Any real recovery is separately validated.',
            'warning'), controls);
        }
        const continuable = admissible.filter(action => action.action_id === 'continue');
        if (continuable.length && data.recovery_request && !data.recovery_continuation) {
          const controls = text('div', '', 'choices');
          continuable.forEach(action => controls.append(actionButton(
            'Continue safe analysis',
            () => confirmRecoveryContinuation(taskId, itemId, data.checkpoint_version, action))));
          detailContent.append(text('p',
            'Continue the admitted safe analysis as a bounded DryRun-only continuation; ' +
            'it grants no execute, overwrite, delete, source-cleanup or rollback authority.',
            'warning'), controls);
        }
      } else {
        detailContent.append(text('p', data.refusal_reason || 'No action is currently permitted.',
          'warning'));
      }
      if (data.recovery_request && typeof data.recovery_request === 'object') {
        const request = data.recovery_request;
        detailContent.append(text('h3', 'Admitted recovery request'), cards([
          ['Request', request.request_id], ['Action', request.action_id],
          ['Actor', request.actor], ['Requested', request.requested_at],
          ['Bound checkpoint', request.checkpoint_version], ['Next action', request.next_action]
        ]));
      }
      const continuation = data.recovery_continuation &&
        typeof data.recovery_continuation === 'object' ? data.recovery_continuation : null;
      if (continuation) {
        const continuationSection = text('div', '', 'choices');
        continuationSection.append(text('h3', 'Recovery continuation'), cards([
          ['Status', continuation.status], ['Boundary', continuation.boundary],
          ['Bound checkpoint', continuation.checkpoint_version], ['Authority', 'DRY_RUN_ONLY']
        ]));
        const continuationList = document.createElement('dl');
        field(continuationList, 'Continuation', continuation.continuation_id);
        field(continuationList, 'Request', continuation.request_id);
        field(continuationList, 'Job', continuation.job_id || '-');
        field(continuationList, 'New Task', continuation.new_task_id || '-');
        field(continuationList, 'New Result', continuation.new_result_id || '-');
        field(continuationList, 'Error', continuation.error || 'none');
        field(continuationList, 'Recovery', continuation.recovery || '-');
        field(continuationList, 'Next action', continuation.next_action || '-');
        continuationSection.append(continuationList);
        const continuationLinks = text('div', '', 'choices');
        if (continuation.job_id) {
          continuationLinks.append(actionButton('Open linked Job', () => showJob(continuation.job_id)));
        }
        if (continuation.new_task_id) {
          continuationLinks.append(actionButton('Open linked Task', () => showTask(continuation.new_task_id)));
        }
        if (continuationLinks.childNodes.length) continuationSection.append(continuationLinks);
        detailContent.append(continuationSection);
      }
      const recoveryLink = data.manualRecoveryLink &&
        typeof data.manualRecoveryLink === 'object' ? data.manualRecoveryLink : null;
      if (recoveryLink) {
        const linkSection = text('div', '', 'choices');
        linkSection.append(text('h3', 'Continued manual Organize authority'), cards([
          ['Status', recoveryLink.status], ['Link', recoveryLink.link_id],
          ['Exact Preview', recoveryLink.preview_id],
          ['One-shot authorization', recoveryLink.authorization_id],
          ['Analysis Task', recoveryLink.analysis_task_id || '-']
        ]));
        linkSection.append(text('p', recoveryLink.next_action || '-', 'warning'));
        const linkButtons = text('div', '', 'choices');
        if (recoveryLink.authorizationPath) {
          linkButtons.append(actionButton('Open exact Preview / authorization',
            () => showManualAuthorization(recoveryLink.authorization_id)));
        }
        if (recoveryLink.status === 'authorized') {
          linkButtons.append(actionButton('Execute continued manual organize',
            () => confirmManualRecoveryExecute(taskId, itemId, recoveryLink)));
        }
        if (recoveryLink.execution_id) {
          linkButtons.append(actionButton('Open continued execution',
            () => showManualExecution(recoveryLink.execution_id)));
        }
        linkSection.append(linkButtons);
        detailContent.append(linkSection);
      } else if (continuation && continuation.status === 'completed') {
        const controls = text('div', '', 'choices');
        controls.append(actionButton('Authorize continued manual organize',
          () => confirmManualRecoveryAuthorize(taskId, itemId, data.checkpoint_version)));
        detailContent.append(text('p',
          'A completed DryRun re-analysis is linked. Authorizing continued manual organize ' +
          'creates a fresh exact Preview and a separate one-shot execution authority; it ' +
          'performs no media mutation until the authority is explicitly executed.',
          'warning'), controls);
      }
      const results = Array.isArray(data.prior_results) ? data.prior_results.slice() : [];
      if (data.latest_result) results.unshift(data.latest_result);
      if (results.length) {
        detailContent.append(text('h3', 'Persisted results'), table(
          ['Result', 'Status', 'Effect certainty', 'Operation', 'Destination'],
          results.map(result => [result.result_id, result.status, result.effect_certainty,
            result.operation || '-', result.destination_path || '-'])));
      }
      detail.hidden = false;
    } catch (error) { message(errorText(error), true); }
  }
  function renderFileMediaSections(data) {
    const evidence = Array.isArray(data.evidence) ? data.evidence : [];
    detailContent.append(text('h3', `Captured pipeline evidence (${evidence.length})`));
    if (!evidence.length) {
      detailContent.append(text('p',
        'No captured evidence is available for this legacy record. Unavailable fields are ' +
        'shown explicitly and are never inferred from the current state.', 'warning'));
    }
    evidence.forEach(record => {
      const sections = record.sections || {};
      detailContent.append(text('h4',
        `Attempt ${record.attempts || '-'} - ${record.outcome || '-'} (${record.evidenceId || '-'})`));
      detailContent.append(table(['Field', 'Value'], [
        ['Task', record.taskId], ['Item', record.itemId],
        ['Configuration snapshot', record.configurationSnapshotId || '-'],
        ['Configuration digest', record.configurationSnapshotDigest || '-'],
        ['Captured', record.capturedAt], ['Error', record.error || 'none']
      ]));
      Object.keys(sections).forEach(name => {
        const section = sections[name];
        if (!section) return;
        detailContent.append(text('h4',
          `${name} - ${section.available ? 'available' : 'unavailable'}`));
        if (section.unavailableReason) {
          detailContent.append(text('p', section.unavailableReason, 'warning'));
        }
        if (section.value && Object.keys(section.value).length) {
          const rows = Object.entries(section.value).map(([key, value]) => [key,
            Array.isArray(value) ? value.join(', ') :
              value === null || value === undefined ? '-' : String(value)]);
          detailContent.append(table(['Field', 'Value'], rows));
        }
        if (Array.isArray(section.items) && section.items.length) {
          detailContent.append(table(['Item'],
            section.items.map(item => [JSON.stringify(item)])));
        }
        if (section.truncated) {
          detailContent.append(text('p', 'This evidence section is truncated.', 'warning'));
        }
      });
    });
    const items = Array.isArray(data.items) ? data.items : [];
    detailContent.append(text('h3', `Related TaskItems / checkpoints (${items.length})`));
    if (items.length) {
      detailContent.append(table(
        ['Task', 'Item', 'Status', 'Stage', 'Updated', 'Checkpoint', 'TaskItem'],
        items.map(item => [item.taskId, item.itemId, item.status, item.stage, item.updatedAt,
          item.checkpoint && item.checkpoint.checkpoint_version || '-',
          actionButton('Open checkpoint', () => showTaskItem(item.taskId, item.itemId))])));
      items.forEach(item => {
        const checkpoint = item.checkpoint && typeof item.checkpoint === 'object' ?
          item.checkpoint : null;
        if (!checkpoint) {
          detailContent.append(text('p',
            `Checkpoint for TaskItem ${item.itemId} is unavailable; no state is inferred.`,
            'warning'));
          return;
        }
        const effects = checkpoint.effects && typeof checkpoint.effects === 'object' ?
          checkpoint.effects : {};
        detailContent.append(text('h4', `Checkpoint history - ${item.itemId}`));
        detailContent.append(table(['Field', 'Value'], [
          ['Status', checkpoint.status || item.status],
          ['Durable stage', checkpoint.stage || item.stage],
          ['Raw stage', checkpoint.raw_stage || '-'],
          ['Attempts', checkpoint.attempts],
          ['Effect certainty', effects.certainty || 'unknown'],
          ['Completed effects', Array.isArray(effects.completed_operations) &&
            effects.completed_operations.length ? effects.completed_operations.join(', ') : 'none'],
          ['Uncertain effects', Array.isArray(effects.uncertain_effects) &&
            effects.uncertain_effects.length ? effects.uncertain_effects.join(', ') : 'none'],
          ['Error category', checkpoint.error_category || 'none'],
          ['Retry safety', checkpoint.retry_safety || 'unknown'],
          ['Refusal reason', checkpoint.refusal_reason || 'none']
        ]));
        if (checkpoint.blocker) {
          const blocker = checkpoint.blocker;
          const blockerControls = text('div', '', 'choices');
          blockerControls.append(text('p',
            `${blocker.kind}: ${blocker.id} (${blocker.status})`));
          if (blocker.resolution_path) blockerControls.append(actionButton('Open resolution',
            () => showCheckpointBlocker(blocker.resolution_path)));
          detailContent.append(blockerControls);
        }
        const audits = Array.isArray(checkpoint.audits) ? checkpoint.audits : [];
        if (audits.length) {
          detailContent.append(text('h5', `Checkpoint audits (${audits.length})`), table(
            ['Audit', 'Kind', 'Occurred', 'Actor'],
            audits.map(audit => [audit.audit_id, audit.kind, audit.occurred_at,
              audit.actor || '-'])));
        }
        const recovery = Array.isArray(checkpoint.recovery_requests) ?
          checkpoint.recovery_requests : [];
        if (recovery.length) {
          detailContent.append(text('h5', `Recovery requests (${recovery.length})`), table(
            ['Request', 'Action', 'Status', 'Next action'],
            recovery.map(request => [request.request_id, request.action_id, request.status,
              request.next_action || '-'])));
        }
      });
    }
    const results = Array.isArray(data.results) ? data.results : [];
    detailContent.append(text('h3', `Results / effects (${results.length})`));
    if (results.length) {
      detailContent.append(table(
        ['Result', 'Status', 'Type', 'Operation', 'Destination', 'Effect certainty',
          'Completed effects', 'Uncertain effects', 'Error', 'Created'],
        results.map(result => [result.resultId, result.status, result.recognitionType || '-',
          result.operation || '-', result.destinationPath || '-',
          result.effectCertainty || 'unknown',
          Array.isArray(result.completedOperations) && result.completedOperations.length ?
            result.completedOperations.join(', ') : 'none',
          Array.isArray(result.uncertainEffects) && result.uncertainEffects.length ?
            result.uncertainEffects.join(', ') : 'none',
          result.error || 'none', result.createdAt])));
    }
    const actions = Array.isArray(data.currentActions) ? data.currentActions : [];
    detailContent.append(text('h3', `Current valid actions (${actions.length})`));
    if (actions.length) {
      detailContent.append(table(
        ['Action', 'Item', 'Admissible', 'Confirmation', 'Authority', 'Resolution', 'Open'],
        actions.map(action => [action.label || action.actionId, action.itemId,
          action.admissible ? 'yes' : 'no',
          action.confirmationRequired ? 'required' : 'not required',
          action.requiredAuthority || '-', action.resolutionSurface || '-',
          actionButton('Open checkpoint', () => action.resolutionSurface ?
            showCheckpointBlocker(action.resolutionSurface) :
            showTaskItem(action.taskId, action.itemId))])));
    } else {
      detailContent.append(text('p', items.length ?
        'No replay control is exposed for the current terminal or ineligible state.' :
        'No durable TaskItem state is available for this file.', 'warning'));
    }
    if (data.truncated && typeof data.truncated === 'object') {
      Object.entries(data.truncated).filter(([, value]) => value).forEach(([name]) => {
        detailContent.append(text('p', `${name} truncated; showing a bounded set.`, 'warning'));
      });
    }
  }
  function confirmRecoveryContinuation(taskId, itemId, checkpointVersion, action) {
    const confirmation = text('div', '', 'choices');
    const label = action.label || action.action_id;
    confirmation.append(text('p',
      `Confirm ${label} for checkpoint ${checkpointVersion}? This re-enters the production ` +
      `pipeline for exactly this one item as analysis-only (DRY_RUN). It grants no execute, ` +
      `overwrite, delete, source-cleanup or rollback authority and performs no media mutation.`),
      actionButton(`Confirm ${label}`, async () => {
        try {
          await api(`/api/v1/tasks/${encodeURIComponent(taskId)}/items/${encodeURIComponent(itemId)}/recovery/continue`, {
            method: 'POST',
            body: JSON.stringify({expectedCheckpointVersion: checkpointVersion})
          });
          await showTaskItem(taskId, itemId); message('Recovery continuation admitted.');
        } catch (error) { message(errorText(error), true); }
      }), actionButton('Keep item unchanged', () => confirmation.remove()));
    detailContent.append(confirmation);
  }
  function confirmManualRecoveryAuthorize(taskId, itemId, checkpointVersion) {
    const confirmation = text('div', '', 'choices');
    confirmation.append(text('p',
      'Authorize continued manual organize for this exact original item? This creates a ' +
      'fresh current-source Preview and one separate one-shot execution authority. ' +
      'Storage remains unchanged until that authority is explicitly executed.'),
      actionButton('Confirm authorization', async () => {
        try {
          const link = await api(`/api/v1/tasks/${encodeURIComponent(taskId)}/items/` +
            `${encodeURIComponent(itemId)}/recovery/authorize-organize`, {
              method: 'POST',
              body: JSON.stringify({expectedCheckpointVersion: checkpointVersion,
                confirmation: true})
          });
          await showTaskItem(taskId, itemId);
          message(`Continued manual Organize authorized: ${link.link_id}`);
        } catch (error) { message(errorText(error), true); }
      }), actionButton('Keep source unchanged', () => confirmation.remove()));
    detailContent.append(confirmation);
  }
  function confirmManualRecoveryExecute(taskId, itemId, link) {
    const confirmation = text('div', '', 'choices');
    confirmation.append(text('p',
      'Execute the continued exact manual Organize authority exactly once? The persisted ' +
      'plan and current source will be revalidated; results and effects are recorded per item.'),
      actionButton('Confirm continued execution', async () => {
        try {
          await api(`/api/v1/manual-recovery-links/${encodeURIComponent(link.link_id)}/execute`, {
            method: 'POST', body: JSON.stringify({confirmation: true})
          });
          await showTaskItem(taskId, itemId);
          message('Continued manual execution completed or recorded per item.');
        } catch (error) { message(errorText(error), true); }
      }), actionButton('Do not execute', () => confirmation.remove()));
    detailContent.append(confirmation);
  }
  function confirmTaskRecovery(taskId, itemId, checkpointVersion, action) {
    const confirmation = text('div', '', 'choices');
    const label = action.label || action.action_id;
    confirmation.append(text('p',
      `Confirm ${label} for checkpoint ${checkpointVersion}? This records a bounded request only; no media mutation occurs now.`),
      actionButton(`Confirm ${label}`, async () => {
        try {
          await api(`/api/v1/tasks/${encodeURIComponent(taskId)}/items/${encodeURIComponent(itemId)}/recovery`, {
            method: 'POST',
            body: JSON.stringify({actionId: action.action_id,
              expectedCheckpointVersion: checkpointVersion})
          });
          await showTaskItem(taskId, itemId); message('Recovery request admitted.');
        } catch (error) { message(errorText(error), true); }
      }), actionButton('Keep item unchanged', () => confirmation.remove()));
    detailContent.append(confirmation);
  }
  async function showCheckpointBlocker(path) {
    const match = typeof path === 'string' &&
      path.match(/^\\/api\\/v1\\/([^/?]+)\\/([^/?]+)$/);
    const detailKinds = new Set(['confirmations', 'recognition-reviews', 'metadata-reviews',
      'metadata-corrections', 'classification-reviews']);
    if (match && detailKinds.has(match[1])) {
      await showDetail(match[1], decodeURIComponent(match[2]));
      return;
    }
    try {
      const data = await api(path);
      clear(detailContent); detailContent.append(text('h2', 'Blocking review / conflict'));
      detailContent.append(scalarDetails(data)); detail.hidden = false;
    } catch (error) { message(errorText(error), true); }
  }
  async function showJob(id) {
    try {
      const data = await api(`/api/v1/jobs/${encodeURIComponent(id)}`);
      clear(detailContent); detailContent.append(text('h2', 'Automation job detail'),
        scalarDetails(data));
      if (data.failure_category) detailContent.append(text('p',
        `Configuration failure: ${data.failure_category}. ` +
        `State: ${data.failure_durable_state || '-'}. ` +
        `Side effects: ${data.failure_side_effects || 'unknown'}. ` +
        `Retry safe: ${data.failure_retry_safe ? 'YES' : 'NO'}. ` +
        `Next action: ${data.failure_next_action || 'inspect the saved snapshot'}.`, 'error'));
      if (data.workerId) detailContent.append(text('p',
        `Owner worker: ${data.workerId} (${data.ownerStatus || '-'}, last heartbeat ` +
        `${data.ownerLastHeartbeatAt || '-'}).`, 'hint'));
      if (data.operationalCondition) detailContent.append(text('p',
        `Worker condition: ${data.operationalCondition.condition || '-'}. ` +
        `${data.operationalCondition.durableState || ''} ` +
        `Next action: ${data.operationalCondition.nextAction || '-'}.`, 'warning'));
      if (data.task_id) detailContent.append(actionButton('Open linked task', () => showTask(data.task_id)));
      if (data.status === 'pending' || data.status === 'running') {
        detailContent.append(text('p', data.status === 'running' ?
          'Cancellation is cooperative. An in-flight operation may finish and completed work is not rolled back.' :
          'Cancellation prevents this pending job from starting. It grants no media execution authority.',
          'warning'));
        detailContent.append(actionButton('Request cancellation', () => confirmJobCancellation(id)));
      }
      detail.hidden = false;
    } catch (error) { message(errorText(error), true); }
  }
  function confirmJobCancellation(id) {
    const confirmation = text('div', '', 'choices');
    confirmation.append(text('p', 'Cancel this automation job? This does not roll back completed work.'),
      actionButton('Confirm cancellation', () => cancelJob(id)),
      actionButton('Keep job', () => confirmation.remove()));
    detailContent.append(confirmation);
  }
  async function cancelJob(id) {
    try {
      await api(`/api/v1/jobs/${encodeURIComponent(id)}/cancel`, {method: 'POST'});
      await renderObservability('jobs'); await showJob(id); message('Cancellation recorded.');
    } catch (error) { message(errorText(error), true); }
  }
  function confirmManualScanCancellation(id) {
    const confirmation = text('div', '', 'choices');
    confirmation.append(text('p',
      'Request cancellation for this bounded Scan? Persisted discovery is kept, no Storage media ' +
      'mutation is performed, and the Task will remain distinguishable from a completed full reconciliation.'),
      actionButton('Confirm Scan cancellation', () => cancelManualScan(id)),
      actionButton('Keep Scan running', () => confirmation.remove()));
    detailContent.append(confirmation);
  }
  async function cancelManualScan(id) {
    try {
      await api(`/api/v1/scans/${encodeURIComponent(id)}/cancel`, {method: 'POST'});
      await showTask(id); message('Manual Scan cancellation request persisted.');
    } catch (error) { message(errorText(error), true); }
  }
  async function showDetail(kind, id) {
    try {
      const data = await api(`/api/v1/${kind}/${encodeURIComponent(id)}`);
      clear(detailContent); detailContent.append(text('h2', 'Review detail'));
      const list = document.createElement('dl');
      Object.entries(data).filter(([, value]) => !Array.isArray(value) && typeof value !== 'object')
        .forEach(([key, value]) => field(list, key, value)); detailContent.append(list);
      if (kind === 'files') {
        const discovery = data.discovery || {};
        const processing = data.processing || {};
        const occurrence = data.currentOccurrence || {};
        detailContent.append(text('h3', 'Current-source lifecycle'));
        detailContent.append(table(['Dimension', 'State', 'Evidence / next action'], [
          ['Scan / discovery', discovery.status || data.scanStatus || '-',
            `change ${discovery.change || data.change || '-'}; ` +
            `last seen ${discovery.lastSeenAt || data.lastSeenAt || '-'}`],
          ['Processing disposition', processing.disposition || data.processingDisposition || '-',
            processing.nextAction || '-'],
          ['Current occurrence', occurrence.occurrenceId || '-',
            `fingerprint ${occurrence.fingerprint || '-'}; state ${occurrence.state || 'unverified'}`]
        ]));
        const scanPayload = manualScanPayloadFromFile(data);
        if (scanPayload) {
          detailContent.append(actionButton('Scan current source (DryRun)', () =>
            confirmManualScan(scanPayload, `Scan current FileIndex item ${id}`)));
        } else {
          detailContent.append(text('p',
            'Manual Scan unavailable: select a verified ready current occurrence from FileIndex.',
            'warning'));
        }
        const previewPayload = manualPreviewPayloadFromFile(data);
        if (previewPayload) {
          detailContent.append(actionButton('Preview current source (DryRun)', () =>
            confirmCurrentPreview(previewPayload, `Preview current FileIndex item ${id}`)));
        } else {
          detailContent.append(text('p',
            'Preview unavailable: select a verified ready current occurrence from FileIndex.',
            'warning'));
        }
        const reprocess = data.reprocess || {};
        if (reprocess.eligible === true) {
          detailContent.append(actionButton('Request explicit Reprocess', () =>
            confirmFileReprocess(id, data)));
        } else {
          detailContent.append(text('p',
            `Reprocess unavailable: ${reprocess.reason || 'current occurrence is not eligible'}. ` +
            'Refresh discovery or resolve the durable processing state before retrying.', 'warning'));
        }
        const history = Array.isArray(data.occurrenceHistory) ? data.occurrenceHistory : [];
        if (history.length) {
          detailContent.append(text('h3', `Occurrence history (${history.length})`), table(
            ['Occurrence', 'State', 'Current', 'Processing disposition', 'First seen', 'Superseded'],
            history.map(item => [item.occurrenceId, item.state, item.current ? 'yes' : 'no',
              item.processingDisposition || '-', item.firstSeenAt || '-', item.supersededAt || '-'])));
        }
        const reprocessRequests = Array.isArray(data.reprocessRequests) ? data.reprocessRequests : [];
        if (reprocessRequests.length) {
          detailContent.append(text('h3', `Reprocess admissions (${reprocessRequests.length})`), table(
            ['Request', 'Status', 'Actor', 'Occurrence', 'Next action'],
            reprocessRequests.map(item => [item.requestId, item.status, item.actor,
              item.occurrenceId, item.nextAction || '-'])));
        }
        renderManualExecutionDiscovery(data.manualExecutionDiscovery);
        detailContent.append(actionButton('Start manual organize for this file', () =>
          confirmManualIntent([id])));
        if (data.latestResult && data.latestResult.taskId) {
          detailContent.append(actionButton('Open linked task',
            () => showTask(data.latestResult.taskId)));
        }
        if (data.latestResult && ['failed', 'partial'].includes(data.latestResult.status)) {
          detailContent.append(actionButton('Request re-plan',
            () => resolve(`/api/v1/files/${encodeURIComponent(id)}/re-plan`, {})));
        }
        if (Array.isArray(data.relatedReviews) && data.relatedReviews.some(item =>
          item.kind === 'recognition' && item.status === 'pending')) {
          detailContent.append(actionButton('Request re-recognition',
            () => resolve(`/api/v1/files/${encodeURIComponent(id)}/re-recognize`, {})));
        }
        if (Array.isArray(data.relatedReviews) && data.relatedReviews.some(item =>
          item.kind === 'metadata_correction' && item.status === 'pending')) {
          renderFileReMatchForm(id);
        }
        const continuationReview = Array.isArray(data.relatedReviews)
          ? data.relatedReviews.find(item => item.kind === 'metadata_correction' &&
              item.status === 'resolved' && (item.canContinue || item.continuation))
          : null;
        if (continuationReview) renderMetadataContinuation(id, continuationReview);
        if (Array.isArray(data.relatedReviews) && data.relatedReviews.length) {
          const rows = data.relatedReviews.map(item => [item.kind, item.reviewId,
            item.status, item.taskId, item.itemId || '-', item.continuation ?
              item.continuation.status : '-',
            actionButton('Open review', () => showDetail(
              item.kind === 'conflict' ? 'confirmations' :
                item.kind === 'metadata_correction' ? 'metadata-corrections' :
                `${item.kind}-reviews`, item.reviewId))]);
          detailContent.append(text('h3', 'Related reviews'),
            table(['Kind', 'Review', 'Status', 'Task', 'Item', 'Continuation', 'Open'], rows));
        }
        renderFileMediaSections(data);
      }
      if (['confirmations', 'recognition-reviews', 'metadata-reviews',
        'classification-reviews', 'metadata-corrections'].includes(kind) &&
        (data.source_storage_id || data.sourceStorageId)) {
        detailContent.append(actionButton('Open File/Media detail',
          () => openFileFromSource(data.source_storage_id || data.sourceStorageId,
            data.resource_library_id || data.resourceLibraryId,
            data.source_path || data.sourcePath)));
      } else if (['confirmations', 'recognition-reviews', 'metadata-reviews',
        'classification-reviews', 'metadata-corrections'].includes(kind)) {
        detailContent.append(text('p',
          'File/Media link unavailable: this review has no durable source identity; no File ID is guessed.',
          'warning'));
      }
      if (kind === 'confirmations' && data.status === 'pending') renderConflictActions(id);
      if (kind === 'metadata-reviews' && data.status === 'pending') renderRankActions(kind, id, data.candidates || [],
        'candidateRank', ['rank', 'title', 'year', 'provider_id']);
      if (kind === 'classification-reviews' && data.status === 'pending') renderRankActions(kind, id, data.choices || [],
        'choiceRank', ['rank', 'rule_id', 'media_library_id', 'relative_path']);
      detail.hidden = false;
    } catch (error) { message(errorText(error), true); }
  }
  function actionButton(label, action) {
    const button = text('button', label); button.addEventListener('click', action); return button;
  }
  async function openFileFromSource(storageId, resourceLibraryId, path) {
    if (!storageId || !path) {
      message('File source identity is unavailable; the current file cannot be resolved.', true);
      return;
    }
    const parts = [`storageId=${encodeURIComponent(storageId)}`,
      `path=${encodeURIComponent(path)}`];
    if (resourceLibraryId) parts.push(`resourceLibrary=${encodeURIComponent(resourceLibraryId)}`);
    try {
      const data = await api(`/api/v1/files/by-source?${parts.join('&')}`);
      if (!data.available || !data.fileId) {
        message(`File link unavailable: ${data.unavailableReason || 'no current indexed file'}`,
          true);
        return;
      }
      await showDetail('files', data.fileId);
    } catch (error) { message(errorText(error), true); }
  }
  function renderConflictActions(id) {
    const actions = text('div', '', 'choices');
    ['skip', 'rename'].forEach(strategy => actions.append(actionButton(strategy,
      () => resolve(`/api/v1/confirmations/${encodeURIComponent(id)}/resolve`, {strategy}))));
    detailContent.append(text('h3', 'Allowed decisions'), actions);
  }
  function renderRankActions(kind, id, items, key, fields) {
    const choices = text('div', '', 'choices');
    items.forEach(item => {
      const row = text('div', '', 'choice'); const description = fields.map(name => item[name])
        .filter(value => value !== null && value !== undefined).join(' | ');
      row.append(text('span', description), actionButton(`Select rank ${item.rank}`,
        () => resolve(`/api/v1/${kind}/${encodeURIComponent(id)}/resolve`, {[key]: item.rank})));
      choices.append(row);
    }); detailContent.append(text('h3', 'Persisted choices'), choices);
  }
  async function resolve(path, payload) {
    try { await api(path, {method: 'POST', body: JSON.stringify(payload)});
      detail.hidden = true; message('Decision saved. Task was not resumed.'); await load();
    } catch (error) { message(errorText(error), true); }
  }
  async function load() {
    try { message('Loading...');
      if (view === 'dashboard') renderDashboard(await api('/api/v1/dashboard?recentLimit=10'));
      else if (view === 'tasks' || view === 'jobs') await renderObservability(view);
      else if (view === 'schedules') await renderSchedules();
      else if (view === 'automation') await renderAutomation();
      else if (view === 'notifications') await renderNotifications();
      else if (view === 'logs') await renderLogs();
      else if (view === 'system') await renderSystem();
      else if (view === 'workers') await renderWorkers();
      else if (view === 'configuration') await renderConfiguration();
      else if (view === 'files') await renderFiles();
      else if (view === 'file-index') await renderFileIndex();
      else await renderQueue(view); message('Connected.');
    } catch (error) { clear(content); message(errorText(error), true); }
  }
  document.getElementById('connect').addEventListener('click', async () => {
    token = tokenInput.value; tokenInput.value = '';
    try {
      const readiness = await api('/api/v1/management/readiness');
      if (readiness.setupRequired || readiness.recoveryRequired) {
        view = 'configuration';
        document.querySelectorAll('nav button').forEach(item =>
          item.classList.toggle('active', item.dataset.view === view));
      }
      await load();
    } catch (error) { clear(content); message(errorText(error), true); }
  });
  document.getElementById('disconnect').addEventListener('click', () => {
    token = ''; tokenInput.value = ''; clear(content); detail.hidden = true; message('Disconnected.');
  });
  document.getElementById('close-detail').addEventListener('click', () => { detail.hidden = true; });
  document.querySelectorAll('nav button').forEach(button => button.addEventListener('click', () => {
    document.querySelectorAll('nav button').forEach(item => item.classList.remove('active'));
    button.classList.add('active'); view = button.dataset.view; detail.hidden = true; load();
  }));
})();
"""


ASSETS = {
    "/ui": ("text/html; charset=utf-8", INDEX_HTML),
    "/ui/": ("text/html; charset=utf-8", INDEX_HTML),
    "/ui/app.js": ("text/javascript; charset=utf-8", APP_JS),
    "/ui/style.css": ("text/css; charset=utf-8", STYLE_CSS),
}
