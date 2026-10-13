"""Run a repeatable deployment smoke check against a live ContentShield API."""

from __future__ import annotations

import argparse
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _get_json(base_url: str, path: str) -> dict:
    request = Request(f"{base_url.rstrip('/')}{path}", headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"GET {path} failed: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"GET {path} did not return a JSON object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()
    try:
        health = _get_json(args.base_url, "/health")
        if health.get("status") != "ok":
            raise RuntimeError(f"Unexpected health response: {health}")
        openapi = _get_json(args.base_url, "/openapi.json")
        paths = openapi.get("paths") or {}
        required = {"/health", "/api/clips", "/api/scan", "/api/scans", "/api/style-match"}
        missing = sorted(required - set(paths))
        if missing:
            raise RuntimeError(f"OpenAPI is missing expected paths: {', '.join(missing)}")
    except RuntimeError as exc:
        print(f"SMOKE CHECK FAILED: {exc}", file=sys.stderr)
        return 1
    print(f"SMOKE CHECK PASSED: {args.base_url.rstrip('/')}")
    print(f"Health: {health.get('service')} v{health.get('version')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
