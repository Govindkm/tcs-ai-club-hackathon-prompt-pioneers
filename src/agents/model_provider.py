"""Model provider factory for Strands agents.

Reads STRANDS_MODEL_PROVIDER (and related env vars) so agents stay
model-agnostic and configuration is separated from agent/skill code.
"""
from __future__ import annotations

import json
import os
import re

from dotenv import load_dotenv

load_dotenv()

# Cloud "thinking" models (e.g. gemma4:*-cloud) leave message.content empty when
# reasoning is left on, and don't reliably honor the Ollama "format" JSON-schema
# constraint - they may reply with markdown-fenced JSON, free-form prose with a
# JSON object buried inside it, or valid JSON that ignores the requested shape
# entirely. Handle all of these here by also spelling the schema out in the
# prompt text (not just the "format" request field) and retrying once with a
# stronger, more explicit instruction if the first reply doesn't match.
_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


def _schema_note(schema: dict, *, strong: bool) -> str:
    required = schema.get("required", [])
    emphasis = (
        "Your previous reply did not match the required shape. This time, respond "
        if strong
        else "Respond "
    )
    return (
        f"\n\n{emphasis}with ONLY a single valid JSON object - no markdown, no code fences, "
        f"no explanation - with exactly these top-level keys: {required}. "
        f"Full JSON schema to match: {json.dumps(schema)}"
    )


def _extract_json_object(text: str) -> str | None:
    """Return the first balanced {...} substring in text, or None if none is found."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _build_thinking_safe_ollama_model(host: str, model_id: str):
    from strands.models.ollama import OllamaModel

    class ThinkingSafeOllamaModel(OllamaModel):
        async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):
            import ollama

            schema = output_model.model_json_schema()
            formatted_request = self.format_request(messages=prompt, system_prompt=system_prompt)
            formatted_request["format"] = schema
            formatted_request["stream"] = False
            formatted_request.setdefault("think", False)
            formatted_request["messages"] = [
                *formatted_request["messages"],
                {"role": "user", "content": _schema_note(schema, strong=False)},
            ]

            client = ollama.AsyncClient(self.host, **self.client_args)

            last_error: Exception | None = None
            for attempt in range(2):
                response = await client.chat(**formatted_request)
                content = _JSON_FENCE_RE.sub("", (response.message.content or "").strip()).strip()
                for candidate in (content, _extract_json_object(content)):
                    if not candidate:
                        continue
                    try:
                        yield {"output": output_model.model_validate_json(candidate)}
                        return
                    except Exception as e:  # noqa: BLE001 - try the next candidate/attempt
                        last_error = e
                if attempt == 0:
                    formatted_request["messages"] = [
                        *formatted_request["messages"],
                        {"role": "user", "content": _schema_note(schema, strong=True)},
                    ]

            raise ValueError(f"Failed to parse or load content into model: {last_error}")

    return ThinkingSafeOllamaModel(host=host, model_id=model_id)


def get_model():
    """Return a Strands model instance for the configured provider.

    Import of provider-specific classes is deferred so the SDK only needs
    the extras for the provider actually in use.
    """
    provider = os.getenv("STRANDS_MODEL_PROVIDER", "ollama").lower()

    if provider == "bedrock":
        from strands.models import BedrockModel

        return BedrockModel(
            model_id=os.getenv(
                "BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0"
            ),
            region_name=os.getenv("AWS_REGION", "us-east-1"),
        )

    if provider == "anthropic":
        from strands.models.anthropic import AnthropicModel

        return AnthropicModel(
            client_args={"api_key": os.getenv("ANTHROPIC_API_KEY")},
            model_id=os.getenv("ANTHROPIC_MODEL_ID", "claude-3-5-sonnet-latest"),
        )

    if provider == "openai":
        from strands.models.openai import OpenAIModel

        return OpenAIModel(
            client_args={"api_key": os.getenv("OPENAI_API_KEY")},
            model_id=os.getenv("OPENAI_MODEL_ID", "gpt-4o-mini"),
        )

    if provider == "ollama":
        return _build_thinking_safe_ollama_model(
            host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            model_id=os.getenv("OLLAMA_MODEL_ID", "gemma4:31b-cloud"),
        )

    raise ValueError(f"Unsupported STRANDS_MODEL_PROVIDER: {provider}")
