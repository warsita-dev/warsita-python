import asyncio
import hashlib
import hmac
import json
import pathlib
import time

import httpx
import pytest
import yaml

from warsita import OPERATIONS, AsyncWarsita, Warsita, WarsitaError, WebhookVerificationError, verify_webhook


class Recorder:
    """Answers each request with the next response and records what was sent."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        status, body, headers = (self.responses.pop(0) if self.responses else (200, {}, {}))
        if status == 204:
            return httpx.Response(204)
        return httpx.Response(status, json=body, headers=headers)

    def body(self, i: int):
        return json.loads(self.requests[i].content)


def client(recorder, api_key="wsk_test", **kw):
    return Warsita(api_key, http_client=httpx.Client(transport=httpx.MockTransport(recorder)), **kw)


def method_at(obj, path):
    for part in path.split("."):
        obj = getattr(obj, part)
    return obj


def test_every_spec_operation_has_a_method():
    spec = yaml.safe_load((pathlib.Path(__file__).parent.parent / "openapi.yaml").read_text())
    ids = {op["operationId"] for ops in spec["paths"].values() for op in ops.values() if isinstance(op, dict) and "operationId" in op}
    assert ids == set(OPERATIONS)
    for c in (client(Recorder()), AsyncWarsita("wsk_test")):
        for path in OPERATIONS.values():
            assert callable(method_at(c, path)), path


def test_send_uses_the_key_an_idempotency_key_and_unwraps_data():
    rec = Recorder((202, {"data": {"id": "msg_1", "status": "queued"}}, {}))
    m = client(rec).messages.send(to="+6281234567890", text="Hi")
    assert m == {"id": "msg_1", "status": "queued"}
    req = rec.requests[0]
    assert str(req.url) == "https://api.warsita.com/v1/messages"
    assert req.headers["Authorization"] == "Bearer wsk_test"
    assert len(req.headers["Idempotency-Key"]) == 36
    assert rec.body(0) == {"to": "+6281234567890", "text": "Hi"}


def test_a_token_adds_session_id():
    rec = Recorder((202, {"data": {}}, {}), (200, {"data": []}, {}), (200, {"data": []}, {}))
    w = client(rec, api_key="wsp_token", session_id="ses_a")
    w.messages.send(to="+6281234567890", text="Hi")
    w.groups.list()
    w.groups.list(session_id="ses_b")
    assert rec.body(0)["session_id"] == "ses_a"
    assert rec.requests[1].url.params["session_id"] == "ses_a"
    assert rec.requests[2].url.params["session_id"] == "ses_b"
    with pytest.raises(ValueError, match="session_id"):
        client(Recorder(), api_key="wsp_token").contacts.list()


def test_whole_responses_and_no_content():
    rec = Recorder((201, {"session": {"id": "ses_1"}, "api_key": "wsk_new"}, {}), (204, None, {}))
    w = client(rec, api_key="wsp_token")
    assert w.sessions.create(name="Support") == {"session": {"id": "ses_1"}, "api_key": "wsk_new"}
    assert w.sessions.restart("ses_1") is None
    assert rec.requests[1].url.path == "/v1/sessions/ses_1/restart"


def test_rate_limits_retry_and_keep_the_idempotency_key():
    rec = Recorder(
        (429, {"error": {"code": "rate_limited", "message": "Slow down"}}, {"Retry-After": "0"}),
        (503, {}, {}),
        (202, {"data": {"id": "msg_1"}}, {}),
    )
    client(rec).messages.send(to="+6281234567890", text="Hi")
    assert len(rec.requests) == 3
    assert len({r.headers["Idempotency-Key"] for r in rec.requests}) == 1


def test_server_errors_are_not_retried_when_unsafe():
    rec = Recorder((504, {"error": {"code": "runtime_timeout", "message": "WhatsApp did not answer in time."}}, {}))
    with pytest.raises(WarsitaError) as err:
        client(rec).groups.create("Team", ["+6281234567890"])
    assert (err.value.status, err.value.code) == (504, "runtime_timeout")
    assert len(rec.requests) == 1


def test_escaping_and_uploads():
    rec = Recorder((200, {"data": {}}, {}), (201, {"data": {"id": "med_1"}}, {}))
    w = client(rec)
    w.groups.get("120363012345678901@g.us")
    assert rec.requests[0].url.raw_path == b"/v1/groups/120363012345678901%40g.us"
    assert w.media.upload(b"\x89PNG", filename="a.png", content_type="image/png")["id"] == "med_1"
    assert rec.requests[1].headers["Content-Type"].startswith("multipart/form-data")


def test_async_client():
    rec = Recorder((202, {"data": {"id": "msg_1"}}, {}))

    async def run():
        async with AsyncWarsita("wsk_test", http_client=httpx.AsyncClient(transport=httpx.MockTransport(rec))) as w:
            return await w.messages.send(to="+6281234567890", text="Hi")

    assert asyncio.run(run()) == {"id": "msg_1"}


def test_verify_webhook():
    secret = "whsec_test"
    body = json.dumps({"event": "messages.received", "session_id": "ses_1", "timestamp": "2026-10-28T00:00:00Z", "data": {"text": "Hi"}})
    t = int(time.time())
    sig = f"t={t},v1=" + hmac.new(secret.encode(), f"{t}.{body}".encode(), hashlib.sha256).hexdigest()
    assert verify_webhook(body, sig, secret)["data"]["text"] == "Hi"
    with pytest.raises(WebhookVerificationError, match="does not match"):
        verify_webhook(body, sig, "whsec_other")
    with pytest.raises(WebhookVerificationError, match="too old"):
        verify_webhook(body, sig, secret, now=t + 600)
    with pytest.raises(WebhookVerificationError, match="missing"):
        verify_webhook(body, None, secret)
