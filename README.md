# Warsita for Python

The official Python client for the [Warsita](https://warsita.com) WhatsApp API: send messages, manage sessions, contacts and groups, and verify webhooks. Sync and asyncio clients, one dependency ([httpx](https://www.python-httpx.org)).

```bash
pip install warsita
```

Python 3.9 or newer.

## Send a message

```python
from warsita import Warsita

warsita = Warsita(api_key="wsk_…")  # the session's API key, or set WARSITA_API_KEY

message = warsita.messages.send(to="+6281234567890", text="Your order has shipped.")
print(message["id"], message["status"])  # msg_… queued
```

Every `send` carries an `Idempotency-Key` (generated, or pass `idempotency_key=`), so the client retries rate limits and dropped connections without sending twice.

```python
warsita.messages.send(to="120363012345678901@g.us", image={"url": "https://example.com/receipt.png", "caption": "Receipt"})
warsita.messages.send(to="+6281234567890", poll={"name": "Which day?", "options": ["Friday", "Saturday"], "selectable_count": 1})

with open("invoice.pdf", "rb") as f:
    file = warsita.media.upload(f.read(), filename="invoice.pdf", content_type="application/pdf")
warsita.messages.send(to="+6281234567890", document={"media_id": file["id"]})
```

## asyncio

```python
from warsita import AsyncWarsita

async with AsyncWarsita(api_key="wsk_…") as warsita:
    await warsita.messages.send(to="+6281234567890", text="Hello")
    async for state in warsita.sessions.events("ses_…"):  # with a token: live status and QR codes
        print(state)
```

## Personal access tokens

A session API key (`wsk_…`) acts for its own session. A personal access token (`wsp_…`) acts for the whole workspace and manages sessions; name the session for messaging calls:

```python
warsita = Warsita(api_key="wsp_…", session_id="ses_3kV9mQ2pX7aL0zR5tN8w")
sessions = warsita.sessions.list()
warsita.groups.list(session_id=sessions[1]["id"])  # or per call
```

## Receive webhooks

Pass the raw body, not parsed JSON:

```python
from flask import Flask, request
from warsita import verify_webhook

app = Flask(__name__)

@app.post("/webhook")
def webhook():
    event = verify_webhook(request.get_data(), request.headers.get("X-Warsita-Signature"), WEBHOOK_SECRET)
    if event["event"] == "messages.received":
        print(event["data"].get("text"))
    return "", 200
```

`verify_webhook` raises `WebhookVerificationError` on a wrong signature or one older than five minutes.

## What's included

| | |
| --- | --- |
| `messages` | `send`, `list`, `get`, `edit`, `delete`, `resend`, `react`, `mark_read` |
| `media` | `upload`, `get` |
| `account` | `get`, `set_presence`, `set_chat_presence` |
| `contacts` | `list`, `check`, `get`, `picture`, `ids`, `block`, `unblock`, `blocklist` |
| `groups` | `list`, `get`, `create`, `update`, `update_participants`, `set_picture`, `invite_link`, `reset_invite_link`, `invite_info`, `join`, `leave` |
| `sessions` | `list`, `create`, `get`, `update`, `delete`, `connect`, `restart`, `disconnect`, `qr`, `pairing_code`, `regenerate_api_key`, `logs`, `clear_messages`, `events` (live stream) |
| `sessions.webhook` | `get`, `set`, `rotate_secret`, `test`, `deliveries`, `resend` |

Methods return the API's JSON as dicts and lists; responses that hold only `data` are unwrapped. Errors raise `WarsitaError` with the API's `status`, `code` and `message` (and `retry_after` on rate limits). The full reference is at [warsita.com/docs](https://warsita.com/docs).

## Development

`openapi.yaml` is a copy of the published spec (`curl -sf https://warsita.com/openapi.yaml -o openapi.yaml`). `pip install -e ".[test]" && pytest` checks, among other things, that every operation in the spec has a method.
