# Social_Media

A production-shaped full-stack social network: **Django 5 + DRF** for the core app,
**FastAPI** for an isolated async AI microservice, **Celery + Redis** so no request ever
waits on a model provider, and **PostgreSQL** (SQLite for local dev).

Two deployable services, one repo, independent lifecycles.

---

## Architecture

```
                          ┌──────────────────────────────┐
        Browser ────────▶ │  Django (templates + BS5)    │
        (session auth)    │  social_media/               │
                          │  ├─ accounts   JWT + profile │
        API client ─────▶ │  ├─ posts      CRUD + feed   │
        (Bearer JWT)      │  ├─ social     follow/like/  │
                          │  │             comment       │
                          │  ├─ notifications  inbox     │
                          │  └─ ai_companion  client     │
                          └──────┬───────────────┬───────┘
                                 │               │
                       Celery task (async)       │ httpx (sync, timed)
                                 │               │
                          ┌──────▼──────┐        │
                          │ Redis broker│        │
                          └──────┬──────┘        │
                                 │               │
                    ┌────────────▼───┐           │
                    │ Celery worker  │           │
                    │  queue: ai     │           │
                    └────────────┬───┘           │
                                 │               │
                                 │  POST /moderate
                                 │  POST /caption      POST /mood-check
                                 ▼               ▼
                    ┌───────────────────────────────────────┐
                    │ FastAPI ai_service (async)            │
                    │  X-API-Key auth + per-key rate limit  │
                    │  ├─ provider: openai                  │
                    │  ├─ provider: huggingface             │
                    │  └─ provider: heuristic (fallback)    │
                    └───────────────┬───────────────────────┘
                                    │ httpx.AsyncClient (timeouts)
                                    ▼
                        OpenAI  /  HF Inference API

  Celery beat ──nightly 02:30──▶ mood sweep ──▶ MoodCheck ──▶ 3-day streak? ──▶ nudge
```

**Why this split.** Moderation and generation are slow, flaky and paid. Keeping them in a
separate async service means a model-provider outage degrades one feature instead of taking
the whole site down, and the AI service can be scaled, rate-limited and cost-audited on its
own. Django never blocks on it: post creation enqueues a Celery task and returns.

---

## Features

| Area | What's implemented |
|---|---|
| **accounts** | Signup/login (username *or* email), JWT access/refresh with rotation + blacklist, profile with avatar, bio, private accounts, change password |
| **posts** | Create/edit/delete (soft delete), image upload with type+size validation, home feed, explore, hashtags, edit re-triggers moderation |
| **social** | Follow/unfollow, follow *requests* for private accounts (accept/reject), likes (idempotent), threaded comments, notifications on every interaction |
| **notifications** | DB-backed inbox, unread badge (server-rendered + polled), mark read / mark all read, moderation + nudge notifications |
| **ai_companion** | Post moderation pipeline, caption suggestions, nightly mood sweep, dismissible wellbeing nudge, per-user rate-limited proxy endpoints |
| **Cross-cutting** | Structured JSON logs with request-id correlation, uniform DRF error envelope, DRF throttles, CORS, OpenAPI schema at `/api/docs/`, 160 tests |

---

## Quickstart (no Docker)

```bash
# 1. Dependencies (Python 3.11+)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pip install -r ai_service/requirements-dev.txt

# 2. Config
cp .env.example .env                       # edit DJANGO_SECRET_KEY
cp ai_service/.env.example ai_service/.env # keep API_KEYS in sync with AI_SERVICE_API_KEY

# 3. Database (SQLite by default; set DATABASE_URL for Postgres)
python manage.py migrate

# 4. Demo data (optional) — runs through the real moderation pipeline
python manage.py seed_demo
# login: rajeev / DemoPass!234

# 5. Run the AI service, then Django (two terminals)
cd ai_service && uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
python manage.py runserver 0.0.0.0:8000
```

| URL | What |
|---|---|
| http://localhost:8000 | Web UI (feed, profile, compose, notifications, check-ins) |
| http://localhost:8000/api/docs/ | OpenAPI / Swagger UI |
| http://localhost:8000/api/v1/ | JSON API |
| http://localhost:8000/healthz | Django health probe |
| http://localhost:8001/docs | AI service docs |
| http://localhost:8001/health | AI service probe |

### With real async workers

```bash
docker run -p 6379:6379 redis:7-alpine          # or use docker compose
export CELERY_TASK_ALWAYS_EAGER=False
celery -A social_media worker -l info -Q default,ai
celery -A social_media beat   -l info            # nightly mood sweep
```

