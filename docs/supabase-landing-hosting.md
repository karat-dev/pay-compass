# Лендинг в том же Supabase-проекте (без второго project)

Если лендинг раньше жил в **отдельном** Supabase только ради static site — перенесите файлы в проект бота.

## Storage + public bucket

1. Dashboard → **Storage** → New bucket `landing` → **Public**.
2. Upload `landing/index.html` (и assets, если появятся).
3. Включите **CDN** для bucket (Settings).
4. URL вида: `https://<project-ref>.supabase.co/storage/v1/object/public/landing/index.html`
5. (Опционально) Custom domain в Supabase → Settings → Custom domains.

## Остановка старого проекта

Dashboard → старый landing-only project → **Project Settings → General → Pause project**.

После паузы слот free tier снова доступен для другого проекта.
