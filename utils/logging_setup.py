"""Единая настройка логирования для CLI и (при необходимости) Flask."""

from __future__ import annotations

import contextlib
import logging
import os
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


@contextlib.contextmanager
def quiet_generation_logs(*, verbose: bool) -> Iterator[None]:
    """
    Без -v: только ERROR и выше — чтобы этапы генерации (чат, картинка, PDF) не засоряли консоль.
    С -v: уровень не меняется.
    """
    if verbose:
        yield
        return
    root = logging.getLogger()
    previous = root.level
    root.setLevel(logging.ERROR)
    try:
        yield
    finally:
        root.setLevel(previous)


@contextlib.contextmanager
def silence_native_stderr() -> Iterator[None]:
    """
    Подавляет stderr на уровне fd на время блока (сообщения GLib-GIO-WARNING от GTK/WeasyPrint на Windows).
    Восстанавливает sys.stderr и дескриптор 2 после выхода.
    """
    saved_stderr = sys.stderr
    saved_fd = os.dup(2)
    devnull_fd = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(devnull_fd, 2)
        sys.stderr = open(os.devnull, "w", encoding="utf-8", errors="replace")
        yield
    finally:
        try:
            sys.stderr.flush()
        except Exception:
            pass
        try:
            sys.stderr.close()
        except Exception:
            pass
        os.dup2(saved_fd, 2)
        os.close(saved_fd)
        os.close(devnull_fd)
        sys.stderr = saved_stderr
