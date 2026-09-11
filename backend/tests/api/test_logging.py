"""configure_logging: app.* records must reach stdout (see the Massive 404 that
was logged on every poll and never appeared in `docker compose logs`)."""

import logging
import sys

import pytest

from app.main import LOG_HANDLER_NAME, configure_logging, create_app


def _ours() -> list[logging.Handler]:
    return [h for h in logging.getLogger().handlers if h.get_name() == LOG_HANDLER_NAME]


@pytest.fixture(autouse=True)
def fresh_root(monkeypatch):
    """Start each test without our handler and restore the root level after."""
    root = logging.getLogger()
    old_level = root.level
    for handler in _ours():
        root.removeHandler(handler)
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    yield
    for handler in _ours():
        root.removeHandler(handler)
    root.setLevel(old_level)


def test_create_app_installs_a_stdout_handler_at_info():
    create_app()

    root = logging.getLogger()
    (handler,) = _ours()
    assert isinstance(handler, logging.StreamHandler)
    assert handler.stream is sys.stdout
    assert root.level == logging.INFO
    assert "%(name)s" in handler.formatter._fmt
    assert "%(levelname)s" in handler.formatter._fmt


def test_calling_twice_adds_no_second_handler():
    create_app()
    create_app()

    assert len(_ours()) == 1


def test_log_level_env_var_is_respected(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "debug")
    configure_logging()
    assert logging.getLogger().level == logging.DEBUG


def test_unknown_log_level_falls_back_to_info(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "LOUD")
    configure_logging()
    assert logging.getLogger().level == logging.INFO


def test_app_records_are_written_to_stdout(capsys):
    configure_logging()

    logging.getLogger("app.market.massive_client").info("Massive poller started")

    assert "INFO app.market.massive_client: Massive poller started" in capsys.readouterr().out


def test_uvicorn_loggers_are_left_alone():
    """Uvicorn's own loggers keep their handlers and do not propagate to ours."""
    before = {
        name: (list(logging.getLogger(name).handlers), logging.getLogger(name).propagate)
        for name in ("uvicorn", "uvicorn.error", "uvicorn.access")
    }

    configure_logging()

    for name, (handlers, propagate) in before.items():
        assert logging.getLogger(name).handlers == handlers
        assert logging.getLogger(name).propagate == propagate
