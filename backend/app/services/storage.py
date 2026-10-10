"""Cloud Storage helpers for original and suspicious clips."""

from __future__ import annotations

from pathlib import Path

from google.cloud import storage

from app.config import get_settings


def upload_file(local_path: Path, destination: str, content_type: str) -> str:
    """Upload a local video to the configured bucket and return its GCS URI."""

    settings = get_settings()
    client = storage.Client(project=settings.gcp_project_id)
    blob = client.bucket(settings.gcs_bucket).blob(destination)
    blob.upload_from_filename(str(local_path), content_type=content_type)
    return f"gs://{settings.gcs_bucket}/{destination}"


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

