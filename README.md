# environment-deployment-tracker

Proof of concept: a static page showing what version is deployed to each environment.

- Page source: `site/` (edit `site/deployments.json` to update the data)
- Published to GitHub Pages by `.github/workflows/pages.yml` on every push to `main`

## Inline editing and new deployments

1. Open the [tracker](https://insignia3000.github.io/environment-deployment-tracker/) and expand **Enable saving with a GitHub token**.
2. Create a short-lived [fine-grained personal access token](https://github.com/settings/personal-access-tokens/new).
   Select only `insignia3000/environment-deployment-tracker` and grant **Contents: Read and write**.
   The token's account must have repository write access, and branch rules must permit direct commits to `main`.
3. Enter it in the password field and select **Use token**. It stays in memory only, not cookies or browser storage.
   Refreshing clears it. **Clear token** removes it when finished; revoke it in GitHub settings if necessary.
4. Click the table fields to edit **Deployed by**, **Branch**, **Version**, **Environment**, or **Deployed**.
   The environment selector offers only `dev1`, `dev2`, `dev3`, `dev4`, `dev5`, and `dev6`.
   Times display in your browser's local timezone and are stored as UTC.
   The first column holds the deploying person's name, entered manually and not verified;
   Branch holds the branch used for the deployment. There is no separate status or service field.
5. To create an item, select **New deployment**, fill in all fields, and choose **Save**.
   Environment/branch pairs must be unique. The same branch can appear in different environments.
6. Each row's **Save** asks for the name of the person saving, then **Confirm save** commits that
   row to `site/deployments.json`. The name is recorded in the commit message (`Saved by: NAME`)
   for both new and existing rows; it does not replace the **Deployed by** field.
   **Back** cancels the confirmation without losing edits. **Cancel** removes an unsaved new row.
   Saving one row preserves drafts in other rows.
7. **Reset** and **Delete** first ask for the name of the person performing the action. **Reset**
   discards that row's unsaved edits (nothing is committed). **Delete** removes the saved row from
   GitHub and records the name in the commit message (`Deleted by: NAME`), so it appears in the
   repository history.

The bundled rows are sample data for `dev1` through `dev3`, with `main` as a placeholder
branch and no recorded deployer. Replace these with actual details before saving.

The page loads the published JSON without using the GitHub API. Saved items appear
immediately in your edited row; other viewers must wait for the Pages publishing
workflow to finish and then reload. Each token-authenticated commit triggers that workflow.
Saving fetches the latest file SHA directly from GitHub, preserves
other items, and refuses to overwrite an item changed by someone else. If there is a
conflict, copy your edits and reload to review the latest values. Failed saves retain
your inputs. An uncertain network result requires checking the saved data before retrying,
particularly when adding a new item.

GitHub API rate limits apply when saving. The token is sent
only to `api.github.com`; no backend or third-party scripts are used. Only enter the token
in the dedicated password field, never in the table or chat. Any script executing on the
page can access in-memory credentials: this is a POC for trusted repository maintainers,
not a production authentication system.

**This is a public POC.** Saved deployment details, manually entered names, and previous
values in Git history are public. Do not enter sensitive data. Recording a deployment
does not deploy an application or verify who actually deployed it.

## Alternative: GitHub Actions form

The **Record deployment** workflow remains available in Actions. Select `main` as the workflow
branch, choose an environment from `dev1` through `dev6`, enter the deployed branch from an
existing environment/branch pair, and optionally supply an ISO 8601 time with a timezone
(blank means now). It records the submitting GitHub username and changes only the deployment
time and the first column's deployed-by field. It calls Pages explicitly because `GITHUB_TOKEN` pushes do not
start push workflows. Recording runs are serialized, but GitHub can replace an older pending
run with a newer one; check that your run finished.

## Local checks

Run `python3 -m unittest discover -s scripts -p 'test_*.py'`.
Run `node --test scripts/tracker.test.mjs` with Node.js 20 or later.
Preview with `python3 -m http.server --directory site` (saving with a real token changes
the public repository).
