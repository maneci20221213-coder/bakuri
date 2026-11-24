"""Connection reset recovery must preserve TLS, host and package integrity checks."""

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.request import Request

import update_transport as transport


def connection_error(code=12031):
    error = OSError("connection reset")
    error.winerror = code
    return error


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "update.partial"
        self.url = "https://github.com/example/app/releases/latest/download/releases.stable.json"

    def test_retry_restarts_partial_download_and_keeps_primary_proxy_transport(self):
        def first_attempt(*args):
            self.path.write_bytes(b"partial")
            raise connection_error()

        def recovered(*args):
            self.assertFalse(self.path.exists())
            self.path.write_bytes(b"complete")

        with (
            patch.object(transport.sys, "platform", "win32"),
            patch.object(
                transport, "_windows_download", side_effect=[connection_error(), None]
            ) as primary,
            patch.object(transport, "_standard_download") as fallback,
            patch.object(transport.time, "sleep"),
        ):
            calls = iter([first_attempt, recovered])
            primary.side_effect = lambda *args: next(calls)(*args)
            transport.download_to(self.url, self.path, 100)
            self.assertEqual(primary.call_count, 2)
            fallback.assert_not_called()
        self.assertEqual(self.path.read_bytes(), b"complete")

    def test_repeated_12031_switches_to_verified_standard_https(self):
        def standard(*args):
            self.assertFalse(self.path.exists())
            self.path.write_bytes(b"fallback")

        with (
            patch.object(transport.sys, "platform", "win32"),
            patch.object(transport, "_windows_download", side_effect=connection_error()) as primary,
            patch.object(transport, "_standard_download", side_effect=standard) as fallback,
            patch.object(transport.time, "sleep"),
        ):
            transport.download_to(self.url, self.path, 100)
            self.assertEqual(primary.call_count, 2)
            fallback.assert_called_once_with(self.url, self.path, 100, 30)
        self.assertEqual(self.path.read_bytes(), b"fallback")

    def test_primary_success_never_uses_alternate_transport(self):
        with (
            patch.object(transport.sys, "platform", "win32"),
            patch.object(transport, "_windows_download") as primary,
            patch.object(transport, "_standard_download") as fallback,
        ):
            transport.download_to(self.url, self.path, 100)
            primary.assert_called_once()
            fallback.assert_not_called()

    def test_certificate_http_and_file_failures_do_not_switch_transport(self):
        for error in [
            connection_error(12045),
            OSError("Update HTTP status 403"),
            PermissionError("denied"),
        ]:
            with (
                self.subTest(error=error),
                patch.object(transport.sys, "platform", "win32"),
                patch.object(transport, "_windows_download", side_effect=error) as primary,
                patch.object(transport, "_standard_download") as fallback,
            ):
                self.path.write_bytes(b"partial")
                with self.assertRaises(OSError):
                    transport.download_to(self.url, self.path, 100)
                self.assertFalse(self.path.exists())
                primary.assert_called_once()
                fallback.assert_not_called()

    def test_both_transport_failures_keep_diagnostics_and_remove_partial_output(self):
        def broken(*args):
            self.path.write_bytes(b"partial")
            raise OSError("TLS validation failed")

        with (
            patch.object(transport.sys, "platform", "win32"),
            patch.object(transport, "_windows_download", side_effect=connection_error()),
            patch.object(transport, "_standard_download", side_effect=broken),
            patch.object(transport.time, "sleep"),
        ):
            with self.assertRaises(OSError) as caught:
                transport.download_to(self.url, self.path, 100)
            errors = caught.exception.__cause__.exceptions
            self.assertEqual(errors[0].winerror, 12031)
            self.assertIn("TLS validation failed", str(errors[-1]))
        self.assertFalse(self.path.exists())

    def test_standard_transport_keeps_limit_and_discards_oversized_download(self):
        response = io.BytesIO(b"too large")
        response.status = 200
        response.geturl = lambda: self.url
        opener = Mock()
        opener.open.return_value = response
        with (
            patch.object(transport.sys, "platform", "linux"),
            patch.object(transport, "build_opener", return_value=opener),
        ):
            with self.assertRaisesRegex(OSError, "exceeded"):
                transport.download_to(self.url, self.path, 2)
        self.assertFalse(self.path.exists())

    def test_untrusted_redirect_is_rejected_before_following_it(self):
        handler = transport._GithubRedirects()
        for target in ["http://github.com/file", "https://evil.example/file"]:
            with self.subTest(target=target), self.assertRaises(ValueError):
                handler.redirect_request(Request(self.url), None, 302, "Found", {}, target)
        redirected = handler.redirect_request(
            Request(self.url),
            None,
            302,
            "Found",
            {},
            "https://release-assets.githubusercontent.com/file",
        )
        self.assertEqual(redirected.host, "release-assets.githubusercontent.com")
