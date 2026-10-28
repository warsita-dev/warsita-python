"""One method per API operation. ``OPERATIONS`` maps each operationId in openapi.yaml to its
method; a test keeps the two in step.

The same resource classes serve the sync and the async client: with the async client, each
method returns an awaitable.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from ._transport import Call

Json = Dict[str, Any]


def _p(value: str) -> str:
    return quote(value, safe="")


class _Resource:
    def __init__(self, transport: Any):
        self._t = transport


class Messages(_Resource):
    def send(self, *, idempotency_key: Optional[str] = None, session_id: Optional[str] = None, **message: Any) -> Any:
        """Queue a message: ``send(to="+62…", text="Hi")``, or ``image={"url": …}``, ``poll={…}``, ….

        An Idempotency-Key is generated (or pass your own), so the client retries safely: a
        repeat returns the message the first request queued. With a personal access token,
        ``rotate=True`` sends from the workspace's sender rotation instead of a session; the
        answer's ``from`` is the number it goes out from.
        """
        key = idempotency_key or str(uuid.uuid4())
        scoped = not message.get("rotate")
        return self._t.request(
            Call("POST", "/v1/messages", body=message, headers={"Idempotency-Key": key}, scoped=scoped, idempotent=True), session_id
        )

    def list(self, *, limit: Optional[int] = None, status: Optional[str] = None, before: Optional[str] = None, session_id: Optional[str] = None) -> Any:
        return self._t.request(
            Call("GET", "/v1/messages", query={"limit": limit, "status": status, "before": before}, scoped=True, idempotent=True), session_id
        )

    def get(self, id: str, *, session_id: Optional[str] = None) -> Any:
        """A message by id. A token needs no session for this (``session_id`` is ignored), so
        messages sent with rotation are found too."""
        return self._t.request(Call("GET", f"/v1/messages/{_p(id)}", idempotent=True), session_id)

    def edit(self, id: str, text: str, *, session_id: Optional[str] = None) -> Any:
        """Change a sent text message, within 20 minutes of sending."""
        return self._t.request(Call("PATCH", f"/v1/messages/{_p(id)}", body={"text": text}, scoped=True), session_id)

    def delete(self, id: str, *, session_id: Optional[str] = None) -> Any:
        """Delete a sent message for everyone in the chat."""
        return self._t.request(Call("DELETE", f"/v1/messages/{_p(id)}", scoped=True), session_id)

    def resend(self, id: str, *, session_id: Optional[str] = None) -> Any:
        """Queue a failed message again as a new message."""
        return self._t.request(Call("POST", f"/v1/messages/{_p(id)}/resend", scoped=True), session_id)

    def react(self, message_id: str, emoji: str, *, chat: Optional[str] = None, sender: Optional[str] = None, session_id: Optional[str] = None) -> Any:
        """React to a message; an empty emoji removes the reaction."""
        body = {"message_id": message_id, "emoji": emoji, "chat": chat, "sender": sender}
        return self._t.request(Call("POST", "/v1/messages/react", body={k: v for k, v in body.items() if v is not None}, scoped=True), session_id)

    def mark_read(self, chat: str, ids: List[str], *, sender: Optional[str] = None, session_id: Optional[str] = None) -> Any:
        body: Json = {"chat": chat, "ids": ids}
        if sender:
            body["sender"] = sender
        return self._t.request(Call("POST", "/v1/messages/read", body=body, scoped=True), session_id)


class Media(_Resource):
    def upload(self, content: bytes, *, filename: str = "file", content_type: str = "application/octet-stream") -> Any:
        """Upload a file of up to 30 MB to send with ``media_id``; it is kept for 7 days."""
        return self._t.request(Call("POST", "/v1/media", files={"file": (filename, content, content_type)}))

    def get(self, id: str) -> Any:
        """A file, with a download link valid for an hour."""
        return self._t.request(Call("GET", f"/v1/media/{_p(id)}", idempotent=True))


class Account(_Resource):
    def get(self, *, session_id: Optional[str] = None) -> Any:
        return self._t.request(Call("GET", "/v1/account", scoped=True, idempotent=True), session_id)

    def set_presence(self, state: str, *, session_id: Optional[str] = None) -> Any:
        """Show the account online (``available``) or offline (``unavailable``)."""
        return self._t.request(Call("POST", "/v1/presence", body={"state": state}, scoped=True), session_id)

    def set_chat_presence(self, chat: str, state: str, *, session_id: Optional[str] = None) -> Any:
        """Show ``typing`` or ``recording`` in a chat, or stop it (``paused``)."""
        return self._t.request(Call("POST", "/v1/presence/chat", body={"chat": chat, "state": state}, scoped=True), session_id)


class Contacts(_Resource):
    def list(self, *, session_id: Optional[str] = None) -> Any:
        return self._t.request(Call("GET", "/v1/contacts", scoped=True, idempotent=True), session_id)

    def check(self, phones: List[str], *, session_id: Optional[str] = None) -> Any:
        """Which of up to 50 phone numbers use WhatsApp."""
        return self._t.request(Call("POST", "/v1/contacts/check", body={"phones": phones}, scoped=True, idempotent=True), session_id)

    def get(self, jid: str, *, session_id: Optional[str] = None) -> Any:
        return self._t.request(Call("GET", f"/v1/contacts/{_p(jid)}", scoped=True, idempotent=True), session_id)

    def picture(self, jid: str, *, session_id: Optional[str] = None) -> Any:
        return self._t.request(Call("GET", f"/v1/contacts/{_p(jid)}/picture", scoped=True, idempotent=True), session_id)

    def ids(self, jid: str, *, session_id: Optional[str] = None) -> Any:
        """A person's phone number and LID, from either."""
        return self._t.request(Call("GET", f"/v1/contacts/{_p(jid)}/ids", scoped=True, idempotent=True), session_id)

    def block(self, jid: str, *, session_id: Optional[str] = None) -> Any:
        return self._t.request(Call("POST", f"/v1/contacts/{_p(jid)}/block", scoped=True), session_id)

    def unblock(self, jid: str, *, session_id: Optional[str] = None) -> Any:
        return self._t.request(Call("POST", f"/v1/contacts/{_p(jid)}/unblock", scoped=True), session_id)

    def blocklist(self, *, session_id: Optional[str] = None) -> Any:
        return self._t.request(Call("GET", "/v1/contacts/blocklist", scoped=True, idempotent=True), session_id)


