"""The same three boxes as example 03, observed using OpenTelemetry."""
import os
import sys
from pathlib import Path

from dotenv import dotenv_values
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI

from setup_telemetry import provider, tracer

settings = {**dotenv_values(Path(__file__).resolve().parents[1] / "api" / ".env"), **os.environ}


def call_llm(prompt):
    with tracer.start_as_current_span("llm") as span:
        span.set_attribute("llm.model", settings["OPENROUTER_MODEL"])
        model = ChatOpenAI(
            api_key=settings["OPENROUTER_API_KEY"],
            model=settings["OPENROUTER_MODEL"],
            base_url="https://openrouter.ai/api/v1",
            max_tokens=150, timeout=30, max_retries=0,
        )
        response = model.invoke(prompt)
        usage = response.usage_metadata or {}
        for name in ("input_tokens", "output_tokens", "total_tokens"):
            if name in usage:
                span.set_attribute(f"llm.{name}", usage[name])
        span.set_attribute("response.characters", len(response.content))
        return response


def run_chain(topic):
    with tracer.start_as_current_span("chain") as span:
        span.set_attribute("chain.name", "explain_topic")
        prompt = ChatPromptTemplate.from_template("Explain {topic} in two short sentences.")
        span.add_event("prompt_ready")
        chain = prompt | RunnableLambda(call_llm)
        return chain.invoke({"topic": topic}).content


def application(topic):
    with tracer.start_as_current_span("application") as span:
        span.set_attribute("input.characters", len(topic))
        topic = " ".join(topic.split())
        if not topic:
            raise ValueError("Enter a topic")
        span.add_event("input_validated")
        answer = run_chain(topic)
        span.add_event("answer_ready")
        return answer


if __name__ == "__main__":
    topic = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "rain"
    try:
        print("Answer:", application(topic))
    except Exception as error:
        print("Application failed:", type(error).__name__, file=sys.stderr)
        sys.exit(1)
    finally:
        provider.shutdown()
