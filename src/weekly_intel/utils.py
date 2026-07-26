from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_title(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"\W+", " ", text, flags=re.UNICODE).strip()


def display_title(value: str) -> str:
    """Convert small inline LaTeX superscripts into readable Unicode titles."""
    superscripts = str.maketrans("0123456789+-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻")

    def replace(match: re.Match[str]) -> str:
        return match.group(1).translate(superscripts)

    return re.sub(r"\$\^\{?([0-9+-]+)\}?\$", replace, value)
