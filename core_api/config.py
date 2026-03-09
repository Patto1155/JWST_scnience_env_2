"""Configuration module for Science OS."""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


# Guardrails
MAX_STEPS_PER_RUN = int(os.getenv("MAX_STEPS_PER_RUN", "50"))
MAX_COST_PER_RUN = float(os.getenv("MAX_COST_PER_RUN", "10.0"))  # USD

# Sandbox directory
SANDBOX_DIR = Path(os.getenv("SANDBOX_DIR", "./runner_work"))

# Available models (OpenRouter slugs)
AVAILABLE_MODELS = {
    "claude-3.5-sonnet": "anthropic/claude-3.5-sonnet",
    "deepseek-v3.2": "deepseek/deepseek-v3.2",
    "grok-4.1-fast": "x-ai/grok-4.1-fast",
    "gemini-3-pro": "google/gemini-3-pro-preview",
    "gpt-5.1-codex-mini": "openai/gpt-5.1-codex-mini",
    "qwen3-next-80b-a3b-thinking": "qwen/qwen3-next-80b-a3b-thinking",
}

# LLM Configuration
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "anthropic/claude-3.5-sonnet")
LLM_API_URL = os.getenv("LLM_API_URL", "https://openrouter.ai/api/v1/chat/completions")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))

# OpenRouter specific
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", LLM_API_KEY)


def get_model_slug(model_name: str) -> str:
    """
    Get the full OpenRouter model slug from a short name.

    Args:
        model_name: Short name (e.g., 'claude-3.5-sonnet') or full slug

    Returns:
        Full OpenRouter model slug
    """
    # If it's already a full slug (contains '/'), return as-is
    if '/' in model_name:
        return model_name

    # Otherwise look it up in AVAILABLE_MODELS
    return AVAILABLE_MODELS.get(model_name, model_name)
