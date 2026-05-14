"""
AI Client Report Generator — точка входа.

Читает транскрипцию (или для маркетплейса — название и цену), вызывает ИИ, собирает PDF в каталог reports/.
Типы отчёта: диалог клиента, заказ на дизайн сайта (с превью), карточка товара для маркетплейса (фон + текст).
Без аргументов (когда не указан файл и не заданы данные для карточки) запускается интерактивное меню.
"""

from __future__ import annotations

import argparse
import logging
import sys
import traceback
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from utils.ai_processor import (
    process_design_order_with_ai,
    process_dialog_with_ai,
    process_marketplace_card_with_ai,
)
from utils.logging_setup import configure_logging, quiet_cli_dialog
from utils.pdf_generator import (
    PROJECT_ROOT,
    generate_design_pdf_report,
    generate_marketplace_pdf_report,
    generate_pdf_report,
)

logger = logging.getLogger(__name__)

REPORT_CLIENT = "client"
REPORT_DESIGN = "design"
REPORT_MARKETPLACE = "marketplace"
REPORT_CHOICES = (REPORT_CLIENT, REPORT_DESIGN, REPORT_MARKETPLACE)


def read_transcript_from_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def read_transcript_stdin() -> str:
    return sys.stdin.read()


def read_transcript_interactive() -> str:
    print(
        "Введите транскрипцию (несколько строк). "
        "Завершите ввод отдельной строкой END и Enter:",
        flush=True,
    )
    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == "END":
            break
        lines.append(line)
    return "\n".join(lines)


def run_marketplace_pipeline(product_name: str, price: str, notes: str = "") -> Path:
    logger.info("Этап 1/2: чат — текст карточки и промпт для картинки…")
    structured = process_marketplace_card_with_ai(product_name, price, notes)
    logger.info("Этап 2/2: сборка PDF (маркетплейс)…")
    return generate_marketplace_pdf_report(structured)


def run_pipeline(transcript: str, report_type: str) -> Path:
    if report_type == REPORT_DESIGN:
        logger.info("Этап 1/3: чат — структура заказа и промпт для картинки…")
        structured = process_design_order_with_ai(transcript)
        logger.info("Этап 2–3/3: сборка PDF (дизайн)…")
        return generate_design_pdf_report(structured)

    logger.info("Этап 1/2: запрос к LLM…")
    structured = process_dialog_with_ai(transcript)
    logger.info("Этап 2/2: генерация PDF…")
    return generate_pdf_report(structured)


def display_report_path(pdf_path: Path) -> str:
    try:
        rel = pdf_path.resolve().relative_to(Path.cwd().resolve())
    except ValueError:
        rel = pdf_path.resolve().relative_to(PROJECT_ROOT.resolve())
    return rel.as_posix()


def _cli_needs_interactive_menu(args: argparse.Namespace) -> bool:
    """Нет готовых данных для генерации — показываем меню и задаём вопросы."""
    if args.serve:
        return False
    if args.interactive or args.transcript_file:
        return False
    if args.report == REPORT_MARKETPLACE:
        if (args.product or "").strip() and (args.price or "").strip():
            return False
    return True


def _prompt_nonempty(prompt: str) -> str:
    while True:
        try:
            line = input(prompt).strip()
        except EOFError:
            print("\nВвод прерван.", file=sys.stderr)
            raise SystemExit(2) from None
        if line:
            return line
        print("Значение не может быть пустым. Повторите.", flush=True)


