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
    <button data-view="jobs">Jobs</button>
    <button data-view="schedules">Schedules</button>
    <button data-view="notifications">Notifications</button>
    <button data-view="logs">Logs</button>
    <button data-view="confirmations">Conflicts</button>
    <button data-view="metadata-reviews">Metadata</button>
    <button data-view="classification-reviews">Classification</button>
    <button data-view="configuration">Configuration</button>
    <button data-view="system">System</button>
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
  async function renderConfiguration() {
    const data = await api('/api/v1/configuration');
    clear(content); content.append(text('h2', 'Configuration lifecycle'));
    const active = data.active || {};
    content.append(cards([
      ['Authority', data.authority], ['Active status', active.status || '-'],
      ['Active version', active.version || '-'], ['Revision sequence', active.revisionSequence || '-'],
      ['Active digest', active.digest || '-'], ['Health', data.health || '-'],
      ['Runtime ready', data.runtimeReady === undefined ? '-' : data.runtimeReady]
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
  function guidedObjectFields(kind, item = {}) {
    const fields = {
      storages: [['id', 'ID'], ['name', 'Name'], ['rootPath', 'Local root path']],
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
      if (input.type === 'checkbox') value[key] = input.checked;
      else if (key === 'extensions') value[key] = input.value.split(',').map(item => item.trim()).filter(Boolean);
      else if (key === 'maxDepth') value[key] = input.value === '' ? null : Number(input.value);
      else value[key] = input.value;
    });
    if (kind === 'resourceLibraries') {
      if (!value.displayRootPath) delete value.displayRootPath;
      if (!value.extensions || value.extensions.length === 0) delete value.extensions;
      if (value.maxDepth === null) delete value.maxDepth;
    }
    if (kind === 'storages') value.type = 'local';
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
  function configurationRevisionEditable(revision) {
    return revision.status === 'draft' || revision.status === 'validated';
  }
  function renderGuidedObjectList(revision, guided, kind, label) {
    const values = guided.objects && guided.objects[kind] || [];
    const referenceKind = {storages: 'storage', resourceLibraries: 'resource_library',
      mediaLibraries: 'media_library', recognitionTypes: 'recognition_type',
      recognitionRules: 'recognition_rule', recognitionTypePolicies: 'recognition_type_policy',
      metadataPolicies: 'metadata_policy', namingPolicies: 'naming_policy',
      classificationPolicies: 'classification_policy', organizePolicies: 'organize_policy'}[kind] || kind;
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
      if (kind === 'storages' && item.type !== 'local') {
        row.append(text('span', 'Remote/read-only here. Use JSON import for changes.', 'warning'));
      } else if (configurationRevisionEditable(revision)) {
        row.append(actionButton('Edit', () => renderGuidedObjectForm(revision, kind, item)));
        if (kind === 'namingPolicies' || kind === 'classificationPolicies' || kind === 'organizePolicies') row.append(actionButton('Copy', () => {
          const copied = {...item, id: `${item.id}-copy`, name: `${item.name || item.id} copy`};
          renderGuidedObjectForm(revision, kind, copied, true);
        }));
        row.append(actionButton('Delete', () => {
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
        organizePolicies: 'OrganizePolicy'}[kind] || kind;
      const classificationPolicy = kind === 'classificationPolicies';
      const organizePolicy = kind === 'organizePolicies';
      const guidedJson = kind.startsWith('recognition') ||
        kind === 'metadataPolicies' || kind === 'namingPolicies' || classificationPolicy || organizePolicy;
      const objectLabel = classificationPolicy ? 'ClassificationPolicy' : organizePolicy ? 'OrganizePolicy' : singular;
      detailContent.append(actionButton(`${guidedJson ? 'Add' : 'Add Local'} ${objectLabel}`,
        () => renderGuidedObjectForm(revision, kind, null)));
    }
  }
  function renderGuidedObjectForm(revision, kind, item, copyMode = false) {
    if (kind.startsWith('recognition') || kind === 'metadataPolicies' || kind === 'namingPolicies' || kind === 'classificationPolicies' || kind === 'organizePolicies') {
      const metadataPolicy = kind === 'metadataPolicies';
      const namingPolicy = kind === 'namingPolicies';
      const classificationPolicy = kind === 'classificationPolicies';
      const organizePolicy = kind === 'organizePolicies';
      clear(detailContent);
      detailContent.append(text('h2', `${item && !copyMode ? 'Edit' : 'Add'} ${metadataPolicy ? 'MetadataPolicy' : namingPolicy ? 'NamingPolicy' : classificationPolicy ? 'ClassificationPolicy' : organizePolicy ? 'OrganizePolicy' : 'recognition object'}`));
      detailContent.append(text('p', organizePolicy ?
        'Edit one bounded OrganizePolicy JSON object. Overwrite and source cleanup grant destructive authority and are never implicit.' : classificationPolicy ?
        'Edit one bounded ClassificationPolicy JSON object. Rules use the configured conditions and safe relative result paths.' : namingPolicy ?
        'Edit one bounded NamingPolicy JSON object. Templates use the restricted naming variables; separators, traversal, unknown variables and unsupported formats are rejected.' : metadataPolicy ?
        'Edit one bounded MetadataPolicy JSON object. Provider/query/locale/threshold/request settings are validated; credentials and unknown fields are rejected.' :
        'Edit one bounded JSON object. References and rule priority are checked when the Draft is validated; unsafe regex is rejected when saved.', 'warning'));
      const editor = document.createElement('textarea');
      editor.setAttribute('aria-label', metadataPolicy ? 'MetadataPolicy JSON' : namingPolicy ? 'NamingPolicy JSON' : classificationPolicy ? 'ClassificationPolicy JSON' : organizePolicy ? 'OrganizePolicy JSON' : 'Recognition object JSON');
      editor.value = JSON.stringify(item || {}, null, 2); detailContent.append(editor);
      detailContent.append(actionButton(metadataPolicy ? 'Save MetadataPolicy' : namingPolicy ? 'Save NamingPolicy' : classificationPolicy ? 'Save ClassificationPolicy' : organizePolicy ? 'Save OrganizePolicy' : 'Save recognition object', async () => {
        try { await mutateGuidedObject(revision, kind, item && !copyMode && item.id, JSON.parse(editor.value), item && !copyMode ? 'PUT' : 'POST'); }
        catch (error) { message(errorText(error), true); }
      }), actionButton('Back to revision', () => showConfigurationRevision(revision)));
      return;
    }
    clear(detailContent);
    detailContent.append(text('h2', `${item ? 'Edit' : 'Add'} Local ${kind === 'storages' ? 'Storage' :
      kind === 'resourceLibraries' ? 'ResourceLibrary' : 'MediaLibrary'}`));
    detailContent.append(text('p', 'Only Local objects are editable here. Remote objects remain redacted and read-only.', 'warning'));
    detailContent.append(text('p', kind === 'storages' ?
      'Local Storage rootPath is a host-absolute directory. ResourceLibrary storagePath and MediaLibrary rootPath are Storage-relative paths.' :
      'Use Storage-relative paths for this object; absolute paths and traversal are rejected.', 'warning'));
    const form = text('div', '', 'choices'); const fields = guidedObjectFields(kind, item || {});
    Object.values(fields).forEach(input => form.append(input.parentElement)); detailContent.append(form);
    detailContent.append(actionButton('Save guided object', async () => {
      try { await mutateGuidedObject(revision, kind, item && item.id, guidedObjectPayload(kind, fields), item ? 'PUT' : 'POST'); }
      catch (error) { message(errorText(error), true); }
    }), actionButton('Back to revision', () => showConfigurationRevision(revision)));
  }
  function boundedSetupText(value, fallback = '-') {
    return typeof value === 'string' && value.length > 0 && value.length <= 4096 ? value : fallback;
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
    const storages = Array.isArray(objects.storages) ? objects.storages : [];
    const mediaLibraries = Array.isArray(objects.mediaLibraries) ? objects.mediaLibraries : [];
    const localDestinationIds = new Set(storages.filter(storage =>
      String(storage.type || '').toLowerCase() === 'local').map(storage => String(storage.id)));
    const applicable = mediaLibraries.some(library =>
      localDestinationIds.has(String(library.storageId)));
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
    detailContent.append(text('h3', 'Read-only Local destination precheck'));
    if (!activation.applicable) detailContent.append(text('p',
      'Checked activation requirement: not applicable because this Draft has no Local destination.'));
    else if (!activation.satisfied) detailContent.append(text('p', activation.message, activation.style));
    else detailContent.append(text('p',
      'Checked activation requirement: satisfied by current destination precheck evidence.'));
    if (!evidence) detailContent.append(text('p',
      'Status: not run. This observes one Local destination without changing it.', 'warning'));
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
        field(runList, 'Destination root exists / directory', `${result.destinationRootExists === true ? 'YES' : 'NO'} / ${result.destinationRootIsDirectory === true ? 'YES' : 'NO'}`);
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
        field(firstList, 'Target exists', result.targetExists === true ? 'YES' : 'NO');
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
        field(list, 'Destination root exists / directory', `${result.destinationRootExists === true ? 'YES' : 'NO'} / ${result.destinationRootIsDirectory === true ? 'YES' : 'NO'}`);
        field(list, 'Deepest existing ancestor', boundedSetupText(result.deepestExistingAncestor));
        field(list, 'Directories that would be created', Array.isArray(result.directoriesToCreate) ? result.directoriesToCreate.join(', ') : '-');
        field(list, 'Destination path', boundedSetupText(result.destinationPath));
        field(list, 'Target exists', result.targetExists === true ? 'YES' : 'NO');
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
        detailContent.append(table(['Sample', 'Destination', 'Projected outcome', 'Failure category'],
          result.items.map(item => [
            Number.isFinite(item.index) ? String(item.index) : '-',
            boundedSetupText(item.destinationPath),
            boundedSetupText(item.projectedOutcome),
            boundedSetupText(item.failureCategory)
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
  function setupAndStrategyEvidenceIsCurrent(revision, guided) {
    const local = guided && guided.localSetupCheck;
    const strategy = guided && guided.recognitionStrategyTest;
    return Boolean(local && local.status === 'passed' && setupEvidenceIsCurrent(revision, local) &&
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
      if (data.status === 'draft') actions.append(actionButton('Validate Draft', async () => {
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
        const checked = guided && checkedActivationEvidenceIsCurrent(data, guided);
        actions.append(actionButton(checked ? 'Activate checked revision' :
          (guided ? 'Activate unchecked compatibility revision' : 'Activate revision'),
          () => activateConfigurationRevision(data, Boolean(checked))));
        if (!checked && guided) {
          const destination = destinationPrecheckBlocksCheckedActivation(data, guided);
          const warning = destination ?
            `Activation is available for compatibility, but checked activation is blocked by the Local destination precheck; ${destination.nextAction}.` :
            'Activation is available for compatibility, but the guided safe path requires both a current passed Local setup check and a current completed Recognition Strategy Test.';
          actions.append(text('p', warning, 'warning'));
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
      const row = document.createElement('tr'); values.forEach(value => row.append(text('td', value)));
      if (onRow) { row.tabIndex = 0; row.addEventListener('click', () => onRow(index));
        row.addEventListener('keydown', event => { if (event.key === 'Enter') onRow(index); }); }
      body.append(row);
    }); tableNode.append(head, body); return tableNode;
  }
  function itemId(kind, item) {
    if (kind === 'confirmations') return item.confirmationId || item.confirmation_id;
    if (kind === 'metadata-reviews') return item.review_id;
    if (kind === 'files') return item.fileId || item.file_id;
    return item.review_id;
  }
  async function renderQueue(kind) {
    const query = kind === 'confirmations' ? '?status=pending&limit=100' : '?limit=100';
    const data = await api(`/api/v1/${kind}${query}`); const items = data.items || [];
    clear(content); content.append(text('h2', {
      confirmations: 'Conflict confirmations', 'metadata-reviews': 'Metadata reviews',
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
    clear(content); content.append(text('h2', 'File catalog'));
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
      const data = await api(`/api/v1/files?${parts.join('&')}`);
      const items = data.items || [];
      clear(content); content.append(text('h2', 'File catalog'));
      const rows = items.map(item => [item.fileId || item.file_id, item.path,
        item.scanStatus || item.scan_status, item.updatedAt || item.updated_at]);
      content.append(table(['ID', 'Path', 'Scan status', 'Updated'], rows,
        index => showDetail('files', items[index].fileId || items[index].file_id)));
      content.append(actionButton('Refresh files', loadFiles));
    };
    content.append(form, actionButton('Search files', loadFiles));
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
      item.task_id || '-', item.updated_at]);
    content.append(table(['ID', 'Command', 'Status', 'Authority', 'Task', 'Updated'], rows,
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
      const items = (data.items || []).map(item => [item.item_id, item.status, item.stage,
        item.storage_id, item.source_display, item.destination_storage_id || '-',
        item.destination_path || '-']);
      detailContent.append(text('h3', 'Items'), table(
        ['ID', 'Status', 'Stage', 'Source storage', 'Source', 'Target storage', 'Target'], items));
      if (data.items_truncated) detailContent.append(text('p',
        `Items truncated at ${data.item_limit}.`, 'warning'));
      pageNavigation(detailContent, 'items', data.previous_item_cursor, data.next_item_cursor,
        () => showTask(id, data.previous_item_cursor, resultCursor),
        () => showTask(id, data.next_item_cursor, resultCursor));
      const results = (data.results || []).map(item => [item.result_id, item.status,
        item.recognition_type || '-', item.title || '-', item.operation || '-',
        item.destination_path || '-', item.created_at]);
      detailContent.append(text('h3', 'Results'), table(
        ['ID', 'Status', 'Type', 'Title', 'Operation', 'Destination', 'Created'], results));
      if (data.results_truncated) detailContent.append(text('p',
        `Results truncated at ${data.result_limit}.`, 'warning'));
      pageNavigation(detailContent, 'results', data.previous_result_cursor,
        data.next_result_cursor,
        () => showTask(id, itemCursor, data.previous_result_cursor),
        () => showTask(id, itemCursor, data.next_result_cursor));
      detail.hidden = false;
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
  async function showDetail(kind, id) {
    try {
      const data = await api(`/api/v1/${kind}/${encodeURIComponent(id)}`);
      clear(detailContent); detailContent.append(text('h2', 'Review detail'));
      const list = document.createElement('dl');
      Object.entries(data).filter(([, value]) => !Array.isArray(value) && typeof value !== 'object')
        .forEach(([key, value]) => field(list, key, value)); detailContent.append(list);
      if (kind === 'files') {
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
              item.continuation.status : '-']);
          detailContent.append(text('h3', 'Related reviews'),
            table(['Kind', 'Review', 'Status', 'Task', 'Item', 'Continuation'], rows));
        }
      }
      if (kind === 'confirmations') renderConflictActions(id);
      if (kind === 'metadata-reviews') renderRankActions(kind, id, data.candidates || [],
        'candidateRank', ['rank', 'title', 'year', 'provider_id']);
      if (kind === 'classification-reviews') renderRankActions(kind, id, data.choices || [],
        'choiceRank', ['rank', 'rule_id', 'media_library_id', 'relative_path']);
      detail.hidden = false;
    } catch (error) { message(errorText(error), true); }
  }
  function actionButton(label, action) {
    const button = text('button', label); button.addEventListener('click', action); return button;
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
      else if (view === 'notifications') await renderNotifications();
      else if (view === 'logs') await renderLogs();
      else if (view === 'system') await renderSystem();
      else if (view === 'configuration') await renderConfiguration();
      else if (view === 'files') await renderFiles();
      else await renderQueue(view); message('Connected.');
    } catch (error) { clear(content); message(errorText(error), true); }
  }
  document.getElementById('connect').addEventListener('click', () => {
    token = tokenInput.value; tokenInput.value = ''; load();
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
