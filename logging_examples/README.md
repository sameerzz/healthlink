# Observe code as boxes

The same small application runs in all three examples:

```text
Application: clean input → Chain: build prompt → LLM: generate explanation
```

## 01: application logs

`01_application.py` is the original example. It logs at the application level
using a request ID. The inner chain and LLM are not observed separately.

## 02: observe application and chain boxes

```python
with observe("application", request_id) as application_id:
    # Application code happens here.
    run_chain(topic, request_id, application_id)

# Inside run_chain:
with observe("chain", request_id, parent_id=application_id) as chain_id:
    # Chain code happens here.
    chain.invoke(...)
```

`observe` logs **BEFORE**, runs the indented code, then logs **AFTER** with duration
and status. Each box receives its own `span_id`; a chain's span ID is its `chain_id`.
The application and chain have different span IDs and share one request ID.

## 03: add an inner LLM box

```python
# Inside the chain, when it calls the model:
with observe("llm", request_id, parent_id=chain_id) as llm_id:
    return make_model().invoke(prompt)
```

```text
BEFORE application  request_id=req1 span_id=app1   parent_id=-
  BEFORE chain      request_id=req1 span_id=chain1 parent_id=app1
    BEFORE llm      request_id=req1 span_id=llm1   parent_id=chain1
    AFTER llm       request_id=req1 span_id=llm1   parent_id=chain1 status=ok duration_ms=...
  AFTER chain       request_id=req1 span_id=chain1 parent_id=app1   status=ok duration_ms=...
AFTER application   request_id=req1 span_id=app1   parent_id=-      status=ok duration_ms=...
```

All indented work belongs to its box, including any inner boxes. An AFTER log is
also emitted if the code raises an error; its status becomes `error`. Each AFTER
log has the same span ID as that box's BEFORE log.

- **Trace** = the entire request, connected by `request_id`.
- **Span** = one observed box, identified by `span_id`.
- **Parent** = the enclosing box, identified by `parent_id`.

These are manual Python logging examples, not an OpenTelemetry integration.
The small `observe` helper is repeated in 02 and 03 so each file is standalone.

## Run

From the project folder containing `api/` and `logging_examples/`:

```bash
pip install -r logging_examples/requirements.txt
python logging_examples/01_application.py "rain"
python logging_examples/02_application_chain.py "rain"
python logging_examples/03_application_chain_llm.py "rain"
```

The scripts read `OPENROUTER_API_KEY` and `OPENROUTER_MODEL` from the existing
`api/.env`; shell environment variables take precedence. No Redis or API server
is required. Each command is one application request and uses your model account.
API keys and model request/response bodies are not logged. The answer is printed
separately as the application's output. No containers are involved.
