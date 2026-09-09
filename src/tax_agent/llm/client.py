"""
Provider-agnostic LLM client.

OpenAI, DeepSeek, and Qwen (via Alibaba DashScope's OpenAI-compatible mode) are all
reachable through the *same* `openai` Python SDK, pointed at a different `base_url`.
This avoids maintaining three separate SDK integrations for what is, from this agent's
perspective, one HTTP call shape: chat completions in, text out.

Do not add a new provider-specific class unless that provider genuinely does not expose
an OpenAI-compatible endpoint — extend PROVIDER_CONFIG instead.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from openai import OpenAI


class LLMConfigError(RuntimeError):
    """Raised when no provider/API key is configured, or the config is inconsistent."""


@dataclass(frozen=True)
class ProviderSpec:
    base_url: str
    env_key_name: str
    env_model_name: str
    default_model: str


# One entry per supported provider. All are OpenAI-API-compatible endpoints.
PROVIDER_CONFIG: dict[str, ProviderSpec] = {
    "openai": ProviderSpec(
        base_url="https://api.openai.com/v1",
        env_key_name="OPENAI_API_KEY",
        env_model_name="OPENAI_MODEL",
        default_model="gpt-4.1",
    ),
    "deepseek": ProviderSpec(
        base_url="https://api.deepseek.com",
        env_key_name="DEEPSEEK_API_KEY",
        env_model_name="DEEPSEEK_MODEL",
        default_model="deepseek-chat",
    ),
    "qwen": ProviderSpec(
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        env_key_name="QWEN_API_KEY",
        env_model_name="QWEN_MODEL",
        default_model="qwen-plus",
    ),
}


def build_client() -> tuple[OpenAI, str]:
    """
    Read LLM_PROVIDER and the matching API key from the environment and return a
    ready-to-use (client, model_name) pair.

    Raises LLMConfigError with a clear, actionable message if nothing is configured —
    this is intentional. There is no default provider (per design decision: the client
    must explicitly choose one in .env), so this function must fail loudly rather than
    silently pick something.
    """
    provider = os.environ.get("LLM_PROVIDER", "").strip().lower()
    if not provider:
        raise LLMConfigError(
            "LLM_PROVIDER is not set. Copy .env.example to .env, set LLM_PROVIDER to "
            "one of: openai, deepseek, qwen, and fill in that provider's API key."
        )
    if provider not in PROVIDER_CONFIG:
        raise LLMConfigError(
            f"LLM_PROVIDER={provider!r} is not recognized. Valid options: "
            f"{', '.join(PROVIDER_CONFIG)}."
        )

    spec = PROVIDER_CONFIG[provider]
    api_key = os.environ.get(spec.env_key_name, "").strip()
    if not api_key:
        raise LLMConfigError(
            f"LLM_PROVIDER is set to {provider!r} but {spec.env_key_name} is empty. "
            f"Set {spec.env_key_name} in .env."
        )

    base_url = os.environ.get("LLM_BASE_URL_OVERRIDE", "").strip() or spec.base_url
    model = os.environ.get(spec.env_model_name, "").strip() or spec.default_model

    client = OpenAI(api_key=api_key, base_url=base_url)
    return client, model


def complete(system_prompt: str, user_prompt: str, *, temperature: float = 0.3) -> str:
    """
    Single-shot chat completion. Raises LLMConfigError if unconfigured, or lets the
    underlying openai SDK's exceptions propagate for network/API errors — callers
    should not silently swallow those, since a failed narrative call means the report
    should not proceed with a blank recommendations section.
    """
    client, model = build_client()
    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content or ""
