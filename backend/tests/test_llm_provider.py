"""Tests for the provider-agnostic LLM layer (no network calls)."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.core.config import Settings
from app.services.llm_provider import (
    AnthropicProvider,
    LLMProviderError,
    LLMResult,
    OpenAIProvider,
    _strip_fences,
    get_llm_provider,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DB_URL = "sqlite+pysqlite:///./test_provider.db"
_JWT = "test-secret-with-more-than-thirty-two-characters"

_VALID_ANALYSIS_DICT: dict = {
    "summary": "Customer cannot complete payment after invoice update.",
    "category": "billing",
    "recommended_priority": "high",
    "recommended_team": "Billing Ops",
    "next_action": "Validate invoice changes and check payment gateway status.",
    "confidence": 0.9,
}
_VALID_ANALYSIS_JSON = json.dumps(_VALID_ANALYSIS_DICT)

_OAI_REQUEST = httpx.Request("POST", "https://api.openai.com/v1/responses")
_ANT_REQUEST = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
_OAI_RESPONSE_429 = httpx.Response(429, request=_OAI_REQUEST)
_ANT_RESPONSE_429 = httpx.Response(429, request=_ANT_REQUEST)


def _openai_settings(**overrides) -> Settings:
    return Settings(
        llm_provider="openai",
        openai_api_key="sk-test-openai",
        anthropic_api_key=None,
        database_url=_DB_URL,
        jwt_secret=_JWT,
        **overrides,
    )


def _anthropic_settings(**overrides) -> Settings:
    return Settings(
        llm_provider="anthropic",
        anthropic_api_key="sk-ant-test",
        openai_api_key=None,
        database_url=_DB_URL,
        jwt_secret=_JWT,
        **overrides,
    )


def _make_openai_response(text: str, input_tokens: int = 10, output_tokens: int = 20) -> MagicMock:
    r = MagicMock()
    r.output_text = text
    r.usage = MagicMock()
    r.usage.input_tokens = input_tokens
    r.usage.output_tokens = output_tokens
    return r


def _make_anthropic_tool_use_response(
    analysis_dict: dict, input_tokens: int = 10, output_tokens: int = 20
) -> MagicMock:
    # type and name are reserved MagicMock kwargs; set as attributes after creation.
    block = MagicMock()
    block.type = "tool_use"
    block.name = "analyze_ticket"
    block.input = analysis_dict
    r = MagicMock()
    r.content = [block]
    r.usage = MagicMock()
    r.usage.input_tokens = input_tokens
    r.usage.output_tokens = output_tokens
    return r


def _make_anthropic_text_response(text: str, input_tokens: int = 10, output_tokens: int = 20) -> MagicMock:
    block = MagicMock()
    block.type = "text"
    block.text = text
    r = MagicMock()
    r.content = [block]
    r.usage = MagicMock()
    r.usage.input_tokens = input_tokens
    r.usage.output_tokens = output_tokens
    return r


# ---------------------------------------------------------------------------
# Provider selection
# ---------------------------------------------------------------------------


def test_get_llm_provider_returns_openai_when_configured():
    assert isinstance(get_llm_provider(_openai_settings()), OpenAIProvider)


def test_get_llm_provider_returns_anthropic_when_configured():
    assert isinstance(get_llm_provider(_anthropic_settings()), AnthropicProvider)


def test_get_llm_provider_returns_none_when_openai_key_absent():
    s = Settings(llm_provider="openai", openai_api_key=None, database_url=_DB_URL, jwt_secret=_JWT)
    assert get_llm_provider(s) is None


def test_get_llm_provider_returns_none_when_anthropic_key_absent():
    s = Settings(llm_provider="anthropic", anthropic_api_key=None, database_url=_DB_URL, jwt_secret=_JWT)
    assert get_llm_provider(s) is None


def test_get_llm_provider_unknown_value_falls_back_to_openai():
    s = Settings(llm_provider="mistral", openai_api_key="sk-test", database_url=_DB_URL, jwt_secret=_JWT)
    assert isinstance(get_llm_provider(s), OpenAIProvider)


# ---------------------------------------------------------------------------
# _strip_fences
# ---------------------------------------------------------------------------


def test_strip_fences_removes_json_code_fence():
    assert _strip_fences('```json\n{"k": 1}\n```') == '{"k": 1}'


def test_strip_fences_removes_plain_code_fence():
    assert _strip_fences('```\n{"k": 1}\n```') == '{"k": 1}'


def test_strip_fences_leaves_plain_json_unchanged():
    plain = '{"k": 1}'
    assert _strip_fences(plain) == plain


def test_strip_fences_handles_multiline_json():
    fenced = '```json\n{\n  "k": 1\n}\n```'
    assert json.loads(_strip_fences(fenced)) == {"k": 1}


# ---------------------------------------------------------------------------
# OpenAI provider
# ---------------------------------------------------------------------------


def test_openai_complete_returns_llm_result():
    with patch("app.services.llm_provider.OpenAI"):
        p = OpenAIProvider(_openai_settings())
    p._invoke = MagicMock(return_value=_make_openai_response(_VALID_ANALYSIS_JSON, 15, 25))
    result = p.complete({"ticket": {}})
    assert isinstance(result, LLMResult)
    assert result.input_tokens == 15
    assert result.output_tokens == 25
    assert json.loads(result.text)["category"] == "billing"


def test_openai_source_label():
    with patch("app.services.llm_provider.OpenAI"):
        p = OpenAIProvider(_openai_settings())
    assert p.source_label == "openai_structured_output"


def test_openai_cost_fields_match_settings():
    with patch("app.services.llm_provider.OpenAI"):
        p = OpenAIProvider(_openai_settings(openai_input_cost_per_1m=2.0, openai_output_cost_per_1m=8.0))
    assert p.input_cost_per_1m == 2.0
    assert p.output_cost_per_1m == 8.0


def test_openai_timeout_raises_llm_provider_error():
    from openai import APITimeoutError

    with patch("app.services.llm_provider.OpenAI"):
        p = OpenAIProvider(_openai_settings())
    p._invoke = MagicMock(side_effect=APITimeoutError(request=_OAI_REQUEST))
    with pytest.raises(LLMProviderError):
        p.complete({})


def test_openai_connection_error_raises_llm_provider_error():
    from openai import APIConnectionError

    with patch("app.services.llm_provider.OpenAI"):
        p = OpenAIProvider(_openai_settings())
    p._invoke = MagicMock(side_effect=APIConnectionError(request=_OAI_REQUEST))
    with pytest.raises(LLMProviderError):
        p.complete({})


def test_openai_rate_limit_raises_llm_provider_error():
    from openai import RateLimitError

    with patch("app.services.llm_provider.OpenAI"):
        p = OpenAIProvider(_openai_settings())
    p._invoke = MagicMock(
        side_effect=RateLimitError(message="rate limited", response=_OAI_RESPONSE_429, body=None)
    )
    with pytest.raises(LLMProviderError):
        p.complete({})


# ---------------------------------------------------------------------------
# Anthropic provider
# ---------------------------------------------------------------------------


def test_anthropic_complete_extracts_tool_use_input():
    with patch("app.services.llm_provider.Anthropic"):
        p = AnthropicProvider(_anthropic_settings())
    p._invoke = MagicMock(return_value=_make_anthropic_tool_use_response(_VALID_ANALYSIS_DICT, 12, 22))
    result = p.complete({"ticket": {}})
    assert result.input_tokens == 12
    assert result.output_tokens == 22
    assert json.loads(result.text)["category"] == "billing"
    assert json.loads(result.text)["recommended_team"] == "Billing Ops"


def test_anthropic_source_label():
    with patch("app.services.llm_provider.Anthropic"):
        p = AnthropicProvider(_anthropic_settings())
    assert p.source_label == "anthropic_messages"


def test_anthropic_falls_back_to_text_blocks_when_no_tool_use():
    with patch("app.services.llm_provider.Anthropic"):
        p = AnthropicProvider(_anthropic_settings())
    p._invoke = MagicMock(return_value=_make_anthropic_text_response(_VALID_ANALYSIS_JSON))
    result = p.complete({})
    assert json.loads(result.text)["category"] == "billing"


def test_anthropic_strips_fences_from_text_fallback():
    fenced = f"```json\n{_VALID_ANALYSIS_JSON}\n```"
    with patch("app.services.llm_provider.Anthropic"):
        p = AnthropicProvider(_anthropic_settings())
    p._invoke = MagicMock(return_value=_make_anthropic_text_response(fenced))
    result = p.complete({})
    assert json.loads(result.text)["category"] == "billing"


def test_anthropic_token_usage_parsed_correctly():
    with patch("app.services.llm_provider.Anthropic"):
        p = AnthropicProvider(_anthropic_settings())
    p._invoke = MagicMock(return_value=_make_anthropic_tool_use_response(_VALID_ANALYSIS_DICT, 30, 50))
    result = p.complete({})
    assert result.input_tokens == 30
    assert result.output_tokens == 50


def test_anthropic_cost_fields_match_settings():
    with patch("app.services.llm_provider.Anthropic"):
        p = AnthropicProvider(
            _anthropic_settings(anthropic_input_cost_per_1m=4.0, anthropic_output_cost_per_1m=20.0)
        )
    assert p.input_cost_per_1m == 4.0
    assert p.output_cost_per_1m == 20.0


def test_anthropic_invalid_json_from_text_fallback_is_returned_as_is():
    """complete() returns whatever text it gets; agent.py raises ValidationError → fallback."""
    with patch("app.services.llm_provider.Anthropic"):
        p = AnthropicProvider(_anthropic_settings())
    p._invoke = MagicMock(return_value=_make_anthropic_text_response("not json at all"))
    result = p.complete({})
    assert result.text == "not json at all"
    # Confirm the caller (agent.py) would get a ValidationError:
    from pydantic import ValidationError

    from app.schemas import TicketAnalysis

    with pytest.raises((ValidationError, Exception)):
        TicketAnalysis.model_validate_json(result.text)


def test_anthropic_timeout_raises_llm_provider_error():
    from anthropic import APITimeoutError

    with patch("app.services.llm_provider.Anthropic"):
        p = AnthropicProvider(_anthropic_settings())
    p._invoke = MagicMock(side_effect=APITimeoutError(request=_ANT_REQUEST))
    with pytest.raises(LLMProviderError):
        p.complete({})


def test_anthropic_connection_error_raises_llm_provider_error():
    from anthropic import APIConnectionError

    with patch("app.services.llm_provider.Anthropic"):
        p = AnthropicProvider(_anthropic_settings())
    p._invoke = MagicMock(side_effect=APIConnectionError(request=_ANT_REQUEST))
    with pytest.raises(LLMProviderError):
        p.complete({})


def test_anthropic_rate_limit_raises_llm_provider_error():
    from anthropic import RateLimitError

    with patch("app.services.llm_provider.Anthropic"):
        p = AnthropicProvider(_anthropic_settings())
    p._invoke = MagicMock(
        side_effect=RateLimitError(message="rate limited", response=_ANT_RESPONSE_429, body=None)
    )
    with pytest.raises(LLMProviderError):
        p.complete({})


# ---------------------------------------------------------------------------
# Groq
# ---------------------------------------------------------------------------

_GROQ_REQUEST = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")


def _groq_settings(**overrides) -> Settings:
    return Settings(
        llm_provider="groq",
        groq_api_key="gsk-test",
        openai_api_key=None,
        anthropic_api_key=None,
        database_url=_DB_URL,
        jwt_secret=_JWT,
        **overrides,
    )


def _make_groq_response(tool_name: str | None, arguments: str = "", content: str | None = None) -> MagicMock:
    call = MagicMock()
    call.function.name = tool_name
    call.function.arguments = arguments
    message = MagicMock(tool_calls=[call] if tool_name else None, content=content)
    return MagicMock(choices=[MagicMock(message=message)], usage=MagicMock(prompt_tokens=11, completion_tokens=7))


def test_get_llm_provider_returns_groq_when_configured():
    from app.services.llm_provider import GroqProvider

    provider = get_llm_provider(_groq_settings())
    assert isinstance(provider, GroqProvider)
    assert str(provider._client.base_url).startswith("https://api.groq.com/openai/v1")
    assert provider.source_label == "groq_tool_call"


def test_get_llm_provider_returns_none_when_groq_key_absent():
    s = Settings(llm_provider="groq", groq_api_key=None, database_url=_DB_URL, jwt_secret=_JWT)
    assert get_llm_provider(s) is None


def test_groq_complete_json_forces_the_perspectives_tool_and_reads_its_arguments():
    provider = get_llm_provider(_groq_settings())
    arguments = json.dumps({"perspectives": []})
    provider._client.chat.completions.create = MagicMock(return_value=_make_groq_response("generate_perspectives", arguments))

    result = provider.complete_json("system text", {"risk_item": {"title": "t"}})

    kwargs = provider._client.chat.completions.create.call_args.kwargs
    assert kwargs["tool_choice"] == {"type": "function", "function": {"name": "generate_perspectives"}}
    assert kwargs["messages"][0] == {"role": "system", "content": "system text"}
    assert kwargs["model"] == "openai/gpt-oss-120b"
    assert (result.text, result.input_tokens, result.output_tokens) == (arguments, 11, 7)


def test_groq_complete_uses_the_ticket_tool():
    provider = get_llm_provider(_groq_settings())
    provider._client.chat.completions.create = MagicMock(
        return_value=_make_groq_response("analyze_ticket", _VALID_ANALYSIS_JSON)
    )

    result = provider.complete({"ticket": {}})

    tool = provider._client.chat.completions.create.call_args.kwargs["tools"][0]["function"]
    assert tool["name"] == "analyze_ticket"
    assert json.loads(result.text) == _VALID_ANALYSIS_DICT


def test_groq_falls_back_to_fenced_text_when_no_tool_call():
    provider = get_llm_provider(_groq_settings())
    provider._client.chat.completions.create = MagicMock(
        return_value=_make_groq_response(None, content=f"```json\n{_VALID_ANALYSIS_JSON}\n```")
    )

    assert json.loads(provider.complete({"ticket": {}}).text) == _VALID_ANALYSIS_DICT


def test_groq_rate_limit_becomes_provider_error():
    from openai import RateLimitError

    provider = get_llm_provider(_groq_settings())
    provider._invoke = MagicMock(
        side_effect=RateLimitError("rate limited", response=httpx.Response(429, request=_GROQ_REQUEST), body=None)
    )

    with pytest.raises(LLMProviderError):
        provider.complete_json("system", {})


def _tool_use_failed() -> Exception:
    from openai import BadRequestError

    body = {"code": "tool_use_failed", "failed_generation": '{"confidence": 0. nine}'}
    return BadRequestError("bad tool call", response=httpx.Response(400, request=_GROQ_REQUEST), body=body)


def test_groq_retries_a_failed_tool_call():
    provider = get_llm_provider(_groq_settings())
    good = _make_groq_response("generate_perspectives", json.dumps({"perspectives": []}))
    provider._client.chat.completions.create = MagicMock(side_effect=[_tool_use_failed(), good])

    with patch("tenacity.nap.time.sleep"):
        result = provider.complete_json("system", {})

    assert provider._client.chat.completions.create.call_count == 2
    assert json.loads(result.text) == {"perspectives": []}


def test_groq_persistent_tool_failure_returns_the_broken_generation():
    provider = get_llm_provider(_groq_settings())
    provider._client.chat.completions.create = MagicMock(side_effect=_tool_use_failed())

    with patch("tenacity.nap.time.sleep"):
        result = provider.complete_json("system", {})

    assert result.text == '{"confidence": 0. nine}'
    with pytest.raises(json.JSONDecodeError):
        json.loads(result.text)
