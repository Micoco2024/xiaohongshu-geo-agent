"""Claude Messages API calls that return one JSON object matching a schema."""

from __future__ import annotations

import json
from typing import Any


DEFAULT_MODEL = "claude-opus-5"
# Pinned so an ANTHROPIC_BASE_URL in the shell (e.g. a third-party relay) never receives the key.
API_BASE_URL = "https://api.anthropic.com"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_PAUSE_CONTINUATIONS = 5

# Models the workbench offers. Prices are USD per million input / output tokens.
# web_tools: "dynamic" = web_search/web_fetch_20260209, "basic" = the older variants.
MODELS: dict[str, dict[str, Any]] = {
    "claude-opus-5": {
        "label": "Claude Opus 5", "note": "默认，质量与成本均衡", "price": [5, 25],
        "web_tools": "dynamic", "thinking": True, "fallbacks": True,
    },
    "claude-sonnet-5": {
        "label": "Claude Sonnet 5", "note": "更便宜，适合反复试跑", "price": [2, 10],
        "web_tools": "dynamic", "thinking": True, "fallbacks": False,
    },
    "claude-haiku-4-5": {
        "label": "Claude Haiku 4.5", "note": "最便宜，结果较粗", "price": [1, 5],
        "web_tools": "basic", "thinking": False, "fallbacks": False,
    },
    "claude-fable-5-1": {
        "label": "Claude Fable 5.1", "note": "能力最强，价格最高", "price": [10, 50],
        "web_tools": "dynamic", "thinking": True, "fallbacks": True,
    },
}


class ClaudeCallError(RuntimeError):
    """Raised when Claude does not return a usable JSON object."""


def build_request(
    *,
    system: str,
    user: str,
    schema: dict[str, Any],
    model: str = DEFAULT_MODEL,
    tools: list[dict[str, Any]] | None = None,
    max_tokens: int = 64000,
) -> dict[str, Any]:
    config = model_config(model)
    request: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
        "output_config": {"format": {"type": "json_schema", "schema": schema}},
    }
    if config["thinking"]:
        request["thinking"] = {"type": "adaptive"}
    if config["fallbacks"]:
        # Declined requests are re-run server-side on Anthropic's recommended fallback model.
        request["fallbacks"] = "default"
        request["betas"] = [FALLBACK_BETA]
    if tools:
        request["tools"] = tools
    return request


def model_config(model: str) -> dict[str, Any]:
    if model not in MODELS:
        raise ClaudeCallError(f"unsupported model: {model}")
    return MODELS[model]


def web_tools(model: str, allowed_domains: list[str], *, max_searches: int, max_fetches: int) -> list[dict[str, Any]]:
    dynamic = model_config(model)["web_tools"] == "dynamic"
    return [
        {"type": "web_search_20260209" if dynamic else "web_search_20250305", "name": "web_search",
         "max_uses": max_searches, "allowed_domains": allowed_domains},
        {"type": "web_fetch_20260209" if dynamic else "web_fetch_20250910", "name": "web_fetch",
         "max_uses": max_fetches, "allowed_domains": allowed_domains},
    ]


def call_json(api_key: str, request: dict[str, Any], *, timeout_seconds: float = 600) -> dict[str, Any]:
    """Stream one request, resuming pause_turn stops, and parse the final JSON."""
    if not isinstance(api_key, str) or not api_key.strip():
        raise ClaudeCallError("ANTHROPIC_API_KEY is required")
    # Imported here so the Claude Code runtime (tools/local_run.py) works without the SDK installed.
    import anthropic

    client = anthropic.Anthropic(api_key=api_key.strip(), base_url=API_BASE_URL, timeout=timeout_seconds)
    request = {**request, "messages": list(request["messages"])}
    try:
        for _ in range(MAX_PAUSE_CONTINUATIONS + 1):
            with client.beta.messages.stream(**request) as stream:
                message = stream.get_final_message()
            if message.stop_reason != "pause_turn":
                break
            # A long server-tool turn paused; send it back so Claude continues.
            request["messages"].append({"role": "assistant", "content": message.content})
        else:
            raise ClaudeCallError("Claude paused too many times without finishing")
    except anthropic.AuthenticationError as error:
        raise ClaudeCallError("Claude API Key 无效：需要 Anthropic 官方 Key（sk-ant- 开头），第三方中转的 Key 不能用") from error
    except anthropic.RateLimitError as error:
        raise ClaudeCallError("Claude API 触发限流，请稍后再试") from error
    except anthropic.APIStatusError as error:
        raise ClaudeCallError(f"Claude API returned HTTP {error.status_code}: {str(error.message)[:500]}") from error
    except anthropic.APIConnectionError as error:
        raise ClaudeCallError(f"Claude API request failed: {error}") from error
    return extract_json(message)


def extract_json(message: Any) -> dict[str, Any]:
    if message.stop_reason == "refusal":
        details = getattr(message, "stop_details", None)
        raise ClaudeCallError(f"Claude declined the request: {getattr(details, 'explanation', '') or ''}")
    if message.stop_reason == "max_tokens":
        raise ClaudeCallError("Claude response hit max_tokens before finishing")
    # With server tools the reply can hold text before and between searches;
    # the structured answer is the text after the last tool result.
    blocks = list(message.content)
    last_tool = max((i for i, b in enumerate(blocks) if b.type.endswith("_tool_result")), default=-1)
    text = "".join(b.text for b in blocks[last_tool + 1:] if b.type == "text").strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError as error:
        raise ClaudeCallError("Claude response did not contain valid JSON") from error
    if not isinstance(value, dict):
        raise ClaudeCallError("Claude response JSON must be an object")
    return value
