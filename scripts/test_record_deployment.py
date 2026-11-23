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

from record_deployment import main, record_deployment


class RecordDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.deployments = [
            {"environment": "dev1", "branch": "main", "version": "1.4.0"},
            {"environment": "dev2", "branch": "main", "version": "1.3.1"},
        ]

    def test_records_actor_and_normalizes_time_without_changing_other_fields(self):
        untouched = copy.deepcopy(self.deployments[1])
        result = record_deployment(
            self.deployments, "dev1", "main", "2026-11-24T09:00:00+11:00", "octocat"
        )
        self.assertEqual(result[0]["deployedAt"], "2026-11-23T22:00:00Z")
        self.assertEqual(result[0]["deployedBy"], "octocat")
        self.assertEqual(result[0]["version"], "1.4.0")
        self.assertEqual(result[0]["environment"], "dev1")
        self.assertEqual(result[0]["branch"], "main")
        self.assertEqual(result[1], untouched)

    def test_empty_time_uses_current_utc_time_and_replaces_previous_actor(self):
        self.deployments[0]["deployedBy"] = "previous-user"
        before = datetime.now(timezone.utc)
        result = record_deployment(self.deployments, "dev1", "main", "", "octocat")
        timestamp = datetime.fromisoformat(result[0]["deployedAt"].replace("Z", "+00:00"))
        self.assertLessEqual(before, timestamp)
        self.assertLessEqual(timestamp, datetime.now(timezone.utc))
        self.assertEqual(result[0]["deployedBy"], "octocat")

    def test_accepts_utc_suffix(self):
        result = record_deployment(
            self.deployments, "dev1", "main", "2026-11-24T09:00:00Z", "octocat"
        )
        self.assertEqual(result[0]["deployedAt"], "2026-11-24T09:00:00Z")

    def test_invalid_times_do_not_mutate_data(self):
        original = copy.deepcopy(self.deployments)
        for timestamp in ("yesterday", "2026-11-24", "2026-11-24T09:00:00"):
            with self.subTest(timestamp=timestamp), self.assertRaises(ValueError):
                record_deployment(self.deployments, "dev1", "main", timestamp, "octocat")
            self.assertEqual(self.deployments, original)

    def test_rejects_missing_or_ambiguous_target(self):
        for environment, branch in (("dev3", "main"), ("dev1", "feature/unknown")):
            with self.subTest(environment=environment, branch=branch), self.assertRaises(ValueError):
                record_deployment(self.deployments, environment, branch, "", "octocat")
        self.deployments.append(copy.deepcopy(self.deployments[0]))
        with self.assertRaises(ValueError):
            record_deployment(self.deployments, "dev1", "main", "", "octocat")

    def test_records_the_selected_branch_without_changing_other_branches(self):
        self.deployments.append({**self.deployments[0], "branch": "feature/change"})
        original = copy.deepcopy(self.deployments)
        result = record_deployment(self.deployments, "dev1", "feature/change", "", "octocat")
        self.assertEqual(result[:2], original[:2])
        self.assertEqual(result[2]["deployedBy"], "octocat")
        self.assertEqual(result[2]["branch"], "feature/change")

    def test_records_all_six_environments_and_rejects_other_names(self):
        for environment in ("dev1", "dev2", "dev3", "dev4", "dev5", "dev6"):
            with self.subTest(environment=environment):
                data = [{**self.deployments[0], "environment": environment}]
                result = record_deployment(data, environment, "main", "", "octocat")
                self.assertEqual(result[0]["deployedBy"], "octocat")
        original = copy.deepcopy(self.deployments)
        for environment in ("dev0", "dev7", "dev", "staging", "prod", "success", ""):
            with self.subTest(environment=environment), self.assertRaisesRegex(ValueError, "Environment must be"):
                record_deployment(self.deployments, environment, "main", "", "octocat")
            self.assertEqual(self.deployments, original)

    def test_rejects_malformed_data_and_missing_actor(self):
        for data in ({}, [None]):
            with self.subTest(data=data), self.assertRaises(ValueError):
                record_deployment(data, "dev1", "main", "", "octocat")
        with self.assertRaises(ValueError):
            record_deployment(self.deployments, "dev1", "main", "", " ")

    def test_command_saves_success_and_preserves_file_on_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "deployments.json"
            path.write_text(json.dumps(self.deployments), encoding="utf-8")
            inputs = {
                "DEPLOYMENT_ENVIRONMENT": "dev1",
                "DEPLOYMENT_BRANCH": "main",
                "DEPLOYED_AT": "2026-11-24T09:00:00Z",
                "GITHUB_ACTOR": "octocat",
            }
            with patch("record_deployment.Path", return_value=path), patch.dict(os.environ, inputs):
                self.assertEqual(main(), 0)
                saved = path.read_text(encoding="utf-8")
                self.assertEqual(json.loads(saved)[0]["deployedBy"], "octocat")
                os.environ["DEPLOYED_AT"] = "invalid"
                errors = io.StringIO()
                with contextlib.redirect_stderr(errors):
                    self.assertEqual(main(), 1)
                self.assertIn("Unable to record deployment:", errors.getvalue())
                self.assertEqual(path.read_text(encoding="utf-8"), saved)


if __name__ == "__main__":
    unittest.main()
