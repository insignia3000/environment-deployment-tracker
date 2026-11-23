import os
from datetime import datetime, timezone
import json
from pathlib import Path
import sys


ENVIRONMENTS = ("dev1", "dev2", "dev3", "dev4", "dev5", "dev6")


def _text(value, label, required=True):
    if not isinstance(value, str):
        raise ValueError(f"{label} must be text.")
    value = value.strip()
    if required and not value:
        raise ValueError(f"{label} is required.")
    if len(value) > 120 or any(character in value for character in ("\n", "\r")):
        raise ValueError(f"{label} must be a single line of at most 120 characters.")
    return value


def _utc_timestamp(value):
    value = _text(value, "Deployment time", required=False)
    if not value:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    try:
        timestamp = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("Deployment time must be an ISO 8601 datetime with a timezone.") from error
    if timestamp.tzinfo is None:
        raise ValueError("Deployment time must include a timezone, such as Z or +11:00.")
    return timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _validate_deployments(deployments):
    if not isinstance(deployments, list):
        raise ValueError("Deployment data must be an array.")
    keys = set()
    for entry in deployments:
        if not isinstance(entry, dict):
            raise ValueError("Each deployment must be an object.")
        if entry.get("environment") not in ENVIRONMENTS:
            raise ValueError("Deployment environment must be dev1 through dev6.")
        for field in ("branch", "version"):
            _text(entry.get(field), field)
        if entry.get("deployedBy") is not None:
            _text(entry["deployedBy"], "Deployed by", required=False)
        _utc_timestamp(_text(entry.get("deployedAt"), "Deployment time"))
        key = (entry["environment"], entry["branch"])
        if key in keys:
            raise ValueError("Deployment environment and branch pairs must be unique.")
        keys.add(key)


def manage_deployment(
    deployments, operation, environment, branch, version, new_branch, deployed_at,
    confirm_delete, actor
):
    _validate_deployments(deployments)
    actor = _text(actor, "GitHub actor")
    deployed_at = _text(deployed_at, "Deployment time", required=False)
    confirm_delete = _text(confirm_delete, "Delete confirmation", required=False)
    if operation not in ("add", "update", "delete"):
        raise ValueError("Operation must be add, update, or delete.")
    if environment not in ENVIRONMENTS:
        raise ValueError("Environment must be dev1 through dev6.")
    branch = _text(branch, "Branch")
    updated = [entry.copy() for entry in deployments]

    if operation == "add":
        version = _text(version, "Version")
        key = (environment, branch)
        if any((entry["environment"], entry["branch"]) == key for entry in updated):
            raise ValueError("A deployment with that environment and branch already exists.")
        updated.append({
            "deployedBy": actor,
            "branch": branch,
            "version": version,
            "environment": environment,
            "deployedAt": _utc_timestamp(deployed_at),
        })
        return updated

    matches = [
        index for index, entry in enumerate(updated)
        if entry["environment"] == environment and entry["branch"] == branch
    ]
    if len(matches) != 1:
        raise ValueError("Environment and branch must match exactly one existing deployment.")
    index = matches[0]

    if operation == "delete":
        if confirm_delete != "DELETE":
            raise ValueError('To confirm deletion, enter "DELETE".')
        return updated[:index] + updated[index + 1:]

    current = updated[index]
    next_branch = _text(new_branch, "New branch", required=False) or branch
    next_version = _text(version, "Version", required=False) or current["version"]
    next_time = _utc_timestamp(deployed_at) if deployed_at.strip() else current.get("deployedAt")
    next_deployer = actor if deployed_at.strip() else current.get("deployedBy", "")
    if (next_branch, next_version, next_time) == (
        current["branch"], current["version"], current.get("deployedAt")
    ) and next_deployer == current.get("deployedBy", ""):
        raise ValueError("Provide a new branch, version, or deployment time to update.")
    if any(
        entry["environment"] == environment and entry["branch"] == next_branch
        for other_index, entry in enumerate(updated) if other_index != index
    ):
        raise ValueError("A deployment with that environment and branch already exists.")
    current.update({
        "branch": next_branch,
        "version": next_version,
        "deployedAt": next_time,
        "deployedBy": next_deployer,
    })
    return updated


def main():
    path = Path("site/deployments.json")
    try:
        updated = manage_deployment(
            json.loads(path.read_text(encoding="utf-8")),
            os.environ["DEPLOYMENT_OPERATION"],
            os.environ["DEPLOYMENT_ENVIRONMENT"],
            os.environ.get("DEPLOYMENT_BRANCH", ""),
            os.environ.get("DEPLOYMENT_VERSION", ""),
            os.environ.get("DEPLOYMENT_NEW_BRANCH", ""),
            os.environ.get("DEPLOYED_AT", ""),
            os.environ.get("CONFIRM_DELETE", ""),
            os.environ["GITHUB_ACTOR"],
        )
        path.write_text(json.dumps(updated, indent=2) + "\n", encoding="utf-8")
    except (ValueError, OSError, KeyError) as error:
        print(f"Unable to manage deployment: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
