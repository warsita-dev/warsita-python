"""The transport: authentication, session_id, retries, errors and unwrapping ``{"data": …}``."""

from __future__ import annotations

import asyncio
import json
import os
import random
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, Iterator, Mapping, Optional, Tuple

import httpx

VERSION = "0.2.0"
DEFAULT_BASE_URL = "https://api.warsita.com"


class WarsitaError(Exception):
    """An error answered by the API, with its stable ``code``, or a network failure (``status`` 0)."""

    def __init__(self, status: int, code: str, message: str, retry_after: Optional[float] = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.retry_after = retry_after

    def __repr__(self) -> str:
        return f"WarsitaError(status={self.status}, code={self.code!r}, message={self.message!r})"


@dataclass
class Call:
    method: str
    path: str
    query: Mapping[str, Any] = field(default_factory=dict)
    body: Any = None
    files: Optional[Dict[str, Tuple[str, bytes, str]]] = None
    headers: Mapping[str, str] = field(default_factory=dict)
    scoped: bool = False  # acts for one session: with a token, session_id is added
    idempotent: bool = False  # safe to send twice: GETs, and sends with an Idempotency-Key


def unwrap(response: httpx.Response) -> Any:
    if response.status_code == 204 or not response.content:
        return None
    body = response.json()
    if isinstance(body, dict) and list(body.keys()) == ["data"]:
        return body["data"]
    return body


def error_of(response: httpx.Response) -> WarsitaError:
    retry_after = _retry_after(response)
    code, message = "http_error", f"Warsita: HTTP {response.status_code}"
    try:
        err = response.json().get("error") or {}
        code, message = err.get("code", code), err.get("message", message)
    except ValueError:
        pass
    return WarsitaError(response.status_code, code, message, retry_after)


def _retry_after(response: httpx.Response) -> Optional[float]:
    try:
        return float(response.headers["Retry-After"])
    except (KeyError, ValueError):
        return None


def _retryable(call: Call, response: httpx.Response) -> bool:
    # A rate-limited call was not processed, so any call may retry; server errors only when
    # repeating it is harmless.
    return response.status_code == 429 or (call.idempotent and response.status_code in (500, 503, 504))


def _delay(attempt: int, response: Optional[httpx.Response]) -> float:
    if response is not None:
        after = _retry_after(response)
        if after is not None:
            return after
    return 0.5 * 2**attempt + random.random() * 0.25


class _Base:
    def __init__(self, api_key: Optional[str], session_id: Optional[str], base_url: Optional[str], max_retries: int, timeout: float):
        api_key = api_key or os.environ.get("WARSITA_API_KEY")
        if not api_key:
            raise ValueError("Warsita: pass api_key or set WARSITA_API_KEY.")
        self.api_key = api_key
        self.session_id = session_id
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.max_retries = max_retries
        self.timeout = timeout

    @property
    def uses_token(self) -> bool:
        """A session API key already picks its session; a token needs session_id."""
        return not self.api_key.startswith("wsk_")

    def _build(self, call: Call, session_id: Optional[str]) -> Dict[str, Any]:
        query = {k: v for k, v in call.query.items() if v is not None}
        body = call.body
        if call.scoped and self.uses_token:
            sid = session_id or self.session_id
            if not sid:
                raise ValueError("Warsita: pass session_id (to the client or the call) when using a personal access token.")
            if call.method == "POST" and call.files is None:
                body = {**(body or {}), "session_id": sid}
            else:
                query["session_id"] = sid
        headers = {"Authorization": f"Bearer {self.api_key}", "User-Agent": f"warsita-python/{VERSION}", **call.headers}
        req: Dict[str, Any] = {"method": call.method, "url": self.base_url + call.path, "params": query, "headers": headers}
        if call.files is not None:
            req["files"] = call.files
        elif body is not None:
            req["json"] = body
        return req


class SyncTransport(_Base):
    def __init__(self, *args: Any, http_client: Optional[httpx.Client] = None):
        super().__init__(*args)
        self.http = http_client or httpx.Client(timeout=self.timeout)

    def request(self, call: Call, session_id: Optional[str] = None) -> Any:
        return unwrap(self.send(call, session_id))

    def send(self, call: Call, session_id: Optional[str] = None, stream: bool = False) -> httpx.Response:
        req = self._build(call, session_id)
        attempt = 0
        while True:
            try:
                response = self.http.send(self.http.build_request(**req), stream=stream)
            except httpx.TransportError as err:
                if call.idempotent and attempt < self.max_retries:
                    time.sleep(_delay(attempt, None))
                    attempt += 1
                    continue
                raise WarsitaError(0, "network_error", f"Warsita: {err}") from err
            if response.is_success:
                return response
            if stream:
                response.read()
            if _retryable(call, response) and attempt < self.max_retries:
                time.sleep(_delay(attempt, response))
                attempt += 1
                continue
            raise error_of(response)

    def events(self, call: Call) -> Iterator[Dict[str, Any]]:
        response = self.send(call, stream=True)
        try:
            data: list = []
            for line in response.iter_lines():
                if line.startswith("data:"):
                    data.append(line[5:].lstrip())
                elif line == "" and data:
                    yield json.loads("\n".join(data))
                    data = []
        finally:
            response.close()

    def close(self) -> None:
        self.http.close()


class AsyncTransport(_Base):
    def __init__(self, *args: Any, http_client: Optional[httpx.AsyncClient] = None):
        super().__init__(*args)
        self.http = http_client or httpx.AsyncClient(timeout=self.timeout)

    async def request(self, call: Call, session_id: Optional[str] = None) -> Any:
        return unwrap(await self.send(call, session_id))

    async def send(self, call: Call, session_id: Optional[str] = None, stream: bool = False) -> httpx.Response:
        req = self._build(call, session_id)
        attempt = 0
        while True:
            try:
                response = await self.http.send(self.http.build_request(**req), stream=stream)
            except httpx.TransportError as err:
                if call.idempotent and attempt < self.max_retries:
                    await asyncio.sleep(_delay(attempt, None))
                    attempt += 1
                    continue
                raise WarsitaError(0, "network_error", f"Warsita: {err}") from err
            if response.is_success:
                return response
            if stream:
                await response.aread()
            if _retryable(call, response) and attempt < self.max_retries:
                await asyncio.sleep(_delay(attempt, response))
                attempt += 1
                continue
            raise error_of(response)

    async def events(self, call: Call) -> AsyncIterator[Dict[str, Any]]:
        response = await self.send(call, stream=True)
        try:
            data: list = []
            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    data.append(line[5:].lstrip())
                elif line == "" and data:
                    yield json.loads("\n".join(data))
                    data = []
        finally:
            await response.aclose()

    async def aclose(self) -> None:
        await self.http.aclose()
