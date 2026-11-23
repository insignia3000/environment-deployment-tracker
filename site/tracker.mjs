const MANAGE_URL = 'https://github.com/insignia3000/environment-deployment-tracker/actions/workflows/manage-deployments.yml';
const FIELDS = ['deployedBy', 'branch', 'version', 'environment', 'deployedAt'];

const message = document.getElementById('message');
const rows = document.getElementById('rows');
document.getElementById('timezone').textContent = Intl.DateTimeFormat().resolvedOptions().timeZone;

function renderDeployments(deployments) {
  rows.replaceChildren(...deployments.map(deployment => {
    const row = document.createElement('tr');
    for (const field of FIELDS) {
      const cell = document.createElement('td');
      const value = deployment[field];
      cell.textContent = field === 'deployedAt'
        ? new Date(value).toLocaleString()
        : value || '—';
      row.append(cell);
    }

    const actions = document.createElement('td');
    const link = document.createElement('a');
    link.href = MANAGE_URL;
    link.textContent = 'Manage in GitHub Actions';
    link.setAttribute('aria-label', `Edit or delete ${deployment.environment}/${deployment.branch} in GitHub Actions`);
    actions.append(link);
    row.append(actions);
    return row;
  }));
}

fetch('deployments.json', { cache: 'no-store' }).then(async response => {
  if (!response.ok) throw new Error(`Could not load the published file (HTTP ${response.status}).`);
  const deployments = await response.json();
  if (!Array.isArray(deployments)) throw new Error('Deployment data must be an array.');
  renderDeployments(deployments);
  message.textContent = deployments.length
    ? 'Read-only view. Changes are made through GitHub Actions.'
    : 'No deployments yet. Add one through GitHub Actions.';
}).catch(error => {
  rows.replaceChildren();
  message.textContent = `Could not load deployments: ${error.message} Reload to retry.`;
  message.classList.add('error');
});
