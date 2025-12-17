"""Gedeelde OpenAI-helperfuncties om service-modules eenvoudig te houden."""

import json
import logging
import os
from typing import Any, Dict, List, Optional

try:
    from openai import OpenAI  # type: ignore
except ImportError:  # pragma: no cover
    # OpenAI SDK is optioneel - app werkt ook zonder (fallback naar basic data)
    OpenAI = None

logger = logging.getLogger(__name__)
_client = None


def get_openai_client():
    """Geef een hergebruikte OpenAI-client terug als de API-key is ingesteld.
    
    Gebruikt singleton pattern: client wordt één keer geïnitialiseerd en
    daarna hergebruikt. Als API key ontbreekt of ongeldig is, retourneert
    None (callers moeten dit afhandelen met fallback logic).
    """
    global _client
    if _client:
        return _client
    if _client is False:
        # Client initialisatie is al geprobeerd en gefaald - skip opnieuw proberen
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
    """Verwijder markdown code blocks rond JSON.
    
    OpenAI kan soms JSON teruggeven in ```json ... ``` blocks.
    Deze functie verwijdert die formatting zodat we pure JSON hebben.
    """
    text = (text or "").strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.startswith(("json", "JSON")):
            text = text[4:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _to_json(content: str, silent: bool = False) -> Optional[dict]:
    """Zet een JSON-string om naar een dict.

    Args:
        content: tekst die JSON zou moeten bevatten
        silent: als True, geen waarschuwingen loggen bij parse-fouten

    Returns:
        Een dict bij geldige JSON, anders None.
    """
    if not content:
        return None
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        if not silent:
            logger.warning("Bad JSON response from OpenAI: %s", exc)
        return None


def _extract_citation_url(citation: Any) -> Optional[str]:
    """Haal een URL uit een citation-object, ongeacht het exacte formaat."""
    if not citation:
        return None
    if isinstance(citation, dict):
        return citation.get("url") or citation.get("source_url") or citation.get("link")
    if hasattr(citation, "url"):
        return citation.url
    if hasattr(citation, "source_url"):
        return citation.source_url
    if hasattr(citation, "link"):
        return citation.link
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
    """Voer een chat-completion uit en parse het resultaat als JSON.
    
    Gebruikt OpenAI Chat Completions API met JSON response format.
    Als de call faalt (geen API key, quota error, etc.), retourneert None.
    Callers moeten dit afhandelen met fallback logic.
    """
    client = get_openai_client()
    if not client:
        return None
    payload = list(messages or [])
    if not payload:
        if system_prompt:
            payload.append({"role": "system", "content": system_prompt})
        if user_prompt:
            payload.append({"role": "user", "content": user_prompt})
    params: Dict[str, Any] = {"model": model, "messages": payload, "temperature": temperature, "max_tokens": max_tokens}
    if response_format:
        params["response_format"] = {"type": response_format}
    try:
        resp = client.chat.completions.create(**params)  # type: ignore[arg-type]
    except Exception as exc:  # pragma: no cover
        # Log maar crash niet - return None zodat caller fallback kan gebruiken
        extra = f" for {context}" if context else ""
        logger.warning("OpenAI chat completion failed%s: %s", extra, exc)
        return None
    message = resp.choices[0].message if resp and resp.choices else None
    content = _strip_json(message.content if message and message.content else "")
    return _to_json(content)


def responses_json_with_sources(
    prompt: str,
    *,
    model: str = "gpt-4o",
    tools: Optional[List[dict]] = None,
    tool_choice: str = "auto",
    context: str = "",
) -> Optional[Dict[str, Any]]:
    """Voer Responses API uit met web search en retourneer zowel JSON data als sources.
    
    Deze functie gebruikt OpenAI Responses API (niet Chat Completions) omdat
    deze web search ondersteunt. Dit geeft ons zowel de AI output als de
    bronnen (URLs) die gebruikt zijn voor de web search.
    
    Returns:
        {
            "data": dict,  # Geparsed JSON van model output
            "sources": list  # Lijst van source URLs/citations van web search
        }
        of None als de call faalt
    """
    client = get_openai_client()
    if not client:
        return None
    
    # Configureer tools - web_search is een built-in tool van Responses API
    params: Dict[str, Any] = {"model": model, "input": prompt}
    if tools:
        params["tools"] = tools
    if tool_choice:
        params["tool_choice"] = tool_choice
    
    try:
        resp = client.responses.create(**params)  # type: ignore[arg-type]
    except Exception as exc:  # pragma: no cover
        # Log maar crash niet - return None zodat caller fallback kan gebruiken
        extra = f" for {context}" if context else ""
        logger.warning("OpenAI responses call failed%s: %s", extra, exc)
        return None
    
    # Parse output items volgens Responses API structuur
    # Responses API retourneert: { "output": [{"content": [...]}, ...], "citations": [...] }
    # We moeten door meerdere lagen navigeren om zowel text als citations te vinden
    text_chunks: List[str] = []
    sources: List[str] = []
    
    # Haal output items array op
    output_items = getattr(resp, "output", []) or []
    for item in output_items:
        # Behandel content array in output items
        # Content kan zijn: text items, tool call items
        content_list = getattr(item, "content", []) or []
        for content in content_list:
            # Check voor text content (OutputItemText)
            text_attr = getattr(content, "text", None)
            if text_attr:
                if isinstance(text_attr, str):
                    text_chunks.append(text_attr)
                elif hasattr(text_attr, "value"):
                    text_chunks.append(text_attr.value)
            
            # Check voor tool calls (OutputItemToolCall)
            # Tool calls bevatten tool results die citations kunnen hebben
            tool_calls = getattr(content, "tool_calls", []) or []
            for tool_call in tool_calls:
                # Web search tool results kunnen citations bevatten
                tool_result = getattr(tool_call, "result", None)
                if tool_result:
                    # Check of result citations heeft
                    result_citations = getattr(tool_result, "citations", None)
                    if result_citations:
                        if isinstance(result_citations, list):
                            for citation in result_citations:
                                url = _extract_citation_url(citation)
                                if url:
                                    sources.append(url)
                        else:
                            url = _extract_citation_url(result_citations)
                            if url:
                                sources.append(url)
        
        # Check voor citations op het output item zelf
        item_citations = getattr(item, "citations", None)
        if item_citations:
            if isinstance(item_citations, list):
                for citation in item_citations:
                    url = _extract_citation_url(citation)
                    if url:
                        sources.append(url)
            else:
                url = _extract_citation_url(item_citations)
                if url:
                    sources.append(url)
    
    # Check top-level citations object (veelvoorkomende locatie voor web search citations)
    resp_citations = getattr(resp, "citations", None)
    if resp_citations:
        if isinstance(resp_citations, list):
            for citation in resp_citations:
                url = _extract_citation_url(citation)
                if url:
                    sources.append(url)
        else:
            url = _extract_citation_url(resp_citations)
            if url:
                sources.append(url)
    
    # Parse JSON uit verzamelde text
    combined_text = "".join(text_chunks).strip()
    
    if not combined_text:
        # Geen text content, maar we kunnen wel sources hebben
        return {
            "data": None,
            "sources": list(set(sources)) if sources else []
        }
    
    # Probeer eerst als JSON te parsen (silent=True omdat plain text ook mogelijk is)
    parsed_json = _to_json(_strip_json(combined_text), silent=True)
    
    # Als geen JSON, behandel als plain text (veelvoorkomend bij Responses API met web search)
    if parsed_json is None:
        # Retourneer als plain text in een dict structuur
        parsed_json = {"text": combined_text, "content": combined_text}
    
    # Retourneer zowel data als sources (deduplicate sources)
    return {
        "data": parsed_json,
        "sources": list(set(sources))
    }

