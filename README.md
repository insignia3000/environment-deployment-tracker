# Environment Deployment Tracker

A public, read-only GitHub Pages site showing deployments to environments `dev1` through `dev6`.
The page does not accept or store GitHub tokens. Trusted repository writers make changes with
GitHub Actions, where GitHub authenticates the user and records the workflow actor.

## Managing deployments

1. Open the [tracker](https://insignia3000.github.io/environment-deployment-tracker/).
2. Select **Add deployment in GitHub Actions** or **Manage in GitHub Actions** on a row.
   The workflow requires write access to this repository. If you do not have it, ask a repository
   maintainer to make the change.
3. Choose **add**, **update**, or **delete**, and enter the environment and branch. For update and
   delete, these must identify the existing row exactly. Update can change the version, branch, or
   deployment time. To change the environment, delete the row and add it again.
4. For delete, type `DELETE` to confirm. When adding, the signed-in GitHub username is recorded
   as **Deployed by**. When updating a deployment time, the username is recorded as the deployer;
   metadata-only edits preserve the existing deployer.
5. Submit the workflow. It commits the change as GitHub Actions, includes the authenticated user
   in the commit message, and republishes the page. Reload the tracker after the Pages workflow
   finishes. GitHub allows one pending run in a concurrency group; if multiple changes are
   submitted during another run, check that each workflow completes rather than being replaced.

The workflow accepts an optional ISO 8601 deployment time with a timezone (for example,
`2026-11-24T09:00:00+11:00`). When adding, leaving it blank uses the current UTC time. When
updating, leaving it blank preserves the current deployment time.

Changes made with the separate **Record deployment** workflow also run as the signed-in user and
update the deployment time and deployer for an existing environment/branch pair.

## Security and visibility

The repository and tracker are public. Deployment details, authenticated usernames, commits, and
their history are visible to everyone. The Actions workflow is limited to repository writers,
uses GitHub's built-in token only on the runner, validates the requested change, and does not
accept credentials from the web page. Do not enter sensitive data. This tracker records
deployment information; it does not deploy or verify an application.

## Development and publishing

The page is served from `site/`. Pushes to `main` run `.github/workflows/pages.yml`.

Run the checks locally:

```sh
python3 -m unittest discover -s scripts -p 'test_*.py'
node --check site/tracker.mjs
```

Preview the read-only page with `python3 -m http.server --directory site`.
