# Grok и продуктовые обсуждения на ветке

Цель: обсуждать **продукт**, не код, с контекстом репозитория.

## Cursor Cloud Agent (рекомендуется)

1. Открыть репозиторий **karat-dev/flight-navigator**, ветка `cursor/unified-smart-travel-monorepo-c22f` (или актуальная `cursor/*-c22f`).
2. В запросе явно указать: «читай `docs/product/PRODUCT_BRIEF.md` и `docs/MONOREPO.md`».
3. Для модели с Grok в Cursor — выбрать Grok в UI агента; правила подхватят `.cursor/rules/product-context.mdc`.

## X / Grok (MCP)

Если подключён плагин X:

1. Убедиться, что MCP X авторизован.
2. В чат с Grok передать краткий контекст из `PRODUCT_BRIEF.md` + ссылку на PR/ветку flight-navigator.
3. Дорогие вызовы (поиск по постам) — только после явного согласования.

## Telegram @smarttttravel

Продуктовый канал для пользователей; **не** замена Grok. Бот Pay Compass — отдельный `@` (см. `BOT_NAME` в `.env`). После объединения согласовать один бренд в `/start` и на лендинге.

## Что обновлять после решений Grok

- `docs/product/PRODUCT_BRIEF.md` — roadmap и open questions  
- `docs/MONOREPO.md` — если меняется архитектура или Supabase  
- Issue/PR в flight-navigator с меткой `product`
