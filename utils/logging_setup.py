"""Единая настройка логирования для CLI и (при необходимости) Flask."""

from __future__ import annotations

import contextlib
import logging
import sys
from collections.abc import Iterator


def configure_logging(*, verbose: bool) -> None:
    """verbose=True — DEBUG и полные трассировки при ошибках API."""
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stderr)
    fmt = "%(levelname)s [%(name)s] %(message)s"
    handler.setFormatter(logging.Formatter(fmt))
    root.addHandler(handler)
    root.setLevel(logging.DEBUG if verbose else logging.INFO)

    for name in ("httpx", "httpcore", "hpack"):
        logging.getLogger(name).setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.DEBUG if verbose else logging.WARNING)


@contextlib.contextmanager
def quiet_cli_dialog() -> Iterator[None]:
    """
    Временно поднимает порог корневого логгера до WARNING,
    чтобы вопросы меню / интерактивного ввода не смешивались с INFO в stderr.
    """
    root = logging.getLogger()
    previous = root.level
    root.setLevel(logging.WARNING)
    try:
        yield
    finally:
        root.setLevel(previous)