def _prompt_optional(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except EOFError:
        print("\nВвод прерван.", file=sys.stderr)
        raise SystemExit(2) from None


def _normalize_user_path(raw: str) -> Path:
    s = raw.strip().strip('"').strip("'")
    return Path(s).expanduser()


INPUT_DIR = PROJECT_ROOT / "input"


def _ensure_input_dir() -> Path:
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    return INPUT_DIR


def _list_input_files() -> list[Path]:
    """Обычные файлы в input/, только верхний уровень, сортировка по имени."""
    root = _ensure_input_dir()
    paths = [p for p in root.iterdir() if p.is_file()]
    paths.sort(key=lambda p: p.name.lower())
    return paths


def _select_transcript_from_input_menu() -> str:
    """
    Пронумерованный список файлов из папки input; выбор номером.
    0 — ввести полный путь к файлу; «-» в ручном режиме — вставка транскрипции из консоли.
    """
    while True:
        files = _list_input_files()
        abs_input = _ensure_input_dir().resolve()
        print(f"\nФайлы в папке input:\n  {abs_input}\n", flush=True)
        if files:
            for i, p in enumerate(files, start=1):
                print(f"  {i} — {p.name}", flush=True)
            print(
                "  0 — указать полный путь к файлу (или «-» для вставки транскрипции из консоли)\n",
                flush=True,
            )
            sel = _prompt_nonempty(f"Номер файла (1–{len(files)}) или 0: ").strip()
            if sel != "0":
                try:
                    n = int(sel)
                except ValueError:
                    print("Введите целое число.", flush=True)
                    continue
                if 1 <= n <= len(files):
                    path = files[n - 1]
                    transcript = read_transcript_from_file(path)
                    if not transcript.strip():
                        print("Выбранный файл пуст. Укажите другой номер.", flush=True)
                        continue
                    return transcript
                print(f"Номер должен быть от 1 до {len(files)} или 0.", flush=True)
                continue
        else:
            print(
                "  (в папке input нет файлов — добавьте текстовые файлы или укажите путь ниже.)\n",
                flush=True,
            )

        raw = _prompt_nonempty("Полный путь к файлу (или - для вставки из консоли): ")
        if raw.strip() == "-":
            print(
                "Вставьте транскрипцию, затем завершите ввод "
                "(Windows: Ctrl+Z, Enter; macOS/Linux: Ctrl+D):",
                flush=True,
            )
            transcript = read_transcript_stdin()
            if not transcript.strip():
                print("Транскрипция пуста. Повторите.", flush=True)
                continue
            return transcript
        path = _normalize_user_path(raw)
        if not path.is_file():
            print(f"Файл не найден: {path}. Повторите.", flush=True)
            continue
        transcript = read_transcript_from_file(path)
        if not transcript.strip():
            print("Файл пустой. Укажите другой путь.", flush=True)
            continue
        return transcript


def run_interactive_menu() -> tuple[str, str, str, str, str]:
    """
    Меню выбора типа отчёта и ввод данных.
    Возвращает (report_type, transcript, product, price, notes).
    Для client/design transcript непустой, product/price/notes пустые.
    Для marketplace — product и price непустые, transcript пустой.
    """
    print(
        "\n=== Генератор PDF-отчётов ===\n"
        "Выберите тип отчёта:\n"
        f"  1 — отчёт по диалогу с клиентом ({REPORT_CLIENT})\n"
        f"  2 — заказ на дизайн сайта + превью-картинка ({REPORT_DESIGN})\n"
        f"  3 — карточка товара для маркетплейса ({REPORT_MARKETPLACE})\n",
        flush=True,
    )
    choice = _prompt_nonempty("Введите номер (1, 2 или 3): ")
    if choice not in ("1", "2", "3"):
        print("Нужно ввести 1, 2 или 3.", file=sys.stderr)
        raise SystemExit(2)

    if choice == "3":
        print("\n--- Карточка маркетплейса ---\n", flush=True)
        product = _prompt_nonempty("Название товара: ")
        price = _prompt_nonempty("Цена (как на карточке, например 1 290 ₽ или 990): ")
        notes = _prompt_optional("Дополнительно о товаре (необязательно, Enter — пропустить): ")
        return REPORT_MARKETPLACE, "", product, price, notes

    report_type = REPORT_CLIENT if choice == "1" else REPORT_DESIGN
    label = "диалогу с клиентом" if choice == "1" else "заказу на дизайн сайта"
    print(f"\n--- Отчёт по {label} ---\n", flush=True)
    transcript = _select_transcript_from_input_menu()
    return report_type, transcript, "", "", ""


def run_interactive_menu_or_prompts(args: argparse.Namespace) -> tuple[str, str, str, str, str]:
    """
    Полное меню (1–3) или только дозапрос товара/цены, если в CLI уже выбран marketplace без полных данных.
    """
    if args.report == REPORT_MARKETPLACE:
        prod = (args.product or "").strip()
        pr = (args.price or "").strip()
        if not prod or not pr:
            print("\n--- Карточка маркетплейса ---\n", flush=True)
            if not prod:
                prod = _prompt_nonempty("Название товара: ")
            if not pr:
                pr = _prompt_nonempty("Цена (как на карточке, например 1 290 ₽ или 990): ")
            notes = (args.product_notes or "").strip()
            if not notes:
                notes = _prompt_optional("Дополнительно о товаре (необязательно, Enter — пропустить): ")
            return REPORT_MARKETPLACE, "", prod, pr, notes
    return run_interactive_menu()


def _cli_should_defer_startup_log(args: argparse.Namespace) -> bool:
    """Не писать INFO в stderr до конца меню / ввода транскрипции (-i)."""
    if args.serve:
        return False
    if _cli_needs_interactive_menu(args):
        return True
    if args.interactive:
        return True
    return False


def _log_cli_startup(report_type: str) -> None:
    logger.info("Рабочая директория: %s", Path.cwd())
    logger.info("Тип отчёта: %s", report_type)


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Генерация PDF: отчёт по диалогу клиента, бриф на дизайн сайта с превью "
            "или карточка товара для маркетплейса (название + цена → OpenAI → PDF)."
        ),
    )
    p.add_argument(
        "--report",
        choices=REPORT_CHOICES,
        default=REPORT_CLIENT,
        metavar="TYPE",
        help=(
            f"Тип отчёта: {REPORT_CLIENT} — диалог с клиентом; {REPORT_DESIGN} — заказ на дизайн сайта + картинка; "
            f"{REPORT_MARKETPLACE} — карточка товара (нужны --product и --price)."
        ),
    )
    p.add_argument(
        "transcript_file",
        nargs="?",
        help="Путь к текстовому файлу с транскрипцией. Используйте - для чтения из stdin.",
    )
    p.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Ввод транскрипции вручную в консоли (завершение строкой END).",
    )
    p.add_argument(
        "--product",
        default="",
        metavar="NAME",
        help=f"Режим {REPORT_MARKETPLACE}: название товара.",
    )
    p.add_argument(
        "--price",
        default="",
        metavar="PRICE",
        help=f"Режим {REPORT_MARKETPLACE}: цена (строка, как на карточке).",
    )
    p.add_argument(
        "--product-notes",
        default="",
        dest="product_notes",
        metavar="TEXT",
        help=f"Дополнительные пожелания к товару/карточке (только {REPORT_MARKETPLACE}).",
    )
    p.add_argument(
        "--serve",
        action="store_true",
        help="Запустить Flask API (POST /generate).",
    )
    p.add_argument(
        "--host",
        default="127.0.0.1",
        help="Хост для Flask (по умолчанию 127.0.0.1).",
    )
    p.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Порт для Flask (по умолчанию 5000).",
    )
    p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Подробные логи в stderr (DEBUG) и полный traceback при ошибках. Во время меню и ввода транскрипции (-i) сообщения INFO по-прежнему скрыты, чтобы не мешать вопросам.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    configure_logging(verbose=args.verbose)
    if not _cli_should_defer_startup_log(args):
        _log_cli_startup(args.report)

    if args.serve:
        return run_flask(host=args.host, port=args.port)

    if _cli_needs_interactive_menu(args):
        with quiet_cli_dialog():
            report_type, transcript, product, price, notes = run_interactive_menu_or_prompts(args)
        _log_cli_startup(report_type)
        try:
            if report_type == REPORT_MARKETPLACE:
                out = run_marketplace_pipeline(product, price, notes)
            else:
                out = run_pipeline(transcript, report_type)
        except Exception as exc:  # noqa: BLE001
            if args.verbose:
                traceback.print_exception(type(exc), exc, exc.__traceback__, file=sys.stderr)
            print(f"Ошибка: {exc}", file=sys.stderr)
            return 1
        rel = display_report_path(out)
        print(f"Отчёт успешно создан: {rel}")
        return 0

    if args.report == REPORT_MARKETPLACE:
        product = (args.product or "").strip()
        price = (args.price or "").strip()
        if not product or not price:
            print(
                f"Для --report {REPORT_MARKETPLACE} укажите --product и --price (строки).",
                file=sys.stderr,
            )
            return 2
        notes = (args.product_notes or "").strip()
        try:
            out = run_marketplace_pipeline(product, price, notes)
        except Exception as exc:  # noqa: BLE001
            if args.verbose:
                traceback.print_exception(type(exc), exc, exc.__traceback__, file=sys.stderr)
            print(f"Ошибка: {exc}", file=sys.stderr)
            return 1
        rel = display_report_path(out)
        print(f"Отчёт успешно создан: {rel}")
        return 0

    transcript: str | None = None
    if args.interactive:
        with quiet_cli_dialog():
            transcript = read_transcript_interactive()
        _log_cli_startup(args.report)
    elif args.transcript_file:
        if args.transcript_file.strip() == "-":
            transcript = read_transcript_stdin()
        else:
            path = Path(args.transcript_file)
            if not path.is_file():
                print(f"Файл не найден: {path}", file=sys.stderr)
                return 2
            transcript = read_transcript_from_file(path)
    else:
        build_arg_parser().print_help()
        print(
            "\nБез аргументов запускается меню выбора типа отчёта и путь к файлу.\n"
            "\nПример: python main.py\n"
            "         python main.py input/sample_transcript.txt\n"
            f"         python main.py --report {REPORT_MARKETPLACE} --product \"Керамическая кружка\" --price \"890 ₽\"\n"
            "         python main.py --report design input/sample_design_transcript.txt\n"
            "         python main.py --report design input/sample_design_transcript_photo.txt\n"
            "         python main.py - < transcript.txt\n"
            "         python main.py -i",
            file=sys.stderr,
        )
        return 2

    try:
        out = run_pipeline(transcript, args.report)
    except Exception as exc:  # noqa: BLE001 — CLI: показать причину пользователю
        if args.verbose:
            traceback.print_exception(type(exc), exc, exc.__traceback__, file=sys.stderr)
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1

    rel = display_report_path(out)
    print(f"Отчёт успешно создан: {rel}")
    return 0


