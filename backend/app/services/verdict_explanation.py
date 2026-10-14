"""Gemini-backed explanations for the top content-similarity match."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from google import genai
from google.genai import types

from app.config import get_settings


ALLOWED_DECISIONS = {"likely_match", "uncertain", "not_enough_evidence"}
MAX_EVIDENCE_ITEMS = 8
DURATION_TOLERANCE_SECONDS = 0.05


class VerdictExplanationError(RuntimeError):
    """Represent an unavailable or malformed automated verdict explanation."""


class GeminiProviderError(VerdictExplanationError):
    """Represent a Gemini or Vertex AI request failure rather than bad model JSON."""


def _client() -> genai.Client:
    """Create the Vertex AI client used for grounded verdict-explanation prompts."""

    settings = get_settings()
    return genai.Client(
        vertexai=True,
        project=settings.gcp_project_id,
        location=settings.gcp_location,
    )


def _parse_json_response(text: str) -> dict[str, Any]:
    """Parse JSON returned by Gemini, including a fenced JSON response."""

    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```").removeprefix("json").removesuffix("```").strip()
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise VerdictExplanationError("Gemini returned invalid verdict-explanation JSON") from exc
    if not isinstance(payload, dict):
        raise VerdictExplanationError("Gemini verdict explanation must be a JSON object")
    return payload


def _number(value: object, field: str) -> float:
    """Convert a finite evidence timestamp into a JSON-safe number."""

    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise VerdictExplanationError(f"Verdict-explanation field {field} must be numeric") from exc
    if not math.isfinite(number) or number < 0:
        raise VerdictExplanationError(
            f"Verdict-explanation field {field} must be a non-negative number"
        )
    return number


def validate_verdict_explanation_payload(
    payload: dict[str, Any],
    *,
    model: str,
    query_duration_seconds: float | None = None,
    protected_duration_seconds: float | None = None,
) -> dict[str, Any]:
    """Validate and normalize model JSON before it can be stored or displayed."""

    decision = payload.get("decision")
    if decision not in ALLOWED_DECISIONS:
        raise VerdictExplanationError("Verdict explanation returned an unsupported decision")

    explanation = str(payload.get("explanation") or "").strip()
    if not explanation:
        raise VerdictExplanationError("Verdict explanation cannot be empty")

    raw_evidence = payload.get("evidence") or []
    if not isinstance(raw_evidence, list):
        raise VerdictExplanationError("Verdict-explanation evidence must be a list")

    evidence: list[dict[str, Any]] = []
    discarded_duration_items = 0
    for item in raw_evidence[:MAX_EVIDENCE_ITEMS]:
        if not isinstance(item, dict):
            raise VerdictExplanationError(
                "Each verdict-explanation evidence item must be an object"
            )
        observation = str(item.get("observation") or "").strip()
        if not observation:
            raise VerdictExplanationError("Every evidence item needs an observation")
        query_start = _number(item.get("query_start_seconds", 0), "query_start_seconds")
        query_end = _number(item.get("query_end_seconds", 0), "query_end_seconds")
        protected_start = _number(
            item.get("protected_start_seconds", 0), "protected_start_seconds"
        )
        protected_end = _number(
            item.get("protected_end_seconds", 0), "protected_end_seconds"
        )
        if query_end < query_start or protected_end < protected_start:
            raise VerdictExplanationError("Evidence timestamps must have end after start")
        if query_duration_seconds is not None and query_end > query_duration_seconds:
            if query_end - query_duration_seconds <= DURATION_TOLERANCE_SECONDS:
                query_end = query_duration_seconds
            else:
                discarded_duration_items += 1
                continue
        if protected_duration_seconds is not None and protected_end > protected_duration_seconds:
            if protected_end - protected_duration_seconds <= DURATION_TOLERANCE_SECONDS:
                protected_end = protected_duration_seconds
            else:
                discarded_duration_items += 1
                continue
        evidence.append(
            {
                "query_start_seconds": query_start,
                "query_end_seconds": query_end,
                "protected_start_seconds": protected_start,
                "protected_end_seconds": protected_end,
                "observation": observation,
            }
        )

    raw_limitations = payload.get("limitations") or []
    if not isinstance(raw_limitations, list):
        raise VerdictExplanationError("Verdict-explanation limitations must be a list")

    limitations = [
        item.strip() for item in raw_limitations if isinstance(item, str) and item.strip()
    ]
    if discarded_duration_items:
        limitations.append(
            f"{discarded_duration_items} model-provided evidence range(s) exceeded the stored video duration and were omitted."
        )

    return {
        "verdict_explanation_id": f"explain_{uuid4().hex[:12]}",
        "decision": decision,
        "explanation": explanation,
        "confidence_note": str(
            payload.get("confidence_note")
            or "This is an automated assessment and requires creator or legal review."
        ).strip(),
        "evidence": evidence,
        "limitations": limitations,
        "model": model,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def explain_top_match(
    *,
    suspicious_gcs_uri: str,
    protected_gcs_uri: str,
    suspicious_mime_type: str,
    protected_title: str,
    creator_name: str,
    top_match: dict[str, Any],
    suspicious_duration_seconds: float | None = None,
    protected_duration_seconds: float | None = None,
) -> dict[str, Any]:
    """Ask Gemini to explain a retrieved match using both private GCS videos."""

    if not suspicious_gcs_uri.startswith("gs://"):
        raise VerdictExplanationError("The suspicious video does not have a GCS URI")
    if not protected_gcs_uri.startswith("gs://"):
        raise VerdictExplanationError("The protected video does not have a GCS URI")

    settings = get_settings()
    suspicious_duration = (
        f"{suspicious_duration_seconds:.3f}"
        if suspicious_duration_seconds is not None
        else "unknown"
    )
    protected_duration = (
        f"{protected_duration_seconds:.3f}"
        if protected_duration_seconds is not None
        else "unknown"
    )
    prompt = f"""
