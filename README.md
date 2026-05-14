# AI Client Report Generator

Сервис на Python: вызывается **OpenAI** (Chat Completions), формируется **PDF** (Jinja2 + WeasyPrint). Режимы: **отчёт по диалогу клиента**, **отчёт по заказу на дизайн сайта** с превью и **карточка товара для маркетплейса** (фон из Images API + название, цена, описание на странице).

## Возможности

- **Отчёт `client`**: поля по диалогу (клиент, тема, запрос, сроки/стоимость, продукт, тон, шаги).
- **Отчёт `design`**: бриф на дизайн сайта из транскрипции + **англоязычный промпт** для генерации превью + **изображение** в PDF (если доступен Images API).
- **Отчёт `marketplace`**: по **названию товара и цене** чат (`OPENAI_MODEL`, по умолчанию `gpt-4o-mini`) возвращает JSON (название для карточки, цена для отображения, описание, **англ. промпт для картинки**); фон страницы — **`gpt-image-1`**; в PDF поверх фона — название, цена, описание.
- **OpenAI-совместимый** endpoint (официальный OpenAI или шлюз вроде **ProxyAPI** для чата; для картинок шлюз должен поддерживать `/images/generations`, иначе PDF будет без превью).
- **Логи** в stderr, **`-v`** для DEBUG.
- **Flask** API (`POST /generate`).

## Структура проекта

```
├── main.py
├── LICENSE
├── SECURITY.md
├── .gitignore
├── .gitattributes
├── .env.example
├── input/
│   ├── sample_transcript.txt
│   ├── sample_design_transcript.txt
│   └── sample_design_transcript_photo.txt
├── templates/
│   ├── report_template.html
│   ├── report_design_template.html
│   └── report_marketplace_template.html
├── reports/          # сюда пишутся PDF (.gitignore, в репо только .gitkeep)
├── utils/
│   ├── ai_processor.py
│   ├── pdf_generator.py
│   └── logging_setup.py
├── .env              # локально; в Git не входит
├── requirements.txt
└── README.md
```

## Установка

Нужен **Python 3.10+**. Рекомендуется виртуальное окружение.

### Windows (PowerShell)

```powershell
cd "D:\путь\к\папке\VPf10 Кейс 2 AI-автоматизация"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
notepad .env
```

### Linux / macOS

