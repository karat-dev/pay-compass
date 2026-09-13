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
├── bot/
│   ├── handlers/          # Онбординг, главное меню, Stars, юридические команды
│   ├── keyboards/         # Inline клавиатуры шагов и меню
│   ├── states.py          # OnboardingStates & MainMenuStates
│   └── storage.py         # SupabaseStorage для FSM
├── config/
│   └── settings.py        # Pydantic Settings
├── database/
│   ├── client.py          # Асинхронный клиент к Supabase / PostgREST
│   ├── migrations/        # SQL DDL (16 таблиц)
│   └── repositories/      # Users, Sources, Countries
├── scrapers/              # Crawlee, Telethon, RSS fallback
├── texts/                 # Дословные тексты онбординга и политика 152-ФЗ
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

3. Примените SQL-миграции в Supabase SQL Editor:
Выполните скрипт из файла `database/migrations/001_initial_schema.sql`.

4. Запустите тесты:
```bash
python3 -m pytest -v tests/
```

5. Запустите бота:
```bash
python3 main.py
```

6. Запустите сбор данных (по расписанию Cron):
```bash
python3 run_scrapers.py
```
