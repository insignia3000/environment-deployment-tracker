const API = 'https://api.github.com/repos/insignia3000/environment-deployment-tracker/contents/site/deployments.json';
const STATUSES = ['success', 'failed', 'in-progress'];
const FIELDS = ['environment', 'service', 'version', 'status', 'deployedAt', 'deployedBy'];
const key = item => JSON.stringify([item.environment, item.service]);

export function validateData(data) {
  if (!Array.isArray(data)) throw new Error('Deployment data must be an array.');
  const keys = new Set();
  for (const item of data) {
    if (!item || typeof item !== 'object' || Array.isArray(item)) {
      throw new Error('Each deployment must be an object.');
    }
    for (const field of ['environment', 'service', 'version']) {
      if (typeof item[field] !== 'string' || !item[field].trim() || item[field].length > 120) {
        throw new Error(`${field} must contain between 1 and 120 characters.`);
      }
    }
    if (!STATUSES.includes(item.status)) throw new Error('Select a valid deployment status.');
    if (typeof item.deployedAt !== 'string' || !Number.isFinite(Date.parse(item.deployedAt))) {
      throw new Error('Enter a valid deployment time.');
    }
    if (item.deployedBy !== undefined && (typeof item.deployedBy !== 'string' || item.deployedBy.length > 120)) {
      throw new Error('Deployed by must be text of at most 120 characters.');
    }
    if (keys.has(key(item))) throw new Error('An item with that environment and service already exists.');
    keys.add(key(item));
  }
  return data;
}

export function mergeDeployment(latest, original, draft) {
  validateData(latest);
  validateData([draft]);
  if (!draft.deployedBy?.trim()) throw new Error('Enter who deployed this item.');
  if (!original) return validateData([...latest, draft]);
  const index = latest.findIndex(item => key(item) === key(original));
  const snapshot = item => JSON.stringify(Object.keys(item).sort().map(field => [field, item[field]]));
  if (index === -1 || snapshot(latest[index]) !== snapshot(original)) {
    throw new Error('This item changed on GitHub. Copy your edits, reload, and review the latest values before saving.');
  }
  return validateData(latest.map((item, i) => i === index ? { ...item, ...draft } : item));
}

export function encodeContent(value) {
  return btoa(Array.from(new TextEncoder().encode(value), byte => String.fromCharCode(byte)).join(''));
}

export function decodeContent(value) {
  return new TextDecoder('utf-8', { fatal: true }).decode(
    Uint8Array.from(atob(value.replace(/\s/g, '')), character => character.charCodeAt(0))
  );
}

async function request(token, options, fetcher) {
  let response;
  try {
    response = await fetcher(API + (options.method === 'PUT' ? '' : '?ref=main'), {
      ...options,
      cache: 'no-store',
      credentials: 'omit',
      redirect: 'error',
      headers: {
        Accept: 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(options.method === 'PUT' ? { 'Content-Type': 'application/json' } : {})
      }
    });
  } catch {
    throw new Error('Cannot reach GitHub. If saving, the result is uncertain: reload and check the item before retrying.');
  }
  if (!response.ok) {
    const messages = {
      401: 'GitHub rejected the token. Check its value and expiry.',
      403: 'GitHub denied access or the API rate limit was reached. Check token permissions, repository access, and branch rules.',
      404: 'GitHub could not find the deployment file. Check repository access and token repository selection.',
      409: 'The file changed while saving. Your edits are still here; try Save again to check for conflicts.',
      422: 'GitHub rejected the update. Reload to check the latest data and check repository branch rules.'
    };
    throw new Error(messages[response.status] || `GitHub request failed (HTTP ${response.status}).`);
  }
  return response.json();
}

export async function readDeployments(token = '', fetcher = fetch) {
  const file = await request(token, {}, fetcher);
  if (file.encoding !== 'base64' || typeof file.content !== 'string' || typeof file.sha !== 'string') {
    throw new Error('GitHub returned an unsupported file response.');
  }
  return { data: validateData(JSON.parse(decodeContent(file.content))), sha: file.sha };
}

export async function saveDeployment(token, original, draft, fetcher = fetch) {
  if (!token) throw new Error('Enable saving with a GitHub token first.');
  const { data, sha } = await readDeployments(token, fetcher);
  const updated = mergeDeployment(data, original, draft);
  const result = await request(token, {
    method: 'PUT',
    body: JSON.stringify({
      message: original ? 'Update deployment item' : 'Add deployment item',
      branch: 'main',
      sha,
      content: encodeContent(JSON.stringify(updated, null, 2) + '\n')
    })
  }, fetcher);
  if (!result.commit?.sha) {
    throw new Error('GitHub returned an unexpected save response. Reload and verify the item before retrying.');
  }
  return updated.find(item => key(item) === key(draft));
}

export function localTime(iso) {
  const date = new Date(iso);
  const pad = (value, length = 2) => String(value).padStart(length, '0');
  return `${pad(date.getFullYear(), 4)}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}.${pad(date.getMilliseconds(), 3)}`;
}

