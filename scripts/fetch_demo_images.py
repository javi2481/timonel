#!/usr/bin/env python3
"""Download + resize demo JPGs from manifest_demo.json (host-only).

Sources are CC0/PDM URLs curated via Openverse (see LICENSE.md).
Idempotent: skips existing files unless --force.

    python scripts/fetch_demo_images.py
    python scripts/fetch_demo_images.py --force
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "imagenes_muestra" / "manifest_demo.json"
OUT_DIR = ROOT / "imagenes_muestra"
UA = "TimonelDemoFetcher/1.0 (https://github.com/javi2481/timonel; onboarding demos)"


def _pil():
    try:
        from PIL import Image
    except ImportError as exc:
        raise SystemExit(
            "Pillow required. Install: python -m pip install Pillow"
        ) from exc
    return Image


def _get(url: str, timeout: float = 90.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def save_resized(data: bytes, dest: Path, max_width: int, quality: int) -> None:
    Image = _pil()
    img = Image.open(io.BytesIO(data))
    img = img.convert("RGB")
    w, h = img.size
    if w > max_width:
        nh = max(1, int(h * (max_width / w)))
        img = img.resize((max_width, nh), Image.Resampling.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest, format="JPEG", quality=quality, optimize=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--sleep", type=float, default=0.4)
    args = ap.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    max_width = int(manifest.get("max_width", 1600))
    quality = int(manifest.get("jpeg_quality", 80))
    images = manifest.get("images") or []
    if not images:
        print("No images in manifest", file=sys.stderr)
        return 1

    ok = 0
    failed: list[str] = []
    for entry in images:
        filename = entry["filename"]
        dest = args.out / filename
        if dest.exists() and not args.force:
            print(f"skip {filename}")
            ok += 1
            continue
        url = entry.get("source_url") or ""
        if not url:
            print(f"FAIL {filename}: missing source_url", file=sys.stderr)
            failed.append(filename)
            continue
        print(f"fetch {filename} …")
        try:
            time.sleep(args.sleep)
            data = _get(url)
            save_resized(data, dest, max_width, quality)
            print(f"  wrote {dest.name} ({dest.stat().st_size // 1024} KiB)")
            ok += 1
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError) as exc:
            print(f"  FAIL {filename}: {exc}", file=sys.stderr)
            failed.append(filename)

    print(f"done: {ok}/{len(images)} ok")
    if failed:
        print("failed:", ", ".join(failed), file=sys.stderr)
        return 1 if ok < 15 else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
