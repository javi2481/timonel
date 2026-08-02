#!/usr/bin/env python3
"""Construye un índice Face ID en paddlex-face-id y imprime el indexKey.

Uso (stack up, servicio :8087):

    python scripts/face_id_index_build.py --dir path/a/galeria
    # Estructura: galeria/<label>/*.jpg|png

    python scripts/face_id_index_build.py --pair alice=fotos/a.jpg --pair bob=fotos/b.jpg

Pegá el indexKey en .env como FACE_ID_INDEX_KEY=... y recreá adapter+bridge:

    docker compose up -d --force-recreate adapter bridge
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterable

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def _b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def pairs_from_dir(root: Path) -> list[dict[str, str]]:
    """Cada subcarpeta = label; archivos de imagen adentro."""
    out: list[dict[str, str]] = []
    if not root.is_dir():
        raise SystemExit(f"no es directorio: {root}")
    for label_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        label = label_dir.name
        for img in sorted(label_dir.iterdir()):
            if img.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            out.append({"image": _b64(img), "label": label})
    return out


def pairs_from_cli(items: Iterable[str]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for item in items:
        if "=" not in item:
            raise SystemExit(f"--pair espera label=path, got {item!r}")
        label, path_s = item.split("=", 1)
        path = Path(path_s)
        if not path.is_file():
            raise SystemExit(f"archivo faltante: {path}")
        out.append({"image": _b64(path), "label": label.strip()})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--url",
        default=os.getenv("PADDLEX_FACE_ID_URL", "http://127.0.0.1:8087"),
        help="Base URL del serving face-recognition",
    )
    ap.add_argument(
        "--path",
        default="/face-recognition-index-build",
        help="Path del endpoint index-build",
    )
    ap.add_argument("--dir", type=Path, default=None, help="Galería label/imagen")
    ap.add_argument(
        "--pair",
        action="append",
        default=[],
        help="label=path (repetible)",
    )
    args = ap.parse_args()

    pairs: list[dict[str, str]] = []
    if args.dir is not None:
        pairs.extend(pairs_from_dir(args.dir))
    if args.pair:
        pairs.extend(pairs_from_cli(args.pair))
    if not pairs:
        print("FAIL: ningún imageLabelPair (usá --dir o --pair)", file=sys.stderr)
        return 1

    url = f"{args.url.rstrip('/')}{args.path}"
    body = json.dumps({"imageLabelPairs": pairs}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read()
            data = json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read()[:500]
        print(f"FAIL HTTP {exc.code}: {detail!r}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"FAIL unreachable {url}: {exc}", file=sys.stderr)
        return 1

    if not isinstance(data, dict):
        print(f"FAIL: respuesta no JSON object: {data!r}", file=sys.stderr)
        return 1
    if data.get("errorCode") not in (None, 0, "0"):
        print(f"FAIL errorCode={data.get('errorCode')}: {data.get('errorMsg')}", file=sys.stderr)
        return 1

    result = data.get("result") if isinstance(data.get("result"), dict) else data
    key = (
        (result or {}).get("indexKey")
        or (result or {}).get("index_key")
        or data.get("indexKey")
    )
    if not key:
        print(f"FAIL: sin indexKey en respuesta: {json.dumps(data)[:800]}", file=sys.stderr)
        return 1

    print(f"indexKey={key}")
    print(f"pairs={len(pairs)}")
    print("Pegá en .env: FACE_ID_INDEX_KEY=" + str(key))
    print("Luego: docker compose up -d --force-recreate adapter bridge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
