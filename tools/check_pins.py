"""Verifica que TODO paquete instalado esté fijado en constraints.txt o requirements-dev.txt
con la misma versión (reauditoría RA-P2-02). Se ejecuta en CI después de instalar."""

from __future__ import annotations

import re
import sys
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IGNORED = {"pip", "setuptools", "wheel"}


def norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def pins() -> dict[str, str]:
    out: dict[str, str] = {}
    for f in ("constraints.txt", "requirements.txt", "requirements-dev.txt"):
        for line in (ROOT / f).read_text(encoding="utf-8").splitlines():
            m = re.match(r"^\s*([A-Za-z0-9_.\-]+)==([^\s;#]+)", line)
            if m:
                out[norm(m.group(1))] = m.group(2)
    return out


def main() -> int:
    expected = pins()
    errors = []
    for dist in metadata.distributions():
        name = norm(dist.metadata["Name"])
        if name in IGNORED:
            continue
        if name not in expected:
            errors.append(f"{name}=={dist.version} instalado sin versión fijada")
        elif expected[name] != dist.version:
            errors.append(f"{name}: instalado {dist.version}, fijado {expected[name]}")
    for e in errors:
        print("ERROR:", e)
    print("Todas las dependencias instaladas están fijadas." if not errors else f"{len(errors)} problemas.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
