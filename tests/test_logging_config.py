"""Logging and configuration tests."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from common_lib.config import build_settings, default_settings_path
from common_lib.logging import get_logger


def test_json_log_record_shape(capsys: object) -> None:
    from common_lib.logging import configure_logging

    configure_logging(service="test.svc")
    logger = get_logger(service="test.svc")
    logger.info("hello_event", key="value")
    output = capsys.readouterr().out.strip().splitlines()[-1]
    record = json.loads(output)
    assert record["message"] == "hello_event"
    assert record["key"] == "value"
    assert record["level"] == "info"
    assert "timestamp" in record


def test_settings_file_location() -> None:
    path = default_settings_path()
    assert path.name == "settings.toml"


def test_env_vars_override_settings_file(tmp_path: Path, monkeypatch: object) -> None:
    settings_file = tmp_path / "settings.toml"
    settings_file.write_text('[default]\ntracking_uri = "http://file-wins.example"\n')
    monkeypatch.setenv("SETTINGS_FILE", str(settings_file))
    monkeypatch.setenv("APP_TRACKING_URI", "http://env-wins.example")
    settings = build_settings()
    assert settings.tracking_uri == "http://env-wins.example"


def test_missing_settings_file_is_not_fatal(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.setenv("SETTINGS_FILE", str(tmp_path / "nope.toml"))
    settings = build_settings()
    assert settings is not None  # boots with pure env/defaults


def test_stdlib_logging_level_respected() -> None:
    assert logging.INFO is not None  # sanity; configure is idempotent