```bash
cd /path/to/project
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

**WeasyPrint** для PDF использует системные библиотеки. На Windows при проблемах смотрите [установку WeasyPrint](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#installation).

### Сообщения `GLib-GIO-WARNING` в консоли

Строки вида `GLib-GIO-WARNING ... UWP app ...` при запуске на Windows часто идут от GTK/WeasyPrint и **не означают**, что программа упала. Если в конце есть «Отчёт успешно создан», PDF сформирован нормально.

---

## Настройка `.env`

| Переменная | Описание |
|------------|----------|
| `PROXY_API_KEY` или `API_KEY` | Ключ шлюза (ProxyAPI) или запасной вариант имени переменной |
| `OPENAI_BASE_URL` | Базовый URL **OpenAI-совместимого** API (**обязателен**, если нет прямого `OPENAI_API_KEY` и используется только ключ шлюза) |
| `OPENAI_API_KEY` | Прямой ключ OpenAI (если задан, используется вместо `PROXY_API_KEY`) |
| `OPENAI_MODEL` | Модель для **чата** (JSON из транскрипции) |
| `OPENAI_IMAGE_MODEL` | Модель для **картинки** в режиме `design`. **Режим `marketplace`** для фона карточки **всегда** вызывает **`gpt-image-1`** (эта переменная на него не влияет). **ProxyAPI:** `gpt-image-1`, … — см. [документацию](https://proxyapi.ru/docs/openai-image-generation); DALL·E 3 на шлюзе часто **не** поддерживается. Для `gpt-image-*` запрос формируется **без** `response_format` (у ProxyAPI иначе ошибка `unknown_parameter`). Официальный OpenAI: можно `dall-e-3` |
| `OPENAI_IMAGE_SIZE` | Размер, например `1024x1024` (зависит от модели) |
| `OPENAI_IMAGE_QUALITY` | Для `gpt-image-*`: `low` / `medium` / `high` / `auto` |
| `OPENAI_IMAGE_DALLE_QUALITY` | Только для `dall-e-3`: `standard` или `hd` |

### Типы отчёта (`--report`)

| Значение | Описание |
|----------|----------|
| `client` | Отчёт по **диалогу с клиентом** (по умолчанию). Файл: `report_<имя>_....pdf` |
| `design` | Отчёт по **заказу на дизайн сайта**: структура брифа + промпт для превью + изображение. Файл: `report_design_<имя>_....pdf` |
| `marketplace` | **Карточка товара** для маркетплейса: без файла транскрипции — флаги `--product` и `--price` (опционально `--product-notes`). Файл: `report_marketplace_<товар>_....pdf` |

Примеры:

```powershell
python main.py input/sample_transcript.txt
python main.py --report design input/sample_design_transcript.txt
python main.py --report design input/sample_design_transcript_photo.txt
python main.py --report marketplace --product "Керамическая кружка 350 мл" --price "890 ₽"
python main.py --report marketplace --product "Беспроводные наушники" --price "4 990" --product-notes "Акцент на шумоподавлении"
```

Если шлюз **не проксирует** Images API или модель не поддерживается (на ProxyAPI для картинок нужны **`gpt-image-*`**, не `dall-e-3`), в логах будет предупреждение: в режиме **`design`** PDF создаётся **без** вставленной картинки (текст и промпт остаются); в режиме **`marketplace`** PDF всё равно собирается с **запасным градиентным фоном** вместо сгенерированного изображения.

---

### ProxyAPI

Ключ ProxyAPI **не** подходит к официальному `api.openai.com`: запросы нужно слать на хост ProxyAPI. Пример из [документации ProxyAPI](https://proxyapi.ru/docs):

```env
PROXY_API_KEY=ваш-ключ-из-кабинета
OPENAI_BASE_URL=https://api.proxyapi.ru/openai/v1
OPENAI_MODEL=gpt-4o-mini
```

Если задан только `PROXY_API_KEY` без `OPENAI_API_KEY`, приложение **потребует** `OPENAI_BASE_URL` и завершится с явной ошибкой, если база не указана. URL с префиксом `https://` (или `http://` для отладки).

### Другой OpenAI-совместимый шлюз

```env
PROXY_API_KEY=ваш-ключ
OPENAI_BASE_URL=https://ваш-шлюз/полный/путь/v1
OPENAI_MODEL=gpt-4o-mini
```

В логах (без раскрытия ключа) будет видно, **из какой переменной** взят ключ: `OPENAI_API_KEY`, `PROXY_API_KEY` или `API_KEY`.

---

## Как пользоваться (пошагово)

1. Активируйте venv и перейдите в папку проекта (см. выше).
2. Заполните `.env` (ключ и при необходимости `OPENAI_BASE_URL`).
3. Положите файлы транскрипций в папку **`input`** (или укажите путь к файлу при запуске с аргументом). Примеры лежат в `input/sample_*.txt`.
4. Запускайте команду **только** со строки `python ...`, без копирования приглашения `(.venv) PS D:\...>`.

### Запуск без аргументов (меню)

```powershell
python main.py
```

Откроется меню: **1** — отчёт по диалогу с клиентом, **2** — дизайн сайта, **3** — карточка маркетплейса. Для **1** и **2** показывается пронумерованный список **всех файлов** из папки **`input`** в корне проекта (при необходимости папка создаётся автоматически); введите **номер строки** (1…N). **0** — указать полный путь к файлу в другом месте или **`-`** для вставки транскрипции из консоли (Windows: **Ctrl+Z**, Enter; macOS/Linux: **Ctrl+D**). Для **3** — название товара и цену (дополнительное описание по желанию). Пока открыто меню или идёт ввод транскрипции с флагом **`-i`**, служебные сообщения уровня INFO в консоль не пишутся, чтобы не перебивать вопросы; после начала генерации PDF логи снова появляются (с **`-v`** — подробный DEBUG тоже после диалога).

Если задано `python main.py --report marketplace` без полной пары `--product` и `--price`, запрашиваются только недостающие поля (без выбора типа в меню).

### Быстрый тест

```powershell
python main.py input/sample_transcript.txt
```

