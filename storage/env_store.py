from __future__ import annotations

from pathlib import Path

from core.paths import get_env_path


def write_keys(keys: list[str]) -> None:
    env_path = get_env_path()
    existing_lines: list[str] = []

    if env_path.exists():
        existing_lines = env_path.read_text(encoding="utf-8").splitlines()

    kept: list[str] = []
    for line in existing_lines:
        if line.strip().startswith("GEMINI_KEY_"):
            continue
        kept.append(line)

    new_lines = kept[:]
    for idx, key in enumerate(keys, start=1):
        new_lines.append(f"GEMINI_KEY_{idx}={key}")

    env_path.write_text("\n".join(new_lines).rstrip() + "\n", encoding="utf-8")
