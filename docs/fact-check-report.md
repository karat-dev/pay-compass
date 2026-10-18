# Отчёт проверки фактов

Скрипт `scripts/fact_check_report.py` читает `database/data/countries.json` и `config/trust_config.json` и печатает отчёт. Он не меняет справочник, конфиг и базу. Зоны в продукте остаются как записаны.

«Автоматически» в этом документе значит: помощник владельца может выполнить предложенное действие без повторного вопроса. Сам прогон файл не переписывает.

Прогон: вручную в GitHub Actions, каждый понедельник в 09:00 по Москве (`0 6 * * 1` UTC) и при push в `main` файлов `database/data/countries.json` или `config/trust_config.json`. Расписание и push не передают inputs: охват тогда весь справочник. Скрипт по-прежнему ничего не записывает.

## Правило повышения и понижения

Принято владельцем 18.10.2026. Та же формулировка лежит в черновике аудита, раздел 7.0 файла `docs/fact-checking-audit.md`. Пока тот черновик не влит в main, рабочая копия правила — этот раздел.

| Действие | Когда | Поле в JSON |
| --- | --- | --- |
| Понизить | Записанная зона выше зоны по текущей формуле | `suggested_action: downgrade`, `automatic: true` |
| Поднять до жёлтого | Не меньше 3 независимых свежих подтверждений: разные люди или разные площадки. Перепечатка одного источника — одно подтверждение. Голое поле `reports` независимость не доказывает | `upgrade_candidate`, `upgrade_to: yellow`, `automatic: true` |
| Поднять до зелёного | Страница банка, оператора или ведомства открылась и сверка текста разрешена (`content_confirmed: true`) | `upgrade_candidate`, `upgrade_to: green`, `automatic: true` |
| Зелёный только из отзывов | Формула даёт зелёный, а держат его отзывы, даже если их много | `owner_decision`, `automatic: false`, `owner_prompt`: «N подтверждений, поднять до зелёного?» |

Свежее подтверждение — не старше верхней планки свежести (сейчас 30 дней). HTTP 2xx без сверки текста зелёный не включает: действие будет `owner_manual_check`. Пока HTTP в прогоне выключен, для такого факта действие `rerun`.

Сайт-гид, помеченный в данных как official, для зелёного не считается. Список банков, операторов и доменов `.gov` / `.go.th` / `.go.jp` живёт в `is_official_publisher` в скрипте.

Если зелёный уже стоит на одних отзывах, отчёт просит решение владельца и не задаёт вопрос «поднять»: поднимать уже некуда.

## Сводка

Человеческий текст на русском. Счётчики:

- проверено — все карточки в охвате;
- сошлось — записанная зона равна зоне формулы, баллы её держат;
- не сошлось — записанная зона и зона формулы различаются;
- устарело — зона формулы та же, но баллы уже слабее записанной зоны или свежесть в файле не совпала с пересчётом;
- не смогли проверить — пробел, совет или нет данных для формулы;
- нужно решение владельца — карточки с пометкой `decision_needed`.

Раздел «Ручные проверки владельца» нумерует карточки с `needs_owner_check`.

## Схема JSON

`schema_version`: **1**. Файл пишется только если передан `--json`.

Корень:

| Поле | Смысл |
| --- | --- |
| `schema_version` | `1` |
| `generated_at` | Время сборки, ISO 8601 со смещением |
| `as_of` | Дата, на которую считается свежесть, `YYYY-MM-DD` |
| `scope` | `all` или `country` |
| `country` | Slug или `null` |
| `scope_label` | Подпись охвата |
| `http_checked` | Был ли запрошен обход ссылок |
| `rules` | `config/trust_config.json` |
| `upgrade_rule` | Краткая копия правила выше |
| `summary` | Счётчики |
| `facts` | Одна запись на карточку |

Карточка:

