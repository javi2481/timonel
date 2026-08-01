#!/usr/bin/env python3
"""Smoke onboarding: UI + demo core image → events/preview (sin fo_*).

Uso (stack core arriba):

    python scripts/smoke_onboarding.py
    python scripts/smoke_onboarding.py --ui-only

Exit 0 solo si todos los asserts pasan.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = os.getenv("ADAPTER_URL", "http://127.0.0.1:8000").rstrip("/")
TIMEOUT_SEC = float(os.getenv("SMOKE_TIMEOUT_SEC", "120"))
POLL_SEC = float(os.getenv("SMOKE_POLL_SEC", "2"))
PREVIEW_MIN_BYTES = int(os.getenv("SMOKE_PREVIEW_MIN_BYTES", "12000"))
DEFAULT_DEMO = ROOT / "imagenes_muestra" / "demo_03_street.jpg"


class SmokeFail(Exception):
    """Assert de smoke fallido."""


def http_raw(
    method: str,
    path: str,
    *,
    data: Optional[bytes] = None,
    headers: Optional[dict[str, str]] = None,
    allow_redirects: bool = False,
) -> tuple[int, dict[str, str], bytes]:
    url = f"{ADAPTER}{path}"
    req = urllib.request.Request(
        url, data=data, headers=headers or {}, method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as exc:
        if allow_redirects and exc.code in (301, 302, 303, 307, 308):
            return exc.code, dict(exc.headers), exc.read()
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise SmokeFail(f"HTTP {exc.code} {url}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise SmokeFail(f"adapter unreachable ({url}): {exc}") from exc


def http_json(method: str, path: str, body: Optional[dict] = None) -> Any:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    status, _hdrs, raw = http_raw(method, path, data=data, headers=headers)
    if status >= 400:
        raise SmokeFail(f"HTTP {status} {path}")
    if not raw:
        return None
    return json.loads(raw.decode("utf-8"))


def assert_ui() -> None:
    code, hdrs, _ = http_raw("GET", "/", allow_redirects=True)
    if code not in (301, 302, 303, 307, 308):
        # Some stacks may serve SPA at / directly
        if code != 200:
            raise SmokeFail(f"GET / expected redirect or 200, got {code}")
    else:
        loc = hdrs.get("Location") or hdrs.get("location") or ""
        if "/app" not in loc:
            raise SmokeFail(f"GET / redirect Location unexpected: {loc!r}")

    status, _h, html = http_raw("GET", "/app/")
    if status != 200:
        raise SmokeFail(f"GET /app/ → {status}")
    text = html.decode("utf-8", errors="replace")
    if "html" not in text.lower():
        raise SmokeFail("GET /app/ did not return HTML")
    # Vite asset reference
    if "/app/assets/" not in text and "src=" not in text:
        raise SmokeFail("GET /app/ missing asset references")

    status, _h, health = http_raw("GET", "/health")
    if status != 200:
        raise SmokeFail(f"GET /health → {status}")
    print("ui-ok: / -> /app/ + /health")


def select_or_upload(demo: Path) -> str:
    # Ensure core caps active (health may have lagged at adapter boot).
    http_json("PUT", "/capabilities", {"active": {"object": True, "face": True}})
    name = demo.name
    items = http_json("GET", "/media/list")
    names = []
    if isinstance(items, dict):
        names = [
            i.get("name")
            for i in (items.get("items") or items.get("files") or [])
            if isinstance(i, dict)
        ]
        if not names and isinstance(items.get("names"), list):
            names = list(items["names"])
    elif isinstance(items, list):
        names = [
            (i.get("name") if isinstance(i, dict) else str(i)) for i in items
        ]

    if name in names:
        http_json("POST", "/media/select", {"name": name})
        print(f"selected {name}")
        return name

    # multipart upload
    boundary = "----timonelsmoke"
    raw = demo.read_bytes()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{name}"\r\n'
        f"Content-Type: image/jpeg\r\n\r\n"
    ).encode("utf-8") + raw + f"\r\n--{boundary}--\r\n".encode("utf-8")
    status, _h, resp = http_raw(
        "POST",
        "/media/upload",
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
        },
    )
    if status >= 400:
        raise SmokeFail(f"upload failed HTTP {status}: {resp[:200]!r}")
    print(f"uploaded {name}")
    return name


def wait_complete() -> dict[str, Any]:
    deadline = time.time() + TIMEOUT_SEC
    last: dict[str, Any] = {}
    while time.time() < deadline:
        last = http_json("GET", "/events") or {}
        gen = last.get("generation")
        lig = last.get("last_ingest_generation")
        if gen is not None and lig is not None and gen == lig:
            return last
        time.sleep(POLL_SEC)
    raise SmokeFail(
        f"timeout waiting generation==last_ingest "
        f"(generation={last.get('generation')} last_ingest={last.get('last_ingest_generation')})"
    )


def assert_preview() -> None:
    _s, _h, data = http_raw("GET", "/preview.jpg")
    if len(data) < PREVIEW_MIN_BYTES:
        raise SmokeFail(
            f"preview too small ({len(data)} B < {PREVIEW_MIN_BYTES}); placeholder?"
        )
    if data[:2] != b"\xff\xd8":
        raise SmokeFail("preview is not JPEG")
    print(f"preview-ok: {len(data)} B")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ui-only", action="store_true")
    ap.add_argument("--demo", type=Path, default=DEFAULT_DEMO)
    args = ap.parse_args()

    try:
        assert_ui()
        if args.ui_only:
            print("PASS (ui-only)")
            return 0
        if not args.demo.is_file():
            raise SmokeFail(f"demo image missing: {args.demo}")
        try:
            select_or_upload(args.demo)
            envelope = wait_complete()
            events = envelope.get("events") or []
            if not isinstance(events, list):
                raise SmokeFail("events not a list")
            if len(events) < 1:
                raise SmokeFail(
                    "expected >=1 detection on core demo "
                    f"(got 0; try another requires=core image)"
                )
            for ev in events[:5]:
                if not isinstance(ev, dict):
                    raise SmokeFail("event not object")
                if "entity_type" not in ev:
                    raise SmokeFail("event missing entity_type")
            print(f"events-ok: {len(events)} events gen={envelope.get('generation')}")
            assert_preview()
            print("PASS")
            return 0
        finally:
            try:
                http_json("POST", "/media/clear", {})
            except SmokeFail as exc:
                print(f"warn: media clear failed: {exc}", file=sys.stderr)
    except SmokeFail as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