def _parse_report_type(value: object) -> str:
    s = str(value or "").strip().lower()
    if s in REPORT_CHOICES:
        return s
    return REPORT_CLIENT


def run_flask(host: str, port: int) -> int:
    from flask import Flask, jsonify, request

    app = Flask(__name__)

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "report_types": list(REPORT_CHOICES)})

    @app.post("/generate")
    def generate():
        transcript = ""
        report_type = REPORT_CLIENT
        product_name = ""
        price = ""
        notes = ""

        if request.is_json:
            payload = request.get_json(silent=True) or {}
            report_type = _parse_report_type(payload.get("report_type"))
            if report_type == REPORT_MARKETPLACE:
                product_name = str(payload.get("product_name") or payload.get("product") or "").strip()
                price = str(payload.get("price") or "").strip()
                notes = str(payload.get("notes") or payload.get("product_notes") or "").strip()
            else:
                transcript = str(payload.get("transcript", "") or "")
        else:
            report_type = _parse_report_type(request.form.get("report_type"))
            if report_type == REPORT_MARKETPLACE:
                product_name = str(
                    request.form.get("product_name") or request.form.get("product") or "",
                ).strip()
                price = str(request.form.get("price") or "").strip()
                notes = str(request.form.get("notes") or request.form.get("product_notes") or "").strip()
            else:
                transcript = str(request.form.get("transcript") or "")
                if not transcript.strip() and request.files.get("file"):
                    f = request.files["file"]
                    transcript = f.read().decode("utf-8", errors="replace")

        if report_type == REPORT_MARKETPLACE:
            if not product_name or not price:
                return (
                    jsonify(
                        {
                            "ok": False,
                            "error": "Для report_type=marketplace передайте product_name и price (JSON или form-data).",
                        },
                    ),
                    400,
                )
            try:
                out = run_marketplace_pipeline(product_name, price, notes)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Ошибка генерации в POST /generate (marketplace)")
                return jsonify({"ok": False, "error": str(exc)}), 500
            rel = out.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
            return jsonify({"ok": True, "report": rel, "report_type": report_type})

        if not transcript.strip():
            return jsonify({"ok": False, "error": "Передайте transcript в JSON, form-data или файлом file."}), 400

        try:
            out = run_pipeline(transcript, report_type)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Ошибка генерации в POST /generate")
            return jsonify({"ok": False, "error": str(exc)}), 500

        rel = out.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
        return jsonify({"ok": True, "report": rel, "report_type": report_type})

    print(
        f"API: http://{host}:{port}/generate (POST), report_type: {REPORT_CLIENT}|{REPORT_DESIGN}|{REPORT_MARKETPLACE}",
        flush=True,
    )
    app.run(host=host, port=port, debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