You are ContentShield's verdict-explanation assistant. Compare the protected original
video with the suspicious video and explain whether the retrieved match is
credible. This is an evidence summary, not a legal conclusion.

Protected title: {protected_title or "Untitled original"}
Creator: {creator_name or "Unknown"}
Suspicious video duration: {suspicious_duration} seconds
Protected video duration: {protected_duration} seconds
Retrieval result: {json.dumps(top_match, default=str)}

Return only JSON with this shape:
{{
  "decision": "likely_match" | "uncertain" | "not_enough_evidence",
  "explanation": "short grounded explanation",
  "confidence_note": "why the assessment should or should not be trusted",
  "evidence": [
    {{
      "query_start_seconds": 0,
      "query_end_seconds": 1,
      "protected_start_seconds": 0,
      "protected_end_seconds": 1,
      "observation": "visible, concrete comparison"
    }}
  ],
  "limitations": ["specific missing signal or uncertainty"]
}}

Use only visible or explicitly provided evidence. Do not say that the content
is legally infringing, and do not invent URLs, ownership, or timestamps. Every
query timestamp must be between 0 and {suspicious_duration} seconds, and every
protected timestamp must be between 0 and {protected_duration} seconds. Do not
copy the example timestamps above when they do not fit the actual durations. If
there is no valid timestamped evidence, return an empty evidence list and state
that limitation instead.
""".strip()

    content = [
        prompt,
        types.Part(
            file_data=types.FileData(
                file_uri=protected_gcs_uri,
                mime_type=suspicious_mime_type,
            )
        ),
        types.Part(
            file_data=types.FileData(
                file_uri=suspicious_gcs_uri,
                mime_type=suspicious_mime_type,
            )
        ),
    ]
    client: genai.Client | None = None
    try:
        # Keep the client alive for the full request. Calling `_client()` inline
        # can let its underlying HTTP transport close before the SDK finishes.
        client = _client()
        response = client.models.generate_content(
            model=settings.gemini_analysis_model,
            contents=content,
            config={"response_mime_type": "application/json"},
        )
    except Exception as exc:
        # Keep the provider failure actionable for local prototype debugging while
        # truncating the detail so credentials or very large SDK payloads cannot
        # leak through the API response.
        provider_detail = " ".join(str(exc).split())[:240] or type(exc).__name__
        raise GeminiProviderError(
            f"Gemini could not explain the top match: {provider_detail}"
        ) from exc
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                # A request result should not be discarded because transport
                # cleanup itself failed.
                pass

    response_text = getattr(response, "text", None) or ""
    if not response_text.strip():
        raise VerdictExplanationError("Gemini returned an empty verdict explanation")
    return validate_verdict_explanation_payload(
        _parse_json_response(response_text),
        model=settings.gemini_analysis_model,
        query_duration_seconds=suspicious_duration_seconds,
        protected_duration_seconds=protected_duration_seconds,
    )
