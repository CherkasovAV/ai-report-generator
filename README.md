**[English version](README.en.md)**

# AI Report Generator

**Генератор структурированных бизнес-отчётов в PDF на базе LLM**

Сервис автоматически превращает текстовые транскрипты (диалоги с клиентами, брифы) в профессиональные PDF-документы. Поддерживает три режима: отчёт по диалогу, бриф на дизайн сайта с превью и карточку товара для маркетплейса.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

---

## 🚀 Возможности

| Режим | Что делает | Результат |
|-------|------------|-----------|
| **Client** | Анализирует диалог с клиентом | PDF с полями: клиент, тема, запрос, сроки/бюджет, продукт, тон, шаги |
| **Design** | Обрабатывает бриф на дизайн сайта | Структурированный бриф + промпт для генерации превью + изображение в PDF |
| **Marketplace** | Создаёт карточку товара по названию и цене | Готовая карточка с фоном от GPT-Image-1, описанием и ценой |

### Технические особенности

- **OpenAI-совместимый API** — работает с официальным OpenAI или шлюзами (ProxyAPI и др.)
- **Flask API** — интеграция в существующие процессы через `POST /generate`
- **Гибкий ввод** — файлы, stdin, интерактивный режим
- **Детальное логирование** — режим `-v` для отладки

---

## 📦 Структура проекта

```
ai-report-generator/
├── main.py                 # Точка входа, CLI + Flask API
├── utils/
│   ├── ai_processor.py     # LLM-обработка транскриптов
│   ├── pdf_generator.py    # Генерация PDF через WeasyPrint
│   └── logging_setup.py    # Настройка логирования
├── templates/
│   ├── report_template.html
│   ├── report_design_template.html
│   └── report_marketplace_template.html
├── input/                  # Примеры транскриптов
├── reports/                # Сгенерированные PDF (игнорируются Git)
├── requirements.txt
├── .env.example
└── README.md
```

---

## ⚙️ Установка

### Требования