### Docker Compose (everything at once)

```bash
docker compose up --build     # web:8000  ai:8001  postgres:5432  redis:6379
```

---

## API

All under `/api/v1/`. Auth: `Authorization: Bearer <access>`.

| Method | Path | Notes |
|---|---|---|
| POST | `/auth/register/` | Returns user + JWT pair |
| POST | `/auth/login/` | Username **or** email |
| POST | `/auth/token/refresh/` | Rotates the refresh token |
| POST | `/auth/logout/` | Blacklists the refresh token |
| GET/PATCH | `/auth/me/` | Own profile |
| POST | `/auth/me/password/` | Change password |
| GET | `/auth/users/<username>/` | Public profile (email never exposed) |
| GET | `/feed/` | Following + own posts |
| GET/POST | `/posts/` | Explore list / create (queues moderation) |
| GET/PATCH/DELETE | `/posts/<id>/` | Detail / edit / soft delete |
| GET | `/posts/<id>/moderation/` | Audit trail (author + staff only) |
| POST | `/posts/<id>/like/` | Idempotent toggle |
| GET/POST | `/posts/<id>/comments/` | List / add |
| POST | `/users/<username>/follow/` | Follow → unfollow → requested |
| GET | `/follow-requests/` | Pending requests |
| POST | `/follow-requests/<id>/accept|reject/` | Decide |
| GET | `/notifications/` | `?unread=1` filter |
| GET | `/notifications/unread-count/` | Polled by the navbar |
| POST | `/notifications/<id>/read/`, `/notifications/read-all/` | |
| POST | `/ai/caption/` | 2-3 suggestions (rate limited) |
| POST | `/ai/moderate/` | Dry-run check, creates nothing |
| GET | `/ai/mood/` | Own mood history + active nudge |
| GET/POST | `/ai/nudge/`, `/ai/nudge/<id>/dismiss/` | Wellbeing nudge |

### AI microservice (internal, `X-API-Key` required)

| Method | Path | Request → Response |
|---|---|---|
| POST | `/moderate` | `{text, post_id?, language}` → `{is_safe, flags[], scores[], confidence, reason, provider, degraded}` |
| POST | `/caption` | `{idea, tone?, count}` → `{suggestions[], provider, degraded}` |
| POST | `/mood-check` | `{texts[], user_id?}` → `{mood_signal, suggestion, posts_analyzed, …, disclaimer}` |
| GET | `/health` | public liveness |

---

## The three AI flows

**1. Moderation** — `posts.services.create_post()` writes the post as `pending`, then
`moderate_post_task.delay()` queues the check. The worker calls `/moderate` and
`apply_moderation_verdict()` transitions the state:

```
pending ──safe──▶ approved
pending ──unsafe──▶ flagged   (published, author told why)      MODERATION_POLICY=auto_publish
pending ──unsafe──▶ held      (not on any feed until reviewed)  MODERATION_POLICY=hold_unsafe
```

Nothing is ever silently dropped: `moderation_reason` is always recorded, the author gets a
notification, and staff can approve from the admin. If the AI service itself is down the task
retries with backoff and then applies `MODERATION_FAILURE_POLICY` — `fail_open` publishes but
keeps the post flagged and schedules a re-check; `fail_closed` holds it.

**2. Captions** — the compose page calls `/api/v1/ai/caption/`, which proxies to `/caption`.
Throttled at 20/user/hour on the Django side and again per API key on the service side.

**3. Nightly mood sweep** — Celery beat runs `run_mood_check_for_active_users` at 02:30,
fanning out one `check_user_mood_task` per active user. Each stores a `MoodCheck`. A nudge is
created **only** when:

* the signal is negative for `MOOD_NEGATIVE_STREAK_THRESHOLD` (default **3**) consecutive checks, **and**
* no nudge was created in the last `NUDGE_COOLDOWN_DAYS` (default **7**) days.

