"""Model provider factory for Strands agents.

Reads STRANDS_MODEL_PROVIDER (and related env vars) so agents stay
model-agnostic and configuration is separated from agent/skill code.
"""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def get_model():
    """Return a Strands model instance for the configured provider.

    Import of provider-specific classes is deferred so the SDK only needs
    the extras for the provider actually in use.
    """
    provider = os.getenv("STRANDS_MODEL_PROVIDER", "bedrock").lower()

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
        from strands.models.ollama import OllamaModel

        return OllamaModel(
            host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            model_id=os.getenv("OLLAMA_MODEL_ID", "llama3.1"),
        )

    raise ValueError(f"Unsupported STRANDS_MODEL_PROVIDER: {provider}")
