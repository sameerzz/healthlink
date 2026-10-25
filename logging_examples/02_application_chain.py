"""Explain a topic: application -> LangChain chain -> LLM."""
import logging
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from dotenv import dotenv_values
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
settings = {**dotenv_values(Path(__file__).resolve().parents[1] / "api" / ".env"), **os.environ}


def make_model():
    return ChatOpenAI(
        api_key=settings["OPENROUTER_API_KEY"],
        model=settings["OPENROUTER_MODEL"],
        base_url="https://openrouter.ai/api/v1",
        temperature=0,
        max_tokens=150,
        timeout=30,
        max_retries=0,
    )


@contextmanager
def observe(name, request_id, parent_id="-"):
    """Log before and after the code inside this box."""
    span_id = uuid4().hex[:8]
    started = perf_counter()
    status = "ok"
    logging.info("BEFORE %s request_id=%s span_id=%s parent_id=%s",
                 name, request_id, span_id, parent_id)
    try:
        yield span_id  # Run the code inside the with block.
    except Exception:
        status = "error"
        raise
    finally:
        logging.info("AFTER %s request_id=%s span_id=%s parent_id=%s status=%s duration_ms=%.1f",
                     name, request_id, span_id, parent_id, status,
                     (perf_counter() - started) * 1000)


def run_chain(topic, request_id, application_id):
    with observe("chain", request_id, parent_id=application_id) as chain_id:
        # Everything indented here is inside the chain box.
        prompt = ChatPromptTemplate.from_template("Explain {topic} in two short sentences.")
        chain = prompt | make_model()
        return chain.invoke({"topic": topic}).content


def application(topic):
    request_id = uuid4().hex[:8]
    with observe("application", request_id) as application_id:
        # Everything indented here is inside the application box.
        topic = " ".join(topic.split())
        if not topic:
            raise ValueError("Enter a topic")
        return run_chain(topic, request_id, application_id)


if __name__ == "__main__":
    topic = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "rain"
    try:
        print(application(topic))
    except Exception:
        sys.exit(1)
