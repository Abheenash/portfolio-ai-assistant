"""Handler tests with a fake Bedrock client — no network, no AWS credentials."""
import io
import json
import os
import sys

import pytest
from botocore.exceptions import ClientError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lambda"))
os.environ["ALLOW_ORIGIN"] = "https://abheenash.com,https://www.abheenash.com"
import app  # noqa: E402


class FakeBedrock:
    def __init__(self, reply="Abheenash works at Phillips 66.", fail_codes=(), usage=None):
        self.reply = reply
        self.fail_codes = list(fail_codes)
        self.calls = []
        self.usage = usage or {"input_tokens": 12, "output_tokens": 20,
                               "cache_read_input_tokens": 4000, "cache_creation_input_tokens": 0}

    def invoke_model(self, modelId, body):
        self.calls.append(json.loads(body))
        if self.fail_codes:
            code = self.fail_codes.pop(0)
            raise ClientError({"Error": {"Code": code, "Message": code}}, "InvokeModel")
        payload = {"content": [{"type": "text", "text": self.reply}], "stop_reason": "end_turn",
                   "usage": self.usage}
        return {"body": io.BytesIO(json.dumps(payload).encode())}


class Ctx:
    aws_request_id = "req-123"


def event(body=None, origin="https://abheenash.com", method="POST", raw=None):
    return {
        "requestContext": {"http": {"method": method}},
        "headers": {"Origin": origin} if origin is not None else {},
        "body": raw if raw is not None else json.dumps(body or {}),
    }


@pytest.fixture
def bedrock(monkeypatch):
    fake = FakeBedrock()
    monkeypatch.setattr(app, "_bedrock", fake)
    return fake


@pytest.fixture
def logs(capsys):
    def read():
        return [json.loads(l) for l in capsys.readouterr().out.splitlines() if l.startswith("{")]
    return read


def test_happy_path_returns_reply_and_logs_usage(bedrock, logs):
    r = app.handler(event({"message": "Where does he work?"}), Ctx())
    assert r["statusCode"] == 200
    assert json.loads(r["body"])["reply"] == "Abheenash works at Phillips 66."
    assert r["headers"]["Access-Control-Allow-Origin"] == "https://abheenash.com"
    rec = logs()[-1]
    assert rec["Outcome"] == "ok" and rec["request_id"] == "req-123"
    assert rec["InputTokens"] == 12 and rec["OutputTokens"] == 20 and rec["CacheReadTokens"] == 4000
    assert rec["CostUsd"] == pytest.approx((12 * 1.0 + 20 * 5.0 + 4000 * 0.10) / 1e6, rel=1e-6)
    assert rec["_aws"]["CloudWatchMetrics"][0]["Namespace"] == "PortfolioAssistant"
    names = {m["Name"] for m in rec["_aws"]["CloudWatchMetrics"][0]["Metrics"]}
    assert {"LatencyMs", "InputTokens", "OutputTokens", "CacheReadTokens", "CostUsd"} <= names