function startEditor() {
  let token = '';
  let saving = false;
  let nextId = 0;
  const dirtyForms = new Set();
  const rows = document.getElementById('rows');
  const editor = document.getElementById('editor');
  const message = document.getElementById('message');
  const authStatus = document.getElementById('auth-status');
  const tokenInput = document.getElementById('token');
  const showMessage = (text, error = false) => {
    message.textContent = text;
    message.classList.toggle('error', error);
  };
  document.getElementById('timezone').textContent = Intl.DateTimeFormat().resolvedOptions().timeZone;
  document.getElementById('auth-form').addEventListener('submit', event => {
    event.preventDefault();
    token = tokenInput.value.trim();
    tokenInput.value = '';
    authStatus.textContent = token
      ? 'Token loaded in memory. Write access will be checked when saving.'
      : 'Read-only until a token is supplied.';
  });
  document.getElementById('clear-token').addEventListener('click', () => {
    token = '';
    tokenInput.value = '';
    authStatus.textContent = 'Token cleared. Read-only until a token is supplied.';
  });
  window.addEventListener('beforeunload', event => {
    if (dirtyForms.size || saving) {
      event.preventDefault();
      event.returnValue = '';
    }
  });

  function createRow(original) {
    const tr = document.createElement('tr');
    const form = document.createElement('form');
    form.id = `deployment-${++nextId}`;
    const values = original || {
      environment: '', service: '', version: '', status: 'success',
      deployedAt: new Date().toISOString(), deployedBy: ''
    };
    const controls = {};
    for (const field of FIELDS) {
      const td = document.createElement('td');
      const control = document.createElement(field === 'status' ? 'select' : 'input');
      if (field === 'status') {
        for (const status of STATUSES) {
          const option = document.createElement('option');
          option.value = status;
          option.textContent = status;
          control.append(option);
        }
      } else {
        control.type = field === 'deployedAt' ? 'datetime-local' : 'text';
        if (field === 'deployedAt') {
          control.step = '0.001';
          control.min = '0001-01-01T00:00';
          control.max = '9999-12-31T23:59:59.999';
        } else {
          control.maxLength = 120;
        }
      }
      control.value = field === 'deployedAt' ? localTime(values[field]) : values[field] || '';
      control.required = true;
      control.name = field;
      control.setAttribute('form', form.id);
      const label = { deployedAt: 'Deployed time', deployedBy: 'Deployed by' }[field] || field;
      control.setAttribute('aria-label', `${label} (${original ? `${original.environment}/${original.service}` : 'new deployment'})`);
      control.addEventListener('input', () => dirtyForms.add(form));
      control.addEventListener('change', () => dirtyForms.add(form));
      controls[field] = control;
      td.append(control);
      tr.append(td);
    }
    const actions = document.createElement('td');
    const save = document.createElement('button');
    save.type = 'submit';
    save.textContent = 'Save';
    const cancel = document.createElement('button');
    cancel.type = 'button';
    cancel.textContent = original ? 'Reset' : 'Cancel';
    cancel.addEventListener('click', () => {
      dirtyForms.delete(form);
      if (original) tr.replaceWith(createRow(original));
      else tr.remove();
    });
    form.append(save, cancel);
    actions.append(form);
    tr.append(actions);
    form.addEventListener('submit', async event => {
      event.preventDefault();
      if (saving) return;
      const draft = Object.fromEntries(FIELDS.map(field => [field, controls[field].value.trim()]));
      try {
        if (!draft.deployedAt) throw new Error('Enter a deployment time.');
        draft.deployedAt = new Date(draft.deployedAt).toISOString();
        saving = true;
        editor.disabled = true;
        showMessage('Saving to GitHub...');
        const saved = await saveDeployment(token, original, draft);
        dirtyForms.delete(form);
        const replacement = createRow(saved);
        tr.replaceWith(replacement);
        replacement.querySelector('button').focus();
        showMessage('Saved to GitHub. Other viewers will see updates after Pages finishes and they reload.');
      } catch (error) {
        showMessage(error.message, true);
      } finally {
        saving = false;
        editor.disabled = false;
      }
    });
    return tr;
  }

  document.getElementById('add-deployment').addEventListener('click', () => {
    const row = createRow(null);
    rows.append(row);
    dirtyForms.add(row.querySelector('form'));
    row.querySelector('input').focus();
  });
  fetch('deployments.json', { cache: 'no-store' }).then(async response => {
    if (!response.ok) throw new Error(`Could not load the published file (HTTP ${response.status}).`);
    return validateData(await response.json());
  }).then(data => {
    rows.replaceChildren(...data.map(createRow));
    editor.disabled = false;
    showMessage(data.length ? 'Ready. Edit fields and save a row.' : 'No deployments yet. Add a new deployment to get started.');
  }).catch(error => {
    rows.replaceChildren();
    showMessage(`Could not load deployments: ${error.message} Reload to retry.`, true);
  });
}

if (typeof document !== 'undefined') startEditor();
