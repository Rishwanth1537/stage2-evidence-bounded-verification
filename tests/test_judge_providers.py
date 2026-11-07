import sys
import urllib.error
import io
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmarks"))
import llm_judge_args as j  # noqa: E402

MSGS = [{"role": "system", "content": "sys"}, {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1"}, {"role": "user", "content": "q2"}]


def test_anthropic_payload_moves_system_out():
    p = j.anthropic_payload("m", MSGS, 120)
    assert p["system"] == "sys"
    assert [t["role"] for t in p["messages"]] == ["user", "assistant", "user"]
    assert p["max_tokens"] == 120 and p["temperature"] == 0


def test_anthropic_normalise_matches_openai_shape():
    out = j.anthropic_normalise({"content": [{"type": "text", "text": '{"supported": true}'}, {"type": "thinking", "thinking": "x"}],
                                 "usage": {"input_tokens": 10, "output_tokens": 5}})
    assert out["choices"][0]["message"]["content"] == '{"supported": true}'
    assert out["usage"] == {"prompt_tokens": 10, "completion_tokens": 5}


def test_chat_anthropic_end_to_end_with_fake_http(monkeypatch):
    seen = {}

    def fake(url, key, payload=None, timeout=90, style="openai"):
        seen.update(url=url, style=style, payload=payload)
        return {"content": [{"type": "text", "text": "ok"}], "usage": {"input_tokens": 3, "output_tokens": 1}}

    monkeypatch.setattr(j, "http_json", fake)
    out, _ = j.chat("anthropic", "k", "some-model", MSGS)
    assert seen["url"].endswith("/messages") and seen["style"] == "anthropic"
    assert out["choices"][0]["message"]["content"] == "ok"


def test_temperature_rejected_is_retried_without_it(monkeypatch):
    calls = []

    def fake(url, key, payload=None, timeout=90, style="openai"):
        calls.append("temperature" in payload)
        if "temperature" in payload:
            raise urllib.error.HTTPError(url, 400, "bad", {}, io.BytesIO(b'{"error":"temperature is not supported"}'))
        return {"content": [{"type": "text", "text": "ok"}], "usage": {}}

    monkeypatch.setattr(j, "http_json", fake)
    j.chat("anthropic", "k", "m", MSGS, sleep=lambda s: None)
    assert calls == [True, False]


def test_openai_style_unchanged_and_reasoning_headroom(monkeypatch):
    seen = {}

    def fake(url, key, payload=None, timeout=90, style="openai"):
        seen.update(url=url, payload=payload)
        return {"choices": [{"message": {"content": "x"}}]}

    monkeypatch.setattr(j, "http_json", fake)
    j.chat("groq", "k", "openai/gpt-oss-20b", MSGS)
    assert seen["url"].endswith("/chat/completions") and seen["payload"]["max_tokens"] == 1500
    j.chat("groq", "k", "llama-x", MSGS)
    assert seen["payload"]["max_tokens"] == 120 and "reasoning_effort" not in seen["payload"]
