"""Config management for lava — stored at platformdirs user_config_dir / config.toml."""

import os
import tempfile
from pathlib import Path
from typing import Any

import platformdirs
import toml

DEFAULT_CONFIG: dict[str, Any] = {
    "vault": {
        "path": "",
        "history": [],
    },
    "search": {
        "backend": "bm25",
    },
    "pagination": 50,
    "editor": "",
    "links_folder": "",
    "ui": {
        "tree_depth": 4,
    },
}


def get_config_path() -> Path:
    config_dir = Path(platformdirs.user_config_dir("lava"))
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "config.toml"


def load_config() -> dict:
    path = get_config_path()
    if not path.exists():
        save_config(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)

    try:
        loaded = toml.load(str(path))
    except Exception:
        return dict(DEFAULT_CONFIG)

    merged = _deep_merge(DEFAULT_CONFIG, loaded)
    return merged


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def save_config(config: dict) -> None:
    path = get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        toml.dump(config, f)


def get_vault_path() -> str:
    config = load_config()
    return config.get("vault", {}).get("path", "")


def set_vault_path(path: str) -> None:
    config = load_config()
    config["vault"]["path"] = path
    save_config(config)


def add_to_history(path: str) -> None:
    config = load_config()
    history: list = config["vault"].get("history", [])
    if path in history:
        history.remove(path)
    history.insert(0, path)
    config["vault"]["history"] = history[:5]
    save_config(config)


def _session_file() -> Path:
    """Temp file scoped to the parent shell process — cleared when terminal closes."""
    return Path(tempfile.gettempdir()) / f"lava_cwd_{os.getppid()}"


def get_vault_cwd() -> str:
    f = _session_file()
    return f.read_text().strip() if f.exists() else ""


def set_vault_cwd(rel_path: str) -> None:
    f = _session_file()
    if rel_path:
        f.write_text(rel_path)
    else:
        f.unlink(missing_ok=True)


def set_dotted_key(key: str, value: str) -> None:
    """Set a config value using a dotted key like 'ui.pagination' or 'llm.model'."""
    config = load_config()
    parts = key.split(".")
    target = config
    for part in parts[:-1]:
        if part not in target:
            target[part] = {}
        target = target[part]

    final_key = parts[-1]
    existing = target.get(final_key)
    if isinstance(existing, int):
        try:
            target[final_key] = int(value)
        except ValueError:
            target[final_key] = value
    elif isinstance(existing, float):
        try:
            target[final_key] = float(value)
        except ValueError:
            target[final_key] = value
    elif isinstance(existing, bool):
        target[final_key] = value.lower() in ("true", "1", "yes")
    elif isinstance(existing, list):
        target[final_key] = [v.strip() for v in value.split(",") if v.strip()]
    else:
        target[final_key] = value

    save_config(config)
