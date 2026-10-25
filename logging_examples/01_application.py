"""Explain a topic: application -> LangChain chain -> LLM."""
import logging
import os
import sys
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


def run_chain(topic):
    prompt = ChatPromptTemplate.from_template("Explain {topic} to a beginner in two short sentences.")
    chain = prompt | make_model()
    return chain.invoke({"topic": topic}).content


def application(topic):
    request_id = uuid4().hex[:8]
    started = perf_counter()
    logging.info("request_id=%s application.start", request_id)
    try:
        topic = " ".join(topic.split())  # Application work: clean and validate input.
        if not topic:
            raise ValueError("Enter a topic")
        logging.info("request_id=%s application.input_ready", request_id)
        result = run_chain(topic)
    except Exception as error:
        logging.error("request_id=%s application.error type=%s duration_ms=%.1f",
                      request_id, type(error).__name__, (perf_counter() - started) * 1000)
        raise
    logging.info("request_id=%s application.end duration_ms=%.1f",
                 request_id, (perf_counter() - started) * 1000)
    return result


if __name__ == "__main__":
    topic = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Docker"
    try:
        print(application(topic))
    except Exception:
        sys.exit(1)  # The error type is already logged; do not print credentials.
