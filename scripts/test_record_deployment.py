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
            {"environment": "dev", "service": "web-app", "version": "1.4.0", "status": "success"},
            {"environment": "prod", "service": "web-app", "version": "1.3.1", "status": "success"},
        ]

    def test_records_actor_and_normalizes_time_without_changing_other_fields(self):
        untouched = copy.deepcopy(self.deployments[1])
        result = record_deployment(
            self.deployments, "dev", "web-app", "2026-11-24T09:00:00+11:00", "octocat"
        )
        self.assertEqual(result[0]["deployedAt"], "2026-11-23T22:00:00Z")
        self.assertEqual(result[0]["deployedBy"], "octocat")
        self.assertEqual(result[0]["version"], "1.4.0")
        self.assertEqual(result[0]["status"], "success")
        self.assertEqual(result[1], untouched)

    def test_empty_time_uses_current_utc_time_and_replaces_previous_actor(self):
        self.deployments[0]["deployedBy"] = "previous-user"
        before = datetime.now(timezone.utc)
        result = record_deployment(self.deployments, "dev", "web-app", "", "octocat")
        timestamp = datetime.fromisoformat(result[0]["deployedAt"].replace("Z", "+00:00"))
        self.assertLessEqual(before, timestamp)
        self.assertLessEqual(timestamp, datetime.now(timezone.utc))
        self.assertEqual(result[0]["deployedBy"], "octocat")

    def test_accepts_utc_suffix(self):
        result = record_deployment(
            self.deployments, "dev", "web-app", "2026-11-24T09:00:00Z", "octocat"
        )
        self.assertEqual(result[0]["deployedAt"], "2026-11-24T09:00:00Z")

    def test_invalid_times_do_not_mutate_data(self):
        original = copy.deepcopy(self.deployments)
        for timestamp in ("yesterday", "2026-11-24", "2026-11-24T09:00:00"):
            with self.subTest(timestamp=timestamp), self.assertRaises(ValueError):
                record_deployment(self.deployments, "dev", "web-app", timestamp, "octocat")
            self.assertEqual(self.deployments, original)

    def test_rejects_missing_or_ambiguous_target(self):
        for environment, service in (("missing", "web-app"), ("dev", "unknown")):
            with self.subTest(environment=environment, service=service), self.assertRaises(ValueError):
                record_deployment(self.deployments, environment, service, "", "octocat")
        self.deployments.append(copy.deepcopy(self.deployments[0]))
        with self.assertRaises(ValueError):
            record_deployment(self.deployments, "dev", "web-app", "", "octocat")

    def test_rejects_malformed_data_and_missing_actor(self):
        for data in ({}, [None]):
            with self.subTest(data=data), self.assertRaises(ValueError):
                record_deployment(data, "dev", "web-app", "", "octocat")
        with self.assertRaises(ValueError):
            record_deployment(self.deployments, "dev", "web-app", "", " ")

    def test_command_saves_success_and_preserves_file_on_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "deployments.json"
            path.write_text(json.dumps(self.deployments), encoding="utf-8")
            inputs = {
                "DEPLOYMENT_ENVIRONMENT": "dev",
                "DEPLOYMENT_SERVICE": "web-app",
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
