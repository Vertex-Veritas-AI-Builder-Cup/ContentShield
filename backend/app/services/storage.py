"""Cloud Storage helpers for original and suspicious clips."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from google.auth.transport import requests as google_auth_requests
from google.cloud import storage

from app.config import get_settings


def upload_file(local_path: Path, destination: str, content_type: str) -> str:
    """Upload a local video to the configured bucket and return its GCS URI."""

    settings = get_settings()
    client = storage.Client(project=settings.gcp_project_id)
    blob = client.bucket(settings.gcs_bucket).blob(destination)
    blob.upload_from_filename(str(local_path), content_type=content_type)
    return f"gs://{settings.gcs_bucket}/{destination}"


def move_gcs_uri(source_uri: str, destination: str) -> str:
    """Move a stored object into a new path in the configured bucket."""

    if not source_uri.startswith("gs://"):
        raise ValueError("A stored gs:// URI is required")
    source_bucket_name, _, source_blob_name = source_uri.removeprefix("gs://").partition("/")
    if not source_bucket_name or not source_blob_name or not destination.strip():
        raise ValueError("The stored source and destination are invalid")

    settings = get_settings()
    client = storage.Client(project=settings.gcp_project_id)
    source_bucket = client.bucket(source_bucket_name)
    destination_bucket = client.bucket(settings.gcs_bucket)
    source_blob = source_bucket.blob(source_blob_name)
    source_bucket.copy_blob(source_blob, destination_bucket, destination.strip())
    source_blob.delete()
    return f"gs://{settings.gcs_bucket}/{destination.strip()}"


def download_gcs_uri(gcs_uri: str, local_path: Path) -> None:
    """Download a stored object to a local path for background processing."""

    if not gcs_uri.startswith("gs://"):
        raise ValueError("A stored gs:// URI is required")
    bucket_name, _, blob_name = gcs_uri.removeprefix("gs://").partition("/")
    if not bucket_name or not blob_name:
        raise ValueError("The stored URI is invalid")

    settings = get_settings()
    client = storage.Client(project=settings.gcp_project_id)
    client.bucket(bucket_name).blob(blob_name).download_to_filename(str(local_path))


def delete_gcs_uri(gcs_uri: str) -> None:
    """Delete a GCS object referenced by a ``gs://`` URI when it is valid."""

    if not gcs_uri.startswith("gs://"):
        return
    bucket_name, _, blob_name = gcs_uri.removeprefix("gs://").partition("/")
    if not bucket_name or not blob_name:
        return
    settings = get_settings()
    client = storage.Client(project=settings.gcp_project_id)
    client.bucket(bucket_name).blob(blob_name).delete()


def signed_url_for_gcs_uri(gcs_uri: str, *, minutes: int | None = None) -> str | None:
    """Create a short-lived browser URL for a private GCS video when possible."""

    if not gcs_uri.startswith("gs://"):
        return None
    bucket_name, _, blob_name = gcs_uri.removeprefix("gs://").partition("/")
    if not bucket_name or not blob_name:
        return None

    try:
        settings = get_settings()
        minutes = settings.signed_url_minutes if minutes is None else minutes
        if minutes <= 0:
            return None
        client = storage.Client(project=settings.gcp_project_id)
        blob = client.bucket(bucket_name).blob(blob_name)
        credentials = client._credentials
        request = google_auth_requests.Request()

        # Cloud Run uses metadata credentials, which do not contain a private
        # key for local signing. Passing an access token and service-account
        # email makes google-cloud-storage call IAM Credentials signBlob;
        # the runtime identity must have roles/iam.serviceAccountTokenCreator.
        if not credentials.valid or getattr(credentials, "service_account_email", None) in (
            None,
            "default",
        ):
            credentials.refresh(request)
        service_account_email = getattr(credentials, "service_account_email", None)
        access_token = getattr(credentials, "token", None)
        if not service_account_email or service_account_email == "default" or not access_token:
            return None

        return blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=minutes),
            method="GET",
            service_account_email=service_account_email,
            access_token=access_token,
        )
    except Exception:
        return None

