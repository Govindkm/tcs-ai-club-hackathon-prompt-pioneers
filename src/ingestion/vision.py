"""OCR/description for images via a local Ollama vision model.

Default OLLAMA_VISION_MODEL is "gemma4:31b-cloud" (Ollama cloud model), used for
both vision (OCR/image description) and text agent work so a single model_id
covers the whole pipeline. Other options (qwen2.5vl:latest, minicpm-v,
moondream, llama3.2-vision) remain compatible if you override the env var.

Pull whichever model you configure, e.g. `ollama pull gemma4:31b-cloud`, before use.
"""
from __future__ import annotations

import os
import time

import ollama

_OCR_PROMPT = (
    "Transcribe all visible text from this image exactly as written, "
    "preserving line breaks. If there is no readable text, briefly describe "
    "the image content instead."
)

_MAX_ATTEMPTS = 2
_RETRY_DELAY_SECONDS = 2


def _get_client() -> ollama.Client:
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    return ollama.Client(host=host)


def describe_image(image_bytes: bytes) -> str:
    """Run OCR/description on a single image via the configured Ollama vision model."""
    model = os.getenv("OLLAMA_VISION_MODEL", "gemma4:31b-cloud")
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    client = _get_client()
    last_error: Exception | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            response = client.generate(model=model, prompt=_OCR_PROMPT, images=[image_bytes], stream=False)
            return response["response"].strip()
        except Exception as exc:  # noqa: BLE001 - re-raised below with host/model context
            last_error = exc
            if attempt < _MAX_ATTEMPTS:
                time.sleep(_RETRY_DELAY_SECONDS)
    # The raw ollama-client error doesn't say which host/model it tried, which makes
    # this hard to diagnose - so wrap it with that plus the concrete remediation
    # (start Ollama, pull the model, then use the admin "Restart pipeline" action).
    raise ConnectionError(
        f"Could not reach Ollama vision model '{model}' at {host} after {_MAX_ATTEMPTS} attempt(s): {last_error}. "
        f"Start Ollama (`ollama serve`), pull the model (`ollama pull {model}`), then use the admin "
        "'Restart pipeline' action to retry this submission."
    ) from last_error