def test_system_prompt_is_cached_and_grounded(bedrock):
    app.handler(event({"message": "hi"}), Ctx())
    body = bedrock.calls[0]
    assert body["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert "=== KNOWLEDGE BASE ===" in body["system"][0]["text"]
    assert "Phillips 66" in body["system"][0]["text"]
    assert body["max_tokens"] == app.MAX_TOKENS
    assert body["messages"] == [{"role": "user", "content": "hi"}]


def test_options_preflight(bedrock):
    r = app.handler(event(method="OPTIONS"), Ctx())
    assert r["statusCode"] == 200 and r["headers"]["Access-Control-Allow-Methods"] == "POST,OPTIONS"
    assert bedrock.calls == []


def test_disallowed_origin_is_rejected_before_bedrock(bedrock, logs):
    r = app.handler(event({"message": "hi"}, origin="https://evil.example"), Ctx())
    assert r["statusCode"] == 403 and bedrock.calls == []
    assert logs()[-1]["reason"] == "origin"


def test_www_origin_is_allowed(bedrock):
    r = app.handler(event({"message": "hi"}, origin="https://www.abheenash.com"), Ctx())
    assert r["statusCode"] == 200
    assert r["headers"]["Access-Control-Allow-Origin"] == "https://www.abheenash.com"


@pytest.mark.parametrize("raw,status,reason", [
    ("{not json", 400, "bad_json"),
    ("[1,2]", 400, "bad_json"),
    (json.dumps({"message": "   "}), 400, "empty"),
    (json.dumps({}), 400, "empty"),
    (json.dumps({"message": "x" * 1001}), 413, "too_long"),
])
def test_input_validation(bedrock, logs, raw, status, reason):
    r = app.handler(event(raw=raw), Ctx())
    assert r["statusCode"] == status and bedrock.calls == []
    assert logs()[-1]["reason"] == reason


def test_boundary_length_is_accepted(bedrock):
    r = app.handler(event({"message": "x" * 1000}), Ctx())
    assert r["statusCode"] == 200


def test_history_is_trimmed_and_repaired():
    history = [{"role": "assistant", "content": "first?"}] + [
        {"role": "user", "content": f"u{i}"} if i % 2 == 0 else {"role": "assistant", "content": f"a{i}"}
        for i in range(20)
    ]
    msgs = app.build_messages(history, "now")
    assert len(msgs) <= app.MAX_HISTORY_TURNS + 1
    assert msgs[0]["role"] == "user" and msgs[-1] == {"role": "user", "content": "now"}
    for a, b in zip(msgs, msgs[1:]):
        assert a["role"] != b["role"]


def test_history_garbage_is_ignored():
    msgs = app.build_messages(["str", 5, {"role": "system", "content": "x"}, {"role": "user"},
                               {"role": "user", "content": "dangling"}], "q")
    assert msgs == [{"role": "user", "content": "q"}]


def test_history_content_is_capped():
    msgs = app.build_messages([{"role": "user", "content": "y" * 5000}, {"role": "assistant", "content": "a"}], "q")
    assert len(msgs[0]["content"]) == app.MAX_INPUT_CHARS


def test_retries_on_throttle_then_succeeds(monkeypatch, logs):
    fake = FakeBedrock(fail_codes=["ThrottlingException", "ServiceUnavailableException"])
    monkeypatch.setattr(app, "_bedrock", fake)
    monkeypatch.setattr(app.time, "sleep", lambda s: None)
    r = app.handler(event({"message": "hi"}), Ctx())
    assert r["statusCode"] == 200 and len(fake.calls) == 3
    assert logs()[-1]["Retries"] == 2


def test_non_retryable_error_is_502_immediately(monkeypatch, logs):
    fake = FakeBedrock(fail_codes=["ValidationException"])
    monkeypatch.setattr(app, "_bedrock", fake)
    r = app.handler(event({"message": "hi"}), Ctx())
    assert r["statusCode"] == 502 and len(fake.calls) == 1
    rec = logs()[-1]
    assert rec["Outcome"] == "error" and rec["Errors"] == 1 and "ValidationException" in rec["error"]
    assert "ValidationException" not in r["body"]  # detail stays in the log, not the client


def test_gives_up_after_bounded_retries(monkeypatch):
    fake = FakeBedrock(fail_codes=["ThrottlingException"] * 10)
    monkeypatch.setattr(app, "_bedrock", fake)
    monkeypatch.setattr(app.time, "sleep", lambda s: None)
    r = app.handler(event({"message": "hi"}), Ctx())
    assert r["statusCode"] == 502 and len(fake.calls) == 4


def test_empty_model_output_gets_fallback_text(monkeypatch):
    monkeypatch.setattr(app, "_bedrock", FakeBedrock(reply="   "))
    r = app.handler(event({"message": "hi"}), Ctx())
    assert json.loads(r["body"])["reply"] == "Sorry, I didn't catch that."


def test_cost_with_missing_usage_is_zero():
    assert app.cost_usd(None) == 0 and app.cost_usd({}) == 0
