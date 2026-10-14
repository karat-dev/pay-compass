# Единый проект «Умный туризм» (монорепозиторий)

Три репозитория сходятся в **один монорепо** — один код, один Supabase, один продуктовый контур.

> **GitHub сегодня:** вся кодовая база и CI живут в репозитории [`karat-dev/pay-compass`](https://github.com/karat-dev/pay-compass) (исторически бот). Репозиторий [`karat-dev/flight-navigator`](https://github.com/karat-dev/flight-navigator) пока содержит только заглушку README — после мержа PR имеет смысл **переименовать** `pay-compass` в `flight-navigator` или сделать force-push main из pay-compass в flight-navigator и архивировать дубликат.

| Было | Роль | Сейчас |
|------|------|--------|
| `smart-travel-landing` | Лендинг «Умный туризм», Telegram @smarttttravel | `landing/` |
| `pay-compass` | Telegram-бот справочника по оплате за границей + БД | корень репо (`bot/`, `database/`, …) |
| `flight-navigator` | Оболочка продукта (авиа, калькуляторы, контент) | этот репозиторий |

## Supabase: один проект вместо двух

На free tier одновременно активны **2 проекта**. Рекомендуемая схема:

1. **Оставить один «продуктовый» проект Supabase** для flight-navigator (Postgres + миграции из `supabase/migrations/`).
2. **Лендинг с отдельного Supabase-проекта снять** (тот, что был только под static hosting):
   - Supabase Dashboard → старый landing-проект → **Pause project** (или удалить, если данные не нужны).
   - Освобождённый слот — для другого личного проекта или резерв.
3. **Хостинг лендинга** (на выбор, без второго Supabase):
   - **Vercel** (рекомендуется): один деплой — лендинг на `/`, бот на `/api/*` (см. `vercel.json`).
   - **Supabase Storage + CDN** в *том же* проекте, что и бот: bucket `landing`, загрузка `landing/index.html` (см. `docs/supabase-landing-hosting.md`).

### Секреты GitHub (один набор)

В `Settings → Secrets → Actions` репозитория **flight-navigator**:

- `SUPABASE_ACCESS_TOKEN`
- `SUPABASE_PROJECT_ID` — reference ID **единого** проекта
- `SUPABASE_DB_PASSWORD`

Workflow `.github/workflows/supabase_deploy.yml` накатывает миграции при пуше в `main`.

### Переменные приложения

Скопируйте `.env.example` → `.env`. `SUPABASE_URL` и `SUPABASE_KEY` — из **единого** проекта (service role для серверного бота).

## Деплой

| Компонент | Куда |
|-----------|------|
| Бот (webhook) | Vercel → `/api/set_webhook`, polling локально `python3 main.py` |
| Mini App | Vercel `/miniapp/`, локально `python3 -m miniapp` |
| Лендинг | Vercel `/` или Supabase Storage в том же project ref |
| Миграции | GitHub Actions → `supabase db push` |

## Архив старых репозиториев

После переключения доменов и секретов:

1. Зафиксировать в README `pay-compass` и `smart-travel-landing` ссылку: «код перенесён в [flight-navigator](…)».
2. Отключить отдельные Vercel/Supabase-привязки старых репо.
3. (Опционально) Archive на GitHub.

## Ветка для продуктовых обсуждений

Рабочая ветка агента: `cursor/unified-smart-travel-monorepo-c22f`.  
Контекст для Grok / Cloud Agent: `docs/product/PRODUCT_BRIEF.md` и `.cursor/rules/product-context.mdc`.
