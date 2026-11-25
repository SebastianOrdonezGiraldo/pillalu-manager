"""Utilidades de dinero en pesos colombianos (COP).

Los montos se manejan como enteros en pesos. Los porcentajes como fracciones
(0.12 = 12 %).
"""

from __future__ import annotations

import math
import re
from typing import Any


def parse_cop(value: Any) -> int | None:
    """Convierte textos como ``$ 45.900``, ``45,900``, ``45.900,50`` o ``45900`` a entero.

    Devuelve ``None`` si el valor está vacío o no es interpretable (nunca 0 por defecto).

    Reglas de separadores:
    - Con ``.`` y ``,`` a la vez, el último que aparece es el decimal.
    - Con un solo tipo de separador: si todos los grupos posteriores tienen 3 dígitos,
      es separador de miles (``45.900`` / ``1,234,567``); si no, es decimal (``45.5``).
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            return None
        return int(round(value))
    text = re.sub(r"[^\d,.\-]", "", str(value))
    if not text or not re.search(r"\d", text):
        return None
    if "." in text and "," in text:
        decimal = "." if text.rfind(".") > text.rfind(",") else ","
        thousands = "," if decimal == "." else "."
        text = text.replace(thousands, "").replace(decimal, ".")
    else:
        sep = "." if "." in text else ("," if "," in text else None)
        if sep:
            groups = text.split(sep)
            if len(groups) > 1 and all(len(g) == 3 for g in groups[1:]) and groups[0].lstrip("-"):
                text = text.replace(sep, "")
            elif len(groups) == 2:
                text = text.replace(sep, ".")
            else:
                return None
    try:
        return int(round(float(text)))
    except ValueError:
        return None


def parse_pct(value: Any) -> float | None:
    """Convierte ``12``, ``"12 %"``, ``"0,12"`` o ``0.12`` en fracción (0.12).

    Números mayores que 1 se interpretan como porcentaje (12 → 0.12).
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            return None
        number = float(value)
    else:
        text = str(value).strip().replace("%", "").replace(",", ".").strip()
        if not text:
            return None
        try:
            number = float(text)
        except ValueError:
            return None
    return number / 100 if number > 1 else number


def fmt_cop(value: int | float | None) -> str:
    if value is None:
        return "—"
    sign = "-" if value < 0 else ""
    return f"{sign}$ {abs(round(value)):,.0f}".replace(",", ".")


def fmt_pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.1f} %".replace(".", ",")


def round_commercial(price: float) -> int:
    """Sube el precio al siguiente valor terminado en 900 (p. ej. 45.231 → 45.900)."""
    return int(math.ceil((price + 100) / 1000) * 1000 - 100)
