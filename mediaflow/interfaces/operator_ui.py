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
    <button data-view="jobs">Jobs</button>
    <button data-view="schedules">Schedules</button>
    <button data-view="notifications">Notifications</button>
    <button data-view="logs">Logs</button>
    <button data-view="confirmations">Conflicts</button>
    <button data-view="metadata-reviews">Metadata</button>
    <button data-view="classification-reviews">Classification</button>
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
  async function api(path, options = {}) {
    if (!token) throw new Error('API token is required');
    const headers = {'Authorization': `Bearer ${token}`};
    if (options.body) headers['Content-Type'] = 'application/json';
    const response = await fetch(path, {...options, headers});
    const document = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error((document.error && document.error.message) ||
      `Request failed (${response.status})`);
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
  async function renderObservability(kind, cursor = null) {
    const suffix = cursor ? `&cursor=${encodeURIComponent(cursor)}` : '';
    const data = await api(`/api/v1/${kind}?limit=100${suffix}`); const items = data.items || [];
    clear(content); content.append(text('h2', kind === 'tasks' ? 'Tasks' : 'Automation jobs'));
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
    } catch (error) { message(error.message, true); }
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
    } catch (error) { message(error.message, true); }
  }
  async function showJob(id) {
    try {
      const data = await api(`/api/v1/jobs/${encodeURIComponent(id)}`);
      clear(detailContent); detailContent.append(text('h2', 'Automation job detail'),
        scalarDetails(data));
      if (data.task_id) detailContent.append(actionButton('Open linked task', () => showTask(data.task_id)));
      detail.hidden = false;
    } catch (error) { message(error.message, true); }
  }
  async function showDetail(kind, id) {
    try {
      const data = await api(`/api/v1/${kind}/${encodeURIComponent(id)}`);
      clear(detailContent); detailContent.append(text('h2', 'Review detail'));
      const list = document.createElement('dl');
      Object.entries(data).filter(([, value]) => !Array.isArray(value) && typeof value !== 'object')
        .forEach(([key, value]) => field(list, key, value)); detailContent.append(list);
      if (kind === 'confirmations') renderConflictActions(id);
      if (kind === 'metadata-reviews') renderRankActions(kind, id, data.candidates || [],
        'candidateRank', ['rank', 'title', 'year', 'provider_id']);
      if (kind === 'classification-reviews') renderRankActions(kind, id, data.choices || [],
        'choiceRank', ['rank', 'rule_id', 'media_library_id', 'relative_path']);
      detail.hidden = false;
    } catch (error) { message(error.message, true); }
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
    } catch (error) { message(error.message, true); }
  }
  async function load() {
    try { message('Loading...');
      if (view === 'dashboard') renderDashboard(await api('/api/v1/dashboard?recentLimit=10'));
      else if (view === 'tasks' || view === 'jobs') await renderObservability(view);
      else if (view === 'schedules') await renderSchedules();
      else if (view === 'notifications') await renderNotifications();
      else if (view === 'logs') await renderLogs();
      else await renderQueue(view); message('Connected.');
    } catch (error) { clear(content); message(error.message, true); }
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
