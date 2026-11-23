import json
import os
from pathlib import Path
import sys
from datetime import datetime, timezone


def record_deployment(deployments, environment, service, deployed_at, actor):
    if not isinstance(deployments, list) or not all(
        isinstance(entry, dict) for entry in deployments
    ):
        raise ValueError("Deployment data must be an array of objects.")
    if not actor.strip():
        raise ValueError("A GitHub actor is required.")
    matches = [
        entry for entry in deployments
        if entry.get("environment") == environment and entry.get("service") == service
    ]
    if len(matches) != 1:
        raise ValueError("Environment and service must match exactly one existing deployment.")

    if deployed_at.strip():
        try:
            timestamp = datetime.fromisoformat(deployed_at.strip().replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError("Deployment time must be an ISO 8601 datetime with a timezone.") from error
        if timestamp.tzinfo is None:
            raise ValueError("Deployment time must include a timezone, such as Z or +11:00.")
    else:
        timestamp = datetime.now(timezone.utc)

    matches[0]["deployedAt"] = timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    matches[0]["deployedBy"] = actor
    return deployments


def main():
    path = Path("site/deployments.json")
    try:
        updated = record_deployment(
            json.loads(path.read_text(encoding="utf-8")),
            os.environ["DEPLOYMENT_ENVIRONMENT"],
            os.environ["DEPLOYMENT_SERVICE"],
            os.environ.get("DEPLOYED_AT", ""),
            os.environ["GITHUB_ACTOR"],
        )
        path.write_text(json.dumps(updated, indent=2) + "\n", encoding="utf-8")
    except (ValueError, OSError, KeyError) as error:
        print(f"Unable to record deployment: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
