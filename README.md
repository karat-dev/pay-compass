# Flight Navigator — «Умный туризм» (монорепозиторий)

Единый репозиторий: **лендинг** (`landing/`), **Telegram-бот Pay Compass** (корень), **Supabase** (`supabase/`).  
План миграции с трёх репо и один Supabase: [`docs/MONOREPO.md`](docs/MONOREPO.md).  
Продуктовый контекст для Grok / агентов: [`docs/product/PRODUCT_BRIEF.md`](docs/product/PRODUCT_BRIEF.md).

---

# Независимый справочник по платежам за границей (Telegram Bot + Канал)

Архитектурный каркас Telegram-бота и системы сбора данных для российских путешественников.
Продукт **не продает** виртуальные карты и **не берет** комиссии с транзакций, предоставляя независимую, верифицированную информацию с обязательным указанием источника, даты проверки и confidence score.

---

## 🚀 Архитектурные особенности

1. **Дословный FSM Онбординг (5 шагов)**:
   - Полное соблюдение 152-ФЗ: обязательное информированное согласие на Шаге 4 без возможности пропуска в главное меню.
   - Команда `/privacy` и кнопка «Политика конфиденциальности».
   - Команды `/my_data` (выгрузка данных субъекта) и `/delete_me` / `/delete_account` (право на забвение).

2. **Persistent FSM State & Возобновление**:
   - Кастомный асинхронный `SupabaseStorage` для `aiogram 3.x`.
   - Состояния и контекст сохраняются в таблице `user_states`.
   - Мягкое возобновление: при паузе > 24 часов бот предлагает продолжить или начать заново.

3. **Модель монетизации и лимитов**:
   - **Бесплатный уровень**: 1 страна в 7 дней (таблица `user_country_access`), базовые верифицированные факты.
   - **Премиум-доступ**: покупка через **Telegram Stars (XTR)** на **90 дней** без рекуррентных рисков. Все страны, алерты реального времени.

4. **Мультиисточниковый сбор с отказоустойчивостью**:
   - Официальные источники (РСХБ, АТБ) через `Crawlee` с экспоненциальным backoff (5 попыток) и записью инцидентов в `source_health`.
   - Публичные каналы Telegram через `Telethon` (поддержка `StringSession` и fallback-мока).
   - СМИ через RSS-фолбэк (`feedparser`: Banki.ru, TourDom, Profi.Travel).

---

## 🛠 Структура проекта

```text
.
├── landing/               # Статический лендинг «Умный туризм» (ex smart-travel-landing)
├── miniapp/               # Telegram Mini App: основной интерфейс
├── docs/                  # MONOREPO, Supabase hosting, product brief, Grok
├── bot/
│   ├── handlers/          # /start открывает Mini App; старые callback-и ещё живы
│   ├── keyboards/         # Клавиатура входа и старые inline-меню
│   ├── notifications.py   # Уведомления со ссылкой на экран Mini App
│   ├── states.py          # OnboardingStates & MainMenuStates
│   └── storage.py         # SupabaseStorage для FSM
├── config/
│   └── settings.py        # Pydantic Settings
├── database/
│   ├── client.py          # Асинхронный клиент к Supabase / PostgREST
│   ├── knowledge_base.py  # Страны, факты, инструкции
│   ├── miniapp_catalog.py # Публичный каталог для Mini App (без оценок)
│   ├── miniapp_store.py   # Профиль, поездка, прогресс, сообщения о неточностях
│   ├── migrations/        # SQL DDL
│   └── repositories/      # Users, Sources, Countries
├── api/                   # Vercel: вебхук бота и /api/catalog, /api/miniapp/*
├── scrapers/              # Crawlee, Telethon, RSS fallback
├── texts/                 # Тексты онбординга и политика 152-ФЗ
├── tests/                 # Модульные тесты
├── main.py                # Точка входа бота
├── run_scrapers.py        # Cron runner сбора данных
├── requirements.txt
└── .env.example
```

---

## ⚙️ Установка и запуск

1. Склонируйте репозиторий и установите зависимости:
```bash
pip install -r requirements.txt
```

2. Настройте конфигурацию:
```bash
cp .env.example .env
# Заполните BOT_TOKEN, SUPABASE_URL, SUPABASE_KEY
```

3. Примените SQL-миграции в Supabase:
   - **Автоматически через GitHub Actions**: добавьте в секреты GitHub репозитория (`Settings -> Secrets and variables -> Actions`):
     - `SUPABASE_ACCESS_TOKEN` (токен из Supabase Dashboard -> Account -> Access Tokens)
     - `SUPABASE_PROJECT_ID` (Reference ID проекта из URL `https://supabase.com/dashboard/project/<id>`)
     - `SUPABASE_DB_PASSWORD` (пароль к базе, заданный при создании проекта)
     При любом пуше в `main` workflow `.github/workflows/supabase_deploy.yml` автоматически накатит миграции из `supabase/migrations/`.
   - **Либо вручную через Supabase SQL Editor**: откройте `database/migrations/001_initial_schema.sql` (или `supabase/migrations/20260913000000_initial_schema.sql`), вставьте его содержимое и нажмите **Run**.

