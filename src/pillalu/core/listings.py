"""Generador de fichas comerciales sin costo (plantillas + reglas).

Reglas de título tomadas de la documentación oficial de Mercado Libre
(docs/FEASIBILITY.md §2.4): sin "stock", sin "envío gratis", sin marcas de
terceros (esto último lo revisa el fundador). La longitud máxima real depende de
la categoría (``max_title_length``); aquí es configurable por canal.

La generación con IA de pago queda fuera de v0.1 (bloqueo B-4).
"""

from __future__ import annotations

import re
import unicodedata

from .models import Product

FORBIDDEN_TITLE_PATTERNS = [
    r"\benv[ií]o\s+gratis\b",
    r"\bstock\b",
    r"\bdisponible(s)?\b",
    r"\boferta\b",
    r"\bpromo(ci[oó]n)?\b",
    r"\bdescuento\b",
]

SMALL_WORDS = {"de", "del", "la", "el", "los", "las", "y", "o", "para", "con", "en", "x", "a", "por", "sin"}


def _strip_emoji(text: str) -> str:
    return "".join(ch for ch in text if unicodedata.category(ch) not in ("So", "Sk", "Cs"))


def clean_title(name: str, max_len: int = 60) -> str:
    """Título limpio, en formato título, recortado en límite de palabra."""
    text = _strip_emoji(name or "")
    for pat in FORBIDDEN_TITLE_PATTERNS:
        text = re.sub(pat, " ", text, flags=re.IGNORECASE)
    text = re.sub(r"[!¡*#|_]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -–,.")
    words = []
    for i, w in enumerate(text.split(" ")):
        if w.isupper() and len(w) <= 4 or any(c.isdigit() for c in w):
            words.append(w)  # siglas y medidas (USB, LED, 500ml) se respetan
        elif i > 0 and w.lower() in SMALL_WORDS:
            words.append(w.lower())
        else:
            words.append(w[:1].upper() + w[1:].lower())
    title = " ".join(words)
    if len(title) > max_len:
        cut = title[:max_len].rsplit(" ", 1)[0]
        title = cut if cut else title[:max_len]
        while title.split(" ")[-1].lower() in SMALL_WORDS:
            title = title.rsplit(" ", 1)[0]
    return title


def _bullets(description: str | None) -> list[str]:
    if not description:
        return []
    text = re.sub(r"<[^>]+>", "\n", description)  # quita HTML simple de Dropi
    parts = re.split(r"[\n•·]+|(?<=\.)\s+", text)
    out = []
    for p in parts:
        p = re.sub(r"\s+", " ", p).strip(" -–*✔✅")
        if len(p) >= 3 and p.lower() not in (x.lower() for x in out):
            out.append(p)
    return out[:12]


def build_description(product: Product, channel: str, footer: str = "") -> str:
    """Descripción en texto plano (Mercado Libre la exige en ``plain_text``)."""
    title = clean_title(product.name, 120)
    lines = [title, ""]
    bullets = _bullets(product.description)
    if bullets:
        lines.append("Características:")
        lines += [f"- {b}" for b in bullets]
        lines.append("")
    if product.has_variants:
        lines.append("Consulta los colores, tallas o referencias disponibles antes de comprar.")
        lines.append("")
    if channel == "facebook":
        lines.append("Escríbenos para confirmar disponibilidad, ciudad de entrega y tiempo de envío.")
    else:
        lines.append("Haz tus preguntas antes de comprar; respondemos lo antes posible.")
    if footer:
        lines += ["", footer.strip()]
    lines += ["", "Pillalú"]
    return "\n".join(lines).strip()


def build_listing(product: Product, channel: str, price: int | None, max_len: int = 60, footer: str = "") -> dict:
    return {
        "title": clean_title(product.name, max_len),
        "description": build_description(product, channel, footer),
        "price": price,
    }
