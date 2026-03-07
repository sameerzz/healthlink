"""Unified LLM adapter with provider switch."""
import json
import logging
from typing import Any, Dict, Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from config.settings import Settings

logger = logging.getLogger("healthlink.llm")
T = TypeVar("T", bound=BaseModel)
SYSTEM_INSTRUCTION = "You are a helpful medical information assistant. Provide structured, accurate responses."


def _normalize_text(content: Any) -> str:
    return content if isinstance(content, str) else json.dumps(content)


def _strip_json_fence(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()


def _build_messages(prompt: str, system_instruction: Optional[str]) -> list:
    messages = []
    if system_instruction:
        messages.append(SystemMessage(content=system_instruction))
    messages.append(HumanMessage(content=prompt))
    return messages


class LLMClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.provider = settings.llm_provider.lower()
        self.model_name = settings.llm_model_name
        self.llm = self._build_chat_model()
        logger.info("LLM client initialized [provider=%s, model=%s]", self.provider, self.model_name)

    def _build_chat_model(self, temperature: Optional[float] = None, max_tokens: Optional[int] = None):
        temp = self.settings.llm_temperature if temperature is None else temperature
        tokens = self.settings.llm_max_tokens if max_tokens is None else max_tokens

        if self.provider == "openai":
            return ChatOpenAI(
                model=self.model_name,
                api_key=self.settings.openai_api_key,
                temperature=temp,
                max_tokens=tokens,
                max_retries=2,
            )
        if self.provider == "gemini":
            return ChatGoogleGenerativeAI(
                model=self.model_name,
                google_api_key=self.settings.gemini_api_key,
                temperature=temp,
                max_output_tokens=tokens,
                max_retries=2,
            )
        raise ValueError(f"Unsupported llm_provider: {self.provider}")

    def generate(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        system_instruction: Optional[str] = None,
    ) -> str:
        llm = self.llm if temperature is None and max_tokens is None else self._build_chat_model(temperature, max_tokens)
        response: AIMessage = llm.invoke(_build_messages(prompt, system_instruction))
        return _normalize_text(response.content)

    def generate_structured(
        self,
        prompt: str,
        response_schema: Type[T],
        temperature: Optional[float] = None,
        system_instruction: Optional[str] = None,
    ) -> T:
        llm = self._build_chat_model(temperature=temperature, max_tokens=self.settings.llm_max_tokens)
        structured_llm = llm.with_structured_output(response_schema)
        return structured_llm.invoke(_build_messages(prompt, system_instruction))


_llm_client: Optional[LLMClient] = None


def get_llm_client(settings: Settings) -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient(settings)
    return _llm_client


def _build_full_prompt(prompt: str, context: Optional[str]) -> str:
    full_prompt = f"TASK:\n{prompt}\n"
    if context:
        full_prompt += f"\nCONTEXT:\n{context}"
    return full_prompt


def _attempt_correction(data: Dict[str, Any], schema: Type[T], error: ValidationError) -> Optional[T]:
    try:
        corrected = data.copy()
        for err in error.errors():
            if err.get("type") != "missing":
                continue
            field_name = err.get("loc", [None])[0]
            field_info = schema.model_fields.get(field_name) if field_name else None
            if not field_info:
                continue
            if field_info.default is not None:
                corrected[field_name] = field_info.default
            elif field_info.annotation == str:
                corrected[field_name] = ""
            elif field_info.annotation == list:
                corrected[field_name] = []
            elif field_info.annotation == dict:
                corrected[field_name] = {}
        return schema(**corrected)
    except Exception as e:
        logger.warning("Correction attempt failed: %s", e)
        return None


def _generate_with_text_fallback(
    client: LLMClient,
    prompt: str,
    schema: Type[T],
    temperature: Optional[float],
    context: Optional[str],
) -> T:
    schema_description = json.dumps(schema.model_json_schema(), indent=2)
    fallback_prompt = (
        "You are a medical information assistant. Respond with ONLY valid JSON matching the schema below.\n\n"
        f"SCHEMA:\n{schema_description}\n\nTASK:\n{prompt}\n"
    )
    if context:
        fallback_prompt += f"\nCONTEXT:\n{context}\n"
    fallback_prompt += "\nRESPONSE (JSON only, no markdown, no explanation):"

    response_text = client.generate(prompt=fallback_prompt, temperature=temperature)
    cleaned = _strip_json_fence(response_text)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error("JSON decode error: %s. Response: %s", e, cleaned)
        raise ValueError(f"LLM returned invalid JSON: {e}")

    try:
        return schema(**parsed)
    except ValidationError as e:
        corrected = _attempt_correction(parsed, schema, e)
        if corrected is not None:
            return corrected
        raise


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def llm_generate(
    prompt: str,
    schema: Type[T],
    temperature: Optional[float] = None,
    context: Optional[str] = None,
    client: Optional[LLMClient] = None,
) -> T:
    if client is None:
        from config.settings import get_settings

        client = get_llm_client(get_settings())

    full_prompt = _build_full_prompt(prompt, context)
    try:
        result = client.generate_structured(
            prompt=full_prompt,
            response_schema=schema,
            temperature=temperature,
            system_instruction=SYSTEM_INSTRUCTION,
        )
        logger.info("Successfully generated and validated %s", schema.__name__)
        return result
    except Exception as e:
        logger.warning("Structured generation failed, falling back to text mode: %s", e)
        return _generate_with_text_fallback(client, prompt, schema, temperature, context)


async def llm_generate_async(
    prompt: str,
    schema: Type[T],
    temperature: Optional[float] = None,
    context: Optional[str] = None,
    client: Optional[LLMClient] = None,
) -> T:
    return llm_generate(prompt, schema, temperature, context, client)