| Поле | Смысл |
| --- | --- |
| `fact_id` | Тот же идентификатор, что в мини-приложении: `{scope}:{sha256(scope + перевод строки + text)[:16]}` |
| `country` | Slug страны |
| `category` | Раздел: checklist, pay_on_site, wallets, local_card, cash, atms, transport, risks, tax_free |
| `instruction_id` | Идентификатор инструкции или `null` |
| `text` | Текст карточки |
| `current_zone` | Зона в файле |
| `computed_zone` | Зона формулы с флагами `refuted`, `contradicted_by_own`, `verified_by_us`. У пробела и совета `null` |
| `score_zone` | Зона одних баллов, без надбавки «проверено нами» |
| `score` | Сумма баллов или `null` |
| `status` | `ok`, `fail`, `stale`, `inconclusive` |
| `reason` | Почему такое действие |
| `source_urls` | HTTP-ссылки из поля `source` |
| `public_source_url` | Ссылка, которую можно показать путешественнику, или `null` |
| `http_results` | См. ниже. Пусто, если HTTP выключен |
| `last_check_date` | `date_verified` или `checked_at`, `YYYY-MM-DD` |
| `suggested_action` | Одно из значений ниже или `null`, если делать нечего |
| `automatic` | Помощник может выполнить действие без нового вопроса |
| `upgrade_to` | `yellow`, `green` или `null` |
| `owner_prompt` | Дословно «N подтверждений, поднять до зелёного?» или `null` |
| `flags` | Служебные метки, отсортированы |

`suggested_action`:

| Значение | Смысл |
| --- | --- |
| `downgrade` | Понизить записанную зону до `computed_zone` |
| `fix_link` | Ссылка отсутствует на видимой карточке или отвечает 404/410 |
| `upgrade_candidate` | Кандидат на повышение. Куда — в `upgrade_to` |
| `rerun` | Повторить прогон: нет HTTP, таймаут, 5xx, 429 |
| `owner_decision` | Нужен ответ владельца. Текст вопроса в `reason` или `owner_prompt` |
| `owner_manual_check` | Открыть источник или свою заметку руками |
| `null` | Зона сходится, отдельного шага нет |

`http_results[]`: `url`, `status_code`, `error`, `content_confirmed`. Обычный загрузчик всегда ставит `content_confirmed: false`: он только открывает страницу и читает начало ответа. Сверка формулировки в этот прогон не входит. 401 и 403 — блок, не битая ссылка.

`summary`: `checked`, `confirmed`, `not_confirmed`, `stale`, `could_not_check`, `needs_owner_decision`, `needs_owner_manual_check`, `gaps`, `unknown_zone`, `no_public_source`, `green_prompts`.

Идентификатор и набор полей версии 1 не переименовываются. Новое поле можно добавить. Ломающее изменение — новая `schema_version`.

## Telegram

После отчёта workflow вызывает `sendMessage` бота @TravelPaymentsGuideBot.

- Токен: секрет **`TELEGRAM_BOT_TOKEN`**. Это тот же секрет, что у бота. `BOT_TOKEN` не используется: в настройках он по умолчанию заглушка.
- Чат: секрет **`OWNER_TELEGRAM_CHAT_ID`**. Если секрета нет, чат `303653591`.
- Секрета токена нет — задание не падает. В сводку пишется, что нужно добавить `TELEGRAM_BOT_TOKEN` в Settings → Secrets and variables → Actions.
- Сообщение короче 4096 символов. Длинный текст режется, ссылка на прогон остаётся.
- Ссылка на прогон берётся из `GITHUB_SERVER_URL`, `GITHUB_REPOSITORY`, `GITHUB_RUN_ID`.

## Запуск локально

```bash
python3 scripts/fact_check_report.py --as-of 2026-10-18 --no-http
python3 scripts/fact_check_report.py --scope country --country georgia --json fact_check_report.json --text fact_check_report.txt
```

`--http` по умолчанию выключен. В workflow он включён. `--send-telegram` шлёт сообщение, только если задан `TELEGRAM_BOT_TOKEN`.
