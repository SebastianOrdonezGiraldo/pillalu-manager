"""Utilidades de dinero en pesos colombianos (COP).

Los montos se manejan como enteros en pesos. Los porcentajes como fracciones
(0.12 = 12 %).
"""

from __future__ import annotations

import math
import re
from typing import Any


# Solo dígitos ASCII (0-9): otros sistemas de numeración se rechazan.
_PREFIX = re.compile(r"^(?:cop\s*)?\$?\s*", re.IGNORECASE)
_SUFFIX = re.compile(r"\s*(?:cop)?$", re.IGNORECASE)
_NUMBER = re.compile(r"-?[0-9]+(?:[.,][0-9]+)*")


def _clean_text(value: Any) -> str:
    text = str(value).replace("\u00a0", " ").strip()
    # Una sola marca de moneda al inicio ("$", "COP", "COP $") y/o "COP" al final.
    text = _PREFIX.sub("", text, count=1)
    return _SUFFIX.sub("", text, count=1).strip()


def parse_cop(value: Any) -> int | None:
    """Convierte ``$ 45.900``, ``45,900``, ``45.900,50``, ``COP 12.000`` o ``45900`` a entero.

    Devuelve ``None`` si el valor está vacío o **no cumple exactamente** un formato
    aceptado (nunca 0 ni un valor recortado). El texto completo se valida ANTES de
    convertir: ``1,20E+04``, ``12 mil``, ``45.9.00`` o ``1.2.3`` se rechazan en vez de
    reinterpretarse (reauditoría RA-P0-01).

    Formatos aceptados (signo ``-`` opcional, ``$``/``COP`` opcional al inicio o final):
    - Sin separadores: ``45900``.
    - Miles con ``.`` o ``,`` en grupos de 3: ``45.900``, ``1,234,567``.
    - Miles y decimales: ``45.900,50`` o ``45,900.50`` (el último separador es el decimal).
    - Un solo separador que no forma grupo de 3: decimal (``45,5``).
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            return None
        return int(round(value))
    text = _clean_text(value)
    if not text or not _NUMBER.fullmatch(text):
        return None
    sign = -1 if text.startswith("-") else 1
    body = text.lstrip("-")
    if "." in body and "," in body:
        decimal = "." if body.rfind(".") > body.rfind(",") else ","
        thousands = "," if decimal == "." else "."
        integer, _, frac = body.rpartition(decimal)
        if not re.fullmatch(rf"[0-9]{{1,3}}(?:{re.escape(thousands)}[0-9]{{3}})*", integer):
            return None
        number = float(integer.replace(thousands, "") + "." + frac)
    else:
        sep = "." if "." in body else ("," if "," in body else None)
        if sep is None:
            number = float(body)
        else:
            groups = body.split(sep)
            if len(groups[0]) <= 3 and all(len(g) == 3 for g in groups[1:]):
                number = float(body.replace(sep, ""))
            elif len(groups) == 2:
                number = float(body.replace(sep, "."))
            else:
                return None
    return sign * int(math.floor(number + 0.5))  # redondeo comercial: ,5 sube


_PCT = re.compile(r"-?[0-9]+(?:[.,][0-9]+)?")


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
        text = str(value).replace("%", "").strip()
        if not text:
            return None
        if not _PCT.fullmatch(text):
            return None
        number = float(text.replace(",", "."))
    return number / 100 if number > 1 else number


def parse_percent_field(value: Any) -> float | None:
    """Campo de formulario rotulado en %: ``12`` → 0.12, ``0,5`` → 0.005. Sin ambigüedad."""
    if value is None:
        return None
    text = str(value).replace("%", "").strip()
    if not text:
        return None
    if not _PCT.fullmatch(text):  # sin exponentes ni texto extra (RA-P0-01)
        return None
    return float(text.replace(",", ".")) / 100


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
