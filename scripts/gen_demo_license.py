#!/usr/bin/env python3
"""Generate imagenes_muestra/LICENSE.md from manifest_demo.json."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "imagenes_muestra" / "manifest_demo.json"
OUT = ROOT / "imagenes_muestra" / "LICENSE.md"


def main() -> None:
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    lines = [
        "# Atribución — imágenes demo de onboarding",
        "",
        "Las fotos `demo_*.jpg` se seleccionaron vía [Openverse](https://openverse.org/)",
        "(licencias **CC0** / **PDM**). Redimensionadas (~1600 px, JPEG q80) para",
        "el onboarding de Timonel.",
        "",
        "| Archivo | Título | Autor | Licencia | Fuente | Requires |",
        "|---------|--------|-------|----------|--------|----------|",
    ]
    for img in m["images"]:
        title = (img.get("title") or "").replace("|", "/").replace("\n", " ")[:60]
        author = (img.get("author") or "Unknown").replace("|", "/")[:40]
        src = img.get("commons_page") or img.get("source_url") or ""
        lines.append(
            f"| `{img['filename']}` | {title} | {author} | "
            f"{img.get('license', 'CC0')} | [link]({src}) | {img.get('requires')} |"
        )
    lines += ["", "Mods: solo resize + recompress JPEG.", ""]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT} ({len(m['images'])} rows)")


if __name__ == "__main__":
    main()
