from __future__ import annotations

import json
from pathlib import Path

from core.paths import get_processed_path


def load_processed() -> set[str]:
    path = get_processed_path()
    if not path.exists():
        return set()

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
        return set(data.get("imagenes_procesadas", []))


def save_processed(processed: set[str]) -> None:
    path = get_processed_path()
    temp_path = path.with_suffix(path.suffix + ".tmp")

    with temp_path.open("w", encoding="utf-8") as f:
        json.dump(
            {"imagenes_procesadas": list(processed)},
            f,
            indent=4,
            ensure_ascii=False,
        )

    temp_path.replace(path)


def add_processed(item: str) -> None:
    processed = load_processed()
    processed.add(item)
    save_processed(processed)