При успехе:

`Отчёт успешно создан: reports/report_<имя_клиента>_YYYY-MM-DD_HH-MM.pdf` (если имя не извлечено — `reports/report_YYYY-MM-DD_HH-MM.pdf`).

### Свой файл

Укажите **реальный путь** к файлу:

```powershell
python main.py D:\Документы\диалог_01.txt
```

Если файл в текущей папке проекта:

```powershell
python main.py transcript.txt
```

### Ввод с клавиатуры

Строка `END` отдельной строкой завершает ввод:

```powershell
python main.py -i
```

### Ввод из stdin

```powershell
Get-Content .\input\sample_transcript.txt | python main.py -
```

### Подробные логи и traceback

```powershell
python main.py -v input/sample_transcript.txt
```

В режиме `-v` — уровень **DEBUG** и полный traceback при ошибке.

### Типичная ошибка в PowerShell

Если в буфер обмена попало **два приглашения** подряд, PowerShell может выдать «Непредвиденная лексема "PS"». Вставляйте **только** команду, начинающуюся с `python`.

---

## Ошибка «Connection error» / `UnsupportedProtocol`

1. **Не указан или неверен адрес шлюза.** Задайте `OPENAI_BASE_URL` (ProxyAPI: `https://api.proxyapi.ru/openai/v1`).
2. **Системный прокси.** `HTTPS_PROXY` / `HTTP_PROXY` должны быть **с схемой**, например `http://127.0.0.1:7890`.

Дополнительно: VPN, файрвол. Диагностика: `python main.py -v …`.

---

## Flask API

```powershell
python main.py --serve --host 127.0.0.1 --port 5000
```

С подробными логами: `python main.py --serve -v --port 5000`

- `GET /health` — проверка (в JSON есть `report_types`: `client`, `design`, `marketplace`).
- `POST /generate` — для `client` / `design`: JSON `{"transcript": "...", "report_type": "design"}` (`report_type` по умолчанию `client`), либо form `transcript` + `report_type`, либо multipart `file` + поле `report_type`. Для **`marketplace`**: JSON `{"report_type": "marketplace", "product_name": "…", "price": "…", "notes": "…"}` (поля `product` / `product_notes` допускаются как синонимы); либо те же поля в form-data **без** обязательного `transcript`.

Ответ при успехе: `{"ok": true, "report": "reports/....pdf", "report_type": "client"}`.

---

## Формат ответа модели

**Режим `client`:** поля `client_name`, `topic`, `main_request`, `deadlines_and_cost`, `product_essentials`, `mood`, `next_steps`.

**Режим `design`:** `client_name`, `project_title`, `order_summary`, `pages_and_features`, `visual_direction`, `deadlines_and_budget`, `image_prompt` (англ., для генератора картинок), `next_steps`; в PDF дополнительно встраивается сгенерированное изображение (`preview_image_data_url`).

**Режим `marketplace`:** из чата — `product_name`, `price_display`, `description`, `image_prompt` (англ.); в PDF — `card_background_data_url` (фон страницы, `gpt-image-1`).

Логика — в `utils/ai_processor.py`, шаблоны — в `templates/`, PDF — в `utils/pdf_generator.py`.

## Публикация на GitHub

1. Убедитесь, что в индекс **не** попадёт `.env` (он в `.gitignore`). Проверка: `git status` не должен показывать `.env`.
2. Создайте репозиторий на GitHub **без** README/LICENSE, если они уже есть локально (или объедините при первом push).
3. В каталоге проекта:

```bash
git init
git add .
git status   # просмотр: не должно быть .env, .venv/, PDF в reports/
git commit -m "Initial commit: AI report generator (client, design, marketplace)"
git branch -M main
git remote add origin https://github.com/<ваш-логин>/<имя-репо>.git
git push -u origin main
```

На Windows в PowerShell команды те же (при установленном [Git for Windows](https://git-scm.com/download/win)).

Подробнее про ключи — [SECURITY.md](SECURITY.md).

---

## Лицензия и использование

Код распространяется по лицензии **MIT** (см. файл [LICENSE](LICENSE)). Учебный/демонстрационный проект: ключи храните только в локальном `.env`, не коммитьте их в публичные репозитории.