The nudge is a single, dismissible, non-blocking card ("Kaise ho? … this is not a diagnosis")
with a link to [findahelpline.com](https://findahelpline.com). It never diagnoses, never
labels, never blocks the user, and the mood history is visible only to its owner.

---

## Configuration

All secrets come from the environment (`python-decouple` on the Django side,
`pydantic-settings` on the AI side). See [`.env.example`](.env.example) and
[`ai_service/.env.example`](ai_service/.env.example).

| Variable | Default | Meaning |
|---|---|---|
| `DJANGO_ENV` | `dev` | `dev` or `prod` settings module |
| `DJANGO_SECRET_KEY` | dev placeholder | **Required in prod** — boot fails without it |
| `DATABASE_URL` | SQLite | Postgres DSN in production |
| `REDIS_URL` / `CELERY_BROKER_URL` | `redis://localhost:6379/0` | Broker + result backend |
| `CELERY_TASK_ALWAYS_EAGER` | `True` (dev) | Run tasks inline; set `False` with a real broker |
| `AI_SERVICE_BASE_URL` / `AI_SERVICE_API_KEY` | localhost | Django → AI service |
| `AI_RATE_LIMIT_PER_USER` | `20/hour` | Django-side AI budget |
| `MODERATION_POLICY` | `auto_publish` | `hold_unsafe` to hold instead |
| `MODERATION_FAILURE_POLICY` | `fail_open` | `fail_closed` to hold on outage |
| `API_KEYS` (AI service) | dev placeholder | Comma separated internal keys |
| `PROVIDER` | `heuristic` | `openai` / `huggingface` / `heuristic` |
| `ALLOW_HEURISTIC_FALLBACK` | `True` | Degrade to the local model on provider failure |
| `TOXICITY_THRESHOLD` / `SPAM_THRESHOLD` | `0.60` / `0.70` | Flag thresholds |

> **Gotcha:** `python-decouple` does *not* strip inline comments — keep `#` comments on
> their own line, otherwise the comment becomes part of the value.

---

## Tests & lint

```bash
pytest                                   # 106 Django tests
cd ai_service && pytest                  # 54 AI service tests
ruff check .                             # lint (both configs)
python manage.py check
python manage.py makemigrations --check --dry-run
```

Django tests run with `CELERY_TASK_ALWAYS_EAGER=True`, so the **real** task code executes
inline; the AI service is replaced by an `httpx.MockTransport`, so the real client (headers,
retries, timeouts, error mapping) is still exercised. The AI service tests use
`fastapi.TestClient` with no network access.

Covered: JWT lifecycle incl. blacklisting, feed/privacy rules, ownership permissions,
moderation state machine (safe/unsafe/hold/timeout/outage/malformed JSON), like and follow
idempotency, follow requests, notifications, nudge guardrails (threshold, cooldown, streak
reset), throttling, and Pydantic contract validation.

---

## Deployment (Render)

[`render.yaml`](render.yaml) is a blueprint for: Postgres, Redis, the Django web service
(+ `migrate` on deploy), a Celery worker, Celery beat, and the AI service.

1. New → Blueprint → pick this repo.
2. Set the secret vars (`API_KEYS` on the AI service, `AI_SERVICE_API_KEY` on Django and the
   worker — they must match; plus `OPENAI_API_KEY` or `HF_API_TOKEN` if you use a hosted model).
3. `DJANGO_ENV=prod` turns on HSTS, secure cookies, `X-Frame-Options: DENY` and requires a
   real `SECRET_KEY`.

CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs on every push/PR: ruff,
Django checks, missing-migration check, both test suites, and an integration job that boots
the AI service and asserts a real HTTP moderation call.

---

## Layout

```
social_media/        settings (base/dev/prod/test), urls, celery, wsgi, asgi
accounts/            custom user, JWT auth, profile
posts/               Post model, feed manager, moderation service layer
social/              Follow / Like / Comment + services
notifications/       inbox model, services, API, polling endpoint
ai_companion/        AI HTTP client, Celery tasks, MoodCheck, WellbeingNudge
common/              JSON logging, middleware, throttles, permissions, error envelope
templates/ static/   Bootstrap 5 UI
ai_service/          FastAPI microservice (app/{core,schemas,providers,routers}, tests)
infra/               Redis image for Render
```

## Key decisions

* **Profile fields on the user model**, not a 1:1 `Profile` — the feed joins users constantly.
* **Service layer** (`posts/services.py`, `social/services.py`) so the API, UI, tasks and
  management commands can't drift on business rules.
* **Soft delete for posts** — moderation history and notifications stay consistent.
* **Follow requests are `Follow(is_active=False)`**, not a second table — one index answers
  "requests I need to review".
* **DB-backed notifications** with a polling endpoint: durable, queryable, and a websocket
  fan-out is a one-line addition in `notifications.services.notify()`.
* **`with_counts()` prefetch** on every feed query to avoid N+1 on like/comment counts.
* **Heuristic provider as a first-class fallback** — moderation stays available (and free)
  when a hosted model is down; `degraded: true` keeps the audit trail honest.
