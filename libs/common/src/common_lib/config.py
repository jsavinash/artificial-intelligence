"""Shared configuration management backed by Dynaconf.

Settings are resolved in 12-factor order: environment variables prefixed with
``APP_`` always win over TOML/YAML files, so the same image runs unchanged
across dev, staging and production.

The settings file is *optional* and its location overridable via
``SETTINGS_FILE`` — containers carry no repo checkout, so a missing file must
never be fatal.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Final

from dynaconf import Dynaconf

SETTINGS_FILE_ENV: Final[str] = "SETTINGS_FILE"


def default_settings_path() -> Path:
    """Repo-root settings.toml (works both from checkout and installed venvs)."""
    override = os.environ.get(SETTINGS_FILE_ENV)
    if override:
        return Path(override)
    # libs/common/src/common_lib/config.py -> repo root is 4 levels up.
    return Path(__file__).resolve().parents[3] / "settings.toml"


def build_settings(env: str | None = None) -> Any:
    """Compose a Dynaconf instance layered over defaults and env vars."""
    settings_file = default_settings_path()
    return Dynaconf(
        envvar_prefix="APP",
        environments=True,
        env=env or "default",
        settings_files=[str(settings_file)] if settings_file.exists() else [],
        load_dotenv=True,
    )


@lru_cache(maxsize=1)
def get_settings() -> Any:
    """Process-wide cached settings accessor."""
    return build_settings()
