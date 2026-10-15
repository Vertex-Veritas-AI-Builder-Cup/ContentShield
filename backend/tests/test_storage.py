from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from app.services.storage import signed_url_for_gcs_uri


class _Credentials:
    service_account_email = "runtime@example.iam.gserviceaccount.com"
    token = None
    valid = False

    def refresh(self, request) -> None:
        self.token = "iam-access-token"
        self.valid = True


class SignedUrlTests(unittest.TestCase):
    @patch("app.services.storage.storage.Client")
    @patch("app.services.storage.get_settings")
    def test_cloud_run_credentials_use_iam_sign_blob(
        self, settings_mock: Mock, client_factory: Mock
    ) -> None:
        settings_mock.return_value.gcp_project_id = "project"
        settings_mock.return_value.signed_url_minutes = 15

        credentials = _Credentials()
        blob = Mock()
        blob.generate_signed_url.return_value = "https://signed/video"
        client = client_factory.return_value
        client._credentials = credentials
        client.bucket.return_value.blob.return_value = blob

        result = signed_url_for_gcs_uri("gs://bucket/video.mp4")

        self.assertEqual(result, "https://signed/video")
        blob.generate_signed_url.assert_called_once()
        kwargs = blob.generate_signed_url.call_args.kwargs
        self.assertEqual(kwargs["service_account_email"], credentials.service_account_email)
        self.assertEqual(kwargs["access_token"], "iam-access-token")


if __name__ == "__main__":
    unittest.main()
