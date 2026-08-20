"""OCR/description for images via a local Ollama vision model.

Recommended OLLAMA_VISION_MODEL:
- "minicpm-v"      (default) - ~8B, strong OCR on dense document scans/photos,
  runs well on the free-tier Colab Ollama server from
  notebooks/colab_ollama_server.ipynb. Best default for this platform since
  most images here are scanned certificates/forms/receipts.
- "moondream"      - ~1.8B, fastest/lightest, good for quick captions on
  CPU-only environments, but weaker at reading dense/small text.
- "llama3.2-vision" - ~11B, strong general-purpose vision-language model,
  best quality but needs more memory/GPU than the above.

Pull whichever model you configure, e.g. `ollama pull minicpm-v`, before use.
"""
from __future__ import annotations

import os

import ollama

_OCR_PROMPT = (
    "Transcribe all visible text from this image exactly as written, "
    "preserving line breaks. If there is no readable text, briefly describe "
    "the image content instead."
)


def _get_client() -> ollama.Client:
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    return ollama.Client(host=host)


def describe_image(image_bytes: bytes) -> str:
    """Run OCR/description on a single image via the configured Ollama vision model."""
    model = os.getenv("OLLAMA_VISION_MODEL", "minicpm-v")
    client = _get_client()
    response = client.generate(model=model, prompt=_OCR_PROMPT, images=[image_bytes], stream=False)
    return response["response"].strip()
