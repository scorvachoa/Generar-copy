from __future__ import annotations

import os
import sys
from pathlib import Path


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parents[1]


def get_env_path() -> Path:
    return get_base_dir() / ".env"


def get_outputs_dir() -> Path:
    return get_base_dir() / "outputs"


def get_processed_path() -> Path:
    return get_base_dir() / "procesadas.json"
