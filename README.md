# HealthLink

A small appointment chat application. FastAPI handles HTTP requests, LangGraph
coordinates four agents, Redis stores sessions and conversation history, and a
SQLite clinic database stores sample doctors, anonymous users, and appointments.

## Request flow

```text
Frontend → FastAPI → session.py → Redis (validate session token)
                  → history.py → Redis (load conversation)
                  → graph.py → agents → LLM / tools.py → database.py
                  → history.py → Redis (save conversation)
                  → HTTP response → Frontend
```

There is no login or password flow. On first use the frontend calls `POST /session`.
The API creates an anonymous user ID in SQLite, generates a random token, and
stores the token-to-user mapping in Redis for 24 hours. Later requests send:

```text
Authorization: Bearer <token>
```

The API validates this token and passes the **user ID**, never the raw token,
to agents and tools. Redis stores each user's conversation separately. A short
Redis lock prevents overlapping turns for the same conversation.

## Agents

- **Symptom agent:** understands the conversation and asks for missing symptom details.
- **Doctor agent:** searches the clinic database for matching doctors.
- **Scheduling agent:** offers available slots, asks for a patient name when booking,
  requests explicit confirmation, and calls the booking tool.
- **Summary agent:** formats a confirmation from the saved booking facts.

`state.py` contains only the shared conversation data. `graph.py` defines nodes,
edges, and routing. `history.py` persists state between HTTP requests; no separate
LangGraph checkpoint service is needed.

Doctor recommendations never require a patient name. Slot selection alone does
not create a booking: the user must confirm. A database uniqueness constraint
prevents duplicate bookings for the same doctor/date/time. Retrying confirmation
returns the same appointment, including after a failed Redis history write.

## Run

Use Python 3.12. From this folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r api/requirements.txt -r frontend/requirements.txt
```

Copy the example configuration if you do not already have `api/.env`:

```bash
cp -n api/.env.example api/.env
```

Choose the provider and model once in `api/config.py`; all agents use them:

```python
MODEL_PROVIDER = "gemini"  # "openai", "openrouter", or "gemini" (alias: "google")
MODEL_NAME = "your-provider-model-id"
```

Set the matching key in `api/.env`: `OPENAI_API_KEY` for OpenAI,
`OPENROUTER_API_KEY` for OpenRouter, or `GEMINI_API_KEY` / `GOOGLE_API_KEY` for
Gemini. If both Gemini keys are set, `GEMINI_API_KEY` takes precedence. Other
providers' keys can remain empty. For example:

```dotenv
GEMINI_API_KEY=your-key
REDIS_URL=rediss://default:password@your-redis-host:6379/0
```

`REDIS_URL` is the full Redis connection URL, including credentials; use the URL
provided by your Redis service. A Redis HTTP/REST endpoint is not interchangeable.
Environment variables take precedence over `.env`.
Restart the API after changing configuration. The default provider remains
OpenRouter, and existing `OPENROUTER_MODEL` values work until you set
`MODEL_NAME` directly in `api/config.py`.

Start the API:

```bash
uvicorn main:app --app-dir api --host 0.0.0.0 --port 8000
```

In another terminal, from this folder:

```bash
source .venv/bin/activate
streamlit run frontend/app.py
```

Chat: http://localhost:8501 · API docs: http://localhost:8000/docs

The frontend only needs `API_BASE_URL` (default `http://localhost:8000`).
Model and Redis credentials remain in the API. **New chat** creates a fresh session;
it does not cancel an existing booking. Sessions expire after 24 hours. The clinic
calendar uses the API server's local clock and offers the next five weekdays.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/session` | Generate anonymous user ID and session token |
| POST | `/chat` | Send `{ "message": "I have a cold for 3 days" }` with the bearer token |
| GET | `/history` | Fetch the current user's messages with the bearer token |
| GET | `/doctors` | Browse doctors; optional `specialty` filter |
| GET | `/specialties` | List specialties |
| GET | `/health` | Check the API process without a model call |

In Swagger, call `/session`, then click **Authorize** and paste its token. Call
`/chat` with messages, choose a numbered slot, supply a name if asked, then confirm.
The response contains `reply`, `phase`, `available_slots`, and `booking`.

## Code map

```text
api/
  main.py             HTTP entry point
  session.py          Token generation and validation
  history.py          Redis history and turn lock
  state.py            Minimal shared graph state
  graph.py            LangGraph nodes, edges, and routing
  agents/             Four focused agents
  tools.py            Doctor search, availability, and booking tools
  database.py         SQLite users, doctors, and appointments
  doctors.json        Initial doctor data, seeded into SQLite
  llm.py              Model client and structured output parsing
  config.py           Environment loading and Redis connection
  schemas.py          HTTP and agent response models
frontend/
  app.py              Chat UI and bearer-token HTTP calls
```

SQLite creates `api/data/healthlink.db` automatically. Override `DATABASE_PATH` to
choose another location. Existing appointment records are preserved when upgrading.
Earlier SQLite conversation records are left untouched; new conversations use Redis.
The database and `.env` are excluded from Git and container images.

Appointments are stored in this classroom application; no real clinic is contacted.
Use sample patient details. This is not medical advice. Email is not implemented.
Deployment is a separate step; SQLite still needs durable storage before scaling.

## Verify

```bash
pip install -r api/requirements-test.txt
python -m unittest discover -s api -v
```

Tests use a temporary SQLite database, an in-memory Redis interface, and scripted
model responses. Application code always connects to the configured Redis and model.
