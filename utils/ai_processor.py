"""Вызов OpenAI API: отчёт по диалогу, дизайн сайта (+ превью), карточка товара для маркетплейса (+ фон)."""

from __future__ import annotations

import base64
import json
import logging
import os
import re
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

logger = logging.getLogger(__name__)


def _first_nonempty_env(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def _first_set_env_name(*names: str) -> str | None:
    for name in names:
        if os.getenv(name, "").strip():
            return name
    return None


def _exc_chain_text(exc: BaseException, max_parts: int = 6) -> str:
    parts: list[str] = []
    cur: BaseException | None = exc
    seen: set[int] = set()
    while cur is not None and len(parts) < max_parts:
        if id(cur) in seen:
            break
        seen.add(id(cur))
        parts.append(f"{type(cur).__name__}: {cur}")
        cur = cur.__cause__
    return " → ".join(parts)


def _require_http_url(url: str, env_name: str) -> str:
    u = url.strip().rstrip("/")
    if not u.lower().startswith(("http://", "https://")):
        raise RuntimeError(
            f"{env_name} должен начинаться с https:// или http:// (сейчас: {url!r}). "
            "Для ProxyAPI обычно: https://api.proxyapi.ru/openai/v1",
        )
    return u


def _network_error_hint(exc: BaseException) -> str:
    chain = _exc_chain_text(exc)
    if "UnsupportedProtocol" not in chain and "missing" not in chain.lower():
        return ""
    return (
        "Проверьте OPENAI_BASE_URL (полный https://…). "
        "Если заданы HTTPS_PROXY/HTTP_PROXY — укажите со схемой, например http://127.0.0.1:7890."
    )


REQUIRED_KEYS = (
    "client_name",
    "topic",
    "main_request",
    "deadlines_and_cost",
    "product_essentials",
    "mood",
    "next_steps",
)

SYSTEM_PROMPT = """Ты аналитик клиентских диалогов. По транскрипции верни ТОЛЬКО валидный JSON без markdown и пояснений.
Схема:
{
  "client_name": "имя или компания клиента, если неизвестно — пустая строка",
  "topic": "краткая тема разговора одной строкой",
  "main_request": "основная потребность/запрос клиента",
  "deadlines_and_cost": "желаемые сроки, бюджет или стоимость, тарифы, если в диалоге упоминались; если нет — кратко «не указано в диалоге»",
  "product_essentials": "что точно должно быть в финальном продукте/услуге: ключевые пожелания, объём, качество, состав, ограничения; если не сформулировано — «не указано в диалоге»",
  "mood": "тон и эмоциональный фон (нейтральный, позитивный, напряжённый и т.д.)",
  "next_steps": "рекомендуемые следующие шаги для менеджера"
}
Язык: тот же, что и в транскрипции (если по-русски — только русский).
Стиль: грамотный деловой русский, литературная норма, без разговорных искажений и без слов-«псевдоинфинитивов»
(неверно: «пришлить», «запросить» в значении «сделать запрос» — пиши нормально: «прислать КП», «направить коммерческое предложение», «отправить расчёт», «связаться с клиентом»).
Правописание: например «коммерческое предложение» — с двумя «м».
Поле next_steps формулируй короткими законченными фразами или нумерованными шагами; перечитай текст и исправь опечатки перед ответом.
Все значения — строки."""

DESIGN_REQUIRED_KEYS = (
    "client_name",
    "project_title",
    "order_summary",
    "pages_and_features",
    "visual_direction",
    "deadlines_and_budget",
    "image_prompt",
    "next_steps",
)

DESIGN_SYSTEM_PROMPT = """Ты аналитик брифов на разработку/дизайн сайта. По транскрипции переговоров с заказчиком верни ТОЛЬКО валидный JSON без markdown.
Схема:
{
  "client_name": "компания или контактное лицо",
  "project_title": "краткое название проекта сайта",
  "order_summary": "суть заказа: цели сайта, ниша, ключевые ожидания заказчика",
  "pages_and_features": "предполагаемые страницы, разделы, функции (лендинг, каталог, личный кабинет и т.д.)",
  "visual_direction": "пожелания по стилю, цветам, настроению, референсам из диалога",
  "deadlines_and_budget": "сроки и бюджет, если звучали; иначе «не указано в диалоге»",
  "image_prompt": "ОДНА строка на АНГЛИЙСКОМ: детальный промпт для генерации одного примера-иллюстрации главной страницы или hero-секции сайта (композиция, стиль, палитра, настроение). Без мелкого нечитаемого текста на макете. До 3500 символов.",
  "next_steps": "что сделать дизайнеру/менеджеру дальше (на русском, грамотно)"
}
Поля кроме image_prompt — на языке транскрипции (обычно русский). image_prompt — только английский, для DALL·E / image API.
Все значения — строки."""

MARKETPLACE_REQUIRED_KEYS = (
    "product_name",
    "price_display",
    "description",
    "image_prompt",
)

MARKETPLACE_SYSTEM_PROMPT = """Ты копирайтер и арт-директор для маркетплейса. По названию товара и цене (и при необходимости кратким примечаниям заказчика) верни ТОЛЬКО валидный JSON без markdown.
Схема:
{
  "product_name": "краткое привлекательное название для карточки (можно слегка отполировать исходное, без лжи о свойствах)",
  "price_display": "цена для отображения на карточке: возьми переданную цену, при необходимости добавь валюту/единицы, если явно не указаны — оставь как ввод или укажи «руб.» для рублей",
  "description": "2–5 коротких предложений на русском: выгоды, для кого товар, ключевые характеристики (разумные допущения по категории товара; не выдумывай сертификаты и гарантии, которых не было во входе)",
  "image_prompt": "ОДНА строка на АНГЛИЙСКОМ: промпт для генерации одного фото товара как фона карточки маркетплейса — чистая композиция, хорошее освещение, без мелкого нечитаемого текста на изображении, без логотипов брендов третьих сторон; стиль премиальный каталожный или lifestyle в зависимости от категории. До 3500 символов."
}
Поля кроме image_prompt — на русском. image_prompt — только английский, для OpenAI Images API (модель gpt-image-1).
Все значения — строки."""


def _strip_json_fence(text: str) -> str:
    text = text.strip()
    m = re.match(r"^```(?:json)?\s*\n?(.*?)\n?```\s*$", text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return text


def _normalize_payload(data: Any, keys: tuple[str, ...]) -> dict[str, str]:
    if not isinstance(data, dict):
        raise ValueError("Ответ модели не является JSON-объектом.")
    out: dict[str, str] = {}
    for key in keys:
        val = data.get(key, "")
        out[key] = "" if val is None else str(val).strip()
    return out


def _build_openai_client() -> OpenAI:
    api_key = _first_nonempty_env("OPENAI_API_KEY", "PROXY_API_KEY", "API_KEY")
    if not api_key:
        raise RuntimeError(
            "Не задан ключ: укажите OPENAI_API_KEY или общий PROXY_API_KEY (или API_KEY) в .env",
        )

    base_url = _first_nonempty_env("OPENAI_BASE_URL", "OPENAI_API_BASE")
    key_from = _first_set_env_name("OPENAI_API_KEY", "PROXY_API_KEY", "API_KEY")

    if key_from in ("PROXY_API_KEY", "API_KEY") and not base_url:
        raise RuntimeError(
            "Используется PROXY_API_KEY (или API_KEY) без OPENAI_API_KEY: укажите OPENAI_BASE_URL — "
            "базовый адрес шлюза со схемой https. Для ProxyAPI: "
            "OPENAI_BASE_URL=https://api.proxyapi.ru/openai/v1",
        )

    client_kwargs: dict = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = _require_http_url(base_url, "OPENAI_BASE_URL")

    logger.info(
        "OpenAI SDK: base_url=%s, ключ из переменной %s",
        base_url or "(дефолт — api.openai.com)",
        key_from,
    )
    return OpenAI(**client_kwargs)


def _chat_json_object(
    client: OpenAI,
    *,
    model: str,
    system: str,
    user: str,
    temperature: float = 0.2,
) -> dict[str, Any]:
    try:
        completion = client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
        )
    except Exception as exc:
        logger.error(
            "Сбой запроса к OpenAI (chat): %s",
            _exc_chain_text(exc),
            exc_info=logger.isEnabledFor(logging.DEBUG),
        )
        hint = (
            "Проверьте OPENAI_BASE_URL (для ProxyAPI: https://api.proxyapi.ru/openai/v1), VPN, файрвол. "
            "Для системного прокси переменные HTTPS_PROXY/HTTP_PROXY должны быть с префиксом http://…"
        )
        extra = _network_error_hint(exc)
        if extra:
            hint = f"{hint} {extra}"
        raise RuntimeError(
            f"Не удалось обратиться к API (OpenAI Chat): {_exc_chain_text(exc)}\n{hint}",
        ) from exc

    raw = completion.choices[0].message.content or "{}"
    raw = _strip_json_fence(raw)
    logger.info("Ответ чата получен, разбор JSON.")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("Невалидный JSON от модели (первые 500 символов): %s", raw[:500])
        raise RuntimeError(f"Модель вернула невалидный JSON: {exc}") from exc


def _call_openai(transcript: str) -> dict[str, str]:
    client = _build_openai_client()
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
    logger.info("OpenAI Chat: model=%r", model)
    logger.debug("Длина транскрипции: %s символов", len(transcript))

    data = _chat_json_object(
        client,
        model=model,
        system=SYSTEM_PROMPT,
        user=f"Транскрипция диалога:\n\n{transcript}",
        temperature=0.1,
    )
    return _normalize_payload(data, REQUIRED_KEYS)


def generate_site_preview_image(client: OpenAI, prompt: str) -> bytes | None:
    """
    Генерирует растровое превью через OpenAI Images API.
    На ProxyAPI модели DALL·E (dall-e-2/3) часто не поддерживаются — используйте gpt-image-1 и семейство gpt-image-*.
    """
    prompt = (prompt or "").strip()
    if not prompt:
        logger.warning("Пустой image_prompt — превью не генерируется.")
        return None

    model = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1").strip()
    size = os.getenv("OPENAI_IMAGE_SIZE", "1024x1024").strip()
    prompt = prompt[:4000]

    return _generate_site_preview_image_once(
        client,
        prompt,
        model=model,
        size=size,
        allow_dalle_fallback=True,
    )


def generate_marketplace_card_image(client: OpenAI, prompt: str) -> bytes | None:
    """
    Фон карточки маркетплейса: всегда модель gpt-image-1 (по требованию сценария).
    Размер и quality берутся из OPENAI_IMAGE_SIZE / OPENAI_IMAGE_QUALITY.
    """
    prompt = (prompt or "").strip()
    if not prompt:
        logger.warning("Пустой image_prompt — фон карточки не генерируется.")
        return None
    size = os.getenv("OPENAI_IMAGE_SIZE", "1024x1024").strip()
    prompt = prompt[:4000]
    return _generate_site_preview_image_once(
        client,
        prompt,
        model="gpt-image-1",
        size=size,
        allow_dalle_fallback=False,
    )


def _model_not_supported_message(exc: BaseException) -> bool:
    s = str(exc).lower()
    return "not supported" in s or "model not supported" in s


def _generate_site_preview_image_once(
    client: OpenAI,
    prompt: str,
    *,
    model: str,
    size: str,
    allow_dalle_fallback: bool,
) -> bytes | None:
    logger.info("OpenAI Images: model=%r, size=%r", model, size)
    kwargs: dict = {"model": model, "prompt": prompt, "n": 1}
    ml = model.lower()

    if ml.startswith("gpt-image"):
        # ProxyAPI: ответ уже в b64_json; параметр response_format не поддерживается
        # (https://proxyapi.ru/docs/openai-image-generation)
        kwargs["size"] = size
        q = os.getenv("OPENAI_IMAGE_QUALITY", "medium").strip()
        if q:
            kwargs["quality"] = q
    elif ml.startswith("dall-e-3"):
        kwargs["size"] = size
        kwargs["response_format"] = "b64_json"
        kwargs["quality"] = os.getenv("OPENAI_IMAGE_DALLE_QUALITY", "standard").strip()
    elif ml.startswith("dall-e-2"):
        kwargs["size"] = size
        kwargs["response_format"] = "b64_json"
    else:
        kwargs["size"] = size
        kwargs["response_format"] = "b64_json"

    try:
        response = client.images.generate(**kwargs)
    except Exception as exc:
        err_s = str(exc).lower()
        if (
            "response_format" in kwargs
            and "response_format" in err_s
            and ("unknown" in err_s or "invalid_request" in err_s)
        ):
            logger.info("Шлюз отклонил response_format — повтор без этого параметра.")
            kwargs.pop("response_format", None)
            try:
                response = client.images.generate(**kwargs)
            except Exception as exc2:
                exc = exc2
            else:
                return _decode_image_response(response)
        if (
            allow_dalle_fallback
            and _model_not_supported_message(exc)
            and ml.startswith("dall-e")
        ):
            logger.warning(
                "Модель %r на шлюзе не поддерживается для /images/generations "
                "(типично для ProxyAPI). Повтор с gpt-image-1.",
                model,
            )
            return _generate_site_preview_image_once(
                client,
                prompt,
                model="gpt-image-1",
                size=size,
                allow_dalle_fallback=False,
            )
        logger.warning(
            "Генерация изображения недоступна или ошибка API: %s. PDF будет без картинки.",
            _exc_chain_text(exc),
            exc_info=logger.isEnabledFor(logging.DEBUG),
        )
        return None

    return _decode_image_response(response)


def _decode_image_response(response: object) -> bytes | None:
    if not response.data:
        return None
    item = response.data[0]
    b64 = getattr(item, "b64_json", None)
    if not b64:
        return None
    try:
        return base64.standard_b64decode(b64)
    except Exception as exc:
        logger.warning("Не удалось декодировать b64 изображения: %s", exc)
        return None


def process_design_order_with_ai(text: str) -> dict[str, str]:
    """
    Отчёт по заказу на дизайн сайта: JSON из транскрипции + data URL превью (если удалось сгенерировать картинку).
    """
    transcript = (text or "").strip()
    if not transcript:
        raise ValueError("Пустая транскрипция.")

    logger.info("ИИ: отчёт «дизайн сайта» (чат + превью)")
    client = _build_openai_client()
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

    data = _chat_json_object(
        client,
        model=model,
        system=DESIGN_SYSTEM_PROMPT,
        user=f"Транскрипция брифа / переговоров по сайту:\n\n{transcript}",
    )
    normalized = _normalize_payload(data, DESIGN_REQUIRED_KEYS)

    png = generate_site_preview_image(client, normalized.get("image_prompt", ""))
    if png:
        b64s = base64.standard_b64encode(png).decode("ascii")
        normalized["preview_image_data_url"] = f"data:image/png;base64,{b64s}"
    else:
        normalized["preview_image_data_url"] = ""

    return normalized


def process_marketplace_card_with_ai(
    product_name: str,
    price: str,
    notes: str = "",
) -> dict[str, str]:
    """
    Карточка товара: JSON из названия/цены (чат) + data URL фона (Images, только gpt-image-1).
    """
    name = (product_name or "").strip()
    price_s = (price or "").strip()
    if not name or not price_s:
        raise ValueError("Укажите название товара и цену.")

    logger.info("ИИ: карточка маркетплейса (чат + фон gpt-image-1)")
    client = _build_openai_client()
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

    extra = (notes or "").strip()
    user_lines = [
        f"Название товара: {name}",
        f"Цена: {price_s}",
    ]
    if extra:
        user_lines.append(f"Дополнительно от заказчика:\n{extra}")

    data = _chat_json_object(
        client,
        model=model,
        system=MARKETPLACE_SYSTEM_PROMPT,
        user="\n".join(user_lines),
        temperature=0.35,
    )
    normalized = _normalize_payload(data, MARKETPLACE_REQUIRED_KEYS)

    png = generate_marketplace_card_image(client, normalized.get("image_prompt", ""))
    if png:
        b64s = base64.standard_b64encode(png).decode("ascii")
        normalized["card_background_data_url"] = f"data:image/png;base64,{b64s}"
    else:
        normalized["card_background_data_url"] = ""

    return normalized


def process_dialog_with_ai(text: str) -> dict[str, str]:
    """
    Отчёт по клиентскому диалогу: OpenAI Chat Completions → поля PDF.
    """
    transcript = (text or "").strip()
    if not transcript:
        raise ValueError("Пустая транскрипция.")

    logger.info("ИИ: отчёт по диалогу клиента")
    return _call_openai(transcript)