class Groups(_Resource):
    def list(self, *, session_id: Optional[str] = None) -> Any:
        return self._t.request(Call("GET", "/v1/groups", scoped=True, idempotent=True), session_id)

    def get(self, jid: str, *, session_id: Optional[str] = None) -> Any:
        return self._t.request(Call("GET", f"/v1/groups/{_p(jid)}", scoped=True, idempotent=True), session_id)

    def create(self, name: str, participants: List[str], *, session_id: Optional[str] = None) -> Any:
        return self._t.request(Call("POST", "/v1/groups", body={"name": name, "participants": participants}, scoped=True), session_id)

    def update(self, jid: str, *, session_id: Optional[str] = None, **changes: Any) -> Any:
        """Change any of ``name``, ``topic`` (description), ``announce`` and ``locked``."""
        return self._t.request(Call("PATCH", f"/v1/groups/{_p(jid)}", body=changes, scoped=True), session_id)

    def update_participants(self, jid: str, action: str, participants: List[str], *, session_id: Optional[str] = None) -> Any:
        """``add``, ``remove``, ``promote`` or ``demote`` people; answers with each person's outcome."""
        body = {"action": action, "participants": participants}
        return self._t.request(Call("POST", f"/v1/groups/{_p(jid)}/participants", body=body, scoped=True), session_id)

    def set_picture(self, jid: str, *, url: Optional[str] = None, media_id: Optional[str] = None, session_id: Optional[str] = None) -> Any:
        """Set the picture from a JPEG, by ``url`` or ``media_id``."""
        body = {"url": url} if url else {"media_id": media_id}
        return self._t.request(Call("PUT", f"/v1/groups/{_p(jid)}/picture", body=body, scoped=True), session_id)

    def invite_link(self, jid: str, *, session_id: Optional[str] = None) -> Any:
        return self._t.request(Call("GET", f"/v1/groups/{_p(jid)}/invite-link", scoped=True, idempotent=True), session_id)

    def reset_invite_link(self, jid: str, *, session_id: Optional[str] = None) -> Any:
        """Replace the invite link; the old one stops working."""
        return self._t.request(Call("POST", f"/v1/groups/{_p(jid)}/invite-link/reset", scoped=True), session_id)

    def invite_info(self, link: str, *, session_id: Optional[str] = None) -> Any:
        """The group an invite link leads to, without joining."""
        return self._t.request(Call("GET", "/v1/groups/invite-info", query={"link": link}, scoped=True, idempotent=True), session_id)

    def join(self, link: str, *, session_id: Optional[str] = None) -> Any:
        return self._t.request(Call("POST", "/v1/groups/join", body={"link": link}, scoped=True), session_id)

    def leave(self, jid: str, *, session_id: Optional[str] = None) -> Any:
        return self._t.request(Call("POST", f"/v1/groups/{_p(jid)}/leave", scoped=True), session_id)