- Python 3.10+
- API-ключ OpenAI или совместимого шлюза (например, [ProxyAPI](https://proxyapi.ru/))

### Шаги

```bash
# 1. Клонировать репозиторий
git clone https://github.com/CherkasovAV/ai-report-generator.git
cd ai-report-generator

# 2. Создать виртуальное окружение
python -m venv .venv

# 3. Активировать
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# 4. Установить зависимости
pip install -r requirements.txt

# 5. Настроить переменные окружения
cp .env.example .env
```

### Системные зависимости

**WeasyPrint** требует системные библиотеки. На Windows — установите [GTK3](https://docs.gtk.org/gtk3/getting_started/windows.html) или используйте [официальный installer WeasyPrint](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#installation).

На Linux:
```bash
# Debian/Ubuntu
sudo apt-get install libpango1.0-dev libharfbuzz-dev libffi-dev

# Fedora
sudo dnf install pango-devel harfbuzz-devel libffi-devel
```

---

## 🔐 Настройка окружения

Отредактируйте `.env`:

```env
# Ключ API (OpenAI или шлюз)
PROXY_API_KEY=your-api-key-here

# Базовый URL API (обязательно для шлюзов)
OPENAI_BASE_URL=https://api.proxyapi.ru/openai/v1

# Прямой ключ OpenAI (если есть — используется вместо PROXY_API_KEY)
# OPENAI_API_KEY=sk-...

# Модель для чата
OPENAI_MODEL=gpt-4o-mini

# Модель для генерации изображений (режим design)
OPENAI_IMAGE_MODEL=gpt-image-1
OPENAI_IMAGE_SIZE=1024x1024
OPENAI_IMAGE_QUALITY=medium
```

| Переменная | Обязательна | Описание |
|------------|-------------|----------|
| `PROXY_API_KEY` | Да* | Ключ шлюза (ProxyAPI и аналоги) |
| `OPENAI_BASE_URL` | Да* | URL API для шлюзов |
| `OPENAI_API_KEY` | Да* | Прямой ключ OpenAI |
| `OPENAI_MODEL` | Нет | Модель чата (по умолчанию `gpt-4o-mini`) |
| `OPENAI_IMAGE_MODEL` | Нет | Модель для изображений (по умолчанию `gpt-image-1`) |

\* Требуется один из вариантов: `OPENAI_API_KEY` **или** пара `PROXY_API_KEY` + `OPENAI_BASE_URL`

---

## 🎯 Использование

### Быстрый старт

```bash
# Запуск с примером
python main.py input/sample_transcript.txt

# Режим дизайна
python main.py --report design input/sample_design_transcript.txt

# Карточка товара
python main.py --report marketplace --product "Керамическая кружка 350 мл" --price "890 ₽"
```

### Интерактивное меню

```bash
python main.py
```

Меню предложит:
1. Отчёт по диалогу с клиентом
2. Бриф на дизайн сайта
3. Карточка товара для маркетплейса
0. Ввести путь к файлу или транскрипцию вручную

### Ввод транскрипции с клавиатуры

```bash
python main.py -i
```

Введите текст, затем `END` на отдельной строке для завершения.

### Подробное логирование

```bash
python main.py -v input/sample_transcript.txt
```

---

## 🔌 Flask API

### Запуск сервера

```bash
python main.py --serve --host 127.0.0.1 --port 5000
```

### Эндпоинты

#### `GET /health`

Проверка доступности сервиса.

```bash
curl http://localhost:5000/health
```

Ответ:
```json
{
  "status": "ok",
  "report_types": ["client", "design", "marketplace"]
}
```

#### `POST /generate`

Генерация отчёта.

**Для client/design:**
```bash
curl -X POST http://localhost:5000/generate \
  -H "Content-Type: application/json" \
  -d '{"transcript": "Текст диалога...", "report_type": "design"}'
```

**Для marketplace:**
```bash
curl -X POST http://localhost:5000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "report_type": "marketplace",
    "product_name": "Беспроводные наушники",
    "price": "4990",
    "notes": "Акцент на шумоподавлении"
  }'
```

Ответ:
```json
{
  "ok": true,
  "report": "reports/report_design_2024-05-14_15-30.pdf",
  "report_type": "design"
}
```

---

## 📄 Формат выходных данных

### Режим `client`

Извлекаемые поля:
- `client_name` — имя клиента
- `topic` — тема разговора
- `main_request` — основной запрос
- `deadlines_and_cost` — сроки и бюджет
- `product_essentials` — суть продукта
- `mood` — настроение/тон
- `next_steps` — следующие шаги

### Режим `design`

Извлекаемые поля:
- `client_name`
- `project_title`
- `order_summary`
- `pages_and_features`
- `visual_direction`
- `deadlines_and_budget`
- `image_prompt` — промпт для генерации превью (англ.)
- `next_steps`

### Режим `marketplace`

Генерируемые поля:
- `product_name` — название для карточки
- `price_display` — цена для отображения
- `description` — описание товара
- `image_prompt` — промпт для фона (англ.)

---

## ⚠️ Устранение неполадок

### Ошибка подключения (`Connection error`, `UnsupportedProtocol`)

1. Проверьте `OPENAI_BASE_URL` — должен включать схему (`https://...`)
2. Убедитесь, что ключ API действителен
3. При использовании прокси задайте `HTTPS_PROXY=http://host:port`

### Ошибки WeasyPrint (Windows)

```
GLib-GIO-WARNING ...
```

Это не ошибка — информационные сообщения GTK. При генерации без `-v` они скрыты.

### Flask API не отвечает

1. Убедитесь, что порт не занят другим процессом
2. Проверьте логи на наличие ошибок при старте сервера
3. Попробуйте другой порт: `--port 5001`

---

## 📝 Примеры использования

### Для агентств

Автоматизируйте создание брифов после звонков с клиентами:

```bash
python main.py --report design call_transcript.txt
```

### Для селлеров на маркетплейсах

Генерируйте карточки товаров пачками:

```bash
python main.py --report marketplace --product "Наушники" --price "4990"
```

### Для фрилансеров

Сохраняйте итоги встреч в структурированном виде:

```bash
python main.py meeting_notes.txt
```

---

## 🔒 Безопасность

- **Никогда не коммитьте `.env`** — в репозитории только `.env.example`
- **Ротируйте ключи** при подозрении на утечку
- **Ограничьте доступ** к Flask API в продакшене

Подробнее — в [SECURITY.md](SECURITY.md)

---

## 📄 Лицензия

MIT License — см. [LICENSE](LICENSE)

---

## 👤 Автор

**CherkasovAV**

GitHub: [@CherkasovAV](https://github.com/CherkasovAV)

---

## 🙋 Поддержка

- Вопросы и предложения: создайте Issue в репозитории
- Telegram: [@CherkasovAV](https://t.me/CherkasovAV)
- Email: [cherkasov83@yandex.ru](mailto:cherkasov83@yandex.ru)
