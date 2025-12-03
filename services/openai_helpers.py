"""Shared OpenAI helpers to keep service modules lean."""

import json
import logging
import os
from typing import Any, Dict, List, Optional

try:
    from openai import OpenAI  # type: ignore
except ImportError:  # pragma: no cover
    OpenAI = None

logger = logging.getLogger(__name__)
_client = None


def get_openai_client():
    """Return a cached OpenAI client if credentials are configured."""
    global _client
    if _client:
        return _client
    if _client is False:
        return None
    if not OpenAI:
        logger.warning("OpenAI SDK not available")
        _client = False
        return None
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "your-api-key-here" or not api_key.strip():
        logger.warning("OPENAI_API_KEY not configured")
        _client = False
        return None
    try:
        _client = OpenAI(api_key=api_key)
    except Exception as exc:  # pragma: no cover
        logger.error("Failed to initialize OpenAI client: %s", exc)
        _client = False
    return _client if _client is not False else None


def _strip_json(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.startswith(("json", "JSON")):
            text = text[4:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _to_json(content: str) -> Optional[dict]:
    if not content:
        return None
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        logger.warning("Bad JSON response from OpenAI: %s", exc)
        return None


def chat_json(
    *,
    messages: Optional[List[dict]] = None,
    system_prompt: str = "",
    user_prompt: str = "",
    model: str = "gpt-4o-mini",
    temperature: float = 0.3,
    max_tokens: int = 600,
    response_format: Optional[str] = "json_object",
    context: str = "",
) -> Optional[dict]:
    """Run a chat completion and parse JSON output."""
    client = get_openai_client()
    if not client:
        return None
    payload = list(messages or [])
    if not payload:
        if system_prompt:
            payload.append({"role": "system", "content": system_prompt})
        if user_prompt:
            payload.append({"role": "user", "content": user_prompt})
    params: Dict[str, Any] = {
        "model": model,
        "messages": payload,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format:
        params["response_format"] = {"type": response_format}
    try:
        resp = client.chat.completions.create(**params)  # type: ignore[arg-type]
    except Exception as exc:  # pragma: no cover
        extra = f" for {context}" if context else ""
        logger.warning("OpenAI chat completion failed%s: %s", extra, exc)
        return None
    message = resp.choices[0].message if resp and resp.choices else None
    content = _strip_json(message.content if message and message.content else "")
    return _to_json(content)


def chat_text(
    *,
    messages: Optional[List[dict]] = None,
    system_prompt: str = "",
    user_prompt: str = "",
    model: str = "gpt-4o-mini",
    temperature: float = 0.7,
    max_tokens: int = 400,
    context: str = "",
) -> str:
    """Run a chat completion and return raw text."""
    client = get_openai_client()
    if not client:
        return ""
    payload = list(messages or [])
    if not payload:
        if system_prompt:
            payload.append({"role": "system", "content": system_prompt})
        if user_prompt:
            payload.append({"role": "user", "content": user_prompt})
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=payload,  # type: ignore[arg-type]
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except Exception as exc:  # pragma: no cover
        extra = f" for {context}" if context else ""
        logger.warning("OpenAI chat text call failed%s: %s", extra, exc)
        return ""
    message = resp.choices[0].message if resp and resp.choices else None
    return (message.content or "").strip() if message and message.content else ""


def responses_json(
    prompt: str,
    *,
    model: str = "gpt-4o",
    tools: Optional[list] = None,
    tool_choice: str = "auto",
    context: str = "",
) -> Optional[dict]:
    """Run the Responses API (for web search, etc.) and parse JSON."""
    client = get_openai_client()
    if not client:
        return None
    params: Dict[str, Any] = {"model": model, "input": prompt}
    if tools:
        params["tools"] = tools
    if tool_choice:
        params["tool_choice"] = tool_choice
    try:
        resp = client.responses.create(**params)  # type: ignore[arg-type]
    except Exception as exc:  # pragma: no cover
        extra = f" for {context}" if context else ""
        logger.warning("OpenAI responses call failed%s: %s", extra, exc)
        return None
    chunks = []
    for item in getattr(resp, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            text = getattr(content, "text", None)
            if isinstance(text, str):
                chunks.append(text)
            elif text and getattr(text, "value", None):
                chunks.append(text.value)
    return _to_json(_strip_json("".join(chunks)))

