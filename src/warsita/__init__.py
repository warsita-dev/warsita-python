"""The official Python client for the Warsita WhatsApp API.

    from warsita import Warsita

    warsita = Warsita(api_key="wsk_…")
    warsita.messages.send(to="+6281234567890", text="Hello")

A session API key (``wsk_…``) acts for its session. A personal access token (``wsp_…``) acts for
the workspace: pass ``session_id`` to the client or to each call.
"""

from __future__ import annotations

from typing import Any, Optional

import httpx

from ._resources import Account, Contacts, Groups, Media, Messages, Sessions
from ._transport import VERSION, AsyncTransport, Call, SyncTransport, WarsitaError
from .webhooks import WebhookVerificationError, verify_webhook

__version__ = VERSION
__all__ = ["Warsita", "AsyncWarsita", "WarsitaError", "verify_webhook", "WebhookVerificationError", "OPERATIONS"]


class _Client:
    def __init__(self, transport: Any):
        self._t = transport
        self.messages = Messages(transport)
        self.media = Media(transport)
        self.account = Account(transport)
        self.contacts = Contacts(transport)
        self.groups = Groups(transport)
        self.sessions = Sessions(transport)

    def health(self) -> Any:
        """Whether the API is up."""
        return self._t.request(Call("GET", "/health", idempotent=True))


class Warsita(_Client):
    """The synchronous client. Use it as a context manager, or call ``close()`` when done."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        session_id: Optional[str] = None,
        base_url: Optional[str] = None,
        max_retries: int = 2,
        timeout: float = 60.0,
        http_client: Optional[httpx.Client] = None,
    ):
        super().__init__(SyncTransport(api_key, session_id, base_url, max_retries, timeout, http_client=http_client))

    def close(self) -> None:
        self._t.close()

    def __enter__(self) -> "Warsita":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


class AsyncWarsita(_Client):
    """The asyncio client: every method returns an awaitable, and ``sessions.events`` an async iterator."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        session_id: Optional[str] = None,
        base_url: Optional[str] = None,
        max_retries: int = 2,
        timeout: float = 60.0,
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        super().__init__(AsyncTransport(api_key, session_id, base_url, max_retries, timeout, http_client=http_client))

    async def aclose(self) -> None:
        await self._t.aclose()

    async def __aenter__(self) -> "AsyncWarsita":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.aclose()


#: Each operationId in openapi.yaml and the method that calls it.
OPERATIONS = {
    "sendMessage": "messages.send",
    "listMessages": "messages.list",
    "getMessage": "messages.get",
    "editMessage": "messages.edit",
    "deleteMessage": "messages.delete",
    "resendMessage": "messages.resend",
    "reactToMessage": "messages.react",
    "markRead": "messages.mark_read",
    "uploadMedia": "media.upload",
    "getMedia": "media.get",
    "getAccount": "account.get",
    "setPresence": "account.set_presence",
    "setChatPresence": "account.set_chat_presence",
    "listContacts": "contacts.list",
    "checkContacts": "contacts.check",
    "getContact": "contacts.get",
    "getContactPicture": "contacts.picture",
    "getContactIDs": "contacts.ids",
    "blockContact": "contacts.block",
    "unblockContact": "contacts.unblock",
    "getBlocklist": "contacts.blocklist",
    "listGroups": "groups.list",
    "getGroup": "groups.get",
    "createGroup": "groups.create",
    "updateGroup": "groups.update",
    "updateGroupParticipants": "groups.update_participants",
    "setGroupPicture": "groups.set_picture",
    "getGroupInviteLink": "groups.invite_link",
    "resetGroupInviteLink": "groups.reset_invite_link",
    "getGroupInviteInfo": "groups.invite_info",
    "joinGroup": "groups.join",
    "leaveGroup": "groups.leave",
    "listSessions": "sessions.list",
    "createSession": "sessions.create",
    "getSession": "sessions.get",
    "updateSession": "sessions.update",
    "deleteSession": "sessions.delete",
    "connectSession": "sessions.connect",
    "restartSession": "sessions.restart",
    "disconnectSession": "sessions.disconnect",
    "getSessionQR": "sessions.qr",
    "requestPairingCode": "sessions.pairing_code",
    "regenerateApiKey": "sessions.regenerate_api_key",
    "getSessionLogs": "sessions.logs",
    "streamSessionEvents": "sessions.events",
    "clearMessages": "sessions.clear_messages",
    "getWebhook": "sessions.webhook.get",
    "setWebhook": "sessions.webhook.set",
    "rotateWebhookSecret": "sessions.webhook.rotate_secret",
    "testWebhook": "sessions.webhook.test",
    "listWebhookDeliveries": "sessions.webhook.deliveries",
    "resendWebhookDelivery": "sessions.webhook.resend",
    "health": "health",
}
