# From example 03 to OpenTelemetry

Same application, same three code boxes:

```text
application
└── chain
    └── llm
```

In example 03, we wrote our own `observe` helper. Here OpenTelemetry provides it:

```python
with tracer.start_as_current_span("chain") as span:
    # The code of interest goes inside this box.
    ...
```

It automatically records the trace ID, each span's ID, parent ID, start and end
times, and any unhandled exception and error status. We no longer pass IDs around.
The duration is the difference between a span's start and end times.

## Record more than a message

```python
span.set_attribute("chain.name", "explain_topic")  # A fact about this box.
span.add_event("prompt_ready")                     # Something happened here.
```

| Box | Extra data we record |
|---|---|
| Application | Input length; input validated and answer ready events |
| Chain | Chain name; prompt ready event |
| LLM | Model name; input/output/total tokens; response length |

Token counts are included only when returned by the model provider. Missing
usage is not reported as zero. The API key, prompt, and answer are not added as
span attributes. Exception details are automatically captured, so use sample inputs.

On success the SDK's default span status is `UNSET` (no error). On an unhandled
exception it becomes `ERROR`, and an exception event is recorded automatically.

## Run

From the project folder containing `api/` and `telemetry/`:

```bash
pip install -r telemetry/requirements.txt
python telemetry/app.py "rain"
```

The example reads `OPENROUTER_API_KEY` and `OPENROUTER_MODEL` from the existing
`api/.env`. Shell environment variables take precedence. Model calls use your
provider account. No Redis, API server, collector, or cloud setup is needed.

Completed spans print as JSON in the terminal, innermost first: LLM, chain,
application. They share a `trace_id`; each has a different `span_id`. A child's
`parent_id` matches its parent's `span_id`.

To demonstrate a validation error without calling the model:

```bash
python telemetry/app.py " "
```

The application span will contain an exception event and `ERROR` status.

## Read the files in this order

1. `setup_telemetry.py`: small SDK setup and console exporter.
2. `app.py`: the three observed blocks and their attributes/events.

This lesson records **trace telemetry**. Token counts here are per-span attributes;
it does not yet create separate OpenTelemetry metric counters or histograms.
