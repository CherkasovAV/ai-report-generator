"""Генерация PDF из HTML через Jinja2 и WeasyPrint."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from utils.logging_setup import silence_native_stderr

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = PROJECT_ROOT / "templates"
REPORTS_DIR = PROJECT_ROOT / "reports"


def ensure_reports_dir() -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return REPORTS_DIR


def sanitize_client_name_for_filename(raw: str | None, *, max_len: int = 80) -> str:
    """Имя клиента для имени файла: без символов, запрещённых в Windows."""
    s = (raw or "").strip()
    if not s:
        return ""
    for ch in '<>:"/\\|?*':
        s = s.replace(ch, "_")
    s = re.sub(r"[\x00-\x1f]", "", s)
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"_+", "_", s).strip("._")
    if len(s) > max_len:
        s = s[:max_len].rstrip("._ ")
    return s


def build_report_filename(*, client_name: str | None = None) -> str:
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    safe = sanitize_client_name_for_filename(client_name)
    if safe:
        return f"report_{safe}_{stamp}.pdf"
    return f"report_{stamp}.pdf"


def build_design_report_filename(*, client_name: str | None = None) -> str:
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    safe = sanitize_client_name_for_filename(client_name)
    if safe:
        return f"report_design_{safe}_{stamp}.pdf"
    return f"report_design_{stamp}.pdf"


def build_marketplace_report_filename(*, product_name: str | None = None) -> str:
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    safe = sanitize_client_name_for_filename(product_name)
    if safe:
        return f"report_marketplace_{safe}_{stamp}.pdf"
    return f"report_marketplace_{stamp}.pdf"


def render_report_html(context: dict) -> str:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("report_template.html")
    return template.render(**context)


def render_design_report_html(context: dict) -> str:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("report_design_template.html")
    return template.render(**context)


def render_marketplace_report_html(context: dict) -> str:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("report_marketplace_template.html")
    return template.render(**context)


def html_to_pdf(html_string: str, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Импорт WeasyPrint инициализирует GTK/GLib и на Windows даёт GLib-GIO-WARNING в stderr — глушим fd на время импорта и записи PDF.
    with silence_native_stderr():
        from weasyprint import HTML

        HTML(string=html_string, base_url=str(TEMPLATES_DIR)).write_pdf(str(output_path))
    return output_path


def generate_pdf_report(data: dict) -> Path:
    """
    Подставляет данные в шаблон, конвертирует в PDF, сохраняет в reports/.
    Имя файла: report_<клиент>_YYYY-MM-DD_HH-MM.pdf (клиент из поля client_name, очищенный).
    """
    ensure_reports_dir()
    filename = build_report_filename(client_name=str(data.get("client_name") or ""))
    out_path = REPORTS_DIR / filename
    html = render_report_html(data)
    logger.info("Сборка PDF: %s", out_path)
    html_to_pdf(html, out_path)
    logger.info("PDF записан, размер %s байт", out_path.stat().st_size)
    return out_path


def generate_design_pdf_report(data: dict) -> Path:
    """
    PDF отчёта по заказу на дизайн сайта (шаблон + встроенное превью).
    Имя: report_design_<клиент>_YYYY-MM-DD_HH-MM.pdf
    """
    ensure_reports_dir()
    filename = build_design_report_filename(client_name=str(data.get("client_name") or ""))
    out_path = REPORTS_DIR / filename
    html = render_design_report_html(data)
    logger.info("Сборка PDF (дизайн): %s", out_path)
    html_to_pdf(html, out_path)
    logger.info("PDF записан, размер %s байт", out_path.stat().st_size)
    return out_path


def generate_marketplace_pdf_report(data: dict) -> Path:
    """
    PDF карточки товара: фон — сгенерированное изображение, поверх — название, цена, описание.
    Имя: report_marketplace_<товар>_YYYY-MM-DD_HH-MM.pdf
    """
    ensure_reports_dir()
    filename = build_marketplace_report_filename(product_name=str(data.get("product_name") or ""))
    out_path = REPORTS_DIR / filename
    html = render_marketplace_report_html(data)
    logger.info("Сборка PDF (маркетплейс): %s", out_path)
    html_to_pdf(html, out_path)
    logger.info("PDF записан, размер %s байт", out_path.stat().st_size)
    return out_path
