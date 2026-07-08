"""Shared helpers: seeding, IO, and formatting."""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config import DATA_DIR, RANDOM_SEED


def set_seed(seed: int = RANDOM_SEED) -> None:
    """Seed all RNGs used in the project for reproducibility."""
    random.seed(seed)
    np.random.seed(seed)


def save_table(df: pd.DataFrame, name: str) -> Path:
    """Persist a dataframe as CSV under data/processed and return the path."""
    path = DATA_DIR / f"{name}.csv"
    df.to_csv(path, index=False)
    return path


def save_metrics(metrics: dict[str, Any], name: str) -> Path:
    """Persist a metrics dict as JSON under data/processed."""
    path = DATA_DIR / f"{name}.json"
    with open(path, "w") as fh:
        json.dump(_to_native(metrics), fh, indent=2)
    return path


def _to_native(obj: Any) -> Any:
    """Recursively convert numpy scalars to native python for JSON."""
    if isinstance(obj, dict):
        return {k: _to_native(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_native(v) for v in obj]
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


def fmt_pct(x: float, digits: int = 2) -> str:
    return f"{x * 100:.{digits}f}%"


def fmt_money(x: float) -> str:
    return f"${x:,.0f}"
