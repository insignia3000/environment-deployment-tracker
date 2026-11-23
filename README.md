# environment-deployment-tracker

Proof of concept: a static page showing what version is deployed to each environment.

- Page source: `site/` (edit `site/deployments.json` to update the data)
- Published to GitHub Pages by `.github/workflows/pages.yml` on every push to `main`

## Record a deployment

1. Click **Record deployment** on the [tracker](https://insignia3000.github.io/environment-deployment-tracker/).
2. Sign in to GitHub with repository write access, select **Run workflow**, and keep the branch set to `main`.
3. Choose the environment and enter the service shown in the tracker. Row buttons open the same form; GitHub does not prefill the row selection.
4. Optionally enter an ISO 8601 deployment time including a timezone, such as `2026-11-24T09:00:00+11:00` or `2026-11-23T22:00:00Z`. Leave blank to use the workflow's recording time.
5. Run the workflow and wait for its recording and publishing jobs to finish, then reload the tracker.

The workflow updates only the selected row's deployment time and `deployedBy`
(the GitHub username that submitted the workflow). Existing sample rows show
**Not recorded** until updated. Version and status remain unchanged. This records
a deployment; it does not deploy the application itself or verify who performed
the actual deployment.

Changes are committed to `site/deployments.json`, then the Pages workflow is
called explicitly: pushes made with `GITHUB_TOKEN` do not start push workflows.
Invalid times and unknown or ambiguous environment/service pairs fail without
saving changes. Repository rules must allow GitHub Actions to push to `main`.
Concurrent recording runs are serialized; GitHub may replace an older pending
run with a newer one, so check that your run completed.

**This is a public POC.** Deployment details, GitHub usernames, and previous values
in Git history are public. Do not enter sensitive data. This requires no tokens
or credentials in the browser.

## Local checks

Run `python3 -m unittest discover -s scripts -p 'test_*.py'`.
