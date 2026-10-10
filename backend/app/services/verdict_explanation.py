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
    for item in raw_evidence[:MAX_EVIDENCE_ITEMS]:
        if not isinstance(item, dict):
            raise VerdictExplanationError(
                "Each verdict-explanation evidence item must be an object"
            )
        observation = str(item.get("observation") or "").strip()
        if not observation:
            raise VerdictExplanationError("Every evidence item needs an observation")
        evidence.append(
            {
                "query_start_seconds": _number(
                    item.get("query_start_seconds", 0), "query_start_seconds"
                ),
                "query_end_seconds": _number(
                    item.get("query_end_seconds", 0), "query_end_seconds"
                ),
                "protected_start_seconds": _number(
                    item.get("protected_start_seconds", 0), "protected_start_seconds"
                ),
                "protected_end_seconds": _number(
                    item.get("protected_end_seconds", 0), "protected_end_seconds"
                ),
                "observation": observation,
            }
        )

    raw_limitations = payload.get("limitations") or []
    if not isinstance(raw_limitations, list):
        raise VerdictExplanationError("Verdict-explanation limitations must be a list")

    return {
        "verdict_explanation_id": f"explain_{uuid4().hex[:12]}",
        "decision": decision,
        "explanation": explanation,
        "confidence_note": str(
            payload.get("confidence_note")
            or "This is an automated assessment and requires creator or legal review."
        ).strip(),
        "evidence": evidence,
        "limitations": [str(item).strip() for item in raw_limitations if str(item).strip()],
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
) -> dict[str, Any]:
    """Ask Gemini to explain a retrieved match using both private GCS videos."""

    if not suspicious_gcs_uri.startswith("gs://"):
        raise VerdictExplanationError("The suspicious video does not have a GCS URI")
    if not protected_gcs_uri.startswith("gs://"):
        raise VerdictExplanationError("The protected video does not have a GCS URI")

    settings = get_settings()
    prompt = f"""
You are ContentShield's verdict-explanation assistant. Compare the protected original
video with the suspicious video and explain whether the retrieved match is
credible. This is an evidence summary, not a legal conclusion.

Protected title: {protected_title or "Untitled original"}
Creator: {creator_name or "Unknown"}
Retrieval result: {json.dumps(top_match, default=str)}

Return only JSON with this shape:
{{
  "decision": "likely_match" | "uncertain" | "not_enough_evidence",
  "explanation": "short grounded explanation",
  "confidence_note": "why the assessment should or should not be trusted",
  "evidence": [
    {{
      "query_start_seconds": 0,
      "query_end_seconds": 5,
      "protected_start_seconds": 0,
      "protected_end_seconds": 5,
      "observation": "visible, concrete comparison"
    }}
  ],
  "limitations": ["specific missing signal or uncertainty"]
}}

Use only visible or explicitly provided evidence. Do not say that the content
is legally infringing, and do not invent URLs, ownership, or timestamps.
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
    try:
        response = _client().models.generate_content(
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

    response_text = getattr(response, "text", None) or ""
    if not response_text.strip():
        raise VerdictExplanationError("Gemini returned an empty verdict explanation")
    return validate_verdict_explanation_payload(
        _parse_json_response(response_text),
        model=settings.gemini_analysis_model,
    )
