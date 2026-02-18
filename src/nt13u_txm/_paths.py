#nt13u_txm/_paths.py
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional, Any, Dict
import tomllib

@lru_cache(maxsize=1)
def find_project_root(start: Optional[Path] = None) -> Path:
    """pyproject.toml を辿ってプロジェクトルートを推定。"""
    cur = (start or Path(__file__).resolve()).parent
    for p in [cur] + list(cur.parents):
        if (p / "pyproject.toml").exists():
            return p
    raise RuntimeError(
        f"pyproject.toml not found when searching upward from {cur}"
    )

@lru_cache(maxsize=1)
def _load_pyproject() -> Dict[str, Any]:
    path = find_project_root() / "pyproject.toml"
    with path.open("rb") as f:
        return tomllib.load(f)
    
def get_latest_json_path() -> Path:
    return find_project_root() / _load_pyproject()["tool"]["nt13u_txm"]["view"]["latest_json"]


def get_view_poll_ms() -> int:
    return int(_load_pyproject()["tool"]["nt13u_txm"]["view"]["poll_ms"])


def get_view_width() -> int:
    return int(_load_pyproject()["tool"]["nt13u_txm"]["view"]["width"])


def get_view_height() -> int:
    return int(_load_pyproject()["tool"]["nt13u_txm"]["view"]["height"])

def get_data_dir() -> Path:
    return find_project_root() / "data"

def get_tmp_dir() -> Path:
    p = get_data_dir() / "tmp"
    p.mkdir(parents=True, exist_ok=True)
    return p

def get_logs_dir() -> Path:
    return find_project_root() / "logs"

def get_remoteex_lock_path() -> Path:
    return get_logs_dir() / "remoteex.lock"
