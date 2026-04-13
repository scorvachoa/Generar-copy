from __future__ import annotations

import re
from pathlib import Path


def normalize_keys(raw_lines: list[str]) -> list[str]:
    keys: list[str] = []
    seen: set[str] = set()

    for line in raw_lines:
        item = line.strip()
        if not item:
            continue

        parts = re.split(r"[\s,;]+", item)
        for part in parts:
            token = part.strip()
            if not token:
                continue

            if "=" in token:
                token = token.split("=", 1)[1].strip()

            if (token.startswith('"') and token.endswith('"')) or (
                token.startswith("'") and token.endswith("'")
            ):
                token = token[1:-1].strip()

            if token and token not in seen:
                seen.add(token)
                keys.append(token)

    return keys


def validate_keys(keys: list[str]) -> tuple[bool, list[str]]:
    errors: list[str] = []

    for idx, key in enumerate(keys, start=1):
        if any(ch.isspace() for ch in key):
            errors.append(f"Clave {idx}: contiene espacios")
            continue
        if len(key) < 20:
            errors.append(f"Clave {idx}: muy corta")
            continue
        if not key.startswith("AIza"):
            errors.append(f"Clave {idx}: formato inusual (no inicia con AIza)")

    hard_errors = [e for e in errors if "formato inusual" not in e]
    if hard_errors:
        return False, errors
    return True, errors


def read_key_file(path: str) -> str:
    raw = Path(path).read_bytes()

    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16")
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig")

    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")
