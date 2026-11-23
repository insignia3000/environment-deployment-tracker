import copy
import contextlib
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from manage_deployments import main, manage_deployment


class ManageDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.deployments = [
            {
                "deployedBy": "octocat",
                "branch": "main",
                "version": "1.4.0",
                "environment": "dev1",
                "deployedAt": "2026-11-23T01:00:00Z",
            },
            {
                "deployedBy": "hubot",
                "branch": "main",
                "version": "1.3.2",
                "environment": "dev2",
                "deployedAt": "2026-11-20T04:30:00Z",
            },
        ]

    def manage(self, operation, **overrides):
        arguments = {
            "deployments": self.deployments,
            "operation": operation,
            "environment": "dev1",
            "branch": "main",
            "version": "",
            "new_branch": "",
            "deployed_at": "",
            "confirm_delete": "",
            "actor": "maintainer",
        }
        arguments.update(overrides)
        return manage_deployment(**arguments)

    def test_add_records_github_actor_and_preserves_existing_rows(self):
        result = self.manage(
            "add", environment="dev3", branch="feature/add", version="2.0.0",
            deployed_at="2026-11-24T09:00:00+11:00",
        )
        self.assertEqual(result[:2], self.deployments)
        self.assertEqual(result[2], {
            "deployedBy": "maintainer",
            "branch": "feature/add",
            "version": "2.0.0",
            "environment": "dev3",
            "deployedAt": "2026-11-23T22:00:00Z",
        })

    def test_add_defaults_time_and_requires_unique_key_and_version(self):
        before = datetime.now(timezone.utc)
        result = self.manage("add", environment="dev3", branch="feature/add", version="2")
        timestamp = datetime.fromisoformat(result[2]["deployedAt"].replace("Z", "+00:00"))
        self.assertLessEqual(before, timestamp)
        self.assertLessEqual(timestamp, datetime.now(timezone.utc))
        for overrides in (
            {"environment": "dev1", "branch": "main", "version": "2"},
            {"environment": "dev3", "branch": "feature/add", "version": ""},
        ):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                self.manage("add", **overrides)

    def test_update_changes_requested_fields_and_preserves_deployer_without_new_deployment_time(self):
        result = self.manage("update", version="2.0.0", new_branch="release/2")
        self.assertEqual(result[0]["version"], "2.0.0")
        self.assertEqual(result[0]["branch"], "release/2")
        self.assertEqual(result[0]["deployedBy"], "octocat")
        self.assertEqual(result[0]["deployedAt"], self.deployments[0]["deployedAt"])
        self.assertEqual(result[1], self.deployments[1])

    def test_update_with_deployment_time_records_authenticated_actor(self):
        result = self.manage("update", deployed_at="2026-11-24T09:00:00+11:00")
        self.assertEqual(result[0]["deployedAt"], "2026-11-23T22:00:00Z")
        self.assertEqual(result[0]["deployedBy"], "maintainer")

    def test_update_rejects_noop_duplicate_branch_and_bad_time(self):
        original = copy.deepcopy(self.deployments)
        for overrides in (
            {},
            {"new_branch": "main", "environment": "dev2"},
            {"new_branch": "invalid", "deployed_at": "yesterday"},
        ):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                self.manage("update", **overrides)
            self.assertEqual(self.deployments, original)

    def test_delete_requires_explicit_confirmation_and_removes_only_selected_row(self):
        with self.assertRaisesRegex(ValueError, "enter"):
            self.manage("delete")
        result = self.manage("delete", confirm_delete="DELETE")
        self.assertEqual(result, [self.deployments[1]])
        self.assertEqual(self.deployments[0]["environment"], "dev1")

    def test_invalid_operation_target_and_actor_are_rejected(self):
        for overrides in (
            {"operation": "other"},
            {"environment": "prod"},
            {"branch": "unknown"},
            {"actor": ""},
            {"actor": "someone\nelse"},
        ):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                operation = overrides.get("operation", "update")
                arguments = {key: value for key, value in overrides.items() if key != "operation"}
                self.manage(operation, **arguments)

    def test_existing_data_must_be_valid_and_unique(self):
        invalid = copy.deepcopy(self.deployments)
        invalid.append(copy.deepcopy(invalid[0]))
        with self.assertRaisesRegex(ValueError, "unique"):
            self.manage("update", deployments=invalid, version="2")
        invalid = copy.deepcopy(self.deployments)
        invalid[0]["deployedAt"] = ""
        with self.assertRaises(ValueError):
            self.manage("update", deployments=invalid, version="2")

    def test_command_saves_success_and_preserves_file_on_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "deployments.json"
            path.write_text(json.dumps(self.deployments), encoding="utf-8")
            inputs = {
                "DEPLOYMENT_OPERATION": "add",
                "DEPLOYMENT_ENVIRONMENT": "dev3",
                "DEPLOYMENT_BRANCH": "feature/cli",
                "DEPLOYMENT_VERSION": "2.0.0",
                "DEPLOYMENT_NEW_BRANCH": "",
                "DEPLOYED_AT": "",
                "CONFIRM_DELETE": "",
                "GITHUB_ACTOR": "maintainer",
            }
            with patch("manage_deployments.Path", return_value=path), patch.dict(os.environ, inputs):
                self.assertEqual(main(), 0)
                saved = path.read_text(encoding="utf-8")
                self.assertEqual(json.loads(saved)[-1]["deployedBy"], "maintainer")
                os.environ["DEPLOYMENT_OPERATION"] = "delete"
                errors = io.StringIO()
                with contextlib.redirect_stderr(errors):
                    self.assertEqual(main(), 1)
                self.assertIn("Unable to manage deployment:", errors.getvalue())
                self.assertEqual(path.read_text(encoding="utf-8"), saved)


if __name__ == "__main__":
    unittest.main()