class Webhook(_Resource):
    """A session's webhook. Personal access token only."""

    def get(self, session_id: str) -> Any:
        return self._t.request(Call("GET", f"/v1/sessions/{_p(session_id)}/webhook", idempotent=True))

    def set(self, session_id: str, *, url: str, events: List[str]) -> Any:
        return self._t.request(Call("PUT", f"/v1/sessions/{_p(session_id)}/webhook", body={"url": url, "events": events}))

    def rotate_secret(self, session_id: str) -> Any:
        return self._t.request(Call("POST", f"/v1/sessions/{_p(session_id)}/webhook/secret"))

    def test(self, session_id: str, event: str) -> Any:
        """Send a signed sample of an event to the webhook now."""
        return self._t.request(Call("POST", f"/v1/sessions/{_p(session_id)}/webhook/test", body={"event": event}))

    def deliveries(self, session_id: str) -> Any:
        return self._t.request(Call("GET", f"/v1/sessions/{_p(session_id)}/webhook/deliveries", idempotent=True))

    def resend(self, session_id: str, delivery_id: str) -> Any:
        """Send a delivered or failed event again, as a new delivery."""
        return self._t.request(Call("POST", f"/v1/sessions/{_p(session_id)}/webhook/deliveries/{_p(delivery_id)}/resend"))


class Sessions(_Resource):
    """Linking and managing WhatsApp numbers. Personal access token only."""

    def __init__(self, transport: Any):
        super().__init__(transport)
        self.webhook = Webhook(transport)

    def list(self) -> Any:
        return self._t.request(Call("GET", "/v1/sessions", idempotent=True))

    def create(self, **session: Any) -> Any:
        """Create a session; the answer holds its API key, shown only this once."""
        return self._t.request(Call("POST", "/v1/sessions", body=session))

    def get(self, id: str) -> Any:
        return self._t.request(Call("GET", f"/v1/sessions/{_p(id)}", idempotent=True))

    def update(self, id: str, **changes: Any) -> Any:
        return self._t.request(Call("PATCH", f"/v1/sessions/{_p(id)}", body=changes))

    def delete(self, id: str) -> Any:
        return self._t.request(Call("DELETE", f"/v1/sessions/{_p(id)}"))

    def connect(self, id: str) -> Any:
        return self._t.request(Call("POST", f"/v1/sessions/{_p(id)}/connect"))

    def restart(self, id: str) -> Any:
        return self._t.request(Call("POST", f"/v1/sessions/{_p(id)}/restart"))

    def disconnect(self, id: str) -> Any:
        """Log the linked number out; linking it again needs a new scan."""
        return self._t.request(Call("POST", f"/v1/sessions/{_p(id)}/disconnect"))

    def qr(self, id: str) -> Any:
        return self._t.request(Call("GET", f"/v1/sessions/{_p(id)}/qr", idempotent=True))

    def pairing_code(self, id: str, phone: str) -> Any:
        """An 8-character code to type in on the phone instead of scanning."""
        return self._t.request(Call("POST", f"/v1/sessions/{_p(id)}/pairing-code", body={"phone": phone}))

    def regenerate_api_key(self, id: str) -> Any:
        """Replace the session's API key; the old one stops working at once."""
        return self._t.request(Call("POST", f"/v1/sessions/{_p(id)}/api-key"))

    def logs(self, id: str, *, limit: Optional[int] = None) -> Any:
        return self._t.request(Call("GET", f"/v1/sessions/{_p(id)}/logs", query={"limit": limit}, idempotent=True))

    def clear_messages(self, id: str) -> Any:
        """Delete the session's finished messages from its log."""
        return self._t.request(Call("DELETE", f"/v1/sessions/{_p(id)}/messages"))

    def events(self, id: str) -> Any:
        """Stream the session's live state (status, QR code); each item is one event's JSON."""
        return self._t.events(Call("GET", f"/v1/sessions/{_p(id)}/events", headers={"Accept": "text/event-stream"}))
