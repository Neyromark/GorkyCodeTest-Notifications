# GorkyCodeTest-Notifications

Сервис отложенных напоминаний. Бэкенд передаёт ему задачу и момент
`date_notify`, сервис держит задание в PostgreSQL и в назначенное время
отправляет сообщение VK-боту (`POST /api/v1/send-message`), а тот — пользователю.

Внутри: FastAPI (приём заявки) и `APScheduler` с `SQLAlchemyJobStore`
(хранение и выполнение заданий). Порт в контейнере — `8080`.

## Запуск

```bash
pip install -r requirements.txt          # Python 3.13
cp .env.example .env                     # заполните POSTGRES_PASSWORD
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Из корня репозитория:

```bash
docker network create app-network 2>/dev/null || true   # сеть объявлена как external
docker compose up -d --build notifications
```

Важно: сервис запускается **в один процесс** (`--workers 1` в `Dockerfile`).
У каждого процесса свой планировщик, поэтому несколько воркеров задублировали бы
отправку напоминаний.

## Переменные окружения

Читаются из `.env` (`pydantic-settings`, лишние ключи игнорируются) или из
окружения контейнера; значения из `environment` в `docker-compose.yml` имеют
приоритет над `.env`.

| Переменная | По умолчанию | Назначение |
| --- | --- | --- |
| `POSTGRES_PASSWORD` | — (обязательна) | Пароль БД; без него сервис не стартует |
| `POSTGRES_USER` / `POSTGRES_DB` | `postgres` / `tasks_db` | Учётные данные БД |
| `POSTGRES_HOST` / `POSTGRES_PORT` | `localhost` / `5432` | В compose — `postgres` / `5432` |
| `NOTIFICATION_SERVICE_URL` | `http://vkbottle_bot/api/v1/send-message` | Куда доставлять напоминание |
| `AUTH_TOKEN` | пусто | Если задан — уходит `Authorization: Bearer …` |
| `REQUEST_TIMEOUT` | `10` | Таймаут HTTP-запроса до бота, секунды |
| `MAX_DELIVERY_ATTEMPTS` | `5` | Предел попыток доставки |
| `RETRY_BASE_DELAY` | `30` | Базовая пауза перед повтором, секунды (далее удваивается) |
| `STALE_AFTER_SECONDS` | `900` | Не отправлять напоминание, если событие началось раньше этого срока |
| `TIMEZONE` | `UTC` | Часовой пояс планировщика |
| `APP_PORT` | `8000` | Порт сервиса на хосте (в контейнере всегда `8080`) |

Строка подключения собирается из этих полей (`settings.database_url`), пароль
URL-кодируется автоматически.

## API

### `POST /notifications`

```http
POST /notifications
Content-Type: application/json

{
  "type": "meeting",
  "date_notify": "2099-01-01T09:45:00Z",
  "user_id": 123,
  "title": "Созвон по проекту",
  "date": "2099-01-01T10:00:00Z"
}
```

```json
201 {"job_id": "notify_123_0f3c9a1b7d2e4c58"}
```

Проверки схемы (`app/schemas.py`):

* `type` — только `task` или `meeting`;
* `user_id > 0`, `title` — от 1 до 500 символов;
* `date_notify` должен быть в будущем и не позже `date`;
* время без часового пояса считается UTC, все моменты приводятся к UTC.

Нарушение правил — `422` с описанием. Интерактивная документация — `/docs`.

### Идемпотентность

`job_id` — `notify_<user_id>_<sha256 от содержимого, 16 hex>`. Одинаковый запрос
даёт одинаковый `job_id` и не создаёт второе задание (`replace_existing=True`),
а разные напоминания на одно и то же время не затирают друг друга.

## Как работает планировщик

* `BackgroundScheduler` с `SQLAlchemyJobStore` в той же PostgreSQL: задания
  переживают перезапуск контейнера.
* Задание — `date`-триггер на `date_notify` с `misfire_grace_time=None`
  (опоздавшее после простоя задание всё равно выполнится) и `coalesce=True`.
* `deliver()` перед отправкой проверяет устаревание: если текущий момент позже
  `date + STALE_AFTER_SECONDS`, напоминание пропускается с предупреждением.
* В payload при планировании кладётся `request_id` (UUID4). Повтор доставки
  идёт с тем же `X-Request-ID`, поэтому бот не отправит сообщение дважды; задания,
  сохранённые до появления `request_id`, получают его при первом запуске.
* Ошибка доставки (`DeliveryError`) планирует повтор через
  `RETRY_BASE_DELAY * 2^(attempt-1)` секунд (по умолчанию 30, 60, 120, 240 с);
  после `MAX_DELIVERY_ATTEMPTS` попыток задание сдаётся и пишется в лог.
* `DeliveryError` — сетевые сбои, `5xx` и `429`. Ответы `4xx` означают ошибку в
  самом запросе: они логируются и не повторяются.

### Формат сообщения

Доставка формирует текст (`app/delivery.py`):

```
Напоминание: Созвон по проекту
Время: 01.01.2099 13:00 МСК
```

Тело запроса к боту: `{"type": "message", "user_id": 123, "message": "..."}`,
заголовки — `Content-Type: application/json`, `X-Request-ID`, при заданном
`AUTH_TOKEN` — `Authorization: Bearer …`.

Время в тексте всегда приводится к Москве (`Europe/Moscow`), независимо от
часового пояса пользователя.

## Структура

```
app/
├── main.py       FastAPI-приложение, старт и остановка планировщика
├── api.py        POST /notifications
├── schemas.py    NotificationCreate, NotificationCreated, валидация
├── scheduler.py  job_id, schedule(), deliver(), повторы
├── delivery.py   форматирование и HTTP-запрос к боту
└── config.py     Settings (pydantic-settings), database_url
tests/
├── conftest.py       TestClient и планировщик в памяти (MemoryJobStore)
├── test_api.py       контракт эндпоинта и валидация
├── test_scheduler.py планирование, идемпотентность, повторы, устаревание
└── test_delivery.py  заголовки, формат сообщения, коды ответов
```

## Тесты

```bash
# 1. БД нужна тестам API: приложение поднимает постоянный планировщик
cd .. && docker compose up -d postgres && cd Notifications

# 2. Прогон (пароль должен совпадать с паролем БД)
POSTGRES_PASSWORD='<пароль БД>' pytest -q
```

`POSTGRES_PASSWORD` обязателен, потому что `Settings` требует его уже на импорте.
29 тестов: `test_scheduler.py` и `test_delivery.py` обходятся планировщиком в
памяти (фикстура подменяет `app.scheduler.scheduler` на `MemoryJobStore`), а
`test_api.py` работает через `TestClient` — тот выполняет `lifespan` приложения,
который стартует настоящий `SQLAlchemyJobStore` и создаёт в PostgreSQL таблицы
заданий. Поэтому тестам API нужен доступный сервер БД по адресу из
`POSTGRES_HOST`/`POSTGRES_PORT`, а без него прогон зависает на подключении.

## Замечания

* Планировщик не разделяет задания между экземплярами — масштабировать сервис
  горизонтально без внешней блокировки нельзя.
* `GET /notifications` и отмена напоминания не реализованы; удаление задания —
  только через БД/планировщик.