4. Запустите тесты:
```bash
python3 -m pytest -v tests/
```

5. Запустите бота:
   - **Для локального запуска (Polling)**:
     ```bash
     python3 main.py
     ```
   - **Для деплоя на Vercel (Serverless Webhook)**:
     Подключите репозиторий в Vercel Dashboard, пропишите переменные окружения и один раз откройте в браузере:
     `https://<ваш-проект>.vercel.app/api/set_webhook` для автоматической привязки вебхука к Telegram.

6. Запустите сбор данных (по расписанию Cron):
```bash
python3 run_scrapers.py
```

---

## Telegram Mini App

Основной интерфейс — Mini App (`miniapp/`). Чат бота остаётся для уведомлений со ссылкой на экран и для кнопки меню / `/start`, которая открывает приложение. Факты не копируются вручную: `/api/catalog` собирает их из `database/data/countries.json`, `config/trust_config.json` и `database/data/routes/` теми же правилами зон, что и бот. Оценки и внутренние пометки в ответ не попадают. Факты ниже `display.default_min` (50) скрыты за «Показать непроверенное».

Локально, на реальных данных и без Telegram:

```bash
python3 -m miniapp
```

Откройте `http://127.0.0.1:4173/miniapp/`. Процесс включает `MINIAPP_DEV_AUTH` и пишет профиль в `miniapp/.local-data/` (файл в gitignore), пока Supabase не настроен. На Vercel этот флаг должен быть выключен.

### Переменные окружения

Уже нужные для бота: `BOT_TOKEN` (им проверяется подпись Telegram `initData`), `SUPABASE_URL`, `SUPABASE_KEY`.

| Переменная | Где | Зачем |
|---|---|---|
| `MINIAPP_URL` | Vercel и бот | Публичный https-адрес приложения, со слэшем на конце. Пример: `https://<проект>.vercel.app/miniapp/` |
| `SUPABASE_KEY` | только сервер | **service role** единого проекта. anon-ключ в браузер не кладём: RLS на таблицах Mini App без политик для anon |
| `MINIAPP_DEV_AUTH` | только локально | `1` принимает `initData` вида `dev:<telegram id>`. На Vercel не задавать |
| `MINIAPP_INITDATA_MAX_AGE_SECONDS` | сервер | Срок жизни `initData`, по умолчанию 86400 |

Секреты только в env. В репозиторий не коммитить.

### BotFather и кнопки

1. Menu Button → URL = значение `MINIAPP_URL` (`https://<проект>.vercel.app/miniapp/`).
2. После деплоя один раз откройте `https://<проект>.vercel.app/api/set_webhook`. Обработчик вешает вебхук и вызывает `setChatMenuButton` с тем же URL.
3. `/start` шлёт кнопку «Открыть приложение». Параметр `/start guide_china` открывает Китай. Так же работают `trip`, `guide`, `sos`, `profile`, `search`, `section_china_2_pay_on_site`, `instruction_wechat_pay`.
4. Уведомления собирайте через `bot.notifications.notification_message(text, screen)`: в чат уходит текст и кнопка на экран, не карточка справочника.
5. Прямая ссылка `t.me/<bot>/<short_name>?startapp=guide_china` заработает после того, как Mini App получит short name в BotFather. Кнопка меню от short name не зависит.

### Vercel

Тот же проект, что и лендинг. `vercel.json` отдаёт `/miniapp/` как статику, `/api/*` — в `api/index.py`, остальное — лендинг. Отдельный сервер не нужен.

Эндпоинты: `GET /api/catalog` (публичный), `GET /api/miniapp/config`, `POST /api/miniapp/session|onboarding|profile|trip|progress|report`. Запись требует заголовок `X-Telegram-Init-Data`.

### Supabase

Накатите миграцию `supabase/migrations/20261014000000_miniapp.sql` (таблицы `miniapp_profiles`, `miniapp_trips`, `miniapp_progress`, `miniapp_fact_reports`). Тот же SQL лежит в `database/migrations/002_miniapp.sql`.

GitHub Actions катит `supabase/migrations/` при пуше в `main`, если заданы `SUPABASE_ACCESS_TOKEN`, `SUPABASE_PROJECT_ID`, `SUPABASE_DB_PASSWORD`. Либо вставьте файл в SQL Editor.

Команда `/delete_me` удаляет и эти строки. Сообщения о неточности пишутся в `miniapp_fact_reports` (у фактов из JSON нет UUID в `verified_facts`).

Согласие по 152-ФЗ спрашивается в онбординге Mini App. В чате по-прежнему есть `/privacy`, `/my_data`, `/delete_me`.
