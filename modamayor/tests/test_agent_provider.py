import json

import httpx
import pytest

from modamayor.agent.provider import (
    AnthropicToolProvider,
    AssistantMessage,
    OllamaToolProvider,
    ToolCall,
    build_tool_provider,
)

TOOLS = [
    {
        "name": "cotizar",
        "description": "Cotiza items",
        "parameters": {"type": "object", "properties": {"q": {"type": "integer"}}},
    }
]

HISTORY = [
    {"role": "system", "content": "sos un bot"},
    {"role": "user", "content": "cotizame 3"},
    {
        "role": "assistant",
        "content": "",
        "tool_calls": [ToolCall(id="call_0", name="cotizar", arguments={"q": 3})],
    },
    {"role": "tool", "tool_call_id": "call_0", "name": "cotizar", "content": "total 300"},
]


def client_returning(payload, seen):
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=payload)

    return httpx.Client(transport=httpx.MockTransport(handler))


def body(request):
    return json.loads(request.content)


def test_ollama_sends_tools_and_think_false():
    seen = []
    c = client_returning({"message": {"role": "assistant", "content": "hola"}}, seen)
    provider = OllamaToolProvider({}, client=c)
    provider.chat([{"role": "user", "content": "hola"}], TOOLS)
    assert str(seen[0].url) == "http://localhost:11434/api/chat"
    sent = body(seen[0])
    assert sent["think"] is False
    assert sent["stream"] is False
    assert sent["options"]["temperature"] == 0
    assert sent["tools"] == [
        {
            "type": "function",
            "function": {
                "name": "cotizar",
                "description": "Cotiza items",
                "parameters": TOOLS[0]["parameters"],
            },
        }
    ]


def test_ollama_normalizes_text_and_synthesizes_call_ids():
    seen = []
    payload = {
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"function": {"name": "cotizar", "arguments": {"q": 1}}},
                {"function": {"name": "buscar_info", "arguments": {"q": "x"}}},
            ],
        }
    }
    provider = OllamaToolProvider({}, client=client_returning(payload, seen))
    msg = provider.chat([{"role": "user", "content": "h"}], TOOLS)
    assert isinstance(msg, AssistantMessage)
    assert msg.text == ""
    assert msg.tool_calls == [
        ToolCall(id="call_0", name="cotizar", arguments={"q": 1}),
        ToolCall(id="call_1", name="buscar_info", arguments={"q": "x"}),
    ]


def test_ollama_plain_text_has_no_tool_calls():
    seen = []
    c = client_returning({"message": {"role": "assistant", "content": " hola "}}, seen)
    msg = OllamaToolProvider({}, client=c).chat([{"role": "user", "content": "h"}], TOOLS)
    assert msg.text == "hola"
    assert msg.tool_calls == []


def test_ollama_translates_history():
    seen = []
    c = client_returning({"message": {"content": "ok"}}, seen)
    OllamaToolProvider({}, client=c).chat(HISTORY, TOOLS)
    assert body(seen[0])["messages"] == [
        {"role": "system", "content": "sos un bot"},
        {"role": "user", "content": "cotizame 3"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"function": {"name": "cotizar", "arguments": {"q": 3}}}],
        },
        {"role": "tool", "tool_name": "cotizar", "content": "total 300"},
    ]


def test_ollama_without_tools_omits_tools_key():
    seen = []
    c = client_returning({"message": {"content": "ok"}}, seen)
    OllamaToolProvider({}, client=c).chat([{"role": "user", "content": "h"}], [])
    assert "tools" not in body(seen[0])


def anthropic(seen, payload):
    env = {"LLM_PROVIDER": "anthropic", "LLM_MODEL": "m2", "ANTHROPIC_API_KEY": "k"}
    return AnthropicToolProvider(env, client=client_returning(payload, seen))


def test_anthropic_sends_headers_tools_and_system():
    seen = []
    provider = anthropic(seen, {"content": [{"type": "text", "text": "ok"}]})
    provider.chat(HISTORY[:2], TOOLS)
    assert str(seen[0].url) == "https://api.anthropic.com/v1/messages"
    assert seen[0].headers["x-api-key"] == "k"
    assert seen[0].headers["anthropic-version"] == "2023-06-01"
    sent = body(seen[0])
    assert sent["model"] == "m2"
    assert sent["max_tokens"] > 0
    assert sent["system"] == "sos un bot"
    assert sent["messages"] == [{"role": "user", "content": "cotizame 3"}]
    assert sent["tools"] == [
        {
            "name": "cotizar",
            "description": "Cotiza items",
            "input_schema": TOOLS[0]["parameters"],
        }
    ]


def test_anthropic_normalizes_tool_use_blocks():
    seen = []
    payload = {
        "content": [
            {"type": "text", "text": "voy"},
            {"type": "tool_use", "id": "toolu_1", "name": "cotizar", "input": {"q": 2}},
        ]
    }
    msg = anthropic(seen, payload).chat(HISTORY[:2], TOOLS)
    assert msg.text == "voy"
    assert msg.tool_calls == [ToolCall(id="toolu_1", name="cotizar", arguments={"q": 2})]


def test_anthropic_translates_history_with_tool_blocks():
    seen = []
    anthropic(seen, {"content": [{"type": "text", "text": "ok"}]}).chat(HISTORY, TOOLS)
    assert body(seen[0])["messages"] == [
        {"role": "user", "content": "cotizame 3"},
        {
            "role": "assistant",
            "content": [{"type": "tool_use", "id": "call_0", "name": "cotizar", "input": {"q": 3}}],
        },
        {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "call_0", "content": "total 300"}],
        },
    ]


def test_anthropic_groups_consecutive_tool_results_in_one_user_message():
    seen = []
    history = [
        {"role": "user", "content": "h"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                ToolCall(id="a", name="cotizar", arguments={}),
                ToolCall(id="b", name="cotizar", arguments={}),
            ],
        },
        {"role": "tool", "tool_call_id": "a", "name": "cotizar", "content": "1"},
        {"role": "tool", "tool_call_id": "b", "name": "cotizar", "content": "2"},
    ]
    anthropic(seen, {"content": [{"type": "text", "text": "ok"}]}).chat(history, TOOLS)
    last = body(seen[0])["messages"][-1]
    assert last["role"] == "user"
    assert [b["tool_use_id"] for b in last["content"]] == ["a", "b"]


def test_build_tool_provider_defaults_to_ollama():
    assert isinstance(build_tool_provider({}), OllamaToolProvider)


def test_build_tool_provider_picks_anthropic():
    env = {"LLM_PROVIDER": "anthropic", "LLM_MODEL": "m", "ANTHROPIC_API_KEY": "k"}
    assert isinstance(build_tool_provider(env), AnthropicToolProvider)


def test_build_tool_provider_rejects_unknown():
    with pytest.raises(RuntimeError, match="Unknown LLM_PROVIDER"):
        build_tool_provider({"LLM_PROVIDER": "nope"})
