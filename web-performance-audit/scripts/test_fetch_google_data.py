import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from urllib.error import HTTPError
from unittest.mock import patch

import fetch_google_data as fetch


class FakeResponse:
    def __init__(self, payload):
        self.raw = json.dumps(payload).encode("utf-8")
        self.headers = {"Content-Length": str(len(self.raw))}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, limit=-1):
        return self.raw if limit < 0 else self.raw[:limit]


class GoogleFetchTests(unittest.TestCase):
    def test_check_key_never_prints_value(self):
        secret = "google-secret-value"
        stdout = io.StringIO()
        with patch.dict("os.environ", {fetch.API_KEY_ENV: secret}, clear=True), redirect_stdout(stdout):
            result = fetch.main(["check-key"])
        self.assertEqual(result, 0)
        self.assertIn("is available", stdout.getvalue())
        self.assertNotIn(secret, stdout.getvalue())

    def test_missing_key_is_actionable_for_crux(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "crux.json"
            stderr = io.StringIO()
            with patch.dict("os.environ", {}, clear=True), redirect_stderr(stderr):
                result = fetch.main(
                    ["crux", "--origin", "https://example.com/", "--output", str(output)]
                )
            self.assertEqual(result, 2)
            self.assertIn("CRUX_API_KEY is not available", stderr.getvalue())
            self.assertIn("Direct CrUX queries require", stderr.getvalue())
            self.assertFalse(output.exists())

    def test_psi_runs_without_key(self):
        captured = {}

        def opener(request, **_kwargs):
            captured["url"] = request.full_url
            return FakeResponse({"id": "https://example.com/", "lighthouseResult": {}})

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "psi.json"
            args = fetch.build_parser().parse_args(
                ["psi", "--url", "https://example.com/", "--output", str(output)]
            )
            path, _size = fetch.run(args, environ={}, opener=opener)

            self.assertEqual(path, output)
            self.assertTrue(output.exists())
            self.assertNotIn("key=", captured["url"])

    def test_unexpected_failure_suppresses_secret_details(self):
        secret = "google-secret-value"
        stderr = io.StringIO()
        with (
            patch.dict("os.environ", {fetch.API_KEY_ENV: secret}, clear=True),
            patch.object(fetch, "run", side_effect=RuntimeError(f"unexpected {secret}")),
            redirect_stderr(stderr),
        ):
            result = fetch.main(
                ["psi", "--url", "https://example.com/", "--output", "unused.json"]
            )
        self.assertEqual(result, 3)
        self.assertNotIn(secret, stderr.getvalue())
        self.assertIn("suppressed", stderr.getvalue())

    def test_success_keeps_key_out_of_output_and_logs(self):
        secret = "google-secret-value"
        captured = {}

        def opener(request, **_kwargs):
            captured["url"] = request.full_url
            return FakeResponse(
                {"id": "https://example.com/", "debug": f"unexpected {secret}", "lighthouseResult": {}}
            )

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "psi.json"
            args = fetch.build_parser().parse_args(
                ["psi", "--url", "https://example.com/", "--output", str(output)]
            )
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                path, _size = fetch.run(args, environ={fetch.API_KEY_ENV: secret}, opener=opener)
                print(f"saved {path}")
            self.assertIn(secret, captured["url"])
            self.assertNotIn(secret, stdout.getvalue())
            saved = output.read_text(encoding="utf-8")
            self.assertNotIn(secret, saved)
            self.assertIn("[REDACTED]", saved)

    def test_http_error_redacts_key(self):
        secret = "google-secret-value"

        def opener(request, **_kwargs):
            body = json.dumps({"error": {"message": f"invalid key {secret}"}}).encode("utf-8")
            raise HTTPError(request.full_url, 403, "Forbidden", {}, io.BytesIO(body))

        args = fetch.build_parser().parse_args(
            ["crux", "--origin", "https://example.com", "--output", "unused.json"]
        )
        request = fetch.build_crux_request(args, secret)
        with self.assertRaises(fetch.FetchError) as raised:
            fetch.fetch_json(request, timeout=10, key=secret, opener=opener)
        self.assertNotIn(secret, str(raised.exception))
        self.assertIn("[REDACTED]", str(raised.exception))

    def test_crux_key_is_not_in_request_body(self):
        secret = "google-secret-value"
        args = fetch.build_parser().parse_args(
            [
                "crux",
                "--origin",
                "https://example.com/",
                "--form-factor",
                "PHONE",
                "--output",
                "crux.json",
            ]
        )
        request = fetch.build_crux_request(args, secret)
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body, {"origin": "https://example.com", "formFactor": "PHONE"})
        self.assertNotIn(secret, request.data.decode("utf-8"))
        self.assertIn(secret, request.full_url)

    def test_refuses_existing_output_before_network(self):
        called = False

        def opener(_request, **_kwargs):
            nonlocal called
            called = True
            return FakeResponse({})

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "existing.json"
            output.write_text("keep", encoding="utf-8")
            args = fetch.build_parser().parse_args(
                ["psi", "--url", "https://example.com/", "--output", str(output)]
            )
            with self.assertRaisesRegex(fetch.FetchError, "already exists"):
                fetch.run(args, environ={fetch.API_KEY_ENV: "secret"}, opener=opener)
            self.assertFalse(called)
            self.assertEqual(output.read_text(encoding="utf-8"), "keep")

    def test_rejects_credentials_in_target(self):
        with self.assertRaisesRegex(fetch.FetchError, "credentials"):
            fetch.validate_target("https://user:password@example.com/")


if __name__ == "__main__":
    unittest.main()
